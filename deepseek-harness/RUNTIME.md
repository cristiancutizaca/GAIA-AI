# Runtime DeepSeek Harness de GAIA

GAIA usa `deepseek-harness-sdk==0.1.5rc1`. El SDK instala automáticamente el wheel `deepseek-harness-runtime-bin` de la misma versión, por lo que el camino normal de ejecución no requiere Node.js ni `node_modules`.

`gaia-safe.patch.yml` desactiva el shell persistente del perfil `sdk-minimal`. GAIA conserva la autoridad sobre acciones, archivos y permisos del equipo.
