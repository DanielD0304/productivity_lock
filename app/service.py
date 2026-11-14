"""Daily state: combines the tasks, runs the timers, remembers what is done."""
import datetime as dt
import json
import os
import re
import threading
import time

from . import checks, history

LEETCODE_TTL_SECONDS = 120
GITHUB_TTL_SECONDS = 300
REMOTE_MIN_REFRESH_SECONDS = 5
JOKER_MIN_REASON_CHARS = 3
TYPING_MAX_REPORT_SECONDS = 60
TYPING_LINK = "https://www.edclub.com/"
PAPERS_LINK = "http://127.0.0.1:47615/papers"
LOG_LINK = "http://127.0.0.1:47615/log"
REVIEW_RATINGS = ("sitzt", "teilweise", "vergessen")
LOG_FIELDS = {"done": "Gemacht", "result": "Ergebnis", "next": "Als Nächstes"}
LOG_MARKER = "<!-- productivity-lock:forschungslog -->"
WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
TERMIN_KINDS = {"meilenstein": "Meilenstein", "frist": "Frist", "pruefung": "Prüfung",
                "treffen": "Treffen", "cluster": "Cluster"}
TASK_ID = re.compile(r"^[a-z0-9_-]+$")


def _calendar_week(day):
    return dt.date.fromisoformat(day).isocalendar()[:2]


