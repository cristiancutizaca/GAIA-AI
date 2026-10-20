# Baseline validation — RC6 Repaired Stable

Baseline: `GAIA-AI-v1.0-RC6-REPAIRED-STABLE.zip`. Checkpoint: `CHECKPOINT_00_RC6_REPAIRED_STABLE` is kept outside the project and read-only.

| Check | Result |
|---|---|
| Clean extraction | PASS |
| Existing RC6 tests | 126 PASS; 3 GUI tests dependency-missing in Linux sandbox |
| Compile | PASS |
| Security regression | PASS |
| Permission Layer / Action Host / Safe Mode / Kill Switch | PASS by existing RC6 contracts |
| Harness tests | PASS for fallback/contracts; real SDK/Ollama E2E not measured |
| Doctor | PASS read-only with physical dependencies pending |

No baseline file was modified before the v1.1 work.
