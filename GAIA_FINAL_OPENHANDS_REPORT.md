# GAIA Final OpenHands Report

Status: `FUNCTIONAL_OPTIONAL_BACKEND` / external execution pending.

The coding worker copies work into an isolated workspace, requires approval before execution, initializes a disposable Git repository, uses `sys.executable` for validation and never edits the original source directly. The installed SDK/API and model credentials are deployment-specific; without them it fails closed with `CONFIG_REQUIRED` or `BLOCKED_BY_EXTERNAL_REQUIREMENT`.
