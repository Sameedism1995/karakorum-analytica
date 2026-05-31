# Karakorum Analytica

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

## Share publicly (Render)

**One-click Blueprint deploy:**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Sameedism1995/karakorum-analytica)

Or open: **https://render.com/deploy?repo=https://github.com/Sameedism1995/karakorum-analytica**

This creates two Render web services from [`render.yaml`](render.yaml):

| Service | Name | URL |
|---------|------|-----|
| API (FastAPI) | `karakorum-analytica-api` | `https://karakorum-analytica-api.onrender.com` |
| Dashboard (Streamlit) | `karakorum-analytica-dashboard` | `https://karakorum-analytica-dashboard.onrender.com` |

Share the **dashboard URL** with users. The dashboard talks to the API using `API_BASE_URL` (set automatically by the Blueprint).

### Project layout (important for Render)

This is a **Python monorepo at the repo root** — not separate `backend/` and `frontend/` folders, and **not** a Node/Vite/Next.js app.

```
app/              FastAPI backend (entry: app.main:app)
dashboard/        Streamlit admin UI (entry: dashboard/streamlit_app.py)
render.yaml       Render Blueprint — two Python web services
requirements.txt  Shared Python dependencies
```

There is no `npm run build`. The dashboard is Streamlit (Python), not React.

### Deploy on Render

1. Sign in at [dashboard.render.com](https://dashboard.render.com) with GitHub
2. **New → Blueprint** → select repo `Sameedism1995/karakorum-analytica`
3. Click **Apply** and wait ~5–10 minutes for both services to build
4. Open the dashboard URL → sidebar should show **Backend connected**
5. Click **Run Collection Now**

**Manual deploy (if Blueprint fails):**

Create two **Web Services** from the same repo:

**Service 1 — API**

| Setting | Value |
|---------|--------|
| Name | `karakorum-analytica-api` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements-api.txt` |
| Start Command | `bash scripts/start_api.sh` |
| Health Check Path | `/health` |

**Service 2 — Dashboard**

| Setting | Value |
|---------|--------|
| Name | `karakorum-analytica-dashboard` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `bash scripts/start_dashboard.sh` |

Set `API_BASE_URL` on the dashboard service to the API service’s public URL (e.g. `https://karakorum-analytica-api.onrender.com`).

### Environment variables — API (`karakorum-analytica-api`)

| Variable | Required | Description |
|----------|----------|-------------|
| `ENVIRONMENT` | Yes (prod) | `production` on Render |
| `DEBUG` | Yes | `false` on Render |
| `DATABASE_URL` | Yes | Default Blueprint uses ephemeral SQLite; use `SUPABASE_DB_URL` for persistence |
| `ALLOWED_ORIGINS` | Yes | Comma-separated CORS origins, e.g. `https://karakorum-analytica-dashboard.onrender.com,http://localhost:8501` |
| `SUPABASE_URL` | Optional | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional | Supabase service role key (backend only) |
| `SUPABASE_BUCKET_NAME` | Optional | Supabase storage bucket name |
| `SUPABASE_DB_URL` | Optional | Postgres connection string (recommended for production) |
| `SCRAPER_API_KEY` | Optional | Third-party scraper API key (if used) |
| `RELIEFWEB_APPNAME` | Optional | ReliefWeb approved appname |
| `ACLED_EMAIL` / `ACLED_API_KEY` | Optional | ACLED credentials |
| `X_POSTING_ENABLED` | Optional | Keep `false` unless posting to X is intentional |

See [`.env.example`](.env.example) or [`backend/.env.example`](backend/.env.example).

### Environment variables — Dashboard (`karakorum-analytica-dashboard`)

| Variable | Required | Description |
|----------|----------|-------------|
| `API_BASE_URL` | Yes | FastAPI public URL, e.g. `https://karakorum-analytica-api.onrender.com` |

The Blueprint wires this automatically via `fromService`. See [`dashboard/.env.example`](dashboard/.env.example).

> **Note:** This dashboard is Streamlit (Python), not Vite/Next.js. It uses `API_BASE_URL`, not `VITE_API_BASE_URL` or `NEXT_PUBLIC_API_BASE_URL`.

### Test URLs after deployment

Replace with your actual Render URLs if different:

```bash
# Health check (Render uses this)
curl https://karakorum-analytica-api.onrender.com/health
# → {"status":"ok","service":"karakorum-analytica-api"}

# Root
curl https://karakorum-analytica-api.onrender.com/
# → {"message":"Karakorum Analytica API is running", ...}

# Dashboard (browser)
open https://karakorum-analytica-dashboard.onrender.com
```

### Manual redeploy

Render → select service → **Manual Deploy → Deploy latest commit**

Or push to `main` on GitHub (auto-deploy if enabled).

### Logs

Render → service → **Logs** tab. Check API logs for collection/scheduler errors; check dashboard logs for Streamlit startup issues.

### Common deployment issues

| Problem | Fix |
|---------|-----|
| **502 Bad Gateway** on first load | Free tier services sleep after ~15 min idle. Wait 30–60 seconds and refresh. Wake the API first: open `/health` |
| Dashboard shows **Backend not connected** | Confirm `API_BASE_URL` on dashboard matches API URL; wake API by opening `/health`; free tier sleeps after ~15 min idle |
| API returns 404 | Wrong start command — must be `uvicorn app.main:app --host 0.0.0.0 --port $PORT` from repo root |
| Data lost after redeploy | Render free SQLite is ephemeral — set `SUPABASE_DB_URL` for persistent Postgres |
| CORS errors from browser | Add your dashboard origin to `ALLOWED_ORIGINS` on the API service |
| ReliefWeb / ACLED empty | Set `RELIEFWEB_APPNAME` and/or ACLED credentials on the API service |
| Build fails | Confirm `PYTHON_VERSION=3.11.9` and `requirements.txt` at repo root |

Full step-by-step: **[DEPLOY.md](DEPLOY.md)**

Alternative: Streamlit Cloud — see **DEPLOY.md Option B** (also requires your login at [share.streamlit.io](https://share.streamlit.io)).

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
app/              FastAPI backend (uvicorn app.main:app)
  collectors/     GDELT, ReliefWeb, ACLED
  processors/     filter, keywords, matching, scoring, drafts
  services/       orchestration layer
  api/            FastAPI routes (/health, /raw-news, …)
  jobs/           APScheduler background collection
  integrations/   Supabase REST client
dashboard/        Streamlit monitoring UI (uses API_BASE_URL)
backend/          .env.example only (API env reference; code is in app/)
supabase/         PostgreSQL schema SQL
scripts/          init_db, run_once
tests/            unit tests
render.yaml       Render Blueprint (API + dashboard)
.env.example      Root env template (local dev)
```

## Tests

```bash
pytest
```
