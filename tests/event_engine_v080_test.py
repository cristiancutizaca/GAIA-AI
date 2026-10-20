"""v0.8 EventEngine bounded data-only bus contract."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_event_engine_v080_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-event-engine-v080-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_AUTOMATION_MODE": "NOTIFY_ONLY",
    })
    from event_engine import Event, EventEngine
    import memory

    memory.init_db()

    async def scenario() -> None:
        engine = EventEngine(queue_max=32)
        received: list[str] = []

        async def subscriber(event: Event) -> None:
            received.append(event.event_type)

        engine.subscribe("test", subscriber)
        await engine.start()
        event = Event.create("ollama.offline", source="test", source_id="health", payload={"status": "offline"}, severity="warning", dedup_key="same")
        assert engine.publish(event) is True
        assert engine.publish(event) is False
        await engine.queue.join()
        assert received == ["ollama.offline"]
        assert engine.status()["dropped_duplicate"] == 1
        try:
            Event.create("not-allowlisted", source="test")
            raise AssertionError("event type must be rejected")
        except ValueError:
            pass
        try:
            Event.create("core.error", source="test", chain_depth=99)
            raise AssertionError("chain depth must be bounded")
        except ValueError:
            pass
        try:
            Event.create("core.error", source="test", payload={"x": "x" * 10000})
            raise AssertionError("payload must be bounded")
        except ValueError:
            pass
        await engine.stop()
        assert engine.status()["running"] is False

    asyncio.run(scenario())

print("EVENT ENGINE V080 TEST OK: allowlist, bounded payload, dedup, chain depth, delivery and shutdown.")
