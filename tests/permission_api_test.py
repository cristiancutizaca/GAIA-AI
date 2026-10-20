"""Permission Memory API contracts."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="gaia_permission_api_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory" / "lumen_memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-permission-api-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lumen-core"))
    from fastapi.testclient import TestClient
    from main import app

    headers = {"Authorization": "Bearer test-permission-api-secret"}
    with TestClient(app) as client:
        granted = client.post("/api/permissions", headers=headers, json={"capability": "apps.open", "resource_scope": "spotify", "decision": "ALWAYS_ALLOW", "risk_level": 1, "device_id": "pc-main"})
        assert granted.status_code == 200 and granted.json()["status"] == "granted"
        listed = client.get("/api/permissions", headers=headers)
        assert listed.status_code == 200 and any(item["capability"] == "apps.open" and item["resource_scope"] == "spotify" for item in listed.json()["permissions"])
        proposed = client.post("/api/chat", headers=headers, json={"message": "abre Spotify", "device": "pc-main"})
        assert proposed.status_code == 200 and proposed.json()["kind"] == "action" and proposed.json()["confirmation_required"] is False
        proposed_payload = proposed.json()
        assert proposed_payload["resource_scope_version"] == "1"
        assert proposed_payload["permission_entries"][0]["resource_scope"] == "spotify"
        assert proposed_payload["action"]["resource_scope"] == "spotify"
        assert proposed_payload["confirmation_options"]["allow_always"] is True
        revoked = client.delete("/api/permissions", headers=headers, params={"capability": "apps.open", "resource_scope": "spotify", "device_id": "pc-main"})
        assert revoked.status_code == 200 and revoked.json()["removed"] == 1
        proposed_after_revoke = client.post("/api/chat", headers=headers, json={"message": "abre Spotify", "device": "pc-main"})
        assert proposed_after_revoke.status_code == 200 and proposed_after_revoke.json()["confirmation_required"] is False
        assert proposed_after_revoke.json()["confirmation_options"]["allow_always"] is True
        import memory
        default_moderate = memory.resolve_permission(principal_type="master", principal_id="", device_id="pc-main", capability="files.rename", resource_scope="/tmp/demo", current_risk_level=2, include_default=True)
        assert default_moderate and default_moderate["effective_decision"] == "ASK"

print("PERMISSION API TEST OK: grant/list/revoke, default low-risk auto policy and moderate ASK.")
