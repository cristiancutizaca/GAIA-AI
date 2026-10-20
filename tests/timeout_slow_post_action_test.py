from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

import desktop_api


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def json(self) -> dict:
        return self.payload


api = desktop_api.LumenDesktopAPI()
original_request = api._request
original_post = desktop_api.POST_ACTION_TIMEOUT
original_completion = desktop_api.ACTION_COMPLETION_TIMEOUT
seen: list[float] = []


def slow_request(method: str, path: str, **kwargs):
    seen.append(float(kwargs["timeout"]))
    time.sleep(0.05)
    return FakeResponse({"status": "completed", "response": "Cancelado de forma segura."})

api._request = slow_request
# Simulate a server response slower than a 10 ms post-action budget but below client timeout.
desktop_api.POST_ACTION_TIMEOUT = 0.01
desktop_api.ACTION_COMPLETION_TIMEOUT = 0.20
try:
    started = time.perf_counter()
    result = api.cancel_action({
        "kind": "action",
        "action_id": "a" * 32,
        "session_id": "slow-session",
        "confirmation_required": True,
        "action": {"type": "action", "name": "open_vscode", "args": {}, "risk_level": 1},
        "preview": "Abrir VS Code",
    })
    elapsed = time.perf_counter() - started
finally:
    api._request = original_request
    desktop_api.POST_ACTION_TIMEOUT = original_post
desktop_api.ACTION_COMPLETION_TIMEOUT = original_completion

assert result["status"] == "completed"
assert seen == [0.20]
assert elapsed >= 0.05 and elapsed < 0.20
print("TIMEOUT SLOW POST-ACTION TEST OK: client survives simulated slow server response within effective timeout.")
