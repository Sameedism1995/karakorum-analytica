#!/usr/bin/env python3
"""Apply supabase/migrations/*.sql to the configured Postgres database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def _split_sql(sql: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") and not buffer:
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statement = "\n".join(buffer).strip()
            buffer = []
            if statement and statement != ";":
                statements.append(statement)
    trailing = "\n".join(buffer).strip()
    if trailing:
        statements.append(trailing)
    return statements


def apply_migrations(database_url: str, *, dry_run: bool = False) -> int:
    from sqlalchemy import create_engine, text

    from app.config import Settings

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print(f"No migration files in {MIGRATIONS_DIR}")
        return 1

    url = Settings._normalize_postgres_url(database_url)
    if dry_run:
        print(f"Would apply {len(files)} migration(s) to {url.split('@')[-1]}")
        for path in files:
            print(f"  • {path.name}")
        return 0

    engine = create_engine(url, pool_pre_ping=True)
    applied = 0
    with engine.begin() as conn:
        for path in files:
            sql = path.read_text(encoding="utf-8")
            statements = _split_sql(sql)
            for statement in statements:
                conn.execute(text(statement))
            applied += 1
            print(f"Applied {path.name} ({len(statements)} statement(s))")

    print(f"Done — {applied} migration file(s) applied.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Supabase SQL migrations")
    parser.add_argument("--dry-run", action="store_true", help="List migrations without executing")
    args = parser.parse_args()

    from app.config import get_settings

    settings = get_settings()
    if not settings.effective_database_url.startswith("postgresql"):
        print("Set SUPABASE_DB_URL (or DATABASE_URL) to a Postgres connection string.")
        return 1

    return apply_migrations(settings.effective_database_url, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
