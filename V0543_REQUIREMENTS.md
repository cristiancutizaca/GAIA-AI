HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.5.4.3 — Requisitos de hardening

## Alcance

v0.5.4.3 es un parche de hardening sobre v0.5.4.2. Cierra los huecos de grounding identificados en `V0543_BASELINE.md` sin ampliar arbitrariamente el allowlist de acciones ni convertir la personalidad en autoridad de ejecución.

## Requisitos obligatorios

| ID | Requisito | Evidencia |
|---|---|---|
| A1 | `VerifiedActionResult` es la única autoridad factual de una acción real. | `_fact_locked_base()` y `post_action_claim_scope_test.py` |
| A2 | Una acción verificada simple no realiza una inferencia post-action innecesaria. | `generated_by_llm=false`, `v0543_performance_test.py` |
| A3 | Un resultado solo puede conservar un comentario de personalidad code-owned y seguro. | `_SAFE_POST_ACTION_SUFFIXES`, `post_action_claim_scope_test.py` |
| A4 | Una conversación sin resultado verificado no puede afirmar ejecución en primera persona. | `_has_unverified_execution_report()`, `action_request_semantics_test.py` |
| A5 | Los marcos `te encargo`, `cuando puedas`, `si tienes un momento`, `en cuanto puedas` y `no te olvides de` se detectan como solicitudes externas. | `action_request_semantics_test.py` |
| A6 | Negaciones y preguntas informativas no ejecutan acciones. | `action_request_semantics_test.py` |
| A7 | Las acciones no allowlisted continúan en capability failure determinista y no pasan a chat libre. | `action_request_semantics_test.py`, `action_grounding_test.py` |
| A8 | El release v0.5.4.3 se construye con allowlist, checksum y validación desde extracción limpia. | `tools/build_release.py`, `tests/release_package_test.py` |

## Restricciones

No se implementa shell libre, `eval`, `exec`, `os.system`, comandos arbitrarios del LLM, automatización de coordenadas, browser agent, elevación automática, borrado masivo, gestión de credenciales ni acceso público. El modelo no puede crear capacidades, modificar permisos, inventar resultados ni ejecutar texto post-action.

La normalización usa marcos lingüísticos estructurales y no una lista de nombres de aplicaciones. Las capacidades siguen limitadas por el registry y la validación local del cliente PC. Android, LAN y nuevas capacidades permanecen sin cambios funcionales en este parche.

## Criterio de aceptación

El release solo puede declararse PASS si pasan los tests históricos, las nuevas regresiones de semantics y scope, compileall, los greps de seguridad, `release_package_test.py`, el build reproducible y la suite completa desde el ZIP extraído en una ruta limpia. La evidencia física se etiqueta por separado como `PHYSICAL`, `AUTOMATED`, `MOCK`, `STATIC` o `NOT TESTED`.
