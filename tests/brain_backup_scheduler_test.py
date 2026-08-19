"""Prueba del scheduler Brain Backup sin esperar horas ni tocar backups reales."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_scheduler_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "scheduler-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "GAIA_BRAIN_BACKUP_ENABLED": "true",
        "GAIA_BRAIN_BACKUP_INTERVAL_HOURS": "24",
    })
    import memory
    import backup_scheduler
    import brain_backup

    memory.init_db()
    calls: list[str] = []
    original = brain_backup.create_brain_backup

    def fake_backup() -> str:
        calls.append("backup")
        path = str(Path(tmp) / "fake_brain.zip")
        memory.set_state("last_brain_backup_at", datetime.now().isoformat())
        return path

    brain_backup.create_brain_backup = fake_backup
    assert backup_scheduler.brain_backup_due()
    assert asyncio.run(backup_scheduler.run_brain_backup_once()) == str(Path(tmp) / "fake_brain.zip")
    assert calls == ["backup"]
    assert not backup_scheduler.brain_backup_due()
    assert asyncio.run(backup_scheduler.run_brain_backup_once()) is None
    assert calls == ["backup"]

    def failing_backup() -> str:
        raise RuntimeError("simulated failure")

    brain_backup.create_brain_backup = failing_backup
    memory.set_state("last_brain_backup_at", "")
    assert asyncio.run(backup_scheduler.run_brain_backup_once()) is None
    brain_backup.create_brain_backup = original

    backup_scheduler.BRAIN_BACKUP_ENABLED = False
    assert not backup_scheduler.brain_backup_due()

    out = Path(tmp) / "retention"
    out.mkdir()
    old = out / "gaia_brain_1.zip"
    middle = out / "gaia_brain_2.zip"
    newest = out / "gaia_brain_3.zip"
    for item in (old, middle, newest):
        item.write_bytes(b"x")
    kept = brain_backup.prune_brain_backups(out, protect=newest, max_files=2)
    assert newest.exists() and len(kept) == 2

print("BRAIN BACKUP SCHEDULER TEST OK: enabled, intervalo, ejecución, fallo y retención.")
