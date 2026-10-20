HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# Safe Mode — GAIA-AI v1.0-RC2

Safe Mode is a startup policy, not a conversational preference. Set `GAIA_SAFE_MODE=true` before the Core process starts. Configuration is read once at import/startup; leaving Safe Mode requires changing configuration and restarting the Core. The LLM cannot enable or disable it.

## Allowed surfaces

Safe Mode allows ordinary conversational chat and LLM responses, read-only diagnostics and status, memory reads, session/history reads within the authenticated namespace, and memory audit. The runtime may keep the minimum event plumbing needed for diagnostics, but it does not start automation scheduling or effectful watchers.

## Blocked surfaces

Safe Mode blocks external action requests and their approval, rejection, claim, heartbeat, completion, and execution lifecycle. It blocks action-host mutation, proactive queue/toggle operations, automation creation or enablement, routine and schedule creation or enablement, advanced-memory CRUD and consolidation, preference/task/project-note mutations, summary refresh, backups, and other effectful mutation endpoints. A blocked operation returns a `409` response containing `SAFE_MODE_BLOCKED` and does not create a pending action or mutate the protected resource.

Disabling actions through a kill switch remains a safety control and is allowed; re-enabling them is blocked. Disabling an automation, pausing runtime, or other fail-safe reduction is allowed, while resuming or enabling effects is blocked.

## Runtime behavior

| Component | Safe Mode behavior |
|---|---|
| Chat and diagnostics | Available; status exposes `safe_mode=true`. |
| Advanced Memory reads and audit | Available through the authenticated namespace context. |
| AutomationEngine | Constructed in safe mode, reports inactive, and does not execute routines. |
| Scheduler | Not started. |
| Watchers | Not started; registry remains available for diagnostics. |
| Proactive loop | Not started by bootstrap. |
| Backup loop | Not started by bootstrap. |
| Event plumbing | Minimum bounded event engine may run for diagnostics; it has no effectful automation path. |
| Remote action host | Heartbeat/claim/complete mutations blocked. |
| ResourceGovernor | Read-only bounded monitor may report policy; it does not alter hardware, power plans, fans, BIOS, GPU state, or models. |

The public status and diagnostics responses expose Safe Mode and the action boundary. Tests verify that conversational action-shaped requests return `SAFE_MODE_BLOCKED`, that no pending action is created, that automation remains paused, and that shared governor authority is reported.

Safe Mode is not a substitute for authentication or namespace authorization. Every memory read and audit operation still requires the normal principal capabilities and exact device/session ownership rules. It also does not assert physical readiness for Windows, Android, GPU, audio, LAN/TLS, Ollama, battery, or thermal behavior.
