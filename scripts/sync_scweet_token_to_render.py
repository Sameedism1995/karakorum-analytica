#!/usr/bin/env python3
"""Refresh Scweet auth token locally and sync SCWEET_AUTH_TOKEN to Render."""

from __future__ import annotations

import argparse
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
from app.integrations.scweet_token_sync import run_sync


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh X/Scweet session and push SCWEET_AUTH_TOKEN to Render"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force Playwright login even if cached session is valid",
    )
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Only refresh local .env / session cache",
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Trigger a Render redeploy after updating env vars",
    )
    parser.add_argument(
        "--if-expiring-within",
        type=float,
        default=2.0,
        metavar="HOURS",
        help="Refresh when session expires within this many hours (default: 2)",
    )
    parser.add_argument(
        "--always-refresh",
        action="store_true",
        help="Same as --refresh (for cron: always login and sync)",
    )
    parser.add_argument(
        "--no-local-env",
        action="store_true",
        help="Do not write SCWEET_AUTH_TOKEN to .env (for CI)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    get_settings.cache_clear()

    force = args.refresh or args.always_refresh
    try:
        result = run_sync(
            force_refresh=force,
            if_expiring_within_hours=None if force else args.if_expiring_within,
            skip_render=args.skip_render,
            deploy=args.deploy,
            update_env=not args.no_local_env,
        )
    except Exception as exc:
        print(f"Sync failed: {exc}")
        return 1

    print(json.dumps({k: v for k, v in result.items() if k != "token_length"}, indent=2))
    if result.get("render_skipped") and result.get("render_note"):
        print(result["render_note"])
    elif result.get("render_services"):
        print(f"Synced to Render: {', '.join(result['render_services'])}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
