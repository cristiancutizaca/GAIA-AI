from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))
from desktop_api import LumenDesktopAPI

api = LumenDesktopAPI(os.environ["LUMEN_CORE_URL"], os.environ["LUMEN_SECRET"])
status_info = api.status()
assert status_info.get("version") == "1.0.0-rc6-pc" and "vault" in status_info and "features" in status_info, status_info
assert "automation" in api.automation_status(), "automation status endpoint must be reachable"
chat = api.send_assistant("hola GAIA")
assert chat.get("kind") == "chat" and chat.get("response"), chat
status = api.send_assistant("Gaia, dime cómo está mi PC")
if status.get("kind") == "action" and status.get("confirmation_required"):
    status = api.confirm_action(status)
assert status.get("kind") == "chat" and status.get("success") is True and "CPU" in status.get("deterministic_response", ""), status
print("DESKTOP CLIENT INTEGRATION OK")
