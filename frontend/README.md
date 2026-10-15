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

Frontend deployment is configured from the repository root; see the deployment
instructions in the main README.

For the complete local setup, Firebase deployment checklist, and troubleshooting
guidance, see [`DEPLOYMENT.md`](DEPLOYMENT.md). A repeatable local and hosted
demo sequence is in [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md).

## Deploy on Firebase Hosting

The frontend is exported as static files in `frontend/out` and deployed to a
Firebase Hosting site. For a manual deployment, set the production API URL
while building, then deploy from the repository root:

```bash
NEXT_PUBLIC_API_URL=https://<your-cloud-run-service>.run.app npm --prefix frontend run build
firebase deploy --only hosting
```

The GitHub Actions workflow deploys automatically after changes are pushed to
`main`. It requires the repository secrets `NEXT_PUBLIC_API_URL` and
`FIREBASE_SERVICE_ACCOUNT_CONTENTSHIELD_HACKATHON`.
