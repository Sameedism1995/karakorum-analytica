#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Starting FastAPI on :8000 and Vite dev server on :5173"
echo "Open http://localhost:5173/llm/"

(
  source venv/bin/activate 2>/dev/null || true
  uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
API_PID=$!

cd llm-dashboard
npm install
npm run dev &
VITE_PID=$!

trap 'kill $API_PID $VITE_PID 2>/dev/null' EXIT
wait
