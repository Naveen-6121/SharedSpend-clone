from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, budgets, categories, categorizer, groups, transactions, users, analytics
from app.api.categories import seed_global_categories
from app.config import settings
from app.db.engine import AsyncSessionLocal, engine
from app.db.base import Base
import app.models  # noqa: F401 — register all ORM models


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (Alembic should manage schema in production; this is a dev safety net)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed global categories
    async with AsyncSessionLocal() as db:
        await seed_global_categories(db)

    yield
    # Cleanup (nothing needed for SQLite)
    await engine.dispose()


app = FastAPI(
    title="SharedSpend API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/v1"
app.include_router(auth.router, prefix=PREFIX)
app.include_router(users.router, prefix=PREFIX)
app.include_router(groups.router, prefix=PREFIX)
app.include_router(budgets.router, prefix=PREFIX)
app.include_router(categories.router, prefix=PREFIX)
app.include_router(transactions.router, prefix=PREFIX)
app.include_router(categorizer.router, prefix=PREFIX)
app.include_router(analytics.router, prefix=PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok"}
