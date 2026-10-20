from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
installer = (ROOT / "install-gaia.ps1").read_text(encoding="utf-8")
wrapper = (ROOT / "setup-windows.bat").read_text(encoding="utf-8")
windows_requirements = (ROOT / "lumen-pc/requirements-windows.txt").read_text(encoding="utf-8")

for marker in ("Get-Python311", "-m', 'venv", "pip<25", "setuptools<70", "lumen-core\\requirements.txt", "lumen-pc\\requirements.txt", "requirements-windows.txt", "New-StrongSecret", "LUMEN_SECRET", "tools\\gaia_doctor.py", "--json"):
    assert marker in installer, marker
assert "ExecutionPolicy Bypass" in wrapper or "ExecutionPolicy Bypass".casefold() in wrapper.casefold()
for dependency in ("pycaw", "comtypes", "psutil", "sounddevice", "numpy", "httpx", "python-dotenv"):
    assert dependency in windows_requirements, dependency
assert "openai-whisper==20231117" in (ROOT / "lumen-core/requirements.txt").read_text(encoding="utf-8")
assert "shell=True" not in installer.casefold()
assert "os.system" not in installer.casefold()
print("WINDOWS INSTALL CONTRACT TEST OK: Python 3.11, venv, requirements, strong secret, import check and Doctor are wired.")
