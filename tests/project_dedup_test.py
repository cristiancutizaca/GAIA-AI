"""Project registry and structured result deduplication tests."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))
from action_engine import ActionEngine
from project_registry import ProjectRegistry

with tempfile.TemporaryDirectory(prefix="gaia_project_dedup_") as tmp:
    root = Path(tmp)
    project_path = root / "gaia"
    project_path.mkdir()
    projects_file = root / "projects.json"
    projects_file.write_text(json.dumps({"projects": [{"name": "gaia", "aliases": ["asistente", "gaia-ai"], "path": str(project_path), "commands": {}}]}), encoding="utf-8")
    registry = ProjectRegistry(projects_file, root)
    listed = registry.list_projects()
    assert len(listed) == 1
    assert listed[0].name == "gaia"
    assert registry.resolve("asistente").name == "gaia"

    engine = ActionEngine(root, projects_file)
    result = engine.execute({"name": "list_projects", "args": {}})
    assert result.success
    assert len(result.data["projects"]) == 1
    assert result.message == "Proyectos registrados: gaia."

print("PROJECT DEDUP TEST OK: canonical project once; aliases resolve without duplicate output.")
