# Migración LUMEN → GAIA y hotfix v0.5.3

GAIA-AI mantiene deliberadamente el namespace histórico `LUMEN_*`, las carpetas `lumen-core/`, `lumen-pc/`, `lumen-mobile/` y el nombre SQLite `lumen_memory.db`. La migración de marca no se ejecuta automáticamente y no renombra variables, carpetas o tablas.

## De v0.5.2 a v0.5.3

La actualización es un hotfix de distribución y Brain Backup sobre schema 5. No requiere migración de SQLite ni cambios del contrato action/plan, RBAC, ownership, ActionCoordinator o Android. Se actualiza la etiqueta Core a `0.5.3-pc`, se restaura `.env.example` en la raíz del ZIP y se añade `.gitignore`.

Extrae `GAIA-AI-v0.5.3-final.zip` en una carpeta nueva, crea `.env` copiando `.env.example`, instala las dependencias desde `lumen-core/requirements.txt` y `lumen-pc/requirements.txt`, y ejecuta Doctor. Conserva `LUMEN_SECRET` existente solo si sigue siendo fuerte y privado. No copies DB, logs, caches, tokens o backups dentro del paquete.

```bash
cp .env.example .env
python3 tools/gaia_doctor.py --json
python3 tests/release_package_test.py
```

## Brain Backup

No se debe cambiar el journal mode de la DB activa para esta actualización. El nuevo Brain Backup crea un snapshot SQLite autónomo en staging temporal, usa payload allowlisted, excluye `memory.db-wal`, `memory.db-shm` y `memory.db-journal`, verifica manifest/ZIP antes de éxito y conserva restore paranoico. Los backups v0.5.2 que pasen validación pueden restaurarse; si contienen un manifest inconsistente, deben rechazarse y generarse de nuevo en v0.5.3.

## Datos excluidos del paquete

No incluyas `.env`, bearer tokens claros, SQLite personal, audio, logs privados, Vault ni backups de la instalación. El paquete contiene código, documentación, pruebas, ejemplos, `.env.example` y `.gitignore`, pero no datos de usuario.

## GAIA_VAULT

`GAIA_VAULT` sigue siendo opt-in. Si está configurado pero no montado, GAIA usa fallback local y reporta la advertencia; no borra ni copia datos silenciosamente. Verifica `/api/diagnostics` y `tools/gaia_doctor.py` antes de mover el volumen.

## Android

La migración Android es estática en este entorno. El cliente conserva la API de ajustes y `flutter_secure_storage`; v0.5.3 no desarrolla Android nuevo y mantiene la versión declarada heredada `0.5.2+8`. No se afirma compilación ni instalación APK sin SDK y dispositivo real.

## Rollback

Si la instalación falla, detén procesos, conserva la carpeta nueva y restaura la carpeta v0.5.2 junto con DB, Vault y backups verificados. No borres la base ni los tokens antes de verificar una copia. Consulta `ROLLBACK.md`.

## Variables históricas

Para instalaciones nuevas se pueden usar aliases `GAIA_HOME`, `GAIA_VAULT`, `GAIA_DATA_DIR`, `GAIA_MEMORY_DB`, `GAIA_BACKUP_DIR` y `GAIA_LOG_DIR`; las variables `LUMEN_*` permanecen como fallback. No se hace una conversión masiva LUMEN→GAIA en esta release.
