from contextlib import asynccontextmanager
import json
import sqlite3
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "lumen-core"), str(ROOT / "lumen-pc")]

import authz
import authority
import brain_backup
import memory
from action_host import ActionHost
from gaia_platform.memory_v2 import MemoryV2Store
from platform_runtime import PlatformRuntime
from reflex_engine import classify_reflex
from routes import api

HEADERS = {"Authorization": "Bearer gaia-memory-reflex-test"}
PC = {"device": "pc-main"}
WAV = {"audio": ("test.wav", b"wav fixture", "audio/wav")}


@pytest.fixture
def application(tmp_path, monkeypatch):
    db_path = tmp_path / "state" / "memory.db"
    backup_dir = tmp_path / "backup"
    db_path.parent.mkdir()
    backup_dir.mkdir()
    for module in (memory, brain_backup):
        monkeypatch.setattr(module, "DB_PATH", db_path)
        monkeypatch.setattr(module, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(authz, "API_SECRET", "gaia-memory-reflex-test")
    monkeypatch.setattr(api, "TTS_ENABLED", False)
    monkeypatch.setattr(api, "SAFE_MODE", False)
    monkeypatch.setattr(api, "ACTION_ENGINE_ENABLED", True)
    monkeypatch.setattr(api, "GAIA_ACTIONS_ENABLED", True)
    monkeypatch.setattr(api, "GAIA_MODE", "FULL")
    monkeypatch.setattr(api, "ACTION_CONFIRM_POLICY", "CONFIRM_EXECUTION")
    monkeypatch.setattr(authority, "SAFE_MODE", False)

    async def no_model(*args, **kwargs):
        pytest.fail("The deterministic route invoked a language model")

    monkeypatch.setattr(api.llm, "chat_completion", no_model)
    monkeypatch.setattr(api.llm, "chat_completion_stream", no_model)
    import intent_classifier
    monkeypatch.setattr(intent_classifier, "classify_intent", no_model)

    @asynccontextmanager
    async def lifespan(app):
        memory.init_db()
        runtime = PlatformRuntime(tmp_path, memory_db=db_path)
        app.state.platform_runtime = runtime
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(lifespan=lifespan)
    app.include_router(api.router, prefix="/api")
    return app


def chat(client, message, *, headers=HEADERS, **fields):
    resp = client.post("/api/chat", headers=headers, json={**PC, "message": message, **fields})
    assert resp.status_code == 200, resp.text
    return resp.json()


def final_event(response):
    assert response.status_code == 200
    for frame in response.text.split("\n\n"):
        if frame.startswith("event: done\n"):
            return json.loads(frame.split("data: ", 1)[1])
    pytest.fail(response.text)


def test_explicit_memory_text_voice_stream_restart_update_delete(application, monkeypatch):
    with TestClient(application) as client:
        saved = chat(client, "GAIA, recuerda que la brújula es plateada")
        item_id = saved["active_context"]["metadata"]["memory_id"]
        assert saved["active_context"]["status"] == "SUCCEEDED"
        assert not client.get("/api/memory/history/" + saved["session_id"], headers=HEADERS).json()
        streamed = final_event(client.post("/api/assistant/stream", headers=HEADERS, json={
            **PC, "message": "GAIA, recuerda proyecto KIROHA: Nébula usa índice local",
        }))
        assert streamed["active_context"]["status"] == "SUCCEEDED"
        chat(client, "Recuerda proyecto AURIA: Nébula usa mezcla automática")

    with TestClient(application) as client:
        monkeypatch.setattr(api, "speech_to_text", lambda _: "GAIA, ¿recuerdas de la brujula?")
        spoken = client.post("/api/chat/voice", params=PC, files=WAV, headers=HEADERS).json()
        assert "plateada" in spoken["response"]
        assert spoken["session_id"] != saved["session_id"]
        assert "índice local" in chat(client, "¿Qué recuerdas de proyecto KIROHA sobre nebula?")["response"]
        assert "mezcla automática" not in chat(client, "¿Qué recuerdas de proyecto KIROHA sobre nebula?")["response"]
        result = client.put(f"/api/memory/explicit/{item_id}", headers=HEADERS, json={"content": "La brújula es dorada"})
        assert result.json()["status"] == "updated"

    with TestClient(application) as client:
        query = chat(client, "¿Te acuerdas de la brújula?")["response"]
        assert "dorada" in query and "plateada" not in query
        exported = client.get("/api/memory/explicit/export", headers=HEADERS).json()
        assert {row["project"] for row in exported} == {"", "kiroha", "auria"}
        assert client.delete(f"/api/memory/explicit/{item_id}", headers=HEADERS).json()["status"] == "deleted"

    with TestClient(application) as client:
        assert "No encontré" in chat(client, "¿Recuerdas la brújula?")["response"]
        assert all(row["memory_id"] != item_id for row in client.get("/api/memory/explicit/export", headers=HEADERS).json())


def test_legacy_import_backup_restore_and_no_resurrection(application, tmp_path):
    legacy = MemoryV2Store(tmp_path / "data" / "platform_memory_v13.db")
    item_id = legacy.add("Faro azul", owner_id="master", namespace="device:pc-main")
    before = legacy.path.read_bytes()
    with TestClient(application) as client:
        assert "Faro azul" in chat(client, "¿Recuerdas el faro?")["response"]
        backup = Path(client.post("/api/backup/brain", headers=HEADERS).json()["path"])
        snapshot = Path(memory.create_backup())
        with sqlite3.connect(snapshot) as db:
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert db.execute("SELECT content FROM memories WHERE memory_id=?", (item_id,)).fetchone()[0] == "Faro azul"
        assert client.delete(f"/api/memory/explicit/{item_id}", headers=HEADERS).status_code == 200

    with TestClient(application) as client:
        assert "No encontré" in chat(client, "¿Recuerdas el faro?")["response"]
        with backup.open("rb") as archive:
            restored = client.post("/api/backup/brain/restore", headers=HEADERS,
                                   files={"archive": ("brain.zip", archive, "application/zip")})
        assert restored.status_code == 200, restored.text
        assert "Faro azul" in chat(client, "¿Recuerdas el faro?")["response"]
    assert legacy.path.read_bytes() == before


def test_secrets_and_other_devices_are_not_returned(application, monkeypatch):
    with TestClient(application) as client:
        hidden = chat(client, "Recuerda que mi contraseña es Prueba123")
        assert hidden["active_context"]["status"] == "INVALID_MEMORY"
        assert "Prueba123" not in str(client.get("/api/memory/explicit/export", headers=HEADERS).json())
        assert "Prueba123" not in str(client.get("/api/memory/history/" + hidden["session_id"], headers=HEADERS).json())
        stored = chat(client, "Recuerda que mi faro es azul")["active_context"]["metadata"]["memory_id"]
        assert "No encontré" in chat(client, "¿Recuerdas mi faro?", device="otro-pc")["response"]

        memory.register_device("pc-main", ["chat", "voice", "memory_read", "memory_write"])
        other = {"Authorization": "Bearer " + memory.create_device_token("pc-main")["token"]}
        assert "No encontré" in chat(client, "¿Recuerdas mi faro?", headers=other)["response"]
        assert client.delete(f"/api/memory/explicit/{stored}", headers=other).status_code == 404
        assert client.get("/api/memory/explicit").status_code == 401

        monkeypatch.setattr(api, "speech_to_text", lambda _: "Recuerda que revisa mi pantalla fue la orden de prueba")
        spoken = client.post("/api/chat/voice", params=PC, files=WAV, headers=HEADERS).json()
        assert spoken["active_context"]["capability"] == "memory.write"
        assert not spoken.get("vision_requested")


@pytest.mark.parametrize(("phrase", "name"), [
    ("GAIA, abre el Bloc de notas.", "open_notepad"),
    ("GAIA, baja el volumen.", "volume_down"),
    ("GAIA, pausa la música.", "media_pause"),
    ("GAIA, abre KIROHA.", "vscode_open_project"),
    ("GAIA, muestra el escritorio.", "desktop_show"),
    ("GAIA, ¿cuánta RAM estoy usando?", "system_ram"),
])
def test_reflex_proposes_without_llm(application, phrase, name):
    with TestClient(application) as client:
        result = chat(client, phrase)
        assert result["kind"] == "action"
        assert result["action"]["name"] == name
        assert result["action"]["source"] == "reflex"
        assert result["permission_entries"]
        assert result["confirmation_required"]
        assert not result["approved"]


def test_reflex_window_target_and_kill_switch(application):
    assert classify_reflex("cierra esta ventana y borra todo") is None
    assert classify_reflex("no bajes el volumen") is None
    with TestClient(application) as client:
        no_target = chat(client, "GAIA, cierra esta ventana")
        assert no_target["kind"] == "chat"
        snapshot = {"active_window": {"window_id": "42", "pid": 100, "process": "notepad.exe"}}
        close = chat(client, "GAIA, cierra esta ventana", desktop_snapshot=snapshot)
        assert close["action"]["args"]["expected_target"]["pid"] == 100
        assert not close["approved"]
        memory.set_state("gaia_actions_enabled", "0")
        assert chat(client, "GAIA, baja el volumen")["kind"] == "chat"


def test_action_host_executes_real_ram_and_checks_volume_result(application, tmp_path, monkeypatch):
    import action_engine
    levels = iter([55, 45])
    monkeypatch.setattr(action_engine, "audio_get", lambda: {"level": next(levels)})
    writes = []
    monkeypatch.setattr(action_engine, "audio_set", lambda value: writes.append(value) or {"level": value})
    with TestClient(application) as client:
        host = ActionHost(tmp_path)
        ram = chat(client, "GAIA, ¿cuánta RAM estoy usando?")
        denied = host.execute(ram, confirmed=False)
        assert denied.cancelled and not denied.execution_verified
        result = host.execute(ram, confirmed=True)
        assert result.execution_verified and result.observation_completed and "RAM:" in result.message
        volume = chat(client, "GAIA, baja el volumen")
        result = host.execute(volume, confirmed=True)
        assert writes == [45] and result.effect_verified


def test_summary_continues_after_32_messages(application):
    with TestClient(application):
        session_id = "long-session"
        for turn in range(36):
            line = {0: "Decidimos usar SQLite.", 32: "Decidimos incluir cifrado."}.get(turn, f"Turno {turn}")
            memory.save_message(session_id, "user", line)
            memory.save_message(session_id, "assistant", f"Respuesta {turn}")
            memory.maybe_update_session_summary(session_id)
        record = memory.get_session_summary_record(session_id)
        assert record["turn_count"] == 32
        assert "Decidimos usar SQLite." in record["important_decisions"]
        memory.maybe_update_session_summary(session_id, force=True)
        updated = memory.get_session_summary_record(session_id)
        assert updated["turn_count"] == 36
        assert {"Decidimos usar SQLite.", "Decidimos incluir cifrado."} <= set(updated["important_decisions"])


def test_private_recall_audio_is_scoped_and_removed(application, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(api, "TTS_ENABLED", True)
    monkeypatch.setattr(api, "TTS_ENGINE", "piper")
    monkeypatch.setattr(api, "speech_to_text", lambda _: "¿Recuerdas el faro?")
    (tmp_path / "audio").mkdir()

    async def fake_tts(text, output_path):
        assert "Faro azul" in text
        Path(output_path).write_bytes(b"audio fixture")
        return output_path

    monkeypatch.setattr(api, "text_to_speech", fake_tts)
    with TestClient(application) as client:
        chat(client, "Recuerda que el Faro azul guía al equipo")
        result = client.post("/api/chat/voice", params=PC, files=WAV, headers=HEADERS).json()
        url = result["audio_url"]
        assert url
        memory.register_device("other-voice", ["voice"])
        other = {"Authorization": "Bearer " + memory.create_device_token("other-voice")["token"]}
        assert client.get(url, headers=other).status_code == 404
        reply = client.get(url, headers=HEADERS)
        assert reply.content == b"audio fixture"
        assert reply.headers["Cache-Control"] == "no-store"
        assert client.get(url, headers=HEADERS).status_code == 404
