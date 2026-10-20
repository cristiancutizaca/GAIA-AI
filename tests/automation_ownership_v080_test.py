"""v0.8.0: automation ownership is isolated by device."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_owner_v080_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"), "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "owner-secret"})
    import automation_store
    import memory

    memory.init_db()
    rule_pc = automation_store.save_rule({"name": "PC", "trigger": {"event_type": "core.ready"}}, owner_device="pc-main", enabled=True)
    rule_phone = automation_store.save_rule({"name": "Phone", "trigger": {"event_type": "core.ready"}}, owner_device="android-phone", enabled=True)
    routine_phone = automation_store.save_routine({"name": "Phone routine", "steps": [{"action": "display_list", "args": {}, "risk_level": 0}]}, owner_device="android-phone", enabled=True)

    assert {item["rule_id"] for item in automation_store.list_rules("pc-main")} == {rule_pc["rule_id"]}
    assert {item["rule_id"] for item in automation_store.list_rules("android-phone")} == {rule_phone["rule_id"]}
    assert automation_store.set_rule_enabled(rule_phone["rule_id"], False, owner_device="pc-main") is False
    assert automation_store.set_rule_enabled(rule_phone["rule_id"], False, owner_device="android-phone") is True
    assert automation_store.set_routine_enabled(routine_phone["routine_id"], False, owner_device="pc-main") is False
    assert automation_store.set_routine_enabled(routine_phone["routine_id"], False, owner_device="android-phone") is True

print("AUTOMATION OWNERSHIP V080 TEST OK: device-scoped listing and mutation boundaries hold.")
