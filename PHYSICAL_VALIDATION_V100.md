HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

HISTORICAL DOCUMENT — DO NOT USE FOR RC5 OPERATIONS

This document is preserved for historical traceability only. For current RC5 operations use `WINDOWS_RC5_VALIDATION_CHECKLIST.md`, `UPDATE_ROLLBACK_GUIDE.md` and `PHYSICAL_VALIDATION_RC5.md`.

# GAIA-AI v1.0-RC1 — Harness de validación física pre-final

> **Estado actual:** PENDING para hardware físico. Esta matriz verifica RC1 en equipos reales; no convierte pruebas del sandbox en validación física ni declara v1.0 final.

## Precondiciones

La prueba debe ejecutarse en un Windows objetivo limpio con Python 3.11, permisos de usuario normales, una instalación de Ollama local, el modelo configurado para la laptop (`qwen3.5:4b` por defecto) disponible, una pantalla y al menos una aplicación controlable. Para Android se requiere Flutter/Android SDK o un APK entregado por un pipeline de build, un teléfono/emulador, cámara o fallback manual, almacenamiento seguro y una red local controlada. Toda prueba debe conservar logs fuera del árbol de release y redactar tokens, secretos, audio, capturas y datos personales.

Antes de comenzar se conservan los ZIPs v0.9.0, v0.9.1 y v0.9.2 con sus SHA-256, se verifica el RC1 desde un canal independiente y se crea un punto de restauración/snapshot externo. El operador debe poder detener Core, GUI, scheduler y host en cualquier momento.

## Primeros comandos en Windows real

```powershell
# 1. Abrir PowerShell normal, no como administrador salvo que el caso lo requiera.
cd C:\GAIA\releases
Get-FileHash .\GAIA-AI-v1.0-RC1-final.zip -Algorithm SHA256
Get-Content .\GAIA-AI-v1.0-RC1-final.zip.sha256

# 2. Extraer en carpeta nueva; no sobrescribir la instalación estable.
Expand-Archive .\GAIA-AI-v1.0-RC1-final.zip -DestinationPath C:\GAIA\install-v1.0-RC1
Set-Location C:\GAIA\install-v1.0-RC1\GAIA-AI-v1.0-RC1

# 3. Inspección version-aware sin mutar la instalación.
py -3.11 .\tools\gaia_migrate.py --root C:\GAIA\stable\GAIA-AI-v0.9.2 --target-version 1.0.0-rc1 --json --safe-mode
py -3.11 .\tools\gaia_migrate.py --root C:\GAIA\stable\GAIA-AI-v0.9.2 --target-version 1.0.0-rc1 --snapshot-dir C:\GAIA\snapshots\rc1 --json --safe-mode

# 4. Instalación de dependencias y configuración segura.
.\setup-windows.bat -PlanMigration -MigrationSourceRoot C:\GAIA\stable\GAIA-AI-v0.9.2 -MigrationSnapshotDir C:\GAIA\snapshots\rc1 -SafeMode
Copy-Item .env.example .env
# Editar .env manualmente; nunca pegar el secreto en un log o chat.

# 5. Doctor y smoke inicial.
.\.venv\Scripts\python.exe .\tools\gaia_doctor.py --json --mode preflight --safe-mode | Tee-Object C:\GAIA\evidence\doctor-before.json
.\setup-windows.bat -ApplyMigration -ApproveMigration -MigrationSourceRoot C:\GAIA\stable\GAIA-AI-v0.9.2 -MigrationSnapshotDir C:\GAIA\snapshots\rc1 -SafeMode
.\.venv\Scripts\python.exe -m compileall -q lumen-core lumen-pc tests tools
```

El primer bloque no debe ejecutarse si el checksum no coincide. `setup-windows.bat` debe devolver el código de salida real de PowerShell; un error no puede ocultarse por una tubería.

## Matriz Core/PC

