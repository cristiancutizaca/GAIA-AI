HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

HISTORICAL DOCUMENT — DO NOT USE FOR RC5 OPERATIONS

This document is preserved for historical traceability only. For current RC5 operations use `WINDOWS_RC5_VALIDATION_CHECKLIST.md`, `UPDATE_ROLLBACK_GUIDE.md` and `PHYSICAL_VALIDATION_RC5.md`.

# GAIA-AI v1.0-RC3 — Requirements and admission record

RC3 is derived from the frozen RC2 project ZIP. It is admitted because it adds bounded, repeatable performance evidence and a physical-validation harness while preserving the RC2 security contracts. It is not a final release and does not authorize a production declaration.

## Meaningful RC3 changes

| Change | Why it is significant | Evidence |
|---|---|---|
| Bounded benchmark tool | Makes memory save/retrieval and governor observation measurable without LLM/service side effects. | `tools/gaia_benchmark.py`, external `benchmark.json` and `benchmark.md`. |
| Guided physical validation tool | Provides a repeatable operator report while defaulting every physical item to PENDING instead of inventing PASS. | `tools/physical_validation.py`, external `physical_validation.json` and `physical_validation.md`. |
| RC3 package identity | Carries the new tools and docs through a deterministic candidate artifact derived from RC2. | `release_manifest.json`, package-first gate, clean extraction. |

## Benchmark result recorded for this run

The bounded benchmark used a temporary SQLite database with 200 explicit semantic items, 30 retrieval iterations, and 30 governor observations. The measured sandbox result was memory save mean **5.412 ms** with p95 **7.130 ms**, retrieval mean **8.003 ms** with p95 **9.032 ms**, and governor observation mean **0.004 ms**. The run recorded `read_only_host=true`, `ollama_started=false`, `model_downloaded=false`, `hardware_mutated=false`, and status `PASS`.

These numbers are not target-laptop performance claims. They are reproducible Linux sandbox evidence for bounded code paths only. GPU/VRAM, Ollama/Qwen, Windows/UIA/SMTC/display/audio, Android/Flutter/APK/signing, LAN/TLS, battery, and thermal behavior remain PENDING / NOT MEASURED.

## RC3 gates

RC3 must pass the same RC2 security and package gates, plus compileall, benchmark contract, physical-validation-template contract, clean extraction, external checksum, and deterministic rebuild comparison. The benchmark must not auto-start Ollama, download a model, mutate hardware, or write runtime artifacts into the project. Physical validation output must remain outside the release ZIP.

No second model, resident Vision, always-on Whisper, aggressive polling, power-plan change, GPU/fan/BIOS control, or new architecture is admitted by RC3. Safe Mode, namespace-first ownership, typed provenance, migration strategies, target identity, rollback modes, and shared governor authority remain unchanged.

The allowed candidate artifact is `GAIA-AI-v1.0-RC3-final.zip`. No `GAIA-AI-v1.0-final.zip` is created.
