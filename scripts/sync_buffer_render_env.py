#!/usr/bin/env python3
"""Sync Buffer/Zapier env vars to Render API service and optionally redeploy."""

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

BUFFER_KEYS = (
    "ZAPIER_BUFFER_WEBHOOK_URL",
    "BUFFER_TEST_SECRET",
    "BUFFER_VALIDATION_STRICT",
    "BUFFER_AUTO_SEND_ON_APPROVE",
)


def _ensure_local_secret() -> str:
    env_path = ROOT / ".env"
    text = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
    for line in text.splitlines():
        if line.startswith("BUFFER_TEST_SECRET=") and line.split("=", 1)[1].strip():
            return line.split("=", 1)[1].strip()
    secret = secrets.token_urlsafe(32)
    line = f"BUFFER_TEST_SECRET={secret}\n"
    if "BUFFER_TEST_SECRET=" in text:
        out = []
        for ln in text.splitlines(keepends=True):
            if ln.startswith("BUFFER_TEST_SECRET="):
                out.append(line)
            else:
                out.append(ln)
        env_path.write_text("".join(out), encoding="utf-8")
    else:
        with env_path.open("a", encoding="utf-8") as f:
            if text and not text.endswith("\n"):
                f.write("\n")
            f.write(line)
    os.environ["BUFFER_TEST_SECRET"] = secret
    return secret


def sync_buffer_env_to_render(*, deploy: bool = False, service_id: str = API_SERVICE_ID) -> list[str]:
    load_env()
    api_key = get_render_api_key()

    if not os.environ.get("ZAPIER_BUFFER_WEBHOOK_URL", "").strip():
        raise RuntimeError("ZAPIER_BUFFER_WEBHOOK_URL is not set in .env")

    if not os.environ.get("BUFFER_TEST_SECRET", "").strip():
        _ensure_local_secret()

    defaults = {
        "BUFFER_VALIDATION_STRICT": "false",
        "BUFFER_AUTO_SEND_ON_APPROVE": "true",
    }

    updated: list[str] = []
    for key in BUFFER_KEYS:
        value = os.environ.get(key, "").strip() or defaults.get(key, "")
        if not value:
            continue
        update_render_env_var(api_key, service_id, key, value)
        updated.append(key)

    if deploy:
        trigger_render_deploy(api_key, service_id)
        if service_id == API_SERVICE_ID:
            secret = os.environ.get("BUFFER_TEST_SECRET", "").strip()
            if secret:
                update_render_env_var(api_key, DASHBOARD_SERVICE_ID, "BUFFER_TEST_SECRET", secret)
                trigger_render_deploy(api_key, DASHBOARD_SERVICE_ID)

    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Buffer/Zapier env to Render API")
    parser.add_argument("--deploy", action="store_true", help="Redeploy API after sync")
    parser.add_argument("--service-id", default=API_SERVICE_ID)
    args = parser.parse_args()

    try:
        keys = sync_buffer_env_to_render(deploy=args.deploy, service_id=args.service_id)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("SUCCESS: synced to Render API:", ", ".join(keys))
    if args.deploy:
        print("  Deploy: triggered")
    print("  Posting mode: relaxed validation + auto-send on approve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
