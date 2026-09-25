# SharedSpend

SharedSpend is a shared-budget and personal-expense application for one person and their invited friends or family. It is intended for a small trusted circle, not as a public SaaS product. Personal transactions stay private to the user who recorded them; group transactions and budgets are available to authorized group members.

## Architecture and current database status

The frontend is React + TypeScript + Vite. The backend is FastAPI with SQLAlchemy async ORM and Pydantic schemas. Versioned API routes are mounted at `/api/v1`; frontend API clients are under `frontend/src/api/`. Alembic manages schema migrations. Local development defaults to SQLite. PostgreSQL URL support and the async driver are implemented. Live migrations and a real-route integration flow were verified against a disposable Neon database on 2026-09-25. Production deployment, backups, restore, and deployment security are not verified; do not treat the app as production-ready.

## Quick Start (Backend)

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Copy env
cp .env.example .env

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Running Tests

```bash
cd backend
pytest -v

cd ../frontend
npm test
npm run build
npm run test:e2e
```

`test:e2e` starts the checkout's FastAPI backend with an isolated in-memory
SQLite database and a temporary signing key, starts Vite on port 5174, and runs
the two-user Chromium browser flow. The runner overrides any inherited
`TEST_DATABASE_URL` with an empty value in its backend process; it does not
connect to or write to Neon.
Install the Playwright Chromium browser once with `npx playwright install chromium`
if it is not already present.

## Neon latency and frontend loading

The Neon pooled endpoint has a measurable cold/resume cost: a cold connection
and `SELECT 1` took about 1.24 seconds in the latest check; an earlier sample
coincided with a just-resumed database. The app intentionally retains its
PgBouncer-compatible connection settings. Dashboard and Analytics requests are
concurrent, with a 30-second React Query stale window. Analytics service
queries were consolidated to reduce database round trips, and page-level lazy
loading reduces the initial JavaScript entry from about 1,069 kB (317 kB gzip)
to 380 kB (119 kB gzip). Analytics and XLSX code are separate chunks, loaded
when their screens/actions are used. These are measured improvements, not a
claim that Neon cold starts or network latency have been eliminated.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| DATABASE_URL | sqlite+aiosqlite:///./sharedspend.db | Local SQLite or production database URL; ignored in staging |
| TEST_DATABASE_URL | unset | Required Neon test URL when `APP_ENV=staging`; ignored by development and rejected in production |
| APP_ENV | development | `development` uses local config, `staging` requires `TEST_DATABASE_URL`, `production` uses `DATABASE_URL` |
| SECRET_KEY | (required) | JWT signing key |
| ACCESS_TOKEN_EXPIRE_MINUTES | 15 | Access token TTL |
| REFRESH_TOKEN_EXPIRE_DAYS | 7 | Refresh token TTL |
| CORS_ORIGINS | Local development defaults to http://localhost:5173; required in production | Allowed HTTPS site origins in production (comma-separated) |

## Database environment separation

Use separate settings for local development, Neon test/staging, and production.
The test database URL is never substituted for `DATABASE_URL` implicitly:

| Environment | `APP_ENV` | Database setting | Behavior |
|---|---|---|---|
| Local | `development` | `DATABASE_URL=sqlite+aiosqlite:///./sharedspend.db` (default) | SQLite schema creation is enabled for local development. If `TEST_DATABASE_URL` is present in `.env`, it is ignored; local mode rejects PostgreSQL `DATABASE_URL`. |
| Test/staging | `staging` | `TEST_DATABASE_URL=<Neon TEST connection string>` | A PostgreSQL test URL is required. `DATABASE_URL` is not used for connection selection. There is no fallback when the test URL is missing. |
| Production | `production` | `DATABASE_URL=<Neon PRODUCTION connection string>` in Render | Production continues to use `DATABASE_URL`; setting `TEST_DATABASE_URL` is rejected. Keep the production URL and `SECRET_KEY` only in Render's environment settings. |

The actual test and production URLs are placeholders above; never replace them
with credentials in this README or any tracked file. Keep real URLs and
passwords in the ignored local `backend/.env` file, process environment, or the
appropriate deployment secret store. Do not copy production users, passwords, transactions, or other
family data into the test project. The prior disposable-Neon integration run
proves PostgreSQL support, not that either current Render production or Neon
TEST dashboard configuration has been inspected.

The application selects SQLAlchemy's async PostgreSQL driver from a standard
`postgresql://` or `postgres://` URI. Neon URLs using `sslmode=require` are
normalized to asyncpg's `ssl=require`, so the connection requires TLS. The
asyncpg driver does not accept Neon/libpq's `channel_binding` URL option; the
application removes that option. The pooled-endpoint engine settings remain in
place. Production backend instances must use the same production `DATABASE_URL`
and `SECRET_KEY`. Staging reads only `TEST_DATABASE_URL`; development ignores
it, and production rejects it if configured.

The checked-in Render Blueprint declares `DATABASE_URL` as a dashboard-managed
production variable and does not declare `TEST_DATABASE_URL` or create a
database. Its value is intentionally not stored in Git. The Blueprint alone
cannot prove which Neon project is configured in an existing Render dashboard;
verify that secret there without copying it into source control.

