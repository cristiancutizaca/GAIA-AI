"""Coordinación común de acciones y planes en clientes PC.

Este módulo no es un segundo Action Engine. Solo orquesta un ActionEngine
existente y nunca obtiene autoridad adicional del texto de la interfaz.
"""
from __future__ import annotations

import threading
from typing import Any, Callable

from action_engine import ActionEngine
from action_response import ActionResponse, parse_action_response, response_for_display


class ActionCoordinatorError(RuntimeError):
    pass


class ActionCoordinator:
    MAX_STEPS = 3
    MAX_RISK = 2

    def __init__(self, engine: ActionEngine, cancel_event: threading.Event | None = None, policy: str = "CONFIRM_EXECUTION") -> None:
        self.engine = engine
        self.cancel_event = cancel_event or threading.Event()
        self.policy = (policy or "CONFIRM_EXECUTION").upper()

    def _validate_step(self, step: dict[str, Any]) -> tuple[bool, str]:
        name = str(step.get("name", "")).strip()
        args = step.get("args")
        if name not in self.engine.SAFE_ACTIONS:
            return False, "Acción no permitida por el catálogo local."
        if not isinstance(args, dict):
            return False, "Los argumentos de la acción no son un objeto válido."
        try:
            risk = int(step.get("risk_level", self.engine.SAFE_ACTIONS[name][0]))
        except (TypeError, ValueError):
            return False, "Nivel de riesgo inválido."
        allowed_risk = int(self.engine.SAFE_ACTIONS[name][0])
        if risk < 1 or risk > self.MAX_RISK or risk > allowed_risk:
            return False, "Nivel de riesgo fuera de los límites locales."
        return True, ""

    def _ask(self, parsed: ActionResponse, confirm: Callable[[str, ActionResponse], bool] | None) -> bool:
        if not parsed.confirmation_required:
            return True
        if self.policy == "BLOCKED":
            return False
        if confirm is None:
            return False
        return bool(confirm(response_for_display(parsed), parsed))

    def execute(self, response: dict[str, Any], *, confirmed: bool = False, confirm: Callable[[str, ActionResponse], bool] | None = None) -> dict[str, Any]:
        parsed = parse_action_response(response)
        if not parsed:
            raise ActionCoordinatorError("Respuesta de acción inválida o incompleta.")
        steps = parsed.steps
        if not 1 <= len(steps) <= self.MAX_STEPS:
            raise ActionCoordinatorError("El plan debe contener entre 1 y 3 acciones.")
        for step in steps:
            valid, reason = self._validate_step(step)
            if not valid:
                raise ActionCoordinatorError(reason)
        if self.policy == "BLOCKED":
            return {"success": False, "action": parsed.kind, "message": "Acciones deshabilitadas por configuración.", "data": {"actions": [], "completed": 0, "total": len(steps)}, "blocked": True, "cancelled": False, "confirmed": False}
        if not confirmed and not self._ask(parsed, confirm):
            return {"success": False, "action": parsed.kind, "message": "Ejecución cancelada antes de comenzar.", "data": {"actions": [], "completed": 0, "total": len(steps)}, "blocked": False, "cancelled": True, "confirmed": False, "plan_id": parsed.action_id if parsed.is_plan else None}

        plan_id = parsed.action_id if parsed.is_plan else None
        results: list[dict[str, Any]] = []
        cancelled = False
        for index, step in enumerate(steps, 1):
            if self.cancel_event.is_set():
                cancelled = True
                break
            result = self.engine.execute(step)
            item = result.as_dict()
            item.update({"step": index, "plan_id": plan_id} if plan_id else {"step": 1})
            results.append(item)
            if not result.success:
                break
        success = len(results) == len(steps) and all(bool(item.get("success")) for item in results)
        if success:
            message = "Plan completado." if parsed.is_plan else (results[0].get("message") or "Acción completada.")
        elif cancelled:
            message = "Plan cancelado antes del siguiente paso."
        elif parsed.is_plan:
            message = "Plan detenido al primer fallo."
        else:
            message = results[0].get("message") if results else "Acción no ejecutada."
        duration_ms = sum(float((item.get("data") or {}).get("duration_ms", 0.0)) for item in results)
        data = {"actions": results, "completed": len(results), "total": len(steps), "plan_id": plan_id, "duration_ms": duration_ms}
        return {"success": success, "action": parsed.kind if parsed.is_plan else (steps[0].get("name") or "unknown"), "message": message, "data": data, "blocked": False, "cancelled": cancelled, "confirmed": True, "plan_id": plan_id}
