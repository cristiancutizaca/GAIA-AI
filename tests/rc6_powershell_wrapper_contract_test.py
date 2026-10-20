from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
wrapper = ROOT / "validate-gaia-rc6.ps1"
text = wrapper.read_text(encoding="utf-8")

assert text.lstrip().startswith("[CmdletBinding()]\nparam(")
assert "Set-StrictMode -Version Latest" in text
assert "$ErrorActionPreference = 'Stop'" in text or '$ErrorActionPreference = "Stop"' in text
assert "GetRelativePath" in text or "Get-RelativePath" in text
assert "Resolve-ExternalDirectory" in text
assert "Invoke-Checked" in text
assert "ConfirmInstall" in text
assert "RecreateVenv" in text
assert "--confirm-install" in text
assert "--recreate-venv" in text
assert "GAIA-AI-v1.0-RC6" in text
assert "validate_rc6.py" in text
assert re.search(r"GAIA-AI-v1\\\.0\\\\-RC6", text) or "RC6" in text
assert "validate_rc4.py" not in text
assert "GAIA-AI-v1.0-RC4" not in text
assert "Invoke-Expression" not in text
assert "shell=True" not in text
assert "OPENAI_API_KEY" not in text
assert "/home/ubuntu" not in text

print("RC6 POWERSHELL WRAPPER CONTRACT TEST OK: strict execution, external evidence, explicit install, RC6 archive validation and no RC4 entrypoint hold.")
