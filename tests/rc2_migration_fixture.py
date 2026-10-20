from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "gaia_migrate.py"
spec = importlib.util.spec_from_file_location("gaia_migrate_rc2_fixture", TOOL)
assert spec and spec.loader
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def make_db(path: Path, content: str = "source durable value", schema: str = "9") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(
            "CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
            "CREATE TABLE memory_items (id INTEGER PRIMARY KEY, content TEXT NOT NULL);"
        )
        conn.execute("INSERT INTO schema_meta VALUES ('schema_version', ?)", (schema,))
        conn.execute("INSERT INTO memory_items VALUES (1, ?)", (content,))


def read_content(path: Path) -> str:
    with sqlite3.connect(path) as conn:
        return str(conn.execute("SELECT content FROM memory_items WHERE id=1").fetchone()[0])


def write_target(root: Path, *, env: str | None = None, version: str = migration.RC6_CORE_VERSION, manifest: dict | None = None) -> None:
    (root / "lumen-core").mkdir(parents=True, exist_ok=True)
    (root / "tools").mkdir(parents=True, exist_ok=True)
    (root / "lumen-core" / "config.py").write_text(f'VERSION = "{version}"\n', encoding="utf-8")
    (root / "tools" / "gaia_migrate.py").write_text("# fixture target migrator\n", encoding="utf-8")
    if manifest is not None:
        (root / "release_manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    else:
        (root / "release_manifest.json").write_text(json.dumps({
            "product": "GAIA-AI", "release": migration.RC6_LABEL, "version": migration.RC6_CORE_VERSION,
            "protocol": migration.RC6_PROTOCOL, "schema_min": migration.MIN_SUPPORTED_SCHEMA,
            "schema_max": migration.SUPPORTED_SCHEMA_MAX, "manifest_format": 1, "deterministic": True,
        }, sort_keys=True) + "\n", encoding="utf-8")
    if env is not None:
        (root / ".env").write_text(env.rstrip() + "\n", encoding="utf-8")


def write_source(root: Path, db: Path, *, env_extra: str = "", version: str = "0.9.2-pc") -> None:
    (root / "lumen-core").mkdir(parents=True, exist_ok=True)
    (root / "lumen-core" / "config.py").write_text(f'VERSION = "{version}"\n', encoding="utf-8")
    lines = [f"GAIA_MEMORY_DB={db}", "LUMEN_SECRET=test-fixture-secret-never-output"]
    if env_extra:
        lines.append(env_extra)
    (root / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / ".env.example").write_text("GAIA_MEMORY_DB=/path/to/vault/data/memory/lumen_memory.db\n", encoding="utf-8")
    make_db(db)


def inspect(source: Path):
    return migration.inspect_installation(source, migration.RC6_VERSION, safe_mode=True)
