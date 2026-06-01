#!/usr/bin/env python3
"""
Local-only sync: read Scweet auth token from data/scweet_state.db and push to Render.

No GitHub Actions, no Playwright — runs on your machine only.

Requires in .env (or environment):
  RENDER_API_KEY=rnd_...
  RENDER_SERVICE_ID=srv-...              # single service
  # or RENDER_SERVICE_IDS=srv-a,srv-b    # API + dashboard

Optional:
  SCWEET_DB_PATH=data/scweet_state.db

Usage:
  python scripts/sync_scweet_token_to_render.py
  python scripts/sync_scweet_token_to_render.py --deploy
  python scripts/sync_scweet_token_to_render.py --db-path data/scweet_state.db
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "scweet_state.db"
RENDER_API_BASE = "https://api.render.com/v1"


def load_env() -> None:
    env_file = ROOT / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(env_file)
    except ImportError:
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def _token_from_cookies_json(raw: str) -> str | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(data, dict):
        token = str(data.get("auth_token") or "").strip()
        return token or None
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("name") == "auth_token":
                value = str(item.get("value") or "").strip()
                if value:
                    return value
    return None


def extract_auth_token_from_db(db_path: Path) -> tuple[str, str]:
    """
    Read the most recently used Scweet account auth token from SQLite.

    Returns (token, username).
    """
    if not db_path.is_file():
        raise FileNotFoundError(
            f"Scweet database not found: {db_path}\n"
            "Log in locally first (python scripts/scweet_login.py) so Scweet can populate the DB."
        )

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT username, auth_token, cookies_json
                FROM accounts
                WHERE (auth_token IS NOT NULL AND TRIM(auth_token) != '')
                   OR (cookies_json IS NOT NULL AND TRIM(cookies_json) != '')
                ORDER BY last_used DESC, id DESC
                LIMIT 10
                """
            ).fetchall()
        except sqlite3.OperationalError as exc:
            raise RuntimeError(
                f"Could not read accounts table from {db_path}: {exc}"
            ) from exc
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise RuntimeError(f"SQLite error reading {db_path}: {exc}") from exc

    if not rows:
        raise RuntimeError(
            f"No accounts with auth tokens in {db_path}.\n"
            "Run a local Scweet login/search first to populate credentials."
        )

    for row in rows:
        username = str(row["username"] or "unknown")
        direct = (row["auth_token"] or "").strip()
        if direct:
            return direct, username
        cookies_raw = row["cookies_json"]
        if cookies_raw:
            from_json = _token_from_cookies_json(str(cookies_raw))
            if from_json:
                return from_json, username

    raise RuntimeError(f"Accounts exist in {db_path} but no auth_token could be extracted.")


def get_render_api_key() -> str:
    key = os.environ.get("RENDER_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "RENDER_API_KEY is not set. Add it to .env "
            "(https://dashboard.render.com/u/settings#api-keys)."
        )
    return key


def get_render_service_ids() -> list[str]:
    """Resolve Render service ID(s) from environment."""
    raw = (
        os.environ.get("RENDER_SERVICE_IDS", "").strip()
        or os.environ.get("RENDER_SCWEET_SERVICE_IDS", "").strip()
        or os.environ.get("RENDER_SERVICE_ID", "").strip()
    )
    if not raw:
        raise RuntimeError(
            "No Render service ID configured. Set RENDER_SERVICE_ID or "
            "RENDER_SERVICE_IDS (comma-separated) in .env."
        )
    ids = [part.strip() for part in raw.replace("\n", ",").split(",") if part.strip()]
    if not ids:
        raise RuntimeError("RENDER_SERVICE_ID(S) is empty after parsing.")
    return ids


def render_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def update_render_env_var(api_key: str, service_id: str, key: str, value: str) -> None:
    """PUT /v1/services/{service_id}/env-vars/{key}"""
    url = f"{RENDER_API_BASE}/services/{service_id}/env-vars/{key}"
    try:
        response = requests.put(
            url,
            headers=render_headers(api_key),
            json={"value": value},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error updating {key} on {service_id}: {exc}") from exc

    if response.status_code >= 400:
        raise RuntimeError(
            f"Render API error updating {key} on {service_id} "
            f"({response.status_code}): {response.text}"
        )


def trigger_render_deploy(api_key: str, service_id: str) -> None:
    url = f"{RENDER_API_BASE}/services/{service_id}/deploys"
    try:
        response = requests.post(
            url,
            headers=render_headers(api_key),
            json={},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error triggering deploy for {service_id}: {exc}") from exc

    if response.status_code >= 400:
        raise RuntimeError(
            f"Render deploy failed for {service_id} ({response.status_code}): {response.text}"
        )


def sync_token_to_render_services(
    token: str,
    *,
    api_key: str,
    service_ids: list[str],
    deploy: bool = False,
) -> list[str]:
    """Push SCWEET_AUTH_TOKEN (and related flags) to each Render service."""
    updated: list[str] = []
    for service_id in service_ids:
        update_render_env_var(api_key, service_id, "SCWEET_AUTH_TOKEN", token)
        update_render_env_var(api_key, service_id, "SCWEET_AUTO_LOGIN", "false")
        update_render_env_var(api_key, service_id, "SCWEET_ENABLED", "true")
        updated.append(service_id)
        if deploy:
            trigger_render_deploy(api_key, service_id)
    return updated


def write_local_env(token: str) -> None:
    """Optional: mirror token into local .env for consistency."""
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    text = env_path.read_text(encoding="utf-8")
    import re

    if re.search(r"^SCWEET_AUTH_TOKEN=", text, flags=re.M):
        text = re.sub(r"^SCWEET_AUTH_TOKEN=.*$", f"SCWEET_AUTH_TOKEN={token}", text, flags=re.M)
    else:
        text = text.rstrip() + f"\nSCWEET_AUTH_TOKEN={token}\n"
    text = re.sub(r"^SCWEET_AUTO_LOGIN=.*$", "SCWEET_AUTO_LOGIN=false", text, flags=re.M)
    env_path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync SCWEET_AUTH_TOKEN from local Scweet SQLite DB to Render (local only)"
    )
    parser.add_argument(
        "--db-path",
        default=os.environ.get("SCWEET_DB_PATH", str(DEFAULT_DB)),
        help=f"Path to Scweet SQLite DB (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Trigger a Render redeploy after updating env vars",
    )
    parser.add_argument(
        "--write-env",
        action="store_true",
        help="Also write SCWEET_AUTH_TOKEN to local .env",
    )
    return parser.parse_args()


def main() -> int:
    load_env()
    args = parse_args()
    db_path = Path(args.db_path)

    try:
        api_key = get_render_api_key()
        service_ids = get_render_service_ids()
        token, username = extract_auth_token_from_db(db_path)

        if args.write_env:
            write_local_env(token)

        synced = sync_token_to_render_services(
            token,
            api_key=api_key,
            service_ids=service_ids,
            deploy=args.deploy,
        )
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: Unexpected failure: {exc}", file=sys.stderr)
        return 1

    print("SUCCESS: SCWEET_AUTH_TOKEN synced to Render.")
    print(f"  Source DB:     {db_path}")
    print(f"  Account:       {username}")
    print(f"  Token length:  {len(token)} chars")
    print(f"  Render services: {', '.join(synced)}")
    if args.deploy:
        print("  Deploy:        triggered for each service")
    if args.write_env:
        print("  Local .env:    updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
