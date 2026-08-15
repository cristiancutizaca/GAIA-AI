"""Tarea periódica de backup automático del Core."""
from __future__ import annotations
import asyncio
import logging
import memory
from config import BACKUP_ENABLED, BACKUP_CHECK_MINUTES

logger = logging.getLogger("lumen.backup")


async def backup_loop() -> None:
    while True:
        try:
            if BACKUP_ENABLED and memory.backup_due():
                logger.info("Backup automático creado: %s", memory.create_backup())
        except Exception:
            logger.exception("No se pudo crear el backup automático")
        await asyncio.sleep(BACKUP_CHECK_MINUTES * 60)
