"""v0.8.0: chain-depth and deduplication prevent event feedback loops."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_loop_v080_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"), "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "loop-secret"})
    import config
    from event_engine import Event, EventEngine
    import memory

    memory.init_db()
    try:
        Event.create("core.ready", source="test", chain_depth=config.AUTOMATION_MAX_CHAIN_DEPTH + 1)
        raise AssertionError("chain depth must be rejected")
    except ValueError:
        pass

    async def scenario() -> None:
        engine = EventEngine(queue_max=32)
        received = []
        engine.subscribe("collector", lambda event: received.append(event.event_id))
        await engine.start()
        event = Event.create("core.ready", source="test", source_id="loop", chain_id="chain", chain_depth=config.AUTOMATION_MAX_CHAIN_DEPTH)
        assert engine.publish(event) is True
        assert engine.publish(event) is False
        await engine.queue.join()
        assert received == [event.event_id], received
        await engine.stop()

    asyncio.run(scenario())

print("AUTOMATION LOOP PREVENTION V080 TEST OK: chain-depth and dedup stop feedback loops.")
