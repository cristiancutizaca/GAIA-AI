"""v0.8.0: deterministic automation never consumes the interactive LLM path."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_priority_v080_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"), "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "priority-secret"})
    import automation_store
    import automation_engine
    from automation_engine import AutomationEngine
    from event_engine import Event, EventEngine
    import memory

    memory.init_db()
    routine = automation_store.save_routine({"name": "No LLM", "steps": [{"action": "display_list", "args": {}, "risk_level": 0}], "max_risk": 0}, owner_device="pc-main", enabled=True)
    automation_store.save_rule({"name": "No LLM rule", "trigger": {"event_type": "core.ready"}, "routine_id": routine["routine_id"]}, owner_device="pc-main", enabled=True)
    original_llm = automation_engine.__dict__.get("llm")
    calls = []

    async def scenario() -> None:
        engine = EventEngine(queue_max=32)
        automation = AutomationEngine(mode="ROUTINES", routine_executor=lambda *_: calls.append("routine") or {"status": "SUCCESS"})
        engine.subscribe("automation", automation.handle_event)
        await engine.start()
        assert engine.publish(Event.create("core.ready", source="test", source_id="interactive-priority")) is True
        await engine.queue.join()
        assert calls == ["routine"]
        assert automation.metrics["background_llm_calls"] == 0
        await engine.stop()

    asyncio.run(scenario())

print("AUTOMATION BACKGROUND PRIORITY V080 TEST OK: automation path is deterministic and does not consume LLM capacity.")
