from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r'''
import json
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "lumen-core"))
import config
import memory
memory.init_db()
with sqlite3.connect(config.DB_PATH) as conn:
    conn.execute("CREATE TABLE IF NOT EXISTS _fresh_install_probe (id INTEGER)")
print(json.dumps({
    "db": str(config.DB_PATH),
    "db_is_file": config.DB_PATH.is_file(),
    "db_is_project_root": config.DB_PATH == config.PROJECT_DIR,
    "data": str(config.DATA_DIR),
    "backup": str(config.BACKUP_DIR),
    "vault": config.VAULT_STATUS,
    "vault_path": str(config.GAIA_VAULT) if config.GAIA_VAULT else None,
}))
'''


def run_case(root: Path, extra: dict[str, str]) -> dict:
    env = os.environ.copy()
    for key in ("GAIA_HOME", "GAIA_VAULT", "GAIA_DATA_DIR", "GAIA_MEMORY_DB", "GAIA_BACKUP_DIR", "GAIA_LOG_DIR", "LUMEN_DATA_DIR", "LUMEN_MEMORY_DB", "LUMEN_BACKUP_DIR", "LUMEN_LOG_DIR"):
        env.pop(key, None)
    env.update({"LUMEN_LLM_BACKEND": "mock", "LUMEN_SECRET": "test-secret-fresh-install", **extra})
    result = subprocess.run([sys.executable, "-c", SCRIPT], cwd=root, env=env, capture_output=True, text=True, check=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


with tempfile.TemporaryDirectory(prefix="gaia_fresh_install_") as tmp:
    temp_root = Path(tmp) / "GAIA"
    shutil.copytree(ROOT, temp_root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "data"))
    shutil.copy2(temp_root / ".env.example", temp_root / ".env")

    blank = run_case(temp_root, {key: "" for key in ("GAIA_HOME", "GAIA_VAULT", "GAIA_DATA_DIR", "GAIA_MEMORY_DB", "GAIA_BACKUP_DIR", "GAIA_LOG_DIR", "LUMEN_DATA_DIR", "LUMEN_MEMORY_DB", "LUMEN_BACKUP_DIR", "LUMEN_LOG_DIR")})
    assert blank["db_is_file"] and not blank["db_is_project_root"]
    assert Path(blank["backup"]).is_dir()
    assert blank["vault"] == "fallback_local"

    explicit = Path(tmp) / "explicit"
    explicit_db = explicit / "memory" / "gaia.db"
    explicit_backup = explicit / "backups"
    configured = run_case(temp_root, {"GAIA_DATA_DIR": str(explicit / "data"), "GAIA_MEMORY_DB": str(explicit_db), "GAIA_BACKUP_DIR": str(explicit_backup), "GAIA_LOG_DIR": str(explicit / "logs")})
    assert configured["db"] == str(explicit_db.resolve()) and explicit_db.is_file() and explicit_backup.is_dir()

    existing_vault = Path(tmp) / "vault"
    existing_vault.mkdir()
    vault_case = run_case(temp_root, {"GAIA_HOME": str(existing_vault), "GAIA_VAULT": str(existing_vault)})
    assert vault_case["vault"] == "configured" and Path(vault_case["db"]).is_file()

    missing_vault = Path(tmp) / "missing-vault"
    missing_case = run_case(temp_root, {"GAIA_HOME": str(missing_vault), "GAIA_VAULT": str(missing_vault)})
    assert missing_case["vault"] == "missing_fallback" and not missing_vault.exists()

    legacy = Path(tmp) / "legacy"
    legacy_case = run_case(temp_root, {"LUMEN_DATA_DIR": str(legacy / "data"), "LUMEN_MEMORY_DB": str(legacy / "memory.db"), "LUMEN_BACKUP_DIR": str(legacy / "backups")})
    assert legacy_case["db"] == str((legacy / "memory.db").resolve()) and (legacy / "memory.db").is_file()

print("FRESH INSTALL TEST OK")
