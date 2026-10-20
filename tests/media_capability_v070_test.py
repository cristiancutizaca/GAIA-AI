from __future__ import annotations

import platform
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

from action_engine import ActionEngine
from capabilities import CapabilityRequest, default_capability_registry
from media_session import MockMediaSession, set_mock_session


def main() -> None:
    registry = default_capability_registry()
    expected = {"media.status": 0, "media.play_pause": 1, "media.next": 1, "media.previous": 1, "media.stop": 1}
    for capability, risk in expected.items():
        definition = registry.get(capability)
        assert definition is not None and definition.implemented
        assert definition.risk_level == risk
        assert definition.executor.startswith("ActionEngine._media_")

    with tempfile.TemporaryDirectory() as tmp:
        engine = ActionEngine(project_dir=Path(tmp), projects_file=Path(tmp) / "projects.json")
        session = MockMediaSession(title="Prueba GAIA", artist="Sistema", state="paused")
        set_mock_session(session)
        try:
            status = engine.execute_capability(CapabilityRequest("media.status", {}))
            assert status.success and status.execution_verified
            assert status.data["title"] == "Prueba GAIA" and status.data["state"] == "paused"

            toggled = engine.execute_capability(CapabilityRequest("media.play_pause", {}))
            assert toggled.success and toggled.data["state"] == "playing"
            assert engine.execute_capability(CapabilityRequest("media.next", {})).success
            assert engine.execute_capability(CapabilityRequest("media.previous", {})).success
            stopped = engine.execute_capability(CapabilityRequest("media.stop", {}))
            assert stopped.success and stopped.data["state"] == "stopped"
        finally:
            set_mock_session(None)

        degraded = engine.execute_capability(CapabilityRequest("media.status", {}))
        assert degraded.status == "UNAVAILABLE"
        assert degraded.success is False
        assert degraded.execution_verified is False
        assert degraded.capability_available is False
        assert degraded.data.get("available") is False
        if platform.system() != "Windows":
            assert degraded.data.get("reason") == "unsupported_os"

    media_source = (ROOT / "lumen-pc" / "media_session.py").read_text(encoding="utf-8").casefold()
    assert "spotify" not in media_source
    assert "client_secret" not in media_source
    assert "access_token" not in media_source
    assert "requests" not in media_source
    assert "httpx" not in media_source
    assert "urllib" not in media_source
    print("MEDIA CAPABILITY V070 TEST OK: mock SMTC, allowlisted controls, graceful degradation and no provider credentials/scraping.")


if __name__ == "__main__":
    main()
