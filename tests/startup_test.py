"""Prueba read-only de la sonda usada por start-gaia."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tools" / "gaia_startup_probe.py"


class Handler(BaseHTTPRequestHandler):
    payload = {"name": "OtherApp", "version": "1", "status": "online"}

    def do_GET(self):  # noqa: N802
        body = json.dumps(self.payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
port = server.server_address[1]
foreign = subprocess.run([sys.executable, str(PROBE), "--port", str(port)], capture_output=True, text=True)
assert foreign.returncode == 2, foreign.stdout + foreign.stderr
Handler.payload = {"name": "GAIA", "version": "1.0.0-rc6-pc", "status": "online"}
active = subprocess.run([sys.executable, str(PROBE), "--port", str(port)], capture_output=True, text=True)
assert active.returncode == 0, active.stdout + active.stderr
server.shutdown()
server.server_close()
offline = subprocess.run([sys.executable, str(PROBE), "--port", str(port)], capture_output=True, text=True)
assert offline.returncode == 1, offline.stdout + offline.stderr

print("STARTUP TEST OK: activo, puerto ajeno y offline se distinguen sin acciones destructivas.")
