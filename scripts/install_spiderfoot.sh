#!/usr/bin/env bash
# Clone SpiderFoot (if missing) and install Python dependencies.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SF_DIR="${SPIDERFOOT_DIR:-third_party/spiderfoot}"

if [ ! -f "$SF_DIR/sf.py" ]; then
  echo "Cloning SpiderFoot into $SF_DIR ..."
  mkdir -p "$(dirname "$SF_DIR")"
  git clone --depth 1 https://github.com/smicallef/spiderfoot.git "$SF_DIR"
fi

if [ -f "$SF_DIR/requirements.txt" ]; then
  pip install -r "$SF_DIR/requirements.txt"
fi

echo "SpiderFoot installed at $SF_DIR"
