HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.8.0 — Diseño del Event Engine

## Propósito y decisión arquitectónica

GAIA-AI v0.8.0 hará que el sistema sea consciente de eventos, pero **no** lo convertirá en un agente autodirigido sin límites. Se adopta un Event Engine interno, ligero y lifecycle-managed dentro del Core FastAPI. Esta decisión conserva la ejecución local, evita introducir una segunda autoridad y permite que el scheduler se detenga limpiamente cuando el Core se apaga.

El scheduler no pretende ser un servicio 24/7 independiente. Si el usuario necesita disponibilidad continua, el equipo deberá permanecer encendido y el proceso del Core deberá estar supervisado por el sistema operativo. No se utiliza una tarea externa para polling minuto a minuto: el motor interno mantiene intervalos bounded y solo inicia watchers cuando existe una regla que los necesita.

> **Eventos son datos, no autoridad.** Un título de ventana, nombre de archivo, branch Git, estado de Ollama o payload de watcher nunca puede cambiar permisos, crear una capability, elegir un ejecutor ni confirmar un efecto.

## Flujo de autoridad

Todo efecto iniciado por automatización sigue la misma frontera de v0.7.2:

```text
Evento observado
  → validación de schema y límites
  → deduplicación/cooldown/cadena
  → evaluación de regla tipada
  → quiet hours / modo / run limit
  → preview o ejecución autorizada
  → preflight del Action Host
  → Permission Memory y confirmación cuando corresponde
  → coordinator bounded
  → VerifiedActionResult
  → notificación factual y auditoría
```

Las rutinas no reciben comandos libres. Sus steps son referencias a capability IDs existentes con parámetros que vuelven a validarse en el host. El LLM puede proponer una regla o rutina desde lenguaje natural, pero el usuario debe revisar el preview, hacer dry-run y confirmar antes de guardar.

## EventEngine

### Modelo de evento

| Campo | Regla |
|---|---|
| `event_id` | UUID local, único y no reutilizable |
| `event_type` | string allowlisted, por ejemplo `ollama.offline`, `schedule.due` o `file.changed` |
| `source` / `source_id` | watcher o subsistema code-owned; nunca texto ejecutable |
| `host` / `device` | host que observó el evento y dispositivo opcional |
| `timestamp` / `expires_at` | UTC ISO-8601; eventos vencidos se descartan |
| `payload` | JSON bounded, redacted y limitado por tamaño; no contiene secretos ni contenido de archivos |
| `severity` | `info`, `warning`, `error` o `critical` |
| `dedup_key` | clave normalizada para dedup temporal |
| `chain_id` / `chain_depth` | prevención de loops y fan-out sin límite |

La cola es `asyncio.Queue(maxsize=256)` y aplica backpressure. Si se llena, se descartan eventos no críticos con métrica explícita; nunca se bloquea el request interactivo esperando al watcher. Se mantiene un índice de dedup por tiempo y cooldown por regla/evento. `chain_depth` tiene un máximo configurable de 4 y no se publican eventos derivados cuando se alcanza.

El bus tiene subscribers code-owned: `AutomationEngine`, `NotificationService`, `Diagnostics`, `Audit` y un stream autenticado para Android. No se carga código desde eventos ni se permiten subscribers dinámicos.

## Catálogo de eventos

El catálogo inicial incluye `core.started`, `core.ready`, `core.stopping`, `core.error`; `ollama.online`, `ollama.offline`, `ollama.latency_high`; `device.paired`, `device.connected`, `device.disconnected`, `device.revoked`; `action.requested`, `action.awaiting_confirmation`, `action.approved`, `action.claimed`, `action.started`, `action.completed`, `action.failed`; `app.started`, `app.closed`; `battery_low`, `battery_state_changed`, `cpu_high`, `memory_high`, `disk_low`, `network_changed`; `git_dirty`, `git_clean`, `branch_changed`; `file.changed`; y `schedule.due`.

