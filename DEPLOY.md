# Deploy & share the dashboard

The dashboard needs **two** public services:

1. **FastAPI backend** (data collection API) — deploy on [Render](https://render.com)
2. **Streamlit dashboard** (UI) — deploy on [Streamlit Community Cloud](https://share.streamlit.io)

Streamlit Cloud runs the UI in the cloud; it calls your public backend URL (not `localhost`).

---

## Step 1 — Push to GitHub

Already done if this repo is on GitHub. If not:

```bash
git init
git add .
git commit -m "Initial commit"
gh repo create pakistan-osint-news-mvp --public --source=. --push
```

---

## Step 2 — Deploy the backend (Render)

1. Go to [dashboard.render.com](https://dashboard.render.com) and sign in.
2. **New → Blueprint** (or **New → Web Service** if Blueprint is unavailable).
3. Connect your GitHub repo `pakistan-osint-news-mvp`.
4. Render reads `render.yaml` and creates `pakistan-osint-api`.
5. After deploy, copy the public URL, e.g. `https://pakistan-osint-api.onrender.com`.
6. Optional: in Render **Environment**, add:
   - `RELIEFWEB_APPNAME` — for ReliefWeb data
   - `ACLED_EMAIL` / `ACLED_API_KEY` — for ACLED data
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL` — for persistent storage (recommended over SQLite)

Free tier sleeps after inactivity; the first request may take ~30s to wake up.

Test: open `https://YOUR-API-URL/` — you should see JSON with `"status": "running"`.

---

## Step 3 — Deploy the dashboard (Streamlit Cloud)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. **Create app** → pick repo `pakistan-osint-news-mvp`.
3. Set **Main file path**: `dashboard/streamlit_app.py`
4. **Advanced settings → Secrets** — paste (replace with your Render URL):

```toml
API_BASE_URL = "https://pakistan-osint-api.onrender.com"
```

5. Click **Deploy**.

Your shareable link will look like:

`https://pakistan-osint-news-mvp.streamlit.app`

(or similar based on app name)

---

## Step 4 — Verify

1. Open the Streamlit URL in a browser.
2. Sidebar should show **Backend connected**.
3. Click **Run Collection Now** and check **Raw News** / **Incidents** tabs.

---

## Safety (unchanged in production)

- `X_POSTING_ENABLED=false` on Render by default
- No auto-posting from the dashboard
- Draft **Approve / Reject** only; **Post** hidden unless X posting is enabled on the backend

---

## Updating after changes

Push to GitHub — both Render and Streamlit Cloud redeploy automatically (if auto-deploy is on).
