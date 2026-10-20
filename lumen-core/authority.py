from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from config import SAFE_MODE
import memory

READ_ONLY = "READ_ONLY"
LOW_RISK = "LOW_RISK"
INTERACTIVE = "INTERACTIVE"
EXTERNAL_SIDE_EFFECT = "EXTERNAL_SIDE_EFFECT"
PRIVILEGED = "PRIVILEGED"
DESTRUCTIVE = "DESTRUCTIVE"

@dataclass(frozen=True)
class AuthorityDecision:
    allowed: bool
    status: str
    reason: str
    capability: str
    risk: str
    def as_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "status": self.status, "reason": self.reason, "capability": self.capability, "risk": self.risk}

def _kill_switch_active() -> bool:
    return memory.get_state("gaia_actions_enabled", "1") != "1"

def authorize(principal: Any, *, capability: str, permission: str | None = None, risk: str = READ_ONLY, resource_scope: str = "", confirmed: bool = False) -> AuthorityDecision:
    """Single gate for runtime capabilities. Read-only operations survive Safe Mode/kill switch; effects do not."""
    required = permission or capability
    allows = bool(getattr(principal, "allows", lambda _: False)(required))
    if not allows:
        return AuthorityDecision(False, "DENIED", f"missing capability: {required}", capability, risk)
    if risk != READ_ONLY and (SAFE_MODE or _kill_switch_active()):
        mode = "SAFE_MODE" if SAFE_MODE else "KILL_SWITCH"
        return AuthorityDecision(False, f"{mode}_BLOCKED", f"{mode} blocks side effects", capability, risk)
    if risk in {INTERACTIVE, EXTERNAL_SIDE_EFFECT, PRIVILEGED, DESTRUCTIVE} and not confirmed:
        return AuthorityDecision(False, "WAITING_PERMISSION", "explicit GAIA confirmation required", capability, risk)
    return AuthorityDecision(True, "AUTHORIZED", "policy passed", capability, risk)

def kill_switch_active() -> bool:
    return _kill_switch_active()
