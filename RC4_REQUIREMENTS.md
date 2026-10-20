HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

HISTORICAL DOCUMENT — DO NOT USE FOR RC5 OPERATIONS

This document is preserved for historical traceability only. For current RC5 operations use `WINDOWS_RC5_VALIDATION_CHECKLIST.md`, `UPDATE_ROLLBACK_GUIDE.md` and `PHYSICAL_VALIDATION_RC5.md`.

# GAIA-AI v1.0-RC4 — Requirements

RC4 is a release-candidate consolidation of the frozen RC3 artifact. Its scope is documentation correctness, reproducible validation, dependency reporting, benchmark/readiness evidence, and identity alignment. It does not introduce a new architecture, a new executor, a second resident model, hardware control, or a production promotion.

## Provenance

The input is `/home/ubuntu/GAIA-AI-v1.0-RC3-final.zip`, verified before extraction with SHA-256 `c67830f89e8e089e4b398d7a9c83c8ab3693ea59f69bc841e3ce6d0af631ca30`. RC3 was extracted into a new directory and remains unchanged. RC4 work occurs only in that extraction.

## Active identity

| Field | RC4 value |
|---|---|
| Product | `GAIA-AI` |
| Release | `1.0-RC4` |
| Core/PC | `1.0.0-rc4-pc` |
| Protocol | `1.0-RC4` |
| Android/Flutter | `1.0.0-rc4+1` |
| Android versionName | `1.0-RC4` |
| Schema range | `8–9` |
| Package root | `GAIA-AI-v1.0-RC4` |
| Project candidate | `GAIA-AI-v1.0-RC4-final.zip` |
| Documentation candidate | `GAIA-AI-v1.0-RC4-docs.zip` |

## Required RC4 changes

The active documentation must start with RC4, describe RC3 as the immediate baseline, and retain RC2/RC1 as historical context without presenting historical results as current. `MODIFIED_FILES.md` must list RC4, RC3, RC2, RC1, and earlier history in descending order. `TEST_REPORT.md` and `FINAL_VALIDATION.txt` must be clean current reports with exact environment, command, counts, PASS/FAIL/SKIP/PENDING/TIMEOUT and limitations.

`tools/validate_rc4.py` must be read-only by default, use list-form subprocess calls with `shell=False`, impose timeouts, write reports outside the project, distinguish dependency absence from functional failures, run the package gate before compilation in `--all`, and never install dependencies without `--install-dependencies --confirm-install`. `validate-gaia-rc4.ps1` must remain a safe Windows wrapper whose PowerShell implementation is authoritative.

`tools/physical_validation.py` must support `new`, `show`, `record`, and `finalize`; create timestamped external sessions; start every control at `PENDING`; require human confirmation and evidence for PASS; preserve previous evidence; and never infer physical PASS from mocks, imports, local APIs, Windows detection, model presence, GPU enumeration, or keystore existence. `tools/gaia_benchmark.py` must report mean, median, p95, max, total, environment, fixture, and side-effect facts without starting Ollama or changing hardware.

## Acceptance gates

RC4 may be frozen only when the RC3 hash and ZIP integrity pass, identity and manifest are RC4-consistent, package gate passes before compilation, syntax compilation passes without contaminating the candidate tree, dependencies are reported, the dynamically discovered complete suite has zero FAIL/TIMEOUT, RC4 focal contracts pass, benchmark and physical-template contracts pass, security scan has no unsafe implementation pattern, the release ZIP is unique/Zip-Slip-safe/hygienic, and two rebuilds are byte-identical. Physical checks may remain PENDING; in that case the allowed decision is `RC4 FROZEN / PHYSICAL VALIDATION PENDING` or `RC4 FROZEN / AUTOMATED PASS / OPERATOR REVIEW REQUIRED`.

The process must never create `GAIA-AI-v1.0-final.zip`, say `production-ready`, or promote RC4 automatically.
