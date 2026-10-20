"""P0: personal folders are discovery-only and file mutation scopes are explicit."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))
sys.path.insert(0, str(ROOT / "lumen-pc"))

with tempfile.TemporaryDirectory(prefix="gaia_v063_p0_") as tmp:
    base = Path(tmp)
    os.environ.update({
        "LUMEN_DATA_DIR": str(base / "data"),
        "GAIA_TRUSTED_FOLDERS_FILE": str(base / "trusted_folders.json"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-v063-p0-security-secret",
    })

    from action_engine import ActionEngine
    from trusted_folders import default_personal_folders, grant_trusted_folder, is_trusted_path
    from action_intent import ActionIntent
    from routes.api import _intent_permission_key

    for row in default_personal_folders():
        assert row["trusted"] is False, row
        assert row["rights"] == [], row
        assert row["write_allowed"] is False, row

    source = base / "source"
    destination = base / "destination"
    blocked = base / "blocked"
    project = base / "project"
    for folder in (source, destination, blocked, project):
        folder.mkdir()
    source_file = source / "note.txt"
    source_file.write_text("gaia", encoding="utf-8")

    read_only = grant_trusted_folder(str(blocked))
    assert read_only["trusted"] is True
    assert read_only["rights"] == ["OPEN", "READ"], read_only
    assert is_trusted_path(blocked / "new.txt", right="COPY_TO") is False

    grant_trusted_folder(str(source), rights=["READ", "COPY_FROM"])
    grant_trusted_folder(str(destination), rights=["READ", "CREATE", "COPY_TO"])
    engine = ActionEngine(project_dir=project, projects_file=base / "projects.json")
    copied = engine.execute({"name": "file_copy", "args": {"source": str(source_file), "destination": str(destination / "copy.txt")}})
    assert copied.success, copied

    denied = engine.execute({"name": "file_copy", "args": {"source": str(source_file), "destination": str(blocked / "copy.txt")}})
    assert denied.success is False, denied

    source_scope = _intent_permission_key(ActionIntent(name="file_copy", args={"source": str(source_file), "destination": str(destination / "copy-2.txt")}, risk_level=2))[1]
    other_scope = _intent_permission_key(ActionIntent(name="file_copy", args={"source": str(source_file), "destination": str(project / "copy-2.txt")}, risk_level=2))[1]
    assert source_scope.startswith("file_copy:from=folder:")
    assert "->to=folder:" in source_scope
    assert source_scope != other_scope

print("V063 P0 SECURITY TEST OK: personal folders require consent; file mutation rights and compound scopes are enforced.")
