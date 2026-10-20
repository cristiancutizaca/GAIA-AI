# Migration and readiness matrix — RC2 to RC3

RC2 is the security and correctness candidate. RC3 is permitted only after RC2 is frozen with all gates passing and only for meaningful performance, stress, and physical-readiness preparation. No row in this matrix authorizes a final v1.0 declaration.

| Area | RC2 contract | RC3 follow-up | Evidence status |
|---|---|---|---|
| Advanced Memory ownership | Namespace-first exact device/session authorization; blank legacy device rows fail closed for non-master. | Stress CRUD/search/history across multiple authenticated devices without changing authorization semantics. | RC2 automated PASS; RC3 stress pending. |
| Provenance | Typed/canonical operational origins are rejected for semantic memory. | Measure rejection throughput and verify no operational auto-memory regressions under load. | RC2 automated PASS; RC3 benchmark pending. |
| External Vault | Clone, explicit reuse, and new-Vault strategies; no implicit source alias. | Profile large bounded snapshot/apply paths and document operator timing. | RC2 automated PASS; physical migration timing pending. |
| Target identity | Manifest/product/release/version/protocol/schema checks before mutation. | Include identity checks in clean extraction and release package gate. | RC2 automated PASS. |
| Rollback | Explicit database-only, database+config, and operator-managed previous-installation modes. | Measure bounded restore duration and preserve secret redaction. | RC2 automated PASS; hardware/filesystem timing pending. |
| Safe Mode | Runtime pause/block policy; chat/diagnostics/read/audit remain available. | Include long-session pause/resume observation without enabling external effects. | RC2 automated PASS; physical observation pending. |
| ResourceGovernor | One read-only runtime authority, bounded refresh, debounce, battery/thermal deferment. | Benchmark prompt budgeting and background intervals; do not add resident models or hardware control. | RC2 automated PASS; target-hardware telemetry pending. |
| Windows integration | Not claimed in sandbox. | Guided operator checklist for Windows/UIA/SMTC/display/audio. | PENDING / NOT MEASURED. |
| Android/Flutter | No APK or signing claim. | Attempt build only if actual toolchain exists; otherwise retain PENDING. | PENDING / NOT MEASURED. |
| Ollama/Qwen/GPU | No target model or GPU measurement in sandbox. | Read-only benchmark can report unavailable; never auto-start Ollama. | PENDING / NOT MEASURED. |
| Battery/thermal/LAN/TLS | No physical or network readiness claim. | Human-confirmed guided report only; excluded from release ZIP. | PENDING / NOT MEASURED. |

## Release order

Freeze RC2 only after the package-first clean extraction gate, compileall, all tests, external SHA-256, and two byte-identical rebuilds pass. Derive RC3 from a clean RC2 extraction rather than mutating frozen artifacts. RC3 changes must be measurable in benchmark, stress, soak, or readiness evidence. If no significant change is required, do not manufacture an RC3 version bump.

The final-readiness report must list exact commands, pass/fail/pending counts, hashes, unavailable physical items, and known limitations. It must explicitly say that the project remains a release candidate and that no `GAIA-AI-v1.0-final.zip` was produced.
