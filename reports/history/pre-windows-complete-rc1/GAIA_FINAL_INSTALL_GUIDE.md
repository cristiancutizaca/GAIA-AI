# GAIA Final Install Guide

On Windows 10/11 with Python 3.11, open PowerShell in the extracted directory and run `Set-ExecutionPolicy -Scope Process Bypass`, then `./install-gaia.ps1` (or install the Core and Desktop requirements separately). Copy `.env.example` to `.env`, set a long private `LUMEN_SECRET`, then run `python tools/gaia_doctor.py --json`.

First start is `python tools/gaia_startup.py enable`, followed by `python -m uvicorn main:app --host 127.0.0.1 --port 8090` from `lumen-core` and `python lumen-pc/desktop_shell.py` from the product root. Production packaging should launch the Core supervisor and shell without a terminal window.

Rollback: stop Core and shell, copy the user vault/backups aside, remove the candidate directory, restore the previous extracted release, restore `.env` manually, and run Doctor. GAIA backups are validated before restore; do not overwrite a live database without a verified backup.
