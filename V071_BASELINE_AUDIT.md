# GAIA-AI v0.7.1 — Baseline Audit for v0.7.2

## Identidad del baseline

Este baseline se creó a partir de `GAIA-AI-v0.7.1-final.zip` y no modifica ni sobrescribe los artefactos estables entregados anteriormente. El nuevo worktree de desarrollo se encuentra en `/home/ubuntu/GAIA-AI-v0.7.2-dev/GAIA-AI-v0.7.1`.

| Elemento | Valor |
|---|---|
| Release de entrada | `0.7.1-pc` |
| Protocolo | `0.7.1` |
| Android | `0.7.1+1`, `versionName 0.7.1` |
| SQLite | Schema 6 |
| Huella del ZIP de entrada | `70c325fcfd7bbf4ac7d622ab242c6948b559005f5ab7fae23bd837a41ddcd204` |
| Entradas del ZIP de proyecto | 199 |
| Entradas del ZIP documental | 37 |
| Tests descubiertos | 73 `*_test.py` |
| Tests no-gate ejecutados en v0.7.1 | 72/72 PASS |
| Package gate | PASS antes de imports en árbol limpio |
| Compileall | PASS desde extracción limpia |
| Flutter/APK | PENDING; SDK no disponible |
| Windows UIA/SMTC/hardware | PENDING; sandbox Linux |

Los checksums de los artefactos de entrada fueron verificados con `sha256sum -c` y ambos ZIPs pasaron `unzip -tq`. La validación del baseline no convierte los mocks ni los contratos estáticos en validación física de Windows o Android.

## Controles heredados confirmados

La frontera de autoridad permanece fuera del LLM. El catálogo de capabilities es code-owned, los parámetros se validan y el Action Engine no ofrece shell libre, `shell=True`, `os.system`, `eval`, `exec`, PowerShell/CMD arbitrario ni click por coordenadas. UIA exige trust de aplicación, identidad de ejecutable, target esperado, redacción de password y protección de target stale. Media usa la ruta SMTC del sistema con mock/degrade honesto. LAN continúa opt-in y Android es companion, no ejecutor.

Resource Scope está centralizado en Core. `permission_entries` y `resource_scope_version` se transportan hacia las interfaces; los grants persistentes rechazan scope vacío, wildcard o unresolved. `ExecutionResult` distingue disponibilidad, observación, efecto y status; `UNAVAILABLE` no se promociona a éxito o ejecución verificada. Safe App trust queda ligado a ruta canónica y fingerprint SHA-256, de modo que un cambio de binario invalida el trust anterior.

## Brechas de integración reproducidas

| Brecha | Evidencia actual | Corrección requerida en v0.7.2 |
|---|---|---|
| Dual truth de contexto | `desktop_api.py` llama a `context_providers.collect_desktop_context()`; el módulo legacy calcula active window de forma independiente | Crear `DesktopContextService` canónico y hacer que el legacy sea un adapter |
| Schema de snapshot incompleto | `desktop_context.py` devuelve `available`, `observed_at`, ventana básica y display, pero no `snapshot_id`, `host_id`, `expires_at`, canonical app/trust, focused control o media | Definir snapshot versionado, TTL y niveles de contexto |
| GUI/HTTP sin contrato de producción probado | Texto y SSE envían `pc_context`; las pruebas existentes no inspeccionan JSON saliente mediante el cliente real | Añadir test de producción con `LumenDesktopAPI` y servidor capturador |
| Voz sin contexto | `desktop_api.send_voice()` y `/api/chat/voice` reconstruyen la solicitud sin snapshot equivalente | Transportar envelope/snapshot de voz con la misma política que texto |
| Terminal divergente | `lumen-pc/client.py` envía solo mensaje, sesión y device en chat/SSE/voice | Usar envelope compartido y contexto canonicalizado, sin inventar HWND remoto |
| Android no puede conocer foreground PC | No existe bridge explícito de preflight contextual al target host | Añadir preflight read-only autenticado al `target_host` y validar el target en PC |
| Preflight no es primer recurso uniforme | La resolución de capability, target, riesgo y scope está repartida entre rutas y executor | Crear resultado first-class de preflight read-only antes de permiso |
| Captura usa contrato local | La captura on-demand existe, pero v0.7.2 exige `capture_id`, ownership, TTL y retrieval autenticado | Introducir registro temporal de captura sin memoria/backup automático |
| VisionBackend no existe como abstracción completa | La captura/UIA no ofrece interfaz de visión opt-in con degradación explícita | Añadir interfaz desactivada por defecto; `VISION_UNAVAILABLE` si falta backend |
| Planes carecen de bindings formales | El plan bounded existe, pero la salida de open/wait y bindings deben quedar tipados | Extender steps con `step_id`, `depends_on`, bindings y result status |
| Android build depende del entorno | Wrapper/Gradle están presentes, pero Flutter y Android SDK no están instalados en sandbox | Intentar build legítimo; si no es posible, documentar blocker exacto, nunca fabricar APK |
| Diagnostics incompleto | Doctor aún no expone todos los estados de contexto/UIA/capture/vision/remote preflight/trust/scope | Añadir checks read-only sin crear runtime ni secretos |

## Prioridad y decisión arquitectónica

La corrección prioritaria es **un servicio de contexto canónico** en el PC con un snapshot efímero versionado. `DesktopAPI`, terminal y voz deben construir un envelope común; Core debe tratarlo como dato no autoritativo y el host target debe resolver y revalidar cualquier identidad remota. `context_providers` se conserva solo como compatibilidad y delega al servicio canónico. Esta opción elimina la doble verdad sin introducir un segundo daemon ni una base persistente de vigilancia.

El preflight se implementará como objeto read-only que normaliza capability y parámetros, resuelve target, scope y riesgo, informa disponibilidad y decide si hace falta confirmación. Nunca ejecutará efectos. La ejecución posterior seguirá pasando por permission policy, confirmación, revalidación, ActionHost y resultado verificado.

## Criterio de entrada para v0.7.2

No se debe iniciar v0.8.0 hasta que v0.7.2 tenga routing real desde GUI/voz/terminal/Android cuando corresponda, snapshot y envelope coherentes, preflight first-class, captura ownership/TTL, Android build intentado honestamente, regresión completa y ZIP final independiente con checksum y documentación. Las capacidades físicas de Windows, Flutter/APK y hardware seguirán clasificadas como **PENDING** si el entorno continúa sin esas dependencias.
