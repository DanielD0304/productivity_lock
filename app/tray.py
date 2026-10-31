"""Tray icon with today's progress, plus reminders while something is still open."""
import datetime as dt
import logging
import threading
import webbrowser

LOOP_SECONDS = 5
ICON_SIZE = 64
UNLOCKED_COLOR = "#1f6f54"
LOCKED_COLOR = "#a8321f"


def open_tasks(status):
    return [check["title"] for check in status["checks"].values() if not check["done"]]


def progress_text(status):
    checks = status["checks"]
    finished = len(checks) - len(open_tasks(status))
    return f"{finished} von {len(checks)} erledigt"


def tooltip(status):
    state = "Joker aktiv" if status["joker"]["active"] else progress_text(status)
    return f"Productivity Lock: {state} · Serie {status['history']['streak']}"


def icon_label(status):
    if status["joker"]["active"]:
        return "J"
    return str(len(status["checks"]) - len(open_tasks(status)))


def reminder_due(now, times, sent):
    """True when a reminder time has newly passed; a late start sends only one reminder."""
    passed = {moment for moment in times if now.strftime("%H:%M") >= moment}
    new = passed - sent
    sent |= passed
    return bool(new)


def draw_icon(status):
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    color = UNLOCKED_COLOR if status["unlocked"] else LOCKED_COLOR
    draw.ellipse((0, 0, ICON_SIZE - 1, ICON_SIZE - 1), fill=color)
    font = ImageFont.load_default(size=44)
    center = ICON_SIZE / 2
    draw.text((center, center), icon_label(status), fill="white", font=font, anchor="mm")
    return image


def _menu_items(pystray, service, url):
    status = service.status(network=False)
    items = [
        pystray.MenuItem("Checkliste öffnen", lambda: webbrowser.open(url), default=True),
        pystray.MenuItem("Jetzt prüfen", lambda: service.status(refresh=True)),
        pystray.Menu.SEPARATOR,
    ]
    for check in status["checks"].values():
        mark = "✓" if check["done"] else "○"
        items.append(pystray.MenuItem(f"{mark} {check['title']}", None, enabled=False))
    return items


def _remind_if_due(icon, status, times, sent_by_day):
    sent = sent_by_day.setdefault(status["day"], set())
    if reminder_due(dt.datetime.now(), times, sent) and not status["unlocked"]:
        icon.notify("Noch offen: " + ", ".join(open_tasks(status)), "Productivity Lock")


def run_tray(service, url, reminder_times, stop=None):
    try:
        import pystray
    except ImportError:
        logging.warning("Kein Tray-Symbol: pystray fehlt, siehe requirements.txt")
        return
    stop = stop or threading.Event()
    menu = pystray.Menu(lambda: _menu_items(pystray, service, url))
    status = service.status(network=False)
    icon = pystray.Icon("productivity_lock", draw_icon(status), tooltip(status), menu)
    icon.run_detached()
    shown = None
    sent_by_day = {}
    while not stop.wait(LOOP_SECONDS):
        try:
            # With the network here, LeetCode counts even with no browser open.
            status = service.status()
            current = (icon_label(status), status["unlocked"], tooltip(status), tuple(open_tasks(status)))
            if current != shown:
                shown = current
                icon.icon = draw_icon(status)
                icon.title = tooltip(status)
                icon.update_menu()
            _remind_if_due(icon, status, reminder_times, sent_by_day)
        except Exception:
            logging.exception("Tray-Schleife fehlgeschlagen")
    icon.stop()
