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
| SECRET_KEY | (required) | JWT signing key |
| ACCESS_TOKEN_EXPIRE_MINUTES | 15 | Access token TTL |
| REFRESH_TOKEN_EXPIRE_DAYS | 7 | Refresh token TTL |
| CORS_ORIGINS | http://localhost:5173 | Allowed CORS origins (comma-separated) |
