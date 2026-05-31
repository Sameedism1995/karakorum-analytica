# Deploy & go live

## Fastest: one click (you approve on Render)

**Click this link** (sign in with GitHub if asked, then click **Apply**):

**https://render.com/deploy?repo=https://github.com/Sameedism1995/pakistan-osint-news-mvp**

Wait ~5–10 minutes. You get:
- API: `https://pakistan-osint-api.onrender.com`
- Dashboard: `https://pakistan-osint-dashboard.onrender.com` ← **share this**

Then open the dashboard → **Run Collection Now**.

> I (the AI) cannot click Approve on Render for you — it requires **your** Render account.

---

## Option A — Render dashboard (same result, manual)

One deploy gives you **two public URLs** (API + dashboard). No Streamlit Cloud needed.

1. Go to [dashboard.render.com](https://dashboard.render.com) → sign in with GitHub
2. **New → Blueprint**
3. Select repo **`Sameedism1995/pakistan-osint-news-mvp`**
4. Click **Apply** — Render creates:
   - `pakistan-osint-api` → `https://pakistan-osint-api.onrender.com`
   - `pakistan-osint-dashboard` → `https://pakistan-osint-dashboard.onrender.com`
5. Wait ~5–10 min for both to build
6. Open the **dashboard URL** — sidebar should show **Backend connected**
7. Click **Run Collection Now**

**Share this link with anyone:** your `pakistan-osint-dashboard.onrender.com` URL.

Optional env vars (Render → each service → Environment):
- `ACLED_EMAIL`, `ACLED_API_KEY`
- `RELIEFWEB_APPNAME`
- `SUPABASE_DB_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (persistent DB)

Free tier sleeps when idle; first load may take ~30s.

---

## Option B — Streamlit Cloud + Render API

Use this if you prefer a `.streamlit.app` URL.

### 1. Deploy API on Render (Blueprint above, or API service only)

Copy the API URL, e.g. `https://pakistan-osint-api.onrender.com`

### 2. Deploy dashboard on Streamlit Cloud

1. [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub
2. **Create app**
3. Repo: `Sameedism1995/pakistan-osint-news-mvp`
4. Main file: `dashboard/streamlit_app.py`
5. **Secrets** (Advanced settings):

```toml
API_BASE_URL = "https://pakistan-osint-api.onrender.com"
```

6. **Deploy**

Share link: `https://your-app-name.streamlit.app`

---

## Verify

- `GET https://YOUR-API-URL/` → JSON with `"status": "running"`
- Dashboard → **Backend connected** → **Run Collection Now** → data in tabs

---

## Safety

- `X_POSTING_ENABLED=false` by default
- Human review only — no auto-posting to X
