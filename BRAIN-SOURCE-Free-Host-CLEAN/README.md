# BRAIN SOURCE — Educational Cognitive Research Lab

The **Project Hub** is built into `index.html`: use its navigation to access the activities, participants, results dashboard, research report, setup guide, deployment notes, and project downloads from one website page. Keep the project files together so the document and ZIP download links work.

BRAIN SOURCE is a bilingual-interface science-fair web app with eight cognitive-style activities, six anonymous participant profiles, randomized question selection, reaction-time trials, a 40-question mixed final, charts, a research summary, CSV export, local autosave, unfinished-session recovery, optional server sync, and a server-backed session planner.

## Quick start: local/offline mode

1. Open `index.html` in Firefox. On Linux/Bazzite, no installation is required.
2. Results and unfinished attempts are saved in that browser on that device.
3. Export CSV backups from the Results dashboard regularly.

Local mode does not require an account or internet access. It does not automatically sync to another browser or device.

## Full-stack mode: persistent server database + administrator sign-in

Requires Python 3.11+ and internet access for the first dependency installation. On Bazzite/Linux, the easiest option is to run `./run-local.sh`; it creates a virtual environment, installs dependencies, prompts for an administrator password, and starts the server.

Manual alternative:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
export BRAIN_SOURCE_ADMIN_PASSWORD='use-a-long-unique-password'
export BRAIN_SOURCE_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export BRAIN_SOURCE_DB="$PWD/data/brain_source.sqlite3"
export BRAIN_SOURCE_COOKIE_SECURE=0  # local HTTP only; set to 1 behind HTTPS in production
uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000` (not the file directly) and click **Cloud sign in**. Sign in with the administrator password. Existing local results and server results are merged by attempt ID, then saved to the server. Subsequent saves sync while that admin session remains active. The session planner is available in Participants after signing in.

The database is stored at `data/brain_source.sqlite3` by default. Keep that directory on persistent storage. Set a unique admin password and secret key through the hosting provider's environment settings; never commit real secrets to source control.

## Docker

From the project root:

```bash
docker build -f backend/Dockerfile -t brain-source .
mkdir -p data
docker run --rm -p 8000:8000 \
  -e BRAIN_SOURCE_ADMIN_PASSWORD='use-a-long-unique-password' \
  -e BRAIN_SOURCE_SECRET_KEY='replace-with-a-long-random-secret' \
  -e BRAIN_SOURCE_DB=/app/data/brain_source.sqlite3 \
  -e BRAIN_SOURCE_COOKIE_SECURE=0 \
  -v "$PWD/data:/app/data" brain-source
```

For a public deployment, terminate HTTPS at the hosting platform or reverse proxy and set `BRAIN_SOURCE_COOKIE_SECURE=1`. Use a persistent volume for `/app/data`. Do not expose a public HTTP-only deployment. See `DEPLOYMENT.md` for production notes and `backend/` for the API.

## Server API included

- `POST /api/login`, `POST /api/logout`, `GET /api/me`
- `GET /api/data`, `PUT /api/data` for authenticated data sync
- `GET /api/appointments`, `POST /api/appointments`, `PATCH/DELETE /api/appointments/{id}`
- `PUT /api/drafts`, `GET /api/drafts/{participant}/{draft_id}` for authenticated recovery snapshots
- `GET /api/export.csv` and `GET /api/admin/audit`
- `GET /api/health`

API documentation is disabled by default. For local development only, set `BRAIN_SOURCE_SHOW_API_DOCS=1` to enable `/api/docs`.

## Data, safety, and limits

- Local browser mode stores data in localStorage. Local server mode stores the app dataset, appointments, recovery drafts, sessions, and a minimal audit log in SQLite. Hosted mode can use PostgreSQL through `BRAIN_SOURCE_DATABASE_URL` so data is not lost with an ephemeral web-service filesystem.
- Server access requires an administrator password. The server uses HTTP-only, SameSite=Strict session cookies and rejects cross-origin write requests. Add platform-level HTTPS, persistent storage, rate limiting, monitoring, and automated backups before public deployment.
- The app is an educational prototype, not a validated IQ/EQ, medical, or clinical assessment. “IQ-style” and “EQ-style” outputs are task-performance estimates, not real IQ or EQ scores.
- English/Arabic interface labels and RTL layout are included, but the question bank is not yet fully translated and psychometrically equated into Arabic. Do not compare language versions as equivalent until translated, piloted, and reviewed.
- No live website has been deployed from this workspace; a hosting account and deployment configuration are still needed.

## Free public hosting: Render + Neon PostgreSQL

This is the intended **$0/month hobby/demo configuration**. It is not always-on: Render's free web service sleeps after inactivity and may take about a minute to wake. Neon has its own free-plan usage and storage limits. Check both providers' current limits before collecting important data. Render free web-service files are temporary, so do not rely on SQLite in the hosted environment. Render documents the free-service filesystem and sleep limitations here: https://render.com/docs/free. Neon free-plan limits are documented here: https://neon.com/pricing.

1. Create a free PostgreSQL project at [Neon](https://neon.tech/).
2. In Neon, copy the PostgreSQL connection string for your database. Keep it private; it includes credentials. Use the pooled connection string if Neon presents one, and make sure SSL is enabled (`sslmode=require`).
3. Create a private GitHub repository and upload the contents of this project folder, including `render.yaml`, `backend/`, and `index.html`. Do not upload `.env`, local data, passwords, or database URLs.
4. Open [Render](https://dashboard.render.com/) → **New** → **Blueprint**, then connect your repository and review the Blueprint. It is configured for a free web service with no persistent disk.
5. When asked for `BRAIN_SOURCE_ADMIN_PASSWORD`, set a strong unique password. Render generates `BRAIN_SOURCE_SECRET_KEY`. For `BRAIN_SOURCE_DATABASE_URL`, paste the Neon connection string. Never put these secrets in source code or chat.
6. Deploy. Wait for the service to become live, then open the generated `https://...onrender.com` URL and visit `/api/health`. It should show `ok: true`, `database: "postgresql"`, and `admin_configured: true`.
7. Use **Cloud sign in** and test with dummy participant records. Verify that records remain after a redeploy before collecting any real observations. Export CSV backups periodically.

### Free-tier limitations

- Render free web services spin down after 15 minutes of inactivity and can take about a minute to wake.
- Render's free web filesystem is ephemeral. The Blueprint deliberately does not attach a disk; it requires an external PostgreSQL URL for persistent records.
- Neon free databases have usage/storage limits and can suspend compute when quotas are exhausted. The free service/database setup is suitable for a small science-fair demo, not critical or regulated records.
- No public deployment is performed automatically by this ZIP. You must connect your own GitHub, Render, and Neon accounts and approve the deployment.

## Paid hosting option

For always-on use, larger participant groups, or higher reliability, choose a paid web service and a database with backups. A persistent disk plus SQLite is supported for a small single-instance deployment, but PostgreSQL is the preferred hosted configuration.
