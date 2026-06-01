#!/usr/bin/env bash
# Install Playwright Python package + Chromium browser (local and Render).
set -euo pipefail
cd "$(dirname "$0")/.."

python -m pip install playwright
python -m playwright install chromium --with-deps 2>/dev/null \
  || python -m playwright install chromium
