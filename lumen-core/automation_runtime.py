"""Composición lifecycle-managed de EventEngine, automatización y watchers."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import automation_store
from automation_engine import AutomationEngine
from config import AUTOMATION_MODE, RESOURCE_GOVERNOR_REFRESH_SECONDS, SAFE_MODE
from event_engine import Event, EventEngine
from automation_action_bridge import create_pending_action
from notification_service import NotificationService
from scheduler import Scheduler
from watchers import WatcherRegistry
from resource_governor import ResourceGovernor


class AutomationRuntime:
    def __init__(self) -> None:
        self.events = EventEngine()
        self.notifications = NotificationService()
        self.safe_mode = bool(SAFE_MODE)
        self.automation = AutomationEngine(mode=AUTOMATION_MODE, routine_executor=self._queue_routine, safe_mode=self.safe_mode)
        self.scheduler = Scheduler(self.events)
        self.watchers = WatcherRegistry(self.events, trusted_roots=[])
        self.governor = ResourceGovernor()
        self._base_scheduler_interval = self.scheduler.interval
        self._base_watcher_intervals = {name: watcher.interval for name, watcher in self.watchers._watchers.items()}
        self._started = False
        self._governor_task: asyncio.Task | None = None
        self._last_policy_state = ""
        self._governor_refresh_seconds = float(RESOURCE_GOVERNOR_REFRESH_SECONDS)
        self.events.subscribe("automation", self.automation.handle_event)
        self.events.subscribe("action-result", self._on_action_result)
        self.events.subscribe("notifications", self.notifications.on_event)

    def _queue_routine(self, routine: dict[str, Any], event: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
        return create_pending_action(routine, owner_device=str(rule.get("owner_device") or "pc-main"), event=event, rule=rule)

    async def _on_action_result(self, event: Event) -> None:
        if event.event_type not in {"action.completed", "action.failed"}:
            return
        payload = event.payload if isinstance(event.payload, dict) else {}
        run_id = str(payload.get("automation_run_id") or "")
        if not run_id:
            return
        status = "completed" if event.event_type == "action.completed" and bool(payload.get("success")) and bool(payload.get("execution_verified")) else "failed"
        automation_store.finish_run(run_id, status, {"action_id": str(payload.get("action_id") or ""), "status": str(payload.get("status") or ""), "success": bool(payload.get("success")), "execution_verified": bool(payload.get("execution_verified")), "effect_verified": bool(payload.get("effect_verified")), "observation_completed": bool(payload.get("observation_completed"))})

    def _apply_governor(self) -> dict[str, Any]:
        policy = self.governor.observe()
        self.scheduler.interval = min(300.0, max(5.0, self._base_scheduler_interval * float(policy["scheduler_multiplier"])))
        for name, watcher in self.watchers._watchers.items():
            base = self._base_watcher_intervals.get(name, watcher.interval)
            watcher.interval = min(300.0, max(15.0, base * float(policy["watcher_multiplier"])))
        return policy

    async def _resource_monitor(self) -> None:
        while self._started:
            await asyncio.sleep(self._governor_refresh_seconds)
            if not self._started:
                break
            policy = self._apply_governor()
            if self.safe_mode:
                continue
            # Re-apply only on a bounded transition; interactive chat is not
            # queued or throttled by this monitor.
            state = f"{policy.get('thermal_state')}:{policy.get('reason')}:{policy.get('profile')}"
            if state != self._last_policy_state:
                self._last_policy_state = state
                await self._refresh_consumer_intervals(policy)

    async def _refresh_consumer_intervals(self, policy: dict[str, Any] | None = None) -> None:
        current = policy or self.governor.policy()
        self.scheduler.interval = min(300.0, max(5.0, self._base_scheduler_interval * float(current["scheduler_multiplier"])))
        for name, watcher in self.watchers._watchers.items():
            base = self._base_watcher_intervals.get(name, watcher.interval)
            watcher.interval = min(300.0, max(15.0, base * float(current["watcher_multiplier"])))

    async def start(self) -> list[asyncio.Task]:
        if self._started:
            return []
        self._started = True
        self.automation.set_safe_mode(self.safe_mode)
        initial_policy = self._apply_governor()
        tasks = [await self.events.start()]
        self.notifications.set_mode(self.automation.mode)
        if not self.safe_mode and self.automation.is_active():
            tasks.append(await self.scheduler.start())
            await self.refresh_watchers()
        self._governor_task = asyncio.create_task(self._resource_monitor(), name="resource-governor")
        tasks.append(self._governor_task)
        self._last_policy_state = f"{initial_policy.get('thermal_state')}:{initial_policy.get('reason')}:{initial_policy.get('profile')}"
        return tasks

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        if self._governor_task is not None:
            self._governor_task.cancel()
            await asyncio.gather(self._governor_task, return_exceptions=True)
            self._governor_task = None
        await self.watchers.stop()
        await self.scheduler.stop()
        await self.events.stop()

    async def refresh_watchers(self) -> None:
        policy = self._apply_governor()
        self._last_policy_state = f"{policy.get('thermal_state')}:{policy.get('reason')}:{policy.get('profile')}"
        if self.safe_mode or not self.automation.is_active():
            await self.watchers.stop()
            return
        names: set[str] = set()
        for rule in automation_store.list_rules(include_disabled=False):
            trigger = rule.get("trigger") if isinstance(rule.get("trigger"), dict) else {}
            event_type = str(trigger.get("event_type") or "")
            if event_type.startswith("ollama.") or event_type in {"core.error", "core.ready"}:
                names.add("health")
            if event_type in {"cpu_high", "memory_high", "disk_low", "battery_low", "network_changed"}:
                names.add("system")
            if event_type == "file.changed":
                names.add("file")
        await self.watchers.ensure(names)

    def set_mode(self, mode: str) -> str:
        value = self.automation.set_mode(mode)
        self.notifications.set_mode(value)
        return value

    def pause(self, paused: bool = True) -> None:
        self.automation.pause(paused)

    def publish(self, event: Event | dict[str, Any]) -> bool:
        return self.events.publish(event)

    def status(self) -> dict[str, Any]:
        resources = self.governor.status()
        resources.update({"runtime_refresh_seconds": self._governor_refresh_seconds, "runtime_safe_mode": self.safe_mode, "shared_runtime_authority": True, "last_policy_state": self._last_policy_state})
        return {"started": self._started, "safe_mode": self.safe_mode, "automation": self.automation.status(), "events": self.events.status(), "scheduler": self.scheduler.status(), "watchers": {"active": self.watchers.active(), "available": self.watchers.available()}, "notifications": self.notifications.status(), "resources": resources}


runtime = AutomationRuntime()
