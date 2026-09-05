import json
import pathlib
import socket
import subprocess
import sys
import time
from contextlib import closing
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
assert (DIST / "control" / "index.html").is_file()
assert json.loads((DIST / "data" / "control-runtime.json").read_text())["schema"] == "biella.control-runtime/v1"

def free_port():
    with closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

port = free_port()
server = subprocess.Popen(
    [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(DIST)],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
try:
    time.sleep(0.4)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for viewport in ({"width": 1440, "height": 900}, {"width": 390, "height": 844}):
            page = browser.new_page(viewport=viewport)
            response = page.goto("http://127.0.0.1:" + str(port) + "/control/", wait_until="networkidle")
            assert response and response.ok
            assert page.locator("#login-title").inner_text() == "Sign in to Biella"
            body = page.content()
            for label in ("Website", "Engine", "Games", "Control", "Work", "Outputs", "System"):
                assert label in body
            assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            page.close()
        browser.close()
    print("CONTROL_BROWSER_QUALIFICATION_PASS desktop=1440x900 mobile=390x844")
finally:
    server.terminate()
    server.wait(timeout=5)
