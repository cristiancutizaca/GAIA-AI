# GAIA-AI v0.5.4.3 — Performance Report

## Método

La medición se ejecutó con `tests/v0543_performance_test.py` sobre el Core local y backend `mock`. El test sustituye temporalmente las funciones de completion por contadores, ejecuta las rutas HTTP reales mediante `TestClient` y restaura las funciones al finalizar. Los tiempos se registran durante la prueba, pero no se presentan como benchmark de hardware porque el entorno es un sandbox compartido.

## Resultados observados

| Flujo | Llamadas LLM observadas | Resultado |
|---|---:|---|
| `abre la calculadora` por `/api/chat` | 0 | Fast path allowlisted |
| `lista proyectos` por `/api/chat` | 0 | Fast path determinista |
| `¿Cómo está mi PC?` por `/api/chat` | 0 | Intent de estado sin classifier |
| `abre la calculadora` por `/api/chat/stream` | 0 | Evento `action` sin streaming LLM |
| Conversación normal | 1 | Una llamada de respuesta conversacional; no se ejecuta classifier previo |
| Completion post-action `git_status` | 0 | Resultado factual; `generated_by_llm=false` |

La salida de aceptación fue:

```text
V0543 PERFORMANCE TEST OK: fast paths=0 LLM, normal conversation=1 LLM, post-action=0 LLM
```

## Interpretación

El routing ya no usa el classifier LLM para conversaciones que no presentan framing de acción externa. Las solicitudes allowlisted conocidas pasan por `detect_action()` y los resultados post-action se cierran desde `VerifiedActionResult`. Una conversación normal mantiene una sola llamada de respuesta, mientras las solicitudes naturales externas desconocidas pueden requerir el classifier para determinar si existe una capability segura.

Estos resultados son `AUTOMATED` sobre backend `MOCK`. No son mediciones de latencia física en Windows, Ollama, GPU o Android y no deben usarse como comparación de hardware.
