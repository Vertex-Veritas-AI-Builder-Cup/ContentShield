# ContentShield

**Team:** Vertex Veritas  
**Track:** Media, Content & Digital Experiences — H2S × Google Cloud AI Builder Cup

Real-time IP theft and style clone detection for creators.

## Project structure

```
contentshield/
├── frontend/          # Next.js dashboard
├── backend/           # FastAPI API (video processing, Gemini, FAISS)
├── plan.md            # Full build plan
├── initialplan.md     # Core technical plan
└── README.md
```

## Prerequisites

- Node.js 18+
- Python 3.12+
- Google Cloud project with APIs enabled (see below)

## Quick start (local)

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs  
Health check: http://localhost:8000/health

Day 3 scan behavior is available at `POST /api/scan`; scan history is available at
`GET /api/scans`. Similarity scores are cosine-similarity scores, not calibrated
probabilities: `>= 0.75` is `high_risk`, `0.50`–`< 0.75` is `medium_risk`, and
`< 0.50` is `low_risk`. These are initial thresholds calibrated against the
deterministic exact-copy, cropped-copy, and unrelated matching fixtures and should
be recalibrated with labelled production-like videos before launch.

Run the backend unit checks from `backend` with:

```bash
python -m unittest discover -s tests -v
```

## API endpoints

The backend exposes the following FastAPI endpoints. Interactive request and
response schemas are available at `/docs` when the backend is running.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Return links to the API docs and health check. |
| `GET` | `/health` | Confirm that the backend process is running. |
| `POST` | `/api/clips/register` | Upload a protected original video, create its versioned video embeddings, and save it to the protected catalog. Accepts multipart `file`, with optional `title` and `creator_name` fields. |
| `GET` | `/api/clips` | List protected originals for the catalog UI. |
| `GET` | `/api/clips/{clip_id}` | Return public metadata for one protected original. |
| `DELETE` | `/api/clips/{clip_id}` | Delete one protected original, its GCS object, and its Firestore record. |
| `POST` | `/api/scan` | Upload a suspicious video, generate query embeddings, search the protected catalog with FAISS, calculate risk verdicts, and persist the scan. Accepts multipart `file`. |
| `GET` | `/api/scans` | Return recent scan history with the scan ID, top similarity, verdict, and timestamp. |
| `POST` | `/api/style-match` | Compare bounded editing-style signals for an uploaded video and a protected clip. Accepts multipart `file`, `protected_clip_id`, and optional `transcript`. |

Similarity values returned by `/api/scan` and `/api/scans` are cosine-similarity
scores, not calibrated infringement probabilities. The current initial verdict
cutoffs are `high_risk` at `>= 0.75`, `medium_risk` at `0.50`–`< 0.75`, and
`low_risk` below `0.50`.

Style Match is a separate creator-intelligence prototype. It compares FFmpeg scene
cuts and optional transcript-based opening-hook cues; it does not reuse content
embeddings, produce a copyright conclusion, or claim that style similarity proves
infringement. OCR-based overlay analysis and transcript timing remain deferred.

### 2. Frontend

```bash
cd frontend
cp .env.local.example .env.local   # or copy manually on Windows
npm install
npm run dev
```

App: http://localhost:3000 — click **Check Backend Health** to verify the connection.

## Environment variables

Copy `.env.example` values into:

| File | Purpose |
|------|---------|
| `backend/.env` | GCP project ID, bucket name, service account path |
| `frontend/.env.local` | `NEXT_PUBLIC_API_URL=http://localhost:8000` |

**Never commit** `.env`, `.env.local`, or `service-account.json`.

## GCP setup (one-time)

Enable in [API Library](https://console.cloud.google.com/apis/library):

- **Gemini Enterprise Agent Platform API** (formerly Vertex AI API)
- Cloud Storage API
- Cloud Run API
- Cloud Firestore API

Create:

- GCS bucket
- Firestore database (Firebase console, linked to same GCP project)
- Service account with Storage Object Admin + Agent Platform User roles

## Team workflow

```bash
git pull                    # before you start
git checkout -b feature/xyz # your branch
git add .
git commit -m "message"
git push -u origin feature/xyz
```

## License

MIT
