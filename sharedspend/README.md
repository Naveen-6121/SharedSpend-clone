# SharedSpend

A shared budget + personal expense tracker for two or more people.

## Quick Start (Backend)

```bash
cd sharedspend/backend
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
cd sharedspend/backend
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

Local development can continue using the default SQLite database. To let
multiple machines use the same SharedSpend data, create a Neon PostgreSQL
database and put its connection URI in `backend/.env` (copy
`backend/.env.example` first). Use the pooled URI from Neon when running
multiple app instances. Keep this file and its credentials private.

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
