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
