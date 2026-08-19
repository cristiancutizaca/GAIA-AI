#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ] && [ -x "$ROOT/.venv/bin/python" ]; then PYTHON="$ROOT/.venv/bin/python"; fi
if [ -z "$PYTHON" ]; then PYTHON="$(command -v python3 || true)"; fi
if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
  echo "GAIA: no encuentro Python del venv ni python3. No instalo dependencias automáticamente." >&2
  exit 1
fi
PORT="${LUMEN_PORT:-8090}"
HOST="${LUMEN_HOST:-127.0.0.1}"
if [ -f "$ROOT/.env" ]; then
  configured_port="$(sed -n 's/^LUMEN_PORT=//p' "$ROOT/.env" | head -n 1)"
  configured_host="$(sed -n 's/^LUMEN_HOST=//p' "$ROOT/.env" | head -n 1)"
  [ -n "$configured_port" ] && PORT="$configured_port"
  [ -n "$configured_host" ] && HOST="$configured_host"
fi
# 0 = GAIA activo; 2 = puerto ajeno; 1 = Core offline.
set +e
"$PYTHON" "$ROOT/tools/gaia_startup_probe.py" --host 127.0.0.1 --port "$PORT"
probe=$?
set -e
if [ "$probe" -eq 0 ]; then
  echo "GAIA Core ya está activo. Abriendo GUI."
  exec "$PYTHON" "$ROOT/lumen-pc/gui.py" --url "http://$HOST:$PORT"
fi
if [ "$probe" -eq 2 ]; then
  echo "GAIA: el puerto $PORT está ocupado por otra aplicación. No iniciaré una segunda instancia ni mataré el proceso." >&2
  exit 2
fi
mkdir -p "$ROOT/lumen-core/data/logs"
cd "$ROOT/lumen-core"
nohup "$PYTHON" main.py >> "$ROOT/lumen-core/data/logs/start-gaia-core.log" 2>&1 &
core_pid=$!
echo "GAIA Core iniciado por este script con PID $core_pid; esperando /api/health (máximo 30 s)."
for _ in $(seq 1 30); do
  set +e
  "$PYTHON" "$ROOT/tools/gaia_startup_probe.py" --host 127.0.0.1 --port "$PORT" >/tmp/gaia_startup_probe.out 2>&1
  probe=$?
  set -e
  if [ "$probe" -eq 0 ]; then
    cat /tmp/gaia_startup_probe.out
    exec "$PYTHON" "$ROOT/lumen-pc/gui.py" --url "http://$HOST:$PORT"
  fi
  if [ "$probe" -eq 2 ]; then
    cat /tmp/gaia_startup_probe.out >&2
    echo "GAIA: el puerto cambió a una aplicación ajena; revisa el log." >&2
    exit 2
  fi
  sleep 1
done
echo "GAIA Core no respondió en 30 s. Revisa $ROOT/lumen-core/data/logs/start-gaia-core.log; el proceso iniciado no fue detenido automáticamente." >&2
exit 1
