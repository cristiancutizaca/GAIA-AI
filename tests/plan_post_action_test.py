"""Contrato HTTP de plan_id, completion, cancelación y auditoría por pasos."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_plan_post_action_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "plan-post-action-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_ACTION_CONFIRM_POLICY": "CONFIRM_EXECUTION",
    })
    from fastapi.testclient import TestClient
    from main import app

    headers = {"Authorization": "Bearer plan-post-action-secret"}
    plan = {
        "type": "plan",
        "confidence": 0.99,
        "actions": [
            {"type": "action", "action": "system_status", "args": {}, "confidence": 0.99},
            {"type": "action", "action": "list_projects", "args": {}, "confidence": 0.99},
        ],
    }
    with TestClient(app) as client:
        planned = client.post("/api/chat", headers=headers, json={"message": "plan post action", "intent": plan})
        assert planned.status_code == 200, planned.text
        payload = planned.json()
        assert payload["kind"] == "plan" and payload["plan"]["plan_id"] == payload["action_id"]
        bad = client.post("/api/actions/complete", headers=headers, json={
            "action_id": payload["action_id"], "session_id": payload["session_id"], "device": "pc",
            "success": True, "message": "incorrecto", "data": {"actions": []},
        })
        assert bad.status_code == 409, bad.text
        steps = [
            {"success": True, "action": "system_status", "message": "estado validado", "data": {"duration_ms": 1.0}},
            {"success": True, "action": "list_projects", "message": "proyectos validados", "data": {"duration_ms": 2.0}},
        ]
        completed = client.post("/api/actions/complete", headers=headers, json={
            "action_id": payload["action_id"], "session_id": payload["session_id"], "device": "pc",
            "success": True, "message": "Plan completado.", "data": {"plan_id": payload["action_id"], "actions": steps, "completed": 2, "total": 2},
        })
        assert completed.status_code == 200, completed.text
        history = client.get("/api/actions/history", headers=headers, params={"session_id": payload["session_id"]})
        assert history.status_code == 200
        rows = history.json()
        assert {row["step"] for row in rows} >= {0, 1, 2}
        assert all(row["plan_id"] == payload["action_id"] for row in rows)

        cancelled_plan = client.post("/api/chat", headers=headers, json={"message": "otro plan", "intent": plan}).json()
        cancelled = client.post("/api/actions/complete", headers=headers, json={
            "action_id": cancelled_plan["action_id"], "session_id": cancelled_plan["session_id"], "device": "pc",
            "success": False, "message": "Ejecución cancelada antes de comenzar.", "data": {"plan_id": cancelled_plan["action_id"], "actions": [], "completed": 0, "total": 2, "cancelled": True},
        })
        assert cancelled.status_code == 200, cancelled.text
        cancelled_history = client.get("/api/actions/history", headers=headers, params={"session_id": cancelled_plan["session_id"]}).json()
        assert cancelled_history[0]["status"] == "cancelled"

print("PLAN POST ACTION TEST OK: plan_id, completion, cancelación cero y auditoría por pasos.")
