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
the two-user Chromium browser flow. It does not connect to or write to Neon.
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
| DATABASE_URL | sqlite+aiosqlite:///./sharedspend.db | Database connection string |
| APP_ENV | development | SQLite `create_all` is enabled only for local development |
| SECRET_KEY | (required) | JWT signing key |
| ACCESS_TOKEN_EXPIRE_MINUTES | 15 | Access token TTL |
| REFRESH_TOKEN_EXPIRE_DAYS | 7 | Refresh token TTL |
| CORS_ORIGINS | http://localhost:5173 | Allowed CORS origins (comma-separated) |

## Shared PostgreSQL with Neon

Local development can continue using the default SQLite database. The intended shared-database direction for private use across devices is managed PostgreSQL, with Neon Free as the current candidate. PostgreSQL URL handling, Alembic migrations, client TLS, and runtime API behavior were verified against one disposable Neon database on 2026-09-25. This is integration evidence only, not production readiness. Keep using a disposable branch/database for repeats. Keep `backend/.env` and all database credentials private.

```dotenv
APP_ENV=production
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB?sslmode=require
SECRET_KEY=<a long random secret>
```

The application selects SQLAlchemy's async PostgreSQL driver from a standard
`postgresql://` or `postgres://` URI. Neon URLs using `sslmode=require` are
normalized to asyncpg's `ssl=require`, so the connection requires TLS. The
asyncpg driver does not accept Neon/libpq's `channel_binding` URL option; the
application removes that option. The pooled-endpoint engine settings remain in
place. Every backend instance must use the same `DATABASE_URL` and `SECRET_KEY`.
Keep them in the ignored `backend/.env` file or the deployment secret store;
never paste the URL into commands, tickets, logs, or source control.

Run migrations deliberately from the backend directory before starting the
application. Prefer Neon’s direct connection for schema migration; use the
pooled URI for the app if required by the deployment:

```bash
cd backend
alembic current
alembic upgrade head
alembic current
python -m app.cli db-status
uvicorn app.main:app --reload --port 8000
```

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
TLS. `python -m app.cli db-status` checks the active client's TLS transport; the
current disposable Neon connection reported TLS enabled.
Use a disposable Neon branch/database for integration tests, never production
or personal data. `backend/tests/test_postgres_live.py` creates uniquely named
synthetic rows and removes only the rows created by that invocation in its
scoped cleanup block. From `backend`, after configuring the disposable URL
in the ignored `.env` and applying migrations, opt in explicitly in PowerShell:

```powershell
$env:SHAREDSPEND_LIVE_POSTGRES = "1"
pytest tests/test_postgres_live.py -q
Remove-Item Env:SHAREDSPEND_LIVE_POSTGRES
```

The test verifies client TLS, tables and Alembic head, the authenticated database
health endpoint, persisted records, and a two-user/two-group API scenario. It
passed against the configured disposable Neon database on 2026-09-25. A separate
manual browser smoke through the actual frontend and FastAPI backend also passed
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
| Python | `3.12.14`, matching the local backend environment |
| Build command | `pip install -r requirements.txt` |
| Start command | `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health` |

The start command applies pending Alembic migrations before starting the API.
Keep this service at one instance while migrations run at startup. If you later
scale to multiple instances, move migration execution to a single pre-deploy
step on a Render plan that supports it. The existing health endpoint returns
only `{"status":"ok"}`; it does not probe Neon.

Set these backend environment variables in Render:

- `APP_ENV=production`
- `DATABASE_URL`: the existing Neon PostgreSQL connection URL; do not create a
  Render database.
- `SECRET_KEY`: a strong random value with at least 32 characters.
- `ACCESS_TOKEN_EXPIRE_MINUTES=15`
- `REFRESH_TOKEN_EXPIRE_DAYS=7`
- `CORS_ORIGINS`: the exact HTTPS origin of the deployed frontend, without a
  path, trailing slash, wildcard, or localhost. The Blueprint leaves this as a
  dashboard-supplied value because the static-site URL is assigned by Render.

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
   Render dashboard. Never put either value in Git, this README, or logs. Enter
   the exact frontend HTTPS origin for `CORS_ORIGINS`. Render assigns that URL
   during service creation; if the prompt appears before the URL is visible,
   use a temporary `https://pending.invalid` value, complete creation, then
   replace it with the actual frontend URL before normal use.
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
