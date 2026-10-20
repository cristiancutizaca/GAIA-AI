HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.8.0 — Requisitos y evidencia

## Propósito

GAIA-AI v0.8.0 introduce el **Event Engine** y una capa de automatización personal bounded. El objetivo es permitir reglas, rutinas y schedules persistentes sin crear una segunda frontera de ejecución. El Core sigue siendo la autoridad de autenticación, ownership, política y resultado; el PC Action Host sigue siendo la autoridad de preflight y efecto local.

> **Regla de seguridad:** los eventos son datos, nunca autoridad. Ningún payload puede conceder permisos, cambiar el modo de automatización, desactivar el kill switch o convertir una capability desconocida en ejecutable.

## Criterios de aceptación

| ID | Criterio | Implementación | Evidencia | Estado |
|---|---|---|---|---|
| V080-01 | Core, protocolo, Action Host, Android y Doctor declaran 0.8.0 coherentemente. | `config.py`, `lan_protocol.py`, `action_host.py`, `request_envelope.py`, `pubspec.yaml`, Gradle y `gaia_doctor.py`. | `smoke_test.py`, `action_host_test.py`, `lan_api_test.py`, `android_onboarding_contract_test.py`, `v051_test.py`. | PASS |
| V080-02 | La migración v0.7.2→v0.8.0 eleva SQLite a schema 7 y crea solo tablas bounded justificadas. | `memory.py` añade `automation_rules`, `routines`, `schedules`, `automation_runs`, `notifications` y `automation_event_log`, con índices acotados. | `db_upgrade_test.py`, `permission_memory_test.py`. | PASS |
| V080-03 | El Event Engine acepta únicamente tipos y severidades allowlisted. | `event_engine.py` valida tipo, severidad, payload UTF-8 bounded, TTL y profundidad de cadena. | `event_engine_v080_test.py`, `automation_loop_prevention_v080_test.py`. | PASS |
| V080-04 | La cola tiene backpressure, deduplicación y ciclo de vida limpio. | `asyncio.Queue` bounded, dedup por clave/TTL y stop cancelable. | `event_engine_v080_test.py`, `automation_loop_prevention_v080_test.py`. | PASS |
| V080-05 | Las condiciones de reglas usan operadores tipados, sin `eval`, shell, expression ni command. | `AutomationEngine` limita `eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `exists` y `contains_safe`. | `automation_scheduler_v080_test.py`, `automation_injection_v080_test.py`, `automation_api_v080_test.py`. | PASS |
| V080-06 | Las reglas y rutinas tienen ownership por dispositivo. | Endpoints y store filtran por `owner_device`; mutaciones cruzadas devuelven rechazo o no-op seguro. | `automation_api_v080_test.py`, `automation_ownership_v080_test.py`. | PASS |
| V080-07 | `OFF` es el default y bloquea activación de reglas; el kill switch gana a cualquier regla. | `AutomationRuntime`, endpoints `/automation/mode` y `/automation/pause`, estado persistente de acciones existente. | `automation_api_v080_test.py`, `automation_kill_switch_v080_test.py`, `smoke_test.py`. | PASS |
| V080-08 | `NOTIFY_ONLY` produce notificaciones sin ejecutar rutinas. | `AutomationEngine` separa notificación y executor. | `automation_scheduler_v080_test.py`. | PASS |
| V080-09 | Dry-run valida sin producir efectos, pending actions, llamadas LLM ni notificaciones. | `AutomationEngine.dry_run()` solo devuelve preview bounded. | `automation_dry_run_v080_test.py`, `automation_api_v080_test.py`. | PASS |
| V080-10 | Las rutinas están limitadas a cinco steps y riesgo unattended máximo 2. | `AutomationEngine._validate_steps()` y `automation_action_bridge.py` aplican allowlist, args escalares bounded y bloqueo de riesgo alto. | `automation_routine_permissions_v080_test.py`, `automation_injection_v080_test.py`. | PASS |
| V080-11 | Las rutinas no pueden eliminar archivos, reiniciar/apagar el sistema, detener procesos, hacer commits destructivos ni auto-concederse permisos. | `FORBIDDEN_UNATTENDED`, `SAFE_ROUTINE_ACTIONS` y detección de self-grant. | `automation_routine_permissions_v080_test.py`. | PASS |
| V080-12 | La ejecución real usa el pending-action protocol existente y no bypass de preflight. | El bridge escribe un pending action aprobado solo para una rutina segura; `RemoteActionHost` reclama, adjunta contexto local, ejecuta preflight y completa con resultado verificado. | `automation_e2e_v080_test.py`, `remote_action_host_test.py`, `remote_action_e2e_v062_test.py`, `preflight_v072_test.py`. | PASS |
| V080-13 | El resultado del Action Host reconcilia `automation_runs` con evidencia mínima y determinista. | `action.completed`/`action.failed` publica metadata bounded; `AutomationRuntime` pasa queued a completed/failed únicamente con `execution_verified`. | `automation_e2e_v080_test.py`. | PASS |
| V080-14 | Scheduler persistente soporta ONE_TIME, DAILY, WEEKDAYS, WEEKLY e INTERVAL con UTC y timezone. | `scheduler.py` y `automation_store.py` usan `next_due_at` y claim SQL atómico. | `automation_scheduler_v080_test.py`. | PASS |
| V080-15 | Schedules atrasados siguen SKIP, RUN_ONCE o ASK sin flood. | Umbral de atraso, avance de `next_due_at`, una sola reclamación y notificación ASK. | `automation_missed_schedule_v080_test.py`. | PASS |
| V080-16 | Watchers se activan lazy, aplican backoff y no capturan contenido de archivos, clipboard, screenshots o recording proactivo. | `WatcherRegistry`, `HealthWatcher`, `SystemWatcher` y `FileWatcher` metadata-only. | `watchers_notifications_v080_test.py`. | PASS |
| V080-17 | Notificaciones son deterministic, bounded, redacted y controlables por ownership. | `NotificationService`, store y endpoints list/patch. | `watchers_notifications_v080_test.py`, `automation_quiet_hours_v080_test.py`, `automation_api_v080_test.py`. | PASS |
| V080-18 | Quiet hours están desactivadas por defecto y pueden suprimir rutinas o degradarlas a notify-only según política. | Configuración explícita y policy `skip`/`notify_only`. | `automation_quiet_hours_v080_test.py`. | PASS |
| V080-19 | La automatización no consume LLM de fondo para ejecutar reglas y no bloquea la ruta interactiva. | Eventos, condiciones, notifications y safe bridge son deterministas; contador de background LLM permanece en cero. | `automation_background_priority_v080_test.py`, `automation_e2e_v080_test.py`. | PASS |
| V080-20 | GUI PC ofrece modo, pausa, reglas y notificaciones; Android ofrece vista companion sin executor local. | `gui.py`, `desktop_api.py`, `automation_screen.dart`, `settings_screen.dart`, `lumen_service.dart`. | `gui_import_test.py`, `android_onboarding_contract_test.py`; build Flutter físico pendiente. | PASS / PENDING |
| V080-21 | Brain Backup conserva reglas, rutinas y schedules durables, pero no cola efímera ni locks. | Integración de backup mantiene datos durables y excluye runtime local. | `brain_backup_scheduler_test.py`, `release_package_test.py`. | PASS |
| V080-22 | El paquete contiene allowlist, documentación, tests, higiene y checksum verificable. | `tools/build_release.py` usa staging, rutas seguras, timestamps fijos, exclusión runtime y `sha256`. | `release_package_test.py`, gate de ZIP limpio. | PASS |

## Contratos de seguridad

La ejecución unattended solo puede comenzar en `ROUTINES` o `FULL_CONFIGURED`, con regla enabled, rutina enabled, cooldown satisfecho, quiet-hours satisfechas, límite diario disponible y kill switch desactivado. La rutina se valida dos veces: al persistir o previsualizar y justo antes de crear el pending action. Las capabilities de la rutina son nombres conocidos del catálogo local; no se aceptan comandos, expresiones, cadenas de shell ni valores que modifiquen autoridad.

El pending action se dirige al `pc-main` por defecto, conserva un `automation_run_id` y aparece en el mismo endpoint que consume el RemoteActionHost. El bridge no importa ni invoca ejecutores del sistema operativo. La autorización unattended es únicamente `RULE_SCOPED_SAFE`; el Action Host aún debe autenticarse, reclamar la acción, hacer preflight local y publicar completion. Si el resultado no contiene evidencia verificable, el run termina como fallo y GAIA no afirma que el efecto ocurrió.

Los payloads de eventos se tratan como observaciones. Un nombre de archivo como `x; rm -rf /`, un título de ventana con sustitución de shell o texto que diga “ignore previous instructions” nunca se concatena a un comando ni modifica el policy. Los watchers de archivos emiten metadata acotada y no contenido.

## API entregada

| Método | Ruta | Propósito |
|---|---|---|
| GET | `/api/automation/status` | Estado de runtime, mode, pause, scheduler, watchers, cola y métricas. |
| POST | `/api/automation/mode` | Cambio master-only entre OFF, NOTIFY_ONLY, ROUTINES y FULL_CONFIGURED. |
| POST | `/api/automation/pause` | Kill switch master-only para detener ejecución background. |
| GET/POST | `/api/automations` | Listar o crear reglas con ownership y preview confirmado. |
| POST | `/api/automations/dry-run` | Previsualizar una regla y evento sin efectos. |
| POST | `/api/automations/{rule_id}/enabled` | Habilitar o deshabilitar una regla dentro de su ownership. |
| GET/POST | `/api/routines` | Listar o crear rutinas safe bounded. |
| POST | `/api/routines/{routine_id}/enabled` | Habilitar o deshabilitar una rutina dentro de su ownership. |
| GET/POST | `/api/schedules` | Listar o crear schedules persistentes. |
| POST | `/api/schedules/{schedule_id}/enabled` | Habilitar o deshabilitar un schedule dentro de su ownership. |
| GET/PATCH | `/api/notifications` | Consultar y marcar notificaciones como leídas/dismissed. |

## Evidencia de pruebas

La suite de desarrollo v0.8.0 contiene **91 tests ejecutables**: 76 heredados de v0.7.2, 14 contract tests de automatización y el E2E de reconciliación. La ejecución se realiza con `PYTHONDONTWRITEBYTECODE=1` y una limpieza previa de runtime artifacts. El resultado de la última regresión limpia es **91 PASS, 0 FAIL**.

El build Android no se etiqueta como PASS físico porque Flutter no está disponible en el sandbox. El contrato estático de pubspec, Gradle, servicio, onboarding y pantalla de automatización sí se valida. La UIA/SMTC, micrófono, GPU, Ollama real, audio real, LAN física y Action Host Windows requieren la validación física descrita en `PHYSICAL_VALIDATION_WINDOWS.md`.

## Rollback y restauración

Para volver a v0.7.2 se conserva el artefacto congelado `GAIA-AI-v0.7.2-final.zip`; no se sobreescribe con v0.8.0. Antes de restaurar un Brain Backup se deben revisar reglas y schedules y no se deben replayar automáticamente acciones vencidas. El rollback de aplicación no debe mezclar la SQLite schema 7 con binarios v0.7.2 sin una copia y migración controladas.

## Resultado

v0.8.0 puede congelarse cuando el builder y la extracción limpia reproduzcan la suite sin fallos, el checksum coincida y las limitaciones físicas permanezcan explícitamente etiquetadas. No se declara completado ningún efecto local que solo pueda demostrarse en Windows o Android físico.
