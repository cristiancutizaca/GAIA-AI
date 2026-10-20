"""v0.8.0: missed schedules follow explicit bounded policies without flooding."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_missed_v080_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"), "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "missed-secret"})
    import automation_store
    from event_engine import EventEngine
    from scheduler import Scheduler
    import memory

    memory.init_db()
    now = datetime.now(timezone.utc)
    due = (now - timedelta(hours=1)).isoformat()
    schedules = {}
    for policy in ("SKIP", "RUN_ONCE", "ASK"):
        schedules[policy] = automation_store.save_schedule({"name": f"Missed {policy}", "schedule_type": "ONE_TIME", "spec": {"at": due}, "missed_policy": policy, "next_due_at": due}, owner_device="pc-main", enabled=True)

    async def scenario() -> None:
        event_engine = EventEngine(queue_max=32)
        received = []
        event_engine.subscribe("collector", lambda event: received.append(event))
        scheduler = Scheduler(event_engine)
        await event_engine.start()
        assert await scheduler.tick(now=now) == 3
        await event_engine.queue.join()
        assert [event.payload["missed_policy"] for event in received] == ["RUN_ONCE"], received
        assert len(automation_store.list_notifications("pc-main")) == 1
        with memory.get_db() as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM automation_runs ORDER BY created_at").fetchall()]
        statuses = {row["result_json"] for row in rows}
        assert len(rows) == 3
        assert any('"policy":"SKIP"' in result for result in statuses)
        assert any('"policy":"ASK"' in result for result in statuses)
        assert await scheduler.tick(now=now + timedelta(minutes=1)) == 0
        await event_engine.stop()

    asyncio.run(scenario())

print("AUTOMATION MISSED SCHEDULE V080 TEST OK: SKIP, RUN_ONCE and ASK are bounded with no flood.")
