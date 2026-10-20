"""v0.7.2 production-path contract for DesktopAPI context/envelope transport."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))
os.environ.setdefault("GAIA_PC_DEVICE_ID", "pc-main")

import desktop_api  # noqa: E402
from desktop_api import LumenDesktopAPI  # noqa: E402
from desktop_context import get_desktop_context  # noqa: E402


class FakeResponse:
    is_error = False
    text = ""

    def __init__(self, payload: dict):
        self.payload = payload

    def json(self) -> dict:
        return dict(self.payload)

    def raise_for_status(self) -> None:
        return None


class FakeStreamResponse(FakeResponse):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def iter_lines(self):
        yield 'event: meta'
        yield 'data: {"session_id":"s-production","request_id":"r-production"}'
        yield 'event: done'
        yield 'data: {"kind":"chat","response":"ok","session_id":"s-production"}'


class CaptureClient:
    requests: list[tuple[str, dict]] = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def request(self, method: str, url: str, **kwargs):
        self.requests.append((url, {"method": method, **kwargs}))
        if url.endswith("/chat/voice"):
            return FakeResponse({"kind": "chat", "response": "voz ok", "session_id": "s-voice"})
        return FakeResponse({"kind": "chat", "response": "ok", "session_id": "s-production"})

    def stream(self, method: str, url: str, **kwargs):
        self.requests.append((url, {"method": method, **kwargs}))
        return FakeStreamResponse({})


api = LumenDesktopAPI("http://capture.invalid", "test-secret")
context = api.desktop_context(force_refresh=True)
snapshot = context.get("desktop_snapshot")
assert isinstance(snapshot, dict)
original_desktop_context = api.desktop_context
api.desktop_context = lambda **_kwargs: context
original_client = desktop_api.httpx.Client
desktop_api.httpx.Client = CaptureClient
try:
    assert snapshot.get("schema_version") == "1"
    assert snapshot.get("snapshot_id")
    assert snapshot.get("host_id")
    assert "expires_at" in snapshot

    api.send_message("hola")
    api.send_assistant("hola")
    with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
        audio.write(b"RIFFfake")
        audio.flush()
        api.send_voice(Path(audio.name))
finally:
    desktop_api.httpx.Client = original_client
    api.desktop_context = original_desktop_context

assert len(CaptureClient.requests) == 3, CaptureClient.requests
chat_url, chat = CaptureClient.requests[0]
assert chat_url.endswith("/chat")
chat_payload = chat["json"]
assert chat_payload["channel"] == "desktop_text"
assert chat_payload["pc_context"]["desktop_snapshot"]["snapshot_id"] == snapshot["snapshot_id"]
assert chat_payload["desktop_snapshot"]["schema_version"] == "1"
assert chat_payload["request_envelope"]["channel"] == "desktop_text"
assert chat_payload["request_envelope"]["desktop_snapshot"]["snapshot_id"] == snapshot["snapshot_id"]

stream_url, stream = CaptureClient.requests[1]
assert stream_url.endswith("/assistant/stream")
stream_payload = stream["json"]
assert stream_payload["channel"] == "desktop_text"
assert stream_payload["request_envelope"]["protocol_version"] == "1.0-RC6"
assert stream_payload["desktop_snapshot"]["snapshot_id"] == snapshot["snapshot_id"]

voice_url, voice = CaptureClient.requests[2]
assert voice_url.endswith("/chat/voice")
voice_form = voice["data"]
voice_envelope = json.loads(voice_form["request_envelope"])
voice_snapshot = json.loads(voice_form["desktop_snapshot"])
assert voice_form["channel"] == "desktop_voice"
assert voice_envelope["channel"] == "desktop_voice"
assert voice_envelope["desktop_snapshot"]["snapshot_id"] == snapshot["snapshot_id"]
assert voice_snapshot["snapshot_id"] == snapshot["snapshot_id"]

# Direct service remains the single provider used by the DesktopAPI adapter.
service_snapshot = get_desktop_context(force_refresh=True)
assert service_snapshot["schema_version"] == snapshot["schema_version"]
print("DESKTOP CONTEXT PRODUCTION PATH V072 TEST OK: real DesktopAPI text/SSE/voice payloads carry canonical snapshot and envelope.")
