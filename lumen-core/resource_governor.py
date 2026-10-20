"""Resource governance for long-running GAIA sessions.

The governor is read-only with respect to the host. It never changes models,
controls fans/voltage, kills interactive work, or requires GPU detection.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import os
import platform
import time
from typing import Any, Callable

PROFILE_NAMES = frozenset({
    "laptop_eco", "laptop_balanced", "laptop_performance",
    "desktop_balanced", "desktop_performance", "custom",
})

_PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    "laptop_eco": {"watcher_multiplier": 3.0, "scheduler_multiplier": 2.0, "background_concurrency": 1, "proactive_llm_per_minute": 0, "llm_keep_alive": "0", "llm_context_cap": 3072},
    "laptop_balanced": {"watcher_multiplier": 1.5, "scheduler_multiplier": 1.5, "background_concurrency": 1, "proactive_llm_per_minute": 1, "llm_keep_alive": "5m", "llm_context_cap": 4096},
    "laptop_performance": {"watcher_multiplier": 1.0, "scheduler_multiplier": 1.0, "background_concurrency": 1, "proactive_llm_per_minute": 1, "llm_keep_alive": "10m", "llm_context_cap": 8192},
    "desktop_balanced": {"watcher_multiplier": 1.0, "scheduler_multiplier": 1.0, "background_concurrency": 1, "proactive_llm_per_minute": 1, "llm_keep_alive": "10m", "llm_context_cap": 4096},
    "desktop_performance": {"watcher_multiplier": 1.0, "scheduler_multiplier": 1.0, "background_concurrency": 1, "proactive_llm_per_minute": 2, "llm_keep_alive": "10m", "llm_context_cap": 8192},
    "custom": {"watcher_multiplier": 1.0, "scheduler_multiplier": 1.0, "background_concurrency": 1, "proactive_llm_per_minute": 1, "llm_keep_alive": "10m", "llm_context_cap": 4096},
}


@dataclass(frozen=True)
class HardwareSnapshot:
    logical_cpus: int
    ram_mb: int
    gpu_info: str
    battery_present: bool
    on_ac: bool | None
    platform: str
    temperature_c: float | None
    cpu_percent: float | None
    memory_percent: float | None
    process_rss_mb: float | None


class ResourceGovernor:
    """Small policy layer for background work; interactive chat is never throttled."""

    def __init__(self, requested_profile: str | None = None, *, sample_provider: Callable[[], HardwareSnapshot] | None = None) -> None:
        self.requested_profile = (requested_profile or os.getenv("GAIA_HARDWARE_PROFILE", "")).strip().lower()
        self._sample_provider = sample_provider
        self.profile = self._resolve_profile(self.requested_profile)
        self._high_streak = 0
        self._low_streak = 0
        self._thermal_state = "normal"
        self._last_sample: HardwareSnapshot | None = None
        self._last_transition_at = 0.0
        self._transitions = 0

    @staticmethod
    def _resolve_profile(requested: str) -> str:
        if requested in PROFILE_NAMES:
            return requested
        if requested in {"eco", "balanced", "performance"}:
            return {"eco": "laptop_eco", "balanced": "laptop_balanced", "performance": "laptop_performance"}[requested]
        snapshot = ResourceGovernor._detect()
        return "laptop_balanced" if snapshot.battery_present else "desktop_balanced"

    @staticmethod
    def _detect() -> HardwareSnapshot:
        logical_cpus = max(1, int(os.cpu_count() or 1))
        ram_mb = 0
        battery_present = False
        on_ac: bool | None = None
        cpu_percent: float | None = None
        memory_percent: float | None = None
        process_rss_mb: float | None = None
        temperature_c: float | None = None
        try:
            import psutil
            virtual = psutil.virtual_memory()
            ram_mb = int(virtual.total / (1024 * 1024))
            memory_percent = float(virtual.percent)
            cpu_percent = float(psutil.cpu_percent(interval=None))
            battery = psutil.sensors_battery()
            if battery is not None:
                battery_present = True
                on_ac = bool(battery.power_plugged)
            try:
                process_rss_mb = float(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
            except (OSError, psutil.Error):
                process_rss_mb = None
            try:
                temperatures = psutil.sensors_temperatures(fahrenheit=False)
                candidates = [float(entry.current) for entries in temperatures.values() for entry in entries if entry.current is not None and float(entry.current) > 0]
                temperature_c = max(candidates) if candidates else None
            except (AttributeError, OSError, psutil.Error, ValueError):
                temperature_c = None
        except (ImportError, OSError, ValueError):
            pass
        return HardwareSnapshot(logical_cpus, ram_mb, "not_detected", battery_present, on_ac, platform.system(), temperature_c, cpu_percent, memory_percent, process_rss_mb)

    def sample(self) -> HardwareSnapshot:
        snapshot = self._sample_provider() if self._sample_provider else self._detect()
        self._last_sample = snapshot
        return snapshot

    def observe(self, snapshot: HardwareSnapshot | None = None) -> dict[str, Any]:
        sample = snapshot or self.sample()
        self._last_sample = sample
        cpu_high = sample.cpu_percent is not None and sample.cpu_percent >= 90.0
        memory_high = sample.memory_percent is not None and sample.memory_percent >= 90.0
        temperature_high = sample.temperature_c is not None and sample.temperature_c >= 85.0
        pressure = (cpu_high and memory_high) or temperature_high
        if pressure:
            self._high_streak += 1
            self._low_streak = 0
        else:
            self._low_streak += 1
            self._high_streak = 0
        if self._thermal_state == "normal" and self._high_streak >= 2:
            self._thermal_state = "throttled"
            self._last_transition_at = time.monotonic()
            self._transitions += 1
        elif self._thermal_state == "throttled" and self._low_streak >= 3:
            self._thermal_state = "normal"
            self._last_transition_at = time.monotonic()
            self._transitions += 1
        return self.policy()

    def policy(self) -> dict[str, Any]:
        policy = dict(_PROFILE_DEFAULTS[self.profile])
        sample = self._last_sample
        if sample and sample.battery_present and sample.on_ac is False:
            policy["watcher_multiplier"] = max(float(policy["watcher_multiplier"]), 2.0)
            policy["scheduler_multiplier"] = max(float(policy["scheduler_multiplier"]), 2.0)
            policy["proactive_llm_per_minute"] = 0
            policy["llm_keep_alive"] = "0"
            policy["defer_consolidation"] = True
            policy["reason"] = "battery"
        else:
            policy["defer_consolidation"] = False
            policy["reason"] = "profile"
        if self._thermal_state == "throttled":
            policy["watcher_multiplier"] = max(float(policy["watcher_multiplier"]), 3.0)
            policy["scheduler_multiplier"] = max(float(policy["scheduler_multiplier"]), 2.0)
            policy["proactive_llm_per_minute"] = 0
            policy["defer_consolidation"] = True
            policy["reason"] = "sustained_pressure"
        policy["profile"] = self.profile
        policy["thermal_state"] = self._thermal_state
        return policy

    def status(self) -> dict[str, Any]:
        snapshot = asdict(self._last_sample) if self._last_sample else None
        return {"profile": self.profile, "requested_profile": self.requested_profile or "auto", "thermal_state": self._thermal_state, "policy": self.policy(), "last_sample": snapshot, "transitions": self._transitions, "read_only": True}
