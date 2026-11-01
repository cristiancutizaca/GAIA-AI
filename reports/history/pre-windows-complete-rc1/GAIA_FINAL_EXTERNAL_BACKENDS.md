# GAIA Final External Backends

## Status labels

- `REAL_IMPLEMENTATION_PHYSICAL_VALIDATION_PENDING`: provider is wired through GAIA and the real dependency is used, but hardware/service validation remains.
- `FUNCTIONAL_OPTIONAL_BACKEND`: implementation and health/lazy loading exist; activation requires optional configuration.
- `BLOCKED_BY_EXTERNAL_REQUIREMENT`: real attempt made but an external service, model, or compatible isolated environment is required.
- `BLOCKED_BY_ENVIRONMENT`: the Sandbox cannot provide the physical GUI/audio/device requirement.

| Backend | Status | Production path | Public E2E | Exact blocker |
|---|---|---|---|---|
| Browser Use 0.13.10 | REAL_IMPLEMENTATION_PHYSICAL_VALIDATION_PENDING | `PlatformRuntime.browser` when `GAIA_FEATURE_BROWSER=true` | local rendered-browser test is prepared; Chromium install/display pending | Browser Use model/action runtime and Chromium must be installed |
| Pipecat 1.12.0 | FUNCTIONAL_OPTIONAL_BACKEND | `PlatformRuntime.voice_provider` lazy pipeline | pipeline construction test | transport/STT/TTS/audio device wiring requires provider and hardware |
| Silero VAD 6.2.3 | REAL_IMPLEMENTATION_PHYSICAL_VALIDATION_PENDING | `SileroVADBackend.detect_file` | fixture test when model can download | torch/model/audio fixture and physical input |
| Local STT Whisper | FUNCTIONAL_OPTIONAL_BACKEND | existing GAIA voice path | existing audio contract | model weights and FFmpeg |
| Local TTS Piper | FUNCTIONAL_OPTIONAL_BACKEND | `LocalTTSBackend` | health/failure test | piper binary and voice model |
| Mem0 2.2.1 | BLOCKED_BY_EXTERNAL_REQUIREMENT | `Mem0MemoryProvider` when configured | provider contract and failure E2E | dependency graph conflicts with Browser Use in global env; isolated Mem0 env and explicit local config required |
| Graphiti 0.30.2 | BLOCKED_BY_EXTERNAL_REQUIREMENT | `GraphitiMemoryProvider` when configured | health/config tests | Neo4j plus embedding/LLM service unavailable |
| OpenHands SDK 1.52.0 | BLOCKED_BY_EXTERNAL_REQUIREMENT | `OpenHandsCodingWorker` isolated workspace boundary | workspace safety E2E; actual agent pending | SDK agent/model runtime must be installed/configured |
| UI-TARS 0.5.1 | BLOCKED_BY_ENVIRONMENT | `UITARSComputerUseBackend` authority boundary | simulated safe block E2E | no physical display/model runtime in Sandbox |
| LiveKit Agents | BLOCKED_BY_EXTERNAL_REQUIREMENT | not enabled; no material need over secure WebSocket baseline | none | not required for local Core; external realtime service/credentials |

All external content remains `EXTERNAL_UNTRUSTED`. No provider can bypass Global Authority, Safe Mode, Kill Switch, Permission Layer, Preflight or Action Host.


## Required explicit rows

| Backend | Version / use | Status | Exact blocker |
|---|---|---|---|
| smolagents | 1.26.0 listed as optional; not used as GAIA authority | NOT CONNECTED / optional | no need to add a second planner authority; use only inside an isolated worker after explicit design approval |
| Agent-S/UI-TARS | UI-TARS 0.5.1 optional; Agent-S not available as an installed provider | BLOCKED_BY_ENVIRONMENT | physical display and model runtime unavailable; no fake implementation substituted |
| LiveKit | not used | NOT CONNECTED | existing secure local/WebSocket transport is sufficient for this release; LiveKit service/credentials were not authorized |
