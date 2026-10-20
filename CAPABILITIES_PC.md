# Capabilities PC y Action Host — v0.6.1

## Principio de autoridad

El registry de capabilities es **code-owned**. El LLM puede proponer un intent conocido, pero no puede registrar capabilities, inventar executors, añadir comandos, cambiar scopes o escoger ejecutables. El PC valida nuevamente el contrato antes de ejecutar.

Cada definición contiene nombre canónico, categoría, descripción, nivel de riesgo, permisos requeridos, sistemas soportados, esquema de parámetros, política de confirmación, reversibilidad, timeout y bandera `implemented`.

| Categoría | Ejemplos | Política |
|---|---|---|
| `apps` | `apps.list`, `apps.is_running`, `apps.open` | Discovery read-only; apertura solo desde Safe App Registry |
| `windows` | `windows.list`, `windows.focus`, `windows.minimize`, `windows.close` | Identificador estructurado; no coordenadas; adapter local con degradación explícita |
| `files`/`folders` | `files.exists`, `files.info`, `folders.open` | Scope validado; mutaciones requieren confirmación |
| `processes` | `processes.list`, `processes.info`, `processes.stop` | Lectura limitada; stop requiere metadata y aprobación |
| `system`/`power` | `system.status`, `system.shutdown` | Read-only implementado; power crítica no implementada por defecto |
| `audio`/`display`/`clipboard` | Volumen/mute, pantallas y clipboard | Adapters estructurados; escritura/lectura sensible queda bajo policy y no registra contenido |
| `network` | `network.status`, `network.adapters`, `network.ip` | Read-only |
| `projects`/`git` | Proyectos trusted, tests registrados y status Git | Comandos únicamente registrados; proyectos trusted |
| `browser` | `browser.open`, `url.open` | URL limitada a HTTP(S) |

## Safe App Registry 2.0

El catálogo de aplicaciones conserva Calculadora, Bloc de notas, Spotify y VS Code. Cada entrada tiene aliases, comandos por OS, estrategia de lanzamiento, nombres de proceso, OS soportados y riesgo base. La discovery solo informa disponibilidad y nunca concede permiso ni ejecuta el proceso.

## Boundary de ejecución

`ActionHost` recibe una respuesta de acción o plan, la procesa con `ActionCoordinator`, llama únicamente a `ActionEngine.execute`, produce `VerifiedActionResult` y escribe una línea de auditoría encadenada. El digest de cada registro incluye el digest anterior, identificador de acción, sesión, dispositivo, resultado, host y timestamp. El texto de personalidad no participa en la decisión factual.

Un resultado `execution_verified=false` no puede usarse para afirmar que el efecto ocurrió. Un dry-run, un bloqueo, una cancelación o una capability no implementada son estados distintos de un éxito ejecutado.

## Validación

La cobertura automatizada se concentra en `capability_registry_test.py`, `safe_apps_test.py`, `action_host_test.py`, `remote_action_host_loop_test.py`, `action_grounding_test.py`, `post_action_claim_scope_test.py`, `permission_api_test.py` y `kill_switch_test.py`. La prueba física de ventanas, audio, clipboard, displays y procesos en Windows queda pendiente hasta disponer del host y del entorno físico correspondientes.
