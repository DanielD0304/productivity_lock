"""Streak and weekly summary from the per-day history."""
import datetime as dt

ONE_DAY = dt.timedelta(days=1)


def _result(days, day):
    return days.get(day.isoformat(), {}).get("result")


def current_streak(days, today):
    # A joker neither extends nor breaks a streak; an open today does not break it yet.
    streak = 0
    day = today
    while True:
        result = _result(days, day)
        if result == "done":
            streak += 1
        elif result != "joker" and day != today:
            return streak
        day -= ONE_DAY


def best_streak(days, today):
    if not days:
        return 0
    best = run = 0
    day = dt.date.fromisoformat(min(days))
    while day <= today:
        result = _result(days, day)
        if result == "done":
            run += 1
        elif result != "joker" and day != today:
            run = 0
        best = max(best, run)
        day += ONE_DAY
    return best


def week_summary(days, today):
    summary = {"done": 0, "joker": 0, "missed": 0}
    if not days:
        return summary
    first_tracked = dt.date.fromisoformat(min(days))
    day = max(today - dt.timedelta(days=today.weekday()), first_tracked)
    while day <= today:
        result = _result(days, day)
        if result in ("done", "joker"):
            summary[result] += 1
        elif day != today:
            summary["missed"] += 1
        day += ONE_DAY
    return summary


def summarize(days, today_iso):
    today = dt.date.fromisoformat(today_iso)
    return {
        "streak": current_streak(days, today),
        "best": best_streak(days, today),
        "week": week_summary(days, today),
        "days": {day: entry["result"] for day, entry in days.items()},
    }
