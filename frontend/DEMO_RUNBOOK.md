# Repeatable frontend demo runbook

Use self-recorded or royalty-free videos for demonstrations. The frontend is a
browser client, so the backend must be healthy and reachable before the demo
starts.

## Local demo

1. Start the backend and confirm `http://localhost:8000/health` responds.
2. In `frontend`, set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env.local`.
3. Install dependencies and start Next.js:

   ```bash
   npm ci
   npm run dev
   ```

4. Open `http://localhost:3000` and use **Check Backend Health**.
5. Open **Originals** and register one or two demo videos. Wait until each
   original is fingerprinted and searchable.
6. Open **Check**, upload an exact, cropped, or unrelated checked video, and
   submit the scan.
7. Review the verdict, evidence, explanation, and optional DMCA draft. Use the
   catalog to confirm that registered originals remain available.

Keep temporary clip IDs, scan IDs, and local media out of source control.

## Firebase demo

1. Confirm the Cloud Run API is healthy and that its `CORS_ORIGINS` contains
   both Firebase Hosting domains.
2. Build with the Cloud Run URL as `NEXT_PUBLIC_API_URL` and deploy Hosting:

   ```bash
   npm --prefix frontend run build
   firebase deploy --only hosting
   ```

3. Open the Firebase Hosting URL assigned to your project in a private browser
   window.
4. Check the home page, `/catalog`, and `/monitor` before uploading media.
5. Run the same original-registration and checked-video scan flow as the local
   demo.
6. Open browser developer tools and confirm API requests use the Cloud Run URL,
   not `localhost`, and return successful responses.

## Release checklist

- [ ] Backend health endpoint responds from the deployment URL.
- [ ] Production build has the correct `NEXT_PUBLIC_API_URL`.
- [ ] `npm run build` succeeds and creates `frontend/out`.
- [ ] Firebase Hosting deploy completes successfully.
- [ ] Home, catalog, monitor, and check routes load from the public domain.
- [ ] Browser requests pass CORS and media URLs load.
- [ ] At least one known matching and one unrelated demo scan work.
- [ ] No credentials, service-account files, or demo videos are committed.

## Quick troubleshooting

| Symptom | Check |
| --- | --- |
| The page calls `localhost` after deployment | Rebuild with the production `NEXT_PUBLIC_API_URL`; it is a build-time value. |
| Browser shows a CORS error | Add the exact Firebase origin to backend `CORS_ORIGINS` and redeploy the backend. |
| A route returns 404 | Confirm the static build completed and deploy from the repository root using the checked-in `firebase.json`. |
| Uploads fail | Check backend health, Cloud Run logs, and the backend's upload limits. |
| Firebase deploy is unauthorized | Run `firebase login` with an account that has access to the project, or use the configured GitHub Actions service account. |
