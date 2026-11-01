# GAIA Final Reality Matrix

| Component | Status | Backend | Production connected | Permission protected | Kill Switch | Safe Mode | Unit | Integration | Public E2E | Physical validation | Blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Core | REAL_E2E_INTEGRATION | FastAPI/PlatformRuntime | yes | yes | yes | yes | PASS | PASS | PASS | no | none |
| Desktop Shell | REAL_IMPLEMENTATION_PHYSICAL_VALIDATION_PENDING | PySide6/LumenDesktopAPI | yes | delegated to Core | yes via Core | yes via Core | PASS | PASS | automated | required | Windows GUI |
| Tray/Orb | REAL_IMPLEMENTATION_PHYSICAL_VALIDATION_PENDING | QSystemTrayIcon/QWidget | yes | client only | yes | yes | PASS | automated | pending | required | PySide6/display |
| Quick Command | REAL_E2E_INTEGRATION | HTTP Core API | yes | Core | yes | yes | PASS | PASS | PASS | no | none |
| Wake Word/Mic | REAL_IMPLEMENTATION_PHYSICAL_VALIDATION_PENDING | openWakeWord/sounddevice | configured | Core voice route | yes | yes | PASS | automated | pending | required | audio hardware |
| Silero/Pipecat/STT/TTS | REAL_IMPLEMENTATION_PHYSICAL_VALIDATION_PENDING | real lazy providers | configured | Core | yes | yes | PASS | PASS | pending | required | providers/audio |
| Barge-in | REAL_IMPLEMENTATION_PHYSICAL_VALIDATION_PENDING | InterruptionFrame/process termination | yes | Core | yes | yes | PASS | automated | pending | required | audio |
| Browser Use | REAL_E2E_INTEGRATION | BrowserSession + Chromium | yes local | Core capability | yes | yes | PASS | PASS | PASS | Windows pending | target Chromium |
| HTTP browser fallback | REAL_E2E_INTEGRATION | SSRF-hardened HTTP | yes | Core capability | yes | yes | PASS | PASS | PASS | no | none |
| SQLite Memory | REAL_E2E_INTEGRATION | owner/namespace SQLite | yes | yes | yes | yes | PASS | PASS | PASS | no | none |
| Mem0 | FUNCTIONAL_OPTIONAL_BACKEND | mem0ai | config required | scope metadata | yes | yes | PASS | pending | pending | no | config/credentials |
| Graphiti | FUNCTIONAL_OPTIONAL_BACKEND | graphiti-core/Neo4j | config required | group isolation | yes | yes | PASS | pending | pending | no | Neo4j |
| MCP | REAL_E2E_INTEGRATION | stdio/HTTP manager | yes | allowlist/Core | yes | yes | PASS | PASS | PASS | no | none |
| OpenHands | FUNCTIONAL_OPTIONAL_BACKEND | OpenHands SDK | config required | approval/workspace | yes | yes | PASS | pending | pending | no | model/API |
| Workers | REAL_E2E_INTEGRATION | WorkerManager/Planner | yes | Core | yes | yes | PASS | PASS | PASS | no | none |
| Computer Use | BLOCKED_BY_ENVIRONMENT | UI-TARS boundary | no | designed | yes | yes | PASS | safe blocked | pending | required | display/dependency |
| Visualizer | AUTOMATED_ONLY | HTTP/SSE consumer | yes | read-only | yes | yes | PASS | PASS | PASS | no | none |
| Android | REAL_IMPLEMENTATION_PHYSICAL_VALIDATION_PENDING | Flutter pairing source | partial | pairing/Core | yes | yes | PASS | contract | pending | required | SDK/device |
| Automations | REAL_E2E_INTEGRATION | persistent scheduler | yes | ownership/risk | yes | yes | PASS | PASS | PASS | no | none |
| Backup/Updater | REAL_E2E_INTEGRATION | BackupManager/installer contracts | yes | Core | yes | yes | PASS | PASS | PASS | Windows pending | operator run |
