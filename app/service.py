"""Daily state: combines the tasks, runs the timers, remembers what is done."""
import datetime as dt
import json
import os
import re
import threading
import time

from . import checks, history, lernchat

LERNCHAT_HINT = "Der Knopf öffnet Claude Code mit /lernchat."
LEETCODE_TTL_SECONDS = 120
GITHUB_TTL_SECONDS = 300
REMOTE_MIN_REFRESH_SECONDS = 5
JOKER_MIN_REASON_CHARS = 3
TASK_ID = re.compile(r"^[a-z0-9_-]+$")


def _calendar_week(day):
    return dt.date.fromisoformat(day).isocalendar()[:2]


def _custom_task(custom):
    base = {"id": custom["id"], "title": custom["title"]}
    kind = custom["type"]
    if kind == "github":
        return {**base, "kind": "remote", "username": custom["username"], "ttl": GITHUB_TTL_SECONDS}
    if kind not in ("timer", "check"):
        raise ValueError(f"Unbekannter Aufgabentyp: {kind}")
    return {
        **base,
        "kind": "timer",
        "minutes": custom["minutes"] if kind == "timer" else 0,
        "min_note_chars": custom.get("min_note_chars", 3),
        "prompt": custom.get("prompt", "Was hast du gemacht?"),
    }


def build_tasks(config):
    reading = config["reading"]
    tasks = [
        {"id": "anki", "title": "Anki", "kind": "anki",
         "hint": "Auf dem Handy gelernt? Synchronisiere Anki einmal am PC."},
        {"id": "leetcode", "title": "LeetCode", "kind": "remote", "ttl": LEETCODE_TTL_SECONDS,
         "link": "https://leetcode.com/problemset/", "link_text": "Aufgabe aussuchen"},
        {"id": "reading", "title": "Lesen", "kind": "timer", "minutes": reading["minutes"],
         "min_note_chars": reading["min_note_chars"], "prompt": "Was hast du gelesen?"},
    ]
    if config.get("lernchat"):
        tasks.append({"id": "lernchat", "title": "Lernchat", "kind": "lernchat", "hint": LERNCHAT_HINT,
                      "action_path": "/lernchat/start", "action_text": "Lernchat starten"})
    tasks += [_custom_task(custom) for custom in config.get("custom_tasks", [])]
    ids = [task["id"] for task in tasks]
    if len(ids) != len(set(ids)) or not all(TASK_ID.match(task_id) for task_id in ids):
        raise ValueError("Aufgaben-IDs müssen eindeutig sein und dürfen nur a-z, 0-9, _ und - enthalten")
    return tasks


