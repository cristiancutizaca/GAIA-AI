# Performance and stress plan — RC2 / RC3

RC2 prioritizes correctness and bounded behavior. Performance work is limited to measurements that can be reproduced in the sandbox without starting persistent services, contacting a real Ollama instance, or pretending that target hardware telemetry exists. RC3 may contain only changes justified by a measured bottleneck, stress result, soak result, or physical-readiness requirement.

## RC2 controls

The shared `ResourceGovernor` is read-only. It keeps heavy background LLM concurrency at one, does not load Vision, Embeddings, or resident Whisper models, and does not change GPU, fan, BIOS, Windows power-plan, or Ollama state. Its monitor interval is bounded by `GAIA_RESOURCE_GOVERNOR_REFRESH_SECONDS` to 15–300 seconds, default 30 seconds. Sustained pressure requires two high samples to throttle and three low samples to recover.

Safe Mode avoids scheduler, watcher, proactive, backup, and external action effects. Chat and diagnostics remain usable. Memory retrieval respects a bounded context and item budget; operational provenance is rejected before semantic memory writes.

## Measurements

| Measurement | Method | Required output | RC2/RC3 status |
|---|---|---|---|
| Memory CRUD/search | Direct deterministic fixture with isolated SQLite database. | JSON and Markdown counts, elapsed time, failures. | RC2 contract; RC3 scale run. |
| Provenance rejection | Canonical variant matrix across separators, case, and compound forms. | Accepted/rejected counts and examples without secrets. | RC2 PASS. |
| Snapshot/restore | SQLite Backup API on temporary fixture databases. | Duration, checksum, row count, rollback result. | RC2 contract; target filesystem timing pending. |
| Governor transitions | Injected read-only snapshots. | Transition count, interval multipliers, deferment, lifecycle. | RC2 PASS. |
| Soak | Bounded process lifetime and fixed event/message counts. | Memory growth, errors, pending tasks, final status. | RC3 only if meaningful. |
| Ollama/Qwen/GPU | Read-only check only; no auto-start. | Explicit unavailable/PENDING state if absent. | PENDING / NOT MEASURED in sandbox. |

The benchmark must emit machine-readable JSON and a human-readable Markdown report. It must not write to project runtime directories, include private config, log tokens, or place generated reports in a release package unless explicitly allowlisted as deterministic source evidence. Physical validation output is operator evidence and stays outside the ZIP.

## RC3 admission rule

RC3 is justified only if the benchmark or stress run identifies a material improvement such as bounded retrieval latency under a larger fixture, lower memory growth, safer transition behavior, or a reproducible readiness gap that can be addressed without a new architecture. Cosmetic version changes, speculative adaptive Ollama keep-alive, aggressive polling, second models, always-on Vision/Whisper, and hardware-control code are out of scope.

Target laptop assumptions supplied by the operator are recorded as planning inputs only: Windows ASUS TUF, i5-12500H, approximately 48 GB RAM, RTX 3050 4 GB, and Ollama `qwen3.5:9b`. They are not measured facts in this environment. GPU/VRAM, battery, thermal, audio, LAN/TLS, Windows/UIA/SMTC/display, Android/Flutter/APK, and signing remain PENDING until human-confirmed physical tests exist.
