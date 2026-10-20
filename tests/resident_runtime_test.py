"""Read-only resident runtime contracts. Run with python tests/resident_runtime_test.py."""
from __future__ import annotations
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))
sys.path.insert(0, str(ROOT / "tools"))

import desktop_shell as module
from desktop_shell import AudioCapture, GlobalHotkey


class Samples:
    def tobytes(self):
        return b"\x01\x00" * 8000


class FakeStream:
    def __init__(self, *, callback, **kwargs):
        self.callback = callback
        assert kwargs["samplerate"] == 16000
        assert kwargs["channels"] == 1
        assert kwargs["dtype"] == "int16"
        self.closed = False

    def start(self):
        self.callback(Samples(), 8000, None, None)

    def stop(self):
        pass

    def close(self):
        self.closed = True


class FakeSD:
    InputStream = FakeStream


def test_capture():
    previous = module.sd
    module.sd = FakeSD()
    paths = []
    try:
        recorder = AudioCapture(paths.append)
        assert recorder.start()["status"] == "CAPTURING"
        result = recorder.stop()
        assert result["status"] == "FINALIZED"
        assert len(paths) == 1
        with wave.open(str(paths[0]), "rb") as input_file:
            assert input_file.getframerate() == 16000
            assert input_file.getnchannels() == 1
            assert input_file.getsampwidth() == 2
            assert input_file.getnframes() == 8000
        paths[0].unlink()
        recorder.start()
        assert recorder.stop(deliver=False)["status"] == "DISCARDED"
        assert len(paths) == 1
    finally:
        module.sd = previous
        for path in paths:
            path.unlink(missing_ok=True)


def test_hotkey():
    assert GlobalHotkey._parse("Ctrl+Space") == (0x4002, 0x20)
    assert GlobalHotkey._parse("Ctrl+Shift+F9") == (0x4006, 0x78)
    try:
        GlobalHotkey._parse("Space")
    except ValueError:
        pass
    else:
        raise AssertionError("A global hotkey must require a modifier")
    assert not GlobalHotkey(lambda: None, lambda: None).registered


def test_wiring():
    launcher = (ROOT / "lumen-pc" / "gaia_desktop_launcher.py").read_text(encoding="utf-8")
    shell = (ROOT / "lumen-pc" / "desktop_shell.py").read_text(encoding="utf-8")
    installer = (ROOT / "install-gaia.ps1").read_text(encoding="utf-8")
    starter = (ROOT / "start-gaia.bat").read_text(encoding="utf-8")
    assert "run_remote_action_host.py" in launcher
    assert "SingleInstance" in launcher
    assert "RESTART_EXIT_CODE = 75" in launcher
    assert "self.signals.event.emit(event)" in shell
    assert "self.capture.stop(deliver=False)" in shell
    assert "requirements-desktop.txt" in installer
    assert "gaia_desktop_launcher.py" in starter
    assert "lumen-pc\\gui.py" not in starter



def test_permission_endpoint_routing():
    """Exercise the real API method without loading audio/Windows dependencies."""
    import ast
    source = (ROOT / "lumen-pc" / "desktop_api.py").read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    api_class = next(n for n in module_ast.body if isinstance(n, ast.ClassDef) and n.name == "LumenDesktopAPI")
    method = next(n for n in api_class.body if isinstance(n, ast.FunctionDef) and n.name == "confirm_permission")
    method.decorator_list = []
    method.returns = None
    for arg in method.args.args + method.args.kwonlyargs:
        arg.annotation = None
    namespace = {"LumenAPIError": type("LumenAPIError", (RuntimeError,), {})}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 "<confirm_permission>", "exec"), namespace)
    calls = []

    class Fake:
        session_id = "session-123"
        def _request(self, method, path, **kwargs):
            calls.append((method, path, kwargs["json"]))
            class Response:
                def json(self): return {"status": "ok"}
            return Response()

    fake = Fake()
    confirm = namespace["confirm_permission"]
    confirm(fake, "act1", "CONFIRM_ONCE", session_id="session-456")
    assert calls[-1] == ("POST", "/api/actions/approve",
                         {"action_id": "act1", "session_id": "session-456", "decision": ""})
    confirm(fake, "act1", "DENY", session_id="session-456")
    assert calls[-1][1] == "/api/actions/reject", "DENY must not approve actions"
    confirm(fake, "act1", "ALWAYS_ALLOW", session_id="session-456")
    assert calls[-1][2]["decision"] == "ALWAYS_ALLOW"
    total = len(calls)
    for action_id, decision in [("", "CONFIRM_ONCE"), ("act2", "ANYTHING")]:
        try:
            confirm(fake, action_id, decision, session_id="session-456")
        except namespace["LumenAPIError"]:
            pass
        else:
            raise AssertionError("Malformed approval request was accepted")
    assert len(calls) == total


def test_microphone_off():
    from desktop_shell import DesktopShell, ShellConfig
    shell = DesktopShell(ShellConfig(microphone=True, wake_word=False), api=object())
    stops = []
    class Capture:
        def stop(self, *, deliver=True):
            stops.append(("capture", deliver))
    class Wake:
        def stop(self):
            stops.append(("wake", False))
    shell.capture = Capture()
    shell.wake = Wake()
    shell.toggle_mic()
    assert shell.health()["microphone"] is False
    assert stops == [("capture", False), ("wake", False)]
    assert shell.wake is None


def test_confirmation_ui_wiring():
    shell_code = (ROOT / "lumen-pc" / "desktop_shell.py").read_text(encoding="utf-8")
    assert 'self._show_permission(data)' in shell_code
    assert 'session_id=session_id' in shell_code
    assert 'self.decide(self.request, "DENY")' in shell_code
    assert 'self.api.kill_switch()' in shell_code
    assert 'self._request_lock.acquire(blocking=False)' in shell_code
    wake_code = (ROOT / "lumen-pc" / "wake_word.py").read_text(encoding="utf-8")
    assert "if not self.running:" in wake_code

if __name__ == "__main__":
    test_capture()
    test_hotkey()
    test_wiring()
    test_permission_endpoint_routing()
    test_microphone_off()
    test_confirmation_ui_wiring()
    print("RESIDENT RUNTIME CONTRACT PASS")
