"""Evaluador seguro de reglas y rutinas para GAIA v0.9.0."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any, Awaitable, Callable

import automation_store
from config import AUTOMATION_MAX_DAILY_RUNS, AUTOMATION_MAX_RULES, AUTOMATION_MODE, AUTOMATION_QUIET_END, AUTOMATION_QUIET_HOURS_ENABLED, AUTOMATION_QUIET_START
from event_engine import Event

logger = logging.getLogger("lumen.automation")

ALLOWED_OPERATORS = frozenset({"eq", "neq", "lt", "lte", "gt", "gte", "exists", "contains_safe"})
ALLOWED_MODES = frozenset({"OFF", "NOTIFY_ONLY", "ROUTINES", "FULL_CONFIGURED"})


def _get_value(event: Event, path: str) -> Any:
    path = str(path).strip()
    if path == "event_type":
        return event.event_type
    if path == "source":
        return event.source
    if path == "severity":
        return event.severity
    if path == "host":
        return event.host
    if path == "device":
        return event.device
    if path == "source_id":
        return event.source_id
    if path.startswith("payload."):
        value: Any = event.payload
        for key in path[8:].split(".")[:4]:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value
    return None


def _compare(operator: str, actual: Any, expected: Any) -> bool:
    if operator == "exists":
        return actual is not None
    if operator == "contains_safe":
        return isinstance(actual, (str, list, tuple, set)) and str(expected).casefold() in str(actual).casefold()
    try:
        if operator == "eq": return actual == expected
        if operator == "neq": return actual != expected
        if operator == "lt": return actual < expected
        if operator == "lte": return actual <= expected
        if operator == "gt": return actual > expected
        if operator == "gte": return actual >= expected
    except (TypeError, ValueError):
        return False
    return False


def _in_quiet_hours(now: datetime | None = None) -> bool:
    if not AUTOMATION_QUIET_HOURS_ENABLED or AUTOMATION_QUIET_START == AUTOMATION_QUIET_END:
        return False
    hour = (now or datetime.now()).hour
    if AUTOMATION_QUIET_START > AUTOMATION_QUIET_END:
        return hour >= AUTOMATION_QUIET_START or hour < AUTOMATION_QUIET_END
    return AUTOMATION_QUIET_START <= hour < AUTOMATION_QUIET_END


class AutomationEngine:
    def __init__(self, *, mode: str = AUTOMATION_MODE, routine_executor: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]] | dict[str, Any]] | None = None, safe_mode: bool = False) -> None:
        self.mode = mode if mode in ALLOWED_MODES else "OFF"
        self.routine_executor = routine_executor
        self._safe_mode = bool(safe_mode)
        self._last_run: dict[str, float] = {}
        self.metrics: dict[str, int] = {"rules_checked": 0, "rules_triggered": 0, "runs_started": 0, "runs_completed": 0, "runs_blocked": 0, "background_llm_calls": 0}
        self._paused = False

    def set_mode(self, mode: str) -> str:
        normalized = str(mode).strip().upper()
        if normalized not in ALLOWED_MODES:
            raise ValueError("Modo de automatización inválido")
        self.mode = normalized
        return self.mode

    def pause(self, paused: bool = True) -> None:
        self._paused = bool(paused)

    def set_safe_mode(self, enabled: bool = True) -> None:
        self._safe_mode = bool(enabled)
        if self._safe_mode:
            self._paused = True

    def is_safe_mode(self) -> bool:
        return self._safe_mode

    def is_active(self) -> bool:
        return self.mode != "OFF" and not self._paused and not self._safe_mode

    @staticmethod
    def _validate_steps(steps: Any) -> list[str]:
        from automation_action_bridge import FORBIDDEN_UNATTENDED, SAFE_ROUTINE_ACTIONS, _legacy_name
        errors: list[str] = []
        if not isinstance(steps, list) or not 1 <= len(steps) <= 5:
            return ["una rutina debe contener entre uno y cinco steps"]
        for index, step in enumerate(steps, 1):
            if not isinstance(step, dict):
                errors.append(f"step {index} inválido")
                continue
            name = str(step.get("name") or step.get("action") or step.get("capability") or "").strip()
            if name in {"permission_grant", "grant_permission", "set_policy", "change_mode", "kill_switch"} or any(key in step for key in ("grant", "permission_grant", "self_grant")):
                errors.append(f"step {index} intenta modificar autoridad o permisos")
                continue
            normalized = _legacy_name(step)
            if normalized not in SAFE_ROUTINE_ACTIONS and name not in SAFE_ROUTINE_ACTIONS:
                errors.append(f"step {index}: capability no habilitada para unattended")
            if name in FORBIDDEN_UNATTENDED or normalized in FORBIDDEN_UNATTENDED:
                errors.append(f"step {index}: acción prohibida unattended")
            if not isinstance(step.get("args", {}), dict):
                errors.append(f"step {index}: args debe ser objeto")
            try:
                risk = int(step.get("risk_level", 0))
            except (TypeError, ValueError):
                errors.append(f"step {index}: risk_level inválido")
                continue
            if risk < 0 or risk > 2:
                errors.append(f"step {index}: riesgo superior al máximo unattended")
        return errors

    @staticmethod
    def validate_rule(rule: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        trigger = rule.get("trigger") if isinstance(rule.get("trigger"), dict) else {}
        event_type = str(trigger.get("event_type") or "")
        if event_type and event_type not in __import__("event_engine").ALLOWED_EVENT_TYPES:
            errors.append("trigger.event_type no permitido")
        conditions = rule.get("conditions") if isinstance(rule.get("conditions"), list) else []
        if len(conditions) > 12:
            errors.append("demasiadas condiciones")
        for condition in conditions:
            if not isinstance(condition, dict):
                errors.append("condición inválida")
                continue
            operator = str(condition.get("op") or "")
            path = str(condition.get("field") or "")
            if operator not in ALLOWED_OPERATORS:
                errors.append("operador no permitido")
            if path not in {"event_type", "source", "severity", "host", "device", "source_id"} and not path.startswith("payload."):
                errors.append("campo de condición no permitido")
        if "command" in rule or "shell" in rule or "expression" in rule:
            errors.append("una regla no admite comandos ni expresiones")
        steps = rule.get("steps") if isinstance(rule.get("steps"), list) else []
        if steps:
            errors.extend(AutomationEngine._validate_steps(steps))
        elif not rule.get("routine_id"):
            errors.append("la regla no referencia una rutina ni contiene steps")
        return errors

    @staticmethod
    def matches(rule: dict[str, Any], event: Event) -> bool:
        trigger = rule.get("trigger") if isinstance(rule.get("trigger"), dict) else {}
        expected_type = str(trigger.get("event_type") or "")
        if expected_type and expected_type != event.event_type:
            return False
        conditions = rule.get("conditions") if isinstance(rule.get("conditions"), list) else []
        return all(_compare(str(condition.get("op") or ""), _get_value(event, str(condition.get("field") or "")), condition.get("value")) for condition in conditions if isinstance(condition, dict))

    def dry_run(self, rule: dict[str, Any], event: Event | None = None, routine: dict[str, Any] | None = None) -> dict[str, Any]:
        errors = self.validate_rule(rule)
        if errors:
            return {"status": "DENIED", "errors": errors, "would_execute": False, "steps": []}
        if event and not self.matches(rule, event):
            return {"status": "SKIPPED", "errors": [], "would_execute": False, "steps": []}
        selected = routine or (automation_store.get_routine(str(rule.get("routine_id"))) if rule.get("routine_id") else None)
        steps = selected.get("steps", []) if selected else rule.get("steps", [])
        step_errors = self._validate_steps(steps)
        if step_errors:
            return {"status": "DENIED", "errors": step_errors, "would_execute": False, "steps": []}
        risk = int(selected.get("max_risk", 0)) if selected else max((int(step.get("risk_level", 0)) for step in steps if isinstance(step, dict)), default=0)
        high_risk = risk >= 3
        return {"status": "READY" if not high_risk else "NEEDS_CONFIRMATION", "errors": [], "would_execute": self.is_active() and not high_risk, "high_risk": high_risk, "max_risk": risk, "steps": steps[:5]}

    async def handle_event(self, event: Event) -> None:
        if not self.is_active():
            return
        if event.event_type == "schedule.due" and str(event.payload.get("routine_id") or ""):
            synthetic = {"rule_id": f"schedule:{event.payload.get('schedule_id', '')}", "name": "Schedule", "owner_device": event.device, "enabled": True, "trigger": {"event_type": "schedule.due"}, "conditions": [], "routine_id": str(event.payload.get("routine_id") or ""), "cooldown_seconds": 60}
            await self._handle_match(synthetic, event)
        rules = automation_store.list_rules_for_event(event.event_type, include_disabled=False)[:AUTOMATION_MAX_RULES]
        for rule in rules:
            self.metrics["rules_checked"] += 1
            if not self.matches(rule, event):
                continue
            self.metrics["rules_triggered"] += 1
            await self._handle_match(rule, event)

    async def _handle_match(self, rule: dict[str, Any], event: Event) -> None:
        rule_id = str(rule.get("rule_id") or "")
        now = time.monotonic()
        cooldown = min(86400, max(5, int(rule.get("cooldown_seconds", 300))))
        run_id = str(event.payload.get("run_id") or "") if isinstance(event.payload, dict) else ""
        last_run = self._last_run.get(rule_id)
        if last_run is not None and now - last_run < cooldown:
            if run_id:
                automation_store.finish_run(run_id, "skipped", {"reason": "cooldown"})
            return
        if _in_quiet_hours():
            policy = str(rule.get("quiet_hour_policy") or "skip")
            if policy == "skip":
                self.metrics["runs_blocked"] += 1
                if run_id:
                    automation_store.finish_run(run_id, "skipped", {"reason": "quiet_hours"})
                return
            if policy == "notify_only":
                self._notify(rule, event, "quiet_hours")
                if run_id:
                    automation_store.finish_run(run_id, "completed", {"reason": "quiet_hours_notify_only"})
                return
        if int(rule.get("run_limit", 0) or 0) and int(rule.get("run_count", 0) or 0) >= int(rule.get("run_limit")):
            self.metrics["runs_blocked"] += 1
            if run_id:
                automation_store.finish_run(run_id, "skipped", {"reason": "run_limit"})
            return
        if self.mode == "NOTIFY_ONLY":
            self._notify(rule, event, "notify_only")
            self._last_run[rule_id] = now
            if run_id:
                automation_store.finish_run(run_id, "completed", {"reason": "notify_only"})
            return
        routine = automation_store.get_routine(str(rule.get("routine_id") or "")) if rule.get("routine_id") else None
        preview = self.dry_run(rule, event, routine)
        if preview["status"] != "READY":
            self._notify(rule, event, str(preview["status"]).lower())
            self.metrics["runs_blocked"] += 1
            if run_id:
                automation_store.finish_run(run_id, "needs_confirmation", {"preview": preview})
            return
        if not self.routine_executor:
            self._notify(rule, event, "no_action_host")
            self.metrics["runs_blocked"] += 1
            if run_id:
                automation_store.finish_run(run_id, "needs_confirmation", {"reason": "no_action_host"})
            return
        self._last_run[rule_id] = now
        self.metrics["runs_started"] += 1
        result = self.routine_executor(routine or rule, event.as_dict(), rule)
        if asyncio.iscoroutine(result):
            result = await result
        result_status = str((result or {}).get("status") if isinstance(result, dict) else "").upper()
        if result_status == "SUCCESS":
            self.metrics["runs_completed"] += 1
            self._notify(rule, event, "completed", message=str(result.get("message") or "Rutina completada con resultado verificado."))
            if run_id:
                automation_store.finish_run(run_id, "completed", result)
        elif result_status == "PENDING":
            self._notify(rule, event, "queued", message=str(result.get("message") or "Rutina encolada para preflight y ejecución verificada."))
            if run_id:
                automation_store.finish_run(run_id, "queued", result)
        elif result_status == "SKIPPED":
            if run_id:
                automation_store.finish_run(run_id, "skipped", result if isinstance(result, dict) else {})
        else:
            self._notify(rule, event, "failed", message=str((result or {}).get("message") if isinstance(result, dict) else "La rutina no produjo un resultado verificable."))
            if run_id:
                automation_store.finish_run(run_id, "failed", result if isinstance(result, dict) else {})

    def _notify(self, rule: dict[str, Any], event: Event, reason: str, *, message: str | None = None) -> None:
        automation_store.add_notification(title=str(rule.get("name") or "Automatización"), message=message or f"Evento {event.event_type}: automatización en modo {reason}.", severity="warning" if reason in {"failed", "needs_confirmation", "no_action_host"} else "info", source=f"automation:{reason}", device_scope=str(rule.get("owner_device") or ""), sensitive=False)

    def status(self) -> dict[str, Any]:
        return {"mode": self.mode, "paused": self._paused, "safe_mode": self._safe_mode, "active": self.is_active(), **self.metrics}
