# GAIA-AI v1.0-RC6 Threat Model

| Amenaza | Control RC6 | Evidencia |
|---|---|---|
| Cache poisoning o fuga cross-namespace | Keys con namespace/owner, límites e invalidación. | Tests de cache y ownership. |
| Doble ejecución o permisos stale | Preflight, deduplicación, confirmación explícita y kill switch. | Tests de Action Host y Safe Mode. |
| Queue flooding o tasks huérfanas | Backpressure, timeouts, cancelación y shutdown ordenado. | Tests de concurrencia. |
| TOCTOU y corrupción SQLite | Ownership, hashes, copias externas, transacciones y query-plan. | Tests de migración y DB. |
| Secretos o datos privados en release | Redacción, allowlist, auditoría de sufijos y ZIPs. | Security scan y file audit. |
| Mutación de hardware o modelo | APIs read-only y política sin descarga/arranque. | AST/estructural y side-effect tests. |

La validación física permanece separada de la automatización Linux.
