from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MIGRATOR = ROOT / "tools" / "gaia_migrate.py"
FIXTURE_DIR = ROOT / "tests"
sys.path.insert(0, str(FIXTURE_DIR))
from rc2_migration_fixture import write_source, write_target  # noqa: E402


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(MIGRATOR), *args],
        cwd=ROOT,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=120,
    )


def assert_rc6_visible(result: subprocess.CompletedProcess[str]) -> str:
    output = (result.stdout or "") + (result.stderr or "")
    assert "RC6" in output, output
    assert not any(token in output for token in ("RC2", "RC3", "RC4", "rc2", "rc3", "rc4")), output
    assert "test-fixture-secret-never-output" not in output, output
    return output


with tempfile.TemporaryDirectory(prefix="gaia_migrator_cli_contract_") as tmp:
    base = Path(tmp)
    source = base / "source"
    target = base / "target"
    snapshot = base / "snapshot"
    source_db = base / "vault" / "source.db"
    write_source(source, source_db)
    write_target(target)

    plan = run("--root", str(source), "--target-version", "1.0.0-rc6", "--safe-mode")
    assert plan.returncode == 0, plan.stderr
    assert_rc6_visible(plan)
    assert "migration plan" in plan.stdout

    snap = run(
        "--root", str(source),
        "--target-version", "1.0.0-rc6",
        "--snapshot-dir", str(snapshot),
        "--snapshot", "--safe-mode", "--json",
    )
    assert snap.returncode == 0, snap.stderr
    assert_rc6_visible(snap)
    snap_payload = json.loads(snap.stdout)
    assert snap_payload["operation"] == "snapshot"
    assert snap_payload["release_target"] == "1.0-RC6"
    assert snap_payload["snapshot"]["format"] == "gaia-rc6-snapshot-1"
    assert (snapshot / "manifest.json").is_file()

    applied = run(
        "--root", str(source), "--target-root", str(target),
        "--target-version", "1.0.0-rc6", "--snapshot-dir", str(snapshot),
        "--apply", "--approve", "--safe-mode", "--db-strategy", "CLONE_TO_TARGET", "--json",
    )
    assert applied.returncode == 0, applied.stderr
    assert_rc6_visible(applied)
    applied_payload = json.loads(applied.stdout)
    assert applied_payload["operation"] == "apply"
    target_db = target / "lumen-core" / "data" / "lumen_memory.db"
    assert target_db.is_file()

    with sqlite3.connect(target_db) as conn:
        conn.execute("UPDATE memory_items SET content='changed after CLI apply' WHERE id=1")

    rolled = run(
        "--root", str(target), "--snapshot-dir", str(snapshot), "--rollback",
        "--approve", "--safe-mode", "--rollback-mode", "ROLLBACK_DATABASE_ONLY", "--json",
    )
    assert rolled.returncode == 0, rolled.stderr
    assert_rc6_visible(rolled)
    rolled_payload = json.loads(rolled.stdout)
    assert rolled_payload["operation"] == "rollback"
    assert rolled_payload["rollback_mode"] == "ROLLBACK_DATABASE_ONLY"
    with sqlite3.connect(target_db) as conn:
        assert conn.execute("SELECT content FROM memory_items WHERE id=1").fetchone()[0] == "source durable value"

print("RC6 MIGRATOR CLI CONTRACT TEST OK: plan, external snapshot, approved apply/rollback, RC6-visible output and secret redaction hold.")
