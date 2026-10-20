"""Standalone regression: GAIA user autostart and verified action feedback.

Only needs the Python standard library; does not modify real login settings.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_autostart():
    spec = importlib.util.spec_from_file_location("gaia_startup_test_module", ROOT / "tools" / "gaia_startup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="gaia_autostart_") as t:
        root = Path(t)
        python_path = root / ".venv" / "bin" / "python"
        python_path.parent.mkdir(parents=True)
        python_path.write_text("fake python", encoding="utf-8")
        launcher = root / "lumen-pc" / "gaia_desktop_launcher.py"
        launcher.parent.mkdir()
        launcher.write_text("fake launcher", encoding="utf-8")
        module.ROOT = root
        module.AUTOSTART = root / ".config" / "autostart" / "gaia.desktop"
        original = module.platform.system
        try:
            module.platform.system = lambda: "Linux"
            assert module.status()["status"] == "DISABLED"
            assert module.enable()["status"] == "ENABLED"
            assert module.status()["status"] == "ENABLED"
            entry = module.AUTOSTART.read_text(encoding="utf-8")
            assert "Exec=" in entry
            assert str(python_path) in entry
            assert "[Desktop Entry]\nType=Application\n" in entry
            python_path.unlink()
            assert module.status()["status"] == "BROKEN"
            assert module.disable()["status"] == "DISABLED"
        finally:
            module.platform.system = original


def _extract_action_result():
    source = (ROOT / "lumen-pc" / "desktop_api.py").read_text(encoding="utf-8")
    parsed = ast.parse(source)
    cls = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == "LumenDesktopAPI")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "action_result")
    method.decorator_list = []
    method.returns = None
    for arg in method.args.args + method.args.kwonlyargs:
        arg.annotation = None
    error = type("LumenAPIError", (RuntimeError,), {})
    scope = {"re": re, "LumenAPIError": error}
    module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    exec(compile(module, "<action_result>", "exec"), scope)
    return scope["action_result"], error


def test_verified_action_result():
    action_result, error = _extract_action_result()

    class Client:
        rows = []
        def _request(self, method, route, **kwargs):
            assert (method, route) == ("GET", "/api/actions/history")
            assert kwargs["params"]["session_id"] == "session-001"
            class Response:
                def json(other):
                    return self.rows
            return Response()

    client = Client()
    assert action_result(client, "action-001", "session-001") is None
    client.rows = [
        {"action_id": "action-001:1", "status": "success", "success": True},
        {"action_id": "action-001", "status": "success", "success": 1,
         "result": {"natural_response": "Calculadora abierta", "execution_verified": True}},
    ]
    result = action_result(client, "action-001", "session-001")
    assert result["success"] is True and result["execution_verified"] is True
    assert result["outcome_verified"] is True
    assert result["response"] == "Calculadora abierta"
    client.rows = [{"action_id": "action-001", "status": "SUCCESS", "success": 1,
                    "result": {"natural_response": "Diagnóstico completado", "observation_completed": True}}]
    observation = action_result(client, "action-001", "session-001")
    assert observation["execution_verified"] is False and observation["outcome_verified"] is True
    client.rows = [{"action_id": "action-001", "status": "FAILED", "success": 0,
                    "result": {"message": "App no encontrada", "execution_verified": False}}]
    result = action_result(client, "action-001", "session-001")
    assert result["success"] is False and result["execution_verified"] is False
    try:
        action_result(client, "invalid/path", "session-001")
        raise AssertionError("Invalid action id was accepted")
    except error:
        pass


def test_core_claim_and_desktop_contracts():
    core = (ROOT / "lumen-core" / "routes" / "api.py").read_text(encoding="utf-8")
    desktop = (ROOT / "lumen-pc" / "desktop_shell.py").read_text(encoding="utf-8")
    launcher = (ROOT / "lumen-pc" / "gaia_desktop_launcher.py").read_text(encoding="utf-8")
    assert "if item.get(\"claimed_by\"):" in core
    assert "La acción ya fue reclamada; nunca se ejecuta dos veces." in core
    assert "if pending.get(\"claimed_by\") or pending.get(\"completed\"):" in core
    assert 'str(pending.get("claimed_by_token") or "")' in core
    assert "self._watch_action(" in desktop
    assert "Acción verificada:" in desktop
    assert "Core still unavailable; will retry" in launcher
    assert "Desktop exited code=" in launcher


if __name__ == "__main__":
    test_autostart()
    test_verified_action_result()
    test_core_claim_and_desktop_contracts()
    print("GAIA AUTOSTART AND VERIFIED ACTION RESULT CONTRACT PASS")
