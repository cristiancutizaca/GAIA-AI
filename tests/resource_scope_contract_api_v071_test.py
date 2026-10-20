from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="gaia_scope_contract_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory" / "lumen_memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "scope-contract-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    core = Path(__file__).resolve().parents[1] / "lumen-core"
    sys.path.insert(0, str(core))
    from action_intent import ActionIntent, ActionPlan
    from authz import Principal
    from routes.api import _action_contract, _permission_entries

    principal = Principal(type="master", device_id="pc-main", permission_level=2)
    single = ActionIntent("open_spotify", {"app": "spotify"}, 1, confirmation_required=True)
    entries = _permission_entries(single, principal, "pc-main")
    assert len(entries) == 1
    assert entries[0]["resource_scope"] == "spotify"
    assert entries[0]["human_scope_description"] == "aplicación spotify"
    assert entries[0]["persistent_grant_allowed"] is True
    assert entries[0]["allow_always"] is True
    contract = _action_contract(single, "scope-action", "scope-session", permission_entries=entries)
    assert contract["resource_scope_version"] == "1"
    assert contract["permission_entries"] == entries
    assert contract["action"]["resource_scope"] == "spotify"
    assert contract["action"]["persistent_grant_allowed"] is True

    uia = ActionIntent("uia_invoke_control", {
        "trusted_app_id": "safe:vscode",
        "expected_target": {"window_id": 1, "pid": 2, "executable": "Code.exe"},
        "control_id": "uia:continue",
    }, 2, confirmation_required=True)
    uia_entries = _permission_entries(uia, principal, "pc-main")
    assert uia_entries[0]["persistent_grant_allowed"] is False
    uia_contract = _action_contract(uia, "uia-action", "scope-session", permission_entries=uia_entries)
    assert uia_contract["confirmation_options"]["allow_always"] is False

    plan = ActionPlan((single, uia), confirmation_required=True)
    plan_entries = _permission_entries(plan, principal, "pc-main")
    plan_contract = _action_contract(plan, "scope-plan", "scope-session", permission_entries=plan_entries)
    assert len(plan_contract["permission_entries"]) == 2
    assert plan_contract["confirmation_options"]["allow_always"] is False
    assert plan_contract["plan"]["actions"][1]["resource_scope"].startswith("uia:")

print("RESOURCE SCOPE CONTRACT API V071 TEST OK: Core emits authoritative scopes and persistent-grant policy for action/plan payloads.")
