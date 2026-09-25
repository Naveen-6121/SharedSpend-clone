"""Opt-in live PostgreSQL integration test for a disposable test database.

Run after applying Alembic migrations with DATABASE_URL configured in
backend/.env: set SHAREDSPEND_LIVE_POSTGRES=1, then run pytest for this file.
This test creates uniquely named users, groups, budgets, transactions, and
settlement rows, then removes only fixtures belonging to its unique run ID. It
never deletes or modifies pre-existing rows.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, inspect, or_, select, text, update

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.api.categories import seed_global_categories
from app.config import settings
from app.db.engine import AsyncSessionLocal, engine
from app.db.session import get_db
from app.main import app
from app.models.budget import BudgetPeriod
from app.models.category import Category
from app.models.group import Group, GroupMember
from app.models.settlement import SettlementRecord
from app.models.transaction import Transaction
from app.models.user import User
from tests.conftest import auth_headers, register_user
from tests.test_regression_consistency import (
    exercise_cross_screen_group_period_visibility_and_budget_consistency,
)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("SHAREDSPEND_LIVE_POSTGRES") != "1",
    reason="set SHAREDSPEND_LIVE_POSTGRES=1 only for an explicitly selected disposable database",
)
async def test_live_postgres_migrations_admin_and_two_user_app_flow():
    assert not settings.is_sqlite, "Live PostgreSQL test opt-in requires a PostgreSQL DATABASE_URL"

    async with engine.connect() as connection:
        server = (await connection.execute(text("SELECT version()"))).scalar_one()
        assert "postgresql" in server.lower()
        raw_connection = await connection.get_raw_connection()
        driver_connection = raw_connection.driver_connection
        transport = getattr(driver_connection, "_transport", None)
        client_tls = bool(transport and transport.get_extra_info("ssl_object"))
        assert client_tls, "PostgreSQL client connection must use TLS"

        tables = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
        assert {
            "users", "groups", "group_members", "budget_periods", "transactions",
            "settlement_records", "categories", "alembic_version",
        }.issubset(tables)
        current = set((await connection.execute(
            text("SELECT version_num FROM alembic_version")
        )).scalars().all())
        before = {
            "users": (await connection.execute(text("SELECT count(*) FROM users"))).scalar_one(),
            "groups": (await connection.execute(text("SELECT count(*) FROM groups"))).scalar_one(),
            "transactions": (await connection.execute(text("SELECT count(*) FROM transactions"))).scalar_one(),
        }

    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")
    heads = set(ScriptDirectory.from_config(Config(config_path)).get_heads())
    assert current == heads, f"Database migration revisions do not match Alembic heads: {current} != {heads}"

    async def live_db():
        async with AsyncSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = live_db
    run_id = uuid4().hex[:10]
    try:
        async with AsyncSessionLocal() as session:
            await seed_global_categories(session)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://postgres-integration"
        ) as client:
            admin_name = f"pg_admin_{run_id}"
            admin_tokens = await register_user(client, admin_name)
            async with AsyncSessionLocal() as session:
                admin = (await session.execute(
                    select(User).where(User.username == admin_name)
                )).scalar_one()
                admin.is_admin = True
                await session.commit()

            status = await client.get(
                "/api/v1/admin/database", headers=auth_headers(admin_tokens)
            )
            assert status.status_code == 200, status.text
            assert status.json()["database_connected"] is True
            assert status.json()["migrations_current"] is True
            assert set(status.json()["current_revisions"]) == heads

            await exercise_cross_screen_group_period_visibility_and_budget_consistency(
                client, run_id
            )

        async with AsyncSessionLocal() as session:
            after = {
                "users": await session.scalar(select(func.count()).select_from(User)),
                "groups": await session.scalar(select(func.count()).select_from(Group)),
                "transactions": await session.scalar(select(func.count()).select_from(Transaction)),
            }
        assert after["users"] - before["users"] == 4
        assert after["groups"] - before["groups"] == 2
        assert after["transactions"] - before["transactions"] == 6
    finally:
        app.dependency_overrides.pop(get_db, None)
        # Live Neon verification must not leave its disposable fixtures in the
        # configured database. Scope cleanup to this invocation's unique names.
        usernames = {
            f"pg_admin_{run_id}",
            f"regression_owner_{run_id}",
            f"regression_member_{run_id}",
            f"regression_outsider_{run_id}",
        }
        group_names = {f"Primary home {run_id}", f"Holiday home {run_id}"}
        async with AsyncSessionLocal() as session:
            user_ids = set((await session.execute(
                select(User.id).where(User.username.in_(usernames))
            )).scalars().all())
            group_ids = set((await session.execute(
                select(Group.id).where(
                    or_(Group.owner_id.in_(user_ids or {"__none__"}), Group.name.in_(group_names))
                )
            )).scalars().all())
            settlement_ids = set((await session.execute(
                select(SettlementRecord.id).where(or_(
                    SettlementRecord.group_id.in_(group_ids or {"__none__"}),
                    SettlementRecord.from_user_id.in_(user_ids or {"__none__"}),
                    SettlementRecord.to_user_id.in_(user_ids or {"__none__"}),
                ))
            )).scalars().all())
            transaction_ids = set((await session.execute(
                select(Transaction.id).where(or_(
                    Transaction.recorded_by_id.in_(user_ids or {"__none__"}),
                    Transaction.payer_id.in_(user_ids or {"__none__"}),
                    Transaction.group_id.in_(group_ids or {"__none__"}),
                    Transaction.settlement_group_id.in_(group_ids or {"__none__"}),
                    Transaction.settlement_record_id.in_(settlement_ids or {"__none__"}),
                ))
            )).scalars().all())
            if transaction_ids:
                await session.execute(update(Transaction).where(
                    Transaction.id.in_(transaction_ids)
                ).values(settlement_record_id=None))
            if settlement_ids:
                await session.execute(update(SettlementRecord).where(
                    SettlementRecord.id.in_(settlement_ids)
                ).values(original_transaction_id=None))
            for model, ids in (
                (Transaction, transaction_ids),
                (SettlementRecord, settlement_ids),
                (BudgetPeriod, set((await session.execute(
                    select(BudgetPeriod.id).where(or_(
                        BudgetPeriod.group_id.in_(group_ids or {"__none__"}),
                        BudgetPeriod.created_by_id.in_(user_ids or {"__none__"}),
                    ))
                )).scalars().all())),
                (GroupMember, set((await session.execute(
                    select(GroupMember.id).where(GroupMember.group_id.in_(group_ids or {"__none__"}))
                )).scalars().all())),
                (Category, set((await session.execute(
                    select(Category.id).where(Category.group_id.in_(group_ids or {"__none__"}))
                )).scalars().all())),
                (Group, group_ids),
                (User, user_ids),
            ):
                if ids:
                    await session.execute(delete(model).where(model.id.in_(ids)))
            await session.commit()