Los eventos de archivo solo observan carpetas Trusted Folders configuradas explícitamente y emiten metadata limitada. No se ingiere contenido, no se hace OCR, no se captura pantalla, no se observa clipboard y no se graba micrófono de forma proactiva.

## AutomationEngine y reglas

### Modelo persistente de regla

| Campo | Regla |
|---|---|
| `rule_id`, `name` | identificadores locales bounded |
| `owner_device` | propietario autenticado; master puede administrar según policy |
| `enabled` | deshabilitable sin borrar historial |
| `trigger` | evento o schedule tipado |
| `conditions` | operadores `eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `exists`, `contains_safe` |
| `routine_id` / `steps` | rutina persistente o steps canónicos bounded |
| `cooldown` / `run_limit` | protección contra repetición y flooding |
| `quiet_hour_policy` | `skip`, `notify_only` o `defer` |
| `schema_version`, timestamps | migración y auditoría |

No existe un campo `command`, `shell`, `expression`, `eval` o script. Las condiciones se interpretan mediante un dispatcher de operadores explícito. `contains_safe` solo funciona sobre campos de payload permitidos y no convierte texto en código.

Las reglas nuevas pasan por cuatro estados operativos: draft, previewed, enabled y disabled. `POST /api/automations/dry-run` no modifica el sistema ni ejecuta efectos. `POST /api/automations` exige un preview confirmado, ownership y policy válida. El LLM no puede guardar una regla directamente.

### Rutinas

Una rutina es un plan reutilizable con `routine_id`, nombre, owner, hasta cinco steps, capabilities requeridas, riesgo máximo, failure policy y enabled. Reutiliza la salida estructurada de v0.7.2 y el `ActionCoordinator`; no hace una segunda interpretación LLM durante la ejecución. Cada step vuelve a pasar capability validator, resource scope, Permission Memory, preflight, target revalidation y result semantics.

Por defecto no se ejecutan unattended acciones de riesgo 3/4, borrado, power, comunicación externa genérica, operaciones financieras ni cambios de permisos. Restart/shutdown siguen requiriendo confirmación. Los grants rule-scoped, si se habilitan, deben ser más estrechos que los grants normales y nunca pueden concederse a sí mismos.

## Scheduler y missed runs

El scheduler guarda schedules durables en SQLite, calcula `next_due_at` en UTC usando timezone declarado y despierta con un intervalo máximo de 30 segundos, sin busy loop. Los tipos son `ONE_TIME`, `DAILY`, `WEEKDAYS`, `WEEKLY` e `INTERVAL`.

La reclamación de un due run es atómica mediante `schedule_run_id`, estado `pending/running/completed/skipped/failed`, `locked_at` y `finished_at`. Un restart no reejecuta ciegamente una ejecución completada. Un schedule vencido usa una política explícita `SKIP`, `RUN_ONCE` o `ASK`, y nunca produce una inundación de ejecuciones atrasadas. El intervalo mínimo es 60 segundos y cada schedule tiene `max_runs_per_day` bounded.

Los recordatorios simples son first-class y deterministas: crean una notification sin llamar al LLM. La generación de estilo o sarcasmo solo ocurre si el modo lo permite y está sujeta a rate limit; el camino principal de alerta no depende de Qwen para reportar que Ollama está offline.

## Watchers lazy

| Watcher | Datos permitidos | Activación |
|---|---|---|
| `HealthWatcher` | estado/latencia de Core y Ollama | reglas de health |
| `SystemWatcher` | CPU, RAM, disco, batería y red | umbral configurado |
| `AppWatcher` | apps relevantes y estado started/closed | apps explícitas/trusted |
| `ProjectWatcher` | Git dirty/clean/branch en proyectos trusted | proyectos explícitos |
| `FileWatcher` | metadata de cambios en Trusted Folders | carpetas explícitas |
| `DeviceWatcher` | paired/connected/disconnected/revoked | dispositivos autorizados |

Los watchers arrancan solo cuando una regla habilitada los requiere. Health y System aplican muestreo bounded, backoff y umbral sostenido para no alertar por spikes. El estado del watcher es efímero y no se convierte en historial permanente de foreground.

## Proactividad, privacidad y notificaciones

Los modos son `OFF`, `NOTIFY_ONLY`, `ROUTINES` y `FULL_CONFIGURED`. El default permanece `OFF`, incluso si existen reglas almacenadas. Un botón separado pausa automatizaciones y el kill switch de acciones tiene autoridad superior. Quiet hours están deshabilitadas hasta que el usuario las configure; los defaults conservadores son no enviar y no ejecutar.

`NotificationService` conserva notificaciones bounded con ID, título, mensaje, severidad, source, timestamp, device scope, read, dismissed y sensitive. Las notificaciones sensibles se redactan en lockscreen/Android. Se aplica límite diario, cooldown, dedup y prioridad: un request interactivo del usuario gana sobre el LLM de background.

No hay watcher de clipboard, screenshots proactivas ni recording proactivo. El contexto foreground mantiene el TTL de v0.7.2 y no se persiste en `automation_events` ni Brain Backup salvo una estadística agregada no sensible.

## Persistencia y backup

La migración v0.7.2→v0.8.0 eleva el schema de memoria a 7 y crea únicamente tablas justificadas: `automation_rules`, `routines`, `schedules`, `automation_runs`, `notifications` y opcionalmente un `event_log` bounded. Se añaden índices para `enabled/next_due_at`, ownership y dedup.

Brain Backup incluye reglas, rutinas, schedules y preferencias durables, pero excluye la cola de eventos, locks, tokens de ejecución, payloads efímeros y notificaciones ya vencidas. Restore nunca reproduce inmediatamente un schedule atrasado: todos los due jobs pasan a `ASK` o quedan pausados para revisión, de acuerdo con la policy elegida.

## API y clientes

El Core expone rutas autenticadas para listar/crear/actualizar/deshabilitar reglas, rutinas y schedules; ejecutar dry-run; pausar/reanudar automatizaciones; listar/marcar/descartar notificaciones; y consultar métricas. Android puede mostrar Automations, Routines, Schedules y Notifications cuando el build esté disponible, pero sigue siendo companion no ejecutor. El stream de eventos reutiliza autenticación, ownership y reconnect bounded.

La GUI PC incorpora paneles de Automations, Routines, Schedules y Notifications. El editor presenta `WHEN`, `IF`, `THEN`, cooldown, permisos, riesgo y dry-run en lenguaje humano; el usuario no necesita escribir JSON. Los payloads enviados por clientes son propuestas y nunca sustituyen el snapshot local del host ni el preflight.

## Métricas y aceptación

Las métricas mínimas son `event_queue_depth`, `event_ms`, `rules_checked`, `rules_triggered`, `routine_ms` y `background_llm_calls`. El motor debe permanecer casi idle cuando no hay watchers necesarios y no puede usar busy loops.

| Gate | Evidencia requerida |
|---|---|
| Event model/bus | schema, queue bounded, TTL, dedup, cooldown y chain depth |
| Automation rules | operadores typed, preview, dry-run, ownership y no self-grant |
| Routines | máximo cinco steps, permisos por step y resultados verificados |
| Scheduler | UTC/timezone, atomic due, missed policy y duplicate protection |
| Watchers | lazy start, sustained threshold, backoff y metadata-only files |
| Notifications | deterministic, quiet hours, privacy redaction y bounded retention |
| Safety | kill switch, interactive priority, injection/loop tests y no `eval` |
| Backup | durable rules included; queue/locks/payloads ephemeral excluded |
| Client path | GUI/API/Android stream contracts; Flutter físico PENDING si no hay SDK |
| Performance | zero busy loop y background LLM rate limit |

La release v0.8.0 solo puede congelarse cuando estos gates pasan y la suite heredada de v0.7.2 continúa en cero fallos. Si una prueba física no es posible, se etiqueta `AUTOMATED`, `MOCK`, `STATIC` o `NOT TESTED`; nunca `PHYSICAL` sin hardware real.
