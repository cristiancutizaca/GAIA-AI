"""Configuración pequeña y predecible de logs para LUMEN."""
from __future__ import annotations
import logging
from config import LOG_LEVEL


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
