HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# Requisitos de GAIA-AI v0.5.2

Fuente original: `/home/ubuntu/upload/pasted_content_6.txt`, instrucciones del usuario, 1861 líneas. La release debe partir de `GAIA-AI-v0.5.1-final.zip`, llamarse `GAIA-AI v0.5.2` y cerrar inconsistencias concretas antes de Android/LAN/Action Host v0.6. No se permite reescritura, migración interna LUMEN→GAIA, control remoto Android→PC, TLS server, browser agent, screen automation, mouse autonomy, filesystem modification, admin privileges, niveles 3–4, multi-agent o agentes recursivos.

## Contrato de acciones

Core, desktop_api, GUI y terminal deben usar un único contrato. Para una acción: `kind=action`, `confirmation_required` top-level, `action` individual, `preview` string, action_id y session_id. Para plan: `kind=plan`, `confirmation_required` top-level, `plan={plan_id, actions}`, `preview` completo y los mismos identificadores. No deben existir campos ambiguos nested/top-level. GUI debe disparar confirmación real para single y plan; AUTO_SAFE permite nivel 1 sin diálogo; BLOCKED no ejecuta y muestra aviso.

## Coordinación y terminal

GUI y terminal deben reutilizar un coordinador común, no duplicar parsers ni crear otro Action Engine. El coordinador limita 3 acciones, revalida cada step, ejecuta secuencialmente, detiene ante fallo, respeta cancelación, plan_id, step, duration y salida limitada. Una confirmación negativa ejecuta cero pasos. Un fallo en step 2 no inicia step 3. Un plan cancelado después de step 1 no revierte step 1. El resultado post-acción puede pasar al LLM solo para verbalizar; esa respuesta no se reclasifica ni genera otra acción/plan.

## RBAC y voz

`/chat/voice` requiere capabilities `voice` y `chat`; voice-only y chat-only reciben 403, voice+chat recibe 200 con STT/TTS mock. La voz no puede saltarse RBAC llamando una route function con Depends desde otra route. Debe existir un servicio interno de chat separado de las funciones FastAPI. STT se trata como input de usuario bajo los mismos controles de inyección.

## Ownership y cancelación

Cada SSE request guarda metadata temporal: request_id, principal_type, device_id, token_id, session_id y created_at, sin token claro. Un device solo cancela sus propios request_id; otro device recibe 403; master puede cancelar; inexistente o expirado recibe 404. Metadata se limpia tras done/cancelled/error/timeout y tiene TTL defensivo. `actions/complete` requiere actions_execute + action_host y debe comprobar acción/plan pendiente, principal, sesión, device y plan_id correctos.

## Semántica de permisos

Capabilities son la fuente real de autorización. `permission_level` es metadata/grouping/future use y no concede acceso implícito; un valor heredado 999 con `capabilities=[chat]` solo permite chat. Master se determina por `LUMEN_SECRET`, nunca por permission_level. Brain Restore permanece master-only.

## Documentación obligatoria

El paquete debe incluir README.md, CHANGELOG.md, AUDIT.md, TEST_REPORT.md, KNOWN_LIMITATIONS.md, MEMORY_ARCHITECTURE.md, SECURITY_MODEL.md, DEVICES.md, MIGRATION_LUMEN_GAIA.md, MODIFIED_FILES.md, ROLLBACK.md y FINAL_VALIDATION.txt. Los documentos deben separar implemented, automated tested, mock tested, static reviewed, physical pending y experimental, y coincidir con el código.

## Pruebas obligatorias

Además de todas las regresiones v0.5.1, se requieren tests de contrato GUI, terminal plan, voice permissions, request ownership y permission_level; HTTP matrix master/chat-only/voice-only/voice+chat; cross-device cancel; plan cancel/failure/post-action; RBAC de todas las rutas operativas; Brain Restore master-only; scheduler; seguridad grep para shell=True, os.system(, eval( y exec(; higiene del ZIP y checksum final `GAIA-AI-v0.5.2-final.zip` + `GAIA-AI-v0.5.2-final.sha256`.

## Límites

Mantener `qwen3.5:9b`, schema 5, `GAIA_LAN_ENABLED=false`, Android solo ajustes mínimos si cambia API, Flutter static review only si no existe SDK y sin afirmar APK. No declarar hardware probado mediante mock.
