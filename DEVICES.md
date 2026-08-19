# Dispositivos y tokens de GAIA-AI v0.5.2

## Registro

Solo el Principal master registra dispositivos y define nombre, tipo, capabilities y `permission_level`. El cliente no puede autoelevar sus capacidades. `touch_device()` registra presencia o actualiza `last_seen`, pero no modifica metadata administrativa.

## Capabilities

Las capabilities son la autoridad de autorización. `permission_level` es metadata de agrupación y futuro uso; incluso un valor legado alto no concede `admin`, `memory_write`, `voice`, `actions_execute` ni restore. El master no depende de esa metadata para autorizarse.

## Token de dispositivo

El master crea un token para un `device_id`. La respuesta muestra el token claro únicamente en esa creación. SQLite conserva SHA-256, `token_id`, expiración, timestamps y revocación, nunca el token claro. El token puede revocarse individualmente o junto con el dispositivo. Tras expiración o revocación, autenticación devuelve 401.

| Operación | Autorización |
|---|---|
| Registrar device | Master |
| Cambiar capabilities o nivel | Master |
| Crear, listar o revocar tokens | Master |
| Consultar `/devices/{id}/self` | Device con `device_self`, solo su propio id; master puede consultar |
| Chat | Capability `chat` |
| Voz conversacional | Capabilities `voice` y `chat` |
| Completar acción local | `actions_execute` + `action_host` |
| Brain Restore | Master |

## Migración y almacenamiento

La metadata heredada se mantiene en schema 5. No se realiza una migración LUMEN→GAIA automática. Los clientes Android deben guardar el token de dispositivo en `flutter_secure_storage`; no deben enviar un secreto master por defecto.

La revocación, expiración y ownership se prueban automáticamente. La seguridad del dispositivo físico, almacenamiento del sistema operativo, copia de pantalla, TLS LAN y pérdida del teléfono requieren validación operativa adicional.
