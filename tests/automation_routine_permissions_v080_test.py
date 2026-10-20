"""v0.8.0: unattended routines require safe capabilities and cannot self-grant."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_permissions_v080_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"), "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "permissions-secret"})
    from automation_action_bridge import create_pending_action
    from automation_engine import AutomationEngine
    from event_engine import Event
    import memory

    memory.init_db()
    event = Event.create("core.ready", source="test")
    rule = {"rule_id": "permission-rule", "owner_device": "pc-main"}
    for step in (
        {"action": "file_delete", "args": {"path": "C:/important"}, "risk_level": 3},
        {"action": "permission_grant", "args": {}, "risk_level": 0},
        {"action": "unknown_capability", "args": {}, "risk_level": 0},
    ):
        result = create_pending_action({"enabled": True, "steps": [step]}, owner_device="pc-main", event=event.as_dict(), rule=rule)
        assert result["status"] == "NEEDS_CONFIRMATION", result

    preview = AutomationEngine(mode="ROUTINES").dry_run(rule, event, {"enabled": True, "steps": [{"action": "system_restart", "args": {}, "risk_level": 4}], "max_risk": 4})
    assert preview["status"] == "DENIED", preview

print("AUTOMATION ROUTINE PERMISSIONS V080 TEST OK: destructive, unknown and self-grant steps are blocked.")
