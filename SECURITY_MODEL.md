# Modelo de seguridad de GAIA-AI v0.5.2

## Principios

GAIA separa autenticación, autorización, clasificación y ejecución. El LLM nunca ejecuta. El Core no ejecuta acciones locales. El cliente PC usa un Action Engine allowlisted y un ActionCoordinator que solo orquesta resultados ya validados.

## Principal y RBAC

El Principal se construye únicamente después de validar bearer master o token de dispositivo en SQLite. El master tiene todas las capacidades. Un device recibe solo las capabilities persistidas en su registro. `permission_level` es metadata y no es una condición suficiente para autorizar.

| Credencial | Resultado |
|---|---|
| Ausente, inválida, expirada o revocada | 401 |
| Válida sin capability requerida | 403 |
| Master en operación administrativa permitida | 200 según validación de datos |
| Device en otra identidad, sesión o acción | 403 |

Los tokens de dispositivo se generan aleatoriamente, se muestran una sola vez y se guardan como SHA-256. `touch_device()` solo modifica presencia. Restore de Brain Backup, registro de devices, permisos, tokens y audit log son master-only.

## Voz y ownership

El endpoint `/api/chat/voice` requiere `voice` y `chat` mediante una dependencia única. STT se considera entrada no confiable y entra al mismo servicio interno de chat. No se llama una función de route desde otra route para saltar Depends.

Cada request SSE almacena temporalmente Principal, `device_id`, `token_id`, sesión y creación. Solo el Principal propietario puede cancelar; master puede cancelar. Metadata inexistente, corrupta o expirada se limpia y responde 404.

## Acción segura

El Core valida acciones estructuradas y planes de máximo tres pasos, cada uno nivel 1–2. El contrato no permite shell arbitrario, `eval`, `exec`, `sudo`, `cmd`, PowerShell, uploads arbitrarios ni argumentos desconocidos. El cliente revalida el catálogo y el riesgo. `AUTO_SAFE` permite únicamente nivel 1; `CONFIRM_EXECUTION` exige confirmación; `BLOCKED` no despacha.

El coordinador ejecuta secuencialmente, detiene ante fallo y no intenta rollback ficticio. La confirmación negativa ejecuta cero pasos. `/api/actions/complete` exige `actions_execute` + `action_host`, comprueba sesión, Principal propietario y `plan_id`, y registra únicamente resultado estructurado y limitado.

## Privacidad y LAN

`privacy=strict` reduce contexto PC y logs. Audio no se conserva por defecto. LAN está desactivada por defecto; al activarla, GAIA advierte que no incluye TLS. La protección de transporte debe aportarla una red confiable, proxy TLS o túnel seguro.

## Controles estáticos

La release se comprueba con grep para `shell=True`, `os.system(`, `eval(` y `exec(`, y con revisión de route-to-route calls. Estas comprobaciones no sustituyen revisión del sistema operativo, dependencias, permisos de archivos ni validación física.
