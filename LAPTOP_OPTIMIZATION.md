# GAIA-AI v0.9.2 — Laptop Optimization Guide

## Perfil recomendado

Para una laptop Windows de clase ASUS TUF con i5-12500H, aproximadamente 48 GB de RAM, RTX 3050 Laptop de 4 GB de VRAM, SSD/NVMe, múltiples monitores y sesiones largas, el punto de partida recomendado es:

```dotenv
GAIA_HARDWARE_PROFILE=laptop_balanced
GAIA_PERFORMANCE_PROFILE=balanced
LUMEN_LLM_MODEL=qwen3.5:4b
GAIA_MAX_CONCURRENT_LLM_REQUESTS=1
GAIA_MEMORY_CONTEXT_MAX_CHARS=4096
GAIA_MEMORY_RELEVANCE_LIMIT=8
GAIA_AUTOMATION_MODE=OFF
LUMEN_PROACTIVE_ENABLED=false
```

El modelo mostrado es una configuración de ejemplo y no se instala ni se cambia automáticamente. `laptop_balanced` es una política de consumo, no una promesa de rendimiento, temperatura o disponibilidad de GPU.

## Qué ajusta v0.9.2

El `ResourceGovernor` observa señales disponibles y produce una política read-only para trabajo no interactivo. En balanced laptop usa multiplicadores conservadores para scheduler y watchers, mantiene `background_concurrency=1`, limita el contexto recomendado a 4096 y permite una proactividad LLM reservada de una llamada por minuto si la función estuviera explícitamente habilitada. En batería o presión sostenida reduce aún más el background, difiere consolidation y desactiva la proactividad reservada.

| Perfil | Uso objetivo | Background | Contexto recomendado | Keep-alive informativo |
|---|---|---:|---:|---:|
| `laptop_eco` | Batería o calor | Muy conservador | 3072 | `0` |
| `laptop_balanced` | Uso diario recomendado | Conservador | 4096 | `5m` |
| `laptop_performance` | Latencia prioritaria, con monitorización | Menos conservador | 8192 como cap de política | `10m` |
| `desktop_balanced` | Desktop configurado explícitamente | Normal | 4096 | `10m` |
| `desktop_performance` | Desktop con recursos medidos | Normal/alto | 8192 | `10m` |
| `custom` | Política administrada por el usuario | Explícito | 4096 por defecto | `10m` |

La tabla describe políticas recomendadas, no una mutación automática. El transporte LLM conserva el modelo y keep-alive configurados salvo que el usuario cambie explícitamente la configuración de la aplicación.

## Restricción de VRAM

Con 4 GB de VRAM no se deben cargar automáticamente modelos locales adicionales, un modelo de visión permanente, embeddings pesados ni una instancia paralela de Whisper. Voz permanece push-to-talk y los backends opcionales son lazy. La ausencia de una medición real de VRAM en el sandbox se reporta como `NOT MEASURED`.

## Sesiones largas y batería

Para sesiones largas, se recomienda mantener proactividad y automatización apagadas inicialmente, observar `/api/diagnostics/performance` y activar capacidades una por una. El governor no termina la solicitud interactiva del usuario: la prioridad interactiva es superior a tareas de mantenimiento. Si la batería no está disponible como señal, no se asume que el equipo está conectado a AC ni se inventa un estado térmico.

## Caché e imports

Desktop context utiliza un TTL corto y se invalida al solicitar refresh. Trusted Folders utiliza un TTL bounded configurable mediante `GAIA_TRUSTED_FOLDERS_TTL_SECONDS` y se invalida después de grant/update/revoke. UIA, screenshot, PIL, audio, Whisper y otros backends opcionales no deben convertirse en imports eager solo para abrir el Core.

## Operación segura

El governor no controla ventiladores, voltaje, overclock, plan de energía Windows, prioridad de procesos, settings NVIDIA o modelos de Ollama. Tampoco concede permisos. Las acciones siguen requiriendo clasificación, policy, confirmación cuando corresponde, preflight, claim del host y resultado verificado.

## Cómo medir en el equipo físico

La validación física debe realizarse con el usuario presente y sin tratar los números como garantía. Registrar por separado: perfil efectivo, modelo, RAM/VRAM, CPU/GPU, temperatura sostenida, estado AC/batería, RSS del Core y Ollama, tiempo de primera respuesta, cola, scheduler/watchers, cantidad de modelos residentes y comportamiento después de varias horas. Repetir en AC y batería, con uno y varios monitores. La suite automatizada de v0.9.2 no sustituye ese harness y el sandbox actual no lo ejecuta.
