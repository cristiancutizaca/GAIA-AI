"""Autenticación y autorización centralizada de GAIA v0.6.0.

El secreto maestro es un Principal administrativo. Los tokens de dispositivo
solo reciben las capacidades persistidas para ese dispositivo. La interfaz no
confía en capabilities declaradas por el cliente: siempre consulta el token
verificado en SQLite.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Callable

from fastapi import Depends, Header, HTTPException

from config import API_SECRET, DEVICE_TOKENS_ENABLED
from lan_protocol import GLOBAL_RATE_LIMITER
import hmac
import memory

CAP_CHAT = "chat"
CAP_MEMORY_READ = "memory_read"
CAP_MEMORY_WRITE = "memory_write"
CAP_VOICE = "voice"
CAP_DIAGNOSTICS = "diagnostics"
CAP_ACTIONS_REQUEST = "actions_request"
CAP_ACTIONS_EXECUTE = "actions_execute"
CAP_ACTION_HOST = "action_host"
CAP_BACKUP_CREATE = "backup_create"
CAP_PROACTIVE_READ = "proactive_read"
CAP_PROACTIVE_CONTROL = "proactive_control"
CAP_DEVICE_SELF = "device_self"
CAP_DEVICE_ADMIN = "device_admin"
CAP_BRAIN_RESTORE = "brain_restore"
CAP_ADMIN = "admin"

ALL_CAPABILITIES = frozenset({
    CAP_CHAT, CAP_MEMORY_READ, CAP_MEMORY_WRITE, CAP_VOICE, CAP_DIAGNOSTICS,
    CAP_ACTIONS_REQUEST, CAP_ACTIONS_EXECUTE, CAP_ACTION_HOST,
    CAP_BACKUP_CREATE, CAP_PROACTIVE_READ, CAP_PROACTIVE_CONTROL,
    CAP_DEVICE_SELF, CAP_DEVICE_ADMIN, CAP_BRAIN_RESTORE, CAP_ADMIN,
})


@dataclass(frozen=True)
class Principal:
    """Identidad autenticada, nunca construida desde el JSON del request."""

    type: str
    device_id: str | None = None
    token_id: str | None = None
    permission_level: int = 0
    capabilities: frozenset[str] = frozenset()

    @property
    def is_master(self) -> bool:
        return self.type == "master"

    def allows(self, capability: str) -> bool:
        if self.is_master:
            return True
        return capability in self.capabilities or CAP_ADMIN in self.capabilities

    def as_safe_dict(self) -> dict:
        return {
            "type": self.type,
            "device_id": self.device_id,
            "token_id": self.token_id,
            "permission_level": self.permission_level,
            "capabilities": sorted(self.capabilities),
        }


def _master_principal() -> Principal:
    return Principal(type="master", permission_level=2, capabilities=ALL_CAPABILITIES)


def authenticate(authorization: str = Header(default="")) -> Principal:
    """Authenticate bearer credentials; distinguish invalid auth from denied auth."""
    allowed, retry_after = GLOBAL_RATE_LIMITER.check(authorization[:512])
    if not allowed:
        raise HTTPException(status_code=429, detail="Límite de solicitudes alcanzado.", headers={"Retry-After": str(retry_after)})
    expected = f"Bearer {API_SECRET}"
    if hmac.compare_digest(authorization, expected):
        return _master_principal()
    if DEVICE_TOKENS_ENABLED and authorization.startswith("Bearer "):
        verified = memory.verify_device_token(authorization[7:])
        if verified:
            return Principal(
                type="device",
                device_id=str(verified["device_id"]),
                token_id=str(verified["token_id"]),
                permission_level=int(verified.get("permission_level", 0)),
                capabilities=frozenset(str(item) for item in verified.get("capabilities", [])),
            )
    raise HTTPException(status_code=401, detail="No autorizado")


def require_capability(capability: str) -> Callable:
    """FastAPI dependency that returns a Principal or fails with 403."""
    async def dependency(principal: Annotated[Principal, Depends(authenticate)]) -> Principal:
        if not principal.allows(capability):
            raise HTTPException(status_code=403, detail=f"Falta la capability requerida: {capability}")
        return principal
    dependency.__name__ = f"require_{capability}"
    return dependency


def require_master(principal: Annotated[Principal, Depends(authenticate)]) -> Principal:
    if not principal.is_master:
        raise HTTPException(status_code=403, detail="Se requiere el Principal master.")
    return principal


def effective_device(principal: Principal, requested: str | None) -> str:
    """Master may name a session device; device tokens are bound to their device."""
    if principal.is_master:
        return str(requested or "pc")[:40]
    return str(principal.device_id or "unknown")[:40]


def can_request_actions(principal: Principal) -> bool:
    return principal.is_master or principal.allows(CAP_ACTIONS_REQUEST)


def can_execute_actions(principal: Principal) -> bool:
    return principal.is_master or (principal.allows(CAP_ACTIONS_EXECUTE) and principal.allows(CAP_ACTION_HOST))
