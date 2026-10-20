"""Compatibilidad para el contexto agregado del cliente PC.

La ventana activa ya no se calcula aquí. ``DesktopContextService`` es la fuente
canónica; este módulo únicamente añade proveedores read-only legacy de proyecto,
Ollama y sistema para consumidores que todavía esperan ese shape.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from desktop_context import get_desktop_context
from .ollama_provider import collect_ollama_context
from .project_provider import detect_active_project
from .system import collect_context


def _legacy_active_window(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    window = snapshot.get("active_window") if isinstance(snapshot, dict) else None
    if not isinstance(window, dict):
        return None
    return {
        "app": str(window.get("process_name") or window.get("process") or window.get("process_executable") or "")[:160],
        "title": str(window.get("title") or "")[:240],
        "pid": window.get("pid"),
        "window_id": str(window.get("window_id") or "")[:120],
        "canonical_app_id": str(window.get("canonical_app_id") or "")[:160],
        "trusted": bool(window.get("trusted")),
        "display_id": window.get("display_id"),
        "bounds": window.get("bounds") if isinstance(window.get("bounds"), dict) else None,
    }


def get_active_window(*, force_refresh: bool = False) -> dict[str, Any] | None:
    """Legacy adapter; active window is resolved by the canonical service."""
    return _legacy_active_window(get_desktop_context(force_refresh=force_refresh))


def collect_desktop_context(*, projects_file=None, base_dir=None, process_limit: int = 12, level: str = "FOREGROUND", force_refresh: bool = False) -> dict[str, Any]:
    """Aggregate canonical desktop snapshot and best-effort read-only providers."""
    snapshot = get_desktop_context(level=level, force_refresh=force_refresh)
    active_window = _legacy_active_window(snapshot)
    project_context = detect_active_project(active_window, projects_file=projects_file, base_dir=base_dir)
    project = project_context.get("active_project") or {}
    project_path = project.get("path") if project else None
    return {
        # Keep the old shape for Core and existing clients.
        "active_window": active_window,
        "ollama": collect_ollama_context(),
        "project": project_context,
        "system": collect_context(project_path=Path(project_path) if project_path else None, process_limit=process_limit),
        # New canonical source remains available to production callers.
        "desktop_snapshot": snapshot,
        "snapshot_id": snapshot.get("snapshot_id"),
        "context_level": snapshot.get("context_level", level),
    }


__all__ = ["collect_context", "collect_desktop_context", "get_active_window", "collect_ollama_context", "detect_active_project"]
