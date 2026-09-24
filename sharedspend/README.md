# SharedSpend

SharedSpend is a shared-budget and personal-expense application for one person and their invited friends or family. It is intended for a small trusted circle, not as a public SaaS product. Personal transactions stay private to the user who recorded them; group transactions and budgets are available to authorized group members.

## Architecture and current database status

The frontend is React + TypeScript + Vite. The backend is FastAPI with SQLAlchemy async ORM and Pydantic schemas. Versioned API routes are mounted at `/api/v1`; frontend API clients are under `frontend/src/api/`. Alembic manages schema migrations. Local development defaults to SQLite. PostgreSQL URL support and the async driver are implemented, with Neon Free as the planned shared-database target, but no live PostgreSQL/Neon integration has been verified. Do not treat the shared-database setup as production-ready until it has been tested against a real PostgreSQL instance.

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
```

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

Local development can continue using the default SQLite database. The intended shared-database direction for private use across devices is managed PostgreSQL, with Neon Free as the current candidate. PostgreSQL URL handling and Alembic support exist, but live Neon/PostgreSQL connectivity, migrations, and runtime behavior have not yet been verified. Treat these instructions as setup guidance for a controlled test, not as evidence of production readiness. Keep `backend/.env` and all database credentials private.

```dotenv
APP_ENV=production
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB?sslmode=require
SECRET_KEY=<a long random secret>
```

The application selects SQLAlchemy's async PostgreSQL driver from a standard
`postgresql://` URI. Every backend instance must use the same `DATABASE_URL`
and `SECRET_KEY`. Run migrations against a new database before starting the
backend:

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

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

Do not share Neon credentials in source control or use this same database URL
for automated tests.
