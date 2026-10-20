HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# ROLLBACK — GAIA-AI v0.5.4.1

## Principio

El rollback debe preservar memoria, Vault, backups, audit log y credenciales. Detén Core, GUI, terminal, wake word, scheduler y proyectos que GAIA haya iniciado. Conserva la carpeta v0.5.4.1, DB, Brain Backup reciente y ZIP con checksum. No borres `GAIA_VAULT`, tokens ni audit log antes de revisar el incidente.

## Downgrade de código

En Windows:

```powershell
python tools\gaia_doctor.py --json > doctor-before.json
# Detén manualmente Core, GUI, terminal, wake word y proyectos iniciados por GAIA.
Rename-Item GAIA-AI-v0.5.4.1 GAIA-AI-v0.5.4.1.failed
Expand-Archive GAIA-AI-v0.5.4-final.zip -DestinationPath .
```

En Linux:

```bash
python3 tools/gaia_doctor.py --json > doctor-before.json
# Detén manualmente Core, clientes, wake word y proyectos iniciados por GAIA.
mv GAIA-AI-v0.5.4.1 GAIA-AI-v0.5.4.1.failed
unzip GAIA-AI-v0.5.4-final.zip -d .
```

No mezcles selectivamente `routes/api.py`, `desktop_api.py`, `config.py`, `authz.py` o tests entre releases. El contrato de estado, grounding y timeout debe pertenecer a una release coherente. No copies `.env`, DB, logs, tokens, audio o caches desde una carpeta fallida.

## Cambios correctivos v0.5.4.1

La petición desconocida queda en `ACTION_REQUEST` y devuelve capability failure determinista; el texto del LLM no obtiene autoridad de ejecución. `VerifiedActionResult` conserva `action`, `success`, `message`, `data` y `execution_verified`. La salida post-action no vuelve al classifier ni al Action Engine. v04/v041 y el fixture GUI se corrigieron en tests, no mediante hacks productivos.

El cliente PC calcula `ACTION_COMPLETION_TIMEOUT = max(60, requested client, post-action + 15)`. Si el parser recibe un valor inválido, usa defaults seguros. Tras rollback, verifica que no se haya restaurado una expectativa de 30 segundos ni una fórmula independiente.

## Ownership y estado temporal

`request_owner:{request_id}` en `lumen_state` es metadata temporal con Principal, device, token, sesión y timestamp. Se elimina en `done`, `cancelled` o error y tiene TTL defensivo. Antes de restaurar DB, deja terminar requests o detén Core. No borres `lumen_state` completo a ciegas porque contiene scheduler, sesiones y preferencias.

## Preparación de backup

Antes de cambiar código, crea snapshot SQLite y Brain Backup desde una sesión master si está habilitado:

```bash
python3 tools/gaia_doctor.py
curl -H "Authorization: Bearer $LUMEN_SECRET" -X POST http://127.0.0.1:8090/api/backup
curl -H "Authorization: Bearer $LUMEN_SECRET" -X POST http://127.0.0.1:8090/api/backup/brain
```

No pegues tokens en logs ni `.env` compartidos. El token claro solo aparece al crearlo; si se pierde, crea otro con master y revoca el anterior.

## Brain Backup portable

El backup contiene exactamente el payload canónico más `manifest.json`; no contiene `memory.db-wal`, `memory.db-shm` ni `memory.db-journal`. Restore rechaza extras, faltantes, traversal, duplicados, hashes inválidos, schema desconocido, sidecars y SQLite corrupta. La DB activa puede estar en WAL; la creación no cambia su journal mode. Durante restore se checkpointa WAL antes del reemplazo y se conserva la DB original cuando es seguro.

## Verificación posterior

Comprueba health, autenticación, SQLite, conversación controlada, acciones pendientes y GUI. La GUI no debe quedar en `Generando`; una conversación no debe afirmar un efecto sin completion estructurado. Ejecuta desde la release restaurada:

```bash
python3 -m compileall -q lumen-core lumen-pc tests tools
python3 tests/release_package_test.py
python3 tests/gui_import_test.py
python3 tests/smoke_test.py
python3 tests/v03_test.py
python3 tests/v04_test.py
python3 tests/v041_test.py
```

Es esperado que v0.5.4 no reconozca `request_state`, capability failure generalizado o la fórmula de timeout corregida. No marques rollback como completo hasta validar el conjunto coherente restaurado.
