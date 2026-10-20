# GAIA-AI v1.0-RC6 — Update, Migration and Rollback Guide

Esta es la guía operativa activa RC6. Para cualquier instalación existente, trabaje sobre una copia, confirme el origen y use un directorio externo para snapshots y evidencia. No sobrescriba una instalación sin aprobación explícita.

## Preflight y snapshot

```text
python tools/gaia_migrate.py --root <source> --target-version 1.0.0-rc6 --json --safe-mode
python tools/gaia_migrate.py --root <source> --target-version 1.0.0-rc6 --snapshot-dir <external-snapshot> --snapshot --json --safe-mode
```

El snapshot usa `gaia-rc6-snapshot-1`, checksum externo y estrategia explícita. No incluye valores secretos y conserva el origen. El esquema soportado permanece entre 8 y 9.

## Apply y rollback

Apply y rollback requieren una estrategia de base de datos, aprobación explícita y rutas de origen/target no anidadas. Tras apply verifique manifest, versión, schema, ownership, namespace, provenance y conteos. Ante cualquier discrepancia, detenga la operación y ejecute rollback desde el snapshot externo aprobado.

```text
python tools/gaia_migrate.py --root <source> --target-root <target> --snapshot-dir <external-snapshot> --target-version 1.0.0-rc6 --db-strategy COPY_EXTERNAL --apply --approve --json
python tools/gaia_migrate.py --root <target> --target-version 1.0.0-rc6 --snapshot-dir <external-snapshot> --rollback --approve --json
```

Los comandos no descargan código, no inician servicios, no emiten secretos y no autorizan una promoción fuera de RC6. Para validación física siga `WINDOWS_RC6_VALIDATION_CHECKLIST.md` y `PHYSICAL_VALIDATION_RC6.md`.
