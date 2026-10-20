from __future__ import annotations

from pathlib import Path
import tempfile

from rc2_migration_fixture import inspect, migration, read_content, write_source, write_target

with tempfile.TemporaryDirectory(prefix="gaia_rc2_new_vault_") as tmp:
    base = Path(tmp)
    source, target, external_db, snapshot, new_vault = base / "source", base / "target", base / "old-vault" / "memory.db", base / "snap", base / "new-vault"
    write_source(source, external_db)
    write_target(target, env="GAIA_MEMORY_DB=old-target.db")
    report = inspect(source)
    result = migration.apply_migration(source, target, snapshot, report, approved=True, db_strategy="CLONE_TO_NEW_VAULT", new_vault=new_vault)
    new_db = new_vault / "data" / "memory" / "lumen_memory.db"
    assert result["memory_copied"] is True and result["same_physical_db"] is False
    assert Path(result["target_db"]).resolve() == new_db.resolve()
    assert new_db.is_file() and read_content(new_db) == "source durable value"
    assert (target / ".env").read_text(encoding="utf-8").strip() == f"GAIA_MEMORY_DB={new_db}"
    assert read_content(external_db) == "source durable value"

print("MIGRATION NEW VAULT RC2 TEST OK: explicit new Vault is external to both roots, configured in target, and populated from the snapshot.")
