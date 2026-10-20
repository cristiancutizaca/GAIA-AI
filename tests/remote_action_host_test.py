"""Remote action ownership and PC host claim flow."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_remote_host_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-remote-host-master-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    from main import app

    master = {"Authorization": "Bearer test-remote-host-master-secret"}
    with TestClient(app) as client:
        android_reg = client.post("/api/devices/register", headers=master, json={"device_id": "android-owner", "capabilities": ["chat", "actions_request"], "permission_level": 0})
        host_reg = client.post("/api/devices/register", headers=master, json={"device_id": "pc-main", "capabilities": ["chat", "actions_execute", "action_host"], "permission_level": 1})
        assert android_reg.status_code == 200 and host_reg.status_code == 200
        android_created = client.post("/api/devices/android-owner/token", headers=master, json={"ttl_days": 2})
        host_created = client.post("/api/devices/pc-main/token", headers=master, json={"ttl_days": 2})
        assert android_created.status_code == 200 and host_created.status_code == 200
        android = {"Authorization": f"Bearer {android_created.json()['token']}"}
        host = {"Authorization": f"Bearer {host_created.json()['token']}"}
        heartbeat = client.post("/api/action-host/heartbeat", headers=host, json={"device_id": "pc-main", "host_version": "1.0.0-rc6-pc", "busy": False})
        assert heartbeat.status_code == 200 and heartbeat.json()["status"] == "online"

        proposed = client.post("/api/chat", headers=android, json={"message": "abre la calculadora", "device": "android-owner", "target_host": "pc-main"})
        assert proposed.status_code == 200 and proposed.json()["kind"] == "action"
        action_id = proposed.json()["action_id"]
        session_id = proposed.json()["session_id"]

        assert client.get("/api/actions/pending", headers=host).json()["actions"] == []
        assert client.post("/api/actions/approve", headers=android, json={"action_id": action_id, "session_id": session_id}).status_code == 200
        pending = client.get("/api/actions/pending", headers=host)
        assert pending.status_code == 200 and pending.json()["actions"] and pending.json()["actions"][0]["action_id"] == action_id
        assert pending.json()["actions"][0]["requesting_device"] == "android-owner" and pending.json()["actions"][0]["target_host"] == "pc-main"
        assert pending.json()["host_status"]["online"] is True
        assert client.post("/api/actions/claim", headers=host, json={"action_id": action_id, "session_id": session_id}).status_code == 200

        completed = client.post("/api/actions/complete", headers=host, json={
            "action_id": action_id,
            "session_id": session_id,
            "device": "pc-main",
            "success": True,
            "message": "La Calculadora se abrió correctamente.",
            "data": {"actions": [{"success": True, "action": "open_calculator", "data": {"app": "calculator", "duration_ms": 1.0}}], "completed": 1, "total": 1, "execution_verified": True, "host_version": "1.0.0-rc6-pc"},
        })
        assert completed.status_code == 200 and completed.json()["generated_by_llm"] is False and completed.json()["verified_result"]["execution_verified"] is True
        assert client.get("/api/actions/pending", headers=host).json()["actions"] == []

        unapproved = client.post("/api/chat", headers=android, json={"message": "abre Spotify", "device": "android-owner", "target_host": "pc-main"})
        assert unapproved.status_code == 200
        denied_claim = client.post("/api/actions/claim", headers=host, json={"action_id": unapproved.json()["action_id"], "session_id": unapproved.json()["session_id"]})
        assert denied_claim.status_code == 409
        # Important regression: approving with a negative decision must NEVER
        # make the pending action executable by the remote host.
        bogus_approval = client.post("/api/actions/approve", headers=android, json={
            "action_id": unapproved.json()["action_id"],
            "session_id": unapproved.json()["session_id"],
            "decision": "DENY",
        })
        assert bogus_approval.status_code == 422, bogus_approval.text
        assert client.get("/api/actions/pending", headers=host).json()["actions"] == []
        assert client.post("/api/actions/claim", headers=host, json={
            "action_id": unapproved.json()["action_id"],
            "session_id": unapproved.json()["session_id"],
        }).status_code == 409
        assert client.post("/api/actions/reject", headers=android, json={"action_id": unapproved.json()["action_id"], "session_id": unapproved.json()["session_id"]}).status_code == 200

print("REMOTE ACTION HOST TEST OK: separate Android owner, heartbeat, explicit approval, PC claim, verified completion and unapproved claim rejection.")
