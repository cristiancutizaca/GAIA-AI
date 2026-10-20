"""v0.8 automation, routines and scheduler contract."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_automation_v080_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-automation-v080-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_AUTOMATION_MODE": "NOTIFY_ONLY",
    })
    import automation_store
    from automation_engine import AutomationEngine
    from event_engine import Event, EventEngine
    from scheduler import Scheduler
    import memory

    memory.init_db()
    routine = automation_store.save_routine({"name": "Rutina segura", "steps": [{"action": "display_list", "args": {}}], "max_risk": 0}, owner_device="pc-main", enabled=True)
    assert routine["steps"][0]["action"] == "display_list"
    try:
        automation_store.save_routine({"name": "Demasiados", "steps": [{"action": "display_list"}] * 6}, owner_device="pc-main")
        raise AssertionError("routine length must be bounded")
    except ValueError:
        pass
    rule = automation_store.save_rule({"name": "Aviso Ollama", "trigger": {"event_type": "ollama.offline"}, "conditions": [{"field": "payload.status", "op": "eq", "value": "offline"}], "routine_id": routine["routine_id"], "cooldown_seconds": 5}, owner_device="pc-main", enabled=True)
    assert rule["enabled"] is True
    engine = EventEngine(queue_max=32)
    automation = AutomationEngine(mode="NOTIFY_ONLY")
    engine.subscribe("automation", automation.handle_event)
    scheduler = Scheduler(engine)

    async def scenario() -> None:
        await engine.start()
        assert engine.publish(Event.create("ollama.offline", source="test", source_id="health", payload={"status": "offline"}, severity="warning", dedup_key="automation-offline")) is True
        await engine.queue.join()
        notes = automation_store.list_notifications("pc-main")
        assert any("Aviso Ollama" == note["title"] for note in notes)
        due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        schedule = automation_store.save_schedule({"name": "Ahora", "schedule_type": "ONE_TIME", "spec": {"at": due}, "routine_id": routine["routine_id"], "next_due_at": due}, owner_device="pc-main", enabled=True)
        assert await scheduler.tick(now=datetime.now(timezone.utc)) == 1
        await engine.queue.join()
        assert await scheduler.tick(now=datetime.now(timezone.utc)) == 0
        claimed_runs = []
        with memory.get_db() as conn:
            claimed_runs = [dict(row) for row in conn.execute("SELECT * FROM automation_runs WHERE schedule_id=?", (schedule["schedule_id"],)).fetchall()]
        assert len(claimed_runs) == 1 and claimed_runs[0]["status"] == "completed"
        await engine.stop()

    asyncio.run(scenario())

print("AUTOMATION SCHEDULER V080 TEST OK: typed rules, routines, NOTIFY_ONLY, atomic due claim and no duplicate run.")
