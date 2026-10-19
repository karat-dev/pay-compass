"""Serve the Mini App and its API on localhost.

Sets MINIAPP_DEV_AUTH so the browser can open the app outside Telegram.
Do not use this process as the production host.
"""

from __future__ import annotations

import json
import os

os.environ["MINIAPP_DEV_AUTH"] = "1"

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from api.miniapp_http import READ_ROUTES, WRITE_ROUTES, dispatch, extract_route

ROOT = Path(__file__).resolve().parent
MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
    ".webp": "image/webp",
    ".png": "image/png",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def log_message(self, fmt: str, *args) -> None:
        print("%s - %s" % (self.log_date_time_string(), fmt % args))

    def _handle(self, method: str) -> None:
        route = extract_route(self.path)
        if route in READ_ROUTES or route in WRITE_ROUTES:
            length = int(self.headers.get("Content-Length", "0") or 0) if method == "POST" else 0
            body = self.rfile.read(length) if length else b""
            parsed = urlparse(self.path)
            query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
            status, payload = dispatch(method, route, body, dict(self.headers.items()), query)
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self._static()

    def _static(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path in {"", "/"}:
            self._redirect("/miniapp/")
            return
        if path == "/miniapp":
            self._redirect("/miniapp/")
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if not path.startswith("/miniapp/"):
            self.send_error(404)
            return
        rel = path[len("/miniapp/"):] or "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        root = ROOT.resolve()
        target = (root / rel).resolve()
        if root not in target.parents and target != root:
            self.send_error(404)
            return
        if not target.is_file():
            self.send_error(404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()


def main() -> None:
    port = int(os.environ.get("PORT", "4173"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Mini App: http://127.0.0.1:{port}/miniapp/")
    server.serve_forever()


if __name__ == "__main__":
    main()