Run migrations deliberately for the selected environment before starting the
application. Startup never runs Alembic migrations automatically. For local
SQLite, use `APP_ENV=development` and the local `DATABASE_URL`. For test/staging,
make the Neon TEST connection available as `TEST_DATABASE_URL` in the ignored
`backend/.env` or the private process environment, then select `APP_ENV=staging`.
Staging chooses only `TEST_DATABASE_URL`; it does not use the `.env`
`DATABASE_URL`. For additional protection when a local `.env` contains a
production URL, use an isolated shell and a harmless SQLite process override
for `DATABASE_URL`. On Windows PowerShell:

```powershell
cd backend
$env:APP_ENV = "staging"
$env:DATABASE_URL = "sqlite+aiosqlite:///:memory:"
alembic current
alembic upgrade head
alembic current
python -m app.cli db-status
$env:SHAREDSPEND_LIVE_POSTGRES = "1"
pytest tests/test_postgres_live.py -q
Remove-Item Env:SHAREDSPEND_LIVE_POSTGRES
Remove-Item Env:APP_ENV
Remove-Item Env:TEST_DATABASE_URL
Remove-Item Env:DATABASE_URL
```

The live integration test requires both `APP_ENV=staging` and
`TEST_DATABASE_URL` in configuration. It will not fall back to
`DATABASE_URL`. It creates uniquely named synthetic rows and removes only rows
created by that invocation. Do not run it against production or personal data.

Production migrations are also manual. Run them only in an isolated one-off
environment that does not load a local `.env` containing `TEST_DATABASE_URL`.
Only after confirming the production target in Render, taking the appropriate
backup, and planning the maintenance window, run Alembic from a one-off shell
with `APP_ENV=production` and the existing production `DATABASE_URL` loaded
from the approved secret store. Run
`alembic current`, `alembic upgrade head`, and `alembic current` there before
starting or scaling the API. Never use `TEST_DATABASE_URL` for that procedure.
The Render start command only launches Uvicorn and does not apply schema
changes. Do not run production migrations as part of app startup.

`db-status` checks connectivity and prints the driver, database name, TLS
state, current Alembic revision(s), expected head(s), table names, and core row
counts. It never prints the connection URL, password, or table contents. The
authenticated `/api/v1/admin/database` endpoint also reports connection and
migration status. `/health` reports only that the API process is responding.

To inspect the database in Neon Console, open the SQL Editor for the test
branch/database and run read-only queries such as:

```sql
SELECT current_database(), current_user;
SELECT version_num FROM alembic_version ORDER BY version_num;
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' ORDER BY table_name;
SELECT id, name, currency FROM groups ORDER BY name;
SELECT id, date, type, amount, group_id
FROM transactions ORDER BY date DESC LIMIT 25;
```

The SQL Editor is a safe place to view test data without copying connection
secrets into a terminal. Treat transaction data and screenshots as private.
For a pooled Neon URL, `pg_stat_ssl` describes the pooler's server-side
connection and may report false even when the client-to-pooler connection uses
TLS. `python -m app.cli db-status` checks the active client's TLS transport.
Use only the separate Neon TEST project for live integration tests, never
production or personal data. `backend/tests/test_postgres_live.py` creates
uniquely named synthetic rows and removes only rows created by that invocation
in its scoped cleanup block. The current Neon TEST project was migrated and
validated on 2026-09-25: TLS was enabled, all expected tables were present,
Alembic was at `f54d2e96b1c7`, and the live two-user/two-group scenario passed.
The post-test status showed no remaining synthetic users, groups, or
transactions. The separate Render production database was not accessed.

The test verifies client TLS, tables and Alembic head, the authenticated database
health endpoint, persisted records, and a two-user/two-group API scenario. It
passed against the current Neon TEST database on 2026-09-25. A separate manual
browser smoke through the actual frontend and FastAPI backend also passed
registration, group creation, budget save, shared transaction, and Dashboard/
Analytics/Forecast consistency against Neon. The live test removes its own
synthetic rows after the run. Do not use it on production or personal data.

SQLite schema creation is retained for local development only. Production
startup does not create or upgrade tables automatically. After registering the
account that should administer the app, promote that existing account from the
backend directory:

```bash
python -m app.cli promote-admin <username>
```

If you already have a local SQLite file created by the earlier
`create_all`-based app, make a copy of the database file first. For a database
that has the existing SharedSpend tables, run `alembic stamp 229e3412032a`
followed by `alembic upgrade head` from `backend`; this records the existing
baseline without recreating it, then applies the additive admin/settlement
migration. Do not stamp an unrelated or incomplete database.

Do not share Neon credentials in source control. Use only a dedicated
disposable database URL for live automated tests; never use production or
personal data.

## Render deployment preparation

The Render Blueprint is [`render.yaml`](render.yaml) in this application
directory. When creating a Blueprint from the `SharedSpend-clone` GitHub
repository, select `sharedspend/render.yaml` as its Blueprint file. It defines
one Python web service and one static site under the nested `sharedspend/`
directory. It does not create a database: the backend uses the existing Neon
PostgreSQL database. Both services have automatic deploys disabled so a later
GitHub push does not deploy until you choose to deploy from Render.

