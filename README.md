# KarakorumAnalytica

Phase 1 backend for collecting public Pakistan-focused crime, conflict, and security news from open APIs, grouping incidents, scoring source confidence, and generating neutral X/Twitter draft posts for human review.

**No ML. No X scraping. No auto-posting by default.**

## What it does

1. Collects public reports from **GDELT**, **ReliefWeb**, and optionally **ACLED**
2. Filters for **Pakistan** and security-related keywords
3. Extracts keywords and detects province/city
4. Groups similar reports into **incidents** (rule-based matching)
5. Scores **confidence** by how many APIs reported the same incident
6. Generates **neutral draft posts** (never auto-published in Phase 1)

## Confidence scoring

Each API has equal weight (**33.33%**):

| Sources matched | Score | Incident status |
|-----------------|-------|-----------------|
| 1 | 33.33 | `save_only` |
| 2 | 66.66 | `needs_review` |
| 3 | 100.00 | `ready_for_review` |

Even `ready_for_review` drafts are **not auto-posted**. A human must approve, and posting requires `X_POSTING_ENABLED=true`.

## Install

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/init_db.py
```

## Supabase (persistent storage)

By default data is stored in local SQLite (`local.db`). For production or shared deploys, use **Supabase PostgreSQL** so raw news, incidents, and drafts persist in the cloud.

### Setup

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **Project Settings → Database** and copy the **Connection string** (URI)
3. Go to **Project Settings → API** and copy:
   - **Project URL** → `SUPABASE_URL`
   - **service_role** key → `SUPABASE_SERVICE_ROLE_KEY` (backend only — never expose in frontend)
4. Add to `.env`:

```
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_DB_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres
```

5. Initialize tables:

```bash
python scripts/init_db.py
```

Or run `supabase/schema.sql` in the Supabase SQL Editor.

### Verify

- `GET /` shows `"database": {"backend": "supabase", "connected": true}`
- `GET /health/database` returns row counts via Supabase REST
- Dashboard **System Status** tab shows Supabase connected

Without Supabase vars, the app continues using SQLite locally.

## Run pipeline once

```bash
python scripts/run_once.py
```

## Start API server

```bash
uvicorn app.main:app --reload
```

- Root: http://127.0.0.1:8000/
- Collect: `POST /collect/run`
- Raw news: `GET /raw-news`
- Incidents: `GET /incidents`
- Drafts: `GET /drafts`

## Streamlit dashboard

Monitor collection from GDELT, ReliefWeb, and ACLED, review incidents, and approve or reject draft posts. **No auto-posting** — X posting stays disabled unless `X_POSTING_ENABLED=true` in `.env`.

```bash
streamlit run dashboard/streamlit_app.py
```

Open http://localhost:8501 (default Streamlit port).

### Recommended local flow

**Terminal 1 — backend:**

```bash
uvicorn app.main:app --reload
```

**Terminal 2 — dashboard:**

```bash
streamlit run dashboard/streamlit_app.py
```

Use **Run Collection Now** in the sidebar to trigger the pipeline, then browse Overview, Raw News, Incidents, and Drafts tabs.

## Share publicly

**One-click deploy (you approve once on Render — ~3 min):**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Sameedism1995/karakorum-analytica)

Or open: **https://render.com/deploy?repo=https://github.com/Sameedism1995/karakorum-analytica**

That creates both public services:
- `https://karakorum-analytica-api.onrender.com`
- `https://karakorum-analytica-dashboard.onrender.com` ← share this link

I cannot complete this step without your Render login. After deploy, open the dashboard URL and click **Run Collection Now**.

Alternative: Streamlit Cloud — see **[DEPLOY.md](DEPLOY.md) Option B** (also requires your login at [share.streamlit.io](https://share.streamlit.io)).

## ACLED (optional)

Register at [ACLED](https://acleddata.com/) and add to `.env`:

```
ACLED_EMAIL=your@email.com
ACLED_API_KEY=your_key
```

If missing, the app logs a warning and continues with GDELT + ReliefWeb.

## ReliefWeb appname (required for ReliefWeb)

ReliefWeb requires a **pre-approved appname**. Request one at:
https://apidoc.reliefweb.int/parameters#appname

Then add to `.env`:

```
RELIEFWEB_APPNAME=your-approved-appname
```

If missing, ReliefWeb collection is skipped gracefully.

## Why Phase 1 does not auto-post

Public OSINT requires careful human review. Drafts are neutral, avoid graphic detail, and never claim official confirmation without an official source. Posting is disabled unless you explicitly set:

```
X_POSTING_ENABLED=true
```

## Adding more sources later

1. Create a collector in `app/collectors/`
2. Register the source in `scripts/init_db.py`
3. Add the source name to `SOURCE_NAMES` in `app/config.py`
4. Update `collect_all()` in `app/services/collection_service.py`
5. Adjust equal weighting if you add a 4th source

## Project structure

```
app/
  collectors/     GDELT, ReliefWeb, ACLED
  processors/     filter, keywords, matching, scoring, drafts
  services/       orchestration layer
  api/            FastAPI routes
  jobs/           APScheduler background collection
  integrations/   Supabase REST client
dashboard/        Streamlit monitoring UI
supabase/         PostgreSQL schema SQL
scripts/          init_db, run_once
tests/            unit tests
```

## Tests

```bash
pytest
```
