# Migration Matrix RC5 → RC6

| Origen | Target RC6 | Schema | Snapshot | Estrategia | Estado |
|---|---|---|---|---|---|
| RC5 `1.0.0-rc5-pc` | `1.0.0-rc6-pc` | 8–9 | `gaia-rc6-snapshot-1` | COPY_EXTERNAL / IN_PLACE explícita | Automatizable |
| RC4 histórico | `1.0.0-rc6-pc` | Según inspect | `gaia-rc6-snapshot-1` | Requiere compatibilidad confirmada | Automatizable si inspect pasa |
| RC3 histórico | `1.0.0-rc6-pc` | Según inspect | `gaia-rc6-snapshot-1` | Requiere copia y aprobación | Automatizable si inspect pasa |
| v0.9.2 histórico | `1.0.0-rc6-pc` | Según inspect | `gaia-rc6-snapshot-1` | Requiere migración explícita | Automatizable si inspect pasa |

El migrador no descarga código, no expone secretos, conserva el origen y rechaza schema fuera de 8–9, rutas anidadas, manifest incompatible, ausencia de aprobación o estrategia ambigua. Rollback requiere snapshot externo verificable.
