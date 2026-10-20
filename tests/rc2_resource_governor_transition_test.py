from __future__ import annotations

import asyncio
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "lumen-core"))

from resource_governor import HardwareSnapshot, ResourceGovernor


def sample(*, battery: bool = False, ac: bool | None = True, cpu: float = 20.0, memory: float = 20.0, temperature: float | None = 45.0) -> HardwareSnapshot:
    return HardwareSnapshot(8, 48000, "not_detected", battery, ac, "Linux", temperature, cpu, memory, 400.0)


with tempfile.TemporaryDirectory(prefix="gaia_rc2_governor_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"), "LUMEN_LLM_BACKEND": "mock", "GAIA_AUTOMATION_MODE": "OFF"})
    sys.path.insert(0, str(ROOT / "lumen-core"))
    from automation_runtime import AutomationRuntime

    readings = [sample(), sample(cpu=95.0, memory=95.0), sample(cpu=95.0, memory=95.0), sample(), sample(), sample(), sample(battery=True, ac=False), sample(battery=True, ac=False), sample(battery=True, ac=True)]
    cursor = {"index": 0}
    def provider():
        index = min(cursor["index"], len(readings) - 1)
        cursor["index"] += 1
        return readings[index]
    governor = ResourceGovernor("laptop_balanced", sample_provider=provider)
    runtime = AutomationRuntime()
    runtime.governor = governor
    base_scheduler = runtime._base_scheduler_interval
    base_watchers = dict(runtime._base_watcher_intervals)

    normal = runtime._apply_governor()
    assert normal["thermal_state"] == "normal" and normal["defer_consolidation"] is False
    assert runtime.scheduler.interval == base_scheduler * 1.5

    first_pressure = runtime._apply_governor()
    assert first_pressure["thermal_state"] == "normal"
    throttled = runtime._apply_governor()
    assert throttled["thermal_state"] == "throttled" and throttled["defer_consolidation"] is True
    assert runtime.scheduler.interval == base_scheduler * 2.0
    assert all(runtime.watchers._watchers[name].interval == min(300.0, max(15.0, base * 3.0)) for name, base in base_watchers.items())

    recovering_1 = runtime._apply_governor()
    recovering_2 = runtime._apply_governor()
    assert recovering_1["thermal_state"] == "throttled" and recovering_2["thermal_state"] == "throttled"
    recovered = runtime._apply_governor()
    assert recovered["thermal_state"] == "normal" and recovered["defer_consolidation"] is False
    assert runtime.scheduler.interval == base_scheduler * 1.5

    battery_1 = runtime._apply_governor()
    assert battery_1["reason"] == "battery" and battery_1["defer_consolidation"] is True and battery_1["proactive_llm_per_minute"] == 0
    battery_2 = runtime._apply_governor()
    assert battery_2["reason"] == "battery"
    ac_recovery = runtime._apply_governor()
    assert ac_recovery["reason"] == "profile" and ac_recovery["defer_consolidation"] is False

    async def bounded_lifecycle() -> None:
        runtime._governor_refresh_seconds = 0.01
        tasks = await runtime.start()
        assert runtime.status()["resources"]["shared_runtime_authority"] is True
        assert runtime.status()["resources"]["read_only"] is True
        assert runtime._governor_task in tasks
        await asyncio.sleep(0.025)
        await runtime.stop()
        assert runtime._governor_task is None and runtime.status()["started"] is False

    asyncio.run(bounded_lifecycle())

print("RC2 RESOURCE GOVERNOR TRANSITION TEST OK: shared authority, sustained-pressure debounce, battery deferment, recovery and bounded monitor lifecycle verified.")
