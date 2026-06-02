#!/usr/bin/env python3
"""Sync Buffer API env vars to Render (never commits BUFFER_API_KEY)."""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sync_scweet_token_to_render import (  # noqa: E402
    get_render_api_key,
    load_env,
    trigger_render_deploy,
    update_render_env_var,
)

API_SERVICE_ID = "srv-d8ec0pkm0tmc73enljm0"
DASHBOARD_SERVICE_ID = "srv-d8ec274m0tmc73enmdbg"

SYNC_KEYS = (
    "BUFFER_API_KEY",
    "BUFFER_CHANNEL_HANDLE",
    "BUFFER_CHANNEL_ID",
    "BUFFER_TEST_SECRET",
    "BUFFER_AUTO_SEND_ON_APPROVE",
)

# Remove legacy Zapier vars from Render when syncing
REMOVE_KEYS = ("ZAPIER_BUFFER_WEBHOOK_URL",)


def _ensure_test_secret() -> None:
    if os.environ.get("BUFFER_TEST_SECRET", "").strip():
        return
    secret = secrets.token_urlsafe(32)
    os.environ["BUFFER_TEST_SECRET"] = secret
    env_path = ROOT / ".env"
    text = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
    line = f"BUFFER_TEST_SECRET={secret}\n"
    if "BUFFER_TEST_SECRET=" in text:
        out = []
        for ln in text.splitlines(keepends=True):
            out.append(line if ln.startswith("BUFFER_TEST_SECRET=") else ln)
        env_path.write_text("".join(out), encoding="utf-8")
    else:
        with env_path.open("a", encoding="utf-8") as f:
            if text and not text.endswith("\n"):
                f.write("\n")
            f.write(line)


def _set_buffer_api_key_in_env(api_key: str) -> None:
    env_path = ROOT / ".env"
    text = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
    line = f"BUFFER_API_KEY={api_key}\n"
    if "BUFFER_API_KEY=" in text:
        out = []
        for ln in text.splitlines(keepends=True):
            if ln.startswith("BUFFER_API_KEY="):
                out.append(line)
            elif ln.startswith("ZAPIER_BUFFER_WEBHOOK_URL="):
                continue
            else:
                out.append(ln)
        env_path.write_text("".join(out), encoding="utf-8")
    else:
        with env_path.open("a", encoding="utf-8") as f:
            if text and not text.endswith("\n"):
                f.write("\n")
            f.write(line)


def sync_buffer_env_to_render(*, deploy: bool = False, service_id: str = API_SERVICE_ID) -> list[str]:
    load_env()
    api_key_render = get_render_api_key()

    if not os.environ.get("BUFFER_API_KEY", "").strip():
        raise RuntimeError("BUFFER_API_KEY is not set in .env")

    _ensure_test_secret()
    os.environ.setdefault("BUFFER_CHANNEL_HANDLE", "@kkanalytica")
    os.environ.setdefault("BUFFER_AUTO_SEND_ON_APPROVE", "true")

    updated: list[str] = []
    for key in SYNC_KEYS:
        value = os.environ.get(key, "").strip()
        if not value:
            continue
        update_render_env_var(api_key_render, service_id, key, value)
        updated.append(key)

    for legacy in REMOVE_KEYS:
        try:
            update_render_env_var(api_key_render, service_id, legacy, "")
        except Exception:
            pass

    secret = os.environ.get("BUFFER_TEST_SECRET", "").strip()
    if secret:
        update_render_env_var(api_key_render, DASHBOARD_SERVICE_ID, "BUFFER_TEST_SECRET", secret)

    if deploy:
        trigger_render_deploy(api_key_render, service_id)
        trigger_render_deploy(api_key_render, DASHBOARD_SERVICE_ID)

    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Buffer API env to Render")
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument("--set-api-key", metavar="KEY", help="Set BUFFER_API_KEY in local .env only")
    args = parser.parse_args()

    if args.set_api_key:
        _set_buffer_api_key_in_env(args.set_api_key.strip())
        print("SUCCESS: BUFFER_API_KEY saved to local .env (not committed)")

    try:
        keys = sync_buffer_env_to_render(deploy=args.deploy)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("SUCCESS: synced to Render API:", ", ".join(keys))
    if args.deploy:
        print("  Deploy: triggered for API + dashboard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
