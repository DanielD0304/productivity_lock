"""Local HTTP API for the browser extension, plus the lock page itself."""
import hmac
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 47615
BASE_URL = f"http://127.0.0.1:{PORT}"
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
SAME_ORIGINS = {f"http://{host}" for host in ALLOWED_HOSTS}
MAX_BODY_BYTES = 10_000
PHONE_PORT = 47616
TOKEN_COOKIE = "plock_token"
TASK_ROUTE = re.compile(r"^/tasks/([a-z0-9_-]+)/(start|finish|joker)$")
CHAT_ROUTE = re.compile(r"^/chats/([a-z0-9_-]+)/(start|stop)$")
STATIC_FILES = {
    "/": ("locked.html", "text/html; charset=utf-8"),
    "/locked.js": ("locked.js", "text/javascript; charset=utf-8"),
    "/locked.css": ("locked.css", "text/css; charset=utf-8"),
}


class LockServer(ThreadingHTTPServer):
    # Without reuse, a second instance fails to bind instead of sharing the port.
    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, service, static_dir, port=PORT, launchers=None, host="127.0.0.1", token=None,
                 phone=None):
        """With a token the server is the phone's access: any host, but every request needs the token."""
        super().__init__((host, port), Handler)
        self.service = service
        self.launchers = {} if token else (launchers or {})
        self.static_dir = static_dir
        self.token = token
        self.phone = phone or {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _origin_allowed(self):
        origin = self.headers.get("Origin")
        return origin is None or origin in SAME_ORIGINS or origin.startswith("chrome-extension://")

    def _token_ok(self):
        sent = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        for part in self.headers.get("Cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == TOKEN_COOKIE:
                sent = sent or value
        return bool(sent) and hmac.compare_digest(sent.encode(), self.server.token.encode())

    def _request_allowed(self):
        if self.server.token:
            # Phone access: the token proves the caller; pages from other origins must not ride along.
            origin = self.headers.get("Origin")
            if not self._token_ok() or (origin and origin != f"http://{self.headers.get('Host')}"):
                self._send_json(403, {"error": "Nicht erlaubt"})
                return False
            return True
        # Websites must not be able to drive the timer, directly or via DNS rebinding.
        if self.headers.get("Host") not in ALLOWED_HOSTS or not self._origin_allowed():
            self._send_json(403, {"error": "Nicht erlaubt"})
            return False
        return True

    def _cors_headers(self):
        origin = self.headers.get("Origin")
        if origin and self._origin_allowed() and not self.server.token:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204 if self._origin_allowed() else 403)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def do_GET(self):
        if not self._request_allowed():
            return
        url = urlparse(self.path)
        if url.path == "/status":
            refresh = parse_qs(url.query).get("refresh") == ["1"]
            status = self.server.service.status(refresh=refresh)
            for chat_id, launcher in self.server.launchers.items():
                check = status["checks"].get(chat_id)
                if check and launcher.running():
                    check.update(action_path=f"/chats/{chat_id}/stop", action_text=f"{check['title']} beenden")
            if self.server.token:
                self._phone_status(status)
            self._send_json(200, status)
        elif url.path in STATIC_FILES:
            name, content_type = STATIC_FILES[url.path]
            with open(os.path.join(self.server.static_dir, name), "rb") as file:
                body = file.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send_json(404, {"error": "Nicht gefunden"})

    def _phone_status(self, status):
        # Chats open on the PC, so the phone shows them without a button.
        for check in status["checks"].values():
            if (check.get("action_path") or "").startswith("/chats/"):
                check.pop("action_path")
                check.pop("action_text", None)
                check["hint"] = "Den Chat startest du am PC."
        status["rollover_hour"] = self.server.service.config["day_rollover_hour"]
        status["phone"] = self.server.phone

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        # Read the body even before refusing: unread data makes Windows reset the connection.
        raw = self.rfile.read(length) if length <= MAX_BODY_BYTES else b""
        if not self._request_allowed():
            return
        if length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "Zu lang"})
            return
        service = self.server.service
        task_route = TASK_ROUTE.match(self.path)
        chat_route = CHAT_ROUTE.match(self.path)
        try:
            body = json.loads(raw or b"{}")
            if not isinstance(body, dict):
                raise ValueError("Ungültige Anfrage")
            if task_route and task_route[2] == "start":
                self._send_json(200, service.start_task(task_route[1]))
            elif task_route and task_route[2] == "joker":
                self._send_json(200, service.use_joker(task_route[1], body.get("reason")))
            elif task_route:
                self._send_json(200, service.finish_task(task_route[1], body.get("note")))
            elif chat_route and chat_route[1] in self.server.launchers:
                launcher = self.server.launchers[chat_route[1]]
                if chat_route[2] == "start":
                    launcher.start()
                else:
                    launcher.stop()
                self._send_json(200, {"ok": True})
            else:
                self._send_json(404, {"error": "Nicht gefunden"})
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
        except OSError as error:
            self._send_json(500, {"error": f"Datei konnte nicht geschrieben werden: {error}"})
