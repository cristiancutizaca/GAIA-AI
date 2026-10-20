from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import os
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MIGRATE = ROOT / "tools" / "gaia_migrate.py"
spec = importlib.util.spec_from_file_location("gaia_migrate_rc1_compat", MIGRATE)
assert spec and spec.loader
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def make_install(base: Path, version: str, schema: str | None) -> Path:
    root = base / f"{version.replace('.', '_').replace('-', '_')}_{schema or 'none'}"
    (root / "lumen-core").mkdir(parents=True)
    (root / "lumen-core" / "config.py").write_text(f'VERSION = "{version}"\n', encoding="utf-8")
    if schema is not None:
        db = root / "lumen-core" / "data" / "lumen_memory.db"
        db.parent.mkdir(parents=True)
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("INSERT INTO schema_meta VALUES ('schema_version', ?)", (schema,))
    return root


with tempfile.TemporaryDirectory(prefix="gaia_rc1_compat_") as tmp:
    base = Path(tmp)
    compatible = migration.inspect_installation(make_install(base, "0.9.2-pc", "9"))
    assert compatible["migration_state"] == "compatible_review_required"
    assert compatible["compatibility"]["source_supported"] is True

    newer_schema = migration.inspect_installation(make_install(base, "0.9.2-pc", "10"))
    assert newer_schema["migration_state"] == "blocked_newer_schema"

    downgrade = migration.inspect_installation(make_install(base, "1.0.1-pc", "9"))
    assert downgrade["migration_state"] == "blocked_downgrade"

    absent = migration.inspect_installation(make_install(base, "0.9.2-pc", None))
    assert absent["migration_state"] == "no_database"
    assert absent["code_downloaded"] is False and absent["secret_values_emitted"] is False

    before = sorted(str(path.relative_to(ROOT)) for path in ROOT.rglob('*'))
    env = dict(os.environ)
    env["LUMEN_LLM_BACKEND"] = "mock"
    env["LUMEN_SECRET"] = "test-rc1-doctor-secret"
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "gaia_doctor.py"), "--json", "--mode", "safe"], capture_output=True, text=True, check=True, env=env)
    payload = json.loads(result.stdout)
    assert payload["doctor"] == "1.0-RC6"
    assert payload["base_version"] == "1.0-RC1"
    assert payload["mode"] == "safe" and payload["read_only"] is True
    assert any(item["name"] == "operation_mode" and item["status"] == "PASS" for item in payload["checks"])
    assert "test-rc1-doctor-secret" not in result.stdout
    after = sorted(str(path.relative_to(ROOT)) for path in ROOT.rglob('*'))
    assert before == after

print("V100 RC2 COMPATIBILITY TEST OK: schema/version fail-closed gates, no-database state, Doctor modes, read-only behavior and secret non-disclosure.")
