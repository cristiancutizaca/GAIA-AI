# GAIA Final Desktop Report

Status: `AUTOMATED_ONLY` / `REAL_IMPLEMENTATION_PHYSICAL_VALIDATION_PENDING`.

The shell now creates a real Core client by default, uses the unified `127.0.0.1:8090` URL, owns the quick-command window, generates a non-empty tray icon, shows the orb according to `GAIA_ORB_MODE`, and stops/restarts the wake listener when microphone state changes. Tray actions are wired to Core or local lifecycle methods; authority remains in Core. Windows tray, multi-monitor placement, focus and physical rendering still require Windows validation.
