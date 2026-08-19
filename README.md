# GAIA-AI v0.5.3

**GAIA** es una asistente personal local en español, directa, sarcástica y deliberadamente poco corporativa. GAIA-AI v0.5.3 es un hotfix sobre v0.5.2: no cambia la arquitectura principal, conserva `lumen-core/`, `lumen-pc/`, `lumen-mobile/`, SQLite schema 5, la configuración `LUMEN_*` y la separación entre Core clasificatorio y ejecución local. Corrige la distribución del release y la portabilidad determinista de Brain Backup.

> **Estado honesto.** El Core Python, SQLite, los contratos HTTP/SSE, el RBAC, el coordinador de acciones y los clientes PC se validan automáticamente con backend mock y bases temporales. Ollama/Qwen, GPU, micrófono, altavoces, Edge TTS, VS Code, navegador, LAN física y Android requieren validación en el equipo real. Flutter/Dart no está instalado en este sandbox; por ello no se afirma la generación de un APK.

## Alcance de v0.5.3

| Área | Implementación | Evidencia |
|---|---|---|
| Contrato | Schema único top-level para `action` y `plan`, con preview e identificadores | `tests/gui_action_contract_test.py` |
| Coordinación PC | `ActionCoordinator` compartido; máximo tres pasos, revalidación, cancelación y fallo temprano | `tests/terminal_plan_test.py` |
| RBAC de voz | `/api/chat/voice` exige simultáneamente `voice` y `chat` | `tests/voice_permissions_test.py` |
| Ownership | SSE vinculado a Principal, device y token; cross-device devuelve 403 | `tests/request_ownership_test.py` |
| Least privilege | `permission_level` es metadata; capabilities son la autoridad | `tests/permission_level_test.py` |
| Post-action | `plan_id`, aggregate, pasos, duración y cancelación auditados | `tests/plan_post_action_test.py` |
| Base heredada | Schema 5, tokens SHA-256, scheduler, Doctor, LAN opt-in y secure storage | Regresiones v0.5.2 y revisión estática |
| Release portable | `.env.example`, `.gitignore`, allowlist de archivos y ZIP verificado desde extracción limpia | `release_package_test.py`, `tools/build_release.py` |
| Brain Backup | Payload canónico, snapshot autónomo, WAL/SHM excluidos, manifest verificado y lock de concurrencia | `brain_backup_wal_test.py`, `brain_backup_portability_test.py` |

## Arquitectura

```text
PC / Android con token de dispositivo
              │
              ▼
        GAIA Core (FastAPI)
          ├─ Principal + RBAC fail-closed
          ├─ SQLite schema 5 + FTS5/fallback
          ├─ memoria y continuidad jerárquicas
          ├─ Ollama/OpenAI/Anthropic/mock
          ├─ SSE, ownership y cancelación
          ├─ classifier → action/plan → política
          ├─ Brain Backup, Doctor y proactividad acotada
          └─ servicio interno de chat reutilizable
              │
              ▼
       Cliente PC → ActionCoordinator
                    → Action Engine local
                    → resultado estructurado y auditado
```

El modelo no tiene autoridad de ejecución. El Core emite nombres de acciones y argumentos validados; el PC vuelve a validar allowlists, rutas, proyectos `trusted`, PID e identidad del proceso. No se aceptan shell arbitrario, `eval`, `exec`, PowerShell, `cmd`, sudo, instalación, borrado arbitrario ni comandos construidos por texto del modelo.

## Instalación

En Windows, desde la carpeta extraída del ZIP final:

```powershell
Expand-Archive GAIA-AI-v0.5.3-final.zip -DestinationPath .
cd .\GAIA-AI-v0.5.3
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r .\lumen-core\requirements.txt
pip install -r .\lumen-pc\requirements.txt
Copy-Item .env.example .env
```

En Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r lumen-core/requirements.txt
pip install -r lumen-pc/requirements.txt
cp .env.example .env
```

GAIA no instala dependencias, descarga modelos, abre puertos públicos ni inicia Ollama. La instalación del servicio Ollama y de `qwen3.5:9b` es manual. Python 3.11 es el objetivo recomendado para el equipo del usuario; el sandbox de esta validación ejecuta Python 3.12. Python 3.13 no fue probado.

## Configuración

Copia `.env.example` como `.env` y cambia `LUMEN_SECRET` por un secreto largo y privado. El perfil `auto` usa heurísticas locales y no realiza una segunda llamada LLM para escoger perfil.

| Variable | Default seguro | Función |
|---|---:|---|
| `LUMEN_LLM_BACKEND` | `ollama` | Backend local; `mock` solo para pruebas |
| `LUMEN_LLM_MODEL` | `qwen3.5:9b` | Modelo preferido |
| `LUMEN_LLM_PROFILE` | `auto` | Router local de perfil |
| `GAIA_AUTO_MEMORY_ENABLED` | `false` | Memoria semántica automática opt-in |
| `GAIA_ACTION_CONFIRM_POLICY` | `CONFIRM_EXECUTION` | `AUTO_SAFE`, `CONFIRM_EXECUTION` o `BLOCKED` |
| `GAIA_DEVICE_TOKENS_ENABLED` | `true` | Tokens hashados, expirables y revocables |
| `GAIA_BRAIN_BACKUP_ENABLED` | `false` | Scheduler portable opcional |
| `GAIA_PRIVACY_MODE` | `normal` | `strict` reduce logs y contexto sensible |
| `LUMEN_PROACTIVE_ENABLED` | `false` | Proactividad apagada por defecto |
| `GAIA_LAN_ENABLED` | `false` | Requerido para escuchar fuera de localhost |
| `LUMEN_HOST` | `127.0.0.1` | Host de escucha |

`GAIA_VAULT` es opt-in. Si no está montado, se conserva el fallback local y se reporta `missing_fallback`; no se borra memoria.

## RBAC, Principal y dispositivos

El secreto master produce un Principal administrativo. Un token de dispositivo se muestra una sola vez y el servidor conserva únicamente SHA-256, expiración, revocación, `device_id`, `token_id`, capabilities y metadata. Un token válido sin capability produce **403**; un token ausente, inválido, expirado o revocado produce **401**.

| Capability | Acceso |
|---|---|
| `chat` | Chat síncrono, SSE y cancelación propia |
| `memory_read` / `memory_write` | Lectura o modificación de memoria |
| `voice` | STT, TTS y audio |
| `diagnostics` | Status, diagnósticos y Vault status |
| `actions_request` | Proponer una acción o plan |
| `actions_execute` + `action_host` | Registrar ejecución local |
| `backup_create` | Crear snapshot o Brain Backup |
| `proactive_read` / `proactive_control` | Leer o controlar cola proactiva |
| `device_self` | Metadata del propio dispositivo |
| Administración | Dispositivos, permisos, tokens, auditoría y restore; master-only |

`permission_level` es metadata de agrupación y futuro uso; **no concede permisos por sí mismo**. Un valor legado `999` con `capabilities=["chat"]` solo permite chat. `touch_device()` actualiza únicamente presencia: no cambia nombre, tipo, capabilities, nivel ni revocación.

## Contrato de acciones y planes

La respuesta canónica de una acción usa `kind=action`, `confirmation_required` top-level, `action`, `preview`, `action_id` y `session_id`. Un plan usa `kind=plan`, `confirmation_required` top-level, `plan={plan_id, actions}`, preview completo e identificadores equivalentes. No se mezclan campos ambiguos nested/top-level.

`ActionCoordinator` es el único coordinador común de GUI, terminal y `desktop_api`. Revalida cada paso contra el catálogo local, limita a tres acciones, ejecuta secuencialmente, detiene el plan ante el primer fallo y revisa cancelación antes de cada paso. Una confirmación negativa ejecuta cero pasos. El resultado se envía a `/api/actions/complete` con `plan_id`, `step`, `duration_ms`, `status` y salida limitada. La verbalización posterior no se reclasifica ni crea una acción nueva.

`AUTO_SAFE` permite solo nivel 1 sin diálogo; un nivel 2 devuelve aviso y no ejecuta. `CONFIRM_EXECUTION` muestra preview completo. `BLOCKED` devuelve un aviso explícito y no despacha acciones.

## Voz, ownership y cancelación

`/api/chat/voice` exige `voice` y `chat`, usa el servicio interno `_chat_service` y no llama otra función de route con dependencias FastAPI. STT se trata como input de usuario bajo los mismos controles de inyección. TTS y audio continúan sujetos a capacidades y hardware.

Cada request SSE guarda temporalmente Principal, device, token, sesión y timestamp. Solo el propietario puede cancelar; otro dispositivo recibe 403, master puede cancelar y un request inexistente o expirado recibe 404. La metadata se limpia tras done, cancelled o error y tiene TTL defensivo.

## Doctor y arranque

```bash
python3 tools/gaia_doctor.py
python3 tools/gaia_doctor.py --json
python3 tools/gaia_doctor.py --strict
./start-gaia.sh
```

En Windows se usa `start-gaia.bat`. Doctor es read-only: inspecciona entorno, DB, Vault, Ollama, voz, aplicaciones y configuración sin instalar, descargar, reparar, matar procesos ni modificar firewall. La sonda de arranque distingue Core GAIA activo, puerto ocupado por otra aplicación y Core offline; nunca inicia Ollama ni mata procesos ajenos.

## API y LAN

`GET /api/health` es una comprobación mínima pública. Las operaciones restantes requieren bearer válido y capability apropiada. Entre las rutas principales están `/api/chat`, `/api/assistant/stream`, `/api/assistant/cancel`, `/api/chat/voice`, `/api/actions/complete`, `/api/memory/*`, `/api/diagnostics`, `/api/backup/brain`, `/api/devices/*` y `/api/admin/audit`.

El Core escucha solo en localhost salvo `GAIA_LAN_ENABLED=true` junto con `LUMEN_HOST`. GAIA no integra TLS: una LAN real requiere red confiable y TLS externo o túnel seguro. No se abre firewall ni se publican puertos automáticamente.

## Memoria, backups y rollback

SQLite schema 5 conserva conversaciones, preferencias, facts con fuente y confianza, tareas temporales, notas, sesiones, summaries y acciones verificadas. Las tareas abiertas no se convierten automáticamente en facts permanentes y la extracción automática está apagada por defecto.

SQLite snapshot y Brain Backup son independientes. El scheduler periódico usa la función corregida, no bloquea el event loop, persiste estado, tolera fallos y poda sin borrar el backup recién creado. Brain Backup construye exactamente el payload allowlisted `memory.db`, `memory_export.json`, `profile.json`, `preferences.json`, `state.json`, `personality.py` y `config.json`; nunca enumera contenido temporal del staging. El snapshot se crea con SQLite Backup API en una copia autónoma, se verifica después de cerrar conexiones temporales y el ZIP se reabre antes de devolver éxito. WAL/SHM/journal no forman parte del manifest ni del ZIP. Restore es master-only, valida traversal, duplicados, faltantes, extras, hashes, versión, sidecars prohibidos, integridad y snapshot previo.

Para rollback, detén Core y clientes, conserva ZIP, DB, Vault y backups, y restaura la carpeta v0.5.2 solo después de verificar una copia. Consulta `ROLLBACK.md`.

## Pruebas

Desde la raíz:

```bash
python3 -m compileall -q lumen-core lumen-pc tests tools
python3 tests/smoke_test.py
python3 tests/v03_test.py
python3 tests/v04_test.py
python3 tests/v041_test.py
python3 tests/v05_test.py
python3 tests/v051_test.py
python3 tests/action_plan_llm_test.py
python3 tests/device_permissions_test.py
python3 tests/device_touch_test.py
python3 tests/brain_backup_scheduler_test.py
python3 tests/startup_test.py
python3 tests/db_upgrade_test.py
python3 tests/backup_integrity_test.py
python3 tests/process_safety_test.py
python3 tests/security_regression_test.py
python3 tests/llm_health_test.py
python3 tests/fresh_install_test.py
python3 tests/vault_missing_test.py
python3 tests/gui_import_test.py
python3 tests/gui_action_contract_test.py
python3 tests/terminal_plan_test.py
python3 tests/voice_permissions_test.py
python3 tests/request_ownership_test.py
python3 tests/permission_level_test.py
python3 tests/plan_post_action_test.py
python3 tests/release_package_test.py
python3 tests/brain_backup_wal_test.py
python3 tests/brain_backup_portability_test.py
```

La validación final separa `WORKTREE TESTS` de `FINAL ZIP EXTRACTED TESTS` y añade grep de seguridad para `shell=True`, `os.system(`, `eval(` y `exec(`, comprobación de route-to-route, higiene del ZIP, path safety y checksum. Ningún mock sustituye validación de Ollama/Qwen, GPU, micrófono, Edge TTS, ventanas activas, proyectos confiables, LAN o Android.

## Release reproducible

`tools/build_release.py` detecta la versión, exige `.env.example` y `.gitignore`, copia una allowlist explícita, bloquea `.env`, bases, logs, backups, audio, tokens, caches y `.git`, crea el ZIP con timestamps fijos, reabre el archivo y compara sus entradas con staging. El SHA-256 se escribe únicamente después de pasar la prueba de ZIP y la suite desde la extracción limpia.

La validación de release debe ejecutarse antes de `compileall` para que los bytecode generados no se confundan con contenido empaquetable:

```bash
python3 tests/release_package_test.py
python3 tests/brain_backup_wal_test.py
python3 tests/brain_backup_portability_test.py
python3 tools/build_release.py --output-dir ..
rm -rf /tmp/gaia-release-check
mkdir -p /tmp/gaia-release-check
unzip ../GAIA-AI-v0.5.3-final.zip -d /tmp/gaia-release-check
cd /tmp/gaia-release-check/GAIA-AI-v0.5.3
```

Después de extraer, se ejecuta la suite completa desde esa copia. El checksum se calcula solo después de que esa suite y la higiene del paquete pasan.

## Android y límites

El prototipo Flutter usa `flutter_secure_storage` para el token de dispositivo, sin secreto master default, y diferencia 401 de 403. Esta release solo permite revisión estática porque el SDK Flutter no está instalado; no incluye APK ni afirma instalación Android real.

No se incluyen browser agent, screen automation, mouse autonomy, acceso remoto Android→PC, TLS server, multi-agent, niveles 3–4, agentes recursivos ni control remoto general.

## Archivos de auditoría

`V052_REQUIREMENTS.md` conserva el resumen auditable de las instrucciones. `TEST_REPORT.md`, `AUDIT.md`, `SECURITY_MODEL.md`, `MEMORY_ARCHITECTURE.md`, `DEVICES.md`, `KNOWN_LIMITATIONS.md`, `MIGRATION_LUMEN_GAIA.md`, `MODIFIED_FILES.md` y `ROLLBACK.md` separan implementación, pruebas automatizadas, revisión estática y validación física pendiente.
