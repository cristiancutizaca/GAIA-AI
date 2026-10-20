# Post-repair test report

Environment: Linux sandbox, Python 3.12.3, localhost-only, no Ollama service, no GUI/audio hardware claim.

| Check | Result | Detail |
|---|---|---|
| Python compilation | PASS | 74 implementation/tool files, 0 failures; bytecode redirected outside release tree |
| Doctor safe/read-only | PASS | `read_only=true`; no service start/stop; Ollama `PENDING`; audio/Flutter `PENDING` |
| Test suite | PASS | 126/126 executable tests PASS, 0 FAIL |
| GUI tests | DEPENDENCY_MISSING | 3 tests require Tkinter, unavailable in this Linux image |
| RC6 runner contract | PASS | External venv transition now validates the supplied interpreter |
| Release build | PASS | 336 deterministic files; forbidden artifacts rejected |
| DeepSeek Harness fallback | PASS | Fallback contract test passes; real runtime remains NOT_MEASURED |
| Harness real E2E | BLOCKED | Requires installed SDK, running Ollama and an installed model |

The release is **automated-stable in this sandbox**, but not physically validated for Windows/ASUS hardware.
