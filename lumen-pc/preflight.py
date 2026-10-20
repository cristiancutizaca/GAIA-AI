"""Read-only preflight for local and remote action contracts.

Preflight never invokes an action handler. It validates the same code-owned
registry used by ActionEngine, resolves optional target identity, and reports
whether execution may proceed to the normal permission/confirmation boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import platform
from typing import Any, Iterable, TYPE_CHECKING

from capabilities import ACTION_TO_CAPABILITY, CapabilityValidationError

if TYPE_CHECKING:
    from action_engine import ActionEngine


@dataclass(frozen=True)
class PreflightResult:
    status: str
    action: str
    capability: str
    message: str
    request_validated: bool
    capability_available: bool
    execution_attempted: bool = False
    side_effect_performed: bool = False
    effect_verified: bool = False
    observation_completed: bool = False
    execution_verified: bool = False
    requires_confirmation: bool = False
    risk_level: int = 0
    target: dict[str, Any] | None = None
    dynamic_risk: int | None = None
    risk_reason: str = ""
    data: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["data"] = dict(self.data or {})
        return payload


def _platform_name() -> str:
    value = platform.system().casefold()
    return {"windows": "windows", "linux": "linux", "darwin": "darwin"}.get(value, value)


def _action_items(contract: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    plan = contract.get("plan") if isinstance(contract, dict) else None
    if isinstance(plan, dict) and isinstance(plan.get("actions"), list):
        items: list[tuple[str, dict[str, Any]]] = []
        for row in plan["actions"]:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or row.get("action") or "").strip()
            items.append((name, dict(row.get("args") or {})))
        return items
    action = contract.get("action") if isinstance(contract, dict) and isinstance(contract.get("action"), dict) else contract
    if not isinstance(action, dict):
        return []
    return [(str(action.get("name") or action.get("action") or "").strip(), dict(action.get("args") or {}))]


def _redact_params(params: dict[str, Any]) -> dict[str, Any]:
    clean = dict(params)
    for key in ("value", "password", "token", "secret", "credential"):
        if key in clean:
            clean[key] = "[REDACTED]"
    return clean


def _supported(definition: Any) -> bool:
    supported = {str(item).casefold() for item in (definition.supported_os or ())}
    return not supported or _platform_name() in supported


def _preflight_one(engine: "ActionEngine", action_name: str, args: dict[str, Any], *, device: str, resource_scope: str) -> PreflightResult:
    if not action_name or action_name not in engine.SAFE_ACTIONS:
        return PreflightResult("DENIED", action_name or "unknown", "", "Acción no permitida por el allowlist local.", False, True, data={"reason": "unknown_action"})
    mapping = ACTION_TO_CAPABILITY.get(action_name)
    if not mapping:
        return PreflightResult("DENIED", action_name, "", "La acción no tiene una capability registrada.", False, True, data={"reason": "unmapped_action"})
    capability_name, defaults = mapping
    private = {key: value for key, value in args.items() if str(key).startswith("_")}
    public_args = {key: value for key, value in args.items() if not str(key).startswith("_")}
    params = dict(defaults)
    params.update(public_args)
    # Contextual actions may omit a window id; resolve only from the current
    # structured desktop snapshot, never from free-form text or coordinates.
    if action_name in {"uia_inspect_window", "uia_list_controls", "uia_get_focused_control", "uia_focus_control", "uia_invoke_control", "uia_set_value", "screen_capture_window"} and not str(params.get("window_id") or "").strip():
        try:
            params["window_id"] = engine._context_window_id(params)
        except Exception as exc:
            return PreflightResult("UNAVAILABLE", action_name, capability_name, str(exc), True, False, data={"reason": "no_structured_window"})
    for key in ("expected_target",):
        if key in params and params[key] == {} and key not in args:
            params.pop(key, None)
    try:
        request = engine.capability_registry.request(capability_name, params, device=device, resource_scope=resource_scope)
    except CapabilityValidationError as exc:
        return PreflightResult("DENIED", action_name, "", str(exc), False, True, data={"reason": "capability_validation"})
    definition = engine.capability_registry.get(request.capability)
    if definition is None:
        return PreflightResult("DENIED", action_name, request.capability, "La capability no está registrada.", False, True, data={"reason": "unregistered"})
    if not definition.implemented:
        return PreflightResult("UNAVAILABLE", action_name, request.capability, "La capability está registrada pero no implementada.", True, False, data={"reason": "not_implemented"})
    if not _supported(definition):
        return PreflightResult("UNAVAILABLE", action_name, request.capability, f"La capability no está disponible en {_platform_name()}.", True, False, risk_level=definition.risk_level, data={"supported_os": list(definition.supported_os)})

    target: dict[str, Any] | None = None
    dynamic_risk: int | None = None
    risk_reason = ""
    try:
        if action_name in {"uia_focus_control", "uia_invoke_control", "uia_set_value"}:
            window_id, identity = engine._uia_interaction_target(args)
            operation = {"uia_focus_control": "focus", "uia_invoke_control": "invoke", "uia_set_value": "set_value"}[action_name]
            from uia import resolve_control_risk
            risk = resolve_control_risk(window_id, str(args.get("control_id") or ""), operation)
            target = dict(identity)
            dynamic_risk = int(risk.get("risk_level", definition.risk_level))
            risk_reason = str(risk.get("reason") or "")
            declared = int(private.get("_declared_risk", definition.risk_level))
            if bool(risk.get("sensitive")) or dynamic_risk > declared:
                return PreflightResult("DENIED", action_name, request.capability, "El preflight UIA rechazó el control por riesgo dinámico; no hubo efecto.", True, True, risk_level=definition.risk_level, target=target, dynamic_risk=dynamic_risk, risk_reason=risk_reason, requires_confirmation=True, data={"declared_risk": declared, "effect_performed": False})
        elif action_name in {"uia_inspect_window", "uia_list_controls", "uia_get_focused_control", "screen_capture_window"}:
            expected = args.get("expected_target")
            if expected:
                target = engine._optional_expected_window_target(args)
        elif action_name.startswith("windows_") and args.get("expected_target"):
            engine._verify_expected_window_target(args)
            target = dict(args["expected_target"])
    except Exception as exc:
        message = str(exc)
        lower = message.casefold()
        if _platform_name() != "windows" or "no está disponible" in lower or "falta pywinauto" in lower:
            return PreflightResult("UNAVAILABLE", action_name, request.capability, message, True, False, risk_level=definition.risk_level, target=target, data={"reason": "platform_or_backend"})
        if "stale" in lower or "cambió" in lower or "target" in lower:
            return PreflightResult("DENIED", action_name, request.capability, message, True, True, risk_level=definition.risk_level, target=target, data={"reason": "stale_or_target"})
        return PreflightResult("DENIED", action_name, request.capability, message, True, True, risk_level=definition.risk_level, target=target, data={"reason": "preflight_error"})

    required_confirmation = bool(definition.risk_level >= 2 or (dynamic_risk is not None and dynamic_risk >= 3))
    return PreflightResult(
        "READY",
        action_name,
        request.capability,
        "Preflight completado; no se ejecutó ningún efecto.",
        True,
        True,
        requires_confirmation=required_confirmation,
        risk_level=max(definition.risk_level, dynamic_risk or 0),
        target=target,
        dynamic_risk=dynamic_risk,
        risk_reason=risk_reason,
        data={"parameters": _redact_params(dict(request.params)), "confirmation_policy": definition.confirmation_policy, "resource_scope": request.resource_scope},
    )


def preflight_contract(engine: "ActionEngine", contract: dict[str, Any], *, device: str = "pc-main", resource_scope: str = "") -> dict[str, Any]:
    """Preflight a single action or bounded plan, never calling ``execute``."""
    items = _action_items(contract if isinstance(contract, dict) else {})
    if not items:
        return PreflightResult("DENIED", "unknown", "", "El contrato no contiene una acción estructurada.", False, True, data={"reason": "empty_contract"}).as_dict()
    results = [_preflight_one(engine, name, args, device=device, resource_scope=resource_scope) for name, args in items]
    statuses = {row.status for row in results}
    if "DENIED" in statuses:
        overall = "DENIED"
    elif "UNAVAILABLE" in statuses:
        overall = "UNAVAILABLE" if len(statuses) == 1 else "PARTIAL"
    else:
        overall = "READY"
    return {
        "status": overall,
        "preflight_only": True,
        "request_validated": all(row.request_validated for row in results),
        "capability_available": all(row.capability_available for row in results),
        "execution_attempted": False,
        "side_effect_performed": False,
        "effect_verified": False,
        "observation_completed": False,
        "execution_verified": False,
        "requires_confirmation": any(row.requires_confirmation for row in results),
        "steps": [row.as_dict() for row in results],
        "message": "Preflight listo." if overall == "READY" else "Preflight bloqueó o no pudo disponer de uno o más pasos.",
    }


__all__ = ["PreflightResult", "preflight_contract"]
