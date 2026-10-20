"""v0.8.0: event-to-routine bridge and verified result reconciliation."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_e2e_v080_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"), "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "e2e-secret", "GAIA_AUTOMATION_MODE": "ROUTINES"})
    import automation_store
    import llm
    import memory
    from automation_runtime import AutomationRuntime
    from event_engine import Event

    memory.init_db()
    routine = automation_store.save_routine({"name": "Rutina E2E", "steps": [{"action": "display_list", "args": {}, "risk_level": 0}], "max_risk": 0}, owner_device="pc-main", enabled=True)
    rule = automation_store.save_rule({"name": "Regla E2E", "trigger": {"event_type": "core.ready"}, "routine_id": routine["routine_id"], "cooldown_seconds": 5}, owner_device="pc-main", enabled=True)
    run_id = "run-e2e-v080"
    now = datetime.now(timezone.utc).isoformat()
    with memory.get_db() as conn:
        conn.execute("INSERT INTO automation_runs(run_id,schedule_id,rule_id,routine_id,dedup_key,chain_id,status,started_at,created_at) VALUES (?,?,?,?,?,?,?,?,?)", (run_id, None, rule["rule_id"], routine["routine_id"], "e2e-v080", "e2e-v080", "pending", now, now))

    async def scenario() -> None:
        runtime = AutomationRuntime()
        await runtime.start()
        before = llm.metrics()["llm_calls"]
        assert runtime.publish(Event.create("core.ready", source="e2e", source_id="start", payload={"run_id": run_id})) is True
        await runtime.events.queue.join()
        assert llm.metrics()["llm_calls"] == before
        pending = [row for row in memory.list_states("pending_action:") if row["key"].startswith("pending_action:")]
        assert len(pending) == 1, pending
        pending_value = __import__("json").loads(pending[0]["value"])
        assert pending_value["approved"] is True and pending_value["intent"]["name"] == "display_list", pending_value
        assert pending_value["automation_run_id"] == run_id
        with memory.get_db() as conn:
            queued = conn.execute("SELECT status FROM automation_runs WHERE run_id=?", (run_id,)).fetchone()[0]
        assert queued == "queued"
        assert runtime.publish(Event.create("action.completed", source="action_host", source_id=pending[0]["key"].split("pending_action:", 1)[1], payload={"action_id": pending[0]["key"].split("pending_action:", 1)[1], "automation_run_id": run_id, "status": "SUCCESS", "success": True, "execution_verified": True, "effect_verified": True})) is True
        await runtime.events.queue.join()
        with memory.get_db() as conn:
            completed = conn.execute("SELECT status,result_json FROM automation_runs WHERE run_id=?", (run_id,)).fetchone()
        assert completed[0] == "completed" and '"execution_verified":true' in completed[1], completed
        await runtime.stop()

    asyncio.run(scenario())

print("AUTOMATION E2E V080 TEST OK: event triggers safe pending routine, no LLM, and verified completion closes the run.")