### Backend web service

| Setting | Value |
|---|---|
| Service type/runtime | Web Service / Python |
| Root directory | `sharedspend/backend` (relative to repository root) |
| Python | `3.11`, pinned in `backend/.python-version` for Render |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health` |

The backend Python version is pinned separately in `backend/.python-version`;
Render's Python selection supports a major/minor value and selects the latest
matching patch. Requirements remain unchanged. The service start command does
not modify the database schema. Confirm the existing Neon database is at the
current Alembic head before startup; run any future migrations deliberately as
a single operation before starting or scaling API instances. The existing
health endpoint returns only `{"status":"ok"}`; it does not probe Neon.

Set these backend environment variables in Render:

- `APP_ENV=production`
- `DATABASE_URL`: the existing Neon PostgreSQL connection URL; do not create a
  Render database.
- `SECRET_KEY`: a strong random value with at least 32 characters.
- `ACCESS_TOKEN_EXPIRE_MINUTES=15`
- `REFRESH_TOKEN_EXPIRE_DAYS=7`
- `CORS_ORIGINS`: one or more comma-separated HTTPS site origins, without a
  path, trailing slash, wildcard, or localhost. The Blueprint leaves this as a
  dashboard-supplied value because the static-site URL is assigned by Render.

The `sync: false` CORS setting has no committed origin. After Render assigns the
static site's URL, set the backend service's `CORS_ORIGINS` in the Dashboard to
that exact HTTPS origin (scheme and host only), then redeploy the backend. For
an existing Blueprint, update this value in the service's Environment settings;
Render does not resync `sync: false` values on later Blueprint updates. A
missing or invalid production origin fails closed with a setup error; the local
Vite origin is supplied only when running in development. Do not leave a
temporary bootstrap origin in place for normal use.

Production startup rejects the development signing key, SQLite, a short secret,
and wildcard, localhost, or non-HTTPS CORS origins. The local SQLite defaults
remain available when `APP_ENV=development`.

### Frontend static site

| Setting | Value |
|---|---|
| Service type | Static Site |
| Root directory | `sharedspend/frontend` (relative to repository root) |
| Build command | `npm ci && npm run build` |
| Publish directory | `dist` |
| SPA routing | Rewrite unmatched paths to `/index.html` |
| API base URL | `VITE_API_BASE_URL`, supplied from the backend service's Render public URL |

Vite bakes `VITE_API_BASE_URL` into the production bundle at build time. The
Blueprint references the backend's `RENDER_EXTERNAL_URL`; the existing API
client appends `/api/v1`. If you later attach a custom backend domain, update
this frontend environment variable and rebuild. If you attach a custom
frontend domain, update backend `CORS_ORIGINS` to that exact origin.

### Initial Render setup and verification

1. Push the prepared commit to the GitHub repository yourself; this work does
   not push or deploy. In Render, create a Blueprint from that repository and
   select `sharedspend/render.yaml`.
2. Enter the existing Neon URL and a strong random `SECRET_KEY` directly in the
   Render dashboard. Never put either value in Git, this README, or logs. Set
   `CORS_ORIGINS` to the static site's exact HTTPS origin as soon as Render
   assigns it. If Render requests this dashboard-only value before the frontend
   URL exists, leave it unset if the form permits; the backend will remain
   stopped until the real origin is entered. If Render requires a temporary
   value to create the services, use an explicit HTTPS validation origin only
   in the dashboard and replace it with the assigned frontend URL before
   allowing frontend API traffic. Never commit a temporary origin as production
   configuration.
3. After both services report Live, verify the backend `/health` returns HTTP
   200 and the frontend login route loads. Confirm the frontend's
   `VITE_API_BASE_URL` resolves to the backend URL and backend CORS lists the
   frontend origin.
4. Log in as Naveen and Alekhya. Check group switching and permissions, shared
   and personal transactions, budgets and budget copy, Dashboard/Analytics/
   Forecast consistency, settlements and payment history, filtered CSV and
   XLSX downloads, dark mode, and in-app budget alerts. Check admin only with
   an account intentionally promoted as global admin.
5. Confirm the API and Neon records after each write using the safe `db-status`
   and read-only SQL inspection steps above. Do not run synthetic live tests
   against personal data.

This Blueprint selects Render's Free web-service plan to avoid creating a
charge. Render describes Free services as suitable for testing/hobby projects,
not production; they spin down after 15 minutes idle and can take about a minute
to start again. Review Render's current [Free instance limitations](https://render.com/docs/free)
before relying on it for regular family use. A paid plan avoids idle spin-down;
choose and authorize that plan in the Dashboard if it fits your needs.

Render deployment itself has not been performed or verified from this checkout.

Render configuration references: [Blueprint YAML reference](https://render.com/docs/blueprint-spec), [Python version selection](https://render.com/docs/python-version), and [static-site rewrites](https://render.com/docs/redirects-rewrites).
