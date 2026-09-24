from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

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


async def run(args: argparse.Namespace) -> int:
    if args.command == "promote-admin":
        found = await promote_admin(args.username)
        if not found:
            print(f"No user found with username {args.username!r}.")
            return 1
        print(f"Administrator access granted to {args.username!r}.")
        return 0
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
    args = parser.parse_args()
    exit_code = asyncio.run(run_and_dispose(args))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
