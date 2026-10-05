# Deploying Fraud Triage

The live demo has three parts:

| Part | Where | What it does |
|---|---|---|
| Database | Supabase (already set up) | Holds the 20,000 pre-scored demo transactions and the reviews |
| API | Render (free web service) | FastAPI in `postgres` mode; serves the precomputed results. Never loads LightGBM or SHAP |
| Web app | Vercel (free) | The Next.js review app in `web/` |

Scoring happens offline on your machine (`python -m src.export_demo --upload`); the deployed parts only read and write the demo tables.

Before you start: the demo data must already be in Supabase (`python -m src.export_demo --upload`), and your latest code must be pushed to GitHub.

---

## 1. API on Render

1. Sign in at [render.com](https://render.com) with GitHub.
2. **New → Web Service**, then pick the `fraud-triage` repository.
3. Enter these settings:

| Setting | Value | Why |
|---|---|---|
| Name | `fraud-triage-api` (or anything) | Becomes part of the URL: `https://<name>.onrender.com` |
| Language / Runtime | Python 3 | |
| Branch | `main` | |
| Root Directory | *(leave empty)* | The API code (`src/`), `config.yaml` and `reports/policy_results.json` are at the repository root |
| Build Command | `pip install -r requirements-api.txt` | Installs only the six production packages, not the machine-learning stack |
| Start Command | `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT --proxy-headers` | Render tells the app which port to use in `$PORT`. `--proxy-headers` makes the rate limit see each visitor's real address instead of Render's proxy |
| Health Check Path | `/health` (under Advanced) | Render calls this to know the service is up |
| Instance Type | Free | |

4. Under **Environment Variables**, add:

| Name | Value | Why |
|---|---|---|
| `DATABASE_URL` | Your Supabase **session pooler** connection string, with the password filled in and no square brackets | Where the demo data lives. Secret: only ever paste it into Render, never into code or chat |
| `DATA_BACKEND` | `postgres` | Serve the precomputed demo instead of scoring live |
| `ALLOWED_ORIGINS` | `https://example.invalid` for now | Which website may call the API from a browser. You'll replace it with your Vercel address in step 3 |
| `FORWARDED_ALLOW_IPS` | `*` | Lets `--proxy-headers` trust the address Render's proxy passes on. Safe on Render because only its proxy can reach the service |
| `PYTHON_VERSION` | `3.14.8` | The version the project was built and tested with. If Render says it isn't available, use the newest 3.13 instead; the production packages work on both |

5. Click **Create Web Service** and wait for the build to finish (a few minutes).
6. Open `https://<your-service>.onrender.com/health`. You should see `{"status":"ok","backend":"postgres"}`.
7. Also try `https://<your-service>.onrender.com/queue?date=2020-12-24` — you should see a list of cases.

**Free tier note:** the service sleeps after about 15 minutes without requests, and the next request wakes it, which can take 30–60 seconds. The web app shows a "waking up" message during that wait.

---

## 2. Web app on Vercel

1. Sign in at [vercel.com](https://vercel.com) with GitHub.
2. **Add New → Project**, then import the `fraud-triage` repository.
3. Enter these settings:

| Setting | Value | Why |
|---|---|---|
| Framework Preset | Next.js (detected automatically) | |
| Root Directory | `web` | The web app lives in `web/`, not at the repository root |
| Build Command | *(default: `npm run build`)* | |
| Install Command | *(default: `npm install`)* | |
| Output Directory | *(default)* | |

4. Under **Environment Variables**, add:

| Name | Value | Why |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://<your-service>.onrender.com` (no slash at the end) | The API's address. Next.js writes it into the site **when it builds**, so if you change it later you must redeploy |

5. Click **Deploy**. When it finishes, copy your site's address, e.g. `https://fraud-triage.vercel.app`.

---

## 3. Connect the two

1. Back on Render, open the service's **Environment** tab.
2. Set `ALLOWED_ORIGINS` to your Vercel address, e.g. `https://fraud-triage.vercel.app` (no slash at the end). To allow more than one site, separate them with commas.
3. Save. Render redeploys the API automatically.

Without this step the site loads, but every page shows "Couldn't reach the API", because the browser blocks calls the API hasn't allowed.

Vercel also creates preview deployments with different addresses for each push. They won't be able to reach the API unless you add their address too; only the main address needs to work.

---

## 4. Check it

Open the Vercel address on your phone and on a laptop in a private window:

1. The queue loads (the first visit may show the "waking up" message for up to a minute).
2. Open a case, click **Confirm fraud** or **Mark legitimate**, and see the true label.
3. In Supabase's **Table Editor**, the `reviews` table has your decision.
4. The **Results** page shows the headline, table and both charts.

If something fails, open the browser's developer console (F12 → Console) and copy the error.

---

## Looking after the demo

| Task | How |
|---|---|
| Clear all reviews | On your machine: `.venv\Scripts\python -m src.api.reset_reviews` |
| Reload the demo data (after retraining) | `.venv\Scripts\python -m src.export_demo --upload` (also clears reviews). Then copy the new charts into `web/public/figures/` and `reports/metrics.json` and `reports/policy_results.json` into `web/data/` (the overview page reads its numbers from them), and push so Vercel redeploys |
| Supabase project paused | Free projects pause after about a week without activity. Open the Supabase dashboard and click **Restore** |
| Too many reviews | After 5,000 reviews the API returns "review limit reached" until you clear them. The limit and the 10-per-minute rate limit are in `config.yaml` under `api:` |
| Change the database password | Reset it in Supabase, then update `DATABASE_URL` in Render (and in your local `.env`) |
