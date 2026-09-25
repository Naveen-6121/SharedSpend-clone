from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import AsyncSessionLocal, engine
from app.models.user import User


async def promote_admin(username: str) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        if not user.is_admin:
            user.is_admin = True
            await db.commit()
        return True


async def show_database_status() -> int:
    """Print safe connectivity/schema metadata without revealing the URL."""
    config_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    heads = sorted(ScriptDirectory.from_config(Config(str(config_path))).get_heads())

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            tables = await connection.run_sync(lambda sync: sorted(inspect(sync).get_table_names()))
            if "alembic_version" in tables:
                result = await connection.execute(
                    text("SELECT version_num FROM alembic_version ORDER BY version_num")
                )
                current = sorted(result.scalars().all())
            else:
                current = []

            database_name = None
            ssl_enabled = None
            if engine.dialect.name == "postgresql":
                database_name = (await connection.execute(text("SELECT current_database()"))).scalar_one()
                # On pooled Neon endpoints pg_stat_ssl describes the pooler's
                # backend connection, not the client-to-pooler TLS session.
                raw_connection = await connection.get_raw_connection()
                driver_connection = raw_connection.driver_connection
                transport = getattr(driver_connection, "_transport", None)
                ssl_enabled = bool(transport and transport.get_extra_info("ssl_object"))

            counts = {}
            for table in ("users", "groups", "transactions"):
                if table in tables:
                    counts[table] = (await connection.execute(
                        text(f'SELECT count(*) FROM "{table}"')
                    )).scalar_one()
    except SQLAlchemyError:
        print("Database connection: FAILED (connection details are intentionally omitted)")
        return 1

    print("Database connection: OK")
    print(f"Driver: {engine.url.drivername}")
    if database_name:
        print(f"Database: {database_name}")
        print(f"TLS: {'enabled' if ssl_enabled else 'disabled/unknown'}")
    print(f"Alembic revision: {', '.join(current) if current else 'not initialized'}")
    print(f"Alembic head: {', '.join(heads)}")
    print(f"Migrations current: {'yes' if current == heads else 'no'}")
    print(f"Tables: {', '.join(tables) if tables else '(none)'}")
    if counts:
        print("Core row counts: " + ", ".join(f"{name}={count}" for name, count in counts.items()))
    return 0 if current == heads else 2


async def run(args: argparse.Namespace) -> int:
    if args.command == "promote-admin":
        found = await promote_admin(args.username)
        if not found:
            print(f"No user found with username {args.username!r}.")
            return 1
        print(f"Administrator access granted to {args.username!r}.")
        return 0
    if args.command == "db-status":
        return await show_database_status()
    return 2


async def run_and_dispose(args: argparse.Namespace) -> int:
    try:
        return await run(args)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="SharedSpend maintenance commands")
    commands = parser.add_subparsers(dest="command", required=True)
    promote = commands.add_parser("promote-admin", help="Promote an existing user to global admin")
    promote.add_argument("username")
    commands.add_parser("db-status", help="Check database connectivity and schema without displaying credentials")
    args = parser.parse_args()
    exit_code = asyncio.run(run_and_dispose(args))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