| ID | Caso | Procedimiento | Resultado esperado | Evidencia | Estado |
|---|---|---|---|---|---|
| W-01 | Instalación limpia | Extraer ZIP verificado, ejecutar setup en carpeta nueva y confirmar venv | Dependencias instaladas, sin modificar release estable | `install.log`, ruta nueva, hash | PENDING |
| W-02 | Instalación repetida | Ejecutar instalador con `.env` válido y sin `-GenerateSecret` | No sobrescribe secreto ni configuración | diff de `.env` sin valores | PENDING |
| W-03 | Migración plan | Ejecutar `gaia_migrate.py --json` antes de cambiar DB | Reporta versión, schema, integrity y preservation sin secretos | JSON redactado | PENDING |
| W-04 | Snapshot pre-update | Crear snapshot en carpeta externa y revisar manifest | DB consistente, env privado separado, SHA del snapshot, fuente intacta | `manifest.json`, hash | PENDING |
| W-05 | Startup | Iniciar Core, GUI y Action Host | Health online, versión coherente, no hangs, Doctor read-only | logs, health, Doctor | PENDING |
| W-06 | Ollama | Confirmar `qwen3.5:4b` (o el modelo configurado), enviar chat normal y revisar latencias | Respuesta visible, sin error de modelo, sin secreto en prompt/log | chat log redactado | PENDING |
| W-07 | Chat normal | Conversación en español con humor moderado | Respuesta factual y personalidad sarcástica sin inventar acciones | transcript redactado | PENDING |
| W-08 | Fast action | Solicitar calculadora allowlisted | Preview/confirmación, preflight y `VerifiedActionResult` real | request/result digest | PENDING |
| W-09 | Safe App | Abrir Spotify/VS Code mediante identity/trust | Solo app trusted y path canónico; cambio no trusted requiere nueva decisión | auditoría host | PENDING |
| W-10 | Audio/media | Probar mute/volume y pause/next con sesión real | Resultado explícito, no credentials provider, falla honestamente si unavailable | captura no permanente + log | PENDING |
| W-11 | Ventanas/displays | Focus/minimize/move con dos displays reales | `expected_target`, scope y ventana correcta; stale target bloqueado | contexto y resultado | PENDING |
| W-12 | UIA read | Inspeccionar app benigna y control password | UIA redacted, sin password/secret value | reporte redacted | PENDING |
| W-13 | UIA invoke | Pulsar botón benigno con target esperado | Preflight, risk, permission, efecto observado y completion verificado | resultado + app state | PENDING |
| W-14 | UIA risk | Intentar control “eliminar cuenta” o equivalente | Riesgo dinámico eleva nivel y exige política/confirmación nueva | denied/re-ask log | PENDING |
| W-15 | Screen capture | Capturar ventana/monitor on-demand | `capture_id`, TTL, ownership, retrieval auth; cleanup posterior | manifest + hash | PENDING |
| W-16 | Terminal | Ejecutar solo acción contextual allowlisted de proyecto | Sin shell libre, path trusted, preflight y resultado honesto | auditoría | PENDING |
| W-17 | Workspace cold start | Preparar VS Code desde estado cerrado | Plan bounded ≤5 steps, cada step con identity/scope/permission | plan/result | PENDING |
| W-18 | Trusted folder | Copiar/mover archivo dentro de trusted folder | Read/write scope explícito; fuera de scope bloqueado | result + audit | PENDING |
| W-19 | Permission persistence | Otorgar Always Allow a un scope exacto, reiniciar Core y repetir | Persistencia exacta; cambio de riesgo/version re-pregunta | DB counts sin tokens | PENDING |
| W-20 | Revoke/kill | Revocar grant, pausar automation y activar kill switch | Nuevas acciones bloqueadas; chat/memory siguen disponibles | status/result | PENDING |

## Matriz Advanced Memory v0.9.0

| ID | Caso | Procedimiento | Resultado esperado | Estado |
|---|---|---|---|---|
| M-01 | Save explícito | Crear preference/project con provenance y scope | Item durable con campos completos | PENDING físico |
| M-02 | Retrieval bounded | Insertar contexto de proyecto y buscar una consulta | Solo items relevantes; `max_chars` nunca se supera | PENDING físico |
| M-03 | Ownership | Consultar desde Android token otro device | 404/403 sin confirmar existencia indebida | PENDING físico |
| M-04 | Contradicción | Guardar dos valores para misma key | Anterior `superseded`, historial visible solo por ruta explícita | PENDING físico |
| M-05 | Delete/export | Borrar item y crear Brain Backup | GET normal/backup ocultan deleted; export no filtra secreto | PENDING físico |
| M-06 | Prompt boundary | Guardar texto que parezca instrucción y conversar | Se usa como contexto auxiliar, nunca como autoridad ni acción | PENDING físico |

