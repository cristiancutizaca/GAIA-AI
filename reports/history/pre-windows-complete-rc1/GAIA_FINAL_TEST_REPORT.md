# GAIA Final Test Report

## Executed gate

| Gate | Result | Evidence |
|---|---|---|
| Historical and current Python tests | PASS | 136 test files, isolated per test |
| v12 platform regression | PASS | `tests/v12_platform_test.py` |
| global authority/security | PASS | `tests/v14_global_authority_test.py` |
| real API E2E | PASS | `tests/v13_core_e2e_test.py` |
| v16 upstream contracts | PASS | `tests/v16_real_backends_test.py` |
| v17 desktop/upstream contracts | PASS | `tests/v17_desktop_and_upstreams_test.py`, 8/8 |
| Browser Use local rendered E2E | PASS | local Chromium, example.com read, screenshot saved |
| CLI smoke | PASS | existing GAIA CLI contracts |
| backup/restore | PASS | existing BackupManager contracts |
| clean startup/shutdown | PASS | existing lifespan and lifecycle contracts |
| physical Windows/Android/audio | PENDING | operator hardware required |

**Final isolated gate result: 136/136 automated checks PASS; 0 FAIL; 0 TIMEOUT.**

Tests were run with `PYTHONDONTWRITEBYTECODE=1` and cleanup before every file, preventing local SQLite/data artifacts from contaminating release hygiene. The initial non-isolated run produced three false failures because earlier tests left `data/`; the isolated rerun passed the three historical runner/package contracts.

## Real-backend evidence

Browser Use uses the installed `BrowserSession` plus actor `Page`/`Element` API, explicitly local-only. The E2E started Chromium, read rendered text from `example.com` and saved a screenshot. Mem0, Graphiti and OpenHands are real lazy boundaries with explicit configuration/credentials and remain honestly classified as deployment-dependent. Pipecat creates a real `PipelineTask`/`PipelineRunner` and uses `InterruptionFrame` for cancellation. PySide6, microphone, Windows GUI, Android SDK/device and UI-TARS remain physical validation items.

No test uses a mock as evidence of physical readiness. Direct class tests are reported separately from public API E2E.
