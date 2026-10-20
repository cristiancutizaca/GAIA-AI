from __future__ import annotations

from pathlib import Path
import tempfile

from rc2_migration_fixture import inspect, migration, write_source, write_target

with tempfile.TemporaryDirectory(prefix="gaia_rc2_same_db_") as tmp:
    base = Path(tmp)
    source, target, external_db, snapshot = base / "source", base / "target", base / "vault" / "memory.db", base / "snap"
    write_source(source, external_db)
    write_target(target, env=f"GAIA_MEMORY_DB={external_db}")
    report = inspect(source)
    try:
        migration.apply_migration(source, target, snapshot, report, approved=True, db_strategy="CLONE_TO_TARGET")
    except ValueError as exc:
        assert "external/aliased" in str(exc)
    else:
        raise AssertionError("implicit aliasing to source DB must be blocked")
    assert not (target / "lumen-core" / "data" / "lumen_memory.db").exists()

    nested_target = source / "nested-target"
    write_target(nested_target)
    try:
        migration.apply_migration(source, nested_target, base / "nested-snap", report, approved=True)
    except ValueError as exc:
        assert "distinct and non-nested" in str(exc)
    else:
        raise AssertionError("nested source/target roots must be blocked")

    same_target = base / "same-target"
    write_target(same_target)
    try:
        migration.apply_migration(source, same_target, source / "illegal-snapshot", report, approved=True)
    except ValueError as exc:
        assert "snapshot destination" in str(exc)
    else:
        raise AssertionError("snapshot inside source must be blocked")

print("MIGRATION SAME DB FAIL-CLOSED RC2 TEST OK: implicit source alias, nested roots and in-tree snapshots are blocked.")
