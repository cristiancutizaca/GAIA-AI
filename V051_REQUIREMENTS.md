HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# Requisitos de GAIA-AI v0.5.1

Fuente: `/home/ubuntu/upload/pasted_content_5.txt`, instrucciones del usuario, 2421 líneas.

## Prioridad de implementación

La versión debe partir de `GAIA-AI-v0.5.0-final.zip`, llamarse GAIA-AI v0.5.1 y conservar FastAPI, SQLite schema 5, FTS5/fallback, memoria, summaries, open tasks, project notes, action history, device tokens, Action Engine, plans, voz, providers, diagnostics, Brain Backup, GAIA_VAULT y regresiones históricas. No se permite reescritura masiva, migración de nombres ni salto a v0.6.

## RBAC y dispositivos

Debe existir un `Principal` central que distinga `master` y `device`, con device_id, permission_level, capabilities y token_id. La autenticación válida sin permiso debe responder 403, no 401. Capabilities mínimas: chat, memory_read, memory_write, voice, diagnostics, actions_request, actions_execute, action_host, backup_create, proactive_read, proactive_control, device_self, device_admin, brain_restore y admin.

El secreto `LUMEN_SECRET` es master. Puede administrar dispositivos/tokens, cambiar permisos, crear/restaurar Brain Backup y administrar proactividad. Los tokens de dispositivo solo reciben capabilities declaradas; Brain Restore debe ser master-only. Token creation y device administration son master-only. Tokens revocados/expirados deben producir 401 y no actualizar last_used_at. Tokens existentes migran con least privilege, nunca admin automático. touch_device solo actualiza presencia y jamás degrada metadata.

## Action Plans

El classifier LLM solo debe producir conversation/action/plan. Los planes nacen de frases naturales, admiten 1–3 acciones, se validan atómicamente con el mismo parser individual, rechazan completamente un plan si un paso es inválido, calculan una política global de confirmación y no pueden iniciar loops. El cliente debe mostrar preview completo, cancelar antes del siguiente paso y registrar plan_id, step, status y duration.

## Backups, Doctor y arranque

SQLite snapshot y Brain Backup portable son independientes. `GAIA_BRAIN_BACKUP_ENABLED=true` debe invocar realmente `create_brain_backup()` en scheduler no bloqueante, persistir last_brain_backup_at, respetar intervalo y retención independiente, no duplicar por reinicios y tolerar fallos. Brain Restore conserva manifest, SHA-256, schema, traversal, duplicates, missing/extra, integrity y snapshot previo; debe escribir audit log.

Crear `tools/gaia_doctor.py` read-only con salida texto y `--json`, sin pip, ollama pull, edición de .env, mkdir crítico ni reparaciones. Crear `start-gaia.sh` y `start-gaia.bat`: localizar proyecto/venv, detectar Core activo, esperar health con timeout, evitar duplicados, no matar procesos, no iniciar Ollama ni tocar firewall.

## Alcance y límites

Mantener memoria automática desactivada, voz estable, Android con device token y flutter_secure_storage, servidor como autoridad, project trust false, no shell/eval/exec, no routing remoto Android→PC, no LAN pública, no agent recursivo, no niveles 3–4 ni nueva GUI. Documentar Implemented, automated/mock/static tested, physical pending y experimental; empaquetar `GAIA-AI-v0.5.1-final.zip` y checksum después del ZIP definitivo sin datos privados.
