from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

from action_host import ActionHost
from remote_action_host import RemoteActionHost

with tempfile.TemporaryDirectory(prefix="gaia_remote_loop_") as tmp:
    captured: list[dict] = []
    item = {
        "action_id": "remote-loop-1",
        "session_id": "remote-session",
        "device": "pc-main",
        "requesting_device": "android-owner",
        "target_host": "pc-main",
        "intent": {"type": "action", "name": "system_status", "args": {}, "risk_level": 0, "confidence": 0.99, "source": "remote"},
    }
    host = RemoteActionHost(core_url="http://mock", token="not-used", device_id="pc-main", project_dir=Path(tmp), action_host=ActionHost(Path(tmp)))
    host.heartbeat = lambda busy=None: {"status": "online", "busy": bool(busy)}
    host.pending = lambda: [item]
    host.claim = lambda action_id, session_id: {"status": "claimed", "action_id": action_id}
    host.complete = lambda pending, verified: (captured.append({"pending": pending, "verified": verified.as_dict()}) or {"status": "completed", "success": verified.success})
    result = host.run_once()
    assert result["pending_seen"] == 1 and result["completed"] and result["completed"][0]["status"] == "completed", result
    assert captured and captured[0]["verified"]["execution_verified"] is True
    assert captured[0]["pending"]["requesting_device"] == "android-owner" and captured[0]["pending"]["target_host"] == "pc-main"
    host.close()
    host.close()
    assert host.stop_event.is_set()

print("REMOTE ACTION HOST LOOP TEST OK: heartbeat, pending, claim, real ActionHost execution and verified completion.")
