# Trusted Folders en GAIA-AI v0.6.2

## Propósito

Trusted Folders es un registro explícito de carpetas autorizadas para operaciones de archivos del PC Action Host. La autorización es independiente de la intención del LLM, de la aplicación solicitante y de la existencia de un path en el sistema.

Cada entrada se canonicaliza con `Path.resolve()`, recibe un `folder_id` estable derivado del path y conserva una etiqueta, `read_allowed` y `write_allowed`. La decisión se evalúa en el límite de ejecución, no solo al construir la preview.

## Defaults personales

Al iniciar el registro se consideran confiables, si existen, las carpetas personales siguientes: `Documents`, `Downloads`, `Desktop` y `Pictures`. Estos defaults no convierten en confiable el home completo ni permiten atravesar hacia rutas hermanas. La raíz del filesystem, el home del usuario y rutas equivalentes a ellos se rechazan como scope raíz.

| Scope | Lectura | Escritura | Nota |
|---|---:|---:|---|
| Project directory del worktree | Sí | Sí según operación validada | Es el scope operativo principal |
| Documents | Sí | Sí por default personal | Se canonicaliza antes de comparar |
| Downloads | Sí | Sí por default personal | No permite confiar en el home entero |
| Desktop | Sí | Sí por default personal | Solo la carpeta canónica |
| Pictures | Sí | Sí por default personal | No incluye todo el home |
| Carpeta concedida por API | Según grant | Según `write_allowed` | Requiere principal master |

## API

La administración se realiza con principal master:

```text
GET    /api/trusted-folders
POST   /api/trusted-folders
DELETE /api/trusted-folders
```

El body de concesión es:

```json
{
  "path": "C:/Users/Ana/Documents/GAIA",
  "label": "Archivos GAIA",
  "write_allowed": true
}
```

La revocación recibe `folder_id`. La ruta mostrada por la API es la canónica; el servidor no acepta un `folder_id` inventado como sustituto del path ni transforma un path remoto en un ejecutable.

## Integración con ActionEngine

`ActionEngine._safe_file(..., write=False)` valida existencia cuando corresponde, mantiene el project scope, comprueba proyectos confiables registrados y consulta Trusted Folders para rutas externas. Las operaciones de escritura pasan `write=True`. `_ensure_allowed_parent()` exige que el directorio padre pertenezca al proyecto o tenga write trust explícito.

Las operaciones no aceptan comandos shell libres, `shell=True`, `eval`, `exec` ni paths entregados como ejecutables. La validación de la capability y la validación de Trusted Folders se ejecutan nuevamente en el host local.

## Recomendaciones de operación

Concede el scope más pequeño que resuelva la tarea y deja `write_allowed=false` para carpetas de consulta. Revoca el grant cuando ya no sea necesario. No concedas el home, el filesystem root, una carpeta de secretos, una carpeta de tokens ni un directorio que contenga credenciales de terceros.

> Trusted Folders amplía un scope de archivos; no concede acceso a procesos, power, navegador, red ni capacidades de ejecución fuera del registry.
