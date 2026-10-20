HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# V054 REQUIREMENTS — GAIA-AI v0.5.4

## Objetivo

v0.5.4 es un hotfix conservador sobre v0.5.3. No se reescribe GAIA, no se desarrolla v0.6 y no se cambia SQLite schema 5, el contrato action/plan, RBAC, ownership, ActionCoordinator, Brain Backup portable, namespace `LUMEN_*` ni Android/LAN.

## Fuente de verdad física

El `lumen-pc/desktop_api.py` adjunto por el usuario se integra primero y conserva `ACTION_COMPLETION_TIMEOUT` de al menos 60 segundos para `confirm_action()` y `cancel_action()`. El archivo físico no se sustituye por una implementación conceptual.

## Requisitos implementados

| Requisito | Implementación | Evidencia |
|---|---|---|
| Timeout sin race | Core post-action configurable; cliente > post defensivo | `config.py`, `desktop_api.py`, `timeout_config_test.py` |
| Action grounding | Conversación no declara efectos; resultado estructurado manda | `routes/api.py`, `action_grounding_test.py` |
| Apps seguras | Registry static allowlisted para Calculator, Notepad, Spotify y VS Code new window | `safe_apps.py`, `safe_apps_test.py` |
| Sin ejecutable del LLM | Parser y classifier aceptan nombres/args cerrados | `action_intent.py`, `intent_classifier.py` |
| Output vacío | Fallback visible para reasoning-only, whitespace y stream vacío | `llm.py`, `routes/api.py`, `empty_llm_output_test.py` |
| Concurrencia | Semaphore default 1, cancelable mientras espera; health/diagnostics/cancel libres | `llm.py`, `llm_concurrency_test.py` |
| GUI busy | Bloqueo de doble envío y reset ante éxito/cancel/error | `gui.py`, `gui_busy_test.py` |
| Proyectos | Dedup por nombre canónico, aliases solo resuelven | `project_registry.py`, `project_dedup_test.py` |
| Personalidad | Humor contextual y sarcasmo moderado; jamás autoridad | `personality.py`, `config.py` |
| Evidencia | Clasificación PHYSICAL/AUTOMATED/MOCK/STATIC/PENDING | `PHYSICAL_VALIDATION_WINDOWS.md` |

## Requisitos de seguridad preservados

No se permite `shell=True`, `os.system`, `eval`, `exec`, shell arbitrario, PowerShell/cmd del LLM, ejecutables suministrados por texto del modelo, permisos derivados de `permission_level`, acciones de riesgo 3–4, browser agent, screen automation, mouse autonomy, Android→PC remoto, TLS server, multi-agent ni agentes recursivos.

## Validación y límites

La suite automatizada usa backend mock, SQLite temporal y mocks de lanzadores. La evidencia Windows física comunicada por el usuario incluye Python 3.11, Ollama/Qwen real, RTX 3050 Laptop, GUI, streaming, VS Code, Git, FFmpeg y detección de audio. Debe separarse de lo ejecutado en sandbox y repetirse por release para afirmar PASS físico. No se afirma APK, Whisper/TTS completo, Brain Restore físico, LAN/TLS ni validación de GPU en el sandbox.
