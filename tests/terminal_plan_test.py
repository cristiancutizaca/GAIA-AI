"""Experiencia de planes del terminal sobre el coordinador compartido."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

from action_coordinator import ActionCoordinator
from action_engine import ExecutionResult


class RecordingEngine:
    SAFE_ACTIONS = {"open_vscode": (1, False), "git_status": (2, False), "show_project": (1, False)}

    def __init__(self, fail_step: int | None = None):
        self.calls = []
        self.fail_step = fail_step

    def execute(self, intent: dict) -> ExecutionResult:
        self.calls.append(intent["name"])
        step = len(self.calls)
        ok = self.fail_step != step
        return ExecutionResult(ok, intent["name"], "ok" if ok else "fallo controlado", {"duration_ms": 1.0})


def response():
    return {
        "kind": "plan",
        "confirmation_required": True,
        "action_id": "p" * 32,
        "session_id": "terminal-session",
        "preview": ["Abrir VS Code", "Consultar Git", "Mostrar proyecto"],
        "plan": {"type": "plan", "plan_id": "p" * 32, "actions": [
            {"type": "action", "name": "open_vscode", "args": {}, "risk_level": 1},
            {"type": "action", "name": "git_status", "args": {}, "risk_level": 2},
            {"type": "action", "name": "show_project", "args": {}, "risk_level": 1},
        ]},
    }


engine_yes = RecordingEngine()
confirmations = []
coordinator = ActionCoordinator(engine_yes)
result_yes = coordinator.execute(response(), confirm=lambda preview, _parsed: (confirmations.append(preview) or True))
assert result_yes["success"] is True
assert engine_yes.calls == ["open_vscode", "git_status", "show_project"]
assert len(confirmations) == 1 and "1. Abrir VS Code" in confirmations[0]

engine_no = RecordingEngine()
result_no = ActionCoordinator(engine_no).execute(response(), confirm=lambda _preview, _parsed: False)
assert result_no["cancelled"] is True and result_no["data"]["completed"] == 0 and engine_no.calls == []

engine_fail = RecordingEngine(fail_step=2)
result_fail = ActionCoordinator(engine_fail).execute(response(), confirm=lambda _preview, _parsed: True)
assert result_fail["success"] is False and engine_fail.calls == ["open_vscode", "git_status"]
assert result_fail["data"]["completed"] == 2

print("TERMINAL PLAN TEST OK: confirm yes=3 pasos, no=0 pasos, fallo detiene siguiente.")
