# App Discovery y Safe App Trust en GAIA-AI v0.6.2

## Modelo

App Discovery enumera aplicaciones instaladas como datos read-only. En Windows inspecciona accesos directos del Start Menu y entradas de registro permitidas por el adapter; en plataformas no compatibles devuelve una lista vacía o un estado degradado explícito. El resultado se cachea con TTL para no escanear el sistema en cada mensaje.

Cada aplicación descubierta recibe un identificador canónico `discovered:<hash>`. El hash se calcula a partir de la definición canónica de lanzamiento y no permite sustituir el identificador por un path libre. La respuesta conserva el display name, origen, launch definition validada y nombres de proceso conocidos.

## Trust lifecycle

Discovery no concede ejecución. El usuario debe elegir `ALLOW_ONCE` o `ALWAYS_ALLOW` mediante la API o la interfaz correspondiente. `DENY`/`BLOCK` persiste un bloqueo para que una aplicación no pueda ser ejecutada por una intención posterior. `ALLOW_ONCE` se consume después de completar la acción; `ALWAYS_ALLOW` permanece hasta revoke.

| Estado | Descubierta | Ejecutable | Persistencia |
|---|---:|---:|---|
| Read-only | Sí | No | Cache TTL |
| `ALLOW_ONCE` | Sí | Una vez | Se consume al completar |
| `ALWAYS_ALLOW` | Sí | Sí | JSON de trust |
| `DENY`/`BLOCK` | Sí | No | JSON de trust |
| Revocada | Puede seguir visible | No | Se elimina o marca según operación |

## API

```text
GET  /api/apps/discovered?force_refresh=false
POST /api/apps/trust
```

Ejemplo de concesión:

```json
{
  "app_id": "discovered:2c6c...",
  "decision": "ALWAYS_ALLOW"
}
```

La API solo acepta `app_id` con prefijo `discovered:` y verifica que la entrada siga existiendo en el resultado de discovery. No se aceptan rutas, comandos, flags ni ejecutables aportados por el cliente.

## ActionEngine

La capability `apps.open_discovered` exige `app_id`, comprueba el prefijo canónico, resuelve la definición registrada, verifica trust persistente o temporal y valida que el launcher final sea un `.exe` existente en Windows. La ejecución usa la lista de argumentos construida por el adapter; nunca construye un comando shell concatenando texto del LLM.

El resultado se envía como `VerifiedActionResult`. Una frase del modelo no puede cambiar el `app_id`, el trust, el path ni el estado de ejecución. Si el trust no existe, la acción se bloquea con motivo explícito y no se crea una afirmación de éxito.

## Política recomendada

Usa discovery para inspeccionar, concede `ALLOW_ONCE` para la primera prueba y reserva `ALWAYS_ALLOW` para una aplicación cuya definición, origen y comportamiento local hayan sido comprobados. Revoca las entradas persistentes cuando se desinstale o cambie la aplicación.
