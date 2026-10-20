HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v1.0-RC5 Windows Validation Checklist

Target: ASUS TUF Gaming F15, Intel i5-12500H, approximately 48 GB RAM, RTX 3050 Laptop, Windows 11. This checklist is operator-guided. Every result starts as `PENDING`; missing sensors or unavailable tooling are `NOT_MEASURED`, never an invented PASS.

## A. Integrity

Verify the RC5 SHA-256 sidecar, extract into a new directory, preserve RC4, run the package gate and run RC5 preflight. Do not overwrite a stable installation.

## B. Dependencies

Create the venv outside the project, confirm explicit installation, record Python executable, `sys.prefix` and `pip freeze`, then run post-install preflight. Do not install globally, request administrator rights, modify antivirus/firewall or download executables.

## C. Core and client

Start only the bounded user-approved components. Test normal conversation, controlled memory, restart/recovery and Safe Mode. Record errors and cleanup; do not treat a mock as physical evidence.

## D. Ollama/Qwen

Detect without auto-starting or downloading. If the operator explicitly confirms availability, run one short local inference, record latency and errors, and stop if the environment is unsafe.

## E. Action Host

Use benign calculator, active-window, display enumeration and available media checks only. Confirm capability checks, kill switch, Safe Mode and rejection of unknown capabilities.

## F. Audio

Enumerate permission state, perform only bounded temporary capture/TTS if explicitly approved, verify deletion and record unavailable hardware as `NOT_MEASURED`.

## G. Displays/UIA

Test one display and available external monitors, scaling and primary display. UIA must use identity and preflight; never use blind coordinates.

## H. Performance and stability

Run the bounded benchmark, then an optional real 10-minute session and optional 30-minute session. Record CPU/RAM/VRAM, AC/battery and trustworthy thermal sensors. Stop if unsafe and do not change power, fan, BIOS or GPU profiles.

## I. Migration and rollback

Run inspect, plan, external snapshot, approved apply on a copy, Doctor postflight, rollback, checksum and source-preservation checks. Keep database-only and database-and-config rollback distinct.

## J. Android/LAN/TLS

Use only real toolchains/devices and an explicitly configured non-localhost network path. Do not declare Android, signing, LAN or TLS PASS from source existence or localhost.
