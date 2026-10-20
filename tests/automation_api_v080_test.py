"""v0.8 automation HTTP boundary contract."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_automation_api_v080_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-automation-api-v080-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_AUTOMATION_MODE": "NOTIFY_ONLY",
    })
    from fastapi.testclient import TestClient
    from main import app

    headers = {"Authorization": "Bearer test-automation-api-v080-secret"}
    with TestClient(app) as client:
        status = client.get("/api/automation/status", headers=headers)
        assert status.status_code == 200
        assert status.json()["automation"]["mode"] == "NOTIFY_ONLY"
        rule = {"name": "Regla HTTP", "trigger": {"event_type": "ollama.offline"}, "conditions": [], "steps": [{"action": "display_list", "args": {}}], "preview_confirmed": False, "enabled": False}
        denied = client.post("/api/automations", headers=headers, json=rule)
        assert denied.status_code == 409
        preview = client.post("/api/automations/dry-run", headers=headers, json={"rule": rule})
        assert preview.status_code == 200 and preview.json()["preview"]["status"] == "READY"
        rule["preview_confirmed"] = True
        saved = client.post("/api/automations", headers=headers, json=rule)
        assert saved.status_code == 200
        rule_id = saved.json()["automation"]["rule_id"]
        listed = client.get("/api/automations", headers=headers)
        assert listed.status_code == 200 and any(item["rule_id"] == rule_id for item in listed.json()["automations"])
        routine = {"name": "Rutina HTTP", "steps": [{"action": "display_list", "args": {}}], "preview_confirmed": True, "enabled": False}
        routine_resp = client.post("/api/routines", headers=headers, json=routine)
        assert routine_resp.status_code == 200
        routine_id = routine_resp.json()["routine"]["routine_id"]
        due = {"name": "Schedule HTTP", "schedule_type": "ONE_TIME", "spec": {"at": "2999-01-01T00:00:00+00:00"}, "routine_id": routine_id, "preview_confirmed": True, "enabled": False}
        schedule_resp = client.post("/api/schedules", headers=headers, json=due)
        assert schedule_resp.status_code == 200
        mode_off = client.post("/api/automation/mode", headers=headers, json={"mode": "OFF"})
        assert mode_off.status_code == 200 and mode_off.json()["mode"] == "OFF"
        blocked_enable = client.post(f"/api/automations/{rule_id}/enabled?enabled=true", headers=headers)
        assert blocked_enable.status_code == 409

print("AUTOMATION API V080 TEST OK: auth, preview, CRUD, ownership boundary and OFF mode.")
