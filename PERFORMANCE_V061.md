# GAIA-AI v0.6.1 — Performance Report

La optimización mantiene separado el estado ocupado del LLM del estado general del sistema. Las capabilities deterministas continúan por fast path y no esperan a Qwen cuando la policy permite ejecutar sin generación.

| Medición | Implementación | Evidencia |
|---|---|---|
| Cliente HTTP | `httpx.AsyncClient` reutilizado por event loop y cerrado en lifespan shutdown. | `lumen-core/llm.py`, `main.py`. |
| Pool y timeout | Pool persistente, timeout configurable y retries acotados. | `_http_client()`, `_timeout()`, `_post_json()`. |
| Cola | Semaphore FIFO con estados observables `queued`, `generating`, `completed`, `cancelled`, `failed`. | `llm.metrics()`, `llm_queue_test.py`. |
| Cancelación | Una solicitud cancelada mientras espera el slot no llega al backend. | `llm_queue_test.py`. |
| TTFT | El primer token visible de streaming Ollama registra `llm_ttft_ms`. | `_ollama_chat_stream()`. |
| Fast paths | Calculator, volume, system status, projects y post-action se mantienen en cero llamadas LLM. | `v0543_performance_test.py`. |
| Contexto | `eco`, `balanced` y `performance` ajustan límites adaptativamente; se mide `last_prompt_context_chars`. | `config.py`, `model_router.py`, `routes/api.py`. |

El perfil por defecto es `balanced`. Ningún perfil cambia automáticamente el modelo configurado. Los límites se aplican a contexto y salida, no a la autoridad ni al catálogo de capabilities.
