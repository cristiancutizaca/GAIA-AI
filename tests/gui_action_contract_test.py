"""Contrato GUI de acciones sin abrir una ventana real."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

import gui as gui_module
from gui import LumenGUI


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeWidget:
    def __init__(self):
        self.state = "normal"

    def configure(self, **kwargs):
        self.state = kwargs.get("state", self.state)


class FakeAPI:
    def __init__(self):
        self.confirmed = []
        self.cancelled = []

    def confirm_action(self, data):
        self.confirmed.append(data)
        return {"kind": "chat", "response": "Acción ejecutada."}

    def cancel_action(self, data):
        self.cancelled.append(data)
        return {"kind": "chat", "response": "Ejecución cancelada antes de comenzar."}


def make_gui(api: FakeAPI):
    instance = LumenGUI.__new__(LumenGUI)
    instance.api = api
    instance.generation_var = FakeVar("Generando")
    instance.voice_output = FakeVar(False)
    instance.send_button = FakeWidget()
    instance.voice_button = FakeWidget()
    instance.stop_button = FakeWidget()
    instance._run = lambda func, on_success=None, on_error=None: on_success(func()) if on_success else func()
    instance._append = lambda _role, _text: None
    return instance

single = {
    "kind": "action",
    "confirmation_required": True,
    "action_id": "a" * 32,
    "session_id": "session",
    "preview": "Abrir Visual Studio Code",
    "action": {"type": "action", "name": "open_vscode", "args": {}, "risk_level": 1},
}
plan = {
    "kind": "plan",
    "confirmation_required": True,
    "action_id": "p" * 32,
    "session_id": "session",
    "preview": ["Abrir VS Code", "Consultar Git", "Mostrar proyecto"],
    "plan": {"type": "plan", "plan_id": "p" * 32, "actions": [
        {"type": "action", "name": "open_vscode", "args": {}, "risk_level": 1},
        {"type": "action", "name": "git_status", "args": {}, "risk_level": 2},
        {"type": "action", "name": "show_project", "args": {}, "risk_level": 1},
    ]},
}

api = FakeAPI()
gui = make_gui(api)
seen = []
original = gui_module.messagebox.askyesno
gui_module.messagebox.askyesno = lambda title, text, parent=None: (seen.append((title, text)) or True)
try:
    gui._receive_chat(single)
    assert len(api.confirmed) == 1 and seen[-1][0].startswith("Confirmar acción")
    gui._receive_chat(plan)
    assert len(api.confirmed) == 2 and "1. Abrir VS Code" in seen[-1][1] and "3. Mostrar proyecto" in seen[-1][1]
finally:
    gui_module.messagebox.askyesno = original

api_cancel = FakeAPI()
gui_cancel = make_gui(api_cancel)
gui_module.messagebox.askyesno = lambda *_args, **_kwargs: False
try:
    gui_cancel._receive_chat(plan)
finally:
    gui_module.messagebox.askyesno = original
assert api_cancel.confirmed == [] and len(api_cancel.cancelled) == 1

print("GUI ACTION CONTRACT TEST OK: single/plan confirman; cancel no ejecuta.")
