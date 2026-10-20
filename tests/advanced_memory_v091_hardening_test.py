from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_memory_v091_hardening_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-v091-hardening-master-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_DEVICE_TOKENS_ENABLED": "true",
    })
    from fastapi.testclient import TestClient
    import advanced_memory
    import memory
    from authz import Principal
    from main import app
    from routes.api import _prepare_context

    assert memory.schema_version() == 9
    with memory.get_db() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(memory_items)")}
        assert {"namespace_type", "namespace_id"} <= cols
        assert "session_owners" in {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    a = advanced_memory.save_item(memory_key="device.host", kind="device_system", category="host", content="HOST-A-PRIVATE", source_type="SYSTEM", source_ref="doctor", device_id="android-a", user_confirmed=True)
    b = advanced_memory.save_item(memory_key="device.host", kind="device_system", category="host", content="HOST-B-PRIVATE", source_type="SYSTEM", source_ref="doctor", device_id="android-b", user_confirmed=True)
    assert memory.get_session_owner("never-created") == {}
    assert advanced_memory.get_item(a["id"])["status"] == "active"
    assert advanced_memory.get_item(b["id"])["status"] == "active"
    assert not any(row["status"] == "superseded" for row in advanced_memory.get_history(a["id"]))

    explicit = advanced_memory.save_item(memory_key="user.preference", kind="preference", category="style", content="Prefiero respuestas breves.", source_type="USER_EXPLICIT", source_ref="chat:explicit", device_id="android-a", user_confirmed=True, pinned=True)
    inferred = advanced_memory.save_item(memory_key="user.preference", kind="preference", category="style", content="Prefiero respuestas largas.", source_type="CHAT_INFERRED", source_ref="chat:inferred", device_id="android-a", user_confirmed=False, pinned=False)
    assert advanced_memory.get_item(explicit["id"])["status"] == "active"
    assert inferred["status"] == "candidate"

    try:
        advanced_memory.save_item(memory_key="blocked", kind="semantic", category="x", content="event payload must not persist", source_type="SYSTEM", source_ref="event:123")
    except ValueError:
        pass
    else:
        raise AssertionError("event provenance was accepted")

    for index in range(10):
        advanced_memory.save_item(memory_key=f"project.marker.{index}", kind="project", category="ctx", content=f"LAPTOP-CONTEXT-MARKER-{index}", source_type="PROJECT", source_ref="project:test", scope="project", project="GAIA", user_confirmed=True)
    bounded = advanced_memory.retrieve("LAPTOP CONTEXT MARKER", project="GAIA", limit=2, max_chars=4000)
    assert len(bounded["items"]) == 2
    assert len([line for line in bounded["context_text"].splitlines() if "LAPTOP-CONTEXT-MARKER" in line]) == 2
    assert isinstance(bounded["retrieval_ms"], (int, float)) and bounded["retrieval_ms"] >= 0

    advanced_memory.save_item(memory_key="android.private", kind="device_system", category="device", content="ANDROID-A-PRIVATE-METADATA dispositivo privado", source_type="SYSTEM", source_ref="device-system", device_id="android-a")
    principal_b = Principal(type="device", device_id="android-b", token_id="token-b", capabilities=frozenset({"chat", "memory_read", "memory_write"}))
    prompt, _ = _prepare_context("session-b", "¿Qué recuerdas de mi dispositivo?", "android-b", principal=principal_b)
    assert "ANDROID-A-PRIVATE-METADATA" not in prompt

    memory.save_message("session-a", "user", "SESIÓN-A-CONTENIDO-PRIVADO", "android-a")
    memory.save_message("session-b-owner", "user", "SESIÓN-B-PROPIA", "android-b")
    with TestClient(app) as client:
        master = {"Authorization": "Bearer test-v091-hardening-master-secret"}
        assert client.post("/api/devices/register", headers=master, json={"device_id": "android-b", "capabilities": ["chat", "memory_read", "memory_write"], "permission_level": 0}).status_code == 200
        token_response = client.post("/api/devices/android-b/token", headers=master, json={"ttl_days": 2})
        assert token_response.status_code == 200
        owner = {"Authorization": "Bearer " + token_response.json()["token"]}
        assert client.post("/api/memory/advanced/consolidate", headers=owner, json={"session_id": "session-a", "max_messages": 8}).status_code == 403
        assert client.get("/api/memory/history/session-a", headers=owner).status_code == 404
        assert client.get("/api/memory/context/session-a", headers=owner).status_code == 404
        assert client.get("/api/memory/sessions/session-a/summary", headers=owner).status_code == 404
        sessions = client.get("/api/memory/sessions", headers=owner)
        assert sessions.status_code == 200 and all(row["session_id"] != "session-a" for row in sessions.json())
        own = client.post("/api/memory/advanced/consolidate", headers=owner, json={"session_id": "session-b-owner", "max_messages": 8})
        assert own.status_code == 200 and own.json()["llm_used"] is False

print("ADVANCED MEMORY V091 HARDENING TEST OK: namespaces, provenance blocks, bounded context, chat isolation and session ownership.")
