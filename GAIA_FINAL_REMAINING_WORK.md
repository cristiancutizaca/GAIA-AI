# GAIA v2.0 — Remaining Work

Only physical, credential or external-service validation remains. These are not software stubs and none permits bypassing the Permission Layer or Action Host.

| Item | Exact missing part | Why / blocker | Attempted | Affected files | Exact next step |
|---|---|---|---|---|---|
| Windows desktop physical validation | PENDING_PHYSICAL_VALIDATION: validate PySide6 tray, overlay, focus behavior, autostart and clean exit | Sandbox has no Windows GUI or PySide6 | Resident launcher, shell lifecycle, generated tray icon and Core client implemented | `lumen-pc/gaia_desktop_launcher.py`, `lumen-pc/desktop_shell.py`, `tools/gaia_startup.py` | Run the Windows checklist with a logged-in desktop and confirm no terminal remains open |
| Voice hardware validation | PENDING_PHYSICAL_VALIDATION: microphone capture, wake word, VAD, barge-in and TTS playback | No microphone/audio device in Sandbox | Wake listener, VAD wrapper, STT/TTS API and barge-in paths implemented | `lumen-pc/wake_word.py`, `lumen-core/gaia_platform/real_backends.py` | Install Windows voice requirements and execute the audio checklist |
| External service execution | Live Mem0, Neo4j/Graphiti and OpenHands runs with configured service credentials | Credentials/services are unavailable; fail-closed behavior is intentional | Lazy real adapters, ownership/group scopes and isolated OpenHands workspace implemented | `lumen-core/gaia_platform/real_backends.py` | Configure explicit credentials and run deployment E2E |
| Computer Use | Real UI-TARS execution on a physical display | No physical GUI and dependency not installed | Provider boundary, health and safe blocked result implemented | `lumen-core/gaia_platform/real_backends.py` | Validate on Windows with UI-TARS and explicit authority grant |
| Android | APK build, pairing and device transport | No Android SDK/device in Sandbox | Source and pairing contracts retained | `lumen-mobile/`, `lumen-pc/desktop_api.py` | Run Android build/on-device checklist |

No solved v1.6/v1.7 issue is listed here. These are physical, credential or external-service requirements, not missing core implementation claims.
