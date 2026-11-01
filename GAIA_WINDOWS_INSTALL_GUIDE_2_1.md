# GAIA 2.0 Windows clean-install guide

**Build:** `2.0-WINDOWS-COMPLETE-RC2`  
**Recommended OS:** Windows 11 x64  
**Python:** 3.11 x64

This release is intentionally an RC until the real Gaia wake model and the physical Windows validation ledger are completed.

## 1. Clean installation

Extract GAIA to a normal user-owned directory. From PowerShell in the extracted folder run:

```powershell
powershell -ExecutionPolicy Bypass -File .\Setup-GAIA.ps1
```

The wrapper selects `full-computer`, generates a strong Core secret, installs the Desktop/Voice/Browser/Memory/Coding/Computer profiles, installs Chromium, optionally installs Ollama, and downloads the baseline faster-whisper + Piper voice assets.

Useful switches:

```powershell
.\Setup-GAIA.ps1 -SkipOllama
.\Setup-GAIA.ps1 -SkipModels
.\Setup-GAIA.ps1 -SkipBrowserRuntime
```

For a smaller profile use the lower-level installer, for example:

```powershell
.\install-gaia.ps1 -Profile desktop -GenerateSecret
.\install-gaia.ps1 -Profile full -GenerateSecret -InstallOllama -InstallModels
```

Large Ollama LLM models are never downloaded silently.

## 2. Check dependencies and models

```powershell
.\.venv\Scripts\python.exe tools\gaia_dependencies.py status --profile full-computer --strict-python
.\.venv\Scripts\python.exe tools\gaia_models.py status
.\.venv\Scripts\python.exe tools\gaia_doctor_v2.py
```

The expected wake-word state on this RC is `CUSTOM_MODEL_MISSING` until a genuine Gaia model is installed.

## 3. Gaia wake word

Do **not** use or rename a Jarvis model. Install a custom model only when its provenance/hash is known:

```powershell
.\.venv\Scripts\python.exe tools\setup_gaia_wakeword.py C:\path\to\gaia.onnx --sha256 EXPECTED_SHA256
```

The repository includes `assets\wakeword\gaia_training.yml` and preparation tooling for the official openWakeWord custom-training workflow. Once installed, `assets\wakeword\gaia.onnx` is explicitly preserved by the release builder.

## 4. Start GAIA now

For a one-time foreground test:

```powershell
.\.venv\Scripts\python.exe lumen-pc\gaia_desktop_launcher.py
```

The supervisor starts Core first, waits for `/api/health`, then launches the resident Desktop shell.

## 5. Start GAIA automatically at Windows login

```powershell
.\.venv\Scripts\python.exe tools\gaia_startup.py enable
.\.venv\Scripts\python.exe tools\gaia_startup.py status
```

Disable it with:

```powershell
.\.venv\Scripts\python.exe tools\gaia_startup.py disable
```

## 6. Physical validation

Store physical evidence **outside** the GAIA project directory:

```powershell
.\.venv\Scripts\python.exe tools\physical_validation.py new --output-dir "$env:USERPROFILE\Documents\GAIA-Physical-Validation"
```

The generated ledger covers tray, Orb, no-focus behavior, Quick Command/PTT hotkeys, microphone, speakers, Gaia wake detection, false positives, Silero, Spanish STT/TTS, barge-in, multi-turn conversation, Browser Use, OpenHands, UIA/PyAutoGUI, Safe Mode, Kill Switch, restart, login startup, clean exit, multi-monitor, Ollama/GPU and optional Android pairing.

A physical PASS must be explicitly confirmed with evidence; the tool never auto-promotes the release.

## 7. Voice architecture in this RC

The working Desktop voice path is:

`wake/PTT → local capture → /api/chat/voice → faster-whisper → normal GAIA Core authority/chat path → Piper → WAV → Desktop audio player`.

Silero performs post-wake endpointing and barge-in monitoring. The optional Pipecat adapter no longer claims a fake six-stage realtime pipeline: it reports `CONFIG_REQUIRED` until real Pipecat processors/transports are provided. This is deliberate truthfulness, not a hidden failure.

## 8. Computer Use

Windows control is deterministic-first:

1. Windows UI Automation / pywinauto when a real control can be addressed.
2. PyAutoGUI coordinate fallback when necessary.
3. Agent-S/UI-TARS remain optional future visual-agent providers; neither is falsely advertised as integrated in this RC.

All interactive actions remain below GAIA Authority, Safe Mode, Kill Switch, Permission Layer and Action Host.

## 9. Repair

The installer is designed to be rerunnable. Re-running the same profile repairs missing Python dependencies without deleting GAIA user data. Back up any important `.env`, memory/project data and local models before major manual changes.

## 10. Current RC blockers before `FINAL`

- Genuine custom `Gaia` wake model still needs to be trained/provided and physically calibrated.
- Physical Windows mic/speaker/hotkey/orb/multi-monitor/barge-in validation is pending.
- Pipecat realtime transport remains optional/config-required; the Desktop voice path above is the actual connected production path for this RC.
- External Graphiti/Neo4j is optional and requires its own service/configuration.
