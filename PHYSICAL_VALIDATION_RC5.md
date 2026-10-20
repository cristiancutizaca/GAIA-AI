HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v1.0-RC5 Physical Validation

This document defines the external operator ledger. A new session contains exactly twelve controls and derives its summary from the actual controls before the JSON is first written.

| ID | Initial status | Evidence rule |
|---|---|---|
| `windows_runtime` | PENDING | Real Windows 11 runtime and clean extraction |
| `uia` | PENDING | Identity-based UIA observation and preflight |
| `smtc_display` | PENDING | Real display/SMTC observation |
| `audio` | PENDING | Bounded microphone/TTS test and cleanup |
| `ollama_qwen` | PENDING | One manually confirmed local inference, no auto-download |
| `gpu_vram` | PENDING | Read-only observation, no tuning |
| `battery_thermal` | PENDING | Trustworthy AC/battery/sensor evidence |
| `lan_tls` | PENDING | Explicit external LAN/TLS path, not localhost |
| `android_flutter` | PENDING | Real toolchain/device/build evidence |
| `signing` | PENDING | Real signed artifact and verification |
| `long_session_soak` | PENDING | Real 10/30-minute duration and observations |
| `rollback_recovery` | PENDING | Copied installation, checksum and source preservation |

Use `python tools/physical_validation.py new --output-dir <external>` and then `validate`, `show`, `record` and `finalize`. `validate` is read-only by default and returns `REPORT_INCONSISTENT` for mismatched summaries, states, IDs, timestamps, history, authorization or Markdown. `--repair-summary` is explicit, records the previous summary in history, preserves individual states and never creates a PASS. `PASS` requires evidence, method, limitations, timestamp and explicit operator confirmation. Finalization closes the ledger only; it does not authorize a final release.
