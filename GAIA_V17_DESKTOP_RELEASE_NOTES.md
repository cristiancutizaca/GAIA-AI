# GAIA v1.7 desktop and upstream release notes

This increment preserves the v1.6 authority chain and adds a resident Windows-first client shell. The shell is a UI client only: permissions, Kill Switch, Safe Mode and Action Host remain in GAIA Core.

Browser Use now uses the installed upstream `BrowserSession` and `actor.Page`/`actor.Element` API. The adapter is local-only (`is_local=True`, `use_cloud=False`) and no longer passes the deprecated `timeout` parameter that silently enabled cloud authentication. The bounded E2E started local Chromium, navigated to `example.com`, extracted rendered text and saved `/tmp/gaia-browser-e2e.png`.

Mem0 now uses the actual `top_k` and `filters` API and includes owner/namespace/project scope. Graphiti uses deterministic `group_id` isolation and `group_ids` searches. OpenHands now creates a temporary git baseline, sends the task through `send_message()`, runs `arun()`, captures events, runs tests and returns a diff without touching the source tree. Pipecat now creates a real `PipelineTask`/`PipelineRunner` and uses `InterruptionFrame` for barge-in.

The new `desktop_shell.py` provides tray menu, quick command window, orb states, dashboard opening, wake-word toggle and clean shutdown. `gaia_startup.py` registers user-scoped Windows HKCU autostart or XDG autostart; it never requires administrator privileges. `requirements-desktop.txt` keeps GUI/audio dependencies optional.

The new deterministic tests are `tests/v17_desktop_and_upstreams_test.py`: **8 passed, 0 failed** with the custom runner. Physical Windows microphone, tray, overlay and Android validation remain operator-dependent.
