"""Matriz RBAC para el chat por voz sin hardware real."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_voice_permissions_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "voice-rbac-test-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_AUTO_MEMORY_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    from main import app
    import routes.api as api_routes
    import config

    api_routes.speech_to_text = lambda _path: "Hola desde voz"

    async def fake_tts(_text: str) -> str:
        audio_dir = config.DATA_DIR / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        path = audio_dir / "voice-rbac.mp3"
        path.write_bytes(b"fake-mp3")
        return str(path)

    api_routes.text_to_speech = fake_tts
    master = {"Authorization": "Bearer voice-rbac-test-secret"}
    devices = {
        "voice-only": ["voice"],
        "chat-only": ["chat"],
        "voice-chat": ["voice", "chat"],
    }
    with TestClient(app) as client:
        tokens = {}
        for device_id, capabilities in devices.items():
            registered = client.post("/api/devices/register", headers=master, json={"device_id": device_id, "capabilities": capabilities, "device_type": "test"})
            assert registered.status_code == 200, registered.text
            created = client.post(f"/api/devices/{device_id}/token", headers=master, json={"ttl_days": 1})
            assert created.status_code == 200, created.text
            tokens[device_id] = {"Authorization": f"Bearer {created.json()['token']}"}

        voice_file = {"audio": ("voice.wav", b"dummy", "audio/wav")}
        assert client.post("/api/chat/voice", headers=tokens["voice-only"], files=voice_file).status_code == 403
        assert client.post("/api/chat/voice", headers=tokens["chat-only"], files=voice_file).status_code == 403
        allowed = client.post("/api/chat/voice", headers=tokens["voice-chat"], files=voice_file)
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["user_text"] == "Hola desde voz"
        assert allowed.json()["kind"] == "chat"

print("VOICE PERMISSIONS TEST OK: voice-only/chat-only 403; voice+chat 200.")
