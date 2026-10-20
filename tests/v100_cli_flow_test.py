from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "gaia_migrate.py"


def install(root: Path, version: str = "0.9.2-pc") -> None:
    (root / "lumen-core" / "data").mkdir(parents=True)
    (root / "lumen-core" / "config.py").write_text(f'VERSION = "{version}"\n', encoding="utf-8")
    if version == "1.0.0-rc6-pc":
        (root / "tools").mkdir(parents=True)
        (root / "tools" / "gaia_migrate.py").write_text("# fixture target migrator\n", encoding="utf-8")
        (root / "release_manifest.json").write_text(json.dumps({"product": "GAIA-AI", "release": "1.0-RC6", "version": "1.0.0-rc6-pc", "protocol": "1.0-RC6", "schema_min": 8, "schema_max": 9, "manifest_format": 1, "deterministic": True}) + "\n", encoding="utf-8")
    with sqlite3.connect(root / "lumen-core" / "data" / "lumen_memory.db") as conn:
        conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '9')")
        conn.execute("CREATE TABLE memory_items (id INTEGER PRIMARY KEY, content TEXT NOT NULL)")
        conn.execute("INSERT INTO memory_items VALUES (1, 'cli durable value')")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=ROOT, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})


with tempfile.TemporaryDirectory(prefix="gaia_rc1_cli_") as tmp:
    base = Path(tmp)
    source = base / "source"
    target = base / "target"
    install(source)
    install(target, "1.0.0-rc6-pc")
    snapshot = base / "snapshot"

    inspected = run("--root", str(source), "--target-version", "1.0.0-rc6", "--json", "--safe-mode")
    assert inspected.returncode == 0, inspected.stderr
    assert json.loads(inspected.stdout)["migration_state"] == "compatible_review_required"

    snap = run("--root", str(source), "--target-version", "1.0.0-rc6", "--snapshot-dir", str(snapshot), "--snapshot", "--json", "--safe-mode")
    assert snap.returncode == 0, snap.stderr
    assert json.loads(snap.stdout)["operation"] == "snapshot"
    assert (snapshot / "manifest.json").is_file() and (snapshot / "memory.snapshot.sqlite").is_file()

    blocked = run("--root", str(source), "--target-root", str(target), "--snapshot-dir", str(base / "blocked"), "--apply", "--json")
    assert blocked.returncode == 2 and "approval" in blocked.stderr.casefold()
    assert not (base / "blocked").exists()

    applied = run("--root", str(source), "--target-root", str(target), "--snapshot-dir", str(snapshot), "--apply", "--approve", "--safe-mode", "--json")
    assert applied.returncode == 0, applied.stderr
    assert json.loads(applied.stdout)["operation"] == "apply"

    target_db = target / "lumen-core" / "data" / "lumen_memory.db"
    with sqlite3.connect(target_db) as conn:
        conn.execute("UPDATE memory_items SET content='changed' WHERE id=1")
    rollback = run("--root", str(target), "--snapshot-dir", str(snapshot), "--rollback", "--approve", "--safe-mode", "--json")
    assert rollback.returncode == 0, rollback.stderr
    assert json.loads(rollback.stdout)["operation"] == "rollback"
    with sqlite3.connect(target_db) as conn:
        assert conn.execute("SELECT content FROM memory_items WHERE id=1").fetchone()[0] == "cli durable value"

print("V100 RC2 CLI FLOW TEST OK: inspect, external snapshot, target identity, approval gate, apply, checksum-verified rollback and safe mode.")
