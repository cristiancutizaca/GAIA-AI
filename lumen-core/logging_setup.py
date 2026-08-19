"""Configuración pequeña y predecible de logs para GAIA."""
from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler

from config import DATA_DIR, LOG_BACKUP_COUNT, LOG_LEVEL, LOG_MAX_BYTES, PRIVACY_MODE


def configure_logging() -> None:
    level_name = "WARNING" if PRIVACY_MODE == "strict" else LOG_LEVEL
    level = getattr(logging, level_name, logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(log_dir / "lumen.log", maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8")
    stream_handler = logging.StreamHandler()
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(stream_handler)
    root.addHandler(file_handler)
