# Performance v0.6.2

## Objetivo

v0.6.2 conserva las optimizaciones de v0.6.1 y añade observabilidad específica para el flujo multi-dispositivo. El objetivo no es prometer latencias físicas universales, sino mantener una ruta rápida determinista, limitar la concurrencia de inferencias pesadas y exponer métricas suficientes para diagnosticar cola, generación y cancelación.

## Métricas

`lumen-core/llm.py` mantiene contadores de llamadas y estados de ciclo de vida: `queued`, `generating`, `completed`, `cancelled` y `failed`. También registra `queue_wait_ms`, `llm_ttft_ms`, `llm_total_ms` y `llm_calls` en el alcance de una respuesta. `GET /api/diagnostics/performance` devuelve esas métricas junto al backend, estado de salud, perfil y presupuesto de contexto sin incluir prompts ni secretos.

| Superficie | Medición | Evidencia |
|---|---|---|
| Cola LLM | FIFO, cancelación queued, semaphore y contadores | `llm_queue_test.py` |
| Concurrencia | Máximo configurable de inferencias pesadas | `llm_concurrency_test.py` |
| Health | No espera un slot de generación | `llm_health_test.py` |
| Fast paths | Acciones deterministas sin post-action LLM innecesario | `action_grounding_test.py`, `action_request_semantics_test.py` |
| Remote Host | Polling acotado, heartbeat y stop event | `remote_action_host_loop_test.py` |
| Diagnóstico | Contrato API no secreto | `token_security_v062_test.py` |

## Perfiles

`GAIA_PERFORMANCE_PROFILE` admite `eco`, `balanced` y `performance`. El perfil ajusta límites de contexto y cantidad de elementos considerados, pero no cambia por sorpresa el modelo ni elimina controles de autorización. `GAIA_MAX_CONCURRENT_LLM_REQUESTS` limita la concurrencia pesada; el default es conservador.

## Interpretación

Las métricas del mock y de la suite local sirven para comprobar contratos, no para estimar una máquina Windows concreta. Ollama, modelo, GPU/CPU, audio, red LAN y Flutter deben medirse en el entorno de despliegue. Un aumento de `queue_wait_ms` sugiere saturación del semaphore; un aumento de `llm_total_ms` puede deberse al backend o al modelo; una acción remota además incorpora RTT, polling y ejecución local.

## Operación segura

El endpoint de performance requiere autenticación diagnóstica. Los logs no deben registrar tokens, hashes, prompts completos ni audio. El host remoto no hace busy-wait: usa `Event.wait()` con intervalo de polling y cierre idempotente.

> PENDING: no se dispone de Flutter/Android SDK ni de una máquina Windows física dentro del sandbox; no se declara un benchmark APK, GPU, micrófono, LAN real o TTS físico.
