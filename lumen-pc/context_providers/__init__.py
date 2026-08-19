"""Proveedores de contexto de solo lectura para los clientes PC de GAIA."""

from pathlib import Path

from .active_window import get_active_window
from .ollama_provider import collect_ollama_context
from .project_provider import detect_active_project
from .system import collect_context


def collect_desktop_context(*, projects_file=None, base_dir=None, process_limit: int = 12) -> dict:
    """Aggregate PC context while keeping each source best-effort and read-only."""
    active_window = get_active_window()
    project_context = detect_active_project(active_window, projects_file=projects_file, base_dir=base_dir)
    project = project_context.get("active_project") or {}
    project_path = project.get("path") if project else None
    return {
        "active_window": active_window,
        "ollama": collect_ollama_context(),
        "project": project_context,
        "system": collect_context(project_path=Path(project_path) if project_path else None, process_limit=process_limit),
    }


__all__ = ["collect_context", "collect_desktop_context", "get_active_window", "collect_ollama_context", "detect_active_project"]
