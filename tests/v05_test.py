"""Pruebas específicas de GAIA v0.5.0: memoria, continuidad, tokens y diagnósticos."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_v05_test_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "v05-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "LUMEN_AUTO_FACTS_ENABLED": "false",
        "GAIA_AUTO_MEMORY_ENABLED": "false",
        "GAIA_ACTION_CONFIRM_POLICY": "CONFIRM_EXECUTION",
    })
    from fastapi.testclient import TestClient
    from main import app
    import memory

    headers = {"Authorization": "Bearer v05-secret"}
    with TestClient(app) as client:
        chat = client.post("/api/chat", headers=headers, json={"message": "Estamos trabajando en GAIA y luego revisaremos Android.", "device": "v05-pc"})
        assert chat.status_code == 200, chat.text
        session_id = chat.json()["session_id"]

        memory.save_fact("proyecto", "GAIA-AI", source="manual", confidence=1.0)
        search = client.get("/api/memory/search", headers=headers, params={"query": "GAIA-AI"})
        assert search.status_code == 200 and any(item["fact"] == "GAIA-AI" for item in search.json()), search.text
        facts = client.get("/api/memory/facts", headers=headers).json()
        fact_id = facts[0]["id"]
        update = client.post(f"/api/memory/fact/{fact_id}", headers=headers, json={"category": "proyecto", "fact": "GAIA-AI v0.5", "confidence": 1.0, "pinned": True})
        assert update.status_code == 200, update.text
        history = client.get(f"/api/memory/fact/{fact_id}/history", headers=headers)
        assert history.status_code == 200 and history.json(), history.text

        task = client.post("/api/memory/tasks", headers=headers, json={"task": "Validar Android", "session_id": session_id})
        assert task.status_code == 200
        task_id = task.json()["id"]
        assert client.get("/api/memory/tasks", headers=headers).json()[0]["task"] == "Validar Android"
        assert client.post(f"/api/memory/tasks/{task_id}/close", headers=headers).status_code == 200

        note = client.post("/api/memory/project-note", headers=headers, json={"project": "GAIA-AI", "note_key": "release", "note": "v0.5 conserva SQLite"})
        assert note.status_code == 200
        notes = client.get("/api/memory/project-notes", headers=headers, params={"project": "GAIA-AI"})
        assert notes.status_code == 200 and notes.json()[0]["note"] == "v0.5 conserva SQLite"
        context = client.get(f"/api/memory/context/{session_id}", headers=headers, params={"query": "GAIA"})
        assert context.status_code == 200 and "recent_messages" in context.json()
        summary = client.get(f"/api/memory/sessions/{session_id}/summary", headers=headers, params={"refresh": "true"})
        assert summary.status_code == 200 and summary.json()["summary"]

        plan = {
            "type": "plan",
            "confidence": 0.99,
            "actions": [
                {"type": "action", "action": "system_status", "args": {}, "confidence": 0.99},
                {"type": "action", "action": "list_projects", "args": {}, "confidence": 0.99},
            ],
        }
        planned = client.post("/api/chat", headers=headers, json={"message": "Ejecuta este plan seguro", "intent": plan})
        assert planned.status_code == 200 and planned.json()["kind"] == "plan", planned.text
        assert planned.json()["confirmation_required"] is True
        assert planned.json()["plan"]["type"] == "plan"
        assert len(planned.json()["plan"]["actions"]) == 2

        registered = client.post("/api/devices/register", headers=headers, json={"device_id": "v05-mobile", "device_type": "android", "name": "Android de prueba", "capabilities": ["chat", "diagnostics"]})
        assert registered.status_code == 200, registered.text
        created = client.post("/api/devices/v05-mobile/token", headers=headers, json={"ttl_days": 2})
        assert created.status_code == 200 and created.json().get("token"), created.text
        token = created.json()["token"]
        token_headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/status", headers=token_headers).status_code == 200
        listed = client.get("/api/devices/v05-mobile/tokens", headers=headers)
        assert listed.status_code == 200 and "token_hash" not in listed.text
        assert client.post(f"/api/device-tokens/{created.json()['token_id']}/revoke", headers=headers).status_code == 200
        assert client.get("/api/status", headers=token_headers).status_code == 401

        diagnostics = client.get("/api/diagnostics", headers=headers)
        assert diagnostics.status_code == 200, diagnostics.text
        payload = diagnostics.json()
        assert {"core", "database", "vault", "ollama", "voice", "action_engine", "devices", "version"}.issubset(payload)
        assert "secret" not in diagnostics.text.lower() and "token_hash" not in diagnostics.text

print("V05 TEST OK: memoria, continuidad, plan seguro, tokens hashados y diagnósticos.")
