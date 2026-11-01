"""Pure checks: how much Anki was done today and whether LeetCode was solved."""
import datetime as dt
import json
import os
import shutil
import sqlite3
import tempfile
import time
import urllib.request

LEETCODE_URL = "https://leetcode.com/graphql"
LEETCODE_QUERY = (
    "query($username:String!,$limit:Int!)"
    "{recentAcSubmissionList(username:$username,limit:$limit){title timestamp}}"
)


def logical_date(moment, rollover_hour):
    """The learning day a moment belongs to; before the rollover it is still yesterday."""
    return (moment - dt.timedelta(hours=rollover_hour)).date()


def day_start(moment, rollover_hour):
    start = dt.datetime.combine(logical_date(moment, rollover_hour), dt.time(rollover_hour))
    return start


def anki_db_path(profile):
    return os.path.join(os.environ["APPDATA"], "Anki2", profile, "collection.anki2")


def anki_signature(db_path):
    """Changes whenever Anki commits, so unchanged collections need no new copy."""
    parts = []
    for path in (db_path, db_path + "-wal"):
        if os.path.exists(path):
            stat = os.stat(path)
            parts.append((stat.st_mtime_ns, stat.st_size))
    return tuple(parts)


def _snapshot(db_path, target):
    # Anki keeps the database locked while open, so we read a copy of db + WAL.
    # A checkpoint between the two copies would mix states, hence the retry.
    for _ in range(5):
        before = anki_signature(db_path)
        shutil.copy2(db_path, target)
        if os.path.exists(db_path + "-wal"):
            shutil.copy2(db_path + "-wal", target + "-wal")
        if anki_signature(db_path) == before:
            return
        time.sleep(0.2)
    raise OSError("Anki schreibt gerade, bitte gleich nochmal prüfen")


def check_anki(db_path, settings, now, rollover_hour):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        copy = os.path.join(tmp, "collection.anki2")
        _snapshot(db_path, copy)
        db = sqlite3.connect(copy)
        try:
            return evaluate_anki(db, settings, now, rollover_hour)
        finally:
            db.close()


def _deck_matches(name, prefixes):
    return any(name == p or name.startswith(p + "::") for p in prefixes)


def evaluate_anki(db, settings, now, rollover_hour):
    start_ms = int(day_start(now, rollover_hour).timestamp() * 1000)

    decks = {
        deck_id: name.replace("\x1f", "::")
        for deck_id, name in db.execute("select id, name from decks")
    }
    cards = {
        card
        for card, did, odid in db.execute("select id, did, odid from cards")
        if _deck_matches(decks.get(odid or did, ""), settings["decks"])
    }

    answers = 0
    spent_ms = 0
    # ease 0 marks manual reschedules, which are not learning.
    query = "select cid, time from revlog where ease > 0 and id >= ?"
    for card, taken_ms in db.execute(query, (start_ms,)):
        if card not in cards:
            continue
        spent_ms += taken_ms
        if taken_ms >= settings["min_answer_ms"]:
            answers += 1

    minutes = spent_ms / 60000
    return {
        "done": answers >= settings["cards"] or minutes >= settings["minutes"],
        "detail": f"{answers}/{settings['cards']} Karten oder {minutes:.0f}/{settings['minutes']} Min",
        "error": None,
    }


def parse_leetcode(payload, start):
    submissions = (payload.get("data") or {}).get("recentAcSubmissionList")
    if submissions is None:
        raise ValueError("LeetCode kennt diesen Benutzernamen nicht")
    today = [s["title"] for s in submissions if int(s["timestamp"]) >= start.timestamp()]
    if today:
        return {"done": True, "detail": f"Gelöst: {today[0]}", "error": None}
    return {"done": False, "detail": "Heute noch keine akzeptierte Lösung", "error": None}


def parse_github(events, start):
    for event in events:
        created = dt.datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
        if event["type"] == "PushEvent" and created.timestamp() >= start.timestamp():
            return {"done": True, "detail": f"Push in {event['repo']['name']}", "error": None}
    return {"done": False, "detail": "Heute noch kein öffentlicher Push", "error": None}


def check_github(username, start):
    request = urllib.request.Request(
        f"https://api.github.com/users/{username}/events/public?per_page=100",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "productivity-lock"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return parse_github(json.load(response), start)


def check_leetcode(username, start):
    body = {"query": LEETCODE_QUERY, "variables": {"username": username, "limit": 20}}
    request = urllib.request.Request(
        LEETCODE_URL,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return parse_leetcode(json.load(response), start)
