"""Lernchat: the chat logs one line per session, this counts them per week."""
import datetime as dt
import json

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
