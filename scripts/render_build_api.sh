#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

git submodule update --init --recursive
pip install -r requirements-api.txt
bash scripts/install_playwright.sh
