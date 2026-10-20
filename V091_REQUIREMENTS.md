HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.9.1 — Memory Isolation, Ownership & Correctness

**Estado:** candidata a freeze; no se considera validada hasta completar clean ZIP, reproducibilidad e inventario final de tests.

| ID | Criterio | Evidencia / contrato |
|---|---|---|
| A-01 | Baseline v0.9.0 extraído y checksum verificado | `/home/ubuntu/gaia-v091-baseline-clean`; validación previa 94/94 PASS |
| A-02 | Reproducción independiente de Bug A | `V090_INDEPENDENT_FINDINGS_REPRO.md`; marcador de android-a se inyectó en prompt para android-b |
| A-03 | Propagación end-to-end de `MemoryAccessContext` | `memory.py`, `routes/api.py`, chat normal/streaming, context bundle y retrieval |
| A-04 | Aislamiento de prompt por dispositivo | `advanced_memory_v091_hardening_test.py`; android-b no recibe marcador de android-a |
| A-05 | Ownership durable de sesión | schema 9, tabla `session_owners`, inferencia conservadora: una identidad activa o cuarentena |
| A-06 | Consolidación cross-device bloqueada | `advanced_memory_v091_hardening_test.py`; phone-b recibe HTTP 403 contra session-a y phone-a 200 |
| A-07 | History/summary/context/list sessions aislados | rutas API devuelven 404 fuera de scope y listan solo sesiones del dispositivo |
| A-08 | Namespace persistente y dedup correcto | `namespace_type`, `namespace_id`, unique namespace-aware; device/session/project independientes |
| A-09 | Migración schema 8→9 sin pérdida silenciosa | `_migrate_memory_namespace`, conservación de rows/history y reconstrucción de unique constraint |
| A-10 | Provenance estructurada | prefijos `event`, `automation`, `clipboard`, `screenshot`, `uia` y `temporary_context` bloqueados sin regex de backspace |
| A-11 | Retrieval bounded | `items` y `context_text` se derivan de la misma selección; se respetan `limit` y `max_chars` |
| A-12 | Métrica de retrieval real | `retrieval_ms` usa `time.perf_counter()` y no permanece hardcodeada en cero |
| A-13 | Cooldown cold-boot corregido | `_last_run` solo se consulta si el rule_id existe; primera coincidencia corre, segunda dentro de cooldown no |
| A-14 | Precedence/contradicciones | USER_EXPLICIT confirmado puede reemplazar; inferencia baja queda `candidate`; history conserva evidencia |
| A-15 | Prompt injection tratado como datos | memoria recuperada se etiqueta como contexto y nunca como autoridad del sistema |
| A-16 | Backup/API/CRUD conservan ownership | export/import incluye namespaces; CRUD device-bound y master cross-device solo por opt-in explícito |
| A-17 | Compatibilidad heredada | suite v0.9.0 actualizada a schema 9; Event Engine, remote action, LAN, Android contract y Doctor conservados |
| A-18 | Release gate | `release_package_test` primero, compileall, todos los tests, clean extraction, reproducible rebuild x2, docs ZIP separado |

## Reglas de seguridad

La memoria avanzada no admite secretos, tokens, eventos, automatizaciones, clipboard, screenshots, observaciones UIA ni contextos temporales como memoria semántica durable. Los tokens de dispositivo nunca se usan como contenido ni como provenance. El master puede consultar cross-device únicamente mediante la ruta autorizada que pasa `include_all_devices=True`; el valor seguro por defecto nunca significa “todos los dispositivos”.

## Estados físicos

Flutter/Android, Windows UIA/SMTC, micrófono, TTS/STT real, Ollama real, GPU, LAN/TLS, thermal/CPU/RAM y signing permanecen **PENDING** hasta la matriz física correspondiente. No se convierten en PASS por ejecutar contratos estáticos en Linux.
