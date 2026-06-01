#!/usr/bin/env python3
"""Print SCWEET_AUTH_TOKEN from local session cache for Render env setup."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / "data" / "scweet_session.json"


def main() -> int:
    cache_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CACHE
    if not cache_path.is_file():
        print(f"Session cache not found: {cache_path}")
        print("Run: python scripts/scweet_login.py --refresh")
        return 1

    session = json.loads(cache_path.read_text(encoding="utf-8"))
    token = str(session.get("auth_token") or "").strip()
    if not token:
        print("No auth_token in session cache. Run login again.")
        return 1

    expires = session.get("expires_at", "unknown")
    print("Add these environment variables on Render (both API + dashboard services):\n")
    print(f"SCWEET_ENABLED=true")
    print(f"SCWEET_AUTH_TOKEN={token}")
    print("SCWEET_AUTO_LOGIN=false")
    print(f"\nSession cached at: {expires} (refresh locally when Scweet auth fails)")
    print("\nRender path: Dashboard → karakorum-analytica-dashboard → Environment → Add variable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
