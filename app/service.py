"""Daily state: combines the checks, runs the reading timer, remembers what is done."""
import datetime as dt
import json
import os
import threading
import time

from . import checks

LEETCODE_TTL_SECONDS = 120
LEETCODE_MIN_REFRESH_SECONDS = 5


class LockService:
    def __init__(self, config, data_dir, clock=time.time, anki_check=None, leetcode_check=None):
        self.config = config
        self.clock = clock
        self.state_path = os.path.join(data_dir, "state.json")
        self.log_path = os.path.join(data_dir, "reading_log.jsonl")
        self.anki_check = anki_check or self._read_anki
        self.leetcode_check = leetcode_check or checks.check_leetcode
        self.lock = threading.RLock()
        self.anki_cache = (None, None)
        self.leetcode_cache = None
        self.leetcode_checked_at = 0
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
        """Today's record; starting a new day resets everything."""
        day = checks.logical_date(self._now(), self.config["day_rollover_hour"]).isoformat()
        if self.state.get("day") != day:
            self.state = {"day": day, "done": {}, "reading": {}}
            self.anki_cache = (None, None)
            self.leetcode_cache = None
            self.leetcode_checked_at = 0
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

    def _refresh_leetcode(self, refresh):
        # Runs outside the state lock so a slow network never stalls the enforcer.
        with self.lock:
            today = self._today()
            if "leetcode" in today["done"]:
                return
            age = self.clock() - self.leetcode_checked_at
            start = checks.day_start(self._now(), self.config["day_rollover_hour"])
        if age < (LEETCODE_MIN_REFRESH_SECONDS if refresh else LEETCODE_TTL_SECONDS):
            return
        self.leetcode_checked_at = self.clock()
        try:
            result = self.leetcode_check(self.config["leetcode"]["username"], start)
        except Exception as error:
            result = {"done": False, "detail": "LeetCode nicht erreichbar", "error": str(error)}
        with self.lock:
            self.leetcode_cache = result
            today = self._today()
            if result["done"]:
                today["done"]["leetcode"] = result["detail"]
                self._save_state()

    def _leetcode_status(self, today):
        if "leetcode" in today["done"]:
            return {"done": True, "detail": today["done"]["leetcode"], "error": None}
        return self.leetcode_cache or {"done": False, "detail": "Wird geprüft …", "error": None}

    def _reading_status(self, today):
        minutes = self.config["reading"]["minutes"]
        reading = today["reading"]
        if reading.get("note"):
            return {"done": True, "detail": reading["note"], "error": None,
                    "state": "done", "remaining_seconds": 0, "minutes": minutes}
        started = reading.get("started_at")
        if started is None:
            return {"done": False, "detail": f"{minutes} Minuten lesen, dann ein Satz dazu", "error": None,
                    "state": "idle", "remaining_seconds": minutes * 60, "minutes": minutes}
        remaining = max(0, round(started + minutes * 60 - self.clock()))
        return {"done": False, "error": None, "minutes": minutes, "remaining_seconds": remaining,
                "state": "running" if remaining else "note",
                "detail": "Timer läuft" if remaining else "Was hast du gelesen?"}

    def status(self, refresh=False, network=True):
        if network:
            self._refresh_leetcode(refresh)
        with self.lock:
            today = self._today()
            anki = self._anki_status(today)
            leetcode = self._leetcode_status(today)
            reading = self._reading_status(today)
            items = {"anki": anki, "leetcode": leetcode, "reading": reading}
            return {
                "day": today["day"],
                "unlocked": all(item["done"] for item in items.values()),
                "checks": items,
            }

    def start_reading(self):
        with self.lock:
            today = self._today()
            today["reading"].setdefault("started_at", self.clock())
            self._save_state()
            return self._reading_status(today)

    def finish_reading(self, note):
        note = " ".join((note or "").split())
        with self.lock:
            today = self._today()
            state = self._reading_status(today)["state"]
            if state == "done":
                return self._reading_status(today)
            if state != "note":
                raise ValueError("Der Timer ist noch nicht abgelaufen")
            required = self.config["reading"]["min_note_chars"]
            if len(note) < required:
                raise ValueError(f"Schreib bitte mindestens {required} Zeichen dazu")
            today["reading"]["note"] = note
            self._save_state()
            with open(self.log_path, "a", encoding="utf-8") as file:
                file.write(json.dumps({"day": today["day"], "note": note}, ensure_ascii=False) + "\n")
            return self._reading_status(today)
