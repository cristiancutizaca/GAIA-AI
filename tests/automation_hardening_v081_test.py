"""v0.9.0: hardening/performance contracts without a new subsystem."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "lumen-core"
sys.path.insert(0, str(CORE))

with tempfile.TemporaryDirectory(prefix="gaia_hardening_v081_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "hardening-v081-master-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_AUTOMATION_MODE": "ROUTINES",
    })
    import memory
    import automation_store
    from automation_engine import AutomationEngine
    from event_engine import Event, EventEngine

    memory.init_db()

    # Fuzz-style input remains bounded and inert.
    try:
        Event.create("file.changed", source="fuzz", payload={"name": "../../" + "á" * 12000})
    except ValueError:
        pass
    else:
        raise AssertionError("large/unicode payload bypassed the event byte limit")

    try:
        Event.create("cpu_high", source="fuzz", chain_depth=99)
    except ValueError:
        pass
    else:
        raise AssertionError("chain depth bypassed the configured limit")

    invalid = AutomationEngine.validate_rule({
        "name": "\u202e hostile",
        "trigger": {"event_type": "cpu_high"},
        "conditions": [{"field": "payload.title", "op": "eval", "value": "__import__('os')"}],
        "command": "rm -rf /",
        "steps": [{"action": "system_status", "args": {}}],
    })
    assert invalid and any("operador" in item for item in invalid) and any("comandos" in item for item in invalid)

    automation_store.save_rule({
        "rule_id": "rule-targeted-v081",
        "name": "Targeted",
        "owner_device": "pc-main",
        "trigger": {"event_type": "cpu_high"},
        "conditions": [],
        "steps": [{"action": "system_status", "args": {}}],
    }, owner_device="pc-main", enabled=True)
    automation_store.save_rule({
        "rule_id": "rule-broad-v081",
        "name": "Broad",
        "owner_device": "pc-main",
        "trigger": {},
        "conditions": [],
        "steps": [{"action": "system_status", "args": {}}],
    }, owner_device="pc-main", enabled=True)
    selected = {item["rule_id"] for item in automation_store.list_rules_for_event("cpu_high")}
    assert {"rule-targeted-v081", "rule-broad-v081"} <= selected
    assert "rule-targeted-v081" not in {item["rule_id"] for item in automation_store.list_rules_for_event("memory_high")}

    engine = EventEngine(queue_max=32)
    for index in range(40):
        assert engine.publish(Event.create("cpu_high", source="fuzz", source_id=str(index), dedup_key=f"fuzz:{index}")) is (index < 32)
    assert engine.metrics["dropped_queue"] == 8
    engine._dedup["old-entry"] = time.monotonic() - 10000
    engine._dedup_prune_at = 0.0
    assert engine.publish(Event.create("cpu_high", source="fuzz", source_id="fresh", dedup_key="fuzz:fresh")) is False
    assert "old-entry" not in engine._dedup
    assert engine.status()["dedup_entries"] <= 33
    asyncio.run(engine.stop())

    due = datetime.now(timezone.utc).isoformat()
    automation_store.save_schedule({
        "schedule_id": "schedule-hot-v081",
        "name": "Due",
        "schedule_type": "ONE_TIME",
        "spec": {"at": due},
        "next_due_at": due,
        "routine_id": "routine-v081",
    }, owner_device="pc-main", enabled=True)
    assert any(item["schedule_id"] == "schedule-hot-v081" for item in automation_store.list_schedules(include_disabled=False, due_before=due))
    with memory.get_db() as conn:
        plan = conn.execute("EXPLAIN QUERY PLAN SELECT * FROM schedules WHERE enabled=1 AND next_due_at IS NOT NULL AND next_due_at<=? ORDER BY next_due_at ASC LIMIT 200", (due,)).fetchall()
    detail = " ".join(str(row[-1]) for row in plan)
    assert "idx_schedules_due" in detail, detail

print("AUTOMATION HARDENING V081 TEST OK: bounded fuzz, event selector, dedup pruning, queue limits and indexed due query.")
