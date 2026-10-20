"""Watchers internos de bajo costo para Event Engine v0.9.0."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any

from config import AUTOMATION_WATCHER_INTERVAL_SECONDS
from event_engine import Event, EventEngine

logger = logging.getLogger("lumen.watchers")


class BaseWatcher:
    name = "base"

    def __init__(self, engine: EventEngine, *, interval: float = AUTOMATION_WATCHER_INTERVAL_SECONDS) -> None:
        self.engine = engine
        self.interval = min(300.0, max(15.0, float(interval)))
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._backoff = 0

    async def poll(self) -> list[Event]:
        return []

    async def start(self) -> asyncio.Task:
        if self._task and not self._task.done():
            return self._task
        self._stop = asyncio.Event()
        self._backoff = 0
        self._task = asyncio.create_task(self._run(), name=f"watcher-{self.name}")
        return self._task

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        self._task = None
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                events = await self.poll()
                for event in events[:20]:
                    self.engine.publish(event)
                self._backoff = 0
                delay = self.interval
            except asyncio.CancelledError:
                raise
            except Exception:
                self._backoff = min(self._backoff + 1, 5)
                delay = min(300.0, self.interval * (2 ** self._backoff))
                logger.warning("Watcher %s falló; backoff=%ss", self.name, delay)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                continue


class HealthWatcher(BaseWatcher):
    name = "health"

    def __init__(self, engine: EventEngine, *, interval: float = AUTOMATION_WATCHER_INTERVAL_SECONDS) -> None:
        super().__init__(engine, interval=interval)
        self._last_status: str | None = None

    async def poll(self) -> list[Event]:
        import llm
        backend = await llm.check_backend()
        status = str(backend.get("status") or "unknown").lower()
        if status == self._last_status:
            return []
        self._last_status = status
        event_type = "ollama.online" if status in {"online", "ready", "ok"} else "ollama.offline"
        severity = "info" if event_type == "ollama.online" else "warning"
        return [Event.create(event_type, source=self.name, source_id="ollama", payload={"status": status, "backend": str(backend.get("backend") or "")[:40]}, severity=severity, dedup_key=f"{event_type}:{status}")]


class SystemWatcher(BaseWatcher):
    name = "system"

    def __init__(self, engine: EventEngine, *, interval: float = AUTOMATION_WATCHER_INTERVAL_SECONDS, cpu_threshold: float = 90.0, memory_threshold: float = 90.0, disk_threshold: float = 90.0) -> None:
        super().__init__(engine, interval=interval)
        self.cpu_threshold = min(99.0, max(50.0, float(cpu_threshold)))
        self.memory_threshold = min(99.0, max(50.0, float(memory_threshold)))
        self.disk_threshold = min(99.0, max(50.0, float(disk_threshold)))
        self._sustained: dict[str, int] = defaultdict(int)

    async def poll(self) -> list[Event]:
        try:
            import psutil
        except ImportError:
            return []
        cpu = float(psutil.cpu_percent(interval=None))
        memory = float(psutil.virtual_memory().percent)
        disk = float(psutil.disk_usage(str(Path.home())).percent)
        values = {"cpu_high": (cpu, self.cpu_threshold), "memory_high": (memory, self.memory_threshold), "disk_low": (disk, self.disk_threshold)}
        events: list[Event] = []
        for event_type, (value, threshold) in values.items():
            if (event_type == "disk_low" and value >= threshold) or (event_type != "disk_low" and value >= threshold):
                self._sustained[event_type] += 1
            else:
                self._sustained[event_type] = 0
            if self._sustained[event_type] >= 2:
                events.append(Event.create(event_type, source=self.name, source_id=event_type, payload={"percent": round(value, 2), "threshold": threshold}, severity="warning", dedup_key=f"{event_type}:sustained"))
        return events


class FileWatcher(BaseWatcher):
    name = "file"

    def __init__(self, engine: EventEngine, roots: list[Path], *, interval: float = AUTOMATION_WATCHER_INTERVAL_SECONDS) -> None:
        super().__init__(engine, interval=interval)
        self.roots = [path.expanduser().resolve() for path in roots[:20] if path.exists() and path.is_dir()]
        self._known: dict[str, tuple[int, int]] = {}

    def _snapshot(self) -> dict[str, tuple[int, int]]:
        current: dict[str, tuple[int, int]] = {}
        for root in self.roots:
            try:
                for path in root.rglob("*"):
                    if not path.is_file() or len(current) >= 1000:
                        continue
                    try:
                        stat = path.stat()
                        current[str(path)] = (int(stat.st_mtime_ns), int(stat.st_size))
                    except OSError:
                        continue
            except OSError:
                continue
        return current

    async def poll(self) -> list[Event]:
        current = self._snapshot()
        if not self._known:
            self._known = current
            return []
        changed = [name for name, stamp in current.items() if self._known.get(name) != stamp]
        removed = [name for name in self._known if name not in current]
        self._known = current
        events: list[Event] = []
        for path in (changed + removed)[:20]:
            # Only path metadata is emitted; file content is never read.
            event_type = "file.changed"
            digest = __import__("hashlib").sha256(path.encode("utf-8")).hexdigest()[:20]
            events.append(Event.create(event_type, source=self.name, source_id=digest, payload={"path_name": Path(path).name[:160], "change": "removed" if path in removed else "modified"}, dedup_key=f"file:{digest}:{event_type}"))
        return events


class WatcherRegistry:
    """Code-owned lazy watcher lifecycle; no dynamic plugin loading."""

    def __init__(self, engine: EventEngine, *, trusted_roots: list[Path] | None = None) -> None:
        self.engine = engine
        self._watchers: dict[str, BaseWatcher] = {
            "health": HealthWatcher(engine),
            "system": SystemWatcher(engine),
            "file": FileWatcher(engine, trusted_roots or []),
        }
        self._active: set[str] = set()

    async def ensure(self, names: set[str] | list[str]) -> None:
        for name in sorted(set(names)):
            watcher = self._watchers.get(name)
            if watcher and name not in self._active:
                await watcher.start()
                self._active.add(name)

    async def stop(self) -> None:
        for name in tuple(self._active):
            watcher = self._watchers.get(name)
            if watcher:
                await watcher.stop()
        self._active.clear()

    def active(self) -> list[str]:
        return sorted(self._active)

    def available(self) -> list[str]:
        return sorted(self._watchers)