## Matriz Android/companion

| ID | Caso | Procedimiento | Resultado esperado | Evidencia | Estado |
|---|---|---|---|---|---|
| A-01 | Build/analyze | Ejecutar Flutter analyze y build debug desde proyecto extraído | Resultado real documentado; no llamar release firmado si no existe keystore | salida completa | PENDING |
| A-02 | Pairing QR/manual | Emparejar por QR y por URI pegado | URI validado, código one-time, capabilities conservadoras | logs redacted | PENDING |
| A-03 | Token storage | Reiniciar app y consultar secure storage | Token no aparece en UI/log; sesión/device persisten | inspección manual | PENDING |
| A-04 | Chat streaming | Enviar chat y cancelar stream | Cancelación limpia, no duplicate/reconnect flood | transcript | PENDING |
| A-05 | Remote action | Pedir abrir app en PC | Preview, scope, risk y aprobación; host reclama solo después | Core/host logs | PENDING |
| A-06 | Capture retrieval | Descargar `capture_id` propio | Auth/ownership correctos, TTL y cleanup | hash/headers | PENDING |
| A-07 | Voice | Push-to-talk con permiso de micrófono | Archivo temporal, Whisper/TTS contextual y cleanup; sin wake word | audio test notes | PENDING |
| A-08 | Lost phone | Revocar device desde PC y usar app | Token antiguo falla, no se accede a memoria/acciones, pairing nuevo requerido | 401/403 logs | PENDING |
| A-09 | Version mismatch | Usar companion incompatible | Mensaje claro, no capabilities desconocidas ni ejecución | UI/log | PENDING |

## Matriz automatización y estabilidad

| ID | Caso | Procedimiento | Resultado esperado | Estado |
|---|---|---|---|---|
| E-01 | Watcher | Activar salud/metadata watcher permitido | Evento bounded, sin contenido de archivo, sin memoria automática | PENDING |
| E-02 | Schedule | Crear reminder y dejarlo vencer | Política SKIP/RUN_ONCE/ASK sin flood ni replay de acciones | PENDING |
| E-03 | Routine | Ejecutar rutina segura ≤5 steps | Mismo flujo pending→claim→preflight→verified completion | PENDING |
| E-04 | Backpressure | Generar carga controlada | Queue/dedup/chain/daily limits observables; chat interactivo mantiene prioridad | PENDING |
| E-05 | Restart | Reiniciar Core en estado idle y con reglas durable | Configuración persiste; locks/pending stale no se reejecutan | PENDING |
| E-06 | Upgrade/rollback | Ejecutar plan, snapshot, apply aprobado, postflight y rollback aprobado desde snapshot | No pérdida de DB/configuración; no mezcla selectiva de módulos; source preservado | PENDING |

## Métricas y criterios de decisión

Se registran idle CPU/RSS, import/startup, fast-action latency, context capture, UIA preflight, media latency, TTFT, chat total, event processing y Android roundtrip. No se inventan SLA universales: se compara contra una línea base del mismo equipo y configuración. La validación debe conservar al menos un caso PASS, un caso DENIED/UNAVAILABLE y un caso de cancelación por cada boundary.

Un caso obtiene **PASS** solo con resultado observable y reproducible en el equipo objetivo. **PENDING** significa que el recurso o hardware no estuvo disponible. **FAIL** significa que el procedimiento fue ejecutable y el resultado violó el contrato. Un FAIL de seguridad, ownership, no disclosure, preflight, stale target, token rotation o rollback bloquea la declaración de v1.0 final y obliga a mantener el estado RC1/no-release.

## Cierre de la campaña física

Al finalizar se guarda Doctor antes/después, hashes de artefactos, logs redacted, tabla de casos, versiones Core/PC/Android/protocol, estado de Flutter/APK, estado de Windows UIA/SMTC, blockers y recomendación. Se revocan tokens de prueba, se eliminan capturas/audio temporales y se conserva el snapshot hasta aceptar formalmente la actualización.
