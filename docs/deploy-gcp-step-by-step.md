# Deploy ZataOne to GCP — step by step

Work **one step at a time**. Finish and verify each block before moving on.

**Already in the repo:** Step 1 (Docker `PORT`, CORS), `cloudbuild.yaml`, and a static demo UI in `web/`.

---

## Step 1 — App ready for Cloud Run ✅

- Container listens on **`$PORT`**.
- **CORS:** set `CORS_ORIGINS` (comma-separated) on Cloud Run to your static site URL. For quick tests only: `CORS_ALLOW_ALL=true`.

---

## Step 2 — GCP project & APIs

**Goal:** A project ID you will use only for ZataOne (recommended), billing on, APIs enabled.

### 2a — Create a project (pick one)

**Option A — Console:** [Google Cloud Console](https://console.cloud.google.com/) → project dropdown → **New project** → name e.g. `zataone-prod` → **Create**. Note the **Project ID** (not only the name).

**Option B — CLI:**

```bash
gcloud projects create YOUR_PROJECT_ID --name="Zataone"
gcloud billing projects link YOUR_PROJECT_ID --billing-account=YOUR_BILLING_ACCOUNT_ID
```

Find billing account IDs: `gcloud billing accounts list`

### 2b — Point `gcloud` at this project

```bash
export PROJECT_ID=YOUR_PROJECT_ID
gcloud config set project $PROJECT_ID
gcloud config get-value project   # should print YOUR_PROJECT_ID
```

### 2c — Enable required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com
```

### 2d — Verify

```bash
gcloud services list --enabled | grep -E 'run.googleapis|sqladmin|artifactregistry|cloudbuild'
```

**Stop here** until you see those services enabled. **Next:** Step 3 (database).

---

## Step 3 — Cloud SQL (PostgreSQL)

**Goal:** A Postgres instance, database `zataone`, user + password, and a connection name for Cloud Run.

Pick a **region** you will reuse (e.g. `us-central1`):

```bash
export REGION=us-central1
export INSTANCE=zataone-pg
export DB_NAME=zataone
export DB_USER=zataone
# Choose a strong password; you will need it in Step 4:
export DB_PASS='replace-with-strong-password'
```

### 3a — Create instance (dev-sized; adjust tier for production)

```bash
gcloud sql instances create $INSTANCE \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=$REGION \
  --root-password="$DB_PASS"
```

(Alternatively create user separately; for simplicity this uses instance with a password you’ll use for the app user — see [Cloud SQL docs](https://cloud.google.com/sql/docs/postgres/create-instance) for separating root vs app user.)

### 3b — Create database and user (if not using only postgres user)

```bash
gcloud sql databases create $DB_NAME --instance=$INSTANCE

gcloud sql users create $DB_USER \
  --instance=$INSTANCE \
  --password="$DB_PASS"
```

### 3c — Connection name (you need this for Cloud Run)

```bash
gcloud sql instances describe $INSTANCE --format='value(connectionName)'
```

Save the output as `CONNECTION_NAME` — it looks like `PROJECT_ID:REGION:INSTANCE`.

### 3d — `DATABASE_URL` for Cloud Run (Unix socket — recommended)

Cloud Run will attach the instance with `--add-cloudsql-instances`. Use a URL like:

```text
postgresql+psycopg2://DB_USER:URL_ENCODED_PASSWORD@localhost/DB_NAME?host=/cloudsql/CONNECTION_NAME
```

- **URL-encode** the password if it has special characters (`@`, `#`, etc.).
- SQLAlchemy default in this project is `postgresql://...`; **psycopg2** accepts the `host=/cloudsql/...` query form. Our code uses `create_engine(DATABASE_URL)` — the standard form that works with the Cloud SQL Python connector / unix socket is:

```text
postgresql://DB_USER:PASSWORD@/DB_NAME?host=/cloudsql/PROJECT_ID:REGION:INSTANCE
```

(Test in Cloud Shell with `psql` over proxy if unsure.)

### 3e — One-time schema (migrations)

From your laptop (with Cloud SQL Auth Proxy) or **Cloud Shell**:

1. Connect to the instance and run the same as local: Python `create_all_tables` + `migrations/*.sql`, **or**
2. Use `psql` and run SQL files in order:

   - `migrations/add_idempotency_key.sql`
   - `migrations/add_violations_table.sql`
   - `migrations/add_evidence_violation_link.sql`

Example using proxy (install [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/connect-auth-proxy)):

```bash
# Terminal 1
cloud-sql-proxy PROJECT_ID:REGION:INSTANCE --port 5432

# Terminal 2
export DATABASE_URL=postgresql://zataone:PASSWORD@127.0.0.1:5432/zataone
cd /path/to/ZetaOne
python -c "from zataone.storage.database import create_all_tables; create_all_tables(); print('OK')"
for f in migrations/*.sql; do psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"; done
```

**Stop here** until you can connect and tables exist. **Next:** Step 4 (image + Cloud Run).

---

## Step 4 — Artifact Registry, build image, deploy Cloud Run

**Goal:** Push a container and run the API with `DATABASE_URL`, Cloud SQL attachment, and CORS.

### 4a — Docker repository (once per project)

```bash
export REGION=us-central1
gcloud artifacts repositories create zataone \
  --repository-format=docker \
  --location=$REGION \
  --description="Zataone API images"
```

### 4b — Build and push (from **repo root**, where `cloudbuild.yaml` lives)

```bash
cd /path/to/ZetaOne
gcloud builds submit --config cloudbuild.yaml --substitutions=_REGION=$REGION .
```

Image will be: `$REGION-docker.pkg.dev/$PROJECT_ID/zataone/zataone-api:latest`

### 4c — Deploy Cloud Run

Replace placeholders. Use **URL-encoded** password in `DATABASE_URL` if needed.

```bash
export CONNECTION_NAME="$PROJECT_ID:$REGION:$INSTANCE"
export DATABASE_URL="postgresql://${DB_USER}:ENCODED_PASS@/${DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"

gcloud run deploy zataone-api \
  --region=$REGION \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/zataone/zataone-api:latest \
  --platform=managed \
  --allow-unauthenticated \
  --add-cloudsql-instances=${CONNECTION_NAME} \
  --set-env-vars="DATABASE_URL=${DATABASE_URL},CORS_ORIGINS=https://your-static-site.host" \
  --memory=2Gi \
  --timeout=300
```

- For **quick browser tests** from random static hosts, you can temporarily add `CORS_ALLOW_ALL=true` (remove for production).
- Increase **memory** if pipeline / ML extractors OOM.

### 4d — Verify API

```bash
export SERVICE_URL=$(gcloud run services describe zataone-api --region=$REGION --format='value(status.url)')
curl -sS "$SERVICE_URL/health"
```

Expect: `{"status":"ok","service":"zataone"}`

**Stop here** until `/health` works and `POST /assets` works (e.g. from `curl`). **Next:** Step 5 (web UI).

---

## Step 5 — Webpage (upload & results)

**Goal:** Users open a page, upload text or image, see the verdict.

### 5a — Try locally against Cloud Run

1. Note `SERVICE_URL` from Step 4d.
2. On Cloud Run, set `CORS_ORIGINS` to include the origin where you serve the UI. Easiest local test:

   ```bash
   # temporarily on the service:
   gcloud run services update zataone-api --region=$REGION \
     --set-env-vars="CORS_ALLOW_ALL=true"
   ```

   (Turn this off later; use explicit origins.)

3. From repo:

   ```bash
   cd web && python -m http.server 5500
   ```

4. Open `http://localhost:5500` → set **API base URL** to `SERVICE_URL` → run a text check.

### 5b — Host the static site (production)

Upload the `web/` folder to **Firebase Hosting**, **Cloud Storage** (website bucket), **Netlify**, etc.

Set Cloud Run env:

```bash
gcloud run services update zataone-api --region=$REGION \
  --set-env-vars="CORS_ORIGINS=https://your-site.web.app"
```

(remove `CORS_ALLOW_ALL` if you used it)

---

## Quick reference — API paths

| Action | Method | Path |
|--------|--------|------|
| Health | GET | `/health` |
| Submit text | POST | `/assets` JSON `{ "content", "type": "text" }` |
| Submit image | POST | `/assets/image` multipart `file` |
| Poll result | GET | `/assets/{asset_id}` |
| Full graph | GET | `/assets/{asset_id}/graph` |

---

## Checklist before real customers

- [ ] No `CORS_ALLOW_ALL` in production.
- [ ] `CORS_ORIGINS` matches your real UI origin(s).
- [ ] API not fully public without auth — add API key, IAP, or Cloud Endpoints as needed.
- [ ] Store `DATABASE_URL` / DB password in **Secret Manager**, reference from Cloud Run.
- [ ] Cloud SQL backups and maintenance window set.
