# ContentShield frontend

This Next.js frontend provides local testing for protected-clip registration,
catalog management, content scans, evidence explanations, and reviewable DMCA
drafts.

## Local development

Start the backend on `http://localhost:8000`, then run:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Copy `.env.local.example` to `.env.local` when the backend uses another URL:

```bash
cp .env.local.example .env.local
```

The browser calls the backend directly, so the backend must allow the frontend
origin through CORS. The local backend already allows `http://localhost:3000`.

## Deploy on Vercel

Import this repository into Vercel and set the project root to `frontend`. Add:

```text
NEXT_PUBLIC_API_URL=https://<your-cloud-run-service>.run.app
```

Redeploy after changing this variable because `NEXT_PUBLIC_*` values are bundled
into the browser build. No frontend Docker image is required.
