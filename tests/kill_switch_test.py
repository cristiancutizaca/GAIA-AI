"""Master kill switch and CHAT_ONLY contracts."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="gaia_kill_switch_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory" / "lumen_memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-kill-switch-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_ACTIONS_ENABLED": "true",
        "GAIA_MODE": "FULL",
    })
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lumen-core"))
    from fastapi.testclient import TestClient
    from main import app
    import routes.api as api_routes

    headers = {"Authorization": "Bearer test-kill-switch-secret"}
    with TestClient(app) as client:
        control = client.get("/api/actions/control", headers=headers)
        assert control.status_code == 200 and control.json()["enabled"] is True

        proposed = client.post("/api/chat", headers=headers, json={"message": "abre la calculadora", "device": "kill-test"})
        assert proposed.status_code == 200 and proposed.json()["kind"] == "action"
        action_id = proposed.json()["action_id"]

        stopped = client.post("/api/actions/kill-switch", headers=headers)
        assert stopped.status_code == 200 and stopped.json()["enabled"] is False and stopped.json()["pending_cancelled"] >= 1
        assert client.post("/api/actions/complete", headers=headers, json={"action_id": action_id, "session_id": proposed.json()["session_id"], "device": "kill-test", "success": True, "message": "falso", "data": {}}).status_code == 404

        blocked = client.post("/api/chat", headers=headers, json={"message": "abre Spotify", "device": "kill-test"})
        assert blocked.status_code == 200 and blocked.json()["response"] == api_routes._ACTIONS_DISABLED_FALLBACK and blocked.json().get("action_id") is None

        chat = client.post("/api/chat", headers=headers, json={"message": "Hola, ¿sigues ahí?", "device": "kill-test"})
        assert chat.status_code == 200 and chat.json()["kind"] == "chat"

        enabled = client.post("/api/actions/enable", headers=headers)
        assert enabled.status_code == 200 and enabled.json()["enabled"] is True
        proposed_again = client.post("/api/chat", headers=headers, json={"message": "abre Spotify", "device": "kill-test"})
        assert proposed_again.status_code == 200 and proposed_again.json()["kind"] == "action"

print("KILL SWITCH TEST OK: pending action cancelled, new actions blocked, chat continued and master re-enabled actions.")
