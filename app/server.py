"""Local HTTP API for the browser extension, plus the lock page itself."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 47615
BASE_URL = f"http://127.0.0.1:{PORT}"
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
SAME_ORIGINS = {f"http://{host}" for host in ALLOWED_HOSTS}
MAX_BODY_BYTES = 10_000
STATIC_FILES = {
    "/": ("locked.html", "text/html; charset=utf-8"),
    "/locked.js": ("locked.js", "text/javascript; charset=utf-8"),
    "/locked.css": ("locked.css", "text/css; charset=utf-8"),
}


class LockServer(ThreadingHTTPServer):
    # Without reuse, a second instance fails to bind instead of sharing the port.
    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, service, static_dir, port=PORT):
        super().__init__(("127.0.0.1", port), Handler)
        self.service = service
        self.static_dir = static_dir


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _origin_allowed(self):
        origin = self.headers.get("Origin")
        return origin is None or origin in SAME_ORIGINS or origin.startswith("chrome-extension://")

    def _request_allowed(self):
        # Websites must not be able to drive the timer, directly or via DNS rebinding.
        if self.headers.get("Host") not in ALLOWED_HOSTS or not self._origin_allowed():
            self._send_json(403, {"error": "Nicht erlaubt"})
            return False
        return True

    def _cors_headers(self):
        origin = self.headers.get("Origin")
        if origin and self._origin_allowed():
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
            self._send_json(200, self.server.service.status(refresh=refresh))
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

    def do_POST(self):
        if not self._request_allowed():
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "Zu lang"})
            return
        raw = self.rfile.read(length)
        service = self.server.service
        try:
            if self.path == "/reading/start":
                self._send_json(200, service.start_reading())
            elif self.path == "/reading/finish":
                self._send_json(200, service.finish_reading(json.loads(raw or b"{}").get("note")))
            elif self.path == "/joker":
                self._send_json(200, service.use_joker(json.loads(raw or b"{}").get("reason")))
            else:
                self._send_json(404, {"error": "Nicht gefunden"})
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
