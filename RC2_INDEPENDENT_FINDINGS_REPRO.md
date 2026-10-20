HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

HISTORICAL DOCUMENT — DO NOT USE FOR RC5 OPERATIONS

This document is preserved for historical traceability only. For current RC5 operations use `WINDOWS_RC5_VALIDATION_CHECKLIST.md`, `UPDATE_ROLLBACK_GUIDE.md` and `PHYSICAL_VALIDATION_RC5.md`.

# GAIA-AI v1.0-RC2 — Reproducción independiente de hallazgos

**Base auditada:** extracción limpia `GAIA-AI-v1.0-RC1-final.zip`, SHA-256 `c1a62ea075ca941f04e0c0dc003c7871a42e2ca062793be0fb6b11531a889b87`. La reproducción se ejecutó antes de modificar el worktree RC2 y no alteró el ZIP RC1.

## Resultado

Los siete hallazgos A–G se reprodujeron en una instalación temporal con `PYTHONDONTWRITEBYTECODE=1`. El reproductor externo fue `/home/ubuntu/reproduce_rc2_findings_before.py`; su salida estructurada está en `/home/ubuntu/RC2_INDEPENDENT_FINDINGS_BEFORE.json`.

| ID | Hallazgo reproducido | Evidencia observada | Causa raíz |
|---|---|---|---|
| A | CRUD/search Advanced Memory cross-device | Un item `session-a` con `device_id=""` apareció para `device-b` en retrieve/list. | `_scope_clause` trata `device_id=''` como visible y `_advanced_memory_visible` usa `not item.device_id`. |
| B | Variantes de provenance operativa | Se aceptaron `event.1`, `event/1`, `event-1`, `automation.run`, `clipboard.copy`, `uia.observation` y `screenshot.foo`; `EVENT:1` sí estaba bloqueado. | El parser divide solo por `:` y no usa un modelo de origen tipado/canónico. |
| C | Alias de DB externa/Vault | Tras apply, la DB target interna se creó pero el `.env` target quedó apuntando a la DB externa de la instalación fuente. | Se resuelve target DB antes de copiar el `.env` fuente y no existe estrategia de DB explícita. |
| D | Target release incorrecto aceptado | Se aplicó sobre una carpeta con `VERSION=0.5.0-pc` porque solo se comprobó `lumen-core`. | No hay manifest/identidad inmutable ni validación de versión target antes de mutar DB. |
| E | Rollback omite configuración | Rollback restauró DB, pero dejó intacto un `.env` target modificado. | `rollback_from_snapshot()` solo restaura SQLite y no tiene modo explícito de configuración. |
| F | Safe Mode no es runtime policy | `main.py` inicia `runtime.start()` sin leer `GAIA_SAFE_MODE`; loops opcionales también se evalúan normalmente. | Safe Mode estaba limitado a migrator/Doctor y no al bootstrap Core ni a la matriz de efectos. |
| G | ResourceGovernor parcialmente desconectado | Runtime tiene un governor, pero solo observa en `_apply_governor()` durante start/refresh; no existe monitor low-frequency de transiciones. | No hay autoridad de estado compartida/monitorizada que actualice todos los consumidores en runtime. |

## Criterio de corrección

RC2 no debe añadir excepciones por cadena concreta. La autorización debe derivarse del namespace y del `MemoryAccessContext`; provenance debe validarse como origen tipado; migración debe exigir estrategia de DB/Vault y target release identity antes de escribir; rollback debe declarar si restaura DB, configuración o instalación; Safe Mode debe bloquear efectos en Core/PC/remote/automation; y el governor debe tener una única autoridad de estado con actualizaciones bounded.

La auditoría física no se infiere de esta reproducción. Windows, Android, Ollama, GPU, audio, LAN/TLS, batería y thermal permanecen fuera del sandbox.
