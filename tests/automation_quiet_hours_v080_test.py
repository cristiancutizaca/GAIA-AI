"""v0.8.0: quiet hours suppress unattended routine execution."""
from __future__ import annotations

import asyncio
from datetime import datetime
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_quiet_v080_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"), "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "quiet-secret"})
    import automation_engine
    import automation_store
    from automation_engine import AutomationEngine
    from event_engine import Event, EventEngine
    import memory

    memory.init_db()
    routine = automation_store.save_routine({"name": "Quiet routine", "steps": [{"action": "display_list", "args": {}, "risk_level": 0}], "max_risk": 0}, owner_device="pc-main", enabled=True)
    automation_store.save_rule({"name": "Quiet rule", "trigger": {"event_type": "core.ready"}, "routine_id": routine["routine_id"], "quiet_hour_policy": "skip"}, owner_device="pc-main", enabled=True)
    original = (automation_engine.AUTOMATION_QUIET_HOURS_ENABLED, automation_engine.AUTOMATION_QUIET_START, automation_engine.AUTOMATION_QUIET_END)
    automation_engine.AUTOMATION_QUIET_HOURS_ENABLED = True
    automation_engine.AUTOMATION_QUIET_START = datetime.now().hour
    automation_engine.AUTOMATION_QUIET_END = (automation_engine.AUTOMATION_QUIET_START + 1) % 24
    calls = []

    async def scenario() -> None:
        engine = EventEngine(queue_max=32)
        automation = AutomationEngine(mode="ROUTINES", routine_executor=lambda *_: calls.append(True) or {"status": "SUCCESS"})
        engine.subscribe("automation", automation.handle_event)
        await engine.start()
        assert engine.publish(Event.create("core.ready", source="test", source_id="quiet")) is True
        await engine.queue.join()
        assert calls == []
        await engine.stop()

    try:
        asyncio.run(scenario())
    finally:
        automation_engine.AUTOMATION_QUIET_HOURS_ENABLED, automation_engine.AUTOMATION_QUIET_START, automation_engine.AUTOMATION_QUIET_END = original

print("AUTOMATION QUIET HOURS V080 TEST OK: configured quiet hours suppress unattended execution.")
