# FINAL_BASELINE_V1_7

## Archive

The v1.7 source archive was checksum-verified before extraction:
`6b87b8309af138d6435ed727118ea3bd76f6f3b459eaaac42b73ff1680bbbfef`.

## Environment

- Linux Sandbox, Python 3.12.3, target Windows Python 3.11.
- Chromium and Playwright/Browser Use available.
- FastAPI, Pipecat, Mem0, Graphiti and OpenHands packages import.
- PySide6, sounddevice, openwakeword and Silero VAD are not installed in the Sandbox.
- No physical microphone, speaker, Windows tray, Windows GUI or Android device is available.

## Baseline results

- Python compileall: PASS.
- Isolated per-file gate: 136 files attempted; legacy v051 and v100 doctor checks initially detected bytecode contamination, and v13 exceeded its bounded window while Pipecat imported. These are tracked and re-tested after hardening.
- Authority, Permission Layer, Action Host, Kill Switch and Safe Mode contracts remain the security baseline.

The baseline is evidence of the starting state, not a claim of physical Windows readiness.
