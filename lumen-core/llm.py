"""Adaptadores LLM de LUMEN: Ollama, OpenAI, Anthropic y modo mock de pruebas."""
from __future__ import annotations
import logging
import httpx
from config import LLM_BACKEND, LLM_MODEL, OLLAMA_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY, LLM_TIMEOUT_SECONDS

logger = logging.getLogger("lumen.llm")


class LLMError(RuntimeError):
    """Fallo comunicando con el backend de conversación configurado."""


async def chat_completion(system_prompt: str, messages: list[dict], temperature: float = 0.8) -> str:
    if LLM_BACKEND == "ollama":
        return await _ollama_chat(system_prompt, messages, temperature)
    if LLM_BACKEND == "openai":
        return await _openai_chat(system_prompt, messages, temperature)
    if LLM_BACKEND == "anthropic":
        return await _anthropic_chat(system_prompt, messages, temperature)
    if LLM_BACKEND == "mock":
        latest = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"Modo técnico de prueba activo. Recibí: {latest[:180]}" if latest else "Modo técnico de prueba activo."
    raise LLMError(f"Backend LLM no soportado: {LLM_BACKEND}")


async def _post_json(url: str, **kwargs) -> dict:
    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(url, **kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError as exc:
        raise LLMError("No se pudo conectar con el backend LLM configurado.") from exc
    except httpx.TimeoutException as exc:
        raise LLMError("El backend LLM agotó el tiempo de espera.") from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("Backend LLM devolvió HTTP %s", exc.response.status_code)
        raise LLMError(f"El backend LLM devolvió HTTP {exc.response.status_code}.") from exc
    except (ValueError, KeyError) as exc:
        raise LLMError("El backend LLM devolvió una respuesta inválida.") from exc


async def _ollama_chat(system_prompt: str, messages: list[dict], temperature: float) -> str:
    data = await _post_json(
        f"{OLLAMA_URL}/api/chat",
        json={"model": LLM_MODEL, "messages": [{"role": "system", "content": system_prompt}, *messages], "stream": False,
              "options": {"temperature": temperature, "num_predict": 1024}},
    )
    text = data.get("message", {}).get("content", "").strip()
    if not text:
        raise LLMError("Ollama no devolvió texto.")
    return text


async def _openai_chat(system_prompt: str, messages: list[dict], temperature: float) -> str:
    if not OPENAI_API_KEY:
        raise LLMError("No hay API key de OpenAI configurada en .env.")
    data = await _post_json(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={"model": LLM_MODEL, "messages": [{"role": "system", "content": system_prompt}, *messages],
              "temperature": temperature, "max_tokens": 1024},
    )
    text = data["choices"][0]["message"]["content"].strip()
    if not text:
        raise LLMError("OpenAI no devolvió texto.")
    return text


async def _anthropic_chat(system_prompt: str, messages: list[dict], temperature: float) -> str:
    if not ANTHROPIC_API_KEY:
        raise LLMError("No hay API key de Anthropic configurada en .env.")
    data = await _post_json(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
        json={"model": LLM_MODEL, "system": system_prompt, "messages": messages,
              "temperature": temperature, "max_tokens": 1024},
    )
    text = data["content"][0]["text"].strip()
    if not text:
        raise LLMError("Anthropic no devolvió texto.")
    return text


async def check_backend() -> dict:
    info = {"backend": LLM_BACKEND, "model": LLM_MODEL, "status": "unknown"}
    try:
        if LLM_BACKEND == "ollama":
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{OLLAMA_URL}/api/tags")
                response.raise_for_status()
                models = [m.get("name", "") for m in response.json().get("models", [])]
            info.update(status="online", available_models=models, model_loaded=any(LLM_MODEL in model for model in models))
        elif LLM_BACKEND == "openai":
            info["status"] = "configured" if OPENAI_API_KEY else "no_api_key"
        elif LLM_BACKEND == "anthropic":
            info["status"] = "configured" if ANTHROPIC_API_KEY else "no_api_key"
        elif LLM_BACKEND == "mock":
            info.update(status="test_only", model="echo")
        else:
            info["status"] = "invalid_backend"
    except Exception as exc:
        info.update(status="offline", error=str(exc))
    return info
