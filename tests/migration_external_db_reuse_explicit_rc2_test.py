from __future__ import annotations

from pathlib import Path
import tempfile

from rc2_migration_fixture import inspect, migration, read_content, write_source, write_target

with tempfile.TemporaryDirectory(prefix="gaia_rc2_external_reuse_") as tmp:
    base = Path(tmp)
    source, target, external_db, snapshot = base / "source", base / "target", base / "vault" / "memory.db", base / "snap"
    write_source(source, external_db)
    write_target(target, env="GAIA_MEMORY_DB=target-placeholder.db")
    report = inspect(source)
    result = migration.apply_migration(source, target, snapshot, report, approved=True, db_strategy="REUSE_EXISTING_EXTERNAL_VAULT")
    assert result["same_physical_db"] is True
    assert result["memory_copied"] is False
    assert Path(result["target_db"]).resolve() == external_db.resolve()
    assert (target / ".env").read_text(encoding="utf-8").strip() == f"GAIA_MEMORY_DB={external_db}"
    assert read_content(external_db) == "source durable value"
    assert not (target / "lumen-core" / "data" / "lumen_memory.db").is_file()

print("MIGRATION EXTERNAL DB REUSE EXPLICIT RC2 TEST OK: external Vault reuse requires explicit strategy and performs no clone.")
