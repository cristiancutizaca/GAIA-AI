# GAIA 2.0 Windows Complete RC1 — repair report

## Result

This repository is now identified as **GAIA 2.0.0 / `2.0-WINDOWS-COMPLETE-RC2`**. It is intentionally **not** labelled FINAL because two classes of evidence are still missing: a genuine trained/provided `Gaia` wake model and physical validation on the target Windows PC. The optional Pipecat realtime transport is also truthfully `CONFIG_REQUIRED`; the actually connected Desktop voice path uses `/api/chat/voice`.

## Major repairs completed

### Clean install and dependencies

- Added canonical `gaia_dependencies.toml` shared by installer/Doctor/dependency tooling.
- Made `full` include Desktop + Voice + Browser + Memory + Coding.
- Added `full-computer` for Windows UI Automation + PyAutoGUI.
- Added/repaired Desktop, Voice, Computer and isolated Graphiti requirement groups.
- Removed unused `smolagents` from the Coding install group because production code does not import it.
- Removed mandatory legacy `openai-whisper`/Edge TTS from normal Core installation; legacy fallbacks remain optional.
- Aligned duplicate `sounddevice`/`pywinauto` constraints across Windows/Desktop requirements.
- Added `Setup-GAIA.ps1` for one-command Windows setup.
- Browser/Full setup installs a Chromium runtime.
- Ollama installation is explicit; large LLM downloads remain explicit.
- Added a model manager for faster-whisper and Piper voice assets.
- Added fail-closed post-install feature activation.

### Resident Desktop

- Fixed PySide6 class-scope errors in the Desktop shell.
- Added real Win32 global hotkey registration rather than a display-only `REGISTERED` state.
- Added actual PTT capture that finalizes a WAV and dispatches it into the voice path.
- Added cancellable local audio playback.
- Added Qt signal bridge so worker/SSE/audio callbacks do not directly mutate widgets from background threads.
- Quick Command Core calls now run off the Qt GUI thread.
- Core SSE events drive Orb/tray states.
- Wake events show the Orb and enter listening state.
- Added supervised Core restart protocol.
- Launcher now uses a Windows named mutex to prevent normal duplicate resident instances.

### Voice

- Default STT is `faster-whisper`, CPU-safe `int8` by default.
- Default TTS is local Piper, invoked as a separate process and backed by explicit voice-model setup.
- `es_MX-claude-high` is the default Spanish voice selection.
- Wake processing uses openWakeWord with PCM `int16` 80 ms chunks rather than two-second normalized-float polling.
- Post-wake endpointing uses streaming Silero VAD.
- Voice session can continue for another turn without repeating the wake phrase.
- Added automatic barge-in monitor while speaker playback is active; it stops playback, emits interrupted state and returns to listening.
- Removed fake Pipecat six-stage classes that did no frame processing. The adapter now refuses to claim a production pipeline unless real processors/transports are supplied.

### Wake word

- No Jarvis detector is silently used as Gaia.
- Missing custom model is reported as `CUSTOM_MODEL_MISSING`.
- Added official-training-oriented configuration/preparation tooling.
- Release builder explicitly preserves `assets/wakeword/gaia.onnx` if a genuine model is later installed/trained.
- No unverified third-party wake model is bundled.

### Browser

- Removed unconditional `/usr/bin/chromium` launch path.
- Added `GAIA_BROWSER_EXECUTABLE` override and cross-platform Chrome/Edge/Chromium discovery.
- If no explicit executable is found, Browser Use is allowed to manage its browser instead of being forced to a Linux path.

### Memory and coding

- Mem0 update/delete verify existing owner/namespace/project before mutation and fail closed when ownership cannot be proven.
- Graphiti remains isolated/optional and requires explicit Neo4j configuration.
- OpenHands remains a real isolated worker using `send_message()`/`arun()`, `sys.executable`, tests and diff before any apply action.

### Computer Use

