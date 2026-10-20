"""PC Action Host boundary tests."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

from action_coordinator import ActionCoordinatorError
from action_host import ActionHost

with tempfile.TemporaryDirectory(prefix="gaia_action_host_") as tmp:
    host = ActionHost(Path(tmp), policy="CONFIRM_EXECUTION")
    status_contract = {
        "kind": "action",
        "confirmation_required": False,
        "action_id": "host-status-1",
        "session_id": "host-session",
        "request_id": "host-request",
        "action": {"type": "action", "name": "system_status", "args": {}, "risk_level": 1, "confidence": 0.99},
        "preview": "Consultar estado.",
        "device": "pc-main",
    }
    result = host.execute(status_contract, confirmed=True)
    assert result.success is True and result.execution_verified is True
    assert result.data["actions"][0]["success"] is True
    assert len(result.audit_digest) == 64 and result.host_version == "1.0.0-rc6-pc"
    assert host.audit_path.exists() and len(host.audit_path.read_text(encoding="utf-8").splitlines()) == 1
    public = host.public_capabilities()
    assert public["status"] == "online" and public["host_version"] == "1.0.0-rc6-pc"
    by_name = {item["name"]: item for item in public["capabilities"]}
    assert by_name["system.status"]["implemented"] is True
    assert by_name["system.shutdown"]["implemented"] is True and by_name["system.shutdown"]["confirmation_policy"] == "ALWAYS_CONFIRM"
    assert "executor" not in by_name["system.status"]

    bad_contract = {**status_contract, "action_id": "host-bad", "action": {"type": "action", "name": "shutdown_everything", "args": {}, "risk_level": 1}}
    try:
        host.execute(bad_contract, confirmed=True)
    except ActionCoordinatorError:
        pass
    else:
        raise AssertionError("Action Host aceptó una acción fuera del allowlist")

print("ACTION HOST TEST OK: verified result, chained audit, public capability metadata and allowlist rejection.")
