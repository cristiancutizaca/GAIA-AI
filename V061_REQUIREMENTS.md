HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.6.1 — Requisitos auditables

GAIA-AI v0.6.1 convierte los contratos de v0.6.0 en funciones operativas sin ampliar la autoridad del modelo. El Core clasifica y conserva la política; el PC Action Host ejecuta únicamente intents estructurados validados por el registro code-owned; Android actúa como companion y nunca ejecuta `ActionEngine`.

| Área | Contrato v0.6.1 | Evidencia implementada |
|---|---|---|
| Permisos | Defaults conservadores por riesgo y device; `ALLOW_ONCE`, `ALWAYS_ALLOW`, `DENY`, `ALWAYS_DENY`; scope visible; most-specific-wins. | `lumen-core/memory.py`, `routes/api.py`, `lumen-pc/gui.py`, tests de Permission Memory/API/GUI. |
| PC capabilities | Apps, ventanas, volumen, clipboard, archivos, procesos, displays, red, Git y power con parámetros validados. | `lumen-pc/capabilities.py`, `action_engine.py`, `platform_capabilities.py`. |
| Remote Host | Heartbeat, polling, pending aprobado, claim atómico, ejecución ActionHost, completion verificado. | `lumen-pc/remote_action_host.py`, `tools/run_remote_action_host.py`, `remote_action_host_test.py`, `remote_action_host_loop_test.py`. |
| Pairing | LAN opt-in; pairing de un solo uso; registro de device Android; token hashado, retornado una sola vez; negociación restringida. | `lan_protocol.py`, `routes/api.py`, `PairingScreen`, `lan_api_test.py`. |
| Android | Persistencia segura de token/device_id, aprobación remota scoped, estado del host y onboarding de primer arranque. | `lumen-mobile/lib/services/lumen_service.dart`, pantallas Android, contrato estático. |
| Voz | Push-to-talk; upload autenticado; Whisper Core; TTS opcional; archivos locales temporales eliminados; sin wake word continuo. | `ChatScreen`, `/api/chat/voice`, `voice_permissions_test.py`, contrato estático Android. |
| Rendimiento | AsyncClient lifecycle-managed, pool reutilizable, cola FIFO cancelable, métricas de queue/TTFT/total y perfiles `eco`, `balanced`, `performance`. | `llm.py`, `model_router.py`, `main.py`, `llm_queue_test.py`, `v0543_performance_test.py`. |
| Seguridad | Sin `shell=True`, `os.system`, `eval`, `exec`, PowerShell/CMD libres, ejecutables recibidos por red ni output LLM directo a subprocess. | Greps de seguridad, `security_regression_test.py`, allowlists y validadores estructurados. |

## Criterios no negociables

Una ejecución solo se considera válida cuando el resultado procede de `VerifiedActionResult`, la acción estaba aprobada por policy, el host autenticado la reclamó de forma atómica y el Core registró la completion sin invocar una segunda generación LLM. El kill switch bloquea acciones nuevas y cancela pendientes, pero no detiene el chat.

La validación física de Windows y la compilación APK dependen de disponer de un equipo Windows/Flutter. En el sandbox se reportan como **PENDING**, nunca como PASS ni como FAIL.
