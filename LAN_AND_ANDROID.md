# LAN, pairing y companion Android — v0.6.1

## LAN opt-in

El Core escucha en localhost por defecto. Para habilitar LAN se requiere `GAIA_LAN_ENABLED=true` y un `LUMEN_HOST` fuera de localhost; la configuración emite una advertencia porque el Core no integra TLS. La exposición remota debe usar una red confiable, un proxy TLS o un túnel seguro.

## Pairing

El master inicia un pairing para un `device_id` y un subconjunto de capabilities conocidas. El servidor genera un código de seis dígitos, conserva solo su digest asociado al `pairing_id`, aplica TTL y elimina el registro tras un uso correcto o tras el máximo de intentos inválidos. En `pairing/complete`, Core registra el Android con capabilities conservadoras, crea un token hashado y devuelve el valor en claro una sola vez. El pairing no crea un ejecutor ni convierte un dispositivo en master.

## Feature negotiation

Los peers negocian únicamente features conocidas y versiones iguales. `actions_execute` y `action_host` se eliminan de la negociación por defecto y solo pueden aparecer cuando el contexto autenticado y la configuración LAN permiten acciones remotas explícitas. Una feature desconocida se ignora, no se interpreta como permiso.

## Rate limiting

La autenticación usa una ventana deslizante por clave hasheada y responde `429` con `Retry-After` cuando se alcanza el límite. El limiter no persiste tokens, secretos ni direcciones completas; su estado en memoria se pierde al reiniciar, por lo que no sustituye un gateway de producción.

## Companion Android

Android conserva el token de dispositivo y `device_id` en `flutter_secure_storage`/`SharedPreferences` y nunca usa el secreto master. `session_id` se guarda para mantener continuidad entre reinicios. La aplicación puede iniciar chat/SSE, push-to-talk, voz/TTS, consultar estado y aprobar o rechazar una acción remota. Android no recibe `actions_execute` ni `action_host`, no importa `ActionEngine`, no recibe comandos locales y no ejecuta procesos.

Una acción remota se presenta como preview, scope, riesgo y opciones Allow Once/Always/Cancelar. La policy puede aprobar automáticamente solo cuando el grant scoped lo permite; solo entonces queda disponible para un PC Action Host con capability `action_host`. El host publica heartbeat, reclama, ejecuta localmente y envía un `VerifiedActionResult`. El prototipo Flutter no fue compilado en este sandbox porque el SDK Flutter no está instalado; la validación Android física queda pendiente.
