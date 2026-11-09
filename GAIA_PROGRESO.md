# GAIA 2.0 RC3 · progreso de la transformación

Base auditada `main@83d09069df3010cb6592d971ce61ffbe2a001eb7`. Rama de trabajo `dev/gaia-memory-reflex`. La identidad canónica es **GAIA-AI 2.0.0**, release `2.0-WINDOWS-COMPLETE-RC3`, protocolo compatible `1.0-RC6` y esquema SQLite 9. Los informes que dicen RC1 o RC2 describen entregas anteriores.

## Fase 1 · Auditoría

Se inventariaron los archivos versionados, los puntos de entrada de `lumen-core/`, `lumen-pc/`, `tools/` y las suites actuales e históricas de `tests/`. Se contrastaron el README, los informes de reparación e instalación, la guía de aislamiento RC3, las guías de escritorio y voz, y los documentos de arquitectura de memoria con el código que ejecuta cada flujo.

| Área | Estado en la base auditada | Pendiente para la transformación |
|---|---|---|
| Escritorio y supervisión | Lanzador con instancia única, Core con health check, bandeja, avatar PySide6, Centro de Control y hotkey global | Validar sesiones largas, gestión de varios monitores, animaciones y recuperación física |
| Memoria | SQLite legacy y avanzado en la base configurada. Los recuerdos explícitos del runtime se guardaban aparte y el comando se atendía solo en chat de texto | Fases 2 y 3 cubren el flujo explícito. Falta evaluar deduplicación semántica, sincronización y políticas históricas |
| Control de Windows | ActionHost, validación de capabilities, preflight, auditoría, Safe Mode, Kill Switch y aprobación visible en el residente | Validar efectos reales y tiempos con aplicaciones de Windows |
| Planificación | Operador local con plantillas de varios pasos, checkpoints, cancelación y recuperación que evita repetir efectos sin revisión. Existe un planner separado de capacidades | Ampliar flujos de proyectos y dependencias, con verificadores y aprobación |
| Voz | PTT y captura local, faster-whisper, Piper por proceso, SAPI de respaldo. SSE entrega el texto tras comprobarlo por completo. Pipecat sigue siendo una integración opcional sin transporte activo | Captura y STT incrementales, TTS reutilizable, selección de micrófono y voz, escucha/interrupción física y eco |
| Wake word | Herramientas y configuración de entrenamiento. En el árbol auditado solo están los archivos de preparación | Entrenar/proveer un `gaia.onnx` genuino y medir falsos positivos/negativos. Usar Ctrl+Espacio mientras tanto |
| Visión | Captura autorizada por monitor y análisis en Ollama loopback. El flujo de observación está separado del flujo de acciones | Confirmar captura y tiempo de inferencia en los monitores de la PC |
| Hardware y modelos | Probes de hardware/GPU, perfiles de recursos, enrutador de modelos y diagnóstico de Ollama | Telemetría AMD validada, estimaciones, descargas autorizadas, políticas de carga/descarga y alertas |
| OpenCode | No había integración de ejecución en el árbol auditado. Doctor ahora detecta CLI y puede pedirle que analice la configuración | Reproducir el error del usuario y diseñar el contrato de proyectos, permisos, cambios, pruebas y commits |
| ComfyUI y multimedia | Hay diagnóstico local de ComfyUI/ROCm y herramientas auxiliares en el repositorio | Detectar el servicio existente en Windows, gestionar jobs/workflows y probar proveedores de vídeo y música. La instalación `C:\IA\ComfyUI_ROCM10` requiere prueba en la PC |
| Android, LAN y SSE | Companion, autenticación, scopes por dispositivo, revocación y SSE autenticado. LAN es opt-in y el Core no trae TLS propio | Prueba en POCO X7 Pro y transporte cifrado antes de habilitar control remoto |
| Instalador | Setup PowerShell con perfiles y entornos separados para Core/Desktop, Browser, Memory y Coding | Construir y validar `GAIA-Setup.exe` con instalación, reparación, actualización y desinstalación |

## Fase 2 · Memoria

