#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PY="$(command -v python)"
else
  echo 'Se necesita Python 3.10+ (recomendado 3.11).' >&2
  exit 1
fi
"$PY" -m pip install --disable-pip-version-check "deepseek-harness-sdk==0.1.5rc1"
"$PY" - <<'PY'
from importlib import metadata
from deepseek_harness import DeepSeekHarness
print(f"DeepSeek-Harness SDK instalado: {metadata.version('deepseek-harness-sdk')}")
PY
