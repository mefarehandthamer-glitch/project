# BRAIN SOURCE deployment and operations

## Before a public launch

1. Choose a hosting provider that supports Python ASGI applications and persistent disk storage. SQLite needs a persistent volume; ephemeral container storage is not sufficient.
2. Configure `BRAIN_SOURCE_ADMIN_PASSWORD` and `BRAIN_SOURCE_SECRET_KEY` as server-side secrets. Use a unique high-entropy password and secret key.
3. Serve the app only through HTTPS, then set `BRAIN_SOURCE_COOKIE_SECURE=1`.
4. Keep `BRAIN_SOURCE_SHOW_API_DOCS=0` in public deployments.
5. Add host-level rate limiting / bot protection to the login route, uptime monitoring, log retention rules, and encrypted scheduled database backups.
6. Test restore from backup before collecting any real participant results.
7. Use a privacy notice and informed-consent process appropriate for the project. Do not collect names, contact details, or other identifying information unless there is a clear approved need.
8. Complete Arabic translation review, usability checks, accessibility review, and a full cross-browser test. The current question bank is not equivalent across English and Arabic.
9. Do not describe the app as measuring clinical cognition or validated IQ/EQ. Its outputs are task scores for a small educational demonstration.

## Example: run locally on Bazzite/Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
export BRAIN_SOURCE_ADMIN_PASSWORD='your-long-password'
export BRAIN_SOURCE_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export BRAIN_SOURCE_DB="$PWD/data/brain_source.sqlite3"
export BRAIN_SOURCE_COOKIE_SECURE=0
uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000`. The `Cloud sign in` control is the opt-in bridge between browser storage and the backend. If the backend is unavailable, the activity app still works in local mode.

## Docker notes

Build from the project root with `docker build -f backend/Dockerfile -t brain-source .`. Mount a persistent host directory to `/app/data`. The container image contains no secrets. Supply secrets at runtime through the platform's secret manager, not by editing the Dockerfile.

## Backup and restore

Stop writes briefly or use the included `backup_db.py` helper to create a consistent SQLite backup. Keep backups encrypted and access-controlled. Restore by replacing the database file while the service is stopped, then restart and verify `/api/health` plus a test login.

## Security scope

The backend is a small single-admin prototype. Login throttling is in-memory and resets when the process restarts; a public deployment should also use provider/proxy rate limits. Use a single application instance unless you move session/rate-limit state to a shared service. SQLite is appropriate for a small science fair; move to a managed database if the project grows. Server-side answer-key protection is not complete because activity questions and scoring are still bundled into the frontend.

## Free hosted setup: Render + Neon PostgreSQL

The included `render.yaml` creates a free Render web service with HTTPS and a health check. Free web-service files are temporary, so this Blueprint intentionally has **no disk** and expects a PostgreSQL connection string in `BRAIN_SOURCE_DATABASE_URL`. The backend supports SQLite for local/offline use and PostgreSQL for hosting.

1. Create a free PostgreSQL database at [Neon](https://neon.tech/).
2. Copy its connection string, keep it secret, and use SSL (`sslmode=require`).
3. Upload this project folder to a private GitHub repository. Include `render.yaml`, `backend/`, and `index.html`; exclude `.env`, passwords, and data files.
4. In [Render Dashboard](https://dashboard.render.com/), select **New → Blueprint** and connect the repository.
5. Set `BRAIN_SOURCE_ADMIN_PASSWORD` to a strong unique password. Let Render generate `BRAIN_SOURCE_SECRET_KEY`. Set `BRAIN_SOURCE_DATABASE_URL` to the Neon connection string.
6. Deploy, then check `https://YOUR-SERVICE.onrender.com/api/health`. Expected: `ok: true`, `database: "postgresql"`, and `admin_configured: true`.
7. Sign in via **Cloud sign in**, test creating/syncing/exporting dummy records, redeploy and verify records still exist. Set a calendar reminder to export backups.

### What free means here

Render free web services sleep after 15 minutes of inactivity and wake on the next request; the first request can take about a minute. Neon free has compute, storage, and network quotas. When free quotas are exhausted, database operations may pause until quota resets or the plan changes. This is appropriate for a small science-fair demo, not mission-critical data. Review current provider limits before using it: https://render.com/docs/free and https://neon.com/pricing.

## Alternative paid setup

The prior SQLite + persistent disk setup requires a paid Render service/disk. For always-on use or more reliability, use a paid web service and a database with backups. Do not use SQLite on a free hosted filesystem for results you need to keep.
