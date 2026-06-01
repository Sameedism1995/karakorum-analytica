# Deploy & go live

## Fastest: one click (you approve on Render)

**Click this link** (sign in with GitHub if asked, then click **Apply**):

**https://render.com/deploy?repo=https://github.com/Sameedism1995/karakorum-analytica**

Wait ~5–10 minutes. You get:
- API: `https://karakorum-analytica-api.onrender.com`
- Dashboard: `https://karakorum-analytica-dashboard.onrender.com` ← **share this**

Then open the dashboard → **Run Collection Now**.

> I (the AI) cannot click Approve on Render for you — it requires **your** Render account.

---

## Option A — Render dashboard (same result, manual)

One deploy gives you **two public URLs** (API + dashboard). No Streamlit Cloud needed.

1. Go to [dashboard.render.com](https://dashboard.render.com) → sign in with GitHub
2. **New → Blueprint**
3. Select repo **`Sameedism1995/karakorum-analytica`**
4. Click **Apply** — Render creates:
   - `karakorum-analytica-api` → `https://karakorum-analytica-api.onrender.com`
   - `karakorum-analytica-dashboard` → `https://karakorum-analytica-dashboard.onrender.com`
5. Wait ~5–10 min for both to build
6. Open the **dashboard URL** — sidebar should show **Backend connected**
7. Click **Run Collection Now**

**Share this link with anyone:** your `karakorum-analytica-dashboard.onrender.com` URL.

Optional env vars (Render → **karakorum-analytica-api** → Environment):

| Variable | Purpose |
|----------|---------|
| `ALLOWED_ORIGINS` | CORS — include dashboard URL + `http://localhost:8501` |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL` | Persistent Postgres |
| `SUPABASE_BUCKET_NAME` | Supabase storage bucket (optional) |
| `SCRAPER_API_KEY` | Optional scraper integration |
| `ACLED_EMAIL`, `ACLED_API_KEY` | ACLED collector |
| `RELIEFWEB_APPNAME` | ReliefWeb collector |

Dashboard service only needs `API_BASE_URL` (auto-set by Blueprint).

**Health check:** `GET /health` → `{"status":"ok","service":"karakorum-analytica-api"}`

**Manual deploy:** Render → service → Manual Deploy → Deploy latest commit

**Logs:** Render → service → Logs

Free tier sleeps when idle; first load may take ~30s.

---

## Option B — Streamlit Cloud + Render API

Use this if you prefer a `.streamlit.app` URL.

### 1. Deploy API on Render (Blueprint above, or API service only)

Copy the API URL, e.g. `https://karakorum-analytica-api.onrender.com`

### 2. Deploy dashboard on Streamlit Cloud

1. [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub
2. **Create app**
3. Repo: `Sameedism1995/karakorum-analytica`
4. Main file: `dashboard/streamlit_app.py`
5. **Secrets** (Advanced settings):

```toml
API_BASE_URL = "https://karakorum-analytica-api.onrender.com"
```

6. **Deploy**

Share link: `https://your-app-name.streamlit.app`

---

## Verify

```bash
curl https://karakorum-analytica-api.onrender.com/health
# {"status":"ok","service":"karakorum-analytica-api"}

curl https://karakorum-analytica-api.onrender.com/
# {"message":"Karakorum Analytica API is running", ...}
```

- Dashboard → **Backend connected** → **Run Collection Now** → data in tabs

---

## Scweet token handoff (Render production)

Render has **no display** — Playwright login cannot run there. Production uses `SCWEET_AUTH_TOKEN` injected via the Render API from your **local machine only** (no GitHub Actions).

### Local sync script

```bash
# .env required:
#   RENDER_API_KEY=rnd_...
#   RENDER_SERVICE_IDS=srv-api-id,srv-dashboard-id

python scripts/sync_scweet_token_to_render.py --deploy --write-env
```

The script:
1. Reads `data/scweet_state.db` (Scweet `accounts` table)
2. Extracts the active `auth_token` (or from `cookies_json`)
3. Calls Render API: `PUT https://api.render.com/v1/services/{service_id}/env-vars/SCWEET_AUTH_TOKEN`
4. Sets `SCWEET_AUTO_LOGIN=false` and `SCWEET_ENABLED=true`

### Local cron (every 10 hours)

```bash
bash scripts/install_scweet_token_cron.sh
```

Logs: `logs/scweet-token-sync.log`

Ensure `data/scweet_state.db` stays populated by using Scweet locally (`python scripts/scweet_login.py` or dashboard X/Scweet tab).

---

## Safety

- `X_POSTING_ENABLED=false` by default
- Human review only — no auto-posting to X by default (Scweet search optional via `SCWEET_ENABLED`)
