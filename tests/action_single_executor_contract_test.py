"""GAIA v2.0 single executor smoke tests. Pure Python 3.11, no server required.

This tests the production methods via AST without importing hardware or
network dependencies. It does NOT prove Windows action execution.
"""
from __future__ import annotations
import ast
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = (ROOT / "lumen-pc" / "desktop_api.py").read_text(encoding="utf-8")
CORE_SOURCE = (ROOT / "lumen-core" / "routes" / "api.py").read_text(encoding="utf-8")


def extract(method: str, names: dict):
    tree = ast.parse(API_SOURCE)
    owner = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "LumenDesktopAPI")
    node = next(x for x in owner.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x.name == method)
    node.decorator_list = []
    node.returns = None
    for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
        arg.annotation = None
    if node.args.vararg:
        node.args.vararg.annotation = None
    if node.args.kwarg:
        node.args.kwarg.annotation = None
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, f"<GAIA:{method}>", "exec"), names)
    return names[method]


class FakeClient:
    def __init__(self):
        self.session_id = "session-alpha"
        self.approvals = []
        self.calls = []
        self.direct_executions = 0

    def confirm_permission(self, action_id, decision, *, session_id):
        self.approvals.append((action_id, decision, session_id))
        return {"status": "approved" if decision != "DENY" else "rejected"}

    def _request(self, method, endpoint, **kwargs):
        self.calls.append((method, endpoint))
        class Reply:
            def json(self):
                return {"kind": "action", "action_id": "act-1", "session_id": "session-beta",
                        "approved": True, "confirmation_required": False,
                        "action": {"name": "open_calculator"}}
        return Reply()

    def desktop_context(self, *, level="FOREGROUND"):
        return {"desktop_snapshot": {}}

    def request_envelope(self, **kwargs):
        return {"channel": kwargs.get("channel")}


def parsed(data):
    return SimpleNamespace(confirmation_required=bool(data.get("confirmation_required")),
                           kind="action", steps=[], is_plan=False, action_id=data.get("action_id"))


def main():
    base = {"parse_action_response": parsed, "REMOTE_HOST_ENABLED": True,
            "ACTION_CONFIRM_POLICY": "CONFIRM_EXECUTION",
            "LumenAPIError": RuntimeError,
            "DEVICE": "pc-main", "LLM_CLIENT_TIMEOUT": 3.0,
            "json": json, "response_for_display": lambda x: "Permiso necesario"}
    confirm = extract("confirm_action", dict(base))
    cancel = extract("cancel_action", dict(base))
    voice = extract("send_voice", dict(base))
    client = FakeClient()
    waiting = {"kind": "action", "action_id": "act-1", "session_id": "session-beta",
               "confirmation_required": True, "approved": False}
    result = confirm(client, waiting)
    assert result["execution_verified"] is False
    assert client.approvals == [("act-1", "CONFIRM_ONCE", "session-beta")]

    queued = {**waiting, "confirmation_required": False, "approved": True}
    result = confirm(client, queued)
    assert result["execution_verified"] is False
    assert len(client.approvals) == 1, "Auto-approved intent must not be approved twice"
    assert client.direct_executions == 0, "PC Action Host is the only executor"

    result = cancel(client, waiting)
    assert result["cancelled"] is True and result["execution_verified"] is False
    assert client.approvals[-1] == ("act-1", "DENY", "session-beta")

    with tempfile.TemporaryDirectory(prefix="gaia_voice_") as temporary:
        audio = Path(temporary) / "recording.wav"
        audio.write_bytes(b"RIFFFAKEWAVE")
        response = voice(client, audio)
        assert response["execution_verified"] is False
        assert response["confirmation_required"] is False
        assert client.calls[-1] == ("POST", "/api/chat/voice")
        assert client.direct_executions == 0, "Voice must not execute action locally"

    assert 'if pending.get("cancelled") or not pending.get("approved"):' in CORE_SOURCE
    assert 'Un host diferente ya reclamó esta acción.' in CORE_SOURCE
    print("GAIA SINGLE EXECUTOR CONTRACT PASS: remote ownership, reject, voice, Core authorization")


if __name__ == "__main__":
    main()
