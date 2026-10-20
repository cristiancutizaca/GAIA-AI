"""v0.9.0: advanced memory HTTP surface and device ownership."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_memory_api_v090_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-advanced-memory-v090-master-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    from main import app

    master = {"Authorization": "Bearer test-advanced-memory-v090-master-secret"}
    with TestClient(app) as client:
        registered = client.post("/api/devices/register", headers=master, json={"device_id": "android-memory", "capabilities": ["chat", "memory_read", "memory_write"], "permission_level": 0})
        assert registered.status_code == 200, registered.text
        token_response = client.post("/api/devices/android-memory/token", headers=master, json={"ttl_days": 2})
        assert token_response.status_code == 200, token_response.text
        owner = {"Authorization": "Bearer " + token_response.json()["token"]}

        created = client.post("/api/memory/advanced/item", headers=master, json={
            "memory_key": "gaia.release", "kind": "project", "category": "release",
            "content": "v0.9.0 usa retrieval bounded.", "source_type": "PROJECT",
            "source_ref": "project:GAIA-AI", "scope": "project", "project": "GAIA-AI",
            "device_id": "pc-main", "user_confirmed": True,
        })
        assert created.status_code == 200, created.text
        master_item = created.json()["item"]
        item_id = master_item["id"]
        searched = client.get("/api/memory/advanced/search", headers=master, params={"query": "retrieval", "project": "GAIA-AI"})
        assert searched.status_code == 200 and searched.json()["items"][0]["id"] == item_id, searched.text
        fetched = client.get(f"/api/memory/advanced/item/{item_id}?history=true", headers=master)
        assert fetched.status_code == 200 and "history" in fetched.json()

        denied_write = client.post("/api/memory/advanced/item", headers=owner, json={
            "memory_key": "foreign", "kind": "semantic", "category": "x", "content": "foreign", "device_id": "pc-main",
        })
        assert denied_write.status_code == 200, denied_write.text
        assert denied_write.json()["item"]["device_id"] == "android-memory"
        assert denied_write.json()["item"]["device_id"] != "pc-main"
        own = client.post("/api/memory/advanced/item", headers=owner, json={
            "memory_key": "android.preference", "kind": "preference", "category": "ui", "content": "Prefiero respuestas breves.", "device_id": "android-memory", "source_type": "USER_EXPLICIT", "source_ref": "android-settings",
        })
        assert own.status_code == 200, own.text
        own_id = own.json()["item"]["id"]
        owner_items = client.get("/api/memory/advanced/items", headers=owner)
        assert owner_items.status_code == 200 and any(item["id"] == own_id for item in owner_items.json())
        assert all(item["id"] != item_id for item in owner_items.json())
        assert client.get(f"/api/memory/advanced/item/{item_id}", headers=owner).status_code == 404

        edited = client.put(f"/api/memory/advanced/item/{own_id}", headers=owner, json={"content": "Prefiero respuestas cortas y claras.", "importance": 0.9})
        assert edited.status_code == 200 and edited.json()["item"]["content"].startswith("Prefiero respuestas cortas")
        flagged = client.patch(f"/api/memory/advanced/item/{own_id}/flags", headers=owner, json={"pinned": True})
        assert flagged.status_code == 200 and flagged.json()["item"]["pinned"] is True
        audit = client.get("/api/memory/advanced/audit", headers=owner)
        assert audit.status_code == 200 and all(entry.get("device_id") in {"", "android-memory"} for entry in audit.json())

        # Consolidation is deterministic and session-scoped; it never calls the LLM.
        from memory import save_message
        save_message("android-session", "user", "Decidimos revisar la memoria del proyecto.", "android-memory")
        consolidated = client.post("/api/memory/advanced/consolidate", headers=owner, json={"session_id": "android-session", "max_messages": 8})
        assert consolidated.status_code == 200 and consolidated.json()["llm_used"] is False
        assert client.delete(f"/api/memory/advanced/item/{own_id}", headers=owner).status_code == 200
        assert client.get(f"/api/memory/advanced/item/{own_id}", headers=owner).status_code == 404

        # Read-only capability does not allow writes.
        read_only_device = client.post("/api/devices/register", headers=master, json={"device_id": "android-read", "capabilities": ["memory_read"], "permission_level": 0})
        assert read_only_device.status_code == 200
        read_only_token = client.post("/api/devices/android-read/token", headers=master, json={"ttl_days": 2}).json()["token"]
        read_only = {"Authorization": "Bearer " + read_only_token}
        assert client.get("/api/memory/advanced/search", headers=read_only).status_code == 200
        assert client.post("/api/memory/advanced/item", headers=read_only, json={"memory_key": "x", "kind": "semantic", "category": "x", "content": "no"}).status_code == 403

print("ADVANCED MEMORY API V090 RC2 TEST OK: CRUD, search, history, pin/delete, deterministic consolidation, derived ownership and device capabilities.")
