"""Lernchat: the chat logs one line per session, this counts them per week."""
import datetime as dt
import json
import os
import shutil
import subprocess
import threading

from . import checks

MODES = ("quiz", "feynman", "sprache")
WEEK_DAYS = 7


def log_entry(at, subject, mode, topic, score):
    if mode not in MODES:
        raise ValueError(f"Modus muss einer von {', '.join(MODES)} sein")
    if not 0 <= score <= 1:
        raise ValueError("Der Score liegt zwischen 0 und 1")
    return {"at": at.isoformat(timespec="seconds"), "subject": subject, "mode": mode,
            "topic": topic, "score": round(score, 2)}


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
    language = len({s["day"] for s in passed if s["mode"] == "sprache"})
    needed = max(0, settings["per_week"] - total, settings["language_per_week"] - language)
    return {"total": total, "language": language, "needed": needed,
            "today": any(s["day"] == today for s in passed)}


def status(sessions, today, settings):
    """Required only once the remaining days are just enough to reach the weekly goal."""
    progress = week_progress(sessions, today, settings)
    count = f"{progress['total']}/{settings['per_week']} diese Woche"
    days_left = WEEK_DAYS - today.weekday()
    if progress["today"]:
        return {"done": True, "detail": f"Heute erledigt ({count})"}
    if progress["needed"] == 0:
        return {"done": True, "detail": f"Wochenziel geschafft ({count})"}
    if progress["needed"] < days_left:
        return {"done": True, "detail": f"Heute frei ({count})"}
    language = settings["language_per_week"] - progress["language"]
    extra = ", davon eins in einer Sprache" if language > 0 else ""
    return {"done": False, "detail": f"{count}: heute ist ein Lernchat dran{extra}"}


def find_claude(configured=None):
    home_install = os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")
    candidates = [configured, shutil.which("claude"), home_install]
    return next((path for path in candidates if path and os.path.isfile(path)), None)


class Launcher:
    """Opens Claude Code with /lernchat in its own console window, one at a time."""

    def __init__(self, project_dir, configured=None, popen=subprocess.Popen):
        self.project_dir = project_dir
        self.configured = configured
        self.popen = popen
        self.process = None
        self.lock = threading.Lock()

    def start(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                raise ValueError("Der Lernchat läuft schon")
            path = find_claude(self.configured)
            if not path:
                raise ValueError("Claude Code wurde nicht gefunden. Trag den Pfad in config.json unter "
                                 "lernchat.claude_path ein")
            flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            self.process = self.popen([path, "/lernchat"], cwd=self.project_dir, creationflags=flags)
