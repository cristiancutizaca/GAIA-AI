# CHANGELOG

## v0.5.3-pc — Hotfix de release portable y Brain Backup determinista

GAIA-AI v0.5.3 es un hotfix conservador sobre v0.5.2. No cambia el schema SQLite 5, el contrato action/plan, RBAC, ownership, ActionCoordinator ni Android/LAN. El Core pasa a `0.5.3-pc`; el prototipo Android se conserva en `0.5.2+8` porque esta release no desarrolla Android.

### Distribución reproducible

Se restauran `.env.example` y `.gitignore` en la raíz distribuible. `.env.example` contiene los defaults actuales y solo un placeholder para `LUMEN_SECRET`; `.gitignore` protege secretos, bases, WAL/SHM, logs, backups, audio, tokens y cachés. `tools/build_release.py` usa allowlist explícita, incluye dotfiles seguros, bloquea archivos privados, fija timestamps ZIP, compara staging contra el ZIP reabierto y calcula SHA-256 después de la validación.

### Brain Backup portable

El payload se define mediante allowlist canónica: `memory.db`, `memory_export.json`, `profile.json`, `preferences.json`, `state.json`, `personality.py` y `config.json`. El manifest solo se genera después de estabilizar el snapshot; no enumera `root.iterdir()`. El snapshot es autónomo y no depende de `memory.db-wal`, `memory.db-shm` o `memory.db-journal`. El ZIP generado se reabre, se compara con el manifest y se elimina si la verificación falla. Un lock de proceso evita dos creaciones concurrentes en el mismo staging.

Restore conserva su validación paranoica y rechaza sidecars, extras, faltantes, traversal, duplicados, hashes incorrectos, schema incompatible y SQLite corrupta. Antes de reemplazar la DB activa, checkpointa su WAL y elimina solo sidecars cerrados; no cambia globalmente el journal mode activo.

### Pruebas y soporte

Se añaden `tests/release_package_test.py`, `tests/brain_backup_portability_test.py` y `tests/brain_backup_wal_test.py`. La portabilidad fuerza WAL, conexión abierta y 12 round-trips create→restore. La validación distingue árbol de trabajo y ZIP extraído. Python 3.11 es el objetivo recomendado y Python 3.12 es el entorno de esta validación; Python 3.13 no fue probado.

La auditoría baseline registró que el ZIP v0.5.2 carecía de `.env.example` y `.gitignore`; la ejecución de `fresh_install_test.py` desde esa extracción falló por `.env.example` ausente. La ejecución de `v04_test.py` en el baseline disponible pasó, por lo que no se afirma una reproducción independiente del fallo WAL/SHM; v0.5.3 añade una reproducción directa con DB WAL real.

## v0.5.2-pc — Contrato único, coordinación compartida, voz RBAC y ownership

GAIA-AI v0.5.2 extiende v0.5.1 de forma conservadora. Se conserva `lumen-core/`, `lumen-pc/`, `lumen-mobile/`, SQLite schema 5 y el namespace `LUMEN_*`. El Core pasa a `0.5.2-pc` y el prototipo Android a `0.5.2+8`.

### Contrato de acciones

Se unifica la respuesta de acción y plan. Una acción usa `kind=action`, `action`, `preview`, `confirmation_required` top-level, `action_id` y `session_id`; un plan usa `kind=plan`, `plan={plan_id, actions}`, preview completo e identificadores equivalentes. Se elimina la interpretación ambigua de un plan como acción individual, conservando tolerancia limitada para respuestas legacy.

### Coordinación y GUI/terminal

Se añade `lumen-pc/action_coordinator.py`, compartido por GUI, terminal y `desktop_api`. El coordinador limita a tres pasos, revalida cada step contra el catálogo local, confirma el conjunto, ejecuta secuencialmente, detiene ante el primer fallo y respeta cancelación antes del siguiente paso. La GUI muestra preview de single y plan; al rechazar confirma la cancelación con Core sin llamar al Action Engine. El terminal ya no inserta un plan directamente en el ejecutor.

