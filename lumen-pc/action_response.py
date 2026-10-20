"""Contrato común para respuestas de acciones de GAIA v0.6.0.

El Core es la autoridad que produce el contrato. Este módulo solo normaliza
la respuesta para los clientes; no concede permisos ni ejecuta acciones.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActionResponse:
    """Respuesta canónica de acción o plan, sin duplicar action/plan."""

    kind: str
    confirmation_required: bool
    action_id: str
    session_id: str
    request_id: str
    action: dict[str, Any] | None
    plan: dict[str, Any] | None
    preview: str | list[str]
    raw: dict[str, Any]

    @property
    def is_action(self) -> bool:
        return self.kind == "action" and self.action is not None

    @property
    def is_plan(self) -> bool:
        return self.kind == "plan" and self.plan is not None

    @property
    def steps(self) -> list[dict[str, Any]]:
        if self.is_action:
            return [self.action or {}]
        if self.is_plan:
            actions = self.plan.get("actions", []) if self.plan else []
            return [item for item in actions if isinstance(item, dict)]
        return []

    def as_dict(self) -> dict[str, Any]:
        result = {
            "kind": self.kind,
            "confirmation_required": self.confirmation_required,
            "action_id": self.action_id,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "preview": self.preview,
        }
        if self.is_action:
            result["action"] = self.action
        elif self.is_plan:
            result["plan"] = self.plan
        return result


def _preview_for_plan(raw: dict[str, Any], actions: list[dict[str, Any]]) -> list[str]:
    preview = raw.get("preview")
    if isinstance(preview, list):
        return [str(item)[:500] for item in preview[:3]]
    if isinstance(preview, str) and preview.strip():
        lines = [line.strip() for line in preview.splitlines() if line.strip()]
        numbered = [line.split(". ", 1)[1] if ". " in line and line.split(". ", 1)[0].isdigit() else line for line in lines]
        if numbered:
            return numbered[:3]
    return [str(item.get("preview") or item.get("name") or "Acción validada.")[:500] for item in actions[:3]]


def parse_action_response(data: dict[str, Any]) -> ActionResponse | None:
    """Normaliza el contrato nuevo y tolera solo la forma legacy conocida."""
    if not isinstance(data, dict):
        return None
    raw_action = data.get("action") if isinstance(data.get("action"), dict) else None
    raw_plan = data.get("plan") if isinstance(data.get("plan"), dict) else None
    if raw_plan is None and raw_action and (raw_action.get("type") == "plan" or isinstance(raw_action.get("actions"), list)):
        raw_plan = raw_action
        raw_action = None
    if data.get("kind") not in {"action", "plan"} and raw_action is None and raw_plan is None:
        return None

    confirmation = bool(data.get("confirmation_required"))
    if raw_action is not None:
        # Fallback only for v0.5.1 responses; the canonical field is top-level.
        confirmation = confirmation or bool(raw_action.get("confirmation_required"))
        action = dict(raw_action)
        action.setdefault("type", "action")
        return ActionResponse("action", confirmation, str(data.get("action_id", "")), str(data.get("session_id", "")), str(data.get("request_id", "")), action, None, str(data.get("preview") or data.get("response") or "Acción validada."), data)

    if raw_plan is None:
        return None
    confirmation = confirmation or bool(raw_plan.get("confirmation_required"))
    actions = raw_plan.get("actions") if isinstance(raw_plan.get("actions"), list) else []
    clean_actions = [dict(item) for item in actions if isinstance(item, dict)][:3]
    plan_id = str(raw_plan.get("plan_id") or data.get("action_id", ""))
    plan = dict(raw_plan)
    plan["plan_id"] = plan_id
    plan["actions"] = clean_actions
    plan.setdefault("type", "plan")
    return ActionResponse("plan", confirmation, str(data.get("action_id") or plan_id), str(data.get("session_id", "")), str(data.get("request_id", "")), None, plan, _preview_for_plan(data, clean_actions), data)


def response_for_display(parsed: ActionResponse) -> str:
    if parsed.is_action:
        return str(parsed.preview)
    if parsed.is_plan:
        lines = parsed.preview if isinstance(parsed.preview, list) else [str(parsed.preview)]
        return "GAIA quiere ejecutar:\n" + "\n".join(f"{index}. {line}" for index, line in enumerate(lines, 1))
    return ""
