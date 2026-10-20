from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

with tempfile.TemporaryDirectory(prefix="gaia_audio_v063_") as tmp:
    os.environ["LUMEN_DATA_DIR"] = tmp
    from action_engine import ActionEngine
    import platform_capabilities

    original = platform_capabilities._audio_backend
    platform_capabilities._audio_backend = lambda: (_ for _ in ()).throw(platform_capabilities.PlatformCapabilityError("backend ausente"))
    try:
        engine = ActionEngine(project_dir=Path(tmp), projects_file=Path(tmp) / "projects.json")
        result = engine.execute({"name": "list_audio_devices", "args": {}})
        assert result.success is False
        assert result.status == "UNAVAILABLE"
        assert result.execution_verified is False
        assert result.capability_available is False
        assert result.data["available"] is False and result.data["devices"] == []
    finally:
        platform_capabilities._audio_backend = original

print("AUDIO CAPABILITY V063 TEST OK: endpoint listing is read-only and unavailable backends degrade honestly.")
