from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install-gaia.ps1"


def extract_import_probe(text: str) -> str:
    match = re.search(r"\$importProbe\s*=\s*\"(.*?)\"\s*\n\s*Invoke-Checked", text, re.DOTALL)
    assert match, "No se encontró $importProbe en el instalador"
    return match.group(1)


def powershell_parse() -> None:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        return
    script = """
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $args[0]), [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) { $errors | ForEach-Object { $_.ToString() }; exit 1 }
"""
    result = subprocess.run([pwsh, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script, str(INSTALLER)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout


def main() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")
    probe = extract_import_probe(installer)
    assert "sys.exit(1 if missing else 0)" in probe
    assert "raise SystemExit" not in probe
    assert "pycaw.pycaw" not in probe

    with tempfile.TemporaryDirectory(prefix="gaia_installer_probe_") as tmp:
        probe_path = Path(tmp) / "probe.py"
        probe_path.write_text(probe, encoding="utf-8")
        result = subprocess.run([sys.executable, str(probe_path)], capture_output=True, text=True)
        assert result.returncode in (0, 1), result.stderr
        assert "SyntaxError" not in result.stderr
        if result.returncode == 1:
            assert "Faltan imports:" in result.stdout
        else:
            assert "Import check OK" in result.stdout

    if not shutil.which("pwsh") and not shutil.which("powershell"):
        assert installer.count("{") == installer.count("}"), "llaves PowerShell desbalanceadas"
        assert installer.count("(") == installer.count(")"), "paréntesis PowerShell desbalanceados"
        assert "try {" in installer and "finally {" in installer
        assert "Set-StrictMode -Version Latest" in installer
    powershell_parse()
    print("INSTALLER EXECUTION CONTRACT V071 TEST OK: extracted Python probe executes, SyntaxError is rejected, and PowerShell/static syntax checks pass.")


if __name__ == "__main__":
    main()