def _custom_task(custom):
    base = {"id": custom["id"], "title": custom["title"]}
    kind = custom["type"]
    if kind == "github":
        return {**base, "kind": "remote", "username": custom["username"], "ttl": GITHUB_TTL_SECONDS}
    if kind == "typing":
        return {**base, "kind": "typing", "minutes": custom["minutes"],
                "link": custom.get("link", TYPING_LINK), "link_text": custom.get("link_text", "Zu edclub")}
    if kind == "papers":
        return {**base, "kind": "papers", "file": custom["file"], "path": custom.get("path"),
                "project": custom.get("project"),
                "min_summary_chars": custom.get("min_summary_chars", 150),
                "min_takeaway_chars": custom.get("min_takeaway_chars", 60),
                "link": PAPERS_LINK, "link_text": "Zum Lesepfad"}
    if kind == "paper_review":
        return {**base, "kind": "paper_review", "intervals": custom.get("intervals", [7, 30, 90]),
                "min_recall_chars": custom.get("min_recall_chars", 80),
                "link": PAPERS_LINK, "link_text": "Zum Wiederholen"}
    if kind == "log":
        return {**base, "kind": "log", "file": custom.get("file"), "project": custom.get("project"),
                "min_done_chars": custom.get("min_done_chars", 40),
                "min_other_chars": custom.get("min_other_chars", 10),
                "link": LOG_LINK, "link_text": "Zum Forschungslog"}
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
        self.papers_path = os.path.join(data_dir, "papers_progress.json")
        self.anki_check = anki_check or self._read_anki
        self.leetcode_check = leetcode_check or checks.check_leetcode
        self.tasks = build_tasks(config)
        self.lock = threading.RLock()
        self.anki_cache = (None, None)
        self.remote_cache = {}
        self.remote_checked_at = {}
        os.makedirs(data_dir, exist_ok=True)
        self.state = self._load_state()
        self.paper_progress = self._load_json(self.papers_path)
        self.research_log_path = os.path.join(data_dir, "research_log.json")
        self.research_log = self._load_json(self.research_log_path)
        self.termine_path = config.get("termine_file")

    def _now(self):
        return dt.datetime.fromtimestamp(self.clock())

    @staticmethod
    def _load_json(path):
        try:
            with open(path, encoding="utf-8") as file:
                return json.load(file)
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _save_json(path, data):
        temp = path + ".tmp"
        with open(temp, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temp, path)

    def _load_state(self):
        return self._load_json(self.state_path)

    def _save_state(self):
        self._save_json(self.state_path, self.state)

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

    def _typing_status(self, task, today):
        seconds = today.get("typing", {}).get(task["id"], {}).get("seconds", 0)
        return {"done": seconds >= task["minutes"] * 60, "error": None,
                "detail": f"{seconds // 60}/{task['minutes']} Min getippt"}

    @staticmethod
    def _reading_plan(task):
        """All reading paths with full paper entries. Read on every call, so edits need no restart.

        The file holds either one path (top-level "papers" list) or several under "paths", whose items
        take title, source and link from the shared "papers" catalogue by id.
        """
        with open(task["file"], encoding="utf-8") as file:
            raw = json.load(file)
        if "paths" not in raw:
            raw = {"paths": [{**raw, "id": "main", "title": raw.get("title", "Lesepfad"), "items": raw["papers"]}]}
        catalogue = raw.get("papers", {}) if isinstance(raw.get("papers"), dict) else {}
        paths = []
        for path in raw["paths"]:
            papers = [{**catalogue.get(item["id"], {}), **item} for item in path["items"]]
            for paper in papers:
                paper.setdefault("short", paper["id"])
                paper.setdefault("related", [])
            paths.append({key: value for key, value in path.items() if key != "items"} | {"papers": papers})
        if not paths:
            raise ValueError("Keine Lesepfade in der Datei")
        wanted = task.get("path")
        default = next((path["id"] for path in paths if path["id"] == wanted), paths[0]["id"])
        return {"paths": paths, "default": default}

    @staticmethod
    def _all_papers(plan):
        papers = {}
        for path in plan["paths"]:
            for paper in path["papers"]:
                papers.setdefault(paper["id"], paper)
        return papers

    def _papers_status(self, task, today):
        try:
            plan = self._reading_plan(task)
            papers = self._all_papers(plan)
            path = next(path for path in plan["paths"] if path["id"] == plan["default"])
        except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
            return {"done": False, "detail": "Leseliste konnte nicht gelesen werden", "error": str(error)}
        read_today = [pid for pid, entry in self.paper_progress.items()
                      if entry.get("read_on") == today["day"] and pid in papers]
        if read_today:
            return {"done": True, "detail": f"Heute gelesen: {papers[read_today[0]]['short']}", "error": None}
        unread = [paper for paper in path["papers"] if paper["id"] not in self.paper_progress]
        if not unread:
            # Fall back to the other paths before giving up, and never lock forever on a finished list.
            unread = [paper for paper in papers.values() if paper["id"] not in self.paper_progress]
        if not unread:
            return {"done": True, "detail": "Leseliste komplett. Neue Paper in papers.json eintragen", "error": None}
        return {"done": False, "detail": f"Als Nächstes: {unread[0]['short']}", "error": None}

    def _papers_task(self):
        for task in self.tasks:
            if task["kind"] == "papers":
                return task
        raise ValueError("Keine Paper-Aufgabe eingerichtet")

    def papers(self):
        """The reading plan with progress, for the reading path page."""
        task = self._papers_task()
        with self.lock:
            today = self._today()
            review_task = self._find_task("paper_review")
            review = None
            if review_task:
                schedule = {pid: self._next_review(review_task, entry) for pid, entry in self.paper_progress.items()}
                review = {
                    "due": sorted((pid for pid, day in schedule.items() if day and day <= today["day"]),
                                  key=lambda pid: schedule[pid]),
                    "next": schedule,
                    "min_recall_chars": review_task["min_recall_chars"],
                    "ratings": list(REVIEW_RATINGS),
                }
            return {
                "plan": self._reading_plan(task),
                "progress": self.paper_progress,
                "today": today["day"],
                "min_summary_chars": task["min_summary_chars"],
                "min_takeaway_chars": task["min_takeaway_chars"],
                "project": task.get("project"),
                "review": review,
            }

    def read_paper(self, paper_id, summary, takeaway):
        """Marks a paper as read with notes in the reader's own words; later calls only edit the notes."""
        task = self._papers_task()
        summary = " ".join((summary or "").split())
        takeaway = " ".join((takeaway or "").split())
        if paper_id not in self._all_papers(self._reading_plan(task)):
            raise ValueError("Unbekanntes Paper")
        if len(summary) < task["min_summary_chars"]:
            raise ValueError(f"Die Kernaussage braucht mindestens {task['min_summary_chars']} Zeichen")
        if len(takeaway) < task["min_takeaway_chars"]:
            raise ValueError(f"Der Projektbezug braucht mindestens {task['min_takeaway_chars']} Zeichen")
        with self.lock:
            today = self._today()
            entry = self.paper_progress.setdefault(paper_id, {"read_on": today["day"]})
            entry.update({"summary": summary, "takeaway": takeaway})
            self._save_json(self.papers_path, self.paper_progress)
        return self.papers()

    def _find_task(self, kind):
        return next((task for task in self.tasks if task["kind"] == kind), None)

    @staticmethod
    def _next_review(task, entry):
        """Day the paper is due again, or None once every interval is passed.

        "sitzt" moves to the next interval, "teilweise" repeats it, "vergessen" starts over.
        """
        level, base = 0, entry.get("read_on")
        if not base:
            return None
        for review in entry.get("reviews", []):
            base = review["on"]
            if review["rating"] == "sitzt":
                level += 1
            elif review["rating"] == "vergessen":
                level = 0
        intervals = task["intervals"]
        if level >= len(intervals):
            return None
        return (dt.date.fromisoformat(base) + dt.timedelta(days=intervals[level])).isoformat()

    def _review_status(self, task, today):
        papers_task = self._find_task("papers")
        try:
            papers = self._all_papers(self._reading_plan(papers_task)) if papers_task else {}
        except (OSError, ValueError, KeyError, TypeError) as error:
            return {"done": False, "detail": "Leseliste konnte nicht gelesen werden", "error": str(error)}

        def short(pid):
            return papers.get(pid, {}).get("short", pid)

        day = today["day"]
        reviewed = [pid for pid, entry in self.paper_progress.items()
                    if any(review["on"] == day for review in entry.get("reviews", []))]
        if reviewed:
            return {"done": True, "detail": f"Heute wiederholt: {short(reviewed[0])}", "error": None}
        schedule = {pid: self._next_review(task, entry) for pid, entry in self.paper_progress.items()}
        due = sorted((when, pid) for pid, when in schedule.items() if when and when <= day)
        if due:
            more = f" (+{len(due) - 1} weitere)" if len(due) > 1 else ""
            return {"done": False, "detail": f"Fällig: {short(due[0][1])}{more}", "error": None}
        upcoming = sorted(when for when in schedule.values() if when)
        detail = "Nichts fällig"
        if upcoming:
            detail += f" · nächste am {dt.date.fromisoformat(upcoming[0]).strftime('%d.%m.')}"
        return {"done": True, "detail": detail, "error": None}

    def review_paper(self, paper_id, recall, rating):
        """Records a recall from memory and how well it matched the old notes."""
        task = self._find_task("paper_review")
        if not task:
            raise ValueError("Keine Wiederhol-Aufgabe eingerichtet")
        recall = " ".join((recall or "").split())
        if rating not in REVIEW_RATINGS:
            raise ValueError("Ungültige Bewertung")
        with self.lock:
            today = self._today()
            entry = self.paper_progress.get(paper_id)
            if not entry:
                raise ValueError("Dieses Paper ist noch nicht gelesen")
            due = self._next_review(task, entry)
            if not due or due > today["day"]:
                raise ValueError("Dieses Paper ist heute nicht zum Wiederholen fällig")
            if len(recall) < task["min_recall_chars"]:
                raise ValueError(f"Schreib mindestens {task['min_recall_chars']} Zeichen aus dem Kopf")
            entry.setdefault("reviews", []).append({"on": today["day"], "recall": recall, "rating": rating})
            self._save_json(self.papers_path, self.paper_progress)
        return self.papers()

    # --- Research log ---------------------------------------------------------------------------

    def _log_status(self, task, today):
        entry = self.research_log.get(today["day"])
        if not entry:
            return {"done": False, "detail": "Zwei, drei Sätze: gemacht, Ergebnis, als Nächstes", "error": None}
        text = entry["done"]
        return {"done": True, "detail": text if len(text) <= 90 else text[:88] + " …", "error": None}

    def log_data(self):
        task = self._find_task("log")
        if not task:
            raise ValueError("Kein Forschungslog eingerichtet")
        with self.lock:
            today = self._today()
            entries = [{"day": day, **entry} for day, entry in sorted(self.research_log.items(), reverse=True)]
            return {"today": today["day"], "entries": entries, "fields": LOG_FIELDS, "file": task["file"],
                    "project": task.get("project"),
                    "min_done_chars": task["min_done_chars"], "min_other_chars": task["min_other_chars"]}

    def write_log(self, fields):
        """Saves today's log entry (editable all day) and rewrites the Markdown file."""
        task = self._find_task("log")
        if not task:
            raise ValueError("Kein Forschungslog eingerichtet")
        entry = {key: " ".join(str((fields or {}).get(key) or "").split()) for key in LOG_FIELDS}
        if len(entry["done"]) < task["min_done_chars"]:
            raise ValueError(f"„Gemacht“ braucht mindestens {task['min_done_chars']} Zeichen")
        for key in ("result", "next"):
            if len(entry[key]) < task["min_other_chars"]:
                raise ValueError(f"„{LOG_FIELDS[key]}“ braucht mindestens {task['min_other_chars']} Zeichen")
        with self.lock:
            today = self._today()
            self.research_log[today["day"]] = entry
            self._save_json(self.research_log_path, self.research_log)
            if task["file"]:
                self._write_log_markdown(task["file"], task.get("project"))
        return self.log_data()

    def _write_log_markdown(self, target, project=None):
        # Never overwrite a file someone else wrote.
        if os.path.exists(target):
            with open(target, encoding="utf-8") as file:
                if LOG_MARKER not in file.read(2000):
                    raise ValueError(f"{target} gibt es schon und stammt nicht vom Lock; Eintrag nur im Lock gespeichert")
        lines = [
            f"# Forschungslog {project}" if project else "# Forschungslog", "",
            LOG_MARKER,
            "*Wird vom Productivity Lock geschrieben (http://127.0.0.1:47615/log), neueste Einträge oben. "
            "Änderungen direkt in dieser Datei werden beim nächsten Eintrag überschrieben.*", "",
        ]
        for day, entry in sorted(self.research_log.items(), reverse=True):
            date = dt.date.fromisoformat(day)
            lines += [f"## {WEEKDAYS[date.weekday()]} {date.strftime('%d.%m.%Y')}", ""]
            lines += [f"- **{label}:** {entry[key]}" for key, label in LOG_FIELDS.items()]
            lines.append("")
        temp = target + ".tmp"
        with open(temp, "w", encoding="utf-8") as file:
            file.write("\n".join(lines))
        os.replace(temp, target)

    # --- Deadlines ------------------------------------------------------------------------------

    def _load_termine(self):
        if not self.termine_path or not os.path.exists(self.termine_path):
            return []
        with open(self.termine_path, encoding="utf-8") as file:
            events = json.load(file)
        if not isinstance(events, list):
            raise ValueError("termine.json muss eine Liste sein")
        return events

    def _calendar_today(self):
        # Countdowns use the real date, not the 4 o'clock lock day.
        return self._now().date()

    def _with_countdown(self, event, today):
        start = dt.date.fromisoformat(event["date"])
        end = dt.date.fromisoformat(event.get("end") or event["date"])
        state = "past" if end < today else ("running" if start <= today else "upcoming")
        return {**event, "days": (start - today).days, "end_days": (end - today).days, "state": state}

    def termine(self):
        with self.lock:
            today = self._calendar_today()
            events = sorted(self._load_termine(), key=lambda event: (event["date"], event.get("end") or ""))
            return {"today": today.isoformat(), "kinds": TERMIN_KINDS,
                    "events": [self._with_countdown(event, today) for event in events]}

    def _upcoming_termine(self, limit=3):
        try:
            events = self.termine()["events"]
        except (OSError, ValueError, KeyError, TypeError):
            return []
        return [event for event in events if event["state"] != "past"][:limit]

    def add_termin(self, body):
        body = body or {}
        title = " ".join(str(body.get("title") or "").split())
        note = " ".join(str(body.get("note") or "").split())
        kind = body.get("kind") or "frist"
        try:
            start = dt.date.fromisoformat(str(body.get("date")))
            end = dt.date.fromisoformat(str(body["end"])) if body.get("end") else None
        except ValueError:
            raise ValueError("Ungültiges Datum") from None
        if end and end < start:
            raise ValueError("Das Ende liegt vor dem Anfang")
        if not 3 <= len(title) <= 120:
            raise ValueError("Der Titel braucht 3 bis 120 Zeichen")
        if kind not in TERMIN_KINDS:
            raise ValueError("Unbekannte Art")
        if not self.termine_path:
            raise ValueError("Keine Termin-Datei eingerichtet")
        event = {"id": os.urandom(4).hex(), "date": start.isoformat(), "title": title, "kind": kind}
        if end and end != start:
            event["end"] = end.isoformat()
        if note:
            event["note"] = note[:300]
        with self.lock:
            events = self._load_termine()
            events.append(event)
            self._save_json(self.termine_path, events)
        return self.termine()

    def delete_termin(self, termin_id):
        with self.lock:
            events = self._load_termine()
            kept = [event for event in events if event.get("id") != termin_id]
            if len(kept) == len(events):
                raise ValueError("Unbekannter Termin")
            self._save_json(self.termine_path, kept)
        return self.termine()

    def _task_status(self, task, today):
        if task["kind"] == "anki":
            result = self._anki_status(today)
        elif task["kind"] == "remote":
            result = self._remote_status(task, today)
        elif task["kind"] == "typing":
            result = self._typing_status(task, today)
        elif task["kind"] == "papers":
            result = self._papers_status(task, today)
        elif task["kind"] == "paper_review":
            result = self._review_status(task, today)
        elif task["kind"] == "log":
            result = self._log_status(task, today)
        else:
            result = self._timer_status(task, today)
        credit = today.get("credited", {}).get(task["id"])
        if credit and not result["done"]:
            # Manual one-day credit written into state.json; it disappears with the next day.
            result = {"done": True, "detail": f"Gutgeschrieben: {credit}", "error": None}
        return {
            **result,
            "title": task["title"],
            "kind": task["kind"],
            "hint": task.get("hint"),
            "link": task.get("link"),
            "link_text": task.get("link_text"),
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

    def _record_history(self, today, items, joker):
        finished = sum(item["done"] for item in items.values())
        if finished == len(items):
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
            self._record_history(today, items, joker)
            return {
                "day": today["day"],
                "unlocked": joker["active"] or all(item["done"] for item in items.values()),
                "checks": items,
                "joker": joker,
                "history": history.summarize(today.get("history", {}), today["day"]),
                "termine": self._upcoming_termine(),
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

    def add_typing(self, seconds):
        """Credits seconds of real typing, as counted by the extension, to every typing task."""
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds <= 0:
            raise ValueError("Ungültige Tippzeit")
        with self.lock:
            today = self._today()
            now = self.clock()
            typing = today.setdefault("typing", {})
            for task in self.tasks:
                if task["kind"] != "typing":
                    continue
                entry = typing.setdefault(task["id"], {"seconds": 0})
                # Never more than the time since the last report, so several tabs cannot add up.
                elapsed = now - entry.get("reported_at", now - TYPING_MAX_REPORT_SECONDS)
                entry["seconds"] += int(max(0, min(seconds, elapsed, TYPING_MAX_REPORT_SECONDS)))
                entry["reported_at"] = now
            self._save_state()
            return {task_id: entry["seconds"] for task_id, entry in typing.items()}

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
