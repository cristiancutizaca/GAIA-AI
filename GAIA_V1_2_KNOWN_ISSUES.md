# GAIA v1.2 known issues

- Browser backend is a safe functional HTTP reader; rendered browser, JavaScript and real Browser Use execution require optional dependency/physical validation.
- Voice state machine and barge-in cancellation are functional contracts, but real STT/TTS/audio devices are not validated.
- Scheduler is functional in-process but not yet a persistent daemon.
- Secret Manager needs Windows Credential Manager/Linux Secret Service or keyring; plaintext fallback is intentionally disabled.
- Computer Use remains disabled and scaffold-only.
- Android, LiveKit, Graphiti and external OpenHands execution remain optional/pending.
- The v1.1 baseline ZIP had a lost executable bit on Android `gradlew`; the v1.2 working tree and release builder correct it without modifying the immutable checkpoint.
