HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

HISTORICAL DOCUMENT — DO NOT USE FOR RC5 OPERATIONS

This document is preserved for historical traceability only. For current RC5 operations use `WINDOWS_RC5_VALIDATION_CHECKLIST.md`, `UPDATE_ROLLBACK_GUIDE.md` and `PHYSICAL_VALIDATION_RC5.md`.

# GAIA-AI v1.0-RC2 — Requirements and acceptance gates

**Release scope.** RC2 is a security, ownership, migration, Safe Mode, and shared-resource-governance hardening release derived exclusively from the clean v1.0-RC1 extraction. It is a release candidate, not a production declaration and not `v1.0 final`.

## Findings A–G and required outcomes

| Finding | RC1 behavior reproduced | RC2 acceptance outcome |
|---|---|---|
| A. Advanced Memory ownership | A row with blank `device_id` could be retrieved or listed by another device. | Namespace-first authorization is enforced at the authenticated API boundary. Device, session, working, and task namespaces require an exact owner device; blank legacy rows fail closed for non-master callers. CRUD, history, search, and audit use the same context. |
| B. Provenance | Delimiter parsing allowed variants such as `event.1`, `event/1`, `event-1`, and compound operational references. | Provenance is canonicalized by type and normalized reference tokens. Operational origins such as events, UIA, screenshots, clipboard, SMTC, automation, scheduler, and system observations are blocked from automatic semantic memory writes regardless of case or separator. |
| C. External Vault alias | Apply could copy the source snapshot and then leave the target runtime pointing at the source database. | Database selection is explicit. Clone-to-target yields a target-local database; external reuse is an explicit strategy; new Vault creation writes the selected target path. Implicit source aliasing is blocked. |
| D. Target identity | Apply accepted a folder mainly because it contained `lumen-core`. | Mutation requires a valid `release_manifest.json`, exact product/release/version/protocol identity, schema range 8–9, target config version, and required migrator files. Validation occurs before snapshot application or target mutation. |
| E. Rollback scope | Rollback restored the database but could leave target configuration changed. | Rollback mode is explicit: database-only, database-and-config, or operator-managed previous-installation procedure. Full config rollback requires a verified pre-change config copy. Secret values are never rendered in reports. |
| F. Safe Mode | `GAIA_SAFE_MODE` was documentation-only for runtime startup. | Safe Mode is read at startup and pauses automation, scheduler, watchers, proactive behavior, and backups. Chat, diagnostics, memory reads, and audit remain available. External actions, approvals, remote execution, automation enablement, and mutations return `SAFE_MODE_BLOCKED`. Exit requires a restart/config change, never an LLM decision. |
| G. ResourceGovernor authority | Runtime and API paths could use different governor instances, with no bounded transition monitor. | The runtime owns one read-only governor. API diagnostics and prompt budgeting resolve that same instance. Battery and sustained thermal/pressure transitions use debounce; scheduler/watchers receive bounded interval changes; heavy background work remains concurrency-one and consolidation can be deferred. |

## Security and packaging gates

The RC2 gate is passed only when the exact test suite completes with zero failures, target modules compile without bytecode artifacts, the release builder passes before full validation, and a clean extraction reproduces the same result. The package may contain source, documentation, tests, and examples only. It must not contain private `.env` files, databases, logs, tokens, audio, backups, runtime directories, generated APKs, or ZIP files nested inside the archive.

The following controls remain absolute: no `shell=True`, `os.system`, `eval`, `exec`, arbitrary command construction, or LLM-to-subprocess path; no unattended high-risk self-grant; no automatic semantic memory from operational origins; no secret values in logs, reports, manifests, or archives; and no physical readiness claim for Windows, Android, Ollama, GPU, audio, LAN/TLS, battery, or thermal items that were not measured on the target hardware.

## Release identity

| Field | Required RC2 value |
|---|---|
| Product | `GAIA-AI` |
| Release label | `1.0-RC2` |
| Core version | `1.0.0-rc2-pc` |
| Protocol | `1.0-RC2` |
| Schema range | Minimum 8, maximum 9 |
| Final artifact name | `GAIA-AI-v1.0-RC2-final.zip` |

The artifact name above is a release-candidate artifact. No file named `GAIA-AI-v1.0-final.zip` may be created.
