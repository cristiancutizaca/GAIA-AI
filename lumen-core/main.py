"""Servidor FastAPI central de GAIA v0.4.1."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import memory
from config import HOST, PORT, CORS_ORIGINS, BACKUP_ENABLED, BRAIN_BACKUP_ENABLED, SAFE_MODE, VERSION, ASSISTANT_NAME, validate_configuration
from logging_setup import configure_logging
from routes.api import router

configure_logging()
logger = logging.getLogger("lumen.core")


@asynccontextmanager
async def lifespan(app: FastAPI):
    warnings = validate_configuration()
    memory.init_db()
    from platform_runtime import PlatformRuntime
    platform_runtime = PlatformRuntime(Path(__file__).resolve().parents[1])
    app.state.platform_runtime = platform_runtime
    await platform_runtime.start()
    logger.info("%s Core %s iniciando", ASSISTANT_NAME, VERSION)
    for warning in warnings:
        logger.warning(warning)
    from llm import check_backend
    backend = await check_backend()
    logger.info("LLM backend=%s estado=%s modelo=%s", backend["backend"], backend["status"], backend["model"])
    tasks: list[asyncio.Task] = []
    from automation_runtime import runtime
    tasks.extend(await runtime.start())
    runtime.publish({"event_type": "core.started", "source": "core", "source_id": VERSION, "payload": {"version": VERSION}, "severity": "info"})
    from proactive import proactive_loop, is_enabled
    if not SAFE_MODE and is_enabled():
        tasks.append(asyncio.create_task(proactive_loop(), name="proactive-loop"))
        logger.info("Proactividad automática activa")
    else:
        logger.info("Proactividad automática desactivada%s; test manual disponible", " por Safe Mode" if SAFE_MODE else "")
    if not SAFE_MODE and (BACKUP_ENABLED or BRAIN_BACKUP_ENABLED):
        from backup_scheduler import backup_loop
        tasks.append(asyncio.create_task(backup_loop(), name="backup-loop"))
        logger.info("Scheduler de backups activo: sqlite=%s brain=%s", BACKUP_ENABLED, BRAIN_BACKUP_ENABLED)
    elif SAFE_MODE:
        logger.info("Safe Mode activo: backup scheduler, proactividad y mutaciones de automatización suspendidos")
    logger.info("Servidor escuchando en http://%s:%s", HOST, PORT)
    yield
    runtime.publish({"event_type": "core.stopping", "source": "core", "source_id": VERSION, "payload": {}, "severity": "info"})
    await runtime.stop()
    await platform_runtime.stop()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    from voice import cleanup_audio
    cleanup_audio()
    from llm import shutdown_http_client
    await shutdown_http_client()
    logger.info("%s Core apagado", ASSISTANT_NAME)


app = FastAPI(
    title=f"{ASSISTANT_NAME} Core",
    description=f"API local de {ASSISTANT_NAME} para clientes de escritorio.",
    version=VERSION,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {"name": ASSISTANT_NAME, "version": VERSION, "status": "online", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False, log_level="info")