- Current coordinate backend is honestly `PyAutoGUIComputerUseBackend`, not presented as real UI-TARS.
- Added deterministic Windows UI Automation provider using pywinauto.
- Added `WindowsComputerUseRouter`: UI Automation first, PyAutoGUI coordinate fallback second.
- Agent-S/UI-TARS Desktop remain optional future visual providers; they are not falsely advertised as integrated.

### Tests and validation

- Added `pytest.ini` so ordinary pytest collects proper `test_*.py` tests instead of executing old script-style regressions at import time.
- Added behavioral runtime closure tests.
- `pytest --collect-only -q`: PASS, 12 tests collected.
- `pytest -q`: PASS, 12/12.
- Critical legacy/regression scripts after the repair:
  - v20 release contract: PASS
  - global authority: PASS
  - Core API E2E: PASS
  - security regression: PASS
  - Kill Switch: PASS
  - permission levels: PASS
  - DeepSeek Harness fallback: PASS
  - memory security matrix: PASS
  - voice permissions: PASS
- Replaced the active RC6 physical validator with a 30-check GAIA 2.0 operator ledger. A smoke-created ledger validates internally but correctly starts with all checks `PENDING`.

## Current production/RC architecture

### Normal Desktop voice path

`wake or PTT → local audio capture → /api/chat/voice → faster-whisper → normal GAIA Core chat/authority path → Piper WAV → Desktop AudioPlayer`

Silero performs endpointing/barge-in. This path is connected in source and can be exercised on Windows once dependencies/models/hardware are present.

### Optional Pipecat

Pipecat is installed by the Voice profile but the generic adapter does **not** pretend to be a finished production realtime graph. It reports configuration required until actual processors/transports are supplied. This avoids the previous false `Pipeline([six classes with pass])` status.

## External implementation references evaluated

No external project replaced GAIA Core or its authority model, and no external source code was copied as part of this repair.

- **Morcool Assistant:** useful Windows resident voice behavior reference: wake, VAD, faster-whisper, Piper, tray/orb, PTT, barge-in.
- **Microsoft UFO²:** useful deterministic Windows UI Automation/Win32/COM architecture reference.
- **Agent-S / UI-TARS Desktop:** retained as optional visual-computer-use candidates rather than default dependencies.
- **openWakeWord:** official custom-model workflow is the basis for the Gaia training configuration.
- **faster-whisper:** production STT default; CPU path does not require NVIDIA/CUDA.
- **Piper:** local TTS process/runtime. Current Piper implementation is GPLv3; it is installed externally and invoked as a subprocess, not copied into this release. Voice model licensing/provenance remains separately governed by its model card.

## Truthful remaining blockers

1. **Genuine Gaia wake model:** no verified redistributable `gaia.onnx` was available in this build environment. Runtime fails closed rather than substituting Jarvis. It must be trained/provided and then physically calibrated.
2. **Physical Windows validation:** tray, global hotkeys, microphone, speaker, real wake accuracy, no-focus Orb behavior, barge-in latency, multi-monitor placement and real Windows UI automation must be confirmed on the target machine.
3. **Clean Windows install execution:** installer logic and manifests are repaired, but this Linux build container cannot prove the entire PowerShell/winget/Windows wheel installation path. That is the first target-PC validation item.
4. **Pipecat realtime graph:** optional adapter remains `CONFIG_REQUIRED`; the connected Desktop voice path is `/api/chat/voice` as documented above.
5. **Graphiti:** external Neo4j/provider configuration remains optional; SQLite/GAIA fallback memory paths remain available.
6. **Large local LLMs:** intentionally not downloaded automatically. Ollama/model choice remains an explicit user setup decision.

## Release decision

**RC1 is appropriate. FINAL is not.** The remaining blockers are now explicit rather than hidden behind fake integration labels. The next phase is deployment on the clean Windows PC, installing the Full-Computer profile, providing/training the Gaia wake model, and completing the physical validation ledger.
