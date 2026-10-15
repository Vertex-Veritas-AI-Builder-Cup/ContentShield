# Frontend deployment and local setup

The ContentShield frontend is a Next.js application exported as static files.
Firebase Hosting serves the generated `frontend/out` directory, while the API
runs separately (locally or on Cloud Run). The frontend does not contain API
credentials; it only needs the public API base URL at build time.

## Prerequisites

- Node.js 20 or newer and npm
- Access to the backend URL you want the browser to call
- Firebase CLI for Hosting deployments (`npm install -g firebase-tools`)
- Access to the Firebase project configured in `.firebaserc`

Check the installed tools:

```bash
node --version
npm --version
firebase --version
```

## Configuration

`NEXT_PUBLIC_API_URL` is embedded into the browser bundle during `next build`.
For local development, copy the example file and set the backend URL:

```bash
cd frontend
cp .env.local.example .env.local       # macOS/Linux/Git Bash
# PowerShell: Copy-Item .env.local.example .env.local
```

Use `http://localhost:8000` when the backend is running locally. For a hosted
build, use the complete HTTPS API URL, for example:

```text
https://your-cloud-run-service.run.app
```

The backend must include every browser origin in its `CORS_ORIGINS` setting.
For a Firebase Hosting project, include both domains assigned to that project:

```text
https://YOUR_FIREBASE_PROJECT.web.app
https://YOUR_FIREBASE_PROJECT.firebaseapp.com
```

Do not put backend secrets, service-account JSON, or private bucket URLs in
frontend environment files. `.env.local` is ignored by Git.

## Run locally

Start the backend first, then run the development server:

```bash
cd frontend
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The app calls the API
directly from the browser, so a backend health check should succeed before
trying uploads or scans.

## Build the static frontend

Run this from the repository root. The API URL must be set for the same shell
that runs the build.

macOS/Linux/Git Bash:

```bash
npm --prefix frontend ci
NEXT_PUBLIC_API_URL=https://your-cloud-run-service.run.app npm --prefix frontend run build
```

PowerShell:

```powershell
npm --prefix frontend ci
$env:NEXT_PUBLIC_API_URL = "https://your-cloud-run-service.run.app"
npm --prefix frontend run build
```

The static output is written to `frontend/out`. If the variable is omitted, the
frontend falls back to `http://localhost:8000`, which is suitable only for a
local build.

## Deploy manually to Firebase Hosting

Log in once and select the Firebase project:

```bash
firebase login
firebase projects:list
firebase use YOUR_FIREBASE_PROJECT_ID
```

Then build with the production API URL and deploy the generated files:

```bash
# Set NEXT_PUBLIC_API_URL as shown in the build section first.
npm --prefix frontend run build
firebase deploy --only hosting
```

The repository's `firebase.json` maps `frontend/out` to Firebase Hosting and
does not add a catch-all rewrite. The default Hosting domains follow this
pattern:

- `https://YOUR_FIREBASE_PROJECT.web.app`
- `https://YOUR_FIREBASE_PROJECT.firebaseapp.com`

After deployment, open both the home page and the `/catalog` and `/monitor`
routes. If the browser reports a CORS error, update the backend's
`CORS_ORIGINS`; rebuilding the frontend alone will not fix CORS.

### Use a different Firebase project

The checked-in `.firebaserc` selects the shared demo project. To deploy a
personal Firebase project without changing that file, pass the project ID on
the command line:

```bash
firebase deploy --only hosting --project YOUR_FIREBASE_PROJECT_ID
```

That project must have Firebase Hosting enabled and the deploying account must
have permission to publish it. If you want to make the project the local
default instead, run `firebase use --add` and select it. A GitHub Actions
deployment to a different project also requires changing the workflow's
`projectId` and service-account secret.

## Optional GitHub Actions deployment

`.github/workflows/firebase-hosting.yml` deploys Hosting after a push to
`main`. In the GitHub repository, configure these Actions secrets:

- `NEXT_PUBLIC_API_URL`: the public backend URL
- `FIREBASE_SERVICE_ACCOUNT_CONTENTSHIELD_HACKATHON`: a Firebase deploy service
  account JSON value

The service-account JSON belongs in GitHub Actions secrets, never in the
repository. A pull request does not publish a live site; merge to `main` to
run the workflow.

## Common deployment checks

- `npm run build` completes without TypeScript or lint errors.
- `frontend/out/index.html` exists after the build.
- The built API URL is the intended backend, not `localhost`.
- The backend allows both Firebase domains through CORS.
- The Firebase deploy command reports a Hosting release.
- Browser requests to `/health`, catalog, and scan endpoints reach the backend.
