HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.6.0 — requisitos y alcance

## Objetivo

GAIA-AI v0.6.0 extiende el Core local de v0.5.4.3 hacia una arquitectura multi-dispositivo opt-in. El objetivo es conservar el routing factual, el Action Host separado y la memoria SQLite, mientras PC y Android comparten sesiones, permisos y continuidad bajo autenticación explícita.

## Requisitos funcionales

| Área | Requisito | Estado de implementación |
|---|---|---|
| Conversación | El chat, memoria y voz continúan disponibles aunque las acciones estén detenidas. | Implementado y probado |
| Routing | Las solicitudes externas se distinguen de preguntas de capacidad e información. | Heredado y probado |
| Action Host | La ejecución local ocurre solo mediante acciones allowlisted del PC. | Implementado y probado |
| Resultado | `VerifiedActionResult` es la autoridad factual posterior a la ejecución. | Implementado y probado |
| Capabilities | Registry code-owned con categorías, riesgo, OS, scopes y estado `implemented`. | Implementado y probado |
| Permisos | Permission Memory persiste decisión, scope, dispositivo, riesgo y versión; un aumento de riesgo vuelve a preguntar. | Implementado y probado |
| Kill switch | Master puede detener nuevas acciones y cancelar pending actions sin apagar chat. | Implementado y probado |
| LAN | LAN permanece desactivada por defecto; pairing y rate limiting son opt-in. | Implementado con pruebas de protocolo |
| Pairing | El código es de un solo uso, tiene TTL y límite de intentos; no se almacena en claro. | Implementado y probado |
| Android | Android solicita y aprueba acciones remotas; no ejecuta comandos ni usa el secreto master. | Implementado en el prototipo |
| Continuidad | `session_id` se conserva de forma persistente en Android y se reutiliza en Core. | Implementado en el prototipo |

## Requisitos de seguridad

No se permite `shell=True`, `os.system`, `eval`, `exec` ni ejecución de strings provenientes del LLM. El Core no recibe ejecutores, comandos, rutas arbitrarias o flags desde el modelo. El Action Host solo acepta el contrato estructurado y lo revalida localmente. Android no es un ejecutor local. Los tokens de dispositivo se guardan en almacenamiento seguro en Android y el Core conserva únicamente hashes de token.

El modo `CHAT_ONLY`, `GAIA_ACTIONS_ENABLED=false` y el kill switch persistente bloquean la creación de nuevas acciones. Un claim remoto requiere aprobación explícita del dispositivo propietario. El completado remoto exige ownership, sesión coincidente y capability `action_host`; el resultado se registra en `action_history` y en la auditoría encadenada del host.

## Fuera de alcance

La versión no promete automatización general de escritorio, control por coordenadas de ratón, shell libre, ejecución autónoma de scripts, acceso cloud implícito, TLS integrado, descubrimiento de aplicaciones como permiso, ni certificación de pruebas físicas de Windows, Android, LAN real, micrófono, GPU u Ollama. Las capabilities no implementadas aparecen como metadata honesta y fallan de forma controlada.

## Gates de aceptación

El release no puede declararse PASS si falla alguno de estos gates: compilación Python, tests heredados, `capability_registry_test.py`, `permission_memory_test.py`, `permission_api_test.py`, `kill_switch_test.py`, `action_host_test.py`, `lan_protocol_test.py`, `compileall`, `release_package_test.py`, extracción limpia del ZIP, Doctor read-only y grep de patrones inseguros. La validación Flutter queda marcada como pendiente si el entorno no dispone del SDK.
