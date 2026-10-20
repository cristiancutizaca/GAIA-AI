from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "gaia_migrate.py"
spec = importlib.util.spec_from_file_location("gaia_migrate_rc2", MODULE_PATH)
assert spec and spec.loader
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def make_db(path: Path, schema: str = "9", content: str = "durable item") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(f"""
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta(key, value) VALUES ('schema_version', '{schema}');
            CREATE TABLE devices (device_id TEXT PRIMARY KEY, capabilities_json TEXT NOT NULL);
            INSERT INTO devices(device_id, capabilities_json) VALUES ('pc-main', '[]');
            CREATE TABLE device_tokens (token_id TEXT PRIMARY KEY, token_hash TEXT NOT NULL);
            INSERT INTO device_tokens(token_id, token_hash) VALUES ('tok-1', 'hash-only');
            CREATE TABLE memory_items (id INTEGER PRIMARY KEY, content TEXT NOT NULL);
            INSERT INTO memory_items(id, content) VALUES (1, {content!r});
            CREATE TABLE memory_item_history (id INTEGER PRIMARY KEY, memory_item_id INTEGER, content TEXT);
            CREATE TABLE session_owners (session_id TEXT PRIMARY KEY, device_id TEXT, principal TEXT);
        """)


with tempfile.TemporaryDirectory(prefix="gaia_rc1_migration_") as tmp:
    base = Path(tmp)
    source = base / "stable"
    (source / "lumen-core").mkdir(parents=True)
    (source / "lumen-core" / "config.py").write_text('VERSION = "0.9.2-pc"\n', encoding="utf-8")
    (source / ".env").write_text("LUMEN_SECRET=test-rc1-secret-must-not-print-123456789\n", encoding="utf-8")
    (source / ".env.example").write_text("LUMEN_SECRET=cambia-este-token\n", encoding="utf-8")
    source_db = source / "lumen-core" / "data" / "lumen_memory.db"
    make_db(source_db)

    report = migration.inspect_installation(source, migration.RC6_VERSION, safe_mode=True)
    assert report["current_version"] == "0.9.2-pc"
    assert report["schema"] == "9" and report["integrity"] == "ok"
    assert report["migration_state"] == "compatible_review_required"
    assert report["compatibility"]["source_supported"] is True
    assert report["safe_mode"] is True
    rendered = json.dumps(report, sort_keys=True)
    assert "rc1-secret-must-not-print" not in rendered
    assert report["secret_values_emitted"] is False

    snapshot = base / "external-snapshot"
    manifest = migration.create_snapshot(source, snapshot, report)
    assert manifest["format"] == "gaia-rc6-snapshot-1"
    assert (snapshot / ".env.private.copy").is_file()
    assert (snapshot / "memory.snapshot.sqlite").is_file()
    assert (snapshot / "manifest.json").is_file()
    assert (source / ".env").read_text(encoding="utf-8").startswith("LUMEN_SECRET=")
    with sqlite3.connect(snapshot / "memory.snapshot.sqlite") as conn:
        assert conn.execute("SELECT content FROM memory_items WHERE id=1").fetchone()[0] == "durable item"

    target = base / "new-release"
    (target / "lumen-core").mkdir(parents=True)
    (target / "tools").mkdir(parents=True)
    (target / "lumen-core" / "config.py").write_text('VERSION = "1.0.0-rc6-pc"\n', encoding="utf-8")
    (target / "tools" / "gaia_migrate.py").write_text("# fixture target migrator\n", encoding="utf-8")
    (target / "release_manifest.json").write_text(json.dumps({"product": "GAIA-AI", "release": "1.0-RC6", "version": "1.0.0-rc6-pc", "protocol": "1.0-RC6", "schema_min": 8, "schema_max": 9, "manifest_format": 1, "deterministic": True}) + "\n", encoding="utf-8")
    applied_snapshot = base / "apply-snapshot"
    try:
        migration.apply_migration(source, target, applied_snapshot, report, approved=False)
    except PermissionError:
        pass
    else:
        raise AssertionError("apply without explicit approval must be blocked")
    assert not applied_snapshot.exists()

    applied = migration.apply_migration(source, target, applied_snapshot, report, approved=True, safe_mode=True)
    assert applied["operation"] == "apply"
    assert applied["source_preserved"] is True and applied["memory_copied"] is True
    assert applied["safe_mode"] is True
    assert not (target / ".env").is_file()
    assert (target / "lumen-core" / "data" / "lumen_memory.db").is_file()
    assert "rc1-secret-must-not-print" not in json.dumps(applied, sort_keys=True)

    target_db = target / "lumen-core" / "data" / "lumen_memory.db"
    with sqlite3.connect(target_db) as conn:
        conn.execute("UPDATE memory_items SET content='changed after apply' WHERE id=1")
    rolled_back = migration.rollback_from_snapshot(applied_snapshot, target, approved=True, safe_mode=True)
    assert rolled_back["operation"] == "rollback"
    assert rolled_back["safe_mode"] is True
    with sqlite3.connect(target_db) as conn:
        assert conn.execute("SELECT content FROM memory_items WHERE id=1").fetchone()[0] == "durable item"

    newer = base / "newer"
    (newer / "lumen-core").mkdir(parents=True)
    (newer / "lumen-core" / "config.py").write_text('VERSION = "0.9.2-pc"\n', encoding="utf-8")
    make_db(newer / "lumen-core" / "data" / "lumen_memory.db", schema="10")
    blocked = migration.inspect_installation(newer, migration.RC6_VERSION)
    assert blocked["migration_state"] == "blocked_newer_schema"

print("V100 RC2 MIGRATION TEST OK: read-only dry-run, external snapshot, target identity, explicit apply/rollback, safe mode, source preservation, schema block and secret redaction.")
