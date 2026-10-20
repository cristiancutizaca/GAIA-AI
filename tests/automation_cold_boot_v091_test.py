from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_automation_v091_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-v091-automation-master-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    import automation_engine
    from event_engine import Event
    from automation_engine import AutomationEngine

    engine = AutomationEngine(mode="NOTIFY_ONLY")
    rule = {"rule_id": "cold-boot-rule", "name": "Cold boot", "cooldown_seconds": 300, "owner_device": "pc-main"}
    event = Event.create("ollama.offline", source="test", device="pc-main")
    ticks = iter((10.0, 20.0))
    original_time = automation_engine.time
    automation_engine.time = SimpleNamespace(monotonic=lambda: next(ticks))
    try:
        asyncio.run(engine._handle_match(rule, event))
        assert engine._last_run["cold-boot-rule"] == 10.0
        asyncio.run(engine._handle_match(rule, event))
        assert engine._last_run["cold-boot-rule"] == 10.0
    finally:
        automation_engine.time = original_time
    assert engine.metrics["runs_blocked"] == 0

print("AUTOMATION COLD-BOOT V091 TEST OK: first match runs and later match honors cooldown.")
