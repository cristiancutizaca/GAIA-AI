"""GUI busy-state tests without creating a real Tk window."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))
from gui import LumenGUI


class FakeInput:
    def get(self, *_args):
        return "segunda petición"

    def delete(self, *_args):
        raise AssertionError("busy guard must return before deleting input")


class FakeVar:
    def __init__(self):
        self.values = []

    def set(self, value):
        self.values.append(value)


gui = object.__new__(LumenGUI)
gui._generation_busy = True
gui.input = FakeInput()
messages: list[str] = []
gui._append = lambda _role, text: messages.append(text)
gui._send()
assert messages and "generación en curso" in messages[-1]

error_gui = object.__new__(LumenGUI)
error_gui._generation_busy = True
error_gui.generation_var = FakeVar()
error_gui._set_generation_busy = lambda busy: setattr(error_gui, "_generation_busy", busy)
error_gui._show_error = lambda exc: setattr(error_gui, "error", str(exc))
LumenGUI._generation_error(error_gui, RuntimeError("timeout"))
assert error_gui._generation_busy is False
assert error_gui.generation_var.values[-1] == "Error"
assert error_gui.error == "timeout"

print("GUI BUSY TEST OK: duplicate send blocked and error resets generation state.")
