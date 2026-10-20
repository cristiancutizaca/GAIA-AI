from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from action_intent import ActionIntent, ActionPlan


@dataclass(frozen=True)
class WorkspaceProfile:
    name: str
    description: str


PROGRAMMING_PROFILE = WorkspaceProfile("programming", "Espacio de programación con VS Code, display principal y Git read-only.")


def _active_window(context: dict[str, Any]) -> dict[str, Any] | None:
    value = context.get("active_window")
    return value if isinstance(value, dict) else None


def _primary_display_id(context: dict[str, Any]) -> str:
    direct = context.get("primary_display_id")
    if direct:
        return str(direct)
    displays = context.get("displays")
    if isinstance(displays, list):
        for display in displays:
            if isinstance(display, dict) and bool(display.get("primary")) and display.get("display_id"):
                return str(display["display_id"])
    display = context.get("display")
    if isinstance(display, dict) and bool(display.get("primary")) and display.get("display_id"):
        return str(display["display_id"])
    return ""


def _window_target(window: dict[str, Any]) -> dict[str, Any]:
    return {key: window[key] for key in ("window_id", "pid", "process", "process_executable", "title") if window.get(key) not in (None, "")}


def build_programming_plan(context: dict[str, Any] | None = None, *, project: str = "default") -> ActionPlan:
    """Build a fixed, bounded plan; it never accepts commands or plugin names."""
    context = context if isinstance(context, dict) else {}
    window = _active_window(context)
    actions: list[ActionIntent] = [
        ActionIntent("display_list", {}, 0, source="workspace:programming"),
        ActionIntent("vscode_focus", {}, 1, source="workspace:programming"),
        ActionIntent("vscode_open_project", {"project": str(project or "default")}, 1, source="workspace:programming"),
    ]
    display_id = _primary_display_id(context)
    window_id = str((window or {}).get("window_id") or "").strip()
    process = str((window or {}).get("process") or (window or {}).get("process_executable") or "").casefold()
    if window_id.isdigit() and display_id and ("code" in process or "vscode" in process or "visual studio" in process):
        actions.append(ActionIntent("windows_move_to_display", {"window_id": window_id, "display_id": display_id, "expected_target": _window_target(window or {})}, 1, source="workspace:programming"))
    actions.append(ActionIntent("git_status", {"path": ""}, 2, source="workspace:programming"))
    return ActionPlan(tuple(actions), False, 0.98, "workspace:programming")


def resolve_window_referent(text: str, context: dict[str, Any] | None = None) -> ActionIntent | None:
    """Resolve a small Spanish referent set once, when the request is created."""
    context = context if isinstance(context, dict) else {}
    window = _active_window(context)
    window_id = str((window or {}).get("window_id") or "").strip()
    if not window_id.isdigit() or not window:
        return None
    target = _window_target(window)
    normalized = " ".join(str(text or "").casefold().split())
    if re.search(r"\bci[eé]rr(?:alo|la)\b", normalized):
        return ActionIntent("windows_close", {"window_id": window_id, "expected_target": target}, 2, source="deterministic:active_window")
    if re.search(r"\bminim[ií]z(?:alo|la)\b", normalized):
        return ActionIntent("windows_minimize", {"window_id": window_id, "expected_target": target}, 1, source="deterministic:active_window")
    if re.search(r"\bm[uú][eé]v(?:elo|ela)\b", normalized) and re.search(r"(?:pantalla|monitor)\s+principal", normalized):
        display_id = _primary_display_id(context)
        if display_id:
            return ActionIntent("windows_move_to_display", {"window_id": window_id, "display_id": display_id, "expected_target": target}, 1, source="deterministic:active_window")
    return None


def detect_workspace_profile(text: str, context: dict[str, Any] | None = None) -> ActionPlan | None:
    normalized = " ".join(str(text or "").casefold().split())
    programming = any(token in normalized for token in ("programar", "programación", "programacion", "código", "codigo"))
    workspace = any(token in normalized for token in ("organiza mi espacio", "organizar mi espacio", "prepara mi entorno", "prepara el entorno", "configura mi espacio", "monta mi entorno"))
    if programming and workspace and not any(token in normalized for token in ("apaga", "shutdown", "formatea", "borra", "elimina", "sudo", "powershell", "cmd")):
        return build_programming_plan(context)
    return None
