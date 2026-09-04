"""
One-time migration script: add missing columns/tables to the live sharedspend.db.
Safe to run multiple times — checks before altering.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.engine import engine
from sqlalchemy import text


async def migrate():
    async with engine.begin() as conn:
        # ── 1. Check existing columns in transactions ─────────────────────────
        cols_result = await conn.execute(text("PRAGMA table_info(transactions)"))
        existing_cols = [row[1] for row in cols_result.fetchall()]
        print(f"Current transaction columns: {existing_cols}")

        # ── 2. Add add_to_settlement if missing ───────────────────────────────
        if "add_to_settlement" not in existing_cols:
            await conn.execute(text(
                "ALTER TABLE transactions ADD COLUMN "
                "add_to_settlement INTEGER NOT NULL DEFAULT 0"
            ))
            print("DONE: Added add_to_settlement column to transactions")
        else:
            print("OK: add_to_settlement already present")

        # ── 3. Check existing tables ──────────────────────────────────────────
        tables_result = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ))
        existing_tables = [row[0] for row in tables_result.fetchall()]
        print(f"Existing tables: {existing_tables}")

        # ── 4. Create settlement_records if missing ───────────────────────────
        if "settlement_records" not in existing_tables:
            await conn.execute(text("""
                CREATE TABLE settlement_records (
                    id          VARCHAR(36)   PRIMARY KEY,
                    group_id    VARCHAR(36)   NOT NULL,
                    from_user_id VARCHAR(36)  NOT NULL,
                    to_user_id  VARCHAR(36)   NOT NULL,
                    amount      NUMERIC(12,2) NOT NULL,
                    status      VARCHAR(10)   NOT NULL DEFAULT 'PENDING',
                    settled_at  DATETIME,
                    created_at  DATETIME      NOT NULL
                )
            """))
            print("DONE: Created settlement_records table")
        else:
            print("OK: settlement_records already present")

        # ── 5. Verify final state ─────────────────────────────────────────────
        cols2 = await conn.execute(text("PRAGMA table_info(transactions)"))
        print(f"Final transaction columns: {[r[1] for r in cols2.fetchall()]}")

        tx_count = await conn.execute(text(
            "SELECT count(*) FROM transactions WHERE is_deleted = 0"
        ))
        print(f"Live transactions (not deleted): {tx_count.scalar()}")

        budget_count = await conn.execute(text("SELECT count(*) FROM budget_periods"))
        print(f"Budget periods: {budget_count.scalar()}")

        # Show existing transactions
        txns = await conn.execute(text(
            "SELECT id, type, amount, date, group_id "
            "FROM transactions WHERE is_deleted = 0 LIMIT 10"
        ))
        print("Sample transactions:")
        for row in txns.fetchall():
            print(f"  {row}")

        budgets = await conn.execute(text(
            "SELECT group_id, year, month, amount FROM budget_periods LIMIT 10"
        ))
        print("Budgets:")
        for row in budgets.fetchall():
            print(f"  {row}")


if __name__ == "__main__":
    asyncio.run(migrate())
    print("\nMigration complete. Restart the backend server.")
