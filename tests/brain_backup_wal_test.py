"""Focused regression: active SQLite WAL remains WAL; backup excludes sidecars."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_backup_wal_") as tmp:
    data_root = Path(tmp) / "data"
    os.environ.update({
        "LUMEN_DATA_DIR": str(data_root),
        "GAIA_MEMORY_DB": str(data_root / "memory" / "lumen_memory.db"),
        "GAIA_BACKUP_DIR": str(Path(tmp) / "backups"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-secret-wal",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    import config
    import memory
    from brain_backup import create_brain_backup

    memory.init_db()
    with sqlite3.connect(config.DB_PATH) as conn:
        assert str(conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower() == "wal"
        conn.execute("CREATE TABLE IF NOT EXISTS _wal_only_probe (value TEXT)")
        conn.execute("INSERT INTO _wal_only_probe(value) VALUES ('active')")
        conn.commit()

    archive = Path(create_brain_backup(Path(tmp) / "backups"))
    with sqlite3.connect(config.DB_PATH) as conn:
        assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert not {"memory.db-wal", "memory.db-shm", "memory.db-journal"} & names

print("BRAIN BACKUP WAL TEST OK: active WAL preserved and sidecars excluded.")
