HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.7.2 — Requisitos y criterios de aceptación

## Alcance

GAIA-AI v0.7.2 es una release de **integration hardening** sobre v0.7.1. Su objetivo es cerrar las brechas entre contratos unitarios y rutas de producción sin ampliar el perímetro inseguro de ejecución. La release debe conservar los gates heredados de v0.7.1 y añadir evidencia de transporte real, preflight read-only, recursos efímeros de captura y recuperación autenticada.

> **Regla de release:** ningún backend físico ausente se convierte en PASS por simulación. Windows UIA/SMTC, Flutter y hardware real se reportan como PENDING cuando el entorno no permite verificarlos.

## Criterios de aceptación

| ID | Criterio | Implementación | Evidencia | Estado esperado |
|---|---|---|---|---|
| V072-01 | El Core, PC, Android, protocolo LAN y builder deben declarar 0.7.2 de manera consistente. | `config.py`, `lan_protocol.py`, `action_host.py`, `pubspec.yaml`, Gradle, Doctor y `build_release.py`. | Tests de smoke, onboarding, LAN, ActionHost, token y startup; auditoría textual de referencias. | PASS |
| V072-02 | Texto, SSE y voz de DesktopAPI deben transportar el mismo snapshot canónico y envelope. | `DesktopContextService`, `request_envelope.py`, `DesktopAPI`, rutas Core y test production-path. | `desktop_context_production_path_v072_test.py`. | PASS |
| V072-03 | Terminal y Android deben usar el mismo esquema de envelope sin afirmar foreground de `pc-main`. | `client.py`, `lumen_service.dart` y `request_envelope.py`. | Contratos de transporte y onboarding Android. | PASS |
| V072-04 | Debe existir un preflight read-only que use el registry real y no invoque handlers. | `lumen-pc/preflight.py` y boundary de `ActionHost`. | `preflight_v072_test.py`. | PASS |
| V072-05 | El preflight debe bloquear acción desconocida, parámetros inválidos, UIA sin `expected_target`, target stale, app no trusted y riesgo dinámico excesivo. | Reutilización de `CapabilityRegistry`, `verify_window_identity`, `is_trusted_executable` y `resolve_control_risk`. | `preflight_v072_test.py`, `dynamic_uia_risk_v071_test.py`, `natural_routing_v071_test.py`. | PASS/PENDING físico según plataforma |
| V072-06 | Toda ejecución debe repetir la validación en el boundary inmediatamente antes del coordinator. | `ActionHost.execute()` y `RemoteActionHost.execute_item()`. | `preflight_v072_test.py`, ActionHost y remote-host regressions. | PASS |
| V072-07 | Las capturas deben ser efímeras y recuperables por `capture_id`, con TTL, manifest, SHA-256, ownership, path containment y limpieza. | `screen_capture.py`. | `capture_resource_v072_test.py`. | PASS |
| V072-08 | El retrieval de una captura debe requerir autenticación, respetar ownership de dispositivo y devolver `image/png` con `Cache-Control: no-store`. | `/api/captures/{capture_id}`, `DesktopAPI.download_capture`, `LumenService.downloadCapture`. | `capture_api_v072_test.py`. | PASS |
| V072-09 | El host remoto debe resolver su contexto local y no aceptar la identidad de foreground enviada por Android como autoridad. | `RemoteActionHost._attach_contextual_target()` y preflight remoto. | `preflight_v072_test.py`, remote-host tests. | PASS |
| V072-10 | El resultado de preflight o backend ausente nunca debe declararse como efecto verificado. | `PreflightResult`, `VerifiedActionResult`, flags de `ActionHost`. | `result_semantics_v071_test.py`, `preflight_v072_test.py`. | PASS |
| V072-11 | Android debe conservar pairing seguro, tokens en secure storage, `device_id`, push-to-talk y transporte de captura sin executor local. | Companion Flutter y Gradle scaffold oficial. | `android_onboarding_contract_test.py`, `android_scaffold_v071_test.py`. | PASS estático; build físico PENDING |
| V072-12 | El builder debe producir un ZIP allowlisted, sin runtime, bytecode, secretos ni ZIP anidado, preservando `gradlew` ejecutable. | `tools/build_release.py`. | `release_package_test.py`, `unzip -tq`, auditoría de permisos y checksum. | PASS |
| V072-13 | La suite completa debe pasar desde extracción limpia; solo los límites físicos permitidos pueden quedar PENDING. | Árbol final extraído. | `TEST_REPORT.md`, `FINAL_VALIDATION.txt` y log de clean validation. | PASS cuando sea 0 FAIL |

## Invariantes de seguridad

La implementación no usa `shell=True`, `eval`, `exec`, comandos shell arbitrarios, coordenadas crudas, automatización de ratón/teclado ni carga dinámica de plugins. El Action Host solo ejecuta acciones presentes en un registry code-owned. El Core no convierte un envelope recibido en autoridad de dispositivo, aplicación o ventana.

Las interacciones UIA requieren `expected_target` estructurado, identidad de ventana actual, aplicación trusted y fingerprint SHA-256 vigente. Los controles sensibles y campos de password no se exponen ni se escriben. El riesgo dinámico puede elevar una acción a DENIED antes del efecto. La captura no se incorpora a memoria durable: se guarda temporalmente, se sirve únicamente dentro del scope del dispositivo y se limpia por TTL o cierre del proceso.

Los grants persistentes conservan las reglas heredadas: `ALWAYS_ALLOW` y `ALWAYS_DENY` requieren un `resource_scope` no vacío, no wildcard y no unresolved. Las acciones remotas mantienen separación entre `requesting_device`, `target_host`, claim atómico, aprobación y completion verificado.

## Validación del entorno

El sandbox dispone de Python y Java. Flutter no está instalado. El intento de Gradle puede detenerse por ausencia de `local.properties`, Flutter SDK o Android SDK; ese resultado no autoriza declarar un APK PASS. La validación física de Windows UIA, SMTC, micrófono, TTS, displays, aplicaciones trusted y LAN real queda reservada al procedimiento de `PHYSICAL_VALIDATION_WINDOWS.md`.

## Gate de cierre

La release v0.7.2 solo se declara PASS si el builder, el checksum, la integridad del ZIP, la higiene del árbol, la compilación Python y todos los tests ejecutables desde una extracción limpia terminan sin FAIL. Las limitaciones físicas deben estar enumeradas explícitamente como PENDING y no deben ocultar errores de implementación.
