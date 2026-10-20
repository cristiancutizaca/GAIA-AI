HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

HISTORICAL DOCUMENT — DO NOT USE FOR RC5 OPERATIONS

This document is preserved for historical traceability only. For current RC5 operations use `WINDOWS_RC5_VALIDATION_CHECKLIST.md`, `UPDATE_ROLLBACK_GUIDE.md` and `PHYSICAL_VALIDATION_RC5.md`.

# GAIA Vault migration — v1.0-RC2

This guide describes the only supported database/Vault migration behaviors in RC2. Inspection is read-only by default. Apply and rollback require explicit operator approval, a verified target release identity, an external snapshot destination, and an explicit database strategy.

## Database strategies

| Strategy | Database result | Target `.env` behavior | Safety meaning |
|---|---|---|---|
| `CLONE_TO_TARGET` | Copies the verified SQLite snapshot into `target/lumen-core/data/lumen_memory.db`. | Existing target configuration must already resolve to that internal path or be absent. | Default clone; implicit external aliases are refused. |
| `REUSE_EXISTING_EXTERNAL_VAULT` | Does not copy the database. | Writes `GAIA_MEMORY_DB` to the inspected external source database. | Deliberate shared/reused Vault; never selected implicitly. |
| `CLONE_TO_NEW_VAULT` | Copies the snapshot into `<new-vault>/data/memory/lumen_memory.db`. | Writes `GAIA_MEMORY_DB` to the new Vault path. | New external Vault must be outside both source and target roots. |
| `KEEP_TARGET_CONFIG` | Resolves the existing target configuration and copies unless it is the same physical database. | Leaves target configuration unchanged. | Requires an existing target `.env`; ambiguous same-DB use is refused. |

The source installation and target installation must be distinct and non-nested. A snapshot destination must be outside the source installation and must be new or empty. Linux paths, opaque Windows drive paths, and UNC spellings are handled as path values; the migrator does not execute, download, or interpret external content as code.

## Configuration resolution

The migrator follows the same alias order used by the runtime: `GAIA_MEMORY_DB`, then `LUMEN_MEMORY_DB`, then `GAIA_DATA_DIR`, then `LUMEN_DATA_DIR`, then `GAIA_HOME`/`GAIA_VAULT`, and finally the local `lumen-core/data/lumen_memory.db` fallback. A process environment value takes precedence over `.env`, matching the runtime's `load_dotenv(..., override=False)` behavior. Operators should therefore clear unrelated process variables before inspecting a foreign installation.

The target is not trusted merely because a folder contains `lumen-core`. Before mutation, RC2 requires `release_manifest.json` with product `GAIA-AI`, release `1.0-RC2`, version `1.0.0-rc2-pc`, protocol `1.0-RC2`, schema range 8–9, and a matching `lumen-core/config.py` version. The target must also contain `tools/gaia_migrate.py`.

## Snapshot and rollback

A snapshot uses SQLite Backup API and records a checksum for `memory.snapshot.sqlite`. It may include `.env.private.copy` and `.env.target.before.copy` as operator-only files outside the release archive. Reports contain paths and booleans, never secret values. The source installation is never rewritten by snapshot creation.

Rollback must specify one of the following modes:

| Mode | Database | Target config | Code |
|---|---|---|---|
| `ROLLBACK_DATABASE_ONLY` | Restore the target database from the verified snapshot. | Leave the target `.env` unchanged. | Not restored. |
| `ROLLBACK_DATABASE_AND_CONFIG` | Restore the target database. | Restore the verified pre-change target `.env`; fail if that copy is absent. | Not restored. |
| `ROLLBACK_TO_PREVIOUS_INSTALLATION` | Restore the target database and config where available. | Restore the pre-change config. | The folder/code swap remains an explicit operator procedure and is reported as `installation_code_restored=false`. |

A database-only rollback is intentionally not a complete installation rollback. Use the full-config mode when a migration changed a target Vault path. Do not paste private config copies into a release archive.

## Operator sequence

First run inspection with `--json --safe-mode`, review compatibility, schema, integrity, externality, and counts, and choose an external snapshot directory. Create the snapshot and verify its checksum. Confirm the target manifest and select one explicit database strategy. Only then run apply with `--approve`. After validation, retain the snapshot until the observation window is complete; if necessary, run rollback with an explicit mode and verify both database content and target configuration.

RC2 does not claim successful migration on Windows, Android, signing, LAN/TLS, Ollama, GPU, battery, or thermal hardware until those physical checks are performed by the operator. Those items remain pending in the readiness records.
