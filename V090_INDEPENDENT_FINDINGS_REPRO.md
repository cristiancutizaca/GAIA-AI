HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# v0.9.0 — Reproducción de hallazgos independientes

> **Método:** se ejecutó `tools/reproduce_independent_findings_v091.py` contra una extracción limpia de v0.9.0, usando DB temporal, tokens sintéticos y backend LLM mock. Cada hallazgo se reprodujo antes de modificar el comportamiento productivo.

| ID | Hallazgo | Resultado | Evidencia observada |
|---|---|---|---|
| A | Fuga de memoria de dispositivo en el prompt de chat | **CONFIRMED** | `ANDROID-A-PRIVATE-METADATA dispositivo privado` de `android-a` apareció en el prompt preparado para `android-b`; el caller no propagaba `device_id` hacia `get_context_bundle`/`retrieve` |
| B | Consolidación sin ownership durable | **CONFIRMED** | `android-b` pudo llamar `/api/memory/advanced/consolidate` para `session-a` y recibió HTTP 200 con `SESIÓN-A-CONTENIDO-PRIVADO` |
| C | Colisión de namespace/dedup | **CONFIRMED** | `device.host` de `android-b` marcó como `superseded` el item de `android-a`; apareció una fila de history de contradicción |
| D | Filtro de provenance con regex frágil | **CONFIRMED** | `_BLOCKED_SOURCE_RE` no bloqueó `event` ni `event:123` porque el patrón contenía caracteres backspace en lugar de límites de palabra |
| E | `limit` no limita `context_text` | **CONFIRMED** | `retrieve(limit=2)` devolvió `items_length=2`, pero `context_text` contenía 10 líneas de marcadores; `retrieval_ms=0` también quedó confirmado como métrica falsa |
| F | Cooldown de Automation en cold boot | **CONFIRMED** | Con `monotonic=10` y cooldown 300, la primera coincidencia no ejecutó ni registró `last_run`; `runs_started=0` |

## Nota sobre Bug A

La primera ejecución exploratoria con una consulta que no contenía términos del marcador no produjo fuga porque el retrieval lexical no seleccionó el item. Esa variante fue clasificada como **no concluyente**, no como ausencia del defecto. Se repitió con una consulta lexicalmente relevante sobre “dispositivo” y se confirmó la fuga de alcance. Esto evita confundir falta de relevancia con aislamiento correcto.

## Reproducción

```bash
cd /home/ubuntu/GAIA-AI-v0.9.1-dev/GAIA-AI-v0.9.1
env PYTHONDONTWRITEBYTECODE=1 python3 tools/reproduce_independent_findings_v091.py
```

El reproductor solo crea datos temporales, no toca ZIPs congelados, no descarga modelos y no debe incluirse como evidencia de una prueba física. Después de esta ejecución se inicia el trabajo de corrección v0.9.1 en una copia separada del baseline.

## Decisión de Stage A

Los seis hallazgos son confirmados y bloquean performance work. Primero se corregirán propagación de `MemoryAccessContext`, ownership durable de sesiones/consolidación, namespace persistente, clasificación estructurada de provenance, selección única bounded con métrica monotonic y cooldown cold-boot. La aceptación requerirá pruebas de regresión separadas y suite histórica completa.
