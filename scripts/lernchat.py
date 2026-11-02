"""Trägt einen Lernchat ein oder zeigt den Stand der Woche. Wird vom Skill /lernchat aufgerufen."""
import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import checks, lernchat  # noqa: E402


def split(text):
    return [part.strip() for part in text.split(";") if part.strip()]


def print_weak_points(path, now):
    points = lernchat.open_weak_points(lernchat.read_entries(path))
    if not points:
        print("Offene Schwächen: keine")
        return
    print("Offene Schwächen (älteste zuerst):")
    for point in points[:10]:
        age = (now - point["at"]).days
        print(f"- {point['point']} ({point['subject']}: {point['topic']}, vor {age} Tagen)")


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    log = commands.add_parser("log")
    log.add_argument("--subject", required=True)
    log.add_argument("--mode", required=True, choices=lernchat.MODES)
    log.add_argument("--topic", required=True)
    log.add_argument("--score", required=True, type=float, help="0 bis 1")
    log.add_argument("--weak", default="", help="Schwächen, getrennt mit ;")
    log.add_argument("--fixed", default="", help="früher schwache Punkte, jetzt richtig, getrennt mit ;")
    args = parser.parse_args()

    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as file:
        config = json.load(file)
    settings = config["lernchat"]
    path = os.path.join(ROOT, "data", "lernchat.jsonl")
    rollover = config["day_rollover_hour"]

    if args.command == "log":
        entry = lernchat.log_entry(dt.datetime.now(), args.subject, args.mode, args.topic, args.score,
                                   split(args.weak), split(args.fixed))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        counted = "zählt" if args.score >= settings["min_score"] else f"zählt nicht (unter {settings['min_score']:.0%})"
        print(f"Eingetragen, {counted}.")

    today = checks.logical_date(dt.datetime.now(), rollover)
    progress = lernchat.week_progress(lernchat.read_sessions(path, rollover), today, settings)
    print(f"Diese Woche: {progress['total']}/{settings['per_week']} Chats, "
          f"davon {progress['language']}/{settings['language_per_week']} in einer Sprache.")
    if progress["attempted_today"] and not progress["today"]:
        print("Heute war noch kein Chat gut genug: nochmal machen, mit den Schwächen.")
    print_weak_points(path, dt.datetime.now())


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        sys.exit(str(error))
