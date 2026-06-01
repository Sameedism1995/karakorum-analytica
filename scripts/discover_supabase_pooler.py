#!/usr/bin/env python3
"""Discover Supabase IPv4 pooler URL and optionally write to .env / sync Render."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus, unquote_plus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

REGIONS = [
    "us-west-1",
    "us-west-2",
    "us-east-1",
    "us-east-2",
    "ca-central-1",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-central-1",
    "eu-central-2",
    "eu-north-1",
    "ap-south-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ap-northeast-2",
    "sa-east-1",
]
PREFIXES = ("aws-1", "aws-0")
PORTS = (5432, 6543)


def _parse_direct_url(raw: str) -> tuple[str, str]:
    match = re.match(
        r"postgresql(?:\+psycopg)?://postgres:([^@]+)@db\.([^.]+)\.supabase\.co:5432/postgres",
        raw.strip(),
    )
    if not match:
        raise ValueError("SUPABASE_DB_URL must be a direct Supabase URI (postgres@db.*.supabase.co:5432)")
    return unquote_plus(match.group(1)), match.group(2)


def discover_pooler(*, password: str, project_ref: str) -> dict[str, str | int]:
    import psycopg

    user = f"postgres.{project_ref}"
    for prefix in PREFIXES:
        for region in REGIONS:
            host = f"{prefix}-{region}.pooler.supabase.com"
            for port in PORTS:
                try:
                    with psycopg.connect(
                        host=host,
                        port=port,
                        dbname="postgres",
                        user=user,
                        password=password,
                        sslmode="require",
                        connect_timeout=6,
                    ) as conn:
                        conn.execute("SELECT 1")
                    return {
                        "host": host,
                        "port": port,
                        "region": region,
                        "prefix": prefix,
                        "user": user,
                    }
                except Exception as exc:
                    err = str(exc)
                    if "Tenant or user not found" in err or "tenant/user" in err.lower():
                        continue
                    if "password authentication failed" in err.lower():
                        raise RuntimeError(
                            f"Pooler host {host}:{port} matched project region but password auth failed"
                        ) from exc
    raise RuntimeError("Could not find Supabase pooler region — paste Session pooler URL from dashboard")


def build_pooler_url(password: str, project_ref: str, host: str, port: int) -> str:
    user = f"postgres.{project_ref}"
    return f"postgresql://{user}:{quote_plus(password)}@{host}:{port}/postgres"


def _upsert_env(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    out: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    if load_dotenv:
        load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description="Discover Supabase pooler URL for Render (IPv4)")
    parser.add_argument("--write-env", action="store_true", help="Write SUPABASE_DB_POOLER_URL to .env")
    parser.add_argument("--deploy", action="store_true", help="Sync env to Render after discovery")
    parser.add_argument("--pooler-url", help="Skip discovery; test and use this Session/Transaction pooler URL")
    args = parser.parse_args()

    direct = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not direct:
        print("ERROR: SUPABASE_DB_URL is not set", file=sys.stderr)
        return 1

    password, project_ref = _parse_direct_url(direct)

    if args.pooler_url:
        import psycopg

        url = args.pooler_url.strip()
        with psycopg.connect(url.replace("postgresql://", "postgresql://")) as conn:
            conn.execute("SELECT 1")
        pooler_url = url
        meta = {"source": "manual"}
    else:
        found = discover_pooler(password=password, project_ref=project_ref)
        pooler_url = build_pooler_url(password, project_ref, found["host"], int(found["port"]))
        meta = found

    print("SUCCESS: pooler reachable")
    print(f"  host: {meta.get('host', 'manual')}")
    print(f"  port: {meta.get('port', 'manual')}")
    print(f"  region: {meta.get('region', 'n/a')}")
    print(f"  prefix: {meta.get('prefix', 'n/a')}")

    if args.write_env:
        env_path = ROOT / ".env"
        _upsert_env(env_path, "SUPABASE_DB_POOLER_URL", pooler_url)
        if meta.get("region"):
            _upsert_env(env_path, "SUPABASE_POOLER_REGION", str(meta["region"]))
        print(f"  wrote: {env_path}")

    if args.deploy:
        if load_dotenv:
            load_dotenv(ROOT / ".env", override=True)
        os.environ["SUPABASE_DB_POOLER_URL"] = pooler_url
        if meta.get("region"):
            os.environ["SUPABASE_POOLER_REGION"] = str(meta["region"])
        from scripts.sync_render_env import sync_env_to_render

        keys = sync_env_to_render(deploy=True)
        print("  synced Render keys:", ", ".join(keys))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
