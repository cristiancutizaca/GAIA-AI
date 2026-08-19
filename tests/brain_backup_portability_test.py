"""Repeated real Brain Backup round-trip tests under SQLite WAL pressure."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_backup_portable_") as tmp:
    data_root = Path(tmp) / "data"
    archive_root = Path(tmp) / "archives"
    os.environ.update({
        "LUMEN_DATA_DIR": str(data_root),
        "GAIA_MEMORY_DB": str(data_root / "memory" / "lumen_memory.db"),
        "GAIA_BACKUP_DIR": str(archive_root),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-secret-portability",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    import config
    import memory
    from brain_backup import BRAIN_BACKUP_FILES, create_brain_backup, restore_brain_backup

    memory.init_db()
    with sqlite3.connect(config.DB_PATH) as active:
        mode = active.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        assert str(mode).lower() == "wal", mode
        active.execute("CREATE TABLE IF NOT EXISTS _wal_probe (id INTEGER PRIMARY KEY, value TEXT)")
        active.execute("INSERT INTO _wal_probe(value) VALUES (?)", ("open-connection",))
        active.commit()
        memory.save_message("portable-session", "user", "estado-A-0", "test")
        # La conexión permanece abierta mientras create_brain_backup ejecuta SQLite Backup API.
        first_archive = Path(create_brain_backup(archive_root))

    with zipfile.ZipFile(first_archive) as bundle:
        names = set(bundle.namelist())
        manifest = json.loads(bundle.read("manifest.json"))
        assert names == set(BRAIN_BACKUP_FILES) | {"manifest.json"}, names
        assert set(manifest["files"]) == set(BRAIN_BACKUP_FILES), manifest["files"]
        assert "memory.db-wal" not in names and "memory.db-shm" not in names
        assert "memory.db-wal" not in manifest["files"] and "memory.db-shm" not in manifest["files"]

    for iteration in range(12):
        memory.save_message("portable-session", "user", f"estado-A-{iteration}", "test")
        with sqlite3.connect(config.DB_PATH) as active:
            active.execute("PRAGMA journal_mode=WAL")
            active.execute("INSERT INTO _wal_probe(value) VALUES (?)", (f"iteration-{iteration}",))
            active.commit()
            archive = Path(create_brain_backup(archive_root))
        with zipfile.ZipFile(archive) as bundle:
            names = set(bundle.namelist())
            manifest = json.loads(bundle.read("manifest.json"))
            assert names == set(BRAIN_BACKUP_FILES) | {"manifest.json"}
            assert set(manifest["files"]) == set(BRAIN_BACKUP_FILES)
            assert not any(name.endswith(("-wal", "-shm", "-journal")) for name in names)
        memory.save_message("portable-session", "user", f"estado-B-{iteration}", "test")
        result = restore_brain_backup(archive, create_current_backup=False)
        assert result["manifest_verified"] is True and result["integrity"] == "ok"
        contents = [row["content"] for row in memory.get_conversation_history("portable-session", limit=200)]
        assert f"estado-A-{iteration}" in contents
        assert f"estado-B-{iteration}" not in contents

    leftovers = [path.name for path in archive_root.rglob("*") if path.is_file() and path.name.endswith(("-wal", "-shm", "-journal"))]
    assert not leftovers, leftovers

print("BRAIN BACKUP PORTABILITY TEST OK: WAL, conexión abierta, 12 round-trips y cleanup.")
