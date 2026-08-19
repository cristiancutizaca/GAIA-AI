from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import tempfile
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))
from action_engine import ActionEngine

with tempfile.TemporaryDirectory(prefix="gaia_process_safety_") as tmp:
    project = Path(tmp)
    process_file = project / ".gaia_processes.json"
    process_file.write_text(json.dumps([{
        "pid": 1234,
        "creation_time": 100.0,
        "executable": "/usr/bin/gaia-child",
        "command": ["gaia-child", "serve"],
        "project": "demo",
        "started_at": 100.0,
    }]), encoding="utf-8")

    class AccessDenied(Exception):
        pass

    class NoSuchProcess(Exception):
        pass

    class FakeProcess:
        terminated = False

        def create_time(self):
            return 200.0

        def exe(self):
            return "/usr/bin/gaia-child"

        def cmdline(self):
            return ["gaia-child", "serve"]

        def terminate(self):
            self.terminated = True

    fake_process = FakeProcess()
    fake_psutil = types.SimpleNamespace(Process=lambda pid: fake_process, AccessDenied=AccessDenied, NoSuchProcess=NoSuchProcess)
    previous = sys.modules.get("psutil")
    sys.modules["psutil"] = fake_psutil
    try:
        engine = ActionEngine(project_dir=project, projects_file=project / "missing.json")
        result = engine.execute({"name": "stop_gaia_process", "args": {"pid": "1234", "creation_time": "100.0"}})
        assert not result.success
        assert "reutilizado" in result.message or "creation_time" in result.message
        assert fake_process.terminated is False
    finally:
        if previous is None:
            sys.modules.pop("psutil", None)
        else:
            sys.modules["psutil"] = previous

print("PROCESS SAFETY TEST OK")
