HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# Windows first-test checklist — RC2 / RC3

This checklist is a guided operator record for the target Windows laptop. It is not executed in the Linux sandbox and must not be represented as a PASS until the operator confirms the observation on the physical machine.

| Check | Operator action | Result |
|---|---|---|
| Clean extraction | Extract the RC project ZIP into a new directory and verify the external SHA-256. | PENDING |
| Python/runtime | Confirm the supported Python 3.11 environment and run the package-first test command. | PENDING |
| Private configuration | Copy `.env.example` to a private `.env`, set a new local secret, and confirm the private file is not inside the project ZIP. | PENDING |
| Safe Mode | Set `GAIA_SAFE_MODE=true`, start the Core, confirm status/diagnostics report Safe Mode, chat works, and action/automation mutations return `SAFE_MODE_BLOCKED`. Restart after changing the setting. | PENDING |
| Vault | Run read-only inspection, create an external snapshot, choose an explicit database strategy, and verify target/source paths are distinct. | PENDING |
| Advanced Memory | Test two device tokens with session, working, task, history, search, and audit isolation. Insert no operational-origin semantic memories. | PENDING |
| Ollama | Check availability read-only. Do not auto-start the service or download a model. Record model name, latency, and context only if manually present. | PENDING / NOT MEASURED |
| GPU/VRAM | Record the physical GPU and available VRAM using a read-only operator check. | PENDING / NOT MEASURED |
| Battery/thermal | Observe a bounded long session on AC and battery; record system telemetry separately. No power-plan, fan, BIOS, or voltage changes are allowed. | PENDING / NOT MEASURED |
| Windows integration | Confirm UI Automation, active-window context, display enumeration, media controls, clipboard policy, and safe app discovery manually. | PENDING / NOT MEASURED |
| LAN/TLS | Test only after explicit LAN opt-in and an external TLS termination plan. | PENDING / NOT MEASURED |
| Android/Flutter | Check whether the actual Flutter/Android toolchain exists. If absent, record PENDING; never fabricate an APK or signing result. | PENDING / NOT MEASURED |

The operator should attach a separate physical validation report outside the release ZIP, including timestamp, machine identifier chosen by the operator, exact commands, pass/fail/pending status, and redacted outputs. Secrets, tokens, private paths, audio, databases, logs, and raw runtime artifacts must not be copied into the project archive.