El fallo reproducible estaba en la ruta de entrada, almacenamiento y búsqueda. El chat de escritorio reconocía el guardado, pero voz y SSE saltaban esa ruta. El patrón de consulta no reconocía formas como «recuerdas», y la búsqueda del almacén explícito traía todas las filas del propietario. El archivo separado no entraba en el snapshot normal de `GAIA_MEMORY_DB`. Los dos ajustes de extracción automática desactivados por defecto son un comportamiento independiente y siguen siendo opt-in.

- `lumen-core/memory_intent.py`, `platform_runtime.py`, `main.py` y `routes/api.py` conectan guardado y recuperación explícitos a texto, voz y SSE. Se reutilizan Authority y las capabilities de memoria. Se omite el duplicado del comando explícito en la transcripción y se rechazan patrones reconocibles de credenciales. El audio de lectura usa síntesis local, caduca y requiere la identidad que lo generó.
- `lumen-core/gaia_platform/memory_v2.py` usa la base SQLite configurada, con migración de una sola vez del almacén legado. Conserva los IDs y el archivo fuente, indexa por propietario/dispositivo/proyecto y usa FTS5 con fallback textual cuando falta. El backup SQLite y Brain Backup incluyen la tabla. El API permite leer, editar, exportar y borrar el recuerdo.
- `lumen-core/memory.py` mantiene la consolidación más allá de la primera ventana de mensajes, conserva hasta 32 decisiones en el resumen estructurado y acota el contexto de los dispositivos. La memoria legacy sigue disponible bajo sus APIs y flujos existentes. `fact_extractor.py` y `memory_privacy.py` filtran candidatos automáticos con patrones de credenciales.
- `lumen-pc/gaia_memory_panel.py`, `gaia_panel.py`, `desktop_shell.py` y `desktop_api.py` incorporan la pantalla **Recuerdos** con búsqueda por proyecto, edición, borrado confirmado y exportación JSON.
- El borrado afecta la base activa. Copias anteriores, transcripciones de versiones previas y almacenes opcionales con retención propia requieren su gestión por separado. La deduplicación semántica y los controles de privacidad granular de todo el histórico quedan pendientes.

Ejemplos desde el Centro de Control o PTT.

```text
Recuerda que prefiero las respuestas breves
¿Recuerdas qué respuestas prefiero?
Recuerda proyecto KIROHA: Nébula usa índice local
¿Qué recuerdas de proyecto KIROHA sobre Nébula?
```

## Fase 3 · GAIA Reflex

`lumen-core/reflex_engine.py` reconoce expresiones completas y propone acciones registradas. `routes/api.py`, `action_intent.py` y `resource_scope.py` asignan permisos y previews. `lumen-pc/action_engine.py`, `capabilities.py`, `platform_capabilities.py` y `media_session.py` ejecutan por ActionHost. El Kill Switch corta nuevas propuestas y se exige confirmación antes de ejecutar un contrato Reflex.

| Orden | Operación |
|---|---|
| «Abre el Bloc de notas» | Lanzador permitido existente |
| «Baja el volumen» | Lee el volumen, resta 10 puntos y verifica el nivel resultante |
| «Pausa la música» | Solicita pausa mediante SMTC y verifica el estado. Una sesión ya pausada sigue pausada |
| «Muestra el escritorio» | Solicita minimizar ventanas con Windows Shell y verifica el escritorio visible |
| «Cierra esta ventana» | Exige una ventana identificada, revalida su identidad y comprueba el cierre. Un diálogo pendiente se comunica como cierre no verificado |
| «Abre KIROHA» | Abre el proyecto confiado registrado como `kiroha` en VS Code |
| «¿Cuánta RAM estoy usando?» | Consulta el uso real de RAM mediante el proveedor del host |

Se eligieron reglas locales sin dependencias nuevas. La búsqueda de «TypeSafe» no confirmó un clasificador local y mantenido que corresponda a ese nombre y a este caso. El enrutamiento complejo existente sigue disponible.

## Fase 4 · Primera medición

