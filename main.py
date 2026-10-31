"""Starts the lock service. --dry-run only reports and never closes a program."""
import argparse
import json
import logging
import os
import threading
import time

from app.enforcer import Enforcer, run_loop
from app.server import BASE_URL, LockServer
from app.service import LockService
from app.tray import run_tray

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    parser.add_argument("--data-dir", default=os.path.join(ROOT, "data"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    os.makedirs(args.data_dir, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(args.data_dir, "lock.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    with open(args.config, encoding="utf-8") as file:
        config = json.load(file)

    service = LockService(config, args.data_dir)
    enforcer = Enforcer(config["blocked_processes"], config["game_process"])
    server = LockServer(service, os.path.join(ROOT, "extension"))
    threading.Thread(
        target=run_loop,
        args=(service, enforcer, BASE_URL + "/", args.dry_run, time.monotonic),
        daemon=True,
    ).start()
    if not args.dry_run:
        threading.Thread(
            target=run_tray,
            args=(service, BASE_URL + "/", config.get("reminders", [])),
            daemon=True,
        ).start()
    logging.info("Gestartet%s", " (Testlauf)" if args.dry_run else "")
    server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Start fehlgeschlagen")
        raise
