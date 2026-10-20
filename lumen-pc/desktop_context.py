"""Servicio canónico de contexto de escritorio, efímero y read-only.

El servicio no captura pantalla, no persiste foreground state y no concede
autoridad de ejecución. Todo target usado posteriormente por una mutación debe
ser revalidado por el host en el momento de ejecutar.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import time
import uuid
from typing import Any

SNAPSHOT_SCHEMA_VERSION = "1"
DEFAULT_TTL_SECONDS = 2.0
CONTEXT_LEVELS = {
    "NONE",
    "FOREGROUND",
    "FOCUSED_CONTROL",
    "UIA_INSPECTION",
    "SCREEN_CAPTURE",
    "VISION",
}


class DesktopContextError(RuntimeError):
    pass


def _copy_context(value: dict[str, Any]) -> dict[str, Any]:
    """Copy JSON-shaped context without retaining mutable nested references."""
    try:
        import json
        return json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return dict(value)


@dataclass
class DesktopContextService:
    """Canonical request-time context provider with a short TTL cache."""

    ttl_seconds: float = DEFAULT_TTL_SECONDS
    host_id: str = "pc-main"

    def __post_init__(self) -> None:
        try:
            self.ttl_seconds = max(0.25, min(10.0, float(self.ttl_seconds)))
        except (TypeError, ValueError):
            self.ttl_seconds = DEFAULT_TTL_SECONDS
        self.host_id = str(self.host_id or "pc-main").strip()[:80] or "pc-main"
        self._cached: dict[str, Any] | None = None
        self._cached_at = 0.0

    def get(self, *, level: str = "FOREGROUND", force_refresh: bool = False) -> dict[str, Any]:
        requested_level = str(level or "FOREGROUND").upper()
        if requested_level not in CONTEXT_LEVELS:
            requested_level = "FOREGROUND"
        now = time.monotonic()
        if not force_refresh and requested_level in {"NONE", "FOREGROUND"} and self._cached is not None and now - self._cached_at <= self.ttl_seconds:
            cached = _copy_context(self._cached)
            cached["context_level"] = requested_level
            return cached
        snapshot = _capture_snapshot(host_id=self.host_id, context_level=requested_level, ttl_seconds=self.ttl_seconds)
        if requested_level in {"FOREGROUND", "FOCUSED_CONTROL"}:
            self._cached = _copy_context(snapshot)
            self._cached_at = now
        return _copy_context(snapshot)

    def invalidate(self) -> None:
        self._cached = None
        self._cached_at = 0.0


# Backwards-compatible name used by the v0.7.1 tests and clients.
DesktopContextProvider = DesktopContextService


def _process_metadata(pid: int) -> tuple[str, str]:
    try:
        import psutil

        process = psutil.Process(pid)
        return str(process.name() or "")[:160], str(process.exe() or "")[:400]
    except (ImportError, OSError, ValueError):
        return "", ""


def _category(process_name: str, title: str) -> str:
    text = f"{process_name} {title}".casefold()
    if any(token in text for token in ("code", "devenv", "pycharm", "idea", "notepad")):
        return "editor"
    if any(token in text for token in ("chrome", "firefox", "edge", "brave", "browser")):
        return "browser"
    if any(token in text for token in ("terminal", "powershell", "cmd", "wt.exe", "bash")):
        return "terminal"
    if any(token in text for token in ("spotify", "vlc", "music", "media")):
        return "media"
    if any(token in text for token in ("explorer", "finder", "nautilus")):
        return "file_manager"
    return "other" if text.strip() else "unknown"


def _app_identity(process_name: str, executable: str) -> tuple[str, bool, str]:
    """Return canonical app id and trust metadata for observation only."""
    process_folded = str(process_name or "").casefold()
    try:
        from safe_apps import WINDOWS_SAFE_APPS, is_trusted_executable

        for app in WINDOWS_SAFE_APPS.values():
            if process_folded and process_folded in {str(item).casefold() for item in app.process_names}:
                return f"safe:{app.canonical_name}", True, "CODE_OWNED"
        if executable and is_trusted_executable(executable):
            return f"executable:{str(executable).casefold()[:260]}", True, "USER_TRUSTED"
    except (ImportError, OSError, ValueError):
        pass
    return "", False, "UNKNOWN"


def _empty_snapshot(*, host_id: str, context_level: str, reason: str, captured_at: float, ttl_seconds: float) -> dict[str, Any]:
    snapshot_id = uuid.uuid4().hex
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "host_id": host_id,
        "captured_at": captured_at,
        "expires_at": captured_at + max(0.25, ttl_seconds),
        "desktop_available": False,
        # v0.7.1 aliases retained for clients that have not migrated yet.
        "available": False,
        "observed_at": captured_at,
        "reason": reason,
        "active_application": "",
        "active_window": None,
        "focused_control": None,
        "active_media": None,
        "foreground_app_category": "unknown",
        "context_level": context_level,
    }


def _capture_snapshot(*, host_id: str, context_level: str, ttl_seconds: float) -> dict[str, Any]:
    captured_at = time.time()
    if context_level == "NONE":
        return _empty_snapshot(host_id=host_id, context_level=context_level, reason="No se solicitó contexto de escritorio.", captured_at=captured_at, ttl_seconds=ttl_seconds)
    if platform.system() != "Windows":
        return _empty_snapshot(host_id=host_id, context_level=context_level, reason="El contexto activo estructurado está disponible en Windows; este host no es Windows.", captured_at=captured_at, ttl_seconds=ttl_seconds)
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = int(user32.GetForegroundWindow())
        if hwnd <= 0:
            return _empty_snapshot(host_id=host_id, context_level=context_level, reason="No hay ventana foreground disponible.", captured_at=captured_at, ttl_seconds=ttl_seconds)
        title_buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
        title = title_buffer.value.strip()[:240]
        pid_value = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_value))
        pid = int(pid_value.value)
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        process_name, process_executable = _process_metadata(pid)
        bounds = {"left": int(rect.left), "top": int(rect.top), "right": int(rect.right), "bottom": int(rect.bottom)}
        canonical_app_id, trusted, trust_source = _app_identity(process_name, process_executable)
        display = _display_for_bounds(bounds) or {}
        active_window = {
            "window_id": str(hwnd),
            "hwnd": hwnd,
            "title": title,
            "pid": pid,
            "process_name": process_name,
            "process": process_name,
            "process_executable": process_executable,
            "canonical_app_id": canonical_app_id,
            "trusted": trusted,
            "trust_source": trust_source,
            "display_id": display.get("display_id"),
            "bounds": bounds,
            "foreground": True,
        }
        return {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "snapshot_id": uuid.uuid4().hex,
            "host_id": host_id,
            "captured_at": captured_at,
            "expires_at": captured_at + max(0.25, ttl_seconds),
            "desktop_available": True,
            "available": True,
            "observed_at": captured_at,
            "active_application": process_name or process_executable or "unknown",
            "active_window": active_window,
            "focused_control": None,
            "active_media": None,
            "display": display or None,
            "foreground_app_category": _category(process_name, title),
            "context_level": context_level,
        }
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        return _empty_snapshot(host_id=host_id, context_level=context_level, reason=f"No se pudo consultar el foreground de Windows: {exc}", captured_at=captured_at, ttl_seconds=ttl_seconds)


def active_desktop_context(*, level: str = "FOREGROUND", force_refresh: bool = False) -> dict[str, Any]:
    return get_desktop_context(level=level, force_refresh=force_refresh)


def _display_for_bounds(bounds: dict[str, int]) -> dict[str, Any] | None:
    try:
        from platform_capabilities import display_list

        center_x = (int(bounds.get("left", 0)) + int(bounds.get("right", 0))) // 2
        center_y = (int(bounds.get("top", 0)) + int(bounds.get("bottom", 0))) // 2
        for display in display_list():
            work = display.get("work_area") or {}
            if int(work.get("left", 0)) <= center_x < int(work.get("right", 0)) and int(work.get("top", 0)) <= center_y < int(work.get("bottom", 0)):
                return {"display_id": display.get("display_id"), "name": display.get("name"), "primary": bool(display.get("primary"))}
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        return None
    return None


_DEFAULT_PROVIDER = DesktopContextService(
    ttl_seconds=float(os.getenv("GAIA_DESKTOP_CONTEXT_TTL_SECONDS", str(DEFAULT_TTL_SECONDS))),
    host_id=os.getenv("GAIA_PC_DEVICE_ID", "pc-main"),
)


def get_desktop_context(*, level: str = "FOREGROUND", force_refresh: bool = False) -> dict[str, Any]:
    return _DEFAULT_PROVIDER.get(level=level, force_refresh=force_refresh)


__all__ = [
    "CONTEXT_LEVELS",
    "SNAPSHOT_SCHEMA_VERSION",
    "DesktopContextError",
    "DesktopContextProvider",
    "DesktopContextService",
    "active_desktop_context",
    "get_desktop_context",
]
