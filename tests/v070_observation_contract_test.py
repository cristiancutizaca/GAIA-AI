from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

from action_engine import ActionEngine
from capabilities import CapabilityRequest, CapabilityValidationError, default_capability_registry
from desktop_context import get_desktop_context
from uia import _normalise_control

with tempfile.TemporaryDirectory(prefix="gaia_v070_observation_") as tmp:
    os.environ["LUMEN_DATA_DIR"] = tmp
    context = get_desktop_context(force_refresh=True)
    assert "available" in context and "active_window" in context

    engine = ActionEngine(project_dir=Path(tmp), projects_file=Path(tmp) / "projects.json")
    observed = engine.execute_capability(CapabilityRequest("desktop.context", {"force_refresh": True}))
    assert "available" in observed.data
    if context.get("available"):
        assert observed.success and observed.execution_verified and observed.status == "SUCCESS"
        assert observed.observation_completed is True
    else:
        assert observed.success is False
        assert observed.execution_verified is False
        assert observed.status == "UNAVAILABLE"
        assert observed.capability_available is False

    registry = default_capability_registry()
    assert registry.request("uia.inspect_window", {"window_id": "123", "max_controls": 20}).capability == "uia.inspect_window"
    try:
        registry.request("uia.inspect_window", {"window_id": "bad"})
    except CapabilityValidationError:
        pass
    else:
        raise AssertionError("UIA aceptó window_id no numérico")
    try:
        registry.request("uia.list_controls", {"window_id": "123", "max_controls": 201})
    except CapabilityValidationError:
        pass
    else:
        raise AssertionError("UIA aceptó max_controls fuera de rango")
    try:
        registry.request("uia.invoke_control", {"window_id": "123", "control_id": "button-1"})
    except CapabilityValidationError:
        pass
    else:
        raise AssertionError("UIA invoke aceptó un control sin identidad canónica y expected_target")
    try:
        registry.request("uia.set_value", {"window_id": "123", "control_id": "uia:abc", "value": "password=secret", "expected_target": {"window_id": "123"}})
    except CapabilityValidationError:
        pass
    else:
        raise AssertionError("UIA set_value aceptó un valor sensible")

    class ElementInfo:
        control_type = "Edit"
        automation_id = "passwordBox"

    class PasswordControl:
        element_info = ElementInfo()
        def window_text(self): return "Password"
        def rectangle(self): return type("R", (), {"left": 1, "top": 2, "right": 3, "bottom": 4})()
        def is_enabled(self): return True
        def has_focus(self): return True

    row = _normalise_control("123", PasswordControl())
    assert row["sensitive"] is True and row["value"] is None

    capture = engine.execute({"name": "screen_capture_display", "args": {"display_id": "primary"}})
    if capture.data.get("available"):
        assert capture.success and capture.status == "SUCCESS" and capture.observation_completed
    else:
        assert capture.success is False and capture.status == "UNAVAILABLE" and capture.execution_verified is False

print("V070 OBSERVATION CONTRACT TEST OK: desktop context fast path, strict UIA schemas, sensitive redaction and on-demand capture policy.")
