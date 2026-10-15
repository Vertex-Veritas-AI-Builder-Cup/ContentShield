# Backend deployment and demo readiness

The backend is designed for a small Cloud Run prototype. It keeps FAISS in
memory, stores source videos in a private GCS bucket, and stores metadata in
Firestore. Do not put credentials, service-account files, generated indexes, or
video assets in Git.

## Configuration checklist

Set these values in the Cloud Run service environment or a local `backend/.env`:

- `GCP_PROJECT_ID`, `GCP_LOCATION`, and `GCS_BUCKET_DEV`
- `GEMINI_ANALYSIS_MODEL`, `GEMINI_VIDEO_EMBEDDING_MODEL`, and
  `GEMINI_EMBEDDING_LOCATION`
- `VIDEO_SEGMENT_SECONDS`, `VIDEO_EMBEDDING_CONCURRENCY`, `MAX_UPLOAD_BYTES`,
  and `MAX_VIDEO_SECONDS`
- `SIGNED_URL_MINUTES` (15 minutes is the cost-safe demo default)
- `CORS_ORIGINS` as a comma-separated list, including the Firebase Hosting
  domains (`https://contentshield-hackathon.web.app` and
  `https://contentshield-hackathon.firebaseapp.com`)

Cloud Run should use an attached service account rather than a checked-in JSON
key. Grant only the permissions needed by the service: bucket-scoped object
read/write/delete access, Firestore read/write access, and Vertex AI user access.
Create these IAM grants at the narrowest project or bucket scope supported by the
environment.

## Local startup

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
python scripts/smoke_check.py --base-url http://localhost:8000
```

The container uses the same startup contract:

```text
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Cloud Run example

Run this from the repository root after selecting the intended GCP project. Keep
the service account and environment values in deployment configuration, not in a
committed command or shell history.

```bash
gcloud run deploy contentshield-api \
  --source backend \
  --region us-central1 \
  --port 8080 \
  --service-account CONTENTSHIELD_RUNTIME_SERVICE_ACCOUNT
```

After deployment, run the smoke check against the service URL:

```bash
python backend/scripts/smoke_check.py --base-url https://SERVICE_URL
```

## Cost-safe demo settings

- Keep uploads at or below 50 MiB and 90 seconds.
- Pre-register the small demo catalog before the presentation so content
  embeddings are generated once, at registration time.
- Use FAISS rather than a managed vector endpoint for the prototype.
- Original registration uploads the video synchronously, then runs content
  fingerprinting in a process-local background task. Only clips with
  `status: fingerprinted` are searchable; use Cloud Tasks or Pub/Sub for a
  durable production worker if the service can scale to zero during jobs.
- Keep signed media URLs short-lived and never make the bucket public.
- Treat Gemini model names and embedding dimensions as configuration; verify
  model availability in the selected region before deployment.

Authentication, queues, retries, rate limiting, multi-tenancy, persistent FAISS
indexes, production calibration, and live platform ingestion remain deferred.
