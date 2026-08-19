from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import brain_backup
import memory
from config import BACKUP_CHECK_MINUTES, BACKUP_ENABLED, BRAIN_BACKUP_ENABLED, BRAIN_BACKUP_INTERVAL_HOURS

logger = logging.getLogger("lumen.backup")


def brain_backup_due(now: datetime | None = None) -> bool:
    if not BRAIN_BACKUP_ENABLED:
        return False
    last = memory.get_state("last_brain_backup_at", "")
    if not last:
        return True
    try:
        return (now or datetime.now()) - datetime.fromisoformat(last) >= timedelta(hours=BRAIN_BACKUP_INTERVAL_HOURS)
    except ValueError:
        return True


def backup_runtime_status() -> dict:
    return {
        "sqlite_enabled": BACKUP_ENABLED,
        "brain_enabled": BRAIN_BACKUP_ENABLED,
        "brain_interval_hours": BRAIN_BACKUP_INTERVAL_HOURS,
        "last_sqlite_backup_at": memory.get_state("last_backup_time", ""),
        "last_brain_backup_at": memory.get_state("last_brain_backup_at", ""),
        "last_brain_backup_path": memory.get_state("last_brain_backup_path", ""),
    }


async def run_brain_backup_once() -> str | None:
    if not brain_backup_due():
        return None
    try:
        path = await asyncio.to_thread(brain_backup.create_brain_backup)
        logger.info("Brain Backup periódico creado: %s", path)
        return path
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("No se pudo crear Brain Backup periódico; GAIA continúa operativa")
        return None


async def backup_loop() -> None:
    """Run legacy SQLite snapshots and portable Brain Backups independently."""
    while True:
        try:
            if BACKUP_ENABLED and memory.backup_due():
                logger.info("Backup SQLite automático creado: %s", await asyncio.to_thread(memory.create_backup))
            await run_brain_backup_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("No se pudo completar una comprobación de backup; el scheduler seguirá vivo")
        await asyncio.sleep(BACKUP_CHECK_MINUTES * 60)
