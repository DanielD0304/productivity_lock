"""Phone access over Tailscale: a second server on the Tailscale address that needs a token."""
import json
import logging
import os
import secrets
import shutil
import subprocess
import time
from urllib.parse import urlencode

from .server import PHONE_PORT, LockServer

RETRY_SECONDS = 30
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TAILSCALE_PATHS = [
    r"C:\Program Files\Tailscale\tailscale.exe",
    r"C:\Program Files (x86)\Tailscale\tailscale.exe",
]
DEFAULT_BLOCKED_APPS = [
    "com.google.android.youtube",
    "com.instagram.android",
    "com.netflix.mediaclient",
    "com.riotgames.league.wildrift",
    "com.linkedin.android",
    "com.reddit.frontpage",
]
# Checked against the address bar of the phone's browsers; subdomains (m., www.) count too.
DEFAULT_BLOCKED_SITES = [
    "youtube.com", "youtu.be", "netflix.com", "instagram.com",
    "linkedin.com", "lnkd.in", "reddit.com", "redd.it",
]


def load_token(data_dir):
    """The token the phone app needs; created once and kept in data/phone_token.txt."""
    path = os.path.join(data_dir, "phone_token.txt")
    try:
        with open(path, encoding="utf-8") as file:
            token = file.read().strip()
        if token:
            return token
    except OSError:
        pass
    token = secrets.token_urlsafe(24)
    with open(path, "w", encoding="utf-8") as file:
        file.write(token + "\n")
    return token


def tailscale_ip(run=subprocess.run):
    exe = shutil.which("tailscale") or next((path for path in TAILSCALE_PATHS if os.path.exists(path)), None)
    if not exe:
        return None
    try:
        output = run([exe, "ip", "-4"], capture_output=True, text=True, timeout=10,
                     creationflags=NO_WINDOW, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    ips = [line.strip() for line in output.splitlines() if line.strip().startswith("100.")]
    return ips[0] if ips else None


def phone_settings(config):
    phone = config.get("phone", {})
    return {
        "enabled": phone.get("enabled", True),
        "host": phone.get("host", "auto"),
        "port": phone.get("port", PHONE_PORT),
        "blocked_apps": phone.get("blocked_apps", DEFAULT_BLOCKED_APPS),
        "blocked_sites": phone.get("blocked_sites", DEFAULT_BLOCKED_SITES),
    }


def serve_phone(service, static_dir, config, data_dir, find_ip=tailscale_ip, sleep=time.sleep):
    """Waits for Tailscale (it may start after us at boot), then serves the phone until the process ends."""
    settings = phone_settings(config)
    if not settings["enabled"]:
        return
    token = load_token(data_dir)
    warned = False
    while True:
        host = find_ip() if settings["host"] == "auto" else settings["host"]
        if host:
            try:
                server = LockServer(service, static_dir, port=settings["port"], host=host, token=token,
                                    phone={"blocked_apps": settings["blocked_apps"],
                                           "blocked_sites": settings["blocked_sites"]})
            except OSError as error:
                logging.warning("Handy-Zugang auf %s:%s nicht möglich: %s", host, settings["port"], error)
            else:
                logging.info("Handy-Zugang auf http://%s:%s", host, settings["port"])
                server.serve_forever()
                return
        elif not warned:
            logging.info("Handy-Zugang wartet auf Tailscale")
            warned = True
        sleep(RETRY_SECONDS)


def pairing_link(address, token):
    return "productivitylock://pair?" + urlencode({"url": address, "token": token})


def main():
    """Shows what the phone app needs: a QR code to scan, and address and token to type in."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(root, "data")
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(root, "config.json"), encoding="utf-8") as file:
        settings = phone_settings(json.load(file))
    host = tailscale_ip() if settings["host"] == "auto" else settings["host"]
    if not host:
        print("Tailscale läuft nicht oder ist nicht angemeldet.")
        return
    address = f"http://{host}:{settings['port']}"
    token = load_token(data_dir)
    print("Adresse:", address)
    print("Token:  ", token)
    try:
        import qrcode
    except ImportError:
        print("Für den QR-Code: python -m pip install -r requirements.txt")
        return
    path = os.path.join(data_dir, "phone_pairing.png")
    qrcode.make(pairing_link(address, token)).save(path)
    print("QR-Code mit der Handy-Kamera scannen:", path)
    os.startfile(path)


if __name__ == "__main__":
    main()
