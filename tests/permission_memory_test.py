"""Permission Memory contracts for GAIA v0.6.0."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="gaia_permission_memory_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory" / "lumen_memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-permission-memory-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lumen-core"))
    import memory

    memory.init_db()
    assert memory.schema_version() == 9
    with memory.get_db() as conn:
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"permission_grants", "automation_rules", "routines", "schedules", "automation_runs", "notifications", "automation_event_log", "memory_items", "memory_item_history", "session_owners"}.issubset(tables)

    grant_id = memory.save_permission_grant(
        principal_type="device",
        principal_id="device-token-1",
        device_id="pc-main",
        capability="apps.open",
        resource_scope="spotify",
        decision="ALWAYS_ALLOW",
        risk_level=1,
    )
    same = memory.resolve_permission(
        principal_type="device", principal_id="device-token-1", device_id="pc-main", capability="apps.open", resource_scope="spotify", current_risk_level=1
    )
    assert same and same["effective_decision"] == "ALWAYS_ALLOW" and same["risk_escalated"] is False

    escalated = memory.resolve_permission(
        principal_type="device", principal_id="device-token-1", device_id="pc-main", capability="apps.open", resource_scope="spotify", current_risk_level=2
    )
    assert escalated and escalated["effective_decision"] == "ALWAYS_ASK" and escalated["risk_escalated"] is True

    assert memory.resolve_permission(
        principal_type="device", principal_id="device-token-1", device_id="android-phone", capability="apps.open", resource_scope="spotify", current_risk_level=1
    ) is None
    assert memory.resolve_permission(
        principal_type="device", principal_id="device-token-1", device_id="pc-main", capability="apps.open", resource_scope="calculator", current_risk_level=1
    ) is None

    once_id = memory.save_permission_grant(
        principal_type="master", principal_id="", device_id="pc-main", capability="folders.open", resource_scope="/tmp/demo", decision="ALLOW_ONCE", risk_level=1
    )
    assert memory.resolve_permission(principal_type="master", device_id="pc-main", capability="folders.open", resource_scope="/tmp/demo", current_risk_level=1)["effective_decision"] == "ALLOW_ONCE"
    memory.mark_permission_used(once_id)
    assert memory.resolve_permission(principal_type="master", device_id="pc-main", capability="folders.open", resource_scope="/tmp/demo", current_risk_level=1) is None

    assert memory.revoke_permission(principal_type="device", principal_id="device-token-1", device_id="pc-main", capability="apps.open", resource_scope="spotify") == 1
    assert memory.resolve_permission(principal_type="device", principal_id="device-token-1", device_id="pc-main", capability="apps.open", resource_scope="spotify", current_risk_level=1) is None
    assert all("token" not in key.casefold() for row in memory.list_permissions() for key in row.keys() if isinstance(row[key], str))

print("PERMISSION MEMORY TEST OK: schema 9, exact scope/device isolation, risk/version re-ask, once grants and revoke.")
