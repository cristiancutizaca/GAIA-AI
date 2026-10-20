HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.5.4.2 — Requisitos del parche

## Propósito y alcance

GAIA-AI v0.5.4.2 es un **parche quirúrgico** sobre v0.5.4.1-pc. Su objetivo es corregir dos defectos observados en la frontera entre clasificación de solicitudes, Action Engine y respuesta posterior a una acción verificada. El parche no redefine la arquitectura, no cambia el modelo local, no amplía el allowlist de acciones y no modifica el prototipo Android.

La autoridad factual sigue siendo `VerifiedActionResult`: el cliente y la personalidad de GAIA pueden presentar el resultado verificado, pero el texto generado posteriormente no puede convertirse en una fuente adicional de efectos del sistema.

## Requisitos funcionales

| ID | Requisito | Criterio verificable |
|---|---|---|
| A-01 | Las peticiones externas expresadas con marcos naturales se clasifican como `ACTION_REQUEST`. | Las variantes `¿puedes abrir X?`, `me abres X`, `quiero que abras X`, `por favor abre X`, `necesito que abras X`, `podrías abrir X` y `hazme el favor de abrir X` pasan la detección semántica de marco. |
| A-02 | La detección no debe depender de enumerar únicamente las frases del caso de prueba. | La implementación normaliza marcos lingüísticos, auxiliares, pronombres y conjugaciones antes de consultar la semántica externa, manteniendo el allowlist como autoridad de ejecución. |
| A-03 | Las acciones allowlisted en lenguaje natural deben resolver al mismo intent seguro que su forma imperativa. | `¿puedes abrir Spotify?`, `me abres la calculadora`, `quiero que abras el bloc de notas`, `quiero Spotify abierto` y `por favor, abre VS Code` se resuelven a intents existentes. |
| A-04 | Las acciones no allowlisted deben fallar de forma determinista y segura. | Una solicitud de apagar el equipo, cerrar una aplicación o ejecutar una capacidad no registrada devuelve el fallback de capacidad no disponible; no se crea una acción pendiente. |
| B-01 | El post-action debe estar bloqueado al resultado verificado. | El prefijo factual conserva mensaje, éxito/fallo, acción, datos y alcance del resultado producido por el Core. |
| B-02 | El LLM no puede añadir efectos no verificados. | Afirmaciones como `También cerré Spotify` se eliminan o sustituyen por el fallback factual, sin registrar ni ejecutar el supuesto efecto. |
| B-03 | Se mantiene la personalidad segura de GAIA. | Un comentario humorístico se conserva únicamente cuando no contiene verbos de efecto no verificados, patrones de inyección ni JSON/estructura de acción. |
| B-04 | Las preguntas de capacidad no activan acciones. | Preguntas como `¿Qué aplicaciones puedes abrir?`, `¿Tienes capacidad para abrir Spotify?`, `¿Cómo funciona?` y `¿Qué pasaría si...?` permanecen en conversación informativa y no generan acción pendiente. |

## Requisitos de seguridad y no regresión

La ejecución continúa limitada al Action Engine allowlisted. No se permite `shell=True`, `os.system`, `eval`, `exec` ni ejecutar texto producido por el modelo. El cliente PC conserva la validación local, RBAC, confirmación y los timeouts existentes. La memoria SQLite, SSE, voz, backups, deduplicación de proyectos, fallback de salida vacía, concurrencia Qwen y contratos heredados de v0.4/v0.5.4.1 deben continuar pasando sus regresiones.

El parche no incluye Android, LAN, automatización de navegador, integración Spotify API, multimedia nueva, automatización de ratón/teclado, shell, agentes nuevos, cambio de modelo ni rediseño de personalidad. La versión del Core/PC pasa a `0.5.4.2-pc`; el Android permanece sin cambios de versión por alcance explícito.

## Evidencia requerida

La evidencia de reproducción de los dos fallos en la base v0.5.4.1 se conserva en `BASELINE_V0541_V0542.txt`. La cobertura automatizada principal está en `tests/action_request_semantics_test.py` y `tests/post_action_claim_scope_test.py`; las regresiones existentes se ejecutan mediante los scripts directos de `tests/`, `compileall` y las búsquedas estáticas de seguridad del procedimiento de release.

El release solo puede declararse válido si `release_package_test.py` pasa, `build_release.py` crea un ZIP limpio con allowlist y el contenido extraído en un directorio nuevo vuelve a pasar la suite completa. Cualquier fallo crítico impide declarar PASS.

## Entregable

El artefacto final esperado es `GAIA-AI-v0.5.4.2-final.zip`, acompañado de su checksum SHA-256 y de la documentación de README, CHANGELOG, AUDIT, TEST_REPORT, FINAL_VALIDATION, MODIFIED_FILES y KNOWN_LIMITATIONS. El ZIP no debe contener secretos, datos runtime, caches, archivos de entorno privados ni otro ZIP.

## Fuentes internas

Los requisitos se derivan de la especificación de v0.5.4.2 recibida para este proyecto, de la evidencia `BASELINE_V0541_V0542.txt` y de los contratos implementados en `lumen-core/routes/api.py`, `lumen-core/action_intent.py` y sus pruebas directas.
