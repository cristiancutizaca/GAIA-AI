# GAIA dependency audit 2.1

## Baseline findings

The previous archive shipped optional requirement files without installing them consistently. `Full` omitted the resident Desktop profile; Computer Use imported `pyautogui` without declaring it; Graphiti was described in the memory profile but intentionally not installed; Windows secret storage could use `keyring` without declaring it; Playwright could be installed without a Chromium runtime; Piper and the Gaia wake model were external assumptions.

## Changes in this repair

- Added canonical `gaia_dependencies.toml`.
- `Full` now includes Desktop + Voice + Browser + Mem0 + Coding.
- Added `full-computer` profile with PyAutoGUI/UIA dependencies.
- Added `keyring`, `soundfile`, `faster-whisper`, `piper-tts`, `pyautogui` and explicit `pywinauto` declarations.
- Full/Browser installation runs `python -m playwright install chromium`.
- Added optional `-InstallOllama`; large LLM models are never downloaded silently.
- Split Graphiti into `requirements-memory-graphiti.txt` because it requires Neo4j and may need dependency/process isolation.
- Added `gaia dependencies status` / `tools/gaia_dependencies.py`.
- GAIA wake word remains fail-closed until a real Gaia ONNX model is trained/installed. A training template is included; no Jarvis model is substituted.

## Runtime repairs

- Real Win32 `RegisterHotKey` message loop with hold-release detection.
- PTT capture now produces a WAV and sends it to the existing Core voice route.
- Desktop background work reaches Qt via Signals rather than touching widgets from worker threads.
- Quick Command network calls no longer block the GUI thread.
- Voice responses are downloaded and played through a single cancellable SoundDevice/SoundFile player.
- Default local voice path prefers faster-whisper (CPU INT8) and Piper; legacy OpenAI Whisper and Edge TTS remain fallback-compatible.
- Windows launcher uses a named mutex and restart exit protocol to restart an owned Core plus Shell.
- PyAutoGUI is named honestly; Windows UI Automation is a separate deterministic provider.
- Fake Pipecat `pass` stages were removed. Pipecat refuses to report a production pipeline unless real processors are supplied; the currently working desktop path is the Core voice endpoint.

## Still requiring external/physical work

- A trusted acoustic `gaia.onnx` is not bundled because no independently licensed, verified model was available without sign-in/training.
- Microphone/speaker/hotkey/barge-in behavior must be validated on the target Windows PC.
- Graphiti requires an actual Neo4j deployment/configuration.
- Visual Agent-S/UI-TARS providers are not installed by default; deterministic UIA + PyAutoGUI are the baseline.
