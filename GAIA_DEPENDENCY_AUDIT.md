# GAIA 2.0 dependency audit

**Release:** `2.0-WINDOWS-COMPLETE-RC2`  
**Target runtime:** Windows 11 x64, Python 3.11, local-first.

This audit is derived from the current source tree and the canonical `gaia_dependencies.toml`. The installer resolves optional profile files through that manifest so Doctor, setup and installation no longer need separate handwritten profile lists.

## Installation profiles

| Profile | Purpose | Optional requirement groups |
|---|---|---|
| `minimal` | Core + CLI | none |
| `desktop` / `standard` | Resident desktop shell | desktop |
| `voice` | Desktop + local voice | desktop, voice |
| `browser` | Web automation | browser |
| `memory` | Mem0 | memory |
| `coding` | OpenHands/smolagents tooling | coding |
| `computer` | Desktop + deterministic computer control | desktop, computer |
| `full` | Normal complete GAIA without computer control | desktop, voice, browser, memory, coding |
| `full-computer` | Recommended Windows complete profile | desktop, voice, browser, memory, coding, computer |
| `development` / `all` | Developer/full integration profile | same groups as full-computer |

`lumen-core/requirements.txt` is always installed. Non-minimal Windows profiles also install the PC and Windows base requirements.

## Canonical components

| Component | Distribution / runtime | Import / probe | Profile | Extra runtime requirement | Current policy |
|---|---|---|---|---|---|
| Desktop UI | PySide6 | `PySide6` | desktop | Windows interactive user session | Required for resident shell |
| Windows hotkeys | pywin32 / Win32 | `win32api`, direct `RegisterHotKey` in shell | desktop | Windows | Real OS registration; not a fake status |
| Audio capture/output | sounddevice + soundfile + NumPy | `sounddevice`, `soundfile`, `numpy` | desktop | physical mic/speaker | CPU-safe baseline |
| Wake word | openWakeWord | `openwakeword` | desktop | real `gaia.onnx` | Fail-closed if model absent; no Jarvis substitution |
| VAD | silero-vad | `silero_vad` | voice | model loaded by package | Used for post-wake endpointing/barge-in |
| STT | faster-whisper | `faster_whisper` | voice | selected Whisper model cache | Default CPU `int8`; legacy Whisper is optional only |
| TTS | Piper | `piper` | voice | Spanish voice ONNX + JSON | Local subprocess; model manager downloads chosen voice |
| Browser | Browser Use + Playwright | `browser_use`, `playwright` | browser/full | Chromium runtime | Installer runs Playwright Chromium setup; adapter no longer hardcodes Linux Chromium |
| Mem0 | mem0ai | `mem0` | memory/full | explicit config as needed | Owner/namespace/project scoping; fail-closed mutation checks |
| Graphiti | graphiti-core | `graphiti_core` | isolated | Neo4j + LLM/embedder config | Separate optional environment/service; not silently enabled |
| Coding | OpenHands SDK | `openhands.sdk` | coding/full | model/backend + Git | Isolated workspace + diff/apply authority |
| Coordinate computer fallback | PyAutoGUI | `pyautogui` | computer/full-computer | Windows desktop | Honest deterministic fallback |
| Windows UI automation | pywinauto | `pywinauto` | computer/full-computer | Windows desktop | Preferred before coordinate clicks |
| Secret storage | keyring | `keyring` | desktop | Windows Credential Manager backend | No plaintext secret fallback in GAIA security model |
| Local LLM | Ollama | process/API probe | external | Ollama + explicit model | Optional installer flag; large LLMs are never silently downloaded |

## Changes made from the reviewed archive

- `full` now actually includes Desktop + Voice + Browser + Memory + Coding.
- `full-computer` includes deterministic Windows UI automation and PyAutoGUI.
- `requirements-computer.txt` now declares the packages its backend imports.
- Desktop dependencies are installed by Full instead of merely being shipped in the ZIP.
- `sounddevice` and `pywinauto` version constraints were aligned across base/Desktop/Computer requirement files to avoid install-order drift.
- Graphiti received a separate requirements file because it is an external/isolated deployment rather than something GAIA should pretend is usable just because the source adapter exists.
- `keyring` is declared for the Windows secret-store path.
- Browser setup installs a Chromium runtime in Browser/Full profiles.
- Unused `smolagents` was removed from the Coding install group because GAIA does not import it in the current production path.
- Production STT is `faster-whisper`; old `openai-whisper` and Edge TTS moved to `requirements-voice-legacy.txt` and are not installed by normal Full.
- Production TTS is local Piper; the model manager explicitly downloads/verifies a Spanish voice instead of assuming the model already exists.
- Wake word is truthful: `Gaia` requires a custom Gaia model. The release builder allows exactly `assets/wakeword/gaia.onnx` if one has been trained/provided, but does not bundle an unverified third-party model.

## External software/models that still require explicit setup or operator consent

1. **Ollama:** can be installed with the setup flag, but large LLM models are never downloaded implicitly.
2. **Gaia wake model:** no verified redistributable model is bundled. The training/config tooling is included; runtime remains `CUSTOM_MODEL_MISSING` until a genuine model is installed.
3. **Piper Spanish voice:** `gaia models install baseline` downloads the selected voice and STT model explicitly.
4. **Graphiti/Neo4j:** optional isolated service; not enabled without service credentials/configuration.
5. **Physical audio/Windows desktop:** packages can be installed automatically, but hardware behavior must be validated on the target PC.

## Clean-install gate

The repository now has a one-command Windows wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File .\Setup-GAIA.ps1
```

It requests `full-computer`, generates a strong Core secret, installs Ollama unless skipped, installs baseline voice models unless skipped, installs Chromium unless skipped, runs fail-closed feature activation, dependency status and Doctor. A clean Windows execution is still an operator/physical validation item because this build environment is not Windows.
