"""Landing and Mini App files served by the Vercel Python handler."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from api.index import handler
from api.static_files import is_static_request, resolve_static

ROOT = Path(__file__).resolve().parents[1]


def test_miniapp_and_landing_paths_resolve_to_public_files():
    html, html_type = resolve_static("/miniapp/", ROOT)
    assert html.name == "index.html"
    assert html.parent.name == "miniapp"
    assert html_type.startswith("text/html")
    assert "Умный туризм" in html.read_text(encoding="utf-8")

    script, script_type = resolve_static("/miniapp/js/main.js?tgWebAppData=1", ROOT)
    assert script.name == "main.js"
    assert script_type.startswith("text/javascript")

    home, _ = resolve_static("/", ROOT)
    assert home == (ROOT / "landing" / "index.html").resolve()
    landing, _ = resolve_static("/landing/index.html", ROOT)
    assert landing == home


def test_static_resolver_rejects_code_and_traversal():
    assert resolve_static("/miniapp/dev_server.py", ROOT) is None
    assert resolve_static("/miniapp/__init__.py", ROOT) is None
    assert resolve_static("/miniapp/../requirements.txt", ROOT) is None
    assert resolve_static("/miniapp/%2e%2e/config/settings.py", ROOT) is None
    assert resolve_static("/landing/README.md", ROOT) is None
    assert resolve_static("/api/miniapp/config", ROOT) is None
    assert is_static_request("/api/set_webhook") is False
    assert is_static_request("/miniapp/styles.css") is True


def test_handler_serves_miniapp_html_and_keeps_api():
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/miniapp/", timeout=10) as response:
            page = response.read().decode("utf-8")
            assert response.status == 200
            assert response.headers["Content-Type"].startswith("text/html")
            assert "<title>Умный туризм</title>" in page
            assert "./js/main.js" in page
        with urllib.request.urlopen(base + "/miniapp/js/main.js", timeout=10) as response:
            script = response.read().decode("utf-8")
            assert response.headers["Content-Type"].startswith("text/javascript")
            assert "function" in script or "const " in script or "import " in script
        with urllib.request.urlopen(base + "/", timeout=10) as response:
            assert "Умный туризм" in response.read().decode("utf-8")
        with urllib.request.urlopen(base + "/api/miniapp/config", timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["token_configured"] in (True, False)
            assert payload["storage"] in ("supabase", "local-file")
        try:
            urllib.request.urlopen(base + "/miniapp/dev_server.py", timeout=10)
        except urllib.error.HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError("python source was served")
    finally:
        server.shutdown()
        server.server_close()
