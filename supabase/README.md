# Supabase — Karakorum Analytica

PostgreSQL schema for raw news, incidents, draft posts, and posted items.

## Tables

| Table | Purpose |
|-------|---------|
| `sources` | Registered feeds (GDELT, ReliefWeb, ACLED, X/Scweet) |
| `raw_news` | Collected articles/tweets before grouping |
| `incidents` | Grouped security events with confidence scores |
| `draft_posts` | X drafts awaiting human review |
| `posted_items` | Audit log of published posts |

## Migrations

Ordered SQL files in `supabase/migrations/`:

| Migration | Description |
|-----------|-------------|
| `20260601000000_create_core_tables.sql` | All tables + comments |
| `20260601000001_create_indexes.sql` | Lookup and dashboard indexes |
| `20260601000002_grants_and_rls.sql` | Role grants (RLS off by default) |
| `20260601000003_seed_sources.sql` | Default source rows (idempotent) |

## Apply to Supabase

### Option A — Supabase CLI (recommended)

```bash
# Install: https://supabase.com/docs/guides/cli
supabase login
supabase link --project-ref YOUR_PROJECT_REF

# Push migrations to remote
supabase db push

# Or reset local linked DB (runs migrations + seed.sql)
supabase db reset
```

### Option B — Python setup script

```bash
# Uses SQLAlchemy create_all + optional SQL apply
python scripts/setup_supabase.py

# Apply migration SQL files directly via Postgres
python scripts/setup_supabase.py --apply-migrations
```

### Option C — SQL Editor

Paste and run `supabase/schema.sql` in the Supabase dashboard SQL Editor.

## Environment variables

```
SUPABASE_URL=https://YOUR_REF.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_DB_URL=postgresql://postgres:PASSWORD@db.YOUR_REF.supabase.co:5432/postgres
```

Set the same vars on Render (`karakorum-analytica-api`) for persistent production data.

## Seed data

`supabase/seed.sql` mirrors `20260601000003_seed_sources.sql` and runs on `supabase db reset`.
