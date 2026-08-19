from __future__ import annotations

"""Relaciona la ventana activa con proyectos previamente registrados."""

import os
from pathlib import Path
from typing import Any

from project_registry import ProjectRegistry, ProjectRegistryError


def detect_active_project(active_window: dict[str, Any] | None, *, projects_file: Path | None = None, base_dir: Path | None = None) -> dict[str, Any]:
    """Return a registered project only when its name or alias appears in the window title."""
    result: dict[str, Any] = {"active_project": None, "status": "no_match"}
    if not active_window:
        result["status"] = "window_unavailable"
        return result
    title = " ".join(str(active_window.get("title") or "").casefold().split())
    if not title:
        result["status"] = "title_unavailable"
        return result

    root = (base_dir or Path.cwd()).expanduser().resolve()
    registry_path = (projects_file or Path(os.getenv("GAIA_PROJECTS_FILE", str(root / "projects.json")))).expanduser().resolve()
    try:
        projects = _unique_projects(ProjectRegistry(registry_path, root).list_projects())
    except ProjectRegistryError:
        result["status"] = "registry_unavailable"
        return result

    matches = []
    for project in projects:
        labels = (project.name, *project.aliases)
        matched_label = max((label for label in labels if _label_in_title(label, title)), key=len, default="")
        if matched_label:
            matches.append((len(matched_label), project.name.casefold(), project, matched_label))
    if not matches:
        return result
    _, _, project, matched_label = max(matches, key=lambda item: (item[0], item[1]))
    result.update({
        "status": "matched",
        "matched_label": matched_label,
        "active_project": {
            "name": project.name,
            "path": str(project.path),
            "working_directory": str(project.working_directory),
            "trusted": bool(project.trusted),
        },
    })
    return result


def _label_in_title(label: str, title: str) -> bool:
    normalized = " ".join(str(label or "").casefold().split())
    if not normalized:
        return False
    return normalized in title


def _unique_projects(projects: list[Any]) -> list[Any]:
    unique: dict[str, Any] = {}
    for project in projects:
        unique.setdefault(project.name.casefold(), project)
    return list(unique.values())


__all__ = ["detect_active_project"]
