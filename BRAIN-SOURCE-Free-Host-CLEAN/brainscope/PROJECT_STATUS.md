# BRAIN SOURCE — implementation and QA status

## Working in the delivered project
- Branded **BRAIN SOURCE** with a responsive English/Arabic interface and RTL layout.
- Eight activities: logical reasoning, pattern recognition, response speed, emotion recognition, memory, concentration, mental mathematics, and general knowledge.
- Randomized question selection and answer-choice order for choice-based activities; official attempts avoid repeating an identical full set when possible.
- Ten randomized reaction-time trials with a variable wait before the target appears and measured response time.
- A separate 40-question mixed final, five questions from each of the eight activity categories, unlocked after all eight individual official activities are completed.
- Category/task scores and a single 1–100 Overall Task Performance Index after the individual tests and mixed final are complete. IQ-style and EQ-style labels are educational task composites, not validated IQ/EQ measurements.
- Local browser storage for results, CSV export, dashboard charts, report rendering/printing, and best-effort unfinished-session recovery.
- Optional FastAPI backend served from the same origin; SQLite is used locally and PostgreSQL is supported for hosted deployments.
- Administrator login with HTTP-only, SameSite=Strict session cookie; authenticated data sync; session planner UI; API endpoints for appointments, recovery drafts, CSV export, and a minimal audit log.
- Local-only use remains available when no server is configured.
- Deployment files: `backend/Dockerfile`, `backend/requirements.txt`, `.env.example`, `render.yaml`, `DEPLOYMENT.md`, `.gitignore`, and a consistent SQLite backup helper.

## Verification performed
| Check | Result | Notes |
|---|---|---|
| Frontend JavaScript syntax | PASS | Extracted inline script passed `node --check`. |
| Backend Python syntax | PASS | `py_compile` passed for API and backup helper. |
| Backend API smoke tests | PASS | Tested health, unauthenticated rejection, invalid/valid login, result sync/readback, recovery draft create/list/read/delete, appointment create/list/delete, CSV export, and logout. Synthetic test records were stored in a temporary database and deleted afterward. |
| Full browser test of new cloud UI | NOT COMPLETED | Chromium could not navigate to the local test server in this environment (`ERR_BLOCKED_BY_ADMINISTRATOR`); do a final browser check after starting the app on the user's machine. |
| Full 40-question mixed test | PASS IN PRIOR PROTOTYPE | Previous version completed a scripted 40-question run. The newest server integration changes were not subjected to that full end-to-end run. |
| Live public deployment | NOT DONE | No hosting account, domain, or production secrets were available. |

## Still needed before calling it production-ready
- Deploy to a chosen host, configure HTTPS and environment secrets, set up backups and rate limiting, and monitor the service. Free Render hosting uses external PostgreSQL; paid SQLite hosting can use a persistent disk.
- Run final manual browser QA for local mode, cloud login/sync, appointment management, logout, and session recovery.
- The English question bank is not yet fully translated into equivalent Arabic items. Arabic labels/RTL exist, but the two languages must not be treated as psychometrically equivalent.
- Activity question banks and answer keys remain in frontend JavaScript. Server-side scoring/answer-key protection is not complete.
- The current auth is a single administrator password, not a full user-registration, role-management, or guardian-consent system.
- Appointment/session planning is available after admin sign-in, but automatic email/SMS reminders are not configured.
- SQLite is suitable for a small science fair deployment; larger use should move to a managed database and shared session/rate-limit storage.
- This is an educational prototype, not a validated clinical assessment or real IQ/EQ test. Avoid diagnostic claims and avoid collecting identifying participant information without an approved need and consent process.


## Unified Project Hub update (November 2026)

- Added a dedicated **Project Hub** view inside `index.html` so app navigation, activity launch, results, research report, local setup, server setup, deployment guidance, project documents, and the complete-project download are presented in one website interface.
- Added responsive layouts and English/Arabic interface strings for the hub, including browser-only and persistent-database paths.
- Added relative download links for the project ZIP, README, deployment guide, and project status. These links require the whole project folder (and the ZIP file alongside the website) to be uploaded together.
- Updated the Arabic mixed-final description to correctly state that all eight activities must be completed first.
- JavaScript syntax check passes. A browser smoke test could not run in this environment because Chromium navigation to the local test server was blocked by the environment's administrator policy; therefore, do not treat the new hub as fully browser-validated yet.


## Hosting preparation update (2026-11-02)
- Added Render Docker hosting configuration with HTTPS edge termination, health check, generated secret key, and secure cookies.
- Updated Docker startup to bind to the platform-provided `PORT` (defaulting to 10000).
- Current free Blueprint uses an external PostgreSQL URL; no persistent disk is attached.
- Not deployed publicly: the user must connect their own GitHub repository, Render account, and Neon database and provide secrets.


## Free-hosting preparation update (2026-11-02)
- Added a shared database adapter: local use remains SQLite; hosted mode uses PostgreSQL when `BRAIN_SOURCE_DATABASE_URL` is set. Added `psycopg2-binary` dependency.
- Changed `render.yaml` to a free Render web service with no persistent disk and an external PostgreSQL URL secret, avoiding data loss from SQLite on Render's ephemeral free filesystem. The app now refuses to start on Render if the persistent database URL is missing.
- Updated README and deployment guide for Render + Neon free-tier setup and clearly documented free-tier sleep/quota limitations.
- Updated the in-app Project Hub text so it no longer promises SQLite persistence for hosted free mode.
- **Post-change verification:** Python syntax passes, JavaScript syntax passes, Render YAML parses, and 19 backend API checks pass with a temporary SQLite database. Live PostgreSQL integration cannot be verified without a real database URL. Browser navigation was blocked by this environment's administrator policy; full browser QA remains unverified.
- Still not published: you must connect your own GitHub, Render, and Neon accounts and configure secrets. Full question-bank Arabic translation and equivalent validation remain incomplete.
