# KNOWN LIMITATIONS — GAIA-AI v0.5.3

## Estado de validación

| Clasificación | Estado |
|---|---|
| Implementado | Core FastAPI, SQLite schema 5, RBAC, tokens hashados, contrato action/plan, ActionCoordinator, GUI/terminal PC, Doctor, startup y build reproducible |
| Probado automáticamente | Contratos HTTP/SSE, 401/403, ownership, cancelación, planes, post-action, migración, seguridad grep y regresiones |
| Brain Backup | Payload allowlisted, snapshot autónomo, manifest exacto, WAL/SHM excluidos, lock y restore round-trip repetido |
| Release | `.env.example`, `.gitignore`, allowlist, ZIP comparison y package hygiene implementados |
| Mock probado | LLM classifier, STT, TTS, audio y ciertos flujos de voz |
| Revisión estática | Flutter, `flutter_secure_storage`, `pubspec.yaml`, scripts Windows |
| Python | Python 3.11 es el objetivo recomendado; Python 3.12 es el entorno validado; Python 3.13 no fue probado |
| Pendiente físico | Ollama/Qwen real, GPU, micrófono, altavoces, Whisper, Edge TTS, VS Code, navegador, ventanas activas, proyectos trusted, LAN y Android |

## Límite de equivalencia del artefacto

La validación de release tiene dos superficies. El árbol de trabajo se prueba durante el desarrollo, pero la afirmación fuerte solo se hace después de construir `GAIA-AI-v0.5.3-final.zip`, extraerlo en una carpeta vacía y ejecutar desde allí la suite, Doctor, fresh install y pruebas de Brain Backup. Los bytecode, DB y logs creados durante esa ejecución no forman parte del ZIP original.

La auditoría baseline mostró que v0.5.2 tenía `.env.example` y `.gitignore` ausentes en el ZIP final. v0.5.3 exige ambos durante el build y el test de estructura. La auditoría independiente disponible también reportó un riesgo WAL/SHM; la reproducción específica de `v04_test.py` en esta sandbox pasó, por lo que no se declara una reproducción de ese fallo histórico mediante ese comando.

## Límites deliberados

GAIA no ejecuta shell arbitrario, no interpreta `eval` o `exec`, no concede privilegios por `permission_level`, no ofrece acceso remoto Android→PC, browser agent, screen automation, mouse autonomy, niveles de riesgo 3–4, TLS server, multi-agent ni agentes recursivos. `GAIA_LAN_ENABLED` permanece `false` por defecto y una LAN real requiere TLS externo o túnel seguro.

El backend `mock` valida contratos, no capacidad de razonamiento ni rendimiento de Qwen. La ausencia de Flutter/Dart impide afirmar APK, instalación Android o comportamiento en un teléfono. La ausencia de hardware de audio impide afirmar micrófono, Whisper, TTS o reproducción.

El scheduler de Brain Backup y Doctor están implementados, pero su comportamiento con apagados abruptos, volúmenes removibles, permisos Windows, servicios reales y recuperación operativa debe probarse en el entorno objetivo. El coordinador no revierte pasos ya ejecutados cuando un paso posterior falla; detiene el plan y registra el resultado.
