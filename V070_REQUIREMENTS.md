HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.7.0 — Requirements and Evidence

## Purpose

Version 0.7.0, **Advanced Desktop Foundation**, extends the validated v0.6.3 PC/Android base with structured desktop observation, Windows UI Automation contracts, active context, code-owned application adapters, operating-system media controls, bounded composite plans, and relevant-only context hints. The release preserves the existing security boundary: no arbitrary shell strings, no `shell=True`, no `eval`/`exec` of model output, no coordinate clicking, and no dynamic executable plugins.

## Acceptance matrix

| Requirement | Implementation evidence | Automated evidence | Physical status |
|---|---|---|---|
| Ephemeral active desktop context | `lumen-pc/desktop_context.py` with TTL cache, foreground metadata, process identity, and display mapping | `v070_observation_contract_test.py` | **PENDING** Windows foreground validation |
| UIA read-only inspection | `lumen-pc/uia.py`; `desktop.context`, `uia.inspect_window`, `uia.list_controls`, and `uia.get_focused_control` | `v070_observation_contract_test.py`; capability registry gate | **PENDING** Windows UIA provider validation |
| UIA interaction allowlist | `focus_control`, `invoke_control`, `set_control_value`; ActionEngine dispatch only | `v070_observation_contract_test.py`; `security_regression_test.py` | **PENDING** Windows interaction validation |
| Trusted executable identity | `safe_apps.is_trusted_executable()` and the UIA interaction guard | UIA contract and security regression tests | **PENDING** Windows executable identity validation |
| Stale-target protection | `expected_target` is mandatory for UIA interactions; window referents preserve a request-time identity snapshot | observation and workspace-plan tests | **PENDING** handle-reuse validation on Windows |
| Password and sensitive-value protection | Password controls are redacted and `uia.set_value` rejects sensitive tokens | `v070_observation_contract_test.py` | **PENDING** physical password-control validation |
| On-demand screen capture | `lumen-pc/screen_capture.py`; TTL cleanup and no continuous surveillance | observation contract test | **PENDING** Windows capture validation |
| Code-owned application adapters | `lumen-pc/app_adapters.py`; canonical `safe:vscode` identity; five VS Code capabilities | capability registry and security tests | **PENDING** Windows VS Code execution validation |
| SMTC media controls | `lumen-pc/media_session.py`; OS SMTC only, no provider credentials or scraping | `media_capability_v070_test.py` | **PENDING** Windows active-session validation |
| Composite programming workspace | `workspace_profiles.py`; bounded display list, VS Code focus/open, optional primary-display move, Git status | `v070_workspace_plan_test.py`; five-step coordinator ceiling | **PENDING** physical multi-display execution |
| Pronoun/referent resolution | `resolve_window_referent()` resolves `ciérralo`, `minimízalo`, and explicit primary-display `muévelo` once at request creation | `v070_workspace_plan_test.py` | **PENDING** Windows stale-target exercise |
| Relevant-only context injection | `active_context` is returned only for app/window/display/context references; PID, executable and full UI trees are not sent | `v070_context_injection_test.py` | **PASS** contract-level; **PENDING** Windows client observation |
| Android/PC pairing continuity | Existing QR pairing, secure storage, token recovery, and LAN opt-in remain intact; Android version is `0.7.0+1` | Android onboarding and LAN regression tests | **PENDING** Flutter build and device pairing |
| LAN default | `GAIA_LAN_ENABLED=false` remains the default; remote actions require explicit host/device permissions | LAN and remote-action regression tests | **PASS** default-policy validation |
| No hidden surveillance | No continuous screen capture, no permanent active-window memory, no automatic Brain Backup inclusion | source review and observation contracts | **PASS** code-contract validation |

## Security invariants

The release is not considered acceptable if any of the following changes: arbitrary shell execution becomes reachable, model output is treated as executable code, UI interaction accepts raw coordinates, password values are exposed, an untrusted executable can receive UIA interaction, stale targets are re-resolved after confirmation, media control requests use provider credentials, or a remote Android device bypasses the same Permission Memory and VerifiedActionResult flow as `pc-main`.

## Validation interpretation

**PASS** means the behavior is demonstrated by deterministic tests in the Linux sandbox or by a source-level contract that does not require Windows or Flutter. **PENDING** means the implementation and contract are present but the physical dependency is unavailable in the sandbox. PENDING is not reported as FAIL, but it is not represented as physical validation.

## Reproducibility

The final project archive must be created by `tools/build_release.py`, reopened and compared with its staging tree, and accompanied by a SHA-256 file. Validation must then run from a fresh extraction with runtime data, caches, credentials, and local ZIPs absent.
