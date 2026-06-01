#!/usr/bin/env python3
"""
Push Supabase (and optional) env vars from local .env to Render services.

Requires in .env:
  RENDER_API_KEY=rnd_...
  RENDER_SERVICE_IDS=srv-api,srv-dashboard
  SUPABASE_DB_URL=postgresql://...
  SUPABASE_URL=https://xxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY=...
  SUPABASE_BUCKET_NAME=karakorum-osint-media  (optional)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sync_scweet_token_to_render import (  # noqa: E402
    get_render_api_key,
    get_render_service_ids,
    load_env,
    trigger_render_deploy,
    update_render_env_var,
)

SYNC_KEYS = (
    "SUPABASE_DB_URL",
    "SUPABASE_DB_POOLER_URL",
    "SUPABASE_POOLER_REGION",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_BUCKET_NAME",
)


def sync_env_to_render(*, deploy: bool = False) -> list[str]:
    api_key = get_render_api_key()
    service_ids = get_render_service_ids()
    updated: list[str] = []

    for key in SYNC_KEYS:
        value = os.environ.get(key, "").strip()
        if not value:
            continue
        for service_id in service_ids:
            update_render_env_var(api_key, service_id, key, value)
        updated.append(key)

    if deploy:
        for service_id in service_ids:
            trigger_render_deploy(api_key, service_id)

    return updated


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Sync Supabase env vars to Render")
    parser.add_argument("--deploy", action="store_true", help="Trigger redeploy after sync")
    args = parser.parse_args()

    if not os.environ.get("SUPABASE_DB_URL", "").strip():
        print("ERROR: SUPABASE_DB_URL is not set in .env", file=sys.stderr)
        return 1

    try:
        keys = sync_env_to_render(deploy=args.deploy)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not keys:
        print("ERROR: No Supabase variables found in .env to sync.", file=sys.stderr)
        return 1

    print("SUCCESS: synced to Render:", ", ".join(keys))
    if args.deploy:
        print("  Deploy: triggered for each service")
    print("  Also run: python scripts/sync_scweet_token_to_render.py --deploy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
