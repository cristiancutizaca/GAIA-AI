# GAIA Final Security Report

## P0 result

The former path allowed `PlatformRuntime.handle_chat()` to reach MCP before the normal action gate and supplied `confirmed=True`. This is fixed.

### Controls now enforced

1. `authority.authorize` is the single runtime gate.
2. Safe Mode blocks all non-read-only capabilities.
3. Kill Switch blocks all non-read-only capabilities and pending actions.
4. Missing capability is denied; no implicit master bypass.
5. Interactive/external/privileged/destructive risks require explicit confirmation.
6. `MCPManager.call()` refuses side-effects unless it receives both a principal and the GAIA authority function.
7. Browser private-host access requires explicit allowlist and remains SSRF-hardened.
8. FilesystemSandbox rejects path traversal and symlink escape.
9. Diagnostics exporter redacts data and records `secret_values_emitted: false`.
10. Secrets support `secret://` and reject plaintext fallback.

## Evidence

- `tests/v14_global_authority_test.py`: Kill Switch, Safe Mode subprocess, permission denial, direct MCP bypass and runtime memory-write blocking — PASS.
- `tests/v13_core_e2e_test.py`: real API chat, Browser, MCP, Planner, Skills and diagnostics export — PASS.

Physical, LAN, Android, browser automation and external credential flows remain pending operator validation.


## Real-provider controls

Browser Use inherits SSRF and allowlist checks; all external page text is untrusted. OpenHands requires an approval flag and uses a disposable workspace. Mem0 and Graphiti never activate from an import alone. Pipecat/VAD are bounded voice providers. UI-TARS returns a safe environment block without a display. Visualizer is read-only and Event Bus payloads are redacted.
