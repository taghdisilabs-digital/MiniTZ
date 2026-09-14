from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
from urllib.parse import urlsplit


def greeting() -> str:
    return "Hello MiniTZ?"


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


_PAGE = b"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MiniTZ Web Candidate</title>
</head>
<body>
  <main>
    <h1>MiniTZ Web Candidate</h1>
    <button id="load" type="button" aria-label="Load exact greeting">Load greeting</button>
    <p id="message" role="status">Waiting</p>
    <output id="diagnostics" aria-label="Runtime diagnostics">runtime_errors=0;network_errors=0</output>
  </main>
  <script>
    window.__minitzDiagnostics = {runtimeErrors: 0, networkErrors: 0};
    function renderDiagnostics() {
      document.getElementById('diagnostics').textContent =
        'runtime_errors=' + window.__minitzDiagnostics.runtimeErrors +
        ';network_errors=' + window.__minitzDiagnostics.networkErrors;
    }
    window.addEventListener('error', () => {
      window.__minitzDiagnostics.runtimeErrors += 1;
      renderDiagnostics();
    });
    window.addEventListener('unhandledrejection', () => {
      window.__minitzDiagnostics.runtimeErrors += 1;
      renderDiagnostics();
    });
    document.getElementById('load').addEventListener('click', async () => {
      try {
        const response = await fetch('/api/greeting');
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const body = await response.json();
        document.getElementById('message').textContent = body.greeting;
      } catch (error) {
        window.__minitzDiagnostics.networkErrors += 1;
        document.getElementById('message').textContent = 'Request failed';
        renderDiagnostics();
      }
    });
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _reply(self, status: int, payload: bytes, media_type: str) -> None:
        self.send_response(status)
        self.send_header("content-type", media_type)
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self.wfile.flush()

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self._reply(200, _PAGE, "text/html; charset=utf-8")
            return
        if path == "/api/health":
            self._reply(
                200,
                _json(
                    {
                        "candidate_commit": os.environ["MINITZ_CANDIDATE_COMMIT"],
                        "candidate_tree": os.environ["MINITZ_CANDIDATE_TREE"],
                        "status": "ok",
                    }
                ),
                "application/json",
            )
            return
        if path == "/api/greeting":
            self._reply(200, _json({"greeting": greeting()}), "application/json")
            return
        if path == "/api/crash":
            self._reply(200, _json({"crashing": True}), "application/json")
            os._exit(17)
        if path == "/api/shutdown":
            self._reply(200, _json({"shutdown": True}), "application/json")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self._reply(404, _json({"error": "not-found"}), "application/json")


def main() -> None:
    port = int(os.environ["MINITZ_PORT"])
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"READY port={port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        print("STOPPED", flush=True)


if __name__ == "__main__":
    main()
