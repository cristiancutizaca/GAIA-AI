HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.9.0 — Requisitos y criterios de aceptación

## Alcance

v0.9.0 es la release de **Advanced Memory**. Extiende la continuidad de GAIA-AI con memoria durable explícita, provenance, historial de contradicciones, recuperación híbrida bounded y endpoints HTTP con ownership por dispositivo. La implementación no introduce un modelo LLM obligatorio, no descarga embeddings por defecto y no convierte eventos, capturas, clipboard, tokens o reglas de automatización en memoria semántica automática.

La autoridad sigue en Core, permisos y usuario. La memoria recuperada es contexto auxiliar para el prompt y nunca una fuente de autoridad para policies, grants, ejecución de acciones o secretos.

## Criterios de aceptación

| ID | Criterio | Evidencia requerida | Estado |
|---|---|---|---|
| M-01 | El schema de SQLite es v8 y crea `memory_items` y `memory_item_history` con índices bounded. | `lumen-core/memory.py`; `tests/db_upgrade_test.py`; `tests/advanced_memory_v090_test.py`. | PASS |
| M-02 | Se soportan los ocho kinds: `working`, `session`, `episodic`, `semantic`, `project`, `task`, `preference` y `device_system`. | `advanced_memory.py`, validación de campos y contrato directo v0.9.0. | PASS |
| M-03 | Se soportan las seis fuentes: `USER_EXPLICIT`, `CHAT_INFERRED`, `PROJECT`, `TASK`, `SYSTEM` e `IMPORT`, con provenance, confidence e importance persistidos. | `MemoryItem`, `save_item()` y aserciones de provenance. | PASS |
| M-04 | La deduplicación es determinista por `memory_key + scope + project + content_hash` y no crea duplicados al reinsertar el mismo contenido. | Restricción UNIQUE, `_hash_content()` y prueba de dedup. | PASS |
| M-05 | Una nueva afirmación para la misma clave y scope conserva historial de contradicción y marca la afirmación anterior como `superseded`. | `memory_item_history`, `change_reason='contradiction'` y prueba de historial. | PASS |
| M-06 | La recuperación híbrida usa FTS5 cuando está disponible y fallback lexical, con score determinista que combina lexical, importance, confidence, recency, pinned y bonuses de project/session. | `retrieve()` y `advanced_memory_v090_test.py`. | PASS |
| M-07 | La recuperación respeta `limit` y `max_chars`, devuelve `context_text` bounded y no requiere LLM ni backend de embeddings. | Prueba de token/char budget, `DisabledEmbeddingBackend`, inspección de imports. | PASS |
| M-08 | Scope, project, session y device filtran la lectura; `device_system` exige `device_id`; no hay cruce accidental de memorias fuera del ámbito. | `_scope_clause()`, validación y pruebas de aislamiento. | PASS |
| M-09 | Editar, borrar, fijar y listar tienen semántica explícita: borrados están ocultos en GET normal y solo aparecen con `include_history=True`. | `update_item()`, `delete_item()`, `set_flags()`, `get_item()` y contratos directo/HTTP. | PASS |
| M-10 | Existe auditoría bounded de cambios, con historial de updates, contradicciones y deletes sin exponer secretos. | `get_history()`, endpoint `/api/memory/advanced/audit` y prueba API. | PASS |
| M-11 | Consolidation es determinista, local y sin LLM; solo actualiza `session_summaries` existentes y no inventa memoria nueva. | `consolidate()`, prueba de consolidación y backend mock. | PASS |
| M-12 | Brain Backup exporta `advanced_items` hasta el límite documentado, excluye items borrados y conserva el formato de backup existente. | `brain_backup.py`, export round-trip y prueba de portabilidad. | PASS |
| M-13 | La API expone search, list, create, update, flags, delete, audit y consolidate con validación Pydantic, capacidades y ownership por device token. | Endpoints `/api/memory/advanced/*`; `advanced_memory_api_v090_test.py`. | PASS |
| M-14 | Los secretos, tokens de dispositivo, payloads de eventos, screenshots, screen capture, clipboard y referencias de automatización son rechazados como memoria durable. | `_SECRET_RE`, `_BLOCKED_SOURCE_RE`, pruebas negativas y auditoría estática. | PASS contractual |
| M-15 | Core, protocolo, host, envelope y Android declaran v0.9.0 coherentemente sin romper contratos heredados. | Versiones en config/protocol/host/mobile y regresión completa. | PASS contractual |
| M-16 | La release se construye mediante allowlist, no incluye datos/runtime/secretos/ZIPs, pasa checksum, `unzip -t`, `compileall` y suite desde extracción limpia. | `tools/build_release.py`, `GAIA-AI-v0.9.0-final.zip.sha256`, extracción `gaia-v090-final-extracted/GAIA-AI-v0.9.0` y 94 logs PASS. | PASS |

## Semántica de seguridad

La memoria avanzada es **contexto, no autoridad**. Un resultado de retrieval no puede auto-conceder permisos, modificar risk tier, ejecutar acciones, aceptar pairing, revelar tokens ni sustituir evidencia de host. El LLM no decide qué se almacena, no consulta memoria para saltarse el Core y no se usa para consolidación en v0.9.0.

La ingestión durable requiere una ruta explícita de `save_item()` y la validación rechaza contenido o provenance que parezca secreto, token, evento, captura de pantalla, clipboard o automatización. Las reglas de automatización siguen siendo configuración ejecutable bajo sus propios límites; no son memoria semántica.

## Compatibilidad y gates físicos

Flutter/analyze/APK, Android físico, Windows UIA/SMTC/display, Action Host sobre aplicaciones reales, micrófono, Whisper, Edge TTS, GPU, Ollama/Qwen real, LAN, TLS y firewall continúan como **PENDING** si el equipo objetivo no está disponible. La ausencia de esos equipos no se convierte en FAIL de código ni en PASS físico por inferencia.

## Evidencia de pruebas

La aceptación técnica mínima de v0.9.0 es la ejecución de los **94 tests** del directorio `tests/` desde un directorio limpio: 92 heredados y 2 nuevos de memoria avanzada. La corrida del worktree terminó con 94/94 PASS y la extracción `gaia-v090-final-extracted/GAIA-AI-v0.9.0` repitió compileall y 94/94 PASS con `PYTHONDONTWRITEBYTECODE=1`, sin reutilizar la base de datos del worktree. El checksum y `unzip -tq` también pasaron.

## Rollback

Si el clean gate o una validación física falla, se conserva intacto `GAIA-AI-v0.8.1-final.zip` y se etiqueta el artefacto como `v0.9.0-dev` hasta corregir la causa. No se mezclan binarios de v0.9.0 con una SQLite no respaldada, no se replayan acciones pendientes y no se reactivan schedules vencidos sin decisión explícita.
