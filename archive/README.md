# Archivo histórico de GAIA-AI

Esta carpeta conserva documentos y reportes anteriores a GAIA 2.0. No son archivos eliminados: cada documento mantiene su contenido original y su historial Git. La raíz del repositorio retiene código, instaladores, pruebas y documentos de compatibilidad RC6 que todavía utilizan herramientas históricas.

- `history/v1.1/` a `history/v1.8/`: informes y notas de desarrollo antiguos.
- `history/baselines/`: instantáneas y documentos anteriores a las correcciones finales.
- `MOVED_FILES.json`: índice de las rutas originales y nuevas, con los SHA de Git para comprobar que los contenidos no cambiaron.

**Restauración:** recupera un archivo desde esta carpeta con `git mv archive/history/<grupo>/<archivo> <archivo>` en una rama de trabajo; revisa las referencias y ejecuta las pruebas antes de integrar. La rama `backup/pre-archive-gaia-2026-10-19` conserva exactamente la estructura anterior al traslado.

Los documentos antiguos no deben tratarse como instrucciones actuales de instalación o seguridad. Para trabajar usa la documentación activa en la raíz.
