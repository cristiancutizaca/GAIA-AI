from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_rc2_safe_mode_") as tmp:
    tmp_path = Path(tmp)
    os.environ.update({
        "LUMEN_DATA_DIR": str(tmp_path),
        "GAIA_MEMORY_DB": str(tmp_path / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-rc2-safe-mode-governor-secret",
        "GAIA_SAFE_MODE": "true",
        "GAIA_AUTOMATION_MODE": "FULL_CONFIGURED",
        "LUMEN_BACKUP_ENABLED": "true",
    })
    from authz import CAP_CHAT, Principal
    from automation_engine import AutomationEngine
    from automation_runtime import runtime
    from event_engine import Event
    from routes import api

    assert runtime.safe_mode is True
    assert runtime.automation.is_safe_mode() is True
    assert runtime.automation.is_active() is False
    assert runtime.status()["safe_mode"] is True
    assert runtime.status()["automation"]["safe_mode"] is True
    assert runtime.status()["watchers"]["active"] == []
    assert api._resource_governor() is runtime.governor
    assert api._actions_enabled() is False
    public_status = asyncio.run(api.status())
    assert public_status["features"]["safe_mode"] is True and public_status["features"]["actions_enabled"] is False
    diagnostics = asyncio.run(api.diagnostics())
    assert diagnostics["core"]["safe_mode"] is True and diagnostics["action_engine"]["safe_mode_blocked"] is True

    executed = []
    engine = AutomationEngine(mode="FULL_CONFIGURED", routine_executor=lambda *_args: executed.append(True), safe_mode=True)
    asyncio.run(engine.handle_event(Event.create("core.ready", source="test", device="device-a")))
    assert executed == []
    assert engine.status()["safe_mode"] is True
    assert engine.status()["active"] is False

    principal = Principal(type="device", device_id="device-a", token_id="token-a", capabilities=frozenset({CAP_CHAT}))

    blocked_memory = api.AdvancedMemoryPayload(memory_key="blocked", kind="semantic", category="test", content="must not mutate")
    try:
        asyncio.run(api.advanced_memory_add(blocked_memory, principal))
    except api.HTTPException as exc:
        assert exc.status_code == 409 and "SAFE_MODE_BLOCKED" in str(exc.detail)
    else:
        raise AssertionError("advanced memory mutation must be blocked in Safe Mode")

    try:
        asyncio.run(api.action_host_heartbeat(api.ActionHostHeartbeatPayload(device_id="device-a"), principal))
    except api.HTTPException as exc:
        assert exc.status_code == 409 and "SAFE_MODE_BLOCKED" in str(exc.detail)
    else:
        raise AssertionError("remote heartbeat must be blocked in Safe Mode")

    try:
        asyncio.run(api._set_action_approval(api.ActionApprovalPayload(action_id="none", session_id="safe-session", decision="APPROVE"), principal, True))
    except api.HTTPException as exc:
        assert exc.status_code == 409 and "SAFE_MODE_BLOCKED" in str(exc.detail)
    else:
        raise AssertionError("action approval must be blocked in Safe Mode")

    try:
        asyncio.run(api.automation_mode(api.AutomationModePayload(mode="FULL_CONFIGURED")))
    except api.HTTPException as exc:
        assert exc.status_code == 409 and "SAFE_MODE_BLOCKED" in str(exc.detail)
    else:
        raise AssertionError("automation enablement must be blocked in Safe Mode")

    request = api.ChatRequest(message="abre la calculadora", session_id="safe-session", device="device-a")
    response = asyncio.run(api._chat_service(request, principal))
    assert response.request_state == "ACTION_REQUEST"
    assert "SAFE_MODE_BLOCKED" in response.response
    assert not any(row["key"].startswith("pending_action:") for row in api.memory.list_states("pending_action:"))

print("RC2 SAFE MODE/GOVERNOR TEST OK: chat remains available, action boundaries are blocked, automation is paused, and diagnostics use the shared governor.")
