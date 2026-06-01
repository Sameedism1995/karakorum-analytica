#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../llm-dashboard"
npm install
npm run build
echo "Built LLM dashboard → llm-dashboard/dist (served at /llm when API runs)"