class LockService:
    def __init__(self, config, data_dir, clock=time.time, anki_check=None, leetcode_check=None):
        self.config = config
        self.clock = clock
        self.state_path = os.path.join(data_dir, "state.json")
        self.log_path = os.path.join(data_dir, "notes_log.jsonl")
        self.lernchat_path = os.path.join(data_dir, "lernchat.jsonl")
        self.anki_check = anki_check or self._read_anki
        self.leetcode_check = leetcode_check or checks.check_leetcode
        self.tasks = build_tasks(config)
        self.lock = threading.RLock()
        self.anki_cache = (None, None)
        self.remote_cache = {}
        self.remote_checked_at = {}
        os.makedirs(data_dir, exist_ok=True)
        self.state = self._load_state()

    def _now(self):
        return dt.datetime.fromtimestamp(self.clock())

    def _load_state(self):
        try:
            with open(self.state_path, encoding="utf-8") as file:
                return json.load(file)
        except (OSError, ValueError):
            return {}

    def _save_state(self):
        temp = self.state_path + ".tmp"
        with open(temp, "w", encoding="utf-8") as file:
            json.dump(self.state, file, ensure_ascii=False, indent=2)
        os.replace(temp, self.state_path)

    def _today(self):
        """Today's record; starting a new day resets everything but the long-term records."""
        day = checks.logical_date(self._now(), self.config["day_rollover_hour"]).isoformat()
        if self.state.get("day") != day:
            self.state = {
                "day": day,
                "done": {},
                "timers": {},
                "jokers": self.state.get("jokers", []),
                "history": self.state.get("history", {}),
            }
            self.anki_cache = (None, None)
            self.remote_cache = {}
            self.remote_checked_at = {}
            self._save_state()
        return self.state

    def _read_anki(self, now):
        settings = self.config["anki"]
        rollover = self.config["day_rollover_hour"]
        path = checks.anki_db_path(settings["profile"])
        signature = checks.anki_signature(path)
        if signature and self.anki_cache[0] == signature:
            return self.anki_cache[1]
        result = checks.check_anki(path, settings, now, rollover)
        self.anki_cache = (signature, result)
        return result

    def _anki_status(self, today):
        if "anki" in today["done"]:
            return {"done": True, "detail": today["done"]["anki"], "error": None}
        try:
            result = self.anki_check(self._now())
        except Exception as error:
            return {"done": False, "detail": "Anki konnte nicht gelesen werden", "error": str(error)}
        if result["done"]:
            today["done"]["anki"] = result["detail"]
            self._save_state()
        return result

    def _lernchat_status(self, today):
        if "lernchat" in today["done"]:
            return {"done": True, "detail": today["done"]["lernchat"], "error": None}
        sessions = lernchat.read_sessions(self.lernchat_path, self.config["day_rollover_hour"])
        result = lernchat.status(sessions, dt.date.fromisoformat(today["day"]), self.config["lernchat"])
        if result.get("keep"):
            today["done"]["lernchat"] = result["detail"]
            self._save_state()
        return {"done": result["done"], "detail": result["detail"], "error": None}

    def _run_remote(self, task, start):
        if task["id"] == "leetcode":
            return self.leetcode_check(self.config["leetcode"]["username"], start)
        return checks.check_github(task["username"], start)

    def _refresh_remote(self, task, refresh):
        # Runs outside the state lock so a slow network never stalls the enforcer.
        task_id = task["id"]
        with self.lock:
            today = self._today()
            if task_id in today["done"]:
                return
            age = self.clock() - self.remote_checked_at.get(task_id, 0)
            start = checks.day_start(self._now(), self.config["day_rollover_hour"])
        if age < (REMOTE_MIN_REFRESH_SECONDS if refresh else task["ttl"]):
            return
        self.remote_checked_at[task_id] = self.clock()
        try:
            result = self._run_remote(task, start)
        except Exception as error:
            result = {"done": False, "detail": f"{task['title']} nicht erreichbar", "error": str(error)}
        with self.lock:
            self.remote_cache[task_id] = result
            today = self._today()
            if result["done"]:
                today["done"][task_id] = result["detail"]
                self._save_state()

    def _remote_status(self, task, today):
        if task["id"] in today["done"]:
            return {"done": True, "detail": today["done"][task["id"]], "error": None}
        return self.remote_cache.get(task["id"]) or {"done": False, "detail": "Wird geprüft …", "error": None}

    def _timer_status(self, task, today):
        minutes = task["minutes"]
        timer = today.setdefault("timers", {}).get(task["id"], {})
        base = {"error": None, "minutes": minutes, "prompt": task["prompt"]}
        if timer.get("note"):
            return {**base, "done": True, "detail": timer["note"], "state": "done", "remaining_seconds": 0}
        started = timer.get("started_at")
        if minutes and started is None:
            return {**base, "done": False, "detail": f"{minutes} Minuten, dann ein Satz dazu",
                    "state": "idle", "remaining_seconds": minutes * 60}
        remaining = max(0, round(started + minutes * 60 - self.clock())) if minutes else 0
        return {**base, "done": False, "remaining_seconds": remaining,
                "state": "running" if remaining else "note",
                "detail": "Timer läuft" if remaining else task["prompt"]}

    def _task_status(self, task, today):
        if task["kind"] == "anki":
            result = self._anki_status(today)
        elif task["kind"] == "remote":
            result = self._remote_status(task, today)
        elif task["kind"] == "lernchat":
            result = self._lernchat_status(today)
        else:
            result = self._timer_status(task, today)
        return {
            **result,
            "title": task["title"],
            "kind": task["kind"],
            "hint": task.get("hint"),
            "link": task.get("link"),
            "link_text": task.get("link_text"),
            "action_path": task.get("action_path"),
            "action_text": task.get("action_text"),
        }

    def _joker_status(self, today):
        allowed = self.config["joker"]["per_week"]
        week = _calendar_week(today["day"])
        used = [j for j in today.get("jokers", []) if _calendar_week(j["day"]) == week]
        current = next((j for j in used if j["day"] == today["day"]), None)
        return {
            "active": current is not None,
            "reason": current["reason"] if current else None,
            "left": max(0, allowed - len(used)),
            "per_week": allowed,
        }

    def _required(self, items):
        """How many tasks unlock the day: `required_tasks`, or all of them when it is not set."""
        return min(self.config.get("required_tasks", len(items)), len(items))

    def _record_history(self, today, items, joker):
        finished = sum(item["done"] for item in items.values())
        if finished >= self._required(items):
            result = "done"
        elif joker["active"]:
            result = "joker"
        elif finished:
            result = "partial"
        else:
            return
        entry = {"result": result, "done": finished, "total": len(items)}
        days = today.setdefault("history", {})
        if days.get(today["day"]) != entry:
            days[today["day"]] = entry
            self._save_state()

    def status(self, refresh=False, network=True):
        if network:
            for task in self.tasks:
                if task["kind"] == "remote":
                    self._refresh_remote(task, refresh)
        with self.lock:
            today = self._today()
            items = {task["id"]: self._task_status(task, today) for task in self.tasks}
            joker = self._joker_status(today)
            finished = sum(item["done"] for item in items.values())
            required = self._required(items)
            self._record_history(today, items, joker)
            return {
                "day": today["day"],
                "unlocked": joker["active"] or finished >= required,
                "required": required,
                "checks": items,
                "joker": joker,
                "history": history.summarize(today.get("history", {}), today["day"]),
            }

    def use_joker(self, reason):
        reason = " ".join((reason or "").split())
        with self.lock:
            status = self.status(network=False)
            joker = status["joker"]
            if joker["active"]:
                return joker
            if status["unlocked"]:
                raise ValueError("Heute ist schon alles erledigt")
            if joker["left"] == 0:
                raise ValueError("Der Joker für diese Woche ist schon verbraucht")
            if len(reason) < JOKER_MIN_REASON_CHARS:
                raise ValueError("Schreib bitte kurz dazu, warum du den Joker brauchst")
            today = self._today()
            today.setdefault("jokers", []).append({"day": today["day"], "reason": reason})
            self._save_state()
            return self._joker_status(today)

    def _timer_task(self, task_id):
        for task in self.tasks:
            if task["id"] == task_id and task["kind"] == "timer":
                return task
        raise ValueError("Unbekannte Aufgabe")

    def start_task(self, task_id):
        task = self._timer_task(task_id)
        with self.lock:
            today = self._today()
            today.setdefault("timers", {}).setdefault(task_id, {}).setdefault("started_at", self.clock())
            self._save_state()
            return self._timer_status(task, today)

    def finish_task(self, task_id, note):
        task = self._timer_task(task_id)
        note = " ".join((note or "").split())
        with self.lock:
            today = self._today()
            state = self._timer_status(task, today)["state"]
            if state == "done":
                return self._timer_status(task, today)
            if state != "note":
                raise ValueError("Der Timer ist noch nicht abgelaufen")
            required = task["min_note_chars"]
            if len(note) < required:
                raise ValueError(f"Schreib bitte mindestens {required} Zeichen dazu")
            today["timers"].setdefault(task_id, {})["note"] = note
            self._save_state()
            entry = {"day": today["day"], "task": task_id, "note": note}
            with open(self.log_path, "a", encoding="utf-8") as file:
                file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            return self._timer_status(task, today)
