"""Lernchat and Sprachchat: a chat logs one line per session, this counts them per week."""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse

from . import checks

WEEK_DAYS = 7
# id -> checklist title, Claude Code skill the button opens, and the modes a session can have.
CHATS = {
    "lernchat": {"title": "Lernchat", "skill": "/lernchat", "modes": ("lernen", "quiz", "feynman", "simulation")},
    "sprachchat": {"title": "Sprachchat", "skill": "/sprachchat", "modes": ("evaluation", "lernen", "gespraech")},
}


def log_entry(at, subject, mode, topic, score, weak=(), fixed=(), level=None, modes=None):
    """One session. `weak` are points that went wrong, `fixed` are earlier weak points answered right now.

    `level` is the language level the session found or confirmed (Sprachchat only).
    """
    if modes and mode not in modes:
        raise ValueError(f"Modus muss einer von {', '.join(modes)} sein")
    if not 0 <= score <= 1:
        raise ValueError("Der Score liegt zwischen 0 und 1")
    entry = {"at": at.isoformat(timespec="seconds"), "subject": subject, "mode": mode,
             "topic": topic, "score": round(score, 2), "weak": list(weak), "fixed": list(fixed)}
    if level:
        entry["level"] = level
    return entry


def read_entries(path):
    """All readable log lines, oldest first, with `at` parsed."""
    try:
        with open(path, encoding="utf-8") as file:
            lines = file.read().splitlines()
    except OSError:
        return []
    entries = []
    for line in lines:
        try:
            entry = json.loads(line)
            entry["at"] = dt.datetime.fromisoformat(entry["at"])
            float(entry["score"])
            entries.append(entry)
        except (ValueError, KeyError, TypeError):
            continue
    return sorted(entries, key=lambda entry: entry["at"])


LECTURE = re.compile(r"\bVL ?0*(\d{1,2})\b", re.IGNORECASE)
SOLID_SCORE = 0.85
MAX_WEAK_FOR_SIMULATION = 2


def lecture_progress(entries, min_score):
    """Per lecture number named in a topic (e.g. "VL03 ..."): learned once a session passed,
    solid once a quiz, Feynman round or simulation reached SOLID_SCORE."""
    lectures = {}
    for entry in entries:
        score = float(entry["score"])
        for number in {int(match) for match in LECTURE.findall(entry.get("topic", ""))}:
            lecture = lectures.setdefault(number, {"learned": False, "solid": False, "best": 0.0})
            lecture["best"] = max(lecture["best"], score)
            lecture["learned"] = lecture["learned"] or score >= min_score
            if entry["mode"] in ("quiz", "feynman", "simulation") and score >= SOLID_SCORE:
                lecture["solid"] = True
    return dict(sorted(lectures.items()))


def simulation_status(entries, min_score, core_lectures):
    """Exam simulations start once every core lecture is solid and hardly any weak point is open."""
    lectures = lecture_progress(entries, min_score)
    missing = [n for n in range(1, core_lectures + 1) if not lectures.get(n, {}).get("solid")]
    weak = len(open_weak_points(entries))
    since = 0
    for entry in reversed(entries):
        if entry["mode"] == "simulation":
            break
        since += 1
    ready = not missing and weak <= MAX_WEAK_FOR_SIMULATION
    return {"ready": ready, "missing": missing, "weak": weak,
            "simulations": sum(entry["mode"] == "simulation" for entry in entries), "since_last": since}


def latest_levels(entries):
    """The most recent level per subject, from the newest session that named one."""
    return {entry["subject"]: entry["level"] for entry in entries if entry.get("level")}


def open_weak_points(entries, subject=None):
    """Weak points no later session has marked as fixed, oldest first."""
    open_points = {}
    for entry in entries:
        if subject is not None and entry.get("subject") != subject:
            continue
        for point in entry.get("fixed", []):
            open_points.pop(str(point).strip().lower(), None)
        for point in entry.get("weak", []):
            key = str(point).strip().lower()
            if key:
                open_points[key] = {"point": str(point).strip(), "at": entry["at"],
                                    "subject": entry.get("subject", ""), "topic": entry.get("topic", "")}
    return sorted(open_points.values(), key=lambda point: point["at"])


def read_sessions(path, rollover_hour):
    """Sessions with their learning day; unreadable lines are skipped."""
    try:
        with open(path, encoding="utf-8") as file:
            lines = file.read().splitlines()
    except OSError:
        return []
    sessions = []
    for line in lines:
        try:
            entry = json.loads(line)
            moment = dt.datetime.fromisoformat(entry["at"])
            sessions.append({
                "day": checks.logical_date(moment, rollover_hour),
                "mode": entry["mode"],
                "score": float(entry["score"]),
            })
        except (ValueError, KeyError, TypeError):
            continue
    return sessions


