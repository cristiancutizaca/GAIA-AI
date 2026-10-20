"""Puente de rutinas bounded hacia el pending-action protocol existente."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
import uuid
from typing import Any

import memory
from action_intent import ActionIntent, ActionPlan
from config import PC_DEVICE_ID

# Only names already owned by the existing Action Engine may cross this boundary.
SAFE_ROUTINE_ACTIONS = frozenset({
    "display_list", "display_info", "system_status", "system_cpu", "system_ram", "system_disk", "system_network",
    "media_status", "get_volume", "desktop_context", "windows_list", "uia_inspect_window", "uia_list_controls", "uia_get_focused_control",
    "git_status", "git_branch", "git_log", "file_exists", "file_info", "file_list", "list_projects", "show_project",
    "open_calculator", "open_notepad", "open_vscode", "open_browser", "set_volume", "mute", "unmute", "media_play_pause", "media_next", "media_previous", "media_stop",
})
FORBIDDEN_UNATTENDED = frozenset({
    "file_delete", "file_move", "file_rename", "folder_create", "git_commit", "git_add", "process_stop", "system_restart", "system_shutdown", "system_sleep", "send", "external_send",
})


def _legacy_name(step: dict[str, Any]) -> str:
    raw = str(step.get("name") or step.get("action") or step.get("capability") or "").strip()
    aliases = {
        "display.list": "display_list", "display.info": "display_info", "system.status": "system_status", "network.status": "system_network",
        "media.status": "media_status", "audio.get_volume": "get_volume", "desktop.context": "desktop_context", "windows.list": "windows_list",
        "uia.inspect_window": "uia_inspect_window", "uia.list_controls": "uia_list_controls", "uia.get_focused_control": "uia_get_focused_control",
        "git.status": "git_status", "git.branch": "git_branch", "git.log": "git_log", "files.exists": "file_exists", "files.info": "file_info", "files.list": "file_list",
        "projects.list": "list_projects", "projects.info": "show_project", "apps.open": "open_vscode",
    }
    return aliases.get(raw, raw)


def _normalize_steps(routine: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    raw_steps = routine.get("steps") if isinstance(routine.get("steps"), list) else []
    if not 1 <= len(raw_steps) <= 5:
        return [], ["Una rutina debe contener entre 1 y 5 steps."]
    normalized: list[dict[str, Any]] = []
    errors: list[str] = []
    for step in raw_steps:
        if not isinstance(step, dict):
            errors.append("step inválido")
            continue
        name = _legacy_name(step)
        if name not in SAFE_ROUTINE_ACTIONS:
            errors.append(f"La capability {name or 'vacía'} no está habilitada para unattended.")
            continue
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        clean_args: dict[str, str] = {}
        for key, value in list(args.items())[:20]:
            if not isinstance(key, str) or key.startswith("_"):
                continue
            if isinstance(value, (str, int, float, bool)):
                clean_args[key[:80]] = str(value)[:500]
        try:
            risk = int(step.get("risk_level", 0))
        except (TypeError, ValueError):
            errors.append(f"risk_level inválido en {name}")
            continue
        if risk < 0 or risk > 2:
            errors.append(f"{name} requiere confirmación puntual por riesgo {risk}.")
            continue
        if name in FORBIDDEN_UNATTENDED:
            errors.append(f"{name} está prohibida unattended.")
            continue
        normalized.append({"name": name, "args": clean_args, "risk_level": risk, "type": "action"})
    return normalized, errors


def create_pending_action(routine: dict[str, Any], *, owner_device: str, event: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    """Create a pending action visible to RemoteActionHost; never execute locally."""
    steps, errors = _normalize_steps(routine)
    if errors:
        return {"status": "NEEDS_CONFIRMATION", "message": "; ".join(errors[:4]), "errors": errors}
    if not bool(routine.get("enabled", True)):
        return {"status": "SKIPPED", "message": "La rutina está deshabilitada."}
    intents = tuple(ActionIntent(name=item["name"], args=item["args"], risk_level=int(item["risk_level"]), confirmation_required=False, confidence=1.0, source="automation") for item in steps)
    intent: ActionIntent | ActionPlan = intents[0] if len(intents) == 1 else ActionPlan(intents, confirmation_required=False, confidence=1.0, source="automation")
    action_id = f"automation_{uuid.uuid4().hex}"
    session_id = f"automation-{uuid.uuid4().hex[:16]}"
    event_id = str(event.get("event_id") or "")[:100]
    rule_id = str(rule.get("rule_id") or "")[:100]
    event_payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    automation_run_id = str(event_payload.get("run_id") or "")[:80]
    pending = {
        "session_id": session_id,
        "device": str(owner_device or PC_DEVICE_ID)[:80],
        "requesting_device": str(owner_device or PC_DEVICE_ID)[:80],
        "target_host": PC_DEVICE_ID,
        "execution_host": PC_DEVICE_ID,
        "principal_type": "master",
        "device_id": None,
        "token_id": None,
        "request_state": "PLAN_REQUEST" if isinstance(intent, ActionPlan) else "ACTION_PENDING_CONFIRMATION",
        "intent": intent.as_dict(),
        "request_id": f"automation:{rule_id}:{event_id}"[:160],
        "approved": True,
        "auto_approved": True,
        "approval_source": "enabled_safe_automation",
        "approval_decision": "RULE_SCOPED_SAFE",
        "automation_rule_id": rule_id,
        "automation_event_id": event_id,
        "automation_run_id": automation_run_id,
        "created_at": datetime.now().isoformat(),
    }
    memory.set_state(f"pending_action:{action_id}", json.dumps(pending, ensure_ascii=False))
    return {"status": "PENDING", "action_id": action_id, "session_id": session_id, "target_host": PC_DEVICE_ID, "steps": len(steps), "message": "Rutina enviada al Action Host para preflight y ejecución verificada."}
