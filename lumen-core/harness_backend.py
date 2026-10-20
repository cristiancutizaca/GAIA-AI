"""Puente asíncrono seguro entre GAIA y DeepSeek Harness sobre Ollama local.

GAIA conserva memoria, permisos y ejecución de acciones. Harness se usa como
motor de razonamiento y se inicia mediante el SDK Python público oficial, cuyo
wheel incluye un runtime de la misma versión. No dependemos de APIs privadas ni
de un Node.js instalado globalmente para el camino normal de ejecución.
"""
from __future__ import annotations

import asyncio
from importlib import metadata
import json
import logging
import uuid
from pathlib import Path

import httpx

from config import (
    DSH_API_KEY,
    DSH_BASE_URL,
    DSH_HOME,
    DSH_PROFILE,
    DSH_PROVIDER,
    DSH_REQUEST_TIMEOUT_SECONDS,
    DSH_WORKSPACE,
    LLM_CONTEXT,
    OLLAMA_URL,
    PROJECT_DIR,
)

logger = logging.getLogger("lumen.deepseek_harness")
_HARNESSES: dict[tuple[str, int, int], object] = {}
_LOCK = asyncio.Lock()
_SDK_DISTRIBUTION = "deepseek-harness-sdk"
_SDK_PIN = "0.1.5rc1"


class HarnessBackendError(RuntimeError):
    """Fallo recuperable del backend DeepSeek Harness."""


def _runtime_info() -> dict[str, str]:
    """Comprueba el SDK/runtime público sin depender de binarios privados."""
    try:
        version = metadata.version(_SDK_DISTRIBUTION)
    except metadata.PackageNotFoundError as exc:
        raise HarnessBackendError(
            "DeepSeek Harness SDK no está instalado. Ejecuta install-deepseek-harness o reinstala lumen-core/requirements.txt."
        ) from exc
    try:
        import deepseek_harness  # noqa: F401
    except Exception as exc:  # pragma: no cover - diagnóstico de instalación rota
        raise HarnessBackendError(f"DeepSeek Harness SDK está instalado pero no puede importarse: {type(exc).__name__}: {exc}") from exc
    return {"distribution": _SDK_DISTRIBUTION, "version": version, "recommended_pin": _SDK_PIN}


def _prompt(system_prompt: str, messages: list[dict]) -> str:
    transcript = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    return (
        "Sigue estas instrucciones de identidad y conducta de GAIA durante esta ejecución:\n"
        f"<gaia_system>\n{system_prompt}\n</gaia_system>\n\n"
        "Continúa la conversación siguiente. Responde únicamente al último mensaje del usuario. "
        "No ejecutes herramientas ni comandos; GAIA procesa las acciones mediante su propio sistema de permisos.\n"
        f"<conversation_json>\n{transcript}\n</conversation_json>"
    )


def _new_harness(model: str, max_tokens: int, context_window: int):
    _runtime_info()
    from deepseek_harness import DeepSeekHarness

    patch = PROJECT_DIR / "deepseek-harness" / "gaia-safe.patch.yml"
    if not patch.is_file():
        raise HarnessBackendError(f"Falta el patch seguro de GAIA: {patch}")
    DSH_HOME.mkdir(parents=True, exist_ok=True)
    DSH_WORKSPACE.mkdir(parents=True, exist_ok=True)
    env = {
        "DSH_CONTEXT_WINDOW": str(max(512, context_window or LLM_CONTEXT)),
        "DSH_HOME": str(DSH_HOME),
        "DSH_SYSTEM_PROMPT": (
            "Eres el motor de razonamiento de GAIA. Sigue las instrucciones GAIA incluidas en cada solicitud. "
            "No uses herramientas: devuelve solamente la respuesta final en español."
        ),
    }
    # base_url/api_key son opciones públicas del SDK. El endpoint por defecto es
    # Ollama OpenAI-compatible, por lo que la clave es solo un valor local no secreto.
    return DeepSeekHarness(
        provider=DSH_PROVIDER,
        model=model,
        max_tokens=max_tokens,
        cwd=str(DSH_WORKSPACE),
        runtime_cwd=str(DSH_WORKSPACE),
        dsh_home=str(DSH_HOME),
        profile=DSH_PROFILE,
        patches=(str(patch),),
        env=env,
        base_url=DSH_BASE_URL,
        api_key=DSH_API_KEY,
        request_timeout_seconds=DSH_REQUEST_TIMEOUT_SECONDS,
    )


async def harness_chat(system_prompt: str, messages: list[dict], options: dict, model: str) -> str:
    max_tokens = max(64, int(options.get("num_predict", 1024)))
    context_window = max(512, int(options.get("num_ctx", LLM_CONTEXT)))
    key = (model, max_tokens, context_window)
    async with _LOCK:
        harness = _HARNESSES.get(key)
        if harness is None:
            harness = _new_harness(model, max_tokens, context_window)
            _HARNESSES[key] = harness
    # GAIA es la fuente canónica de memoria/conversación. Cada ejecución Harness
    # recibe el contexto preparado por GAIA y usa una sesión aislada para evitar
    # duplicar historial entre ambos sistemas de memoria.
    session_id = f"gaia-{uuid.uuid4().hex}"
    try:
        result = await asyncio.to_thread(harness.run, _prompt(system_prompt, messages), session_id=session_id)
    except Exception as exc:
        logger.exception("DeepSeek Harness falló sin exponer credenciales")
        raise HarnessBackendError(f"DeepSeek Harness no pudo completar la respuesta: {type(exc).__name__}: {exc}") from exc
    text = str(result.final_response or "").strip()
    if not text:
        raise HarnessBackendError(
            f"DeepSeek Harness terminó sin respuesta visible (estado: {result.finish_reason or 'desconocido'})."
        )
    return text


async def shutdown_harnesses() -> None:
    async with _LOCK:
        harnesses = list(_HARNESSES.values())
        _HARNESSES.clear()
    await asyncio.gather(*(asyncio.to_thread(item.close) for item in harnesses), return_exceptions=True)


async def harness_health() -> dict:
    try:
        runtime = _runtime_info()
    except HarnessBackendError as exc:
        return {"status": "runtime_missing", "reachable": False, "hint": str(exc)}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            response.raise_for_status()
            models = [str(item.get("name", item.get("model", ""))) for item in response.json().get("models", [])]
        return {
            "status": "online",
            "reachable": True,
            "available_models": models,
            "harness_profile": DSH_PROFILE,
            "base_url": DSH_BASE_URL,
            "workspace": str(DSH_WORKSPACE),
            "runtime": runtime,
        }
    except Exception as exc:
        return {
            "status": "offline",
            "reachable": False,
            "runtime": runtime,
            "error": str(exc),
            "hint": "Ollama no está accesible. Ejecuta `ollama serve` y confirma que el modelo esté instalado.",
        }
