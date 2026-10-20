# PC Remote Action Host

El PC Remote Action Host es un proceso autenticado que consulta al Core por acciones aprobadas para `pc-main`. No recibe comandos libres. El payload pendiente contiene un intent o plan ya validado por el Core; el host lo transforma a un contrato interno y lo entrega a `ActionHost`, que devuelve `VerifiedActionResult` con auditoría encadenada.

## Flujo operativo

1. El Core crea una acción pendiente después de clasificar el mensaje y resolver Permission Memory.
2. La acción no aparece en `/api/actions/pending` hasta que el principal propietario la aprueba explícitamente, salvo que la policy haya producido aprobación automática.
3. El host publica heartbeat autenticado y consulta pending con su token de dispositivo.
4. El host reclama la acción mediante `/api/actions/claim`; el Core impide doble claim o claim sin aprobación.
5. `ActionHost` ejecuta solo capabilities registradas, con parámetros validados y límites de riesgo.
6. El host publica `/api/actions/complete` con el resultado verificado, `execution_verified`, `host_version` y digest de auditoría.
7. El Core registra la acción y genera una respuesta factual sin segunda llamada LLM.

## Inicio en Windows

`start-gaia.bat` inicia Core, Remote Action Host y GUI en background cuando `GAIA_REMOTE_HOST_ENABLED=true`. El helper `tools/run_remote_action_host.py` usa `GAIA_REMOTE_HOST_TOKEN` si está configurado; de lo contrario, puede hacer bootstrap de un token de `pc-main` usando el secreto maestro local y lo guarda en `.gaia_remote_host.token`, archivo que nunca se incluye en el release.

La primera configuración recomendada consiste en crear un token de host en el PC confiable, proteger el archivo con permisos locales y revocarlo inmediatamente desde el endpoint administrativo si el equipo se pierde. El token se almacena hashado en SQLite y solo se muestra en claro durante su creación.

## Estado y recuperación

El heartbeat mantiene `online`, `busy`, `host_version` y `last_seen` en memoria persistente del Core. Si el heartbeat supera tres intervalos configurados, el host se presenta como offline. El proceso aplica backoff cuando Core todavía no responde y no mata procesos ajenos ni inicia una segunda instancia del Core.

El Remote Action Host no sustituye la confirmación de la GUI ni permite a Android ejecutar acciones. Android solicita y aprueba; únicamente el host PC autenticado puede reclamar y completar una acción.

## Cambios específicos de v0.6.2

El modelo remoto separa `requesting_device` —el Android que originó y aprobó— de `target_host` —el PC que puede reclamar—. El endpoint `/api/actions/pending` filtra por `target_host`; el host verifica su propio `device_id` en heartbeat, polling, claim y completion. El resultado `VerifiedActionResult` mantiene `execution_verified=true` únicamente cuando el Action Host confirma éxito de sus acciones estructuradas.

El onboarding PC/Android devuelve un URI `gaia://pair?id=...&code=...&url=...` junto con los campos raw. El URI solo contiene el pairing one-shot y su URL; el token permanente se entrega únicamente en `/api/pairing/complete`, se muestra una vez y se guarda en secure storage Android. `GAIA_PAIRING_SERVER_URL` permite reemplazar la URL local por una dirección LAN alcanzable, mientras `GAIA_LAN_ENABLED=false` continúa siendo el default.

La rotación administrativa usa `POST /api/devices/{device_id}/rotate-token`. El Core revoca tokens activos anteriores de forma atómica, registra una auditoría sin secretos y devuelve el nuevo token una sola vez. Si el Android recibe 401 por expiración o revocación, limpia secure storage y sesión, muestra el motivo y vuelve al PairingScreen; una caída de red sin 401 no borra el token.

El estado de métricas no secretas está disponible en `GET /api/diagnostics/performance` para un principal con capability diagnóstica. El endpoint expone backend, métricas de cola/LLM y perfil de rendimiento, pero no prompts completos, tokens, hashes ni contenido privado.

`RemoteActionHost.close()` activa el `stop_event`, cierra solo el cliente HTTP que posee y es idempotente. `run_forever()` detiene nuevos polls, intenta un último heartbeat defensivo y termina sin ejecutar pending adicionales. Un cierre externo durante una petición en curso no convierte el resultado parcial en éxito: la autoridad final sigue siendo `/api/actions/complete` con contrato verificado.
