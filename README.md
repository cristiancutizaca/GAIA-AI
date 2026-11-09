# GAIA-AI 2.0 — Windows Complete RC3

GAIA is a local-first resident personal assistant. This release focuses on a reproducible Windows installation, a resident Core + Desktop lifecycle, local voice, browser/coding providers, memory isolation and deterministic Windows automation while preserving GAIA's central authority model.

**Product version:** `2.0.0`  
**Release:** `2.0-WINDOWS-COMPLETE-RC3`  
**Wire protocol:** `1.0-RC6` (compatibility identifier, not the product release)

The release remains at RC3. The software has been hardened, but a genuine custom **Gaia** wake-word model and physical Windows validation are still required before calling the package FINAL.

## Fastest clean Windows setup

On Windows 11 x64 with Python 3.11 available, extract the release and run from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\Setup-GAIA.ps1
```

The wrapper selects the `full-computer` profile and prepares Desktop, Voice, Browser, Memory, Coding and deterministic Windows Computer Use. It may install Ollama and baseline voice models unless explicitly skipped. Large Ollama LLM models are never downloaded silently.

See **`GAIA_WINDOWS_INSTALL_GUIDE_2_1.md`** for the complete procedure.

## Normal resident lifecycle

```text
Windows login
  → GAIA supervisor
  → Core starts and passes /api/health
  → Desktop Shell/tray starts
  → wake/PTT/Quick Command
  → GAIA Core authority + capability routing
  → local/provider backend
  → audit/event state
  → response/TTS
```

The Dashboard is secondary. The tray/orb/voice/Quick Command are the intended daily control surfaces.

### GAIA hologram, voice and screen understanding

The resident Desktop now has an animated holographic status widget (not the former
single-color dot), a persistent **Control Center** for errors/replies, live LLM
readiness and explicit multi-monitor screen inspection using a local Ollama
vision model. Hold `Ctrl+Space` for push-to-talk. Saying or typing *“GAIA, mira
mi pantalla”* requests one monitor choice and one read-only capture; images
are not saved or used as instructions to execute actions. Install a vision model
explicitly (`ollama pull qwen2.5vl:7b`) and see
[`GAIA_DESKTOP_VISION_VOICE_GUIDE.md`](GAIA_DESKTOP_VISION_VOICE_GUIDE.md)
for configuration and honest Windows-validation limitations. Wake-by-name still
requires a genuine custom `gaia.onnx` and is not silently faked.

## Security architecture

External systems never become authority. Side effects remain under:

```text
GAIA Core
→ Capability Router / Planner
→ Authority
→ Kill Switch
→ Safe Mode
→ Permission Layer
→ ActionCoordinator / Action Host
→ provider/backend
→ verification/audit
```

Browser Use, OpenHands, Windows UI Automation, PyAutoGUI, MCP, voice and Android are providers/clients below that boundary.

## Voice status

The connected Desktop voice path in this RC is:

```text
wake or PTT
→ local microphone capture
→ /api/chat/voice
→ faster-whisper
→ normal GAIA Core chat/authority path
→ Piper
→ WAV
→ Desktop audio output
```

Silero is used for endpointing and barge-in monitoring. Production defaults are CPU-safe and do not require NVIDIA/CUDA.

Pipecat remains installed as an optional integration layer, but the generic Pipecat adapter now refuses to claim a fake production pipeline unless real processors/transports are configured.

## Wake word status

GAIA no longer substitutes a Jarvis detector and calls it “Gaia”. A real custom `gaia.onnx` is required. If it is absent, the runtime reports `CUSTOM_MODEL_MISSING` and wake mode remains fail-closed.

The release includes official-training-oriented configuration and install/verification tooling under `assets/wakeword/` and `tools/`.

## Windows Computer Use

The current deterministic order is:

1. Windows UI Automation (`pywinauto`) when a real control is addressable.
2. PyAutoGUI coordinate fallback.
3. Optional future visual-agent provider such as Agent-S or UI-TARS Desktop, not installed or falsely advertised by default.

## Useful commands

```powershell
.\.venv\Scripts\python.exe tools\gaia.py version
.\.venv\Scripts\python.exe tools\gaia_dependencies.py status --profile full-computer --strict-python
.\.venv\Scripts\python.exe tools\gaia_models.py status
.\.venv\Scripts\python.exe tools\gaia_doctor_v2.py
.\.venv\Scripts\python.exe tools\gaia_startup.py enable
.\.venv\Scripts\python.exe lumen-pc\gaia_desktop_launcher.py
```

Physical validation must be stored outside the project tree:

```powershell
.\.venv\Scripts\python.exe tools\physical_validation.py new --output-dir "$env:USERPROFILE\Documents\GAIA-Physical-Validation"
```

## Tests

Current normal pytest collection is intentionally limited to proper `test_*.py` tests. Legacy script-style regression gates remain available separately.

```text
python -m compileall -q lumen-core lumen-pc tools tests
pytest --collect-only -q
pytest -q
```

The repair report also records critical legacy regression scripts for Authority, Core E2E, Security, Kill Switch, permission levels, memory security and voice permissions.

## Current documents

- `GAIA_PROGRESO.md` — audit, memory, Reflex, measured timings and remaining Windows checks.

- `GAIA_FINAL_REPAIR_REPORT_2_1.md` — exact repair/reality report.
- `GAIA_DEPENDENCY_AUDIT.md` — dependency/profile audit.
- `GAIA_WINDOWS_INSTALL_GUIDE_2_1.md` — clean Windows installation and physical-validation path.
- `release_manifest.json` — canonical release metadata.
- `gaia_dependencies.toml` — canonical optional dependency/profile manifest.

Older “GAIA_FINAL_*” reports from previous Manus runs were moved under `reports/history/pre-windows-complete-rc1/` so they cannot be mistaken for current reality. The old RC6 README is preserved at `reports/history/README_RC6.md`.

## RC3 dependency isolation

Full/Full-Computer now uses four environments by design: `.venv` (GAIA Core/Desktop/Voice/Computer Use on 3.11), `.venv-browser` (Browser Use 3.11), `.venv-memory` (Mem0 3.11) and `.venv-coding` (OpenHands 3.12). This prevents Browser Use exact pins from mutating Core/Voice dependencies, avoids the Browser Use/Mem0 PostHog conflict, and satisfies OpenHands' Python >=3.12 requirement. See `GAIA_RC3_DEPENDENCY_ISOLATION.md`.
