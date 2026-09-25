from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path


def test_alembic_upgrade_creates_current_runtime_columns():
    backend = Path(__file__).resolve().parents[1]
    filename = f"schema-check-{uuid.uuid4().hex}.db"
    database_path = backend / ".pytest_cache" / filename
    database_path.parent.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///./.pytest_cache/{filename}"
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        tx_columns = {row[1] for row in connection.execute("PRAGMA table_info(transactions)")}
        user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        settlement_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(settlement_records)")
        }
    assert revision == "f54d2e96b1c7"
    assert {
        "add_to_settlement", "settlement_record_id", "settlement_group_id",
        "settlement_participant_ids",
    }.issubset(tx_columns)
    assert "is_admin" in user_columns
    assert {
        "original_transaction_id", "original_description", "original_amount",
        "original_transaction_date",
    }.issubset(settlement_columns)


def test_relative_sqlite_url_is_stable_from_any_launch_directory():
    backend = Path(__file__).resolve().parents[1]
    from app.config import Settings

    configured = Settings(DATABASE_URL="sqlite+aiosqlite:///./sharedspend.db")
    assert configured.async_database_url == f"sqlite+aiosqlite:///{backend / 'sharedspend.db'}"


def test_neon_postgresql_url_uses_asyncpg_ssl_parameter():
    from app.config import Settings
    from sqlalchemy.engine import make_url

    configured = Settings(
        DATABASE_URL=(
            "postgresql://test:encoded%40password@ep-test-pooler.us-east-2.aws.neon.tech/"
            "sharedspend?sslmode=require&channel_binding=require&application_name=sharedspend"
        )
    )

    parsed = make_url(configured.async_database_url)
    assert parsed.drivername == "postgresql+asyncpg"
    assert parsed.password == "encoded@password"
    assert parsed.query["ssl"] == "require"
    assert "sslmode" not in parsed.query
    assert "channel_binding" not in parsed.query
    assert parsed.query["application_name"] == "sharedspend"
    assert "-pooler." in parsed.host


def test_asyncpg_url_keeps_existing_ssl_and_pooler_parameters():
    from app.config import Settings
    from sqlalchemy.engine import make_url

    configured = Settings(
        DATABASE_URL=(
            "postgresql+asyncpg://test:secret@ep-test-pooler.us-east-2.aws.neon.tech/"
            "sharedspend?ssl=require&prepared_statement_cache_size=0"
        )
    )

    parsed = make_url(configured.async_database_url)
    assert parsed.drivername == "postgresql+asyncpg"
    assert parsed.query["ssl"] == "require"
    assert parsed.query["prepared_statement_cache_size"] == "0"


def test_postgresql_ssl_parameters_must_not_conflict():
    import pytest
    from app.config import Settings

    configured = Settings(
        DATABASE_URL="postgresql+asyncpg://test:secret@localhost/db?ssl=require&sslmode=disable"
    )
    with pytest.raises(ValueError, match="ssl and sslmode options conflict"):
        _ = configured.async_database_url


def test_postgresql_alembic_upgrade_generates_schema_sql():
    backend = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost/sharedspend"
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "settlement_group_id" in completed.stdout
    assert "settlement_participant_ids" in completed.stdout
    assert "f54d2e96b1c7" in completed.stdout
