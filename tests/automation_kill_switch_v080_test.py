"""v0.8.0: kill switch has higher authority than automation rules."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_kill_v080_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"), "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "kill-secret"})
    import automation_store
    from automation_engine import AutomationEngine
    from event_engine import Event, EventEngine
    import memory

    memory.init_db()
    routine = automation_store.save_routine({"name": "Rutina segura", "steps": [{"action": "display_list", "args": {}, "risk_level": 0}], "max_risk": 0}, owner_device="pc-main", enabled=True)
    automation_store.save_rule({"name": "Regla kill", "trigger": {"event_type": "core.ready"}, "routine_id": routine["routine_id"]}, owner_device="pc-main", enabled=True)
    calls = []

    async def scenario() -> None:
        engine = EventEngine(queue_max=32)
        automation = AutomationEngine(mode="ROUTINES", routine_executor=lambda *_: calls.append(True) or {"status": "SUCCESS"})
        automation.pause(True)
        engine.subscribe("automation", automation.handle_event)
        await engine.start()
        assert engine.publish(Event.create("core.ready", source="test", source_id="kill")) is True
        await engine.queue.join()
        assert calls == [], "paused automation must not invoke the executor"
        assert automation.status()["paused"] is True
        await engine.stop()

    asyncio.run(scenario())

print("AUTOMATION KILL SWITCH V080 TEST OK: pause blocks background automation before execution.")
