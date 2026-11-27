"""Shell frame: design tokens, on-device storage, and routes that stay off Supabase."""

import shutil
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "miniapp" / "js"


def test_shell_assets_and_tokens_are_wired():
    html = (ROOT / "miniapp" / "index.html").read_text(encoding="utf-8")
    assert 'href="./shell.css"' in html
    assert 'src="./js/main.js"' in html
    sdk = html.find("https://telegram.org/js/telegram-web-app.js")
    module = html.find('src="./js/main.js"')
    assert 0 <= sdk < module
    for ref in ("shell.css", "styles.css", "js/main.js", "js/shell.js", "js/shell_screens.js", "js/shell_router.js", "js/personal_store.js"):
        assert (ROOT / "miniapp" / ref).is_file(), ref

    css = (ROOT / "miniapp" / "shell.css").read_text(encoding="utf-8")
    assert "padding-bottom: 170px" in css
    assert "right: 14px" in css
    assert "bottom: 94px" in css
    assert "width: 48px" in css
    assert "height: 48px" in css
    assert "--ut-zone-green" in css
    assert "--ut-zone-yellow" in css
    assert "--ut-zone-red" in css
    assert "официальный источник" in css
    assert "safe-area-inset-bottom" in css

    main = (JS / "main.js").read_text(encoding="utf-8")
    assert 'failedTitle = "Не удалось войти"' in main
    assert 'failedTitle = "Справочник не открылся"' in main
    assert "startShell" in main


def test_shell_scripts_parse_and_cover_routes():
    for path in JS.glob("*.js"):
        result = subprocess.run(["node", "--check", str(path)], check=False, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    result = subprocess.run(
        ["node", str(ROOT / "tests" / "check_shell_modules.mjs")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_dev_server_serves_the_shell():
    script = r"""
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from miniapp.dev_server import Handler

server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
base = f"http://127.0.0.1:{server.server_address[1]}"
try:
    page = urllib.request.urlopen(base + "/miniapp/", timeout=10).read().decode("utf-8")
    assert "shell.css" in page and "./js/main.js" in page
    css = urllib.request.urlopen(base + "/miniapp/shell.css", timeout=10).read().decode("utf-8")
    assert "padding-bottom: 170px" in css
    script = urllib.request.urlopen(base + "/miniapp/js/shell.js", timeout=10).read().decode("utf-8")
    assert "startShell" in script
    store = urllib.request.urlopen(base + "/miniapp/js/personal_store.js", timeout=10).read().decode("utf-8")
    assert "CloudStorage" in store
    assert "supabase" not in store.lower()
finally:
    server.shutdown()
    server.server_close()
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout


def test_shell_has_no_console_errors():
    chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    if chrome is None and Path("/usr/local/bin/google-chrome").is_file():
        chrome = "/usr/local/bin/google-chrome"
    if chrome is None:
        pytest.skip("Chrome is not installed")
    from api.index import handler

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        result = subprocess.run(
            ["node", str(ROOT / "tests" / "check_shell_console.mjs"), base, chrome],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=40,
        )
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode == 0, result.stdout + result.stderr
