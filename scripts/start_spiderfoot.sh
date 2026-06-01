#!/usr/bin/env bash
# Start SpiderFoot web UI in the background (CherryPy on SPIDERFOOT_PORT).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ "${SPIDERFOOT_ENABLED:-true}" != "true" ]; then
  echo "SpiderFoot disabled (SPIDERFOOT_ENABLED=false)"
  exit 0
fi
if [ "${SPIDERFOOT_AUTOSTART:-true}" != "true" ]; then
  echo "SpiderFoot autostart disabled"
  exit 0
fi

SF_DIR="${SPIDERFOOT_DIR:-third_party/spiderfoot}"
SF_PORT="${SPIDERFOOT_PORT:-5001}"
SF_HOST="${SPIDERFOOT_HOST:-127.0.0.1}"
SF_DATA="${SPIDERFOOT_DATA:-data/spiderfoot}"

if [ ! -f "$SF_DIR/sf.py" ]; then
  echo "SpiderFoot not found at $SF_DIR — skipping autostart"
  exit 0
fi

mkdir -p "$SF_DATA"
export SPIDERFOOT_DATA="$SF_DATA"

if curl -sf "http://${SF_HOST}:${SF_PORT}/ping" >/dev/null 2>&1; then
  echo "SpiderFoot already running on ${SF_HOST}:${SF_PORT}"
  exit 0
fi

PYTHON="${ROOT}/third_party/spiderfoot/venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3 || command -v python)"
fi

echo "Starting SpiderFoot on ${SF_HOST}:${SF_PORT} (data: ${SF_DATA})"
nohup "$PYTHON" "$SF_DIR/sf.py" -l "${SF_HOST}:${SF_PORT}" >> "${SF_DATA}/spiderfoot.log" 2>&1 &
echo $! > "${SF_DATA}/spiderfoot.pid"

for _ in $(seq 1 30); do
  if curl -sf "http://${SF_HOST}:${SF_PORT}/ping" >/dev/null 2>&1; then
    echo "SpiderFoot ready"
    exit 0
  fi
  sleep 1
done

echo "WARNING: SpiderFoot did not respond on /ping within 30s — check ${SF_DATA}/spiderfoot.log"
