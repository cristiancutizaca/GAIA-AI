from __future__ import annotations

import json
from pathlib import Path
import tempfile

from rc2_migration_fixture import inspect, migration, read_content, write_source, write_target

with tempfile.TemporaryDirectory(prefix="gaia_rc2_external_clone_") as tmp:
    base = Path(tmp)
    source, target, external_db, snapshot = base / "source", base / "target", base / "vault" / "memory.db", base / "snap"
    write_source(source, external_db)
    write_target(target, env="GAIA_MEMORY_DB=lumen-core/data/lumen_memory.db")
    report = inspect(source)
    assert report["source_db_external"] is True
    result = migration.apply_migration(source, target, snapshot, report, approved=True, safe_mode=True, db_strategy="CLONE_TO_TARGET")
    target_db = target / "lumen-core" / "data" / "lumen_memory.db"
    assert result["memory_copied"] is True and result["same_physical_db"] is False
    assert read_content(target_db) == "source durable value"
    assert read_content(external_db) == "source durable value"
    assert (target / ".env").read_text(encoding="utf-8").strip() == "GAIA_MEMORY_DB=lumen-core/data/lumen_memory.db"
    encoded = json.dumps(result, sort_keys=True)
    assert "fixture-secret-never-output" not in encoded
    assert result["source_preserved"] is True

print("MIGRATION EXTERNAL DB CLONE RC2 TEST OK: external Vault cloned to target without source alias or secret disclosure.")
