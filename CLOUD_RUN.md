# Asteril CRM Automation — Cloud Run

## What changed for Cloud Run

- Selenium jobs run inside the HTTP request instead of detached daemon threads.
- The container uses one Gunicorn worker and one thread. Deploy the service with **maximum instances = 1** and **concurrency = 1** so the in-memory process lock remains effective.
- Secret files can be mounted under `/secrets`. The existing Render `/etc/secrets` path is still supported.
- The container timezone is set to `Europe/Kyiv`.
- `.dockerignore` excludes credentials and local artifacts from the image build context.

## Required secrets

Create these Secret Manager secrets in your Google Cloud project:

- `token-json` — contents of the existing Google OAuth `token.json`
- `asteril-cookies-json` — contents of `asteril_cookies.json`
- `asteril-login` — Asteril login/email
- `asteril-password` — Asteril password

Do not commit these files or values to GitHub.

The Cloud Run service account needs:
- Secret Manager Secret Accessor on the four secrets.
- Access to the target Google spreadsheet(s) for the Google account represented by `token.json`.

## Deploy

Enable the Cloud Run, Cloud Build, and Secret Manager APIs first. Run the following commands from the repository root after selecting the correct project:

```bash
gcloud config set project YOUR_PROJECT_ID

gcloud run deploy asteril-automation \
  --source . \
  --region europe-central2 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600 \
  --concurrency 1 \
  --max 1 \
  --set-env-vars TZ=Europe/Kyiv \
  --update-secrets=/secrets/token.json=token-json:latest,/secrets/asteril_cookies.json=asteril-cookies-json:latest,ASTERIL_LOGIN=asteril-login:latest,ASTERIL_PASSWORD=asteril-password:latest
```

Replace `YOUR_PROJECT_ID` with the Google Cloud project ID. The deploy identity must be allowed to deploy Cloud Run services and attach the selected runtime service account. Grant the **runtime service account** Secret Manager Secret Accessor on each secret.

If the service should not be publicly accessible, remove `--allow-unauthenticated` and configure access for the intended users.

## Important runtime behavior

- A run request stays open until Selenium and the spreadsheet updates finish. The configured request timeout is 60 minutes.
- Do not launch two jobs simultaneously. Cloud Run is configured for one instance and one concurrent request; the app also has an in-process lock.
- Cloud Run's local filesystem is temporary. Downloaded CRM reports are processed inside the request and are not retained as durable files.
- `/status` reports the most recent state held by the current instance. It is not a durable job history.
- The existing Google OAuth token must contain a valid refresh token. If it is revoked or expires without a refresh token, re-authorize Google and replace the Secret Manager secret.

## Render compatibility

The existing `render.yaml` remains unchanged. Render Secret Files mounted at `/etc/secrets` continue to be detected. Cloud Run-specific changes are isolated to runtime configuration and secret path handling.
