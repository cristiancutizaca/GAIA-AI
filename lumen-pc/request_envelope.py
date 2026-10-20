"""Construcción segura de metadatos de request compartidos por canales PC.

El envelope transporta datos de contexto y ownership; nunca contiene comandos ni
concede autoridad de ejecución. Los consumidores deben validar de nuevo cualquier
target en el host que vaya a producir un efecto.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid
try:
    from gaia_version import PROTOCOL_VERSION
except ImportError:
    PROTOCOL_VERSION = "1.0-RC6"

ENVELOPE_SCHEMA_VERSION = "1"
VALID_CHANNELS = {
    "desktop_text",
    "desktop_voice",
    "terminal",
    "android_text",
    "android_voice",
    "automation",
    "schedule",
    "event",
}


def _safe_text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def build_request_envelope(
    *,
    session_id: str = "",
    channel: str,
    requesting_device: str,
    target_host: str = "",
    message: str = "",
    desktop_snapshot: dict[str, Any] | None = None,
    request_id: str = "",
    audio: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return bounded, data-only request metadata.

    ``desktop_snapshot`` is copied and bounded by the caller/service. This helper
    only establishes a stable shape and does not interpret it as authority.
    """
    normalized_channel = _safe_text(channel, 32) or "desktop_text"
    if normalized_channel not in VALID_CHANNELS:
        normalized_channel = "desktop_text"
    envelope: dict[str, Any] = {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "request_id": _safe_text(request_id, 80) or uuid.uuid4().hex,
        "session_id": _safe_text(session_id, 64),
        "channel": normalized_channel,
        "requesting_device": _safe_text(requesting_device, 80),
        "target_host": _safe_text(target_host, 80),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "protocol_version": PROTOCOL_VERSION,
        "text": _safe_text(message, 12000),
    }
    if isinstance(desktop_snapshot, dict):
        envelope["desktop_snapshot"] = dict(desktop_snapshot)
    if isinstance(audio, dict):
        envelope["audio"] = {str(key)[:40]: value for key, value in audio.items() if str(key)[:40] in {"filename", "mime", "size"}}
    return envelope


__all__ = ["ENVELOPE_SCHEMA_VERSION", "PROTOCOL_VERSION", "VALID_CHANNELS", "build_request_envelope"]
