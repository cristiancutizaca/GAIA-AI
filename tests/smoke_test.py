"""Prueba del Core v0.2 sin credenciales ni dispositivos externos."""
from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "lumen-core"
sys.path.insert(0, str(CORE))

with tempfile.TemporaryDirectory(prefix="lumen_test_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-secret-for-lumen-v02",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "LUMEN_AUTO_FACTS_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    from main import app
    import routes.api as api_routes
    import config

    api_routes.speech_to_text = lambda _: "Prueba de voz"
    async def fake_tts(_: str) -> str:
        audio_dir = config.DATA_DIR / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        path = audio_dir / "voice_test.mp3"
        path.write_bytes(b"fake-mp3")
        return str(path)
    api_routes.text_to_speech = fake_tts
    headers = {"Authorization": "Bearer test-secret-for-lumen-v02"}

    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200 and health.json()["version"] == "0.2.0-pc", health.text
        assert client.get("/api/status").status_code == 401
        status = client.get("/api/status", headers=headers)
        assert status.status_code == 200 and status.json()["features"]["auto_facts"] is False, status.text
        chat = client.post("/api/chat", headers=headers, json={"message": "Me llamo Cris", "device": "test"})
        assert chat.status_code == 200, chat.text
        session_id = chat.json()["session_id"]
        history = client.get(f"/api/memory/history/{session_id}", headers=headers)
        assert history.status_code == 200 and len(history.json()) == 2, history.text
        facts = client.get("/api/memory/facts", headers=headers)
        assert facts.json() == [], "Auto-facts debe estar apagado por defecto"
        saved = client.post("/api/memory/fact", headers=headers, json={"category": "nombre", "fact": "Cris"})
        assert saved.status_code == 200
        stored = client.get("/api/memory/facts", headers=headers).json()
        assert stored[0]["source"] == "manual"
        deleted = client.delete(f"/api/memory/fact/{stored[0]['id']}", headers=headers)
        assert deleted.status_code == 200
        voice = client.post("/api/chat/voice", headers=headers, files={"audio": ("test.wav", b"dummy", "audio/wav")})
        assert voice.status_code == 200 and voice.json()["audio_url"] == "/api/voice/audio/voice_test.mp3", voice.text
        audio = client.get(voice.json()["audio_url"], headers=headers)
        assert audio.status_code == 200 and audio.content == b"fake-mp3"
        backup = client.post("/api/backup", headers=headers)
        assert backup.status_code == 200 and Path(backup.json()["path"]).exists()
        client.post("/api/proactive/test", headers=headers, json={"message": "prueba lista"})
        delivered = client.get("/api/proactive/check", headers=headers)
        assert delivered.json().get("message") == "prueba lista"
print("SMOKE TEST v0.2 OK: auth, status, chat, memoria manual, voz/API, backup y polling.")
