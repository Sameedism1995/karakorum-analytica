#!/usr/bin/env bash
# Install a macOS/Linux cron job to refresh Scweet token every 10 hours.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${ROOT}/venv/bin/python"
SCRIPT="${ROOT}/scripts/sync_scweet_token_to_render.py"
LOG_DIR="${ROOT}/logs"
LOG_FILE="${LOG_DIR}/scweet-token-sync.log"

if [ ! -x "${PYTHON}" ]; then
  PYTHON="$(command -v python3)"
fi

mkdir -p "${LOG_DIR}"

CRON_LINE="0 */10 * * * cd ${ROOT} && ${PYTHON} ${SCRIPT} --deploy --write-env >> ${LOG_FILE} 2>&1"

if (crontab -l 2>/dev/null || true) | grep -F "${SCRIPT}" >/dev/null; then
  echo "Cron job already installed for sync_scweet_token_to_render.py"
else
  ((crontab -l 2>/dev/null || true); echo "${CRON_LINE}") | crontab -
  echo "Installed cron job (every 10 hours):"
  echo "${CRON_LINE}"
fi

echo ""
echo "Requirements in ${ROOT}/.env:"
echo "  RENDER_API_KEY=rnd_..."
echo "  RENDER_SERVICE_IDS=srv-...,srv-...   # or RENDER_SERVICE_ID for one service"
echo "  data/scweet_state.db populated by local Scweet login"
echo ""
echo "Logs: ${LOG_FILE}"
