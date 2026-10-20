from __future__ import annotations

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_v063_remote_e2e_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-v062-e2e-master-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    from main import app

    master = {"Authorization": "Bearer test-v062-e2e-master-secret"}
    with TestClient(app) as client:
        android_reg = client.post("/api/devices/register", headers=master, json={"device_id": "android-owner", "capabilities": ["chat", "actions_request"], "permission_level": 0})
        host_reg = client.post("/api/devices/register", headers=master, json={"device_id": "pc-main", "capabilities": ["chat", "actions_execute", "action_host"], "permission_level": 1})
        assert android_reg.status_code == 200 and host_reg.status_code == 200, (android_reg.text, host_reg.text)
        android_token = client.post("/api/devices/android-owner/token", headers=master, json={"ttl_days": 2}).json()["token"]
        host_token = client.post("/api/devices/pc-main/token", headers=master, json={"ttl_days": 2}).json()["token"]
        android = {"Authorization": f"Bearer {android_token}"}
        host = {"Authorization": f"Bearer {host_token}"}
        client.post("/api/action-host/heartbeat", headers=host, json={"device_id": "pc-main", "host_version": "1.0.0-rc6-pc", "busy": False})

        first = client.post("/api/chat", headers=android, json={"message": "abre Spotify", "device": "android-owner"})
        assert first.status_code == 200, first.text
        first_payload = first.json()
        assert first_payload["kind"] == "action" and first_payload["confirmation_required"] is True and first_payload["approved"] is False, first_payload
        action_id = first_payload["action_id"]
        session_id = first_payload["session_id"]
        approved = client.post("/api/actions/approve", headers=android, json={"action_id": action_id, "session_id": session_id, "decision": "ALWAYS_ALLOW"})
        assert approved.status_code == 200, approved.text
        pending = client.get("/api/actions/pending", headers=host)
        assert pending.status_code == 200 and pending.json()["actions"], pending.text
        first_item = pending.json()["actions"][0]
        assert first_item["requesting_device"] == "android-owner" and first_item["target_host"] == "pc-main", first_item
        assert client.post("/api/actions/claim", headers=host, json={"action_id": action_id, "session_id": session_id}).status_code == 200
        completed = client.post("/api/actions/complete", headers=host, json={"action_id": action_id, "session_id": session_id, "device": "pc-main", "success": True, "message": "Spotify abierto.", "data": {"execution_verified": True}})
        assert completed.status_code == 200 and completed.json()["verified_result"]["execution_verified"] is True, completed.text

        second = client.post("/api/chat", headers=android, json={"message": "abre Spotify", "device": "android-owner"})
        assert second.status_code == 200, second.text
        second_payload = second.json()
        assert second_payload["confirmation_required"] is False and second_payload["approved"] is True and second_payload["target_host"] == "pc-main", second_payload
        second_pending = client.get("/api/actions/pending", headers=host).json()["actions"]
        assert any(item["action_id"] == second_payload["action_id"] and item["auto_approved"] for item in second_pending), second_pending

print("REMOTE ACTION E2E V063 TEST OK: Android requester, pc-main target, persistent ALWAYS_ALLOW, zero second approval and host-visible pending.")
