"""Notificaciones deterministas y bounded para el Event Engine."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

import automation_store
from config import AUTOMATION_MAX_NOTIFICATIONS, AUTOMATION_QUIET_END, AUTOMATION_QUIET_HOURS_ENABLED, AUTOMATION_QUIET_START
from event_engine import Event

logger = logging.getLogger("lumen.notifications")


class NotificationService:
    def __init__(self) -> None:
        self._last_keys: dict[str, float] = {}
        self.metrics = {"created": 0, "suppressed_quiet": 0, "suppressed_dedup": 0}
        self.mode = "OFF"

    def set_mode(self, mode: str) -> None:
        self.mode = str(mode).upper()

    @staticmethod
    def quiet_hours(now: datetime | None = None) -> bool:
        if not AUTOMATION_QUIET_HOURS_ENABLED or AUTOMATION_QUIET_START == AUTOMATION_QUIET_END:
            return False
        hour = (now or datetime.now()).hour
        if AUTOMATION_QUIET_START > AUTOMATION_QUIET_END:
            return hour >= AUTOMATION_QUIET_START or hour < AUTOMATION_QUIET_END
        return AUTOMATION_QUIET_START <= hour < AUTOMATION_QUIET_END

    async def on_event(self, event: Event) -> None:
        if self.mode == "OFF":
            return
        templates = {
            "ollama.offline": ("Ollama no disponible", "Ollama no responde; no se ejecutó ninguna reparación automática.", "warning"),
            "ollama.latency_high": ("Ollama lento", "La latencia de Ollama superó el umbral configurado.", "warning"),
            "cpu_high": ("CPU elevada", "La CPU permanece elevada; revisa las aplicaciones abiertas.", "warning"),
            "memory_high": ("RAM elevada", "La memoria permanece elevada; revisa las aplicaciones abiertas.", "warning"),
            "disk_low": ("Espacio reducido", "El espacio disponible del disco requiere revisión.", "warning"),
            "battery_low": ("Batería baja", "La batería del equipo está baja.", "warning"),
        }
        template = templates.get(event.event_type)
        if not template:
            return
        if self.quiet_hours():
            self.metrics["suppressed_quiet"] += 1
            return
        key = f"{event.event_type}:{event.dedup_key}"
        now = datetime.now(timezone.utc).timestamp()
        if now - self._last_keys.get(key, 0.0) < 300:
            self.metrics["suppressed_dedup"] += 1
            return
        self._last_keys[key] = now
        title, message, severity = template
        automation_store.add_notification(title=title, message=message, severity=severity, source=f"event:{event.source}", device_scope=event.device, sensitive=False)
        self.metrics["created"] += 1
        self._prune()

    def _prune(self) -> None:
        import memory
        with memory.get_db() as conn:
            rows = conn.execute("SELECT notification_id FROM notifications ORDER BY timestamp DESC LIMIT -1 OFFSET ?", (AUTOMATION_MAX_NOTIFICATIONS,)).fetchall()
            if rows:
                conn.executemany("DELETE FROM notifications WHERE notification_id=?", [(row["notification_id"],) for row in rows])

    def status(self) -> dict[str, Any]:
        return {"mode": self.mode, **self.metrics}
