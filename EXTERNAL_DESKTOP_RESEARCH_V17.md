# External desktop research — v1.7 final candidate

Sources consulted:

- https://github.com/PersonalJarvis/PersonalJarvis — README states Apache 2.0 for current releases and original MIT retained through 1.6.0; relevant patterns: Python/FastAPI core, desktop shell, WebSockets, event bus, central tool executor, approvals, worktree-isolated coding missions, local wake-word processing.
- https://github.com/coolmorimer/morcool-assistant — README describes a Windows-local assistant with openWakeWord, Silero VAD, faster-whisper, Piper, barge-in, tray, overlay and Windows packaging. License must be verified from the repository before copying code; GAIA only adopts patterns, not source.
- https://github.com/tamanhansalia/voice-overlay — README says MIT; Electron/React overlay, tray, global hotkey, auto-start, persistent position and pluggable speech providers. GAIA uses the UX pattern only; no source copied.
- https://github.com/Greninja110/Greninja-Personal_Assistant — README describes an offline Windows assistant with openWakeWord, faster-whisper, Kokoro, Tauri overlay, WebSocket bridge and no-cloud audio. Used as architecture reference; no source copied without an explicit compatible license.

Decision: keep GAIA Core, authority, Permission Layer and Action Host. The new desktop shell remains a client. No external source was copied into GAIA.