### RBAC de voz y servicio interno

`/api/chat/voice` requiere `voice` y `chat` simultáneamente. Se extrae `_chat_service` para que voz y chat compartan lógica sin llamadas route-to-route que puedan saltarse Depends. Se conservan respuestas diferenciadas 401/403 y el STT sigue tratado como input no confiable.

### Ownership, cancelación y post-action

Cada SSE request guarda metadata temporal de Principal, `device_id`, `token_id`, sesión y timestamp. Solo el propietario puede cancelar; otro device recibe 403, master puede cancelar y requests inexistentes/caducados reciben 404. La metadata se limpia en done, cancelled y error con TTL defensivo. `actions/complete` comprueba Principal, sesión, device, plan_id y action host. Los resultados cancelled se registran como `cancelled`, no como fallo genérico.

### Pruebas y documentación

Se añaden `gui_action_contract_test.py`, `terminal_plan_test.py`, `voice_permissions_test.py`, `request_ownership_test.py`, `permission_level_test.py` y `plan_post_action_test.py`. Se actualizan smoke, v0.4, v0.5, v0.5.1 y classifier plan al contrato canónico. Se añaden `KNOWN_LIMITATIONS.md`, `MEMORY_ARCHITECTURE.md`, `SECURITY_MODEL.md`, `DEVICES.md` y se actualizan README, auditoría, reporte de pruebas, rollback, migración e inventario.

No se declaran pruebas físicas de Ollama/Qwen, GPU, audio, Edge TTS, LAN o Android. Flutter/Dart no está disponible y no se afirma APK.

## v0.5.1-pc — RBAC, Action Plans, Doctor y operación endurecida

GAIA-AI v0.5.1 extiende v0.5.0 sin eliminar `lumen-core/`, `lumen-pc/`, `lumen-mobile/`, `LUMEN_*`, SQLite schema 5 ni el flujo histórico de memoria. Añade Principal master/device, capabilities fail-closed, tokens hashados, expiración, revocación, audit log, planes LLM, Brain Backup scheduler, Doctor read-only, startup probe, LAN opt-in y secure storage Android estático.

## v0.5.0-pc — Memoria jerárquica, continuidad y operación segura

Se introduce schema SQLite 5 con migración tolerante, facts estructurados, FTS5/fallback, tareas temporales, notas de proyecto, sesiones, summaries, contexto PC read-only, TTS por frases, selector persistente de micrófono, planes de uno a tres pasos, tokens SHA-256, diagnósticos, proactividad sostenida, rotación de logs y Android secure storage.

## v0.4.1-pc — Correcciones de seguridad, routing y restore

Se corrigieron resolución de rutas, clasificación LLM como propuesta JSON, perfil `auto`, overrides de contexto, validación por acción, proyectos `trusted=false`, Brain Backup, protección contra PID reuse, estado de Ollama, continuidad de sesión y errores de GUI/Android.

## v0.4.0-pc — GAIA resiliente, memoria portable y Action Engine ampliado

Se añadieron perfiles y router de modelos, keep-alive/contexto/reintentos de Ollama, cancelación cooperativa, logs de backend, filtrado de reasoning, Action Engine ampliado, registro de proyectos, action history, GAIA_VAULT, Brain Backup, restore no destructivo, proactividad y providers read-only.

## v0.3.0-pc — Streaming, perfiles y Action Engine seguro

Se añadieron SSE, eventos `meta/token/action/done/error`, perfiles, filtro de reasoning, router allowlisted, Action Engine PC con listas de argumentos, finalización autenticada, proyectos registrados y pruebas de streaming/seguridad.

## v0.2.1-pc — Migración visible LUMEN → GAIA

La identidad visible pasa a GAIA y se conserva el namespace histórico para evitar romper instalaciones, memoria y clientes.
