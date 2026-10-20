"""v0.8.0: dry-run is side-effect free."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_dryrun_v080_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"), "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "dryrun-secret"})
    import automation_store
    from automation_engine import AutomationEngine
    from event_engine import Event
    import memory

    memory.init_db()
    routine = {"routine_id": "dry", "enabled": True, "steps": [{"action": "display_list", "args": {}, "risk_level": 0}], "max_risk": 0}
    rule = {"rule_id": "dry-rule", "name": "Dry", "trigger": {"event_type": "core.ready"}, "routine_id": "dry"}
    called = []
    engine = AutomationEngine(mode="ROUTINES", routine_executor=lambda *_: called.append(True) or {"status": "SUCCESS"})
    preview = engine.dry_run(rule, Event.create("core.ready", source="test"), routine)
    assert preview["status"] == "READY" and preview["would_execute"] is True, preview
    assert called == []
    assert memory.list_states("pending_action:") == []
    assert automation_store.list_notifications("pc-main") == []

print("AUTOMATION DRY RUN V080 TEST OK: preview is side-effect free and never invokes the executor.")
