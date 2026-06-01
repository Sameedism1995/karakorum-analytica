#!/usr/bin/env python3
"""Initialize Karakorum Analytica tables on Supabase PostgreSQL.

Usage:
  1. Create a project at https://supabase.com
  2. Copy credentials into .env (see .env.example)
  3. Run:  python scripts/setup_supabase.py

Or pass credentials once (not saved):
  python scripts/setup_supabase.py \\
    --supabase-url https://YOUR_REF.supabase.co \\
    --service-role-key eyJ... \\
    --db-url 'postgresql://postgres:PASSWORD@db.YOUR_REF.supabase.co:5432/postgres'
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SETUP_STEPS = """
Supabase setup checklist
------------------------
1. Go to https://supabase.com/dashboard and create a project (or open an existing one).
2. Project Settings → Database → Connection string → URI (Direct connection, port 5432)
   → set SUPABASE_DB_URL in .env
3. Project Settings → API
   → Project URL  → SUPABASE_URL
   → service_role secret → SUPABASE_SERVICE_ROLE_KEY  (backend only, never in frontend)
4. Run this script again:  python scripts/setup_supabase.py
5. On Render: add the same three env vars to karakorum-analytica-api → Environment → redeploy.

Optional: run supabase/schema.sql in Supabase → SQL Editor instead of this script.
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize Supabase database for Karakorum Analytica")
    parser.add_argument("--supabase-url", help="https://YOUR_REF.supabase.co")
    parser.add_argument("--service-role-key", help="Supabase service_role JWT")
    parser.add_argument("--db-url", help="Postgres URI (direct connection, port 5432)")
    parser.add_argument("--db-password", help="Database password (uses SUPABASE_URL to build URI)")
    parser.add_argument(
        "--apply-sql",
        action="store_true",
        help="Also run supabase/schema.sql via psycopg (tables are created by bootstrap by default)",
    )
    return parser.parse_args()


def _apply_env_overrides(args: argparse.Namespace) -> None:
    if args.supabase_url:
        os.environ["SUPABASE_URL"] = args.supabase_url.strip()
    if args.service_role_key:
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = args.service_role_key.strip()
    if args.db_url:
        os.environ["SUPABASE_DB_URL"] = args.db_url.strip()
    if args.db_password:
        os.environ["SUPABASE_DB_PASSWORD"] = args.db_password.strip()


def _validate_env() -> list[str]:
    errors: list[str] = []
    if not os.getenv("SUPABASE_URL", "").strip():
        errors.append("SUPABASE_URL is missing")
    if not os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip():
        errors.append("SUPABASE_SERVICE_ROLE_KEY is missing")
    has_db_url = bool(os.getenv("SUPABASE_DB_URL", "").strip())
    has_db_password = bool(os.getenv("SUPABASE_DB_PASSWORD", "").strip()) and bool(
        os.getenv("SUPABASE_URL", "").strip()
    )
    if not has_db_url and not has_db_password:
        errors.append("SUPABASE_DB_URL or SUPABASE_DB_PASSWORD is missing")
    return errors


def _apply_schema_sql(database_url: str) -> None:
    schema_path = ROOT / "supabase" / "schema.sql"
    if not schema_path.is_file():
        print(f"Schema file not found: {schema_path}")
        return

    from sqlalchemy import create_engine, text

    from app.config import Settings

    url = Settings._normalize_postgres_url(database_url)
    engine = create_engine(url, pool_pre_ping=True)
    sql = schema_path.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    print(f"Applied {len(statements)} statements from {schema_path.name}")


def main() -> int:
    args = _parse_args()
    _apply_env_overrides(args)

    errors = _validate_env()
    if errors:
        print("Cannot connect to Supabase yet:\n")
        for err in errors:
            print(f"  • {err}")
        print(SETUP_STEPS)
        return 1

    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    print(f"Target database: {settings.database_backend}")
    if settings.using_supabase:
        print(f"Supabase project: {settings.supabase_project_ref or '(from DB URL)'}")
    print(f"Connection host: {settings.effective_database_url.split('@')[-1]}")

    from app.database import check_database_connection, reconfigure_engine

    reconfigure_engine()
    db_status = check_database_connection()
    if not db_status.get("ok"):
        print(f"\nDatabase connection failed: {db_status.get('error')}")
        print("\nTips:")
        print("  • Use the Direct connection URI (db.PROJECT_REF.supabase.co:5432)")
        print("  • URL-encode special characters in the password (@ → %40, : → %3A)")
        print("  • Supabase may pause free-tier projects — open the dashboard to wake it")
        return 1

    print("Database connection: OK")

    if args.apply_sql:
        _apply_schema_sql(settings.effective_database_url)

    from app.bootstrap import bootstrap_database

    bootstrap_database()
    print("Tables created / verified and default sources seeded.")

    from app.database import SessionLocal
    from app.integrations.supabase_client import check_supabase_api, check_supabase_storage
    from app.services.stats_service import get_dashboard_stats

    db = SessionLocal()
    try:
        stats = get_dashboard_stats(db)
        print("\nRow counts:")
        print(f"  raw_news:   {stats['total_raw']}")
        print(f"  incidents:  {stats['total_incidents']}")
        print(f"  drafts:     {stats['total_drafts']}")
        print(f"  sources:    {stats['sources_active']} active feed(s)")
    finally:
        db.close()

    api_status = check_supabase_api()
    if api_status.get("ok"):
        print(f"\nSupabase REST API: OK (sources table reachable, count={api_status.get('sources_count')})")
    else:
        print(f"\nSupabase REST API: {api_status.get('error', 'unavailable')}")
        print("  (Data still persists via Postgres; REST is used for health checks only.)")

    storage_status = check_supabase_storage()
    if storage_status.get("ok"):
        print(f"Supabase table counts via REST: {storage_status.get('counts')}")

    print("\nDone. Next steps:")
    print("  • Local: keep SUPABASE_* vars in .env and restart the API")
    print("  • Render: set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_DB_URL on the API service")
    print("  • Run collection: POST /collect/run or dashboard → Run Collection Now")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
