#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="python3"
[ -x "$ROOT/.venv/bin/python" ] && PYTHON="$ROOT/.venv/bin/python"
cd "$ROOT/lumen-pc"
exec "$PYTHON" gui.py "$@"
