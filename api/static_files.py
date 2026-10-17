"""Serve the landing page and Mini App from the Vercel Python function.

Vercel selects the FastAPI preset because fastapi is listed in
requirements.txt, and that preset sends every path to this function.
Static files therefore never reach the CDN. The same helper also covers a
project-level catch-all route.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def _request_path(raw_path: str) -> str:
    path = unquote(urlparse(raw_path or "").path or "/")
    if "\x00" in path:
        return "/"
    if not path.startswith("/"):
        path = "/" + path
    return path


def is_static_request(raw_path: str) -> bool:
    path = _request_path(raw_path)
    if path == "/api" or path.startswith("/api/"):
        return False
    return (
        path in {"/", "/index.html", "/landing", "/landing/"}
        or path.startswith("/landing/")
        or path in {"/miniapp", "/miniapp/"}
        or path.startswith("/miniapp/")
    )


def resolve_static(raw_path: str, root: Path) -> tuple[Path, str] | None:
    if not is_static_request(raw_path):
        return None
    path = _request_path(raw_path)
    if path in {"/", "/index.html", "/landing", "/landing/"}:
        base = (root / "landing").resolve()
        relative = "index.html"
    elif path == "/landing/index.html":
        base = (root / "landing").resolve()
        relative = "index.html"
    elif path.startswith("/landing/"):
        base = (root / "landing").resolve()
        relative = path[len("/landing/") :]
    else:
        base = (root / "miniapp").resolve()
        relative = path[len("/miniapp/") :] if path.startswith("/miniapp/") else ""
        if path == "/miniapp":
            relative = ""
    if relative.endswith("/") or relative == "":
        relative = relative + "index.html"
    parts = Path(relative).parts
    if not parts or any(part in {"", ".", ".."} or part.startswith(".") for part in parts):
        return None
    suffix = Path(relative).suffix.lower()
    content_type = CONTENT_TYPES.get(suffix)
    if content_type is None:
        return None
    candidate = (base / relative).resolve()
    if candidate != base and base not in candidate.parents:
        return None
    if not candidate.is_file():
        return None
    return candidate, content_type
