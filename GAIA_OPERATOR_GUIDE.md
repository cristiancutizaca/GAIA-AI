# GAIA Operator: automatización local verificable

Esta entrega añade un **orquestador acotado y persistente**, no una IA con libertad para ejecutar comandos. Las plantillas deterministas crean secuencias de acciones del `ActionHost`; cada paso pasa por `preflight`, la capa de capacidades y la auditoría del host.

## Uso rápido (Python 3.11 y dependencias de GAIA)

```bash
python tools/gaia_operator.py plan "GAIA revisa sistema y procesos"
python tools/gaia_operator.py plan "diagnostica ComfyUI y ROCm"
python tools/gaia_operator.py plan "revisa GPU, VRAM y memoria"
python tools/gaia_operator.py list
python tools/gaia_operator.py run job_ID
python tools/gaia_operator.py show job_ID
python tools/gaia_operator.py cancel job_ID
python tools/gaia_operator.py recover job_ID   # solo reintenta lectura tras revisar interrupción
```

Para trabajar con proyectos, primero registra el proyecto en `projects.json`, con ruta real, `trusted: true` y un comando `tests` como lista de argumentos. GAIA **no ejecuta comandos arbitrarios extraídos del chat**.

```bash
python tools/gaia_operator.py plan "revisa proyecto y ejecuta pruebas" --project mi-proyecto
python tools/gaia_operator.py run job_ID       # solo diagnóstico hasta encontrar el paso protegido
python tools/gaia_operator.py approve job_ID   # consentimiento LOCAL explícito
python tools/gaia_operator.py run job_ID
```

El estado se guarda en `~/.gaia/operator.sqlite3`. Puedes cambiarlo con `--db` y establecer el área de trabajo con `--workdir`. `GAIA_OPERATOR_HALT=1` detiene la ejecución de nuevos pasos y `GAIA_SAFE_MODE=1` bloquea operaciones con efectos. Un paso marcado `RUNNING` tras interrupción requiere revisión: **GAIA no repite a ciegas acciones con efectos**. El `ActionHost` conserva su auditoría encadenada en `.gaia_action_audit.jsonl`.

## Alcance verificado y pendientes

- Implementado: planes de 2 a 4 pasos para estado del PC, procesos/red, GPU/RAM y diagnóstico inicial de ComfyUI; ejecución a través de `ActionHost`, preflight, checkpoints SQLite, permiso para lanzar tests de proyectos trusted y parada antes de acciones no aprobadas.
- Implementado: acceso autenticado al SSE del visualizador usando `Authorization: Bearer ...` mediante `fetch` streaming, sin token en la URL.
- No implementado: autoreparación general, LLM que genere planes arbitrarios, acceso sin restricciones al sistema, automatización de instalaciones, gestión completa de temperaturas AMD, monitorización desatendida, conversación por voz E2E. Estos puntos requieren contratos de herramientas y validación física de Windows.
- Si Ollama está apagado, las plantillas funcionan igualmente, pero no constituyen razonamiento de un LLM.

## Pruebas

```bash
python -m pytest -q tests/test_gaia_operator.py tests/test_action_handler_dispatch.py tests/test_functional_action_chain.py
```
