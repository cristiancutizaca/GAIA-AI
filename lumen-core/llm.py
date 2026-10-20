"""Adaptadores LLM de GAIA v0.4 con routing, streaming y resiliencia."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

import httpx

from config import (
    ANTHROPIC_API_KEY,
    DSH_FALLBACK_TO_OLLAMA,
    LLM_BACKEND,
    LLM_CONTEXT,
    LLM_HIDE_REASONING,
    LLM_KEEP_ALIVE,
    LLM_MODEL,
    LLM_PROFILE,
    LLM_RETRY_COUNT,
    MAX_CONCURRENT_LLM_REQUESTS,
    LLM_STREAM_ENABLED,
    LLM_TIMEOUT_SECONDS,
    OLLAMA_URL,
    OPENAI_API_KEY,
)
from model_router import PROFILES, ModelSelection, fallback_selection, profile_options, resolve_profile, selection_for

logger = logging.getLogger("lumen.llm")
_LLM_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_LLM_REQUESTS)
_HTTP_CLIENT: httpx.AsyncClient | None = None
_HTTP_CLIENT_LOOP_ID: int | None = None
_METRICS = {"queued": 0, "generating": 0, "completed": 0, "cancelled": 0, "failed": 0, "llm_calls": 0, "queue_wait_ms": 0.0, "llm_ttft_ms": 0.0, "llm_total_ms": 0.0}


async def _http_client() -> httpx.AsyncClient:
    global _HTTP_CLIENT, _HTTP_CLIENT_LOOP_ID
    loop_id = id(asyncio.get_running_loop())
    if _HTTP_CLIENT is None or _HTTP_CLIENT_LOOP_ID != loop_id:
        _HTTP_CLIENT = httpx.AsyncClient(timeout=_timeout())
        _HTTP_CLIENT_LOOP_ID = loop_id
    return _HTTP_CLIENT


async def shutdown_http_client() -> None:
    global _HTTP_CLIENT, _HTTP_CLIENT_LOOP_ID
    if _HTTP_CLIENT is not None:
        await _HTTP_CLIENT.aclose()
    _HTTP_CLIENT = None
    _HTTP_CLIENT_LOOP_ID = None
    try:
        from harness_backend import shutdown_harnesses
        await shutdown_harnesses()
    except ImportError:
        pass


def metrics() -> dict:
    return {key: round(float(value), 3) if isinstance(value, float) else int(value) for key, value in _METRICS.items()}


class LLMError(RuntimeError):
    """Fallo comunicando con el backend de conversación configurado."""


def _latest_user_message(messages: list[dict]) -> str:
    return next((str(item.get("content", "")) for item in reversed(messages) if item.get("role") == "user"), "")


def _mock_classifier_response(system_prompt: str, message: str) -> str:
    """Deterministic mock for classifier integration tests; never executes anything."""
    lowered = message.casefold()
    if "shutdown" in lowered or "apaga" in lowered or "formatea" in lowered:
        return json.dumps({"type": "plan", "actions": [{"action": "open_vscode", "args": {}}, {"action": "shutdown", "args": {}}], "confidence": 0.98, "source": "llm"})
    if any(marker in lowered for marker in ("prepara", "empezar a programar", "preparar mi entorno", "abre el proyecto y revisa git")):
        actions = [{"action": "open_project", "args": {"project": "default"}}, {"action": "git_status", "args": {"path": ""}}]
        if "tests" in lowered:
            actions.append({"action": "run_tests", "args": {"path": ""}})
        return json.dumps({"type": "plan", "actions": actions[:3], "confidence": 0.92, "source": "llm"})
    if "abre vscode" in lowered or "abre vs code" in lowered:
        return json.dumps({"type": "action", "action": "open_vscode", "args": {}, "confidence": 0.97, "source": "llm"})
    return json.dumps({"type": "conversation", "confidence": 0.0, "source": "llm"})


async def chat_completion(system_prompt: str, messages: list[dict], temperature: float = 0.8, profile: str | None = None, context_override: int | None = None) -> str:
    selected_profile = resolve_profile(_latest_user_message(messages), requested=profile or LLM_PROFILE)
    selection = selection_for(selected_profile)
    options = profile_options(selected_profile, context_override)
    started = time.perf_counter()
    queued_at = time.perf_counter()
    _METRICS["queued"] += 1
    _METRICS["llm_calls"] += 1
    acquired = False
    try:
        async with _LLM_SEMAPHORE:
            acquired = True
            _METRICS["queued"] -= 1
            queue_wait = (time.perf_counter() - queued_at) * 1000
            _METRICS["queue_wait_ms"] += queue_wait
            _METRICS["generating"] += 1
            try:
                text = await _chat_once(system_prompt, messages, options, selection)
            except LLMError as first_error:
                fallback = fallback_selection(selection, str(first_error))
                if not fallback:
                    raise
                text = await _chat_once(system_prompt, messages, options, fallback)
                selection = fallback
            _METRICS["completed"] += 1
            return text
    except asyncio.CancelledError:
        _METRICS["cancelled"] += 1
        raise
    except Exception:
        _METRICS["failed"] += 1
        raise
    finally:
        if not acquired and _METRICS["queued"] > 0:
            _METRICS["queued"] -= 1
        if _METRICS["generating"] > 0:
            _METRICS["generating"] -= 1
        total_ms = (time.perf_counter() - started) * 1000
        _METRICS["llm_total_ms"] += total_ms
        logger.info("LLM completion backend=%s model=%s profile=%s total_ms=%.0f queue_wait_ms=%.0f llm_calls=%s chars=%s fallback=%s", LLM_BACKEND, selection.selected_model, selected_profile, total_ms, (time.perf_counter() - queued_at) * 1000, _METRICS["llm_calls"], len(locals().get("text", "")), selection.used_fallback)


async def _chat_once(system_prompt: str, messages: list[dict], options: dict, selection: ModelSelection) -> str:
    if LLM_BACKEND in {"deepseek-harness", "dsh"}:
        from harness_backend import HarnessBackendError, harness_chat
        try:
            return await harness_chat(system_prompt, messages, options, selection.selected_model)
        except HarnessBackendError as exc:
            if not DSH_FALLBACK_TO_OLLAMA:
                raise LLMError(str(exc)) from exc
            logger.warning("DeepSeek Harness no disponible; fallback directo a Ollama local: %s", exc)
            return await _ollama_chat(system_prompt, messages, options, selection.selected_model)
    if LLM_BACKEND == "ollama":
        return await _ollama_chat(system_prompt, messages, options, selection.selected_model)
    if LLM_BACKEND == "openai":
        return await _openai_chat(system_prompt, messages, options, selection.selected_model)
    if LLM_BACKEND == "anthropic":
        return await _anthropic_chat(system_prompt, messages, options, selection.selected_model)
    if LLM_BACKEND == "mock":
        latest = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if any(marker in system_prompt.casefold() for marker in ("clasificador de intenciones", "clasificador estructurado")):
            return _mock_classifier_response(system_prompt, latest)
        return f"Modo técnico de prueba activo. Recibí: {latest[:180]}" if latest else "Modo técnico de prueba activo."
    raise LLMError(f"Backend LLM no soportado: {LLM_BACKEND}")


async def chat_completion_stream(system_prompt: str, messages: list[dict], profile: str | None = None, context_override: int | None = None) -> AsyncIterator[str]:
    """Entrega fragmentos visibles, registra TTFT y permite cancelación queued."""
    selected_profile = resolve_profile(_latest_user_message(messages), requested=profile or LLM_PROFILE)
    selection = selection_for(selected_profile)
    options = profile_options(selected_profile, context_override)
    emitted = False
    started = time.perf_counter()
    queued_at = time.perf_counter()
    _METRICS["queued"] += 1
    _METRICS["llm_calls"] += 1
    acquired = False
    try:
        async with _LLM_SEMAPHORE:
            acquired = True
            _METRICS["queued"] -= 1
            _METRICS["queue_wait_ms"] += (time.perf_counter() - queued_at) * 1000
            _METRICS["generating"] += 1
            try:
                async for chunk in _stream_once(system_prompt, messages, options, selection):
                    emitted = True
                    yield chunk
            except LLMError as first_error:
                fallback = fallback_selection(selection, str(first_error))
                if not fallback or emitted:
                    _METRICS["failed"] += 1
                    raise
                async for chunk in _stream_once(system_prompt, messages, options, fallback):
                    emitted = True
                    yield chunk
                selection = fallback
            _METRICS["completed"] += 1
    except asyncio.CancelledError:
        _METRICS["cancelled"] += 1
        logger.info("LLM stream cancelado backend=%s model=%s profile=%s", LLM_BACKEND, selection.selected_model, selected_profile)
        raise
    except Exception:
        _METRICS["failed"] += 1
        raise
    finally:
        if not acquired and _METRICS["queued"] > 0:
            _METRICS["queued"] -= 1
        if _METRICS["generating"] > 0:
            _METRICS["generating"] -= 1
        total_ms = (time.perf_counter() - started) * 1000
        _METRICS["llm_total_ms"] += total_ms
        logger.info("LLM stream backend=%s model=%s profile=%s total_ms=%.0f queue_wait_ms=%.0f llm_calls=%s fallback=%s", LLM_BACKEND, selection.selected_model, selected_profile, total_ms, (time.perf_counter() - queued_at) * 1000, _METRICS["llm_calls"], selection.used_fallback)


async def _stream_once(system_prompt: str, messages: list[dict], options: dict, selection: ModelSelection) -> AsyncIterator[str]:
    if not LLM_STREAM_ENABLED:
        yield await _chat_once(system_prompt, messages, options, selection)
        return
    if LLM_BACKEND in {"deepseek-harness", "dsh"}:
        from harness_backend import HarnessBackendError, harness_chat
        try:
            yield await harness_chat(system_prompt, messages, options, selection.selected_model)
            return
        except HarnessBackendError as exc:
            if not DSH_FALLBACK_TO_OLLAMA:
                raise LLMError(str(exc)) from exc
            logger.warning("DeepSeek Harness no disponible durante streaming; fallback a Ollama local: %s", exc)
            async for chunk in _ollama_chat_stream(system_prompt, messages, options, selection.selected_model):
                yield chunk
            return
    if LLM_BACKEND == "ollama":
        async for chunk in _ollama_chat_stream(system_prompt, messages, options, selection.selected_model):
            yield chunk
        return
    if LLM_BACKEND == "openai":
        async for chunk in _openai_chat_stream(system_prompt, messages, options, selection.selected_model):
            yield chunk
        return
    if LLM_BACKEND == "anthropic":
        async for chunk in _anthropic_chat_stream(system_prompt, messages, options, selection.selected_model):
            yield chunk
        return
    if LLM_BACKEND == "mock":
        latest = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        yield f"Modo técnico de prueba activo. Recibí: {latest[:180]}" if latest else "Modo técnico de prueba activo."
        return
    raise LLMError(f"Backend LLM no soportado: {LLM_BACKEND}")


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(LLM_TIMEOUT_SECONDS, connect=min(15.0, LLM_TIMEOUT_SECONDS), read=LLM_TIMEOUT_SECONDS, write=30.0, pool=30.0)


async def _post_json(url: str, **kwargs) -> dict:
    last_error: Exception | None = None
    for attempt in range(LLM_RETRY_COUNT + 1):
        try:
            client = await _http_client()
            response = await client.post(url, **kwargs)
            response.raise_for_status()
            return response.json()
        except asyncio.CancelledError:
            raise
        except httpx.ConnectError as exc:
            last_error = exc
            if attempt < LLM_RETRY_COUNT:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            raise LLMError("No se pudo conectar con el backend LLM configurado. El Core sigue funcionando.") from exc
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < LLM_RETRY_COUNT:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            raise LLMError(f"El backend LLM agotó el tiempo de espera ({LLM_TIMEOUT_SECONDS:g} s). Puedes cancelar y reintentar sin cerrar GAIA.") from exc
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                detail = exc.response.json().get("error", {}).get("message", "")
            except ValueError:
                detail = exc.response.text[:240]
            logger.warning("Backend LLM devolvió HTTP %s: %s", exc.response.status_code, detail)
            if exc.response.status_code == 404:
                raise LLMError(f"El modelo configurado no está disponible en el backend: {detail or 'modelo no encontrado'}.") from exc
            raise LLMError(f"El backend LLM devolvió HTTP {exc.response.status_code}: {detail or 'error remoto'}.") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMError("El backend LLM devolvió una respuesta inválida.") from exc
    raise LLMError(f"Falló el backend LLM: {last_error}")


def _payload_messages(system_prompt: str, messages: list[dict]) -> list[dict]:
    return [{"role": "system", "content": system_prompt}, *messages]


def _ollama_options(options: dict) -> dict:
    return {"temperature": options["temperature"], "num_predict": options["num_predict"], "num_ctx": options.get("num_ctx", LLM_CONTEXT)}


async def _ollama_chat(system_prompt: str, messages: list[dict], options: dict, model: str) -> str:
    payload = {"model": model, "messages": _payload_messages(system_prompt, messages), "stream": False, "keep_alive": LLM_KEEP_ALIVE, "options": _ollama_options(options)}
    data = await _post_json(f"{OLLAMA_URL}/api/chat", json=payload)
    text = _visible_text(data.get("message", {}).get("content", ""))
    if not text:
        logger.warning("event=llm_empty_visible_output backend=ollama model=%s reasoning_filtered=true", model)
        return ""
    return text


async def _openai_chat(system_prompt: str, messages: list[dict], options: dict, model: str) -> str:
    if not OPENAI_API_KEY:
        raise LLMError("No hay API key de OpenAI configurada en .env.")
    data = await _post_json("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}, json={"model": model, "messages": _payload_messages(system_prompt, messages), "temperature": options["temperature"], "max_tokens": options["num_predict"]})
    text = _visible_text(data["choices"][0]["message"]["content"])
    if not text:
        logger.warning("event=llm_empty_visible_output backend=openai model=%s reasoning_filtered=true", model)
        return ""
    return text


async def _anthropic_chat(system_prompt: str, messages: list[dict], options: dict, model: str) -> str:
    if not ANTHROPIC_API_KEY:
        raise LLMError("No hay API key de Anthropic configurada en .env.")
    data = await _post_json("https://api.anthropic.com/v1/messages", headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}, json={"model": model, "system": system_prompt, "messages": messages, "temperature": options["temperature"], "max_tokens": options["num_predict"]})
    text = _visible_text(data["content"][0]["text"])
    if not text:
        logger.warning("event=llm_empty_visible_output backend=anthropic model=%s reasoning_filtered=true", model)
        return ""
    return text


async def _ollama_chat_stream(system_prompt: str, messages: list[dict], options: dict, model: str) -> AsyncIterator[str]:
    payload = {"model": model, "messages": _payload_messages(system_prompt, messages), "stream": True, "keep_alive": LLM_KEEP_ALIVE, "options": _ollama_options(options)}
    try:
        client = await _http_client()
        async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as response:
                if response.status_code == 404:
                    raise LLMError(f"Ollama no encuentra el modelo {model!r}. Instálalo o configura GAIA_MODEL_FALLBACK.")
                response.raise_for_status()
                filterer = _ReasoningFilter()
                first_token = True
                started = time.perf_counter()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug("Ignorando línea no JSON de Ollama")
                        continue
                    message = data.get("message") or {}
                    chunk = message.get("content", "")
                    if message.get("thinking") or not chunk:
                        continue
                    visible = filterer.feed(chunk)
                    if visible:
                        if first_token:
                            first_token_ms = (time.perf_counter() - started) * 1000
                            _METRICS["llm_ttft_ms"] += first_token_ms
                            logger.info("LLM first_token_ms=%.0f backend=ollama model=%s", first_token_ms, model)
                            first_token = False
                        yield visible
                tail = filterer.finish()
                if tail:
                    yield tail
    except asyncio.CancelledError:
        logger.info("Ollama stream cancellation requested model=%s", model)
        raise
    except httpx.ConnectError as exc:
        raise LLMError("No se pudo conectar con Ollama. Comprueba que `ollama serve` esté activo.") from exc
    except httpx.TimeoutException as exc:
        raise LLMError(f"Ollama tardó más de {LLM_TIMEOUT_SECONDS:g} s. El Core sigue funcionando; puedes reintentar.") from exc
    except httpx.HTTPStatusError as exc:
        raise LLMError(f"Ollama devolvió HTTP {exc.response.status_code}.") from exc


async def _openai_chat_stream(system_prompt: str, messages: list[dict], options: dict, model: str) -> AsyncIterator[str]:
    if not OPENAI_API_KEY:
        raise LLMError("No hay API key de OpenAI configurada en .env.")
    payload = {"model": model, "messages": _payload_messages(system_prompt, messages), "temperature": options["temperature"], "max_tokens": options["num_predict"], "stream": True}
    try:
        client = await _http_client()
        async with client.stream("POST", "https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json=payload) as response:
                response.raise_for_status()
                filterer = _ReasoningFilter()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:]
                    if raw == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    chunk = ((data.get("choices") or [{}])[0].get("delta") or {}).get("content", "")
                    visible = filterer.feed(chunk)
                    if visible:
                        yield visible
                tail = filterer.finish()
                if tail:
                    yield tail
    except asyncio.CancelledError:
        raise
    except httpx.ConnectError as exc:
        raise LLMError("No se pudo conectar con OpenAI.") from exc
    except httpx.TimeoutException as exc:
        raise LLMError(f"OpenAI agotó el tiempo de espera ({LLM_TIMEOUT_SECONDS:g} s).") from exc
    except httpx.HTTPStatusError as exc:
        raise LLMError(f"OpenAI devolvió HTTP {exc.response.status_code}.") from exc


async def _anthropic_chat_stream(system_prompt: str, messages: list[dict], options: dict, model: str) -> AsyncIterator[str]:
    if not ANTHROPIC_API_KEY:
        raise LLMError("No hay API key de Anthropic configurada en .env.")
    payload = {"model": model, "system": system_prompt, "messages": messages, "temperature": options["temperature"], "max_tokens": options["num_predict"], "stream": True}
    try:
        client = await _http_client()
        async with client.stream("POST", "https://api.anthropic.com/v1/messages", headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"}, json=payload) as response:
                response.raise_for_status()
                filterer = _ReasoningFilter()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        data = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    if data.get("type") != "content_block_delta":
                        continue
                    visible = filterer.feed((data.get("delta") or {}).get("text", ""))
                    if visible:
                        yield visible
                tail = filterer.finish()
                if tail:
                    yield tail
    except asyncio.CancelledError:
        raise
    except httpx.ConnectError as exc:
        raise LLMError("No se pudo conectar con Anthropic.") from exc
    except httpx.TimeoutException as exc:
        raise LLMError(f"Anthropic agotó el tiempo de espera ({LLM_TIMEOUT_SECONDS:g} s).") from exc
    except httpx.HTTPStatusError as exc:
        raise LLMError(f"Anthropic devolvió HTTP {exc.response.status_code}.") from exc


class _ReasoningFilter:
    def __init__(self) -> None:
        self.buffer = ""
        self.in_thinking = False

    def feed(self, chunk: str) -> str:
        if not LLM_HIDE_REASONING:
            return chunk
        self.buffer += chunk
        output: list[str] = []
        opening_tag = "<think>"
        closing_tag = "</think>"
        while self.buffer:
            if self.in_thinking:
                close = self.buffer.find(closing_tag)
                if close < 0:
                    keep = len(closing_tag) - 1
                    self.buffer = self.buffer[-keep:] if keep else ""
                    break
                self.buffer = self.buffer[close + len(closing_tag):]
                self.in_thinking = False
                continue
            opening = self.buffer.find(opening_tag)
            if opening >= 0:
                output.append(self.buffer[:opening])
                self.buffer = self.buffer[opening + len(opening_tag):]
                self.in_thinking = True
                continue
            keep = len(opening_tag) - 1
            if len(self.buffer) <= keep:
                break
            output.append(self.buffer[:-keep])
            self.buffer = self.buffer[-keep:]
        return "".join(output)

    def finish(self) -> str:
        if self.in_thinking:
            self.buffer = ""
            return ""
        result = self.buffer
        self.buffer = ""
        return result


def _visible_text(text: str) -> str:
    if not text:
        return ""
    filterer = _ReasoningFilter()
    return (filterer.feed(str(text)) + filterer.finish()).strip()


async def check_backend() -> dict:
    info = {"backend": LLM_BACKEND, "model": LLM_MODEL, "profile": LLM_PROFILE, "streaming": LLM_STREAM_ENABLED, "hide_reasoning": LLM_HIDE_REASONING, "timeout_seconds": LLM_TIMEOUT_SECONDS, "keep_alive": LLM_KEEP_ALIVE, "context": LLM_CONTEXT, "status": "unknown"}
    try:
        if LLM_BACKEND in {"deepseek-harness", "dsh"}:
            from harness_backend import harness_health
            info.update(await harness_health())
        elif LLM_BACKEND == "ollama":
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{OLLAMA_URL}/api/tags")
                response.raise_for_status()
                models = [m.get("name", "") for m in response.json().get("models", [])]
            effective_profile = resolve_profile(requested=LLM_PROFILE)
            selection = selection_for(effective_profile, models)
            preferred_installed = selection.preferred_model in models
            if selection.used_fallback:
                status = "fallback_model"
                hint = f"El modelo preferido {selection.preferred_model} no está instalado; se usa {selection.selected_model}."
            elif not preferred_installed:
                status = "model_missing"
                hint = f"El modelo {selection.preferred_model} no está instalado. Ejecuta: ollama pull {selection.preferred_model}"
            else:
                status = "online"
                hint = ""
            info.update(status=status, reachable=True, available_models=models, model_loaded=preferred_installed, selected_model=selection.selected_model, model_selection=selection.as_dict(), hint=hint)
        elif LLM_BACKEND == "openai":
            info["status"] = "configured" if OPENAI_API_KEY else "no_api_key"
        elif LLM_BACKEND == "anthropic":
            info["status"] = "configured" if ANTHROPIC_API_KEY else "no_api_key"
        elif LLM_BACKEND == "mock":
            info.update(status="test_only", model="echo", selected_model="echo")
        else:
            info["status"] = "invalid_backend"
    except Exception as exc:
        info.update(status="offline", reachable=False, error=str(exc), hint="Ollama no está accesible. Ejecuta `ollama serve`; GAIA no descargará modelos automáticamente.")
    return info
