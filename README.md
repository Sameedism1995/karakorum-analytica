# Pakistan OSINT News MVP

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

## Share publicly (Streamlit Cloud)

To share the dashboard with anyone, deploy the **backend** (Render) and **dashboard** (Streamlit Cloud). Full step-by-step guide: **[DEPLOY.md](DEPLOY.md)**.

Quick summary:

1. Push this repo to GitHub
2. Deploy API with Render using `render.yaml` → copy public URL
3. Deploy on [share.streamlit.io](https://share.streamlit.io) with main file `dashboard/streamlit_app.py`
4. Add Streamlit secret: `API_BASE_URL = "https://your-api.onrender.com"`

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
dashboard/        Streamlit monitoring UI
scripts/          init_db, run_once
tests/            unit tests
```

## Tests

```bash
pytest
```
