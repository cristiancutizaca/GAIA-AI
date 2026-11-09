# Changelog

## En revisión · Estabilización de GAIA 2.0 RC3

- Corrige la incompatibilidad de PyAV 19 con faster-whisper 1.2.1 y evita descargas de Whisper al iniciar una grabación de forma predeterminada.
- Separa respuesta y síntesis en el escritorio. Reutiliza una voz Piper y reproduce frases en orden con cancelación local.
- Respeta el micrófono seleccionado, descarta audio pendiente al desactivarlo y hace visibles los conflictos de atajos.
- Valida la capacidad visual antes de capturar y distingue el estado de los modelos de Ollama instalados y cargados.
- Mejora la supervisión del Core, la limpieza de estado SSE, el diagnóstico de memoria y OpenCode, y el respaldo de `.env` durante una reparación autorizada.

La evidencia y el estado de cada problema están en [GAIA_BUG_FIX_REPORT.md](GAIA_BUG_FIX_REPORT.md).


## 2.0-WINDOWS-COMPLETE-RC3

- Browser Use isolated into `.venv-browser` to prevent exact runtime pins from mutating Core/Voice dependencies.
- Browser execution now crosses a JSON-lines sidecar boundary while GAIA Core retains authority, URL validation and content-trust policy.
- `requirements-computer.txt` no longer overrides Pillow owned by the main PC stack.
- Chromium/Playwright installation runs with the browser sidecar interpreter.

- Rebuilt clean-install profiles around a canonical dependency manifest; `full` now includes Desktop/Voice/Browser/Memory/Coding and `full-computer` adds Windows UIA/PyAutoGUI.
- Repaired resident Desktop: real Win32 hotkeys, PTT audio finalization, SSE→Qt signal bridge, non-blocking Quick Command, real response playback, supervised Core restart and Windows named mutex.
- Modernized local voice to faster-whisper + Piper, streaming Silero endpointing/barge-in, multi-turn wake session and truthful custom Gaia wake-model handling.
- Removed fake Pipecat placeholder stages; adapter now reports configuration required unless real processors/transports are supplied.
- Added deterministic Windows UI Automation before PyAutoGUI coordinate fallback; UI-TARS/Agent-S remain optional rather than falsely integrated.
- Removed Browser Use Linux-only Chromium hardcode.
- Hardened Mem0 ownership mutation checks and preserved Graphiti isolation.
- Repaired normal pytest collection/execution and added runtime behavioral closure tests.
- Replaced active RC6 physical validator with GAIA 2.0 operator-confirmed validation.

## v1.0-RC6 + DeepSeek-Harness

Integra DeepSeek-Harness `0.1.5-rc.1` como motor de razonamiento sobre Ollama local. Conserva memoria, voz, automatizaciones, clientes y permisos de GAIA. El perfil seguro desactiva el shell directo del Harness y deja toda acción del equipo bajo el flujo de autorización existente de GAIA. Incluye SDK Python oficial integrado, instaladores para Windows/Linux, diagnóstico y retorno inmediato al backend Ollama anterior.

## v1.0-RC6

RC6 corrige la inconsistencia reproducida entre el proyecto RC5 y su ZIP documental, adopta un builder documental derivado del archive de proyecto, añade paridad byte-a-byte sobre archivos Markdown/TXT, amplía la clasificación de documentos históricos, actualiza la identidad activa a RC6 y prepara comparaciones de rendimiento reproducibles. El trabajo funcional de RC5 se conserva; RC5 permanece clasificada como `RC5 NOT FROZEN / ARTIFACT CONSISTENCY FAILURE` y no se modifica retroactivamente.

Las optimizaciones solo se aceptan después de perfilado, cambio mínimo, tests y benchmark comparable. Los controles físicos continúan PENDING hasta validación humana en Windows.

## Historial

Los cambios RC1–RC5 permanecen en los documentos históricos y en la matriz de migración. No deben confundirse con comandos operativos vigentes.

## DeepSeek Harness hardening (local patch)
- Harness usa el SDK Python público `deepseek-harness-sdk==0.1.5rc1` y su runtime emparejado; se retiró la copia vendorizada y la ruta privada `_launch_args`.
- Laptop default cambiado a `qwen3.5:4b`, contexto global 4096 y concurrencia 1.
- Harness se ejecuta en un workspace dedicado y conserva el patch que desactiva shells del perfil `sdk-minimal`.
- Si Harness falla, GAIA puede degradar automáticamente a Ollama directo mediante `GAIA_DSH_FALLBACK_TO_OLLAMA=true`.
- Se añadió smoke E2E físico en `tools/test_deepseek_harness_e2e.py` y pruebas de integración/fallback.
