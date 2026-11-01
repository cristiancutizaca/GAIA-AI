# GAIA Final Windows Report

Status: `REAL_IMPLEMENTATION_PHYSICAL_VALIDATION_PENDING`.

Windows-specific startup writes HKCU Run using the active `sys.executable` (or explicit `GAIA_PYTHON`), while Linux uses XDG autostart. The shell and installer contracts are present, and no terminal is required by the intended packaged launcher. Required operator checks are tray presence, Core health, orb rendering, microphone privacy, wake word, close-to-tray, restart and clean exit. Sandbox cannot perform these GUI/audio checks.
