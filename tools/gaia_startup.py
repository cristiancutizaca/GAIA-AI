#!/usr/bin/env python3
"""Enable GAIA at user login (never a privileged Windows service)."""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "GAIA Desktop Assistant"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART = Path.home() / ".config" / "autostart" / "gaia.desktop"


def _python_path() -> Path:
    override = os.environ.get("GAIA_PYTHON", "").strip()
    if override:
        interpreter = Path(override).expanduser()
    elif platform.system() == "Windows":
        preferred = ROOT / ".venv" / "Scripts" / "pythonw.exe"
        interpreter = preferred if preferred.exists() else ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        preferred = ROOT / ".venv" / "bin" / "python"
        interpreter = preferred if preferred.exists() else Path(sys.executable)
    if platform.system() == "Windows" and interpreter.name.lower() == "python.exe":
        silent = interpreter.with_name("pythonw.exe")
        if silent.exists():
            interpreter = silent
    return interpreter


def command() -> str:
    interpreter = _python_path()
    launcher = ROOT / "lumen-pc" / "gaia_desktop_launcher.py"
    return f'"{interpreter}" "{launcher}"'


def _check_installation() -> None:
    if not _python_path().is_file():
        raise FileNotFoundError("Falta el Python de GAIA (.venv); ejecuta install-gaia.ps1 antes de activar autostart.")
    if not (ROOT / "lumen-pc" / "gaia_desktop_launcher.py").is_file():
        raise FileNotFoundError("No se encuentra el launcher de GAIA.")


def enable() -> dict:
    _check_installation()
    launch = command()
    if platform.system() == "Windows":
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
            winreg.SetValueEx(key, "GAIA", 0, winreg.REG_SZ, launch)
        return {"status": "ENABLED", "scope": "HKCU", "command": launch}
    AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART.write_text(
        "[Desktop Entry]\nType=Application\n"
        f"Name={NAME}\nExec={launch}\n"
        "Hidden=false\nX-GNOME-Autostart-enabled=true\n",
        encoding="utf-8",
    )
    return {"status": "ENABLED", "path": str(AUTOSTART)}


def disable() -> dict:
    if platform.system() == "Windows":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, "GAIA")
        except FileNotFoundError:
            pass
        return {"status": "DISABLED"}
    AUTOSTART.unlink(missing_ok=True)
    return {"status": "DISABLED", "path": str(AUTOSTART)}


def status() -> dict:
    expected = command()
    if platform.system() == "Windows":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_READ) as key:
                installed, _ = winreg.QueryValueEx(key, "GAIA")
        except (FileNotFoundError, OSError):
            return {"status": "DISABLED"}
        if not _python_path().is_file() or str(installed) != expected:
            return {"status": "BROKEN", "reason": "Python no existe o comando obsoleto", "command": str(installed), "expected": expected}
        return {"status": "ENABLED", "command": str(installed)}
    if not AUTOSTART.is_file():
        return {"status": "DISABLED", "path": str(AUTOSTART)}
    if not _python_path().is_file() or f"Exec={expected}" not in AUTOSTART.read_text(encoding="utf-8"):
        return {"status": "BROKEN", "path": str(AUTOSTART), "reason": "Ruta de Python obsoleta"}
    return {"status": "ENABLED", "path": str(AUTOSTART)}


def main() -> None:
    parser = argparse.ArgumentParser(description="GAIA user-session startup")
    parser.add_argument("action", choices=["enable", "disable", "status", "test"])
    args = parser.parse_args()
    if args.action == "enable":
        print(enable())
    elif args.action == "disable":
        print(disable())
    elif args.action == "status":
        print(status())
    else:
        _check_installation()
        raise SystemExit(subprocess.run([str(_python_path()), str(ROOT / "lumen-pc" / "gaia_desktop_launcher.py"), "--once"], check=False).returncode)


if __name__ == "__main__":
    main()
