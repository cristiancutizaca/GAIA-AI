"""Contratos del Capability Registry PC v0.6.0."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

from capabilities import CapabilityRegistry, CapabilityValidationError, VerifiedCapabilityResult, default_capability_registry
from action_engine import ActionEngine

registry = default_capability_registry()
all_capabilities = {item.name: item for item in registry.all()}
assert {"apps.open", "apps.list", "system.status", "files.delete", "git.status", "projects.list", "browser.open"} <= set(all_capabilities)
assert all_capabilities["system.status"].risk_level == 0
assert all_capabilities["apps.open"].risk_level == 1
assert all_capabilities["files.delete"].risk_level == 3
assert all_capabilities["system.shutdown"].risk_level == 4
assert all_capabilities["system.shutdown"].confirmation_policy == "ALWAYS_CONFIRM"
assert all_capabilities["system.shutdown"].implemented is True

open_spotify = registry.request_for_action("open_spotify")
assert open_spotify.capability == "apps.open" and open_spotify.params["app"] == "spotify"
open_url = registry.request_for_action("open_url", {"url": "https://example.com"})
assert open_url.capability == "url.open" and open_url.params["url"] == "https://example.com"
status = registry.request_for_action("system_status")
assert status.capability == "system.status"

try:
    registry.request("apps.open", {"app": "spotify", "executable": "powershell"})
except CapabilityValidationError:
    pass
else:
    raise AssertionError("un parámetro arbitrario no puede entrar en apps.open")

shutdown = registry.request("system.shutdown", {})
assert shutdown.capability == "system.shutdown" and shutdown.params == {}

try:
    registry.request("apps.open", {"app": "unknown-app"})
except CapabilityValidationError:
    pass
else:
    raise AssertionError("apps.open aún debe validar alias/canonical app en el adaptador local")

assert not hasattr(registry, "register"), "el registry no debe ser ampliable por el LLM en runtime"
result = VerifiedCapabilityResult("apps.open", True, "Spotify abierto.", {"app": "spotify"})
payload = result.as_dict()
assert payload["execution_verified"] is True and payload["data"]["app"] == "spotify"

engine = ActionEngine(ROOT)
dry_run = engine.execute_capability(open_spotify, allow_execution=False)
assert dry_run.success is True and dry_run.execution_verified is False and dry_run.data["dry_run"] is True
status_result = engine.execute_capability(status, allow_execution=True)
assert status_result.execution_verified is True and status_result.capability == "system.status"

implemented_count = sum(1 for item in registry.all() if item.implemented)
assert implemented_count >= 40
print(f"CAPABILITY REGISTRY TEST OK: immutable definitions, {implemented_count}/{len(all_capabilities)} implemented, strict params, high-risk policy metadata and verified result.")
