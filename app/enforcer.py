"""Closes blocked programs while the day's tasks are open."""
import csv
import logging
import subprocess
import threading
import webbrowser

LOOP_SECONDS = 3
LOCK_PAGE_COOLDOWN_SECONDS = 300
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def running_processes():
    output = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, encoding="mbcs", errors="replace",
        creationflags=NO_WINDOW, check=True,
    ).stdout
    return {row[0].lower() for row in csv.reader(output.splitlines()) if row}


def kill_process(name):
    subprocess.run(
        ["taskkill", "/F", "/IM", name],
        capture_output=True, creationflags=NO_WINDOW, check=False,
    )


class Enforcer:
    def __init__(self, processes, game_process, lister=running_processes, killer=kill_process):
        self.processes = processes
        self.game_process = game_process.lower()
        self.lister = lister
        self.killer = killer
        self.match_grace = False

    def tick(self, unlocked):
        """Returns the processes it closed."""
        if unlocked:
            self.match_grace = True
            return []
        running = self.lister()
        # A match that was allowed when it started may finish after the 4 o'clock reset.
        if self.match_grace and self.game_process in running:
            return []
        self.match_grace = False
        targets = [name for name in self.processes if name.lower() in running]
        for name in targets:
            self.killer(name)
        return targets


def run_loop(service, enforcer, lock_page_url, dry_run, clock, stop=None):
    stop = stop or threading.Event()
    last_page_opened = -LOCK_PAGE_COOLDOWN_SECONDS
    while not stop.wait(LOOP_SECONDS):
        try:
            unlocked = service.status(network=False)["unlocked"]
            if dry_run:
                continue
            closed = enforcer.tick(unlocked)
            if closed:
                logging.info("Geschlossen: %s", ", ".join(closed))
                if clock() - last_page_opened >= LOCK_PAGE_COOLDOWN_SECONDS:
                    last_page_opened = clock()
                    webbrowser.open(lock_page_url)
        except Exception:
            logging.exception("Sperrschleife fehlgeschlagen")
