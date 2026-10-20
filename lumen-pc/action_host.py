"""PC Action Host: boundary local entre Core action contracts y ActionEngine.

El host no interpreta texto libre ni recibe executors desde el Core. Consume el
contrato estructurado ya validado, ejecuta mediante ActionCoordinator y emite
un resultado verificable que puede ser la única fuente factual post-action.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from action_coordinator import ActionCoordinator, ActionCoordinatorError
from action_engine import ActionEngine
from action_response import parse_action_response
from capabilities import default_capability_registry
from preflight import preflight_contract
try:
    from gaia_version import PRODUCT_VERSION
except ImportError:
    PRODUCT_VERSION = "2.0.0"

HOST_VERSION = PRODUCT_VERSION


@dataclass(frozen=True)
class VerifiedActionResult:
    action_id: str
    session_id: str
    device: str
    success: bool
    action: str
    message: str
    data: dict[str, Any]
    execution_verified: bool
    host_version: str = HOST_VERSION
    completed_at: str = ""
    audit_digest: str = ""
    blocked: bool = False
    cancelled: bool = False
    confirmed: bool = True
    plan_id: str | None = None
    status: str = "FAILED"
    request_validated: bool = True
    execution_attempted: bool = True
    capability_available: bool | None = None
    side_effect_performed: bool = False
    effect_verified: bool = False
    observation_completed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "session_id": self.session_id,
            "device": self.device,
            "success": bool(self.success),
            "action": self.action,
            "message": self.message,
            "data": self.data,
            "status": self.status,
            "request_validated": bool(self.request_validated),
            "execution_attempted": bool(self.execution_attempted),
            "capability_available": self.capability_available,
            "side_effect_performed": bool(self.side_effect_performed),
            "effect_verified": bool(self.effect_verified),
            "observation_completed": bool(self.observation_completed),
            "execution_verified": bool(self.execution_verified),
            "host_version": self.host_version,
            "completed_at": self.completed_at,
            "audit_digest": self.audit_digest,
            "blocked": bool(self.blocked),
            "cancelled": bool(self.cancelled),
            "confirmed": bool(self.confirmed),
            "plan_id": self.plan_id,
        }


class ActionHost:
    """Local executor boundary with capability metadata and tamper-evident audit."""

    def __init__(self, project_dir: Path | None = None, *, policy: str = "CONFIRM_EXECUTION") -> None:
        self.project_dir = (project_dir or Path.cwd()).expanduser().resolve()
        self.engine = ActionEngine(self.project_dir)
        self.coordinator = ActionCoordinator(self.engine, policy=policy)
        self.audit_path = self.project_dir / ".gaia_action_audit.jsonl"
        self.registry = default_capability_registry()

    def public_capabilities(self) -> dict[str, Any]:
        definitions = []
        for item in self.registry.all():
            definitions.append({
                "name": item.name,
                "category": item.category,
                "description": item.description,
                "risk_level": item.risk_level,
                "required_permissions": list(item.required_permissions),
                "supported_os": list(item.supported_os),
                "parameter_schema": list(item.parameter_schema),
                "confirmation_policy": item.confirmation_policy,
                "reversible": item.reversible,
                "timeout": item.timeout,
                "implemented": item.implemented,
            })
        return {"host": "pc", "host_version": HOST_VERSION, "status": "online", "capabilities": definitions}

    def execute(self, action_response: dict, *, confirmed: bool = True) -> VerifiedActionResult:
        parsed = parse_action_response(action_response)
        if not parsed:
            raise ActionCoordinatorError("Respuesta de acción inválida o incompleta.")
        action_id = str(action_response.get("action_id") or parsed.action_id or "")[:120]
        session_id = str(action_response.get("session_id") or "")[:120]
        device = str(action_response.get("device") or "pc-main")[:120]
        execution_contract = self._execution_contract(action_response, device=device, action_id=action_id)
        preflight = preflight_contract(self.engine, execution_contract, device=device)
        if preflight.get("status") != "READY":
            if preflight.get("request_validated") is False:
                raise ActionCoordinatorError(str(preflight.get("message") or "El contrato no pasó la validación del allowlist."))
            action_name = str((preflight.get("steps") or [{}])[0].get("action") or parsed.kind)
            status = str(preflight.get("status") or "FAILED").upper()
            if status not in {"DENIED", "UNAVAILABLE", "PARTIAL", "FAILED"}:
                status = "FAILED"
            message = str(preflight.get("message") or "La acción no pasó el preflight.")
            local_data = {"preflight": preflight, "status": status, "capability_available": preflight.get("capability_available"), "side_effect_performed": False, "effect_verified": False, "observation_completed": False, "execution_verified": False}
            result = {"action_id": action_id, "session_id": session_id, "device": device, "success": False, "action": action_name, "message": message, "data": local_data, "status": status, "request_validated": bool(preflight.get("request_validated")), "execution_attempted": False, "capability_available": preflight.get("capability_available"), "side_effect_performed": False, "effect_verified": False, "observation_completed": False, "execution_verified": False, "host_version": HOST_VERSION}
            digest = self._audit(result)
            return VerifiedActionResult(action_id=action_id, session_id=session_id, device=device, success=False, action=action_name, message=message, data=local_data, execution_verified=False, completed_at=result["completed_at"], audit_digest=digest, blocked=status == "DENIED", cancelled=False, confirmed=bool(confirmed), plan_id=str(action_response.get("plan", {}).get("plan_id")) if isinstance(action_response.get("plan"), dict) and action_response.get("plan", {}).get("plan_id") else None, status=status, request_validated=bool(result["request_validated"]), execution_attempted=False, capability_available=result["capability_available"], side_effect_performed=False, effect_verified=False, observation_completed=False)
        local = self.coordinator.execute(execution_contract, confirmed=confirmed)

        local_data = dict(local.get("data") or {})
        action_name = str(local.get("action") or parsed.kind)
        action_items = [item for item in (local_data.get("actions") if isinstance(local_data.get("actions"), list) else []) if isinstance(item, dict)]
        item_statuses = [str(item.get("status") or ("SUCCESS" if item.get("success") else "FAILED")).upper() for item in action_items]
        if bool(local.get("blocked")):
            status = "DENIED"
        elif bool(local.get("cancelled")):
            status = "CANCELLED"
        elif any(item_status == "UNAVAILABLE" for item_status in item_statuses):
            status = "UNAVAILABLE"
        elif bool(local.get("success")) and action_items and all(item_status == "SUCCESS" for item_status in item_statuses):
            status = "SUCCESS"
        elif action_items and len(action_items) < int(local_data.get("total") or len(action_items)):
            status = "PARTIAL"
        else:
            status = "FAILED"
        capability_available = all(item.get("capability_available", True) is not False for item in action_items) if action_items else (False if status == "UNAVAILABLE" else True)
        side_effect_performed = any(bool(item.get("side_effect_performed")) for item in action_items)
        mutating_items = [item for item in action_items if not bool(item.get("observation_completed"))]
        observing_items = [item for item in action_items if bool(item.get("observation_completed"))]
        effect_verified = bool(status == "SUCCESS" and mutating_items and all(bool(item.get("effect_verified")) for item in mutating_items))
        observation_completed = bool(status == "SUCCESS" and observing_items and len(observing_items) == len(action_items) and all(bool(item.get("observation_completed")) for item in observing_items))
        execution_verified = bool(status == "SUCCESS" and action_items and all(bool(item.get("execution_verified")) for item in action_items))
        local_data.update({"status": status, "capability_available": capability_available, "side_effect_performed": side_effect_performed, "effect_verified": effect_verified, "observation_completed": observation_completed, "execution_verified": execution_verified})
        result = {
            "action_id": action_id,
            "session_id": session_id,
            "device": device,
            "success": bool(status == "SUCCESS"),
            "action": action_name,
            "message": str(local.get("message") or "Acción completada."),
            "data": local_data,
            "status": status,
            "request_validated": True,
            "execution_attempted": bool(action_items) or bool(local.get("blocked")) or bool(local.get("cancelled")),
            "capability_available": capability_available,
            "side_effect_performed": side_effect_performed,
            "effect_verified": effect_verified,
            "observation_completed": observation_completed,
            "execution_verified": execution_verified,
            "host_version": HOST_VERSION,
        }
        digest = self._audit(result)
        return VerifiedActionResult(
            action_id=action_id,
            session_id=session_id,
            device=device,
            success=bool(result["success"]),
            action=action_name,
            message=result["message"],
            data=local_data,
            execution_verified=execution_verified,
            completed_at=result["completed_at"],
            audit_digest=digest,
            blocked=bool(local.get("blocked")),
            cancelled=bool(local.get("cancelled")),
            confirmed=bool(local.get("confirmed")),
            plan_id=str(local.get("plan_id")) if local.get("plan_id") else None,
            status=str(result["status"]),
            request_validated=bool(result["request_validated"]),
            execution_attempted=bool(result["execution_attempted"]),
            capability_available=result["capability_available"],
            side_effect_performed=bool(result["side_effect_performed"]),
            effect_verified=bool(result["effect_verified"]),
            observation_completed=bool(result["observation_completed"]),
        )

    @staticmethod
    def _execution_contract(action_response: dict[str, Any], *, device: str, action_id: str) -> dict[str, Any]:
        """Copy structured action data and attach non-public capture metadata."""
        contract = copy.deepcopy(action_response)
        def decorate(action: dict[str, Any]) -> None:
            args = dict(action.get("args") or {})
            args.update({"_owner_device": device, "_target_host": str(contract.get("target_host") or "pc-main")[:120], "_request_id": action_id})
            action["args"] = args
        plan = contract.get("plan") if isinstance(contract.get("plan"), dict) else None
        if plan and isinstance(plan.get("actions"), list):
            for action in plan["actions"]:
                if isinstance(action, dict):
                    decorate(action)
        elif isinstance(contract.get("action"), dict):
            decorate(contract["action"])
        return contract

    def _audit(self, result: dict[str, Any]) -> str:
        safe = {
            "action_id": result["action_id"],
            "session_id": result["session_id"],
            "device": result["device"],
            "success": result["success"],
            "action": result["action"],
            "status": result["status"],
            "execution_verified": result["execution_verified"],
            "capability_available": result["capability_available"],
            "side_effect_performed": result["side_effect_performed"],
            "effect_verified": result["effect_verified"],
            "observation_completed": result["observation_completed"],
            "host_version": HOST_VERSION,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        result["completed_at"] = safe["completed_at"]
        previous = ""
        if self.audit_path.exists():
            try:
                previous = json.loads(self.audit_path.read_text(encoding="utf-8").splitlines()[-1]).get("digest", "")
            except (OSError, ValueError, IndexError):
                previous = ""
        safe["previous_digest"] = previous
        canonical = json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        safe["digest"] = digest
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe, ensure_ascii=False, sort_keys=True) + "\n")
        return digest
