#!/usr/bin/env python3
"""Print SCWEET_AUTH_TOKEN from local session cache for Render env setup."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from app.integrations.scweet_token_sync import read_cached_session, run_sync


def main() -> int:
    if "--sync" in sys.argv:
        from app.config import get_settings

        get_settings.cache_clear()
        result = run_sync(force_refresh="--refresh" in sys.argv, deploy="--deploy" in sys.argv)
        if not result.get("ok"):
            return 1
        print("Synced. See output above.")
        return 0

    session = read_cached_session()
    if not session:
        print("Session cache not found. Run: python scripts/sync_scweet_token_to_render.py --refresh")
        return 1

    token = str(session.get("auth_token") or "").strip()
    if not token:
        print("No auth_token in session cache.")
        return 1

    expires = session.get("expires_at", "unknown")
    print("Add these environment variables on Render (both API + dashboard services):\n")
    print("SCWEET_ENABLED=true")
    print(f"SCWEET_AUTH_TOKEN={token}")
    print("SCWEET_AUTO_LOGIN=false")
    print(f"\nSession expires: {expires}")
    print("\nAutomate with:")
    print("  python scripts/sync_scweet_token_to_render.py --refresh")
    print("  bash scripts/install_scweet_token_cron.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
