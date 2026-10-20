from __future__ import annotations

from pathlib import Path
import tempfile

from rc2_migration_fixture import inspect, migration, write_source, write_target

with tempfile.TemporaryDirectory(prefix="gaia_rc2_target_identity_") as tmp:
    base = Path(tmp)
    source, source_db = base / "source", base / "vault" / "memory.db"
    write_source(source, source_db)
    report = inspect(source)

    missing = base / "missing"
    write_target(missing)
    (missing / "release_manifest.json").unlink()
    try:
        migration.apply_migration(source, missing, base / "missing-snap", report, approved=True)
    except ValueError as exc:
        assert "manifest missing" in str(exc)
    else:
        raise AssertionError("missing manifest must block apply")

    for field, value in (("product", "OTHER"), ("release", "1.0-RC1"), ("version", "0.5.0-pc"), ("protocol", "0.9"), ("schema_min", 7), ("schema_max", 10)):
        target = base / f"bad-{field}"
        manifest = {"product": "GAIA-AI", "release": "1.0-RC6", "version": "1.0.0-rc6-pc", "protocol": "1.0-RC6", "schema_min": 8, "schema_max": 9}
        manifest[field] = value
        write_target(target, manifest=manifest)
        try:
            migration.apply_migration(source, target, base / f"snap-{field}", report, approved=True)
        except ValueError as exc:
            assert "mismatch" in str(exc)
        else:
            raise AssertionError(f"bad manifest field {field} must be blocked")
        assert not (target / "lumen-core" / "data" / "lumen_memory.db").exists()

    valid = base / "valid"
    write_target(valid)
    result = migration.apply_migration(source, valid, base / "valid-snap", report, approved=True)
    assert result["operation"] == "apply"

print("MIGRATION TARGET IDENTITY RC2 TEST OK: manifest, release, protocol, version and schema gates are fail-closed before mutation.")
