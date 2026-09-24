from __future__ import annotations

from uuid import uuid4

from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

database_url = settings.async_database_url
parsed_database_url = make_url(database_url)
connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
engine_options = {}

# Neon pooled endpoints use PgBouncer. Avoid client-side connection pooling and
# give prepared statements unique names when talking to that endpoint.
if parsed_database_url.host and "-pooler." in parsed_database_url.host:
    engine_options["poolclass"] = NullPool
    connect_args["prepared_statement_name_func"] = lambda: f"__asyncpg_{uuid4()}__"

engine = create_async_engine(
    database_url,
    echo=False,
    future=True,
    connect_args=connect_args,
    **engine_options,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
