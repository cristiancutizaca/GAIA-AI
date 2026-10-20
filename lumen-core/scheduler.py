"""Scheduler persistente y bounded para GAIA v0.9.0."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any

import automation_store
from config import AUTOMATION_POLL_SECONDS
from event_engine import Event, EventEngine

logger = logging.getLogger("lumen.scheduler")
SCHEDULE_TYPES = frozenset({"ONE_TIME", "DAILY", "WEEKDAYS", "WEEKLY", "INTERVAL"})
MISSED_POLICIES = frozenset({"SKIP", "RUN_ONCE", "ASK"})
MISSED_GRACE_SECONDS = 300.0


def _utc(value: datetime | None = None) -> datetime:
    value = value or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def next_due(schedule: dict[str, Any], *, now: datetime | None = None, after: datetime | None = None) -> str | None:
    now_utc = _utc(now)
    basis = _utc(after) if after else now_utc
    schedule_type = str(schedule.get("schedule_type") or "").upper()
    spec = schedule.get("spec") if isinstance(schedule.get("spec"), dict) else {}
    if schedule_type not in SCHEDULE_TYPES:
        return None
    if schedule_type == "ONE_TIME":
        candidate = _parse_iso(str(spec.get("at") or schedule.get("next_due_at") or ""))
        return candidate.isoformat() if candidate and candidate > now_utc else None
    if schedule_type == "INTERVAL":
        seconds = min(86400 * 30, max(60, int(spec.get("seconds", 3600))))
        candidate = basis + timedelta(seconds=seconds)
        return candidate.isoformat()
    try:
        tz = ZoneInfo(str(schedule.get("timezone") or "UTC"))
    except (ZoneInfoNotFoundError, ValueError):
        tz = timezone.utc
    local = basis.astimezone(tz)
    hour = min(23, max(0, int(spec.get("hour", 9))))
    minute = min(59, max(0, int(spec.get("minute", 0))))
    candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    weekdays = spec.get("weekdays") if isinstance(spec.get("weekdays"), list) else []
    if schedule_type == "DAILY":
        if candidate <= local:
            candidate += timedelta(days=1)
    elif schedule_type == "WEEKDAYS":
        for _ in range(8):
            if candidate > local and candidate.weekday() < 5:
                break
            candidate += timedelta(days=1)
    elif schedule_type == "WEEKLY":
        weekday = min(6, max(0, int(spec.get("weekday", 0))))
        for _ in range(8):
            if candidate > local and candidate.weekday() == weekday:
                break
            candidate += timedelta(days=1)
    if weekdays and schedule_type in {"DAILY", "WEEKDAYS"}:
        allowed = {min(6, max(0, int(item))) for item in weekdays if str(item).lstrip("-").isdigit()}
        if allowed:
            for _ in range(8):
                if candidate > local and candidate.weekday() in allowed:
                    break
                candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc).isoformat()


class Scheduler:
    def __init__(self, event_engine: EventEngine, *, interval: float = AUTOMATION_POLL_SECONDS) -> None:
        self.event_engine = event_engine
        self.interval = min(300.0, max(5.0, float(interval)))
        self._task: asyncio.Task | None = None
        self._stopping = False
        self.metrics = {"ticks": 0, "due_found": 0, "runs_claimed": 0, "runs_skipped": 0, "errors": 0}

    async def start(self) -> asyncio.Task:
        if self._task and not self._task.done():
            return self._task
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="automation-scheduler")
        return self._task

    async def stop(self) -> None:
        self._stopping = True
        task = self._task
        self._task = None
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def tick(self, *, now: datetime | None = None) -> int:
        self.metrics["ticks"] += 1
        now_utc = _utc(now)
        due = 0
        for schedule in automation_store.list_schedules(include_disabled=False, due_before=now_utc.isoformat()):
            candidate = _parse_iso(str(schedule.get("next_due_at") or ""))
            if not candidate or candidate > now_utc:
                continue
            due += 1
            self.metrics["due_found"] += 1
            claimed = automation_store.claim_due_schedule(str(schedule.get("schedule_id") or ""), now=now_utc.isoformat())
            if not claimed:
                continue
            self.metrics["runs_claimed"] += 1
            schedule_id = str(claimed.get("schedule_id") or "")
            run_id = str(claimed.get("run_id") or "")
            following = next_due(claimed, now=now_utc, after=now_utc)
            automation_store.set_schedule_next_due(schedule_id, following)
            try:
                missed_policy = str(claimed.get("missed_policy") or "SKIP").upper()
                scheduled_at = _parse_iso(str(schedule.get("next_due_at") or ""))
                is_missed = bool(scheduled_at and (now_utc - scheduled_at).total_seconds() > MISSED_GRACE_SECONDS)
                if missed_policy not in MISSED_POLICIES:
                    missed_policy = "SKIP"
                if is_missed and missed_policy == "SKIP":
                    automation_store.finish_run(run_id, "skipped", {"reason": "missed_schedule", "policy": "SKIP"})
                    self.metrics["runs_skipped"] += 1
                    continue
                if is_missed and missed_policy == "ASK":
                    automation_store.add_notification(title=str(claimed.get("name") or "Schedule atrasado"), message="Un schedule vencido no se ejecutó automáticamente; requiere decisión explícita.", severity="warning", source="scheduler:missed_ask", device_scope=str(claimed.get("owner_device") or ""), sensitive=False)
                    automation_store.finish_run(run_id, "needs_confirmation", {"reason": "missed_schedule", "policy": "ASK"})
                    self.metrics["runs_skipped"] += 1
                    continue
                event = Event.create("schedule.due", source="scheduler", source_id=schedule_id, host="core", device=str(claimed.get("owner_device") or ""), payload={"schedule_id": schedule_id, "run_id": run_id, "routine_id": str(claimed.get("routine_id") or ""), "rule_id": str(claimed.get("rule_id") or ""), "missed_policy": missed_policy, "missed": is_missed}, severity="info", dedup_key=f"schedule:{schedule_id}:{run_id}", ttl_seconds=3600)
                if not self.event_engine.publish(event):
                    automation_store.finish_run(run_id, "skipped", {"reason": "event_queue_full"})
                    self.metrics["runs_skipped"] += 1
            except (TypeError, ValueError):
                automation_store.finish_run(run_id, "skipped", {"reason": "invalid_schedule_data"})
                self.metrics["runs_skipped"] += 1
        return due

    async def _run(self) -> None:
        while not self._stopping:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.metrics["errors"] += 1
                logger.exception("Fallo controlado en scheduler")
            await asyncio.sleep(self.interval)

    def status(self) -> dict[str, Any]:
        return {"running": bool(self._task and not self._task.done()), "interval_seconds": self.interval, **self.metrics}
