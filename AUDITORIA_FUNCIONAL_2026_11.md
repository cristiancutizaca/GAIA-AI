# GAIA 2.0 RC3 | Auditoría funcional para el objetivo de asistente administrador

**Origen:** `GAIA-AI-main.zip` facilitado por el usuario. **Entorno de verificación:** Linux/Python 3.13, sin Ollama ni Windows UI Automation. **Política:** pruebas locales de lectura, sandbox temporal para modificaciones, sin operaciones peligrosas sobre el equipo.

## Objetivo de producto

GAIA debe interpretar encargos en lenguaje natural, planificar pasos, inspeccionar el estado real de la PC, ejecutar acciones mediante un host de confianza, comprobar sus efectos y recuperar tareas interrumpidas. Administración programada y proactiva solo bajo reglas/permisos configurados. Prioridad: funcionamiento por encima de retoques visuales.

## Evidencia de funcionamiento

- **Core:** FastAPI ejecutado, `/api/health` respondió HTTP 200 en sesión anterior.
- **ActionEngine:** `system_status`, `system_processes` y `file_exists` fueron invocados realmente con éxito durante esta auditoría. `file_list` fallaba por falta del método `_file_list`.
- **Permisos/preflight:** la capa `preflight_contract` validó acciones read-only sin ejecutarlas. En Linux, `windows_list` quedó bloqueado por plataforma. La validación `file_delete` reconoce el contrato, pero la ejecución no fue solicitada.
- **Catálogo:** 76 capacidades declaradas `implemented=True`, 87 acciones locales del motor. **Esto es registro de código, no garantía de que todas funcionen**; se encontraron tres nombres de métodos sin correspondencia.
- **Reconocimiento natural:** con trece encargos de ejemplo, el detector determinista asignó un nombre de acción a tres; los demás no se reconocieron en esa ruta. El planificador `gaia_platform.planner.Planner.plan` produjo un solo paso en los trece casos, no planes autónomos que ejecuten acciones en secuencia.
- **Limitación concreta:** «revisa la temperatura de mi procesador y GPU» fue clasificado como `system_cpu`, cuyo resultado muestra porcentaje de uso, no temperatura.

## Reparación aplicada en una COPIA del ZIP

Se mantuvieron los métodos de implementación preexistentes y se incorporaron tres adaptadores con nombres esperados por `ActionEngine.execute`:

- `file_list` → `_list_files`.
- `file_open` → `_open_file`.
- `folder_create` → `_create_folder`.

Pruebas nuevas: comprobación de los 87 handlers, listado real de archivos, creación de carpeta temporal, apertura de archivo simulada mediante monkeypatch (sin iniciar una aplicación), y cadena completa `ActionHost` → preflight → ActionCoordinator → ActionEngine → auditoría para **listado de archivos de prueba**.

**Resultado tras el parche:** `pytest -q`: **24 passed** en este entorno. Las pruebas físicas de Windows, integración de Ollama y voz siguen pendientes; las 24 no demuestran autonomía completa.

## Prioridades para cumplir la visión de GAIA

**P0: encargo → plan verificable.** El planificador actual toma decisiones mayormente por expresiones regulares y construye un único paso. Evolucionar hacia interpretación estructurada de un encargo, pasos de 1..N, dependencias y criterios de éxito; ejecutar solo herramientas permitidas por ActionHost. Pruebas de tareas de varios pasos, cancelación y recuperación.

**P1: administrar una PC de verdad.** Windows UI Automation para abrir, inspeccionar y manipular ventanas y controles; detección del proceso/ventana correctos; resultados verificados; fallos reportados. Ejemplo de aceptación: abrir VS Code, localizar un proyecto autorizado, ejecutar tests registrados, leer resultados y producir un informe. Validación física en Windows obligatoria.

**P1: observabilidad y mantenimiento.** CPU, GPU AMD/NVIDIA, VRAM, temperaturas (con sensor real disponible), RAM, discos, servicios y procesos. Alertas basadas en umbrales; acciones no destructivas automáticas cuando estén autorizadas. `nvidia-smi` por sí solo no cubre AMD.

**P1: archivos y proyectos.** Indexar directorios autorizados, listar/copiar/organizar con vista previa, registrar proyectos trusted y comandos de arranque/test; respaldar antes de modificaciones masivas. No ejecutar comandos arbitrarios construidos por el LLM.

**P2: persistencia/autonomía.** Cola durable de tareas, reinicio supervisado, checkpoints, reintentos idempotentes, permisos por recurso, logs y botón de parada global. Un asistente "autónomo" que no recuerde lo que estaba haciendo al reiniciar no cumple el objetivo.

**P2: experiencia por voz y control remoto.** Voz (wake personalizado GAIA, Whisper, Piper), bandeja/atajos y cliente móvil para ordenar al Core de forma autenticada. No confundir una interfaz visual con capacidades operativas.

**Seguridad previa a LAN:** proteger el SSE `/api/visualizer/events`, que en la revisión anterior respondió sin autorización; validar identidad y permisos de cualquier cliente remoto.

## Límites conocidos

- La plataforma anfitriona de esta auditoría es Linux; no se realizó ejecución real de acciones Windows ni de Ollama.
- No se garantizan tareas autónomas complejas, autorreparación de ComfyUI ni administración desatendida a partir de las funciones declaradas en la versión actual.
- El ZIP original y el repositorio remoto no fueron modificados; el paquete `GAIA-AI-control-parche-2026-11-01.zip` contiene la copia con reparación mínima y tests.
