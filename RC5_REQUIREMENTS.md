HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v1.0-RC5 Requirements

## Baseline

RC5 must be derived only from the frozen RC4 project ZIP with SHA-256 `3d4af9e3e68106fdbfae4869a4505bebea6ffe65bd313f31fa4e5fcb93891165` and RC4 documentation ZIP with SHA-256 `4c406b0cb6282b9502a8249a2c5fce33142373fc8a5fda3404e0726c3d648f5c`. RC4 remains immutable.

## Confirmed defects corrected by RC5

| Defect | Required correction | Required evidence |
|---|---|---|
| New physical ledger saved summary counts at zero | Call dynamic summary calculation before first save | `rc5_physical_validation_integrity_test.py` |
| Ledger test did not read immediately after `new` | Validate 12 real controls before `show` | Same test |
| Active rollback guide remained RC1 | Reconstruct active guide as RC5 with target `1.0.0-rc5` | Documentation identity test |
| Historical command documents lacked warnings | Preserve content and prepend historical-use warning with RC5 links | Historical warning test |
| Install flow validated before dependency installation | Package gate, initial preflight, explicit venv installation, freeze, post-install preflight, then tests | Runner contract |
| Runner ignored newly created venv | Resolve and use the venv interpreter for every post-install stage | Runner contract and report |
| Wrapper remained RC4 | Add StrictMode RC5 wrapper with path/archive/evidence/install checks | PowerShell contract |
| Migrator printed RC2 and used RC4 snapshot identity | RC5 messages, target and `gaia-rc5-snapshot-1` | Migrator CLI contract |
| Documentation test omitted rollback guide | Include all active documents and CLI/wrapper surfaces | Documentation contract |
| Artifact index was incomplete | Enumerate all 16 external delivery artifacts with self-hash strategy | Artifact-index contract |

## Acceptance

RC5 may be frozen only when baseline verification, all defect regressions, package gate, compile, dependency flow, full dynamic suite, benchmark, security classification, manifest, deterministic rebuilds, clean extraction, exact 16-file delivery inventory and checksums pass. Physical controls must remain PENDING unless independently confirmed by the operator. No final GAIA 1.0 artifact or promotion is permitted.
