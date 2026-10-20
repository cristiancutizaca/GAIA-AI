"""Static contract checks for the v1.0 installation/update preparation."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
installer = (ROOT / "install-gaia.ps1").read_text(encoding="utf-8")
launcher = (ROOT / "setup-windows.bat").read_text(encoding="utf-8")
migrator = (ROOT / "tools" / "gaia_migrate.py").read_text(encoding="utf-8")
ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

assert "Set-StrictMode -Version Latest" in installer
assert "$ErrorActionPreference = 'Stop'" in installer
assert "function Invoke-Checked" in installer
assert "$LASTEXITCODE" in installer
assert "PlanMigration" in installer and "MigrationSnapshotDir" in installer
assert "ApplyMigration" in installer and "ApproveMigration" in installer
assert "SafeMode" in installer and "Rollback" in installer
assert "RollbackSnapshotDir" in installer and "RollbackTargetRoot" in installer
assert "gaia_migrate.py" in installer and "tools" in installer
assert "Write-Host" in installer
assert "LUMEN_SECRET" not in installer.split("Write-Host", 1)[-1] or "valor no se imprime" in installer
assert "Invoke-Expression" not in installer
assert "Start-Process" not in installer
assert "shell=True" not in installer
assert "subprocess" not in migrator
assert "urllib" not in migrator
assert "requests" not in migrator
assert "code_downloaded" in migrator
assert "secret_values_emitted" in migrator
assert "def apply_migration" in migrator and "def rollback_from_snapshot" in migrator
assert "--safe-mode" in migrator and "--approve" in migrator and "--snapshot" in migrator
assert "RC6_VERSION" in migrator and "SUPPORTED_SCHEMA_MAX = 9" in migrator
assert "set \"RC=%ERRORLEVEL%\"" in launcher
assert "exit /b %RC%" in launcher
for pattern in (".env", "*.db", "logs", "backups", "tokens", "__pycache__"):
    assert pattern in ignore, pattern

print("V100 RC2 INSTALL/UPDATE CONTRACT TEST OK: strict installer, explicit plan/apply/rollback/safe mode, exit propagation, no free shell/download and private-file protections.")
