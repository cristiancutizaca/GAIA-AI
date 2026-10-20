"""v0.7.2 first-class preflight and remote-target contracts."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

from action_engine import ActionEngine  # noqa: E402
from action_host import ActionHost  # noqa: E402
from preflight import preflight_contract  # noqa: E402
from remote_action_host import RemoteActionHost  # noqa: E402

with tempfile.TemporaryDirectory(prefix="gaia_v072_preflight_") as tmp:
    project = Path(tmp)
    engine = ActionEngine(project)
    calls = []
    original_execute = engine.execute
    engine.execute = lambda *_args, **_kwargs: calls.append(True)  # type: ignore[method-assign]

    ready = preflight_contract(engine, {"kind": "action", "action": {"name": "desktop_context", "args": {"force_refresh": True}}})
    assert ready["status"] == "READY", ready
    assert ready["preflight_only"] is True
    assert ready["execution_attempted"] is False
    assert ready["effect_verified"] is False
    assert calls == [], "preflight no debe llamar a ActionEngine.execute"

    denied = preflight_contract(engine, {"kind": "action", "action": {"name": "uia_invoke_control", "args": {"window_id": "123", "control_id": "uia:abc"}}})
    assert denied["status"] == "DENIED", denied
    assert denied["execution_attempted"] is False
    assert denied["effect_verified"] is False
    assert denied["steps"][0]["request_validated"] is False

    engine.execute = original_execute  # type: ignore[method-assign]
    host = ActionHost(project)
    host_result = host.execute({"kind": "action", "action_id": "action-preflight-1", "session_id": "session-1", "device": "pc-main", "action": {"name": "desktop_context", "args": {"force_refresh": True}}}, confirmed=True)
    assert host_result.status in {"SUCCESS", "UNAVAILABLE"}, host_result
    if host_result.status == "SUCCESS":
        assert host_result.observation_completed is True
        assert host_result.execution_verified is True
    else:
        assert host_result.capability_available is False
        assert host_result.observation_completed is False
        assert host_result.execution_verified is False

    remote = RemoteActionHost(token="test-token", device_id="pc-main", project_dir=project, client=type("Client", (), {"close": lambda self: None})())
    contract = {"kind": "action", "action": {"name": "screen_capture_window", "args": {}}}
    remote._attach_contextual_target(contract, {"active_window": {"window_id": "42", "pid": 7, "process": "trusted.exe", "process_executable": "C:/trusted.exe", "title": "Trusted", "bounds": {"left": 1, "top": 2, "right": 3, "bottom": 4}}})
    args = contract["action"]["args"]
    assert args["window_id"] == "42"
    assert args["expected_target"]["pid"] == 7
    remote.close()

print("PREFLIGHT V072 TEST OK: read-only preflight, typed denial, host boundary and remote contextual target.")
