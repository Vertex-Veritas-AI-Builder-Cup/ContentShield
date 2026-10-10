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
