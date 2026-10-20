"""Protocol primitives for the opt-in GAIA v0.6 LAN boundary.

This module is deliberately transport-neutral. TLS remains an external
responsibility; the Core stays localhost by default and all pairing values are
short-lived, one-time and stored only as hashes.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets
import threading
from typing import Iterable

from gaia_version import PROTOCOL_VERSION
PAIRING_TTL_SECONDS = max(60, int(os.getenv("GAIA_PAIRING_TTL_SECONDS", "300")))
PAIRING_MAX_ATTEMPTS = max(1, int(os.getenv("GAIA_PAIRING_MAX_ATTEMPTS", "5")))
RATE_LIMIT_PER_MINUTE = max(10, int(os.getenv("GAIA_RATE_LIMIT_PER_MINUTE", "120")))
KNOWN_FEATURES = {
    "chat": "1",
    "memory_continuity": "1",
    "voice": "1",
    "actions_request": "1",
    "actions_execute": "1",
    "action_host": "1",
    "device_permissions": "1",
    "permission_memory": "1",
    "streaming_sse": "1",
    "brain_backup": "1",
}


@dataclass(frozen=True)
class PairingRecord:
    pairing_id: str
    device_id: str
    capabilities: tuple[str, ...]
    code_digest: str
    expires_at: datetime
    attempts: int = 0


class PairingManager:
    def __init__(self) -> None:
        self._records: dict[str, PairingRecord] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _digest(pairing_id: str, code: str) -> str:
        return hashlib.sha256(f"{pairing_id}:{code}".encode("utf-8")).hexdigest()

    def start(self, device_id: str, capabilities: Iterable[str]) -> dict:
        safe_device = str(device_id).strip()[:120]
        if not safe_device:
            raise ValueError("device_id vacío")
        clean_caps = tuple(sorted({str(item).strip()[:80] for item in capabilities if str(item).strip() in KNOWN_FEATURES}))
        pairing_id = secrets.token_urlsafe(18)
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires = datetime.now(timezone.utc) + timedelta(seconds=PAIRING_TTL_SECONDS)
        with self._lock:
            self._records[pairing_id] = PairingRecord(pairing_id, safe_device, clean_caps, self._digest(pairing_id, code), expires)
        return {"pairing_id": pairing_id, "code": code, "expires_at": expires.isoformat(), "protocol_version": PROTOCOL_VERSION, "device_id": safe_device}

    def complete(self, pairing_id: str, code: str) -> dict:
        with self._lock:
            record = self._records.get(str(pairing_id))
            if not record or record.expires_at <= datetime.now(timezone.utc):
                self._records.pop(str(pairing_id), None)
                raise ValueError("Pairing expirado o inexistente.")
            if not hmac.compare_digest(record.code_digest, self._digest(record.pairing_id, str(code).strip())):
                attempts = record.attempts + 1
                if attempts >= PAIRING_MAX_ATTEMPTS:
                    self._records.pop(record.pairing_id, None)
                else:
                    self._records[record.pairing_id] = PairingRecord(record.pairing_id, record.device_id, record.capabilities, record.code_digest, record.expires_at, attempts)
                raise ValueError("Código de pairing inválido.")
            self._records.pop(record.pairing_id, None)
        return {"pairing_id": record.pairing_id, "device_id": record.device_id, "capabilities": list(record.capabilities), "protocol_version": PROTOCOL_VERSION}


class SlidingWindowRateLimiter:
    def __init__(self, limit: int = RATE_LIMIT_PER_MINUTE, window_seconds: int = 60) -> None:
        self.limit = max(1, int(limit))
        self.window = max(1, int(window_seconds))
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        current = float(now if now is not None else datetime.now(timezone.utc).timestamp())
        cutoff = current - self.window
        with self._lock:
            events = self._events.setdefault(hashlib.sha256(str(key).encode("utf-8")).hexdigest(), deque())
            while events and events[0] <= cutoff:
                events.popleft()
            allowed = len(events) < self.limit
            if allowed:
                events.append(current)
            retry_after = max(1, int(events[0] + self.window - current)) if events else self.window
            if len(self._events) > 2048:
                stale = [name for name, values in self._events.items() if not values or values[-1] <= cutoff]
                for name in stale[:512]:
                    self._events.pop(name, None)
            return allowed, retry_after


def negotiate_features(local: dict[str, str] | None, remote: dict[str, str] | None, *, allow_remote_actions: bool = False) -> dict:
    local = {str(k): str(v) for k, v in (local or KNOWN_FEATURES).items() if str(k) in KNOWN_FEATURES}
    remote = {str(k): str(v) for k, v in (remote or {}).items() if str(k) in KNOWN_FEATURES}
    common = {name: local[name] for name in sorted(set(local) & set(remote)) if local[name] == remote[name]}
    if not allow_remote_actions:
        common.pop("actions_execute", None)
        common.pop("action_host", None)
    return {"protocol_version": PROTOCOL_VERSION, "features": common, "restricted": not allow_remote_actions, "local_only_actions": ["actions_execute", "action_host"]}


PAIRING_MANAGER = PairingManager()
GLOBAL_RATE_LIMITER = SlidingWindowRateLimiter()
