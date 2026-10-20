HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

HISTORICAL DOCUMENT — DO NOT USE FOR RC5 OPERATIONS

This document is preserved for historical traceability only. For current RC5 operations use `WINDOWS_RC5_VALIDATION_CHECKLIST.md`, `UPDATE_ROLLBACK_GUIDE.md` and `PHYSICAL_VALIDATION_RC5.md`.

# Physical validation — GAIA-AI v1.0-RC4

This document defines the operator-facing physical validation contract. It is not evidence that the checks passed. The Linux sandbox cannot confirm Windows UI Automation, SMTC, displays, audio, Ollama inference, GPU performance, battery, thermal behavior, LAN/TLS, Android, signing, or long-session stability.

## Session protocol

Create a new external session with `python tools/physical_validation.py new --output-dir <external-directory>`. The tool writes `physical_validation_RC4_<timestamp>.json` and the matching Markdown report. Use `show` for a read-only summary. Use `record` only after the operator has performed the check and has a redacted evidence file. Use `finalize` to close the ledger; finalization does not promote RC4 or authorize v1.0 final.

Every control starts as `PENDING`. A `PASS` requires `--operator-confirmed` and `--evidence-file`; the tool stores only byte count and SHA-256 of the evidence file, not its contents. Previous observations are copied into the report history and are never silently overwritten. The report and raw evidence remain outside the project ZIP.

## Controls

| ID | Physical scope | Minimum evidence requirement |
|---|---|---|
| `windows_runtime` | Windows 11 Python 3.11 clean extraction and Doctor. | Redacted command output from the target machine. |
| `uia` | Read-only UIA and trusted interaction boundary. | Human observation tied to window identity and preflight. |
| `smtc_display` | SMTC and one/external display enumeration. | Human-confirmed display/media behavior. |
| `audio` | Bounded microphone/TTS permission and cleanup. | Redacted recording metadata and cleanup result; no audio in ZIP. |
| `ollama_qwen` | Manually present Ollama/Qwen inference. | Exact model name, short request timing, and degradation test; no auto-download. |
| `gpu_vram` | Read-only GPU/VRAM observation. | Target-machine telemetry; enumeration alone is insufficient for performance PASS. |
| `battery_thermal` | AC/battery and trustworthy temperature readings. | Bounded observation; missing sensors remain `NOT_MEASURED`. |
| `lan_tls` | Explicit LAN opt-in and external TLS path. | Real path evidence; localhost is not physical LAN/TLS evidence. |
| `android_flutter` | Actual Flutter/Android build and companion flow. | Toolchain/build/device evidence; source existence is not PASS. |
| `signing` | Real APK/release signature verification. | Verified signed artifact; keystore existence alone is not PASS. |
| `long_session_soak` | Bounded 10/30 minute stability. | Timed session, errors, resource observations, and stop behavior. |
| `rollback_recovery` | Copied installation migration and rollback. | Inspect, snapshot, approved apply, rollback, checksum, source preservation. |

Allowed statuses are `PASS`, `FAIL`, `PENDING`, `NOT_MEASURED`, `BLOCKED`, and `SKIP`. If any relevant check is `FAIL`, `PENDING`, `BLOCKED`, or `NOT_MEASURED`, the session reports `NO_FINAL_RELEASE_AUTHORIZATION`. RC4 remains a release candidate and the operator must not treat the report as production certification.
