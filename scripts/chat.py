"""Trägt einen Chat ein oder zeigt den Stand. Wird von den Skills /lernchat und /sprachchat aufgerufen.

    python scripts/chat.py lernchat status
    python scripts/chat.py sprachchat log --subject es --mode lernen --topic "Perfekt" --score 0.8 --level A2
"""
import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import checks, chats  # noqa: E402


def split(text):
    return [part.strip() for part in text.split(";") if part.strip()]


def print_weak_points(entries, now, subject=None, label=""):
    points = chats.open_weak_points(entries, subject)
    if not points:
        print(f"Offene Schwächen{label}: keine")
        return
    print(f"Offene Schwächen{label} (älteste zuerst):")
    for point in points[:10]:
        age = (now - point["at"]).days
        print(f"- {point['point']} ({point['topic']}, vor {age} Tagen)")


def print_languages(entries, languages, now):
    levels = chats.latest_levels(entries)
    for code, name in languages.items():
        mine = [entry for entry in entries if entry["subject"] == code]
        if code not in levels and not any(entry["mode"] == "evaluation" for entry in mine):
            print(f"{code} ({name}): noch nicht evaluiert, zuerst die Sprachevaluation machen")
            continue
        last = mine[-1]["at"].date().isoformat() if mine else "nie"
        print(f"{code} ({name}): Niveau {levels.get(code, '?')}, {len(mine)} Chats, zuletzt {last}")
        print_weak_points(entries, now, code, f" {name}")


def print_lectures(entries, settings):
    learned = settings.get("learned_score", 0.7)
    lectures = chats.lecture_progress(entries, learned)
    if lectures:
        print("Stand je Vorlesung:")
        for number, lecture in lectures.items():
            state = "gefestigt" if lecture["solid"] else "erarbeitet" if lecture["learned"] else "angefangen"
            print(f"- VL{number:02d}: {state}, bester Score {lecture['best']:.2f}")
    else:
        print("Stand je Vorlesung: noch keine")
    simulation = chats.simulation_status(entries, learned, settings.get("core_lectures", 6))
    if simulation["ready"]:
        print(f"Prüfungssimulation: bereit ({simulation['simulations']} bisher, "
              f"letzte vor {simulation['since_last']} Chats)")
    else:
        reasons = []
        if simulation["missing"]:
            reasons.append("noch nicht gefestigt: " + ", ".join(f"VL{n:02d}" for n in simulation["missing"]))
        if simulation["weak"] > chats.MAX_WEAK_FOR_SIMULATION:
            reasons.append(f"{simulation['weak']} offene Schwächen")
        print("Prüfungssimulation: noch nicht (" + "; ".join(reasons) + ")")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("chat", choices=sorted(chats.CHATS))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    log = commands.add_parser("log")
    log.add_argument("--subject", required=True, help="Fach, bei sprachchat der Sprachcode")
    log.add_argument("--mode", required=True)
    log.add_argument("--topic", required=True)
    log.add_argument("--score", required=True, type=float, help="0 bis 1")
    log.add_argument("--weak", default="", help="Schwächen, getrennt mit ;")
    log.add_argument("--fixed", default="", help="früher schwache Punkte, jetzt richtig, getrennt mit ;")
    log.add_argument("--level", default="", help="Sprachniveau, nur sprachchat (z. B. B1 oder HSK3)")
    args = parser.parse_args()

    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as file:
        config = json.load(file)
    settings = config[args.chat]
    spec = chats.CHATS[args.chat]
    path = os.path.join(ROOT, "data", f"{args.chat}.jsonl")
    rollover = config["day_rollover_hour"]
    languages = settings.get("languages", {})

    if args.command == "log":
        if languages and args.subject not in languages:
            sys.exit(f"Sprache muss eine von {', '.join(languages)} sein")
        entry = chats.log_entry(dt.datetime.now(), args.subject, args.mode, args.topic, args.score,
                                split(args.weak), split(args.fixed), args.level, spec["modes"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if args.score >= settings["min_score"]:
            print("Eingetragen, zählt für heute.")
        else:
            print(f"Eingetragen, zählt nicht (unter {settings['min_score']:.0%}).")

    now = dt.datetime.now()
    today = checks.logical_date(now, rollover)
    progress = chats.week_progress(chats.read_sessions(path, rollover), today, settings)
    print(f"Diese Woche: {progress['total']}/{settings['per_week']} {spec['title']}s.")
    if progress["attempted_today"] and not progress["today"]:
        print("Heute war noch kein Chat gut genug: nochmal machen, mit den Schwächen.")
    entries = chats.read_entries(path)
    if languages:
        print_languages(entries, languages, now)
    else:
        print_lectures(entries, settings)
        print_weak_points(entries, now)


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        sys.exit(str(error))
