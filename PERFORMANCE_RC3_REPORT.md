# Performance report — GAIA-AI v1.0-RC3

## Scope

This report records a bounded deterministic run over the RC3 code derived from frozen RC2. It exercises Advanced Memory writes and retrieval against temporary SQLite storage and observes the read-only ResourceGovernor. It does not start a service, auto-start Ollama, download a model, change hardware, or use physical target telemetry.

## Recorded run

| Metric | Value |
|---|---:|
| Temporary memory items | 200 |
| Retrieval iterations | 30 |
| Memory save total | 1082.609 ms |
| Memory save mean | 5.412 ms |
| Memory save p95 | 7.130 ms |
| Retrieval mean | 8.003 ms |
| Retrieval p95 | 9.032 ms |
| Retrieval results returned | 240 |
| Governor observe total | 0.118 ms |
| Governor observe mean | 0.004 ms |
| Governor transitions | 0 |
| Governor profile | `laptop_balanced` |
| Host read-only | `true` |
| Ollama started | `false` |
| Model downloaded | `false` |
| Hardware mutated | `false` |
| Run status | **PASS** |

The JSON source is kept as external evidence at `RC3-benchmark-evidence/benchmark.json` in the working environment; the release package contains the benchmark source and this report, not runtime databases or external evidence directories.

## Interpretation

The result demonstrates that the bounded code path completes with finite work and stable aggregate timings for the selected fixture. It does not establish latency, thermals, VRAM use, battery behavior, Ollama throughput, Windows integration, Android behavior, audio behavior, LAN/TLS behavior, or long-session performance on the operator's ASUS TUF laptop. Those measurements require a human-confirmed physical run and remain PENDING / NOT MEASURED.

The benchmark's read-only host contract is intentional. It is not permitted to start Ollama or install a model as a side effect of measurement. A future target-hardware run may provide additional evidence, but it must preserve the same no-side-effect rule and report exact commands, configuration profile, and redacted output.
