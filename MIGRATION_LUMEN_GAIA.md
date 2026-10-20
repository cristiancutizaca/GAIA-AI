HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# Migración LUMEN → GAIA — v0.5.4 → v0.5.4.1

## Alcance

v0.5.4.1 es un hotfix correctivo y no una migración de schema. Conserva SQLite schema 5, el namespace `LUMEN_*`, el contrato action/plan, RBAC, ownership, ActionCoordinator, safe apps, Brain Backup, Android heredado y el modelo configurado. No se añade Android, LAN, browser automation ni acceso remoto.

## Procedimiento conservador

Detén Core, clientes PC y scheduler. Conserva el ZIP v0.5.4, el `.env` privado, la DB, el Vault y los backups fuera de la carpeta de release. Extrae `GAIA-AI-v0.5.4.1-final.zip` en una carpeta nueva; no mezcles módulos de releases distintas.

Copia `.env.example` a `.env` solo si el entorno nuevo todavía no tiene configuración. Mantén el secreto existente, revisa `GAIA_POST_ACTION_LLM_TIMEOUT`, `GAIA_CLIENT_ACTION_TIMEOUT`, `GAIA_MAX_CONCURRENT_LLM_REQUESTS` y `GAIA_ACTION_CONFIRM_POLICY`. El cliente PC calcula el timeout efectivo con margen; los valores inválidos generan warning y usan defaults seguros.

No hay migración de datos ni cambio de schema. Si se conserva la DB existente, detén todos los procesos que la usen y realiza una copia antes de arrancar. Brain Backup es portable y excluye WAL/SHM/journal del manifest.

## Cambios correctivos

La petición imperativa desconocida queda en `ACTION_REQUEST` y devuelve capability failure determinista en vez de chat libre. Los estados de pending, plan, success y failure se distinguen explícitamente. `VerifiedActionResult` conserva los hechos estructurados; la verbalización no puede crear una acción secundaria. v04 y v041 fueron corregidos en sus expectativas/fixtures, y el test GUI usa widgets falsos explícitos mientras `gui_busy_test.py` conserva la garantía productiva.

## Validación posterior

Desde la raíz extraída, ejecuta primero `python3 tests/release_package_test.py`, después la suite completa de `TEST_REPORT.md`, `python3 tools/gaia_doctor.py --json` y los greps de seguridad. Repite la comprobación desde la misma extracción final, no desde el worktree original. Verifica que `.git`, `.env`, DB, logs, audio, caches y tokens no estén dentro del ZIP.

## Compatibilidad histórica

La migración no renombra variables, carpetas, tablas ni la base `lumen_memory.db`. Las variables `LUMEN_*` permanecen como fallback compatible; `GAIA_*` contiene los controles nuevos y preferidos. Android no se incrementa en esta revisión y no se afirma APK.

## Brain Backup

No cambies el journal mode de la DB activa. El snapshot usa SQLite Backup API en staging temporal, payload allowlisted y verificación de manifest/ZIP. Restore conserva rechazo de traversal, extras, faltantes, sidecars, hashes inválidos, schema desconocido y SQLite corrupta.

## Rollback

Si el hotfix falla, detén procesos, conserva logs fuera del release y vuelve a la carpeta v0.5.4 previamente verificada. No copies módulos v0.5.4.1 aislados sobre v0.5.4. Si una DB fue usada por la nueva versión, restaura la copia previa o un Brain Backup validado; nunca borres la única DB. Consulta `ROLLBACK.md`.
