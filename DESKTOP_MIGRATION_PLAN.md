# GAIA-AI v0.9.2 — Desktop Migration Plan

## Principio

v0.9.2 se entrega con defaults seguros para laptop. Un desktop no se infiere como permiso para consumir más recursos. La migración debe ser **explícita, reversible y medible** mediante variables de configuración, sin cambiar el modelo por debajo de la interfaz ni cargar backends adicionales automáticamente.

## Pasos recomendados

| Paso | Acción | Evidencia requerida |
|---|---|---|
| 1 | Registrar modelo, RAM/VRAM, CPU/GPU, sistema operativo y fuente de energía | Inventario local comunicado por el operador |
| 2 | Elegir `GAIA_HARDWARE_PROFILE=desktop_balanced` | `/api/diagnostics/performance` muestra `requested_profile` y `profile` |
| 3 | Mantener `GAIA_PERFORMANCE_PROFILE=balanced` inicialmente | Comparación de latencia/cola/idle |
| 4 | Mantener `GAIA_MAX_CONCURRENT_LLM_REQUESTS=1` | Diagnóstico y prueba de concurrencia |
| 5 | Aumentar explícitamente `GAIA_MEMORY_CONTEXT_MAX_CHARS` solo si hay medición | Prompt metrics y RSS antes/después |
| 6 | Aumentar `GAIA_MEMORY_RELEVANCE_LIMIT` gradualmente, de 8 a 12 o 16 | Exactitud, latencia y memoria observadas |
| 7 | Habilitar `performance` solo durante una ventana controlada | Registro de temperatura, cola y cancelación |
| 8 | Activar vision/embeddings/Whisper solo por feature y bajo demanda | El backend confirma disponibilidad sin descarga automática |
| 9 | Repetir en idle y carga interactiva | No se perjudica la prioridad del usuario |
| 10 | Revertir a laptop balanced si el beneficio no supera el coste | Variables restauradas y nueva lectura de diagnostics |

## Ejemplo explícito

```dotenv
GAIA_HARDWARE_PROFILE=desktop_balanced
GAIA_PERFORMANCE_PROFILE=balanced
GAIA_MEMORY_CONTEXT_MAX_CHARS=8192
GAIA_MEMORY_RELEVANCE_LIMIT=12
GAIA_MAX_CONCURRENT_LLM_REQUESTS=1
```

Este ejemplo no cambia `LUMEN_LLM_MODEL`, no habilita un segundo modelo y no configura GPU. El operador debe verificar que los valores son adecuados para la máquina real.

## Límites que no se modifican

La migración no concede permisos, no cambia ownership, no convierte eventos en memoria, no desactiva confirmaciones de alto riesgo, no habilita shell libre, no cambia el plan de energía del sistema, no muta fan/voltaje/overclock y no expone tokens en logs o diagnostics. El governor sigue siendo una capa de política read-only para background y contexto.

## Rollback

Para volver a la configuración laptop, restaurar:

```dotenv
GAIA_HARDWARE_PROFILE=laptop_balanced
GAIA_PERFORMANCE_PROFILE=balanced
GAIA_MEMORY_CONTEXT_MAX_CHARS=4096
GAIA_MEMORY_RELEVANCE_LIMIT=8
GAIA_MAX_CONCURRENT_LLM_REQUESTS=1
```

Reiniciar el Core, comprobar el perfil efectivo y verificar que la cola de background y el prompt budget regresan a los valores esperados. El rollback de configuración no borra la memoria, sesiones ni backups.

## Futuras ampliaciones

Un perfil desktop futuro podría incorporar caches más grandes, contexto mayor o visión, pero cada ampliación debe tener un contrato de recursos, límites, pruebas y rollback independiente. La versión v0.9.2 no considera esos recursos como habilitados ni declara resultados físicos sin una medición real.