`lumen-core/gaia_latency.py` y `routes/api.py` exponen p50, p95 y p99 en `GET /api/diagnostics/performance`, por etapa y con 256 muestras como máximo por etapa. Se registra la clasificación, la recuperación, el primer token interno, el texto comprobado, la transcripción final y la disponibilidad del archivo de síntesis. ActionHost mantiene el tiempo por acción. El cliente de escritorio evita pedir telemetría a Ollama para Reflex y comandos explícitos de memoria. Voz solo toma el snapshot local necesario para resolver referencias de escritorio.

Medición HTTP loopback en Linux x86_64, Python 3.12.14, AMD EPYC 9V74 (9 CPU visibles). Se usó un Core Uvicorn, SQLite temporal y un perfil de prueba sin modelo real. Las rutas medidas no necesitan un LLM. Se reutilizó la conexión HTTP y se tomaron 35 muestras por operación.

| Medición | p50 ms | p95 ms | p99 ms |
|---|---:|---:|---:|
| Recuperación explícita por HTTP | 3.257 | 5.849 | 14.198 |
| Propuesta de acción Reflex por HTTP | 9.999 | 13.989 | 18.777 |
| Recuperación explícita dentro del Core | 0.718 | 1.713 | 2.045 |
| Clasificación local dentro del Core | 0.008 | 0.012 | 0.013 |

Tiempo de captura/detección, primer audio audible, interrupción, ejecución de acciones GUI, GPU y p99 en Windows quedan sin medir. La propuesta Reflex HTTP solo mide la respuesta del Core antes de la aprobación y de la ejecución en el host.

## Evidencia y continuación

- Base previa a los cambios. `python -m pytest -q` aprobó 78 pruebas.
- Rama de trabajo. `python -m pytest -q` aprobó 91 pruebas, incluidas las regresiones de `tests/test_gaia_memory_reflex.py`. El test de RAM ejecuta el proveedor real de Linux. STT, volumen y audio privado usan fixtures o dobles donde se necesita hardware.
- Regresiones históricas ejecutadas aparte. Release v20, autoridad v14, Core E2E v13, Kill Switch, matriz y endurecimiento de memoria v091, permisos de voz, contrato de escritorio v072 y Brain Backup WAL pasaron.
- Cuatro arranques de procesos Uvicorn con la misma base comprobaron guardar, volver a leer, editar y verificar el borrado. Qt offscreen comprobó el acceso al panel, la recepción desde el hilo y la selección de un recuerdo.
- `tools/gaia_doctor_v2.py --opencode-config` detectó que OpenCode no estaba disponible en este entorno. En Windows, ejecutarlo desde la carpeta donde aparece el error. El diagnóstico usa `--pure debug config` si la CLI admite `--pure`, descarta la configuración efectiva y comunica el código de salida. La causa de la falla en la PC queda pendiente.
- Siguiente fase. Ejecutar la lista física de Windows, medir STT y TTS con micrófono y altavoz, y optimizar Piper y la entrega de voz con resultados comparables. Luego integrar OpenCode y ComfyUI con autorización por acción.

### Evaluación de voz para la próxima fase

- Piper conserva `es_MX-claude-high` y el fallback Windows SAPI. El API de Piper permite iterar fragmentos de audio y controlar velocidad y volumen. Reutilización del modelo, selección de voces y reproducción incremental quedan por validar. [API oficial de Piper](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md)
- Qwen3-TTS VoiceDesign 1.7B admite español e instrucciones de estilo. La función de inferencia publicada devuelve audio completo y su opción de simulación de entrada no da streaming real. La aceleración de PyTorch en Windows sobre RX 9060 XT tiene soporte documentado por AMD para determinadas versiones. Falta comprobar este modelo concreto, su consumo y la latencia con CPU y AMD. [Qwen3-TTS oficial](https://github.com/QwenLM/Qwen3-TTS) · [Código de VoiceDesign](https://github.com/QwenLM/Qwen3-TTS/blob/main/qwen_tts/inference/qwen3_tts_model.py) · [AMD para Windows](https://www.amd.com/en/resources/support-articles/release-notes/RN-AMDGPU-WINDOWS-PYTORCH-7-2.html)
- Kokoro 82M ofrece `ef_dora` como voz femenina en español. Queda por comparar pronunciación, acento y latencia reales con la voz de Piper y el perfil «GAIA Friendly Playful Voice». [Voces del modelo Kokoro](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)
