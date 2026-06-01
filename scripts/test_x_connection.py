#!/usr/bin/env python3
"""Test X (Twitter) API connection using credentials in .env."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from app.config import get_settings
from app.integrations.x_client import check_x_connection


def main() -> int:
    settings = get_settings()
    print(f"X configured: {settings.x_configured}")
    print(f"X OAuth (can post): {settings.x_oauth_configured}")
    print(f"X posting enabled: {settings.x_posting_enabled}")
    print()

    if not settings.x_configured:
        print("Add credentials to .env — see .env.example (X API section).")
        print("Get keys: https://developer.x.com/en/portal/dashboard")
        return 1

    result = check_x_connection()
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
