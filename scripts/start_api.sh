#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
python -m playwright install chromium 2>/dev/null || true
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
