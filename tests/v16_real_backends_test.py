from __future__ import annotations
import asyncio, os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "lumen-core"))

from gaia_platform.browser_real import BrowserProfile, BrowserUseBackend, HttpBrowserBackend
from gaia_platform.real_backends import (
    GraphitiMemoryProvider, Mem0MemoryProvider, OpenHandsCodingWorker,
    PipecatVoiceBackend, SileroVADBackend, UITARSComputerUseBackend,
)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'<html><title>GAIA E2E</title><body><h1>GAIA local page</h1><button id="go">Go</button><input id="name"></body></html>'
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *_): pass

def test_health_and_real_symbols():
    assert BrowserUseBackend().health()["status"] == "AVAILABLE"
    assert SileroVADBackend().health()["status"] == "AVAILABLE"
    assert PipecatVoiceBackend().health()["status"] == "AVAILABLE"
    assert Mem0MemoryProvider().health()["status"] == "AVAILABLE"
    assert GraphitiMemoryProvider().health()["status"] in {"AVAILABLE", "CONFIG_REQUIRED"}
    assert OpenHandsCodingWorker(ROOT / "data" / "test-workspaces").health()["status"] == "AVAILABLE"
    assert UITARSComputerUseBackend().health()["status"] in {"DEPENDENCY_MISSING", "BLOCKED_BY_ENVIRONMENT"}

def test_pipecat_pipeline_and_vad_contract():
    voice = PipecatVoiceBackend(); pipeline = voice.build_pipeline([])
    assert type(pipeline).__name__ == "Pipeline"
    assert asyncio.run(voice.start())["status"] == "READY"
    assert asyncio.run(voice.interrupt())["event"] == "INTERRUPTED"

def test_http_fallback_ssrf_and_injection_guard():
    b = HttpBrowserBackend(BrowserProfile(allow_private=True))
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        result = asyncio.run(b.navigate(f"http://127.0.0.1:{server.server_port}/"))
        assert result["content"]["trusted"] is False and "GAIA local page" in result["content"]["content"]
    finally: server.shutdown(); server.server_close()
    blocked = HttpBrowserBackend(BrowserProfile())
    try: asyncio.run(blocked.navigate("http://127.0.0.1:1/")); assert False, "SSRF must fail closed"
    except PermissionError: pass

def test_browser_use_real_rendered_page_and_action():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    b = BrowserUseBackend(BrowserProfile(name="e2e", allow_private=True, allowed_domains={"127.0.0.1"}))
    async def run():
        await b.launch(); await b.navigate(f"http://127.0.0.1:{server.server_port}/")
        page = await b.read_page(); assert "GAIA local page" in page["content"]
        clicked = await b.click("#go"); typed = await b.type("#name", "verified")
        assert clicked["status"] == "clicked" and typed["status"] == "typed"
        await b.close()
    try: asyncio.run(run())
    finally: server.shutdown(); server.server_close()

def test_openhands_permission_and_isolation():
    worker = OpenHandsCodingWorker(ROOT / "data" / "test-workspaces")
    result = asyncio.run(worker.run("inspect", ROOT / "lumen-core", approved=False))
    assert result["status"] == "WAITING_PERMISSION" and result["approval_required"] is True

def test_visualizer_is_read_only_surface():
    html = (ROOT / "lumen-core" / "static" / "gaia_visualizer.html").read_text()
    assert "authority remains in GAIA Core" in html
    assert "/api/visualizer/events" in html
