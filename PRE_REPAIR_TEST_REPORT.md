# Pre-repair test report

Executed on a copy of the current package before code repair.

| Area | Result | Evidence |
|---|---|---|
| Python compilation | PASS | 74 files, 0 syntax failures |
| Doctor safe/read-only | PASS with WARN/PENDING | No services started; missing sandbox dependencies and Ollama reported honestly |
| Initial suite | BLOCKED by environment | Most failures were `ModuleNotFoundError` for `httpx`/`dotenv`; 3 GUI tests lacked Tkinter |
| Release gate | FAIL in copy | Compilation generated `__pycache__` and contaminated the source tree before the gate |
| RC6 runner transition | FAIL | External `--venv-path` was rejected because the parent process was outside the venv |
| Harness real E2E | NOT_MEASURED | SDK/Ollama/model were not available in the sandbox |

The initial dependency and artifact failures were reproduced without altering the immutable baseline.
