#!/usr/bin/env python3
"""Initialize database and seed API sources."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.bootstrap import bootstrap_database
from app.config import get_settings


def main() -> None:
    settings = get_settings()
    print(f"Database backend: {settings.database_backend}")
    if settings.using_supabase:
        print(f"Supabase project: {settings.supabase_project_ref or 'configured'}")
    bootstrap_database()
    print("Database bootstrap complete.")


if __name__ == "__main__":
    main()
