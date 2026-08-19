# MODIFIED FILES — GAIA-AI v0.5.3

La copia v0.5.3 se deriva directamente de la extracción del ZIP final v0.5.2. Conserva `lumen-core/`, `lumen-pc/`, `lumen-mobile/`, `LUMEN_*`, SQLite schema 5, action contract, RBAC, ownership, ActionCoordinator y secure storage Android. No se desarrolla v0.6, Android nuevo, LAN nueva ni Action Host.

## Baseline incorporado

| Archivo | Delta v0.5.3 |
|---|---|
| `BASELINE_V052.txt` | Registra auditoría desde ZIP v0.5.2: faltan `.env.example` y `.gitignore`; fresh install falla; `v04_test.py` pasó en reproducción disponible |
| `.env.example` | Nuevo dotfile distribuible con defaults actuales y placeholder de secreto |
| `.gitignore` | Nuevo dotfile con protecciones de secretos, SQLite/WAL/SHM, logs, backups, tokens, audio y caches |

## Core modificado

| Archivo | Delta v0.5.3 |
|---|---|
| `lumen-core/config.py` | Versión `0.5.3-pc`; schema, defaults y aliases conservados |
| `lumen-core/brain_backup.py` | Payload allowlisted, snapshot estable, sidecars prohibidos, manifest/ZIP verificados, lock de creación, checkpoint WAL activo antes de restore |
| `lumen-core/authz.py` | Header actualizado a v0.5.3; capabilities y permission_level intactos |

## PC, Android y tools

| Archivo | Delta v0.5.3 |
|---|---|
| `lumen-pc/gui.py` | Etiquetas visibles a v0.5.3; contrato y coordinator v0.5.2 conservados |
| `lumen-pc/action_response.py` | Docstring de release v0.5.3; parser canónico intacto |
| `lumen-mobile/pubspec.yaml` | Se conserva `0.5.2+8`; no se desarrolla Android en esta hotfix |
| `tools/gaia_doctor.py` | Etiqueta Doctor a v0.5.3 |
| `tools/build_release.py` | Nuevo build reproducible: allowlist, dotfiles, fail-closed hygiene, ZIP comparison, fixed timestamps y SHA posterior |

## Pruebas nuevas

| Archivo | Cobertura |
|---|---|
| `tests/release_package_test.py` | Estructura, dotfiles, documentación, hygiene, secrets patterns y git safety |
| `tests/brain_backup_portability_test.py` | DB WAL, conexión abierta, 12 round-trips create→restore, manifest exacto y cleanup de staging |
| `tests/brain_backup_wal_test.py` | Journal mode WAL activo preservado y sidecars excluidos |

## Pruebas actualizadas

| Archivo | Delta |
|---|---|
| `tests/smoke_test.py` | Assertions y etiqueta a `0.5.3-pc` |
| `tests/startup_test.py` | Health payload a `0.5.3-pc` |
| `tests/v051_test.py` | Version assertion a `0.5.3-pc`; Android heredado permanece `0.5.2+8` |
| `tests/device_permissions_test.py` | Docstring v0.5.3; RBAC v0.5.2 conservado |

## Documentación actualizada

| Archivo | Delta |
|---|---|
| `README.md` | Instalación literal desde ZIP, Python support, build, extracted tests y Brain Backup portable |
| `CHANGELOG.md` | Entrada v0.5.3 con fixes implementados y baseline honesto |
| `AUDIT.md` | Hallazgos v0.5.2 y controles de release/backup |
| `TEST_REPORT.md` | Separación WORKTREE/FINAL ZIP EXTRACTED y nuevas suites |
| `KNOWN_LIMITATIONS.md` | Debe conservar límites físicos y añadir soporte Python/package validation |
| `MIGRATION_LUMEN_GAIA.md` | Debe conservar namespace y describir actualización hotfix desde v0.5.2 |
| `ROLLBACK.md` | Debe añadir rollback de build/dotfiles/Brain Backup v0.5.3 |
| `MODIFIED_FILES.md` | Este inventario |
| `FINAL_VALIDATION.txt` | Se completa tras validar ZIP extraído y checksum final |

## Archivos heredados preservados

`routes/api.py`, `memory.py`, `action_intent.py`, `intent_classifier.py`, `llm.py`, `action_engine.py`, `action_coordinator.py`, `desktop_api.py`, `client.py`, `backup_scheduler.py`, startup, Doctor, Android service y las regresiones v0.3–v0.5.2 se conservan sin reescritura arquitectónica.
