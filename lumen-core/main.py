"""Servidor FastAPI central de LUMEN v0.2."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import memory
from config import HOST, PORT, CORS_ORIGINS, BACKUP_ENABLED, VERSION, validate_configuration
from logging_setup import configure_logging
from routes.api import router

configure_logging()
logger = logging.getLogger("lumen.core")


@asynccontextmanager
async def lifespan(app: FastAPI):
    warnings = validate_configuration()
    memory.init_db()
    logger.info("LUMEN Core %s iniciando", VERSION)
    for warning in warnings:
        logger.warning(warning)
    from llm import check_backend
    backend = await check_backend()
    logger.info("LLM backend=%s estado=%s modelo=%s", backend["backend"], backend["status"], backend["model"])
    tasks: list[asyncio.Task] = []
    from proactive import proactive_loop, is_enabled
    if is_enabled():
        tasks.append(asyncio.create_task(proactive_loop(), name="proactive-loop"))
        logger.info("Proactividad automática activa")
    else:
        logger.info("Proactividad automática desactivada; test manual disponible")
    if BACKUP_ENABLED:
        from backup_scheduler import backup_loop
        tasks.append(asyncio.create_task(backup_loop(), name="backup-loop"))
        logger.info("Backup automático activo")
    logger.info("Servidor escuchando en http://%s:%s", HOST, PORT)
    yield
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    from voice import cleanup_audio
    cleanup_audio()
    logger.info("LUMEN Core apagado")


app = FastAPI(
    title="LUMEN Core",
    description="API local de LUMEN para clientes de escritorio.",
    version=VERSION,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {"name": "LUMEN", "version": VERSION, "status": "online", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False, log_level="info")
