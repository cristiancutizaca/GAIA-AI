"""Event bus interno, bounded y sin autoridad de ejecución para GAIA v0.8."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from automation_store import record_event
from config import AUTOMATION_DEDUP_SECONDS, AUTOMATION_EVENT_RETENTION_DAYS, AUTOMATION_MAX_CHAIN_DEPTH, AUTOMATION_MAX_EVENT_BYTES, AUTOMATION_QUEUE_MAX

logger = logging.getLogger("lumen.events")

ALLOWED_EVENT_TYPES = frozenset({
    "core.started", "core.ready", "core.stopping", "core.error",
    "ollama.online", "ollama.offline", "ollama.latency_high",
    "device.paired", "device.connected", "device.disconnected", "device.revoked",
    "action.requested", "action.awaiting_confirmation", "action.approved", "action.claimed", "action.started", "action.completed", "action.failed",
    "app.started", "app.closed", "battery_low", "battery_state_changed", "cpu_high", "memory_high", "disk_low", "network_changed",
    "git_dirty", "git_clean", "branch_changed", "file.changed", "schedule.due", "notification.created",
})
ALLOWED_SEVERITIES = frozenset({"info", "warning", "error", "critical"})
Subscriber = Callable[["Event"], Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    source: str
    source_id: str
    host: str
    device: str
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"
    dedup_key: str = ""
    chain_id: str = ""
    chain_depth: int = 0
    expires_at: str | None = None

    @classmethod
    def create(
        cls,
        event_type: str,
        *,
        source: str,
        source_id: str = "",
        host: str = "core",
        device: str = "",
        payload: dict[str, Any] | None = None,
        severity: str = "info",
        dedup_key: str = "",
        chain_id: str = "",
        chain_depth: int = 0,
        ttl_seconds: int | None = 300,
    ) -> "Event":
        event_type = str(event_type).strip()[:100]
        source = str(source).strip()[:80]
        severity = str(severity).strip().lower()[:16]
        if event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError("event_type no permitido")
        if not source:
            raise ValueError("source es obligatorio")
        if severity not in ALLOWED_SEVERITIES:
            raise ValueError("severity no permitido")
        if not 0 <= int(chain_depth) <= AUTOMATION_MAX_CHAIN_DEPTH:
            raise ValueError("chain_depth fuera de rango")
        safe_payload = payload if isinstance(payload, dict) else {}
        encoded = json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":"), default=str)
        if len(encoded.encode("utf-8")) > AUTOMATION_MAX_EVENT_BYTES:
            raise ValueError("payload de evento demasiado grande")
        timestamp = _utc_now()
        if ttl_seconds is None:
            expires_at = None
        else:
            expires_at = _iso(timestamp + timedelta(seconds=min(86400, max(1, int(ttl_seconds)))))
        if not dedup_key:
            digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]
            dedup_key = f"{event_type}:{source}:{source_id}:{digest}"[:240]
        return cls(
            event_id=f"event_{uuid.uuid4().hex}",
            event_type=event_type,
            source=source,
            source_id=str(source_id)[:80],
            host=str(host)[:80],
            device=str(device)[:80],
            timestamp=_iso(timestamp),
            payload=json.loads(encoded),
            severity=severity,
            dedup_key=str(dedup_key)[:240],
            chain_id=str(chain_id or uuid.uuid4().hex)[:80],
            chain_depth=int(chain_depth),
            expires_at=expires_at,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "source_id": self.source_id,
            "host": self.host,
            "device": self.device,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
            "severity": self.severity,
            "dedup_key": self.dedup_key,
            "chain_id": self.chain_id,
            "chain_depth": self.chain_depth,
            "expires_at": self.expires_at,
        }


class EventEngine:
    """Minimal async event bus with fail-closed limits and no effect execution."""

    def __init__(self, *, queue_max: int = AUTOMATION_QUEUE_MAX) -> None:
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=min(1024, max(32, int(queue_max))))
        self._subscribers: list[tuple[str, Subscriber]] = []
        self._dedup: dict[str, float] = {}
        self._dedup_prune_at = 0.0
        self._task: asyncio.Task | None = None
        self._stopping = False
        self.metrics: dict[str, int] = {"published": 0, "processed": 0, "dropped_queue": 0, "dropped_duplicate": 0, "dropped_expired": 0, "subscriber_errors": 0}

    def subscribe(self, name: str, callback: Subscriber) -> None:
        safe_name = str(name).strip()[:80]
        if not safe_name or not callable(callback):
            raise ValueError("subscriber inválido")
        if any(existing == safe_name for existing, _ in self._subscribers):
            return
        self._subscribers.append((safe_name, callback))

    def unsubscribe(self, name: str) -> None:
        self._subscribers = [(existing, callback) for existing, callback in self._subscribers if existing != name]

    def publish(self, event: Event | dict[str, Any]) -> bool:
        if self._stopping:
            return False
        if isinstance(event, dict):
            event = Event.create(
                str(event.get("event_type", "")), source=str(event.get("source", "external")), source_id=str(event.get("source_id", "")), host=str(event.get("host", "core")), device=str(event.get("device", "")), payload=event.get("payload") if isinstance(event.get("payload"), dict) else {}, severity=str(event.get("severity", "info")), dedup_key=str(event.get("dedup_key", "")), chain_id=str(event.get("chain_id", "")), chain_depth=int(event.get("chain_depth", 0)), ttl_seconds=None,
            )
        now = time.monotonic()
        if now >= self._dedup_prune_at:
            cutoff = now - max(5.0, float(AUTOMATION_DEDUP_SECONDS))
            self._dedup = {key: value for key, value in self._dedup.items() if value >= cutoff}
            self._dedup_prune_at = now + min(60.0, max(5.0, float(AUTOMATION_DEDUP_SECONDS)))
        last = self._dedup.get(event.dedup_key)
        if last is not None and now - last < AUTOMATION_DEDUP_SECONDS:
            self.metrics["dropped_duplicate"] += 1
            return False
        if event.expires_at:
            try:
                expires = datetime.fromisoformat(event.expires_at)
                if expires <= _utc_now():
                    self.metrics["dropped_expired"] += 1
                    return False
            except ValueError:
                return False
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            if event.severity == "critical":
                self.metrics["dropped_queue"] += 1
                logger.error("Cola de eventos llena; se descarta evento critical para no bloquear el Core")
            else:
                self.metrics["dropped_queue"] += 1
            return False
        self._dedup[event.dedup_key] = now
        self.metrics["published"] += 1
        return True

    async def start(self) -> asyncio.Task:
        if self._task and not self._task.done():
            return self._task
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="event-engine")
        return self._task

    async def stop(self) -> None:
        self._stopping = True
        task = self._task
        self._task = None
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._dedup.clear()
        self._dedup_prune_at = 0.0

    async def _run(self) -> None:
        while not self._stopping:
            event = await self.queue.get()
            try:
                record_event(event.as_dict(), retention_days=AUTOMATION_EVENT_RETENTION_DAYS)
                self.metrics["processed"] += 1
                for name, callback in tuple(self._subscribers):
                    try:
                        result = callback(event)
                        if inspect.isawaitable(result):
                            await result
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.metrics["subscriber_errors"] += 1
                        logger.exception("Subscriber de evento falló: %s", name)
            finally:
                self.queue.task_done()

    def status(self) -> dict[str, Any]:
        return {"running": bool(self._task and not self._task.done()), "queue_depth": self.queue.qsize(), "queue_max": self.queue.maxsize, "dedup_entries": len(self._dedup), "subscribers": [name for name, _ in self._subscribers], **self.metrics}
