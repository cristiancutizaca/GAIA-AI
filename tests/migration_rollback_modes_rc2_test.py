from __future__ import annotations

import json
from pathlib import Path
import tempfile

from rc2_migration_fixture import inspect, migration, read_content, write_source, write_target

with tempfile.TemporaryDirectory(prefix="gaia_rc2_rollback_") as tmp:
    base = Path(tmp)
    source, target, source_db, snapshot = base / "source", base / "target", base / "vault" / "memory.db", base / "snap"
    write_source(source, source_db)
    secret = "test-rollback-secret-never-output"
    write_target(target, env=f"GAIA_MEMORY_DB=lumen-core/data/lumen_memory.db\nLUMEN_SECRET={secret}")
    report = inspect(source)
    applied = migration.apply_migration(source, target, snapshot, report, approved=True, db_strategy="CLONE_TO_TARGET")
    target_db = Path(applied["target_db"])
    target_env_after_apply = (target / ".env").read_text(encoding="utf-8")
    assert target_env_after_apply.endswith(secret + "\n")
    target_db.write_bytes(target_db.read_bytes())
    with target_db.open("ab") as handle:
        handle.write(b"changed")
    db_only = migration.rollback_from_snapshot(snapshot, target, approved=True, rollback_mode="ROLLBACK_DATABASE_ONLY")
    assert db_only["database_restored"] is True and db_only["config_restored"] is False
    assert read_content(target_db) == "source durable value"
    assert (target / ".env").read_text(encoding="utf-8") == target_env_after_apply
    assert secret not in json.dumps(db_only, sort_keys=True)

    (target / ".env").write_text("GAIA_MEMORY_DB=mutated.db\nLUMEN_SECRET=changed-secret\n", encoding="utf-8")
    full = migration.rollback_from_snapshot(snapshot, target, approved=True, rollback_mode="ROLLBACK_DATABASE_AND_CONFIG")
    assert full["database_restored"] is True and full["config_restored"] is True
    assert (target / ".env").read_text(encoding="utf-8") == "GAIA_MEMORY_DB=lumen-core/data/lumen_memory.db\nLUMEN_SECRET=test-rollback-secret-never-output\n"
    assert "test-rollback-secret-never-output" not in json.dumps(full, sort_keys=True)
    assert "changed-secret" not in json.dumps(full, sort_keys=True)

    wrong = base / "wrong-target"
    write_target(wrong, manifest={"product": "GAIA-AI", "release": "1.0-RC6", "version": "0.5.0-pc", "protocol": "1.0-RC6", "schema_min": 8, "schema_max": 9})
    try:
        migration.apply_migration(source, wrong, base / "wrong-snap", report, approved=True)
    except ValueError as exc:
        assert "identity/version/protocol mismatch" in str(exc)
    else:
        raise AssertionError("wrong target identity must be rejected before mutation")
    assert not (wrong / "lumen-core" / "data" / "lumen_memory.db").exists()

print("MIGRATION ROLLBACK MODES RC2 TEST OK: DB-only/full-config semantics, target identity fail-closed and secret redaction hold.")