def week_progress(sessions, today, settings):
    """Distinct days with a passed session this week; two chats on one day count once."""
    monday = today - dt.timedelta(days=today.weekday())
    passed = [s for s in sessions if monday <= s["day"] <= today and s["score"] >= settings["min_score"]]
    total = len({s["day"] for s in passed})
    needed = max(0, settings["per_week"] - total)
    return {"total": total, "needed": needed,
            "today": any(s["day"] == today for s in passed),
            "attempted_today": any(s["day"] == today for s in sessions)}


def status(sessions, today, settings, title="Lernchat"):
    """Required only once the remaining days are just enough to reach the weekly goal."""
    progress = week_progress(sessions, today, settings)
    count = f"{progress['total']}/{settings['per_week']} diese Woche"
    days_left = WEEK_DAYS - today.weekday()
    if progress["today"]:
        return {"done": True, "keep": True, "detail": f"Heute erledigt ({count})"}
    if progress["attempted_today"]:
        return {"done": False, "detail": f"Der {title} heute war zu schwach (unter {settings['min_score']:.0%}), "
                                         "bitte nochmal mit den Schwächen"}
    if progress["needed"] == 0:
        return {"done": True, "detail": f"Wochenziel geschafft ({count})"}
    if progress["needed"] < days_left:
        return {"done": True, "detail": f"Heute frei ({count})"}
    return {"done": False, "detail": f"{count}: heute ist ein {title} dran"}


def find_claude(configured=None):
    home_install = os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")
    candidates = [configured, shutil.which("claude"), home_install]
    return next((path for path in candidates if path and os.path.isfile(path)), None)


class DesktopLauncher:
    """Opens a new Claude Code session in the Claude desktop app with the skill prefilled.

    The app asks once to confirm the folder and waits for Enter; it cannot be watched or closed from here.
    """

    def __init__(self, project_dir, skill, opener=None):
        self.url = "claude://code/new?" + urllib.parse.urlencode({"q": skill, "folder": project_dir},
                                                                 quote_via=urllib.parse.quote)
        self.opener = opener or os.startfile

    def running(self):
        return False

    def start(self):
        try:
            self.opener(self.url)
        except OSError as error:
            raise ValueError(f"Die Claude-App ließ sich nicht öffnen: {error}") from error

    def stop(self):
        raise ValueError("Ein Chat in der Claude-App wird dort geschlossen")


def kill_tree(pid):
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)


class Launcher:
    """Opens Claude Code with a chat skill in its own console window, one at a time.

    Once the chat has logged a passed session, the window closes by itself after a short grace period.
    """

    def __init__(self, project_dir, skill="/lernchat", configured=None, log_path=None, min_score=0.7,
                 grace_seconds=15, popen=subprocess.Popen, kill=kill_tree, sleep=time.sleep, model=None):
        self.project_dir = project_dir
        self.skill = skill
        self.model = model
        self.configured = configured
        self.log_path = log_path
        self.min_score = min_score
        self.grace_seconds = grace_seconds
        self.popen = popen
        self.kill = kill
        self.sleep = sleep
        self.process = None
        self.lock = threading.Lock()

    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self):
        with self.lock:
            if self.running():
                raise ValueError("Der Chat läuft schon. Schließ das Fenster oder beende ihn hier")
            path = find_claude(self.configured)
            if not path:
                raise ValueError("Claude Code wurde nicht gefunden. Trag den Pfad in config.json unter "
                                 "claude_path ein")
            flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            offset = self._log_size()
            command = [path, "--model", self.model, self.skill] if self.model else [path, self.skill]
            self.process = self.popen(command, cwd=self.project_dir, creationflags=flags)
            if self.log_path:
                threading.Thread(target=self._close_when_done, args=(self.process, offset), daemon=True).start()

    def stop(self):
        with self.lock:
            if not self.running():
                raise ValueError("Es läuft kein Chat")
            self.kill(self.process.pid)

    def _log_size(self):
        try:
            return os.path.getsize(self.log_path) if self.log_path else 0
        except OSError:
            return 0

    def _passed_since(self, offset):
        try:
            with open(self.log_path, "rb") as file:
                file.seek(offset)
                lines = file.read().decode("utf-8", "replace").splitlines()
        except OSError:
            return False
        for line in lines:
            try:
                if float(json.loads(line)["score"]) >= self.min_score:
                    return True
            except (ValueError, KeyError, TypeError):
                continue
        return False

    def _close_when_done(self, process, offset):
        while process.poll() is None:
            if self._passed_since(offset):
                self.sleep(self.grace_seconds)
                if process.poll() is None:
                    self.kill(process.pid)
                return
            self.sleep(3)
