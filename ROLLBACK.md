# ROLLBACK — GAIA-AI v0.5.3

## Principio

El rollback debe preservar memoria, Vault, backups, audit log y credenciales. Detén Core, GUI, terminal, wake word y cualquier proyecto que GAIA haya iniciado. Conserva la carpeta v0.5.3, `lumen_memory.db`, el Brain Backup más reciente y el ZIP v0.5.3 con checksum. No borres `GAIA_VAULT`, tokens de dispositivo ni audit log antes de revisar el incidente.

## Downgrade de código

En Windows:

```powershell
python tools\gaia_doctor.py --json > doctor-before.json
# Detén manualmente Core, GUI, terminal, wake word y proyectos iniciados por GAIA.
Rename-Item GAIA-AI-v0.5.3 GAIA-AI-v0.5.3.failed
Expand-Archive GAIA-AI-v0.5.2-final.zip -DestinationPath .
```

En Linux:

```bash
python3 tools/gaia_doctor.py --json > doctor-before.json
# Detén manualmente Core, clientes, wake word y proyectos iniciados por GAIA.
mv GAIA-AI-v0.5.3 GAIA-AI-v0.5.3.failed
unzip GAIA-AI-v0.5.2-final.zip -d .
```

La v0.5.2 original carecía de `.env.example` y `.gitignore` en su ZIP final. Si el downgrade se hace por compatibilidad de código, conserva los dotfiles de v0.5.3 fuera de la carpeta anterior solo si no introducen configuración incompatible; nunca copies `.env`, DB, logs, tokens o caches desde la carpeta fallida.

No mezcles `brain_backup.py` v0.5.3 con el resto de v0.5.2: el módulo usa allowlist y verificación nuevas. Si no existe un ZIP v0.5.2 válido, conserva la carpeta v0.5.3 y restaura primero una copia comprobada.

## Ownership y estado temporal

v0.5.2/v0.5.3 guardan `request_owner:{request_id}` en `lumen_state` mientras una solicitud SSE está activa. Incluye Principal, device, token, sesión y timestamp; se elimina en `done`, `cancelled` o error y tiene TTL defensivo. Es metadata transitoria, no memoria conversacional ni una credencial clara. Antes de restaurar DB deja terminar requests o detén Core. No borres `lumen_state` completo a ciegas: contiene scheduler, sesiones y preferencias.

## Preparación de backup

Antes de cambiar código, crea snapshot SQLite y, si está habilitado, Brain Backup desde una sesión master.

```bash
python3 tools/gaia_doctor.py
# Con Core activo y bearer master:
curl -H "Authorization: Bearer $LUMEN_SECRET" -X POST http://127.0.0.1:8090/api/backup
curl -H "Authorization: Bearer $LUMEN_SECRET" -X POST http://127.0.0.1:8090/api/backup/brain
```

No pegues tokens en logs ni `.env` compartidos. El token claro solo se muestra al crearlo; si se pierde, crea otro con master y revoca el anterior.

## Brain Backup v0.5.3

El backup portable contiene exactamente el payload canónico más `manifest.json`. No contiene `memory.db-wal`, `memory.db-shm` ni `memory.db-journal`. El manifest se genera después de cerrar operaciones temporales, se calcula con SHA-256 y el ZIP se reabre antes de declarar éxito. Un backup con extras, missing, duplicate, traversal, hash mismatch, schema desconocido, sidecar o SQLite corrupta debe rechazarse; no se debe “arreglar” restore ignorando faltantes.

La DB activa puede estar en WAL. La creación usa SQLite Backup API para una copia temporal y no cambia el journal mode de la DB activa. Durante restore se checkpointa el WAL activo antes del reemplazo y se eliminan únicamente sidecars cerrados. Si el proceso falla, conserva el archive y la DB original cuando sea seguro; nunca improvises una mezcla.

## Restaurar solo memoria

La migración v4→v5 es aditiva y conserva facts, pero el rollback de código no debe forzar schema 5 sobre una versión antigua sin copia separada.

```bash
python3 tools/gaia_memory.py migrate --source /ruta/origen/lumen_memory.db --destination /ruta/prueba/memory.db --dry-run
python3 tools/gaia_memory.py migrate --source /ruta/origen/lumen_memory.db --destination /ruta/prueba/memory.db
python3 tools/gaia_memory.py restore /ruta/backups/gaia_brain_YYYYMMDD_HHMMSS.zip
```

Brain Backup valida traversal, duplicados, extras/faltantes, schema, SHA-256 e `integrity_check` antes de tocar la DB activa. Restore crea snapshot actual antes del reemplazo validado y registra audit si se ejecuta desde Core.

## RBAC y tokens

Una versión anterior puede ignorar capabilities, ownership y endpoints nuevos. Si se vuelve a v0.5.0 o v0.4.1, revoca desde el Core v0.5.3 los tokens que pudieran estar expuestos y conserva su inventario para decidir si deben reemitirse. Una base restaurada puede contener hashes y metadata, nunca tokens claros.

## Si GAIA_VAULT no aparece

No crees manualmente una DB vacía dentro del volumen ausente. Revisa `/api/vault/status`, el punto de montaje y `GAIA_HOME`/`GAIA_VAULT`. Mientras la ruta siga ausente, el estado correcto es fallback explícito con advertencia. Copia Vault solo después de verificar integridad y permisos.

## Si el Core no arranca

Ejecuta `python3 tools/gaia_doctor.py --json`, revisa el log y verifica que un `LUMEN_HOST` externo tenga `GAIA_LAN_ENABLED=true`. `start-gaia` no mata procesos ni inicia Ollama; un puerto ocupado por otra aplicación debe resolverse manualmente. Cambiar temporalmente a localhost es preferible a abrir firewall o red.

## Verificación después del rollback

```bash
python3 -m compileall -q lumen-core lumen-pc tests tools
python3 tests/gui_import_test.py
python3 tests/smoke_test.py
python3 tests/v03_test.py
python3 tests/v04_test.py
python3 tests/v041_test.py
```

Es esperado que una versión anterior no reconozca `/api/diagnostics`, planes, audit, capabilities, ownership o los dotfiles nuevos. No marques el rollback como completo hasta comprobar health, autenticación, SQLite, una conversación controlada y, si aplica, restore en una DB temporal.
