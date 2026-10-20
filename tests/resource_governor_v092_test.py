from __future__ import annotations

import asyncio
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

from resource_governor import HardwareSnapshot, ResourceGovernor


def snapshot(*, cpu: float, memory: float, temp: float | None = None, battery: bool = False, on_ac: bool | None = None) -> HardwareSnapshot:
    return HardwareSnapshot(12, 48000, "not_detected", battery, on_ac, "Linux", temp, cpu, memory, 64.0)

normal = ResourceGovernor("laptop_balanced")
policy = normal.observe(snapshot(cpu=8.0, memory=30.0))
assert policy["profile"] == "laptop_balanced" and policy["thermal_state"] == "normal"
assert policy["defer_consolidation"] is False

battery = ResourceGovernor("laptop_balanced")
battery_policy = battery.observe(snapshot(cpu=10.0, memory=35.0, battery=True, on_ac=False))
assert battery_policy["reason"] == "battery"
assert battery_policy["defer_consolidation"] is True
assert battery_policy["proactive_llm_per_minute"] == 0
assert battery_policy["watcher_multiplier"] >= 2.0

pressure = ResourceGovernor("laptop_balanced")
high = snapshot(cpu=95.0, memory=94.0, temp=90.0)
assert pressure.observe(high)["thermal_state"] == "normal"
assert pressure.observe(high)["thermal_state"] == "throttled"
assert pressure.policy()["defer_consolidation"] is True
for _ in range(3):
    pressure.observe(snapshot(cpu=5.0, memory=30.0, temp=45.0))
assert pressure.policy()["thermal_state"] == "normal"

assert ResourceGovernor("eco").profile == "laptop_eco"
assert ResourceGovernor("performance").profile == "laptop_performance"

os.environ.update({"LUMEN_DATA_DIR": str(ROOT / "lumen-core" / "data"), "LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "test-v092-governor-secret"})
from automation_runtime import AutomationRuntime
runtime = AutomationRuntime()
assert runtime.status()["resources"]["read_only"] is True

print("RESOURCE GOVERNOR V092 TEST OK: profiles, battery policy, thermal hysteresis and runtime status.")
