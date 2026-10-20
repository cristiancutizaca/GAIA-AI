HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.6.2 — Requisitos y criterios de aceptación

## Alcance

GAIA-AI v0.6.2 extiende v0.6.1 sin convertir al LLM en autoridad de ejecución. El Core sigue siendo FastAPI con RBAC fail-closed, SQLite schema 6, memoria continua, políticas de permisos y un límite LAN opt-in. Android sigue siendo companion: solicita, muestra preview, aprueba o rechaza y conserva el token de dispositivo; el PC Action Host es el único ejecutor local.

## Criterios de aceptación

| Criterio | Implementación | Evidencia | Estado |
|---|---|---|---|
| Separación de propietario y host | `requesting_device` y `target_host` independientes en pending/claim/completion | `remote_action_e2e_v062_test.py`, `remote_action_host_test.py` | PASS |
| Autoaprobación | La policy devuelve `confirmation_required=false` solo cuando la decisión efectiva es auto-aprobada | `action_request_semantics_test.py`, `permission_api_test.py` | PASS |
| Classifier dinámico | Catálogo derivado de `CapabilityRegistry`; capabilities inventadas se rechazan | `intent_classifier.py`, `dynamic_classifier_test.py` | PASS |
| Capabilities PC | Registry code-owned con 56 entradas implementadas y validación estricta | `capability_registry_test.py` | PASS |
| Displays Windows | Enumeración normalizada y movimiento por `SetWindowPos`, incluyendo coordenadas negativas | `display_capability_test.py` | PASS estático |
| App discovery | `discovered:<hash>` canónico, discovery read-only y trust persistente | `app_discovery_test.py` | PASS estático |
| Trusted folders | Defaults personales, grant/revoke, separación read/write y rechazo de raíz/home | `trusted_folders.py`, `security_regression_test.py` | PASS estático |
| Pairing QR | `gaia://pair?id=...&code=...&url=...`, TTL, one-shot y URL encoding | `lan_api_test.py`, `lan_protocol_test.py` | PASS |
| Android onboarding | Secure storage, parser URI, fallback de pegar URI y version `0.6.2+1` | `android_onboarding_contract_test.py` | PASS estático |
| Recuperación de token | Rotación atómica, revocación del token anterior y retorno a PairingScreen en 401 | `token_security_v062_test.py`, contrato Android | PASS estático/API |
| Observabilidad | `GET /api/diagnostics/performance` expone métricas LLM no secretas | `token_security_v062_test.py` | PASS |
| Shutdown del host | `RemoteActionHost.close()` activa stop event, cierra cliente propio e es idempotente | `remote_action_host_loop_test.py` | PASS |
| Seguridad de ejecución | Sin `shell=True`, `os.system`, `eval` ni `exec` en fuentes Python | grep de seguridad y `process_safety_test.py` | PASS |
| Empaquetado | Allowlist, higiene, estructura, checksum y documentación requerida | `release_package_test.py`, `tools/build_release.py` | PASS |
| Flutter/APK real | SDK, `flutter analyze`, build APK y prueba física | No disponible en sandbox | PENDING |

## Contratos de seguridad

El token master nunca se almacena en Android. Los tokens de dispositivo se muestran una sola vez, se almacenan como digest SHA-256 en Core y se guardan en `flutter_secure_storage` en el companion. La rotación invalida todos los tokens activos del dispositivo antes de insertar el nuevo token. Las listas administrativas exponen `token_id`, estado y timestamps, pero no `token` ni `token_hash`.

> La ausencia de Flutter no es un FAIL de código Android; se reporta como **PENDING** y debe comprobarse en una máquina con Flutter/Android SDK antes de distribuir un APK.

## Configuración mínima para LAN

`GAIA_LAN_ENABLED=false` sigue siendo el default. Para pairing real se debe activar explícitamente LAN, elegir una URL alcanzable desde Android mediante `GAIA_PAIRING_SERVER_URL` y usar una red confiable o TLS externo. El URI QR contiene solo el identificador de sesión, el código temporal y la URL; no contiene el token permanente.

## Release

La release se construye con `python3 tools/build_release.py --output-dir /home/ubuntu`. El resultado esperado es `GAIA-AI-v0.6.2-final.zip` y su `.sha256`. La extracción del ZIP debe volver a pasar `tests/release_package_test.py` y el informe final debe conservar la distinción entre PASS automatizado, PASS estático y PENDING físico.
