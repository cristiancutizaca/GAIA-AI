# GAIA-AI v0.7.0 — Desktop Foundation

## Alcance

La foundation v0.7.0 permite que GAIA observe el estado del escritorio de forma estructurada sin convertirse en un agente de clics por coordenadas. La regla central es **observar estructuralmente primero**: el contexto activo y los controles UI Automation se consultan bajo demanda, con caché TTL breve y sin almacenar permanentemente cada ventana o aplicación abierta.

## Modelo de contexto activo

`desktop.context` devuelve un snapshot efímero con `active_application`, `active_window`, `window_title`, `process`, `display`, `bounds`, `idle_status` opcional y `foreground_app_category`. El proveedor debe devolver `available=false` y una explicación estable cuando el host no sea Windows o falte el adapter. No se toman capturas de pantalla para producir este contexto.

El snapshot se conserva únicamente en memoria durante un TTL corto. Una solicitud contextual resuelve el target en el momento de crear la acción y guarda la identidad observada; una confirmación posterior no vuelve a resolver el pronombre contra otra ventana que se haya convertido en foreground.

## Modelo UIA

Las capabilities read-only iniciales son `uia.inspect_window`, `uia.list_controls` y `uia.get_focused_control`. Cada control se normaliza a `control_id`, `automation_id`, `control_type`, `name`, `enabled`, `focused`, `bounds`, `value_available`, `invoke_available` y `sensitive`. Los campos de valor de controles password o seguridad nunca se devuelven.

La interacción posterior se limita a `uia.focus_control`, `uia.invoke_control` y `uia.set_value`. Requiere aplicación trusted, control resuelto de forma única, policy autorizada y `sensitive=false`. Los nombres `Delete`, `Remove`, `Uninstall`, `Format`, `Reset`, `Purchase`, `Send` y `Pay` elevan el riesgo, pero la etiqueta nunca sustituye a la autorización code-owned.

## Capturas

`screen.capture_display` y `screen.capture_window` son capacidades read-only, on-demand y separadas de UIA. El resultado puede existir en memoria o en un archivo temporal bajo el directorio runtime; debe limpiarse al finalizar. No hay vigilancia continua, persistencia automática ni inclusión automática en memoria o Brain Backup. El backend de visión permanece abstraído y desactivado por defecto; no se descarga ningún modelo multimodal automáticamente.

## Trust y seguridad remota

UIA solo puede interactuar con aplicaciones trusted por identidad ejecutable canónica, no por display name. Un Android remoto no obtiene permisos más amplios que `pc-main`; las solicitudes pasan por el mismo Permission Memory, confirmación, target host y VerifiedActionResult. El host no recibe código, ejecutores, comandos shell ni selectores arbitrarios desde el LLM.

## Stale-target protection

Cada target de ventana contiene `window_id`, `pid`, `process_name`, `process_executable` cuando esté disponible, título y bounds observados. Antes de ejecutar una interacción se verifica que el handle siga perteneciendo al mismo proceso y que la identidad no haya cambiado. Si el handle fue reutilizado, el control dejó de ser único o la app ya no está trusted, la acción se rechaza de forma segura.

## Rendimiento

El proveedor evita escanear el árbol completo continuamente. El contexto foreground usa polling de baja frecuencia o eventos Windows cuando estén disponibles; UIA inspecciona únicamente la ventana seleccionada y bajo demanda. Todas las rutas incluyen duración, disponibilidad y motivo de degradación en diagnostics, sin enviar árboles completos al LLM salvo que una explicación lo requiera.

## Capabilities iniciales

| Capability | Naturaleza | Riesgo inicial | Requisito principal |
|---|---|---:|---|
| `desktop.context` | Read-only fast path | 0 | Snapshot efímero |
| `uia.inspect_window` | Read-only | 0/1 | Ventana seleccionada y trusted o policy metadata |
| `uia.list_controls` | Read-only | 0/1 | No exponer password values |
| `uia.get_focused_control` | Read-only | 0/1 | Control foreground actual |
| `uia.focus_control` | Interacción | 1 | Identidad única y Permission Memory |
| `uia.invoke_control` | Interacción | 2 | Control no sensible y confirmación según riesgo |
| `uia.set_value` | Interacción | 2 | Control editable no sensible; nunca password |
| `screen.capture_display` | Read-only on-demand | 1 | Permiso separado y cleanup |
| `screen.capture_window` | Read-only on-demand | 1 | Window identity y cleanup |

## Límites deliberados

Esta foundation no incorpora mouse automation, clicks por coordenadas, teclado arbitrario, PowerShell/CMD arbitrario, credenciales, password manager, plugins ejecutables dinámicos, descarga automática de modelos ni agentes recursivos. Los adapters de aplicaciones son code-owned y no cargan código desde paths enviados por el LLM.
