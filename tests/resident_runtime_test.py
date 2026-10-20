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


if __name__ == "__main__":
    test_capture()
    test_hotkey()
    test_wiring()
    print("RESIDENT RUNTIME CONTRACT PASS")
