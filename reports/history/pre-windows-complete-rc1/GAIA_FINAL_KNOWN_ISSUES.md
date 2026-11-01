# GAIA Known Issues

1. Optional browser automation, Computer Use, Android physical flow and real-time voice are not fully physically validated in Sandbox.
2. Whisper, Edge TTS, FFmpeg, GUI packages, external graph/vector stores and OpenHands are optional and not bundled.
3. Planner classification is deterministic and conservative; it is not an LLM planner.
4. Project/job stores are local SQLite, not distributed.
5. Safe Mode is read-only for effects and is evaluated from startup configuration.
6. External integrations require explicit feature flags, allowlists, credentials and operator tests.
7. PySide6, microphone hardware, Windows GUI, Android SDK/device and UI-TARS model/display are deployment requirements, not Sandbox guarantees.
8. Mem0 requires explicit `MEM0_CONFIG_JSON` or a local `Memory.from_config` configuration; the code does not silently use a cloud service.
9. Graphiti requires Neo4j URI and credentials; local SQLite memory remains the fallback.

## Resolved in v1.7

The previous Browser Use blocker was partly environmental and partly adapter configuration. The installed API treats the deprecated `timeout` argument as a cloud timeout. The adapter now avoids that argument and explicitly forces local Chromium; the bounded public E2E passed launch, rendered read and screenshot. Mem0 now uses actual `filters` and `top_k`; Graphiti uses scoped `group_ids`; OpenHands uses `send_message()`/`arun()` and a temporary git workspace; Pipecat uses real `PipelineTask`/`PipelineRunner` and `InterruptionFrame`.

The new regression suite passed **8/8**. Physical validation remains intentionally separate and is not promoted to PASS by import or unit evidence.
