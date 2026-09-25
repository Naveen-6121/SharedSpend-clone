"""Safely import Naveen and Alekhya's SQLite data into configured PostgreSQL.

Default invocation is read-only and prints a row-count plan. Applying requires
--apply plus an interactive confirmation. All inserts run in one PostgreSQL
transaction; existing rows are never updated or deleted.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    JSON,
    MetaData,
    Numeric,
    UniqueConstraint,
    and_,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.schema import Table

from app.db.engine import engine


APP_TABLES = (
    "users",
    "groups",
    "group_members",
    "categories",
    "budget_periods",
    "transactions",
    "settlement_records",
)
REVISION_TABLE = "alembic_version"
IMPORT_USERNAMES = {"naveen", "alekhya"}
INSERT_ORDER = (
    "users",
    "groups",
    "categories",
    "group_members",
    "transactions",
    "budget_periods",
    "settlement_records",
)


def read_sqlite(
    source_path: Path,
) -> tuple[dict[str, list[dict[str, Any]]], str, dict[str, set[str]]]:
    if not source_path.is_file():
        raise ValueError("SQLite source file does not exist")
    conn = sqlite3.connect(f"{source_path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError("SQLite integrity check failed")
        if list(conn.execute("PRAGMA foreign_key_check")):
            raise ValueError("SQLite contains foreign-key violations")
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        expected = set(APP_TABLES) | {REVISION_TABLE}
        if tables != expected:
            raise ValueError("SQLite table set differs from the supported migration schema")
        revisions = [row[0] for row in conn.execute(f'SELECT version_num FROM "{REVISION_TABLE}"')]
        if len(revisions) != 1:
            raise ValueError("SQLite must have exactly one Alembic revision")
        data = {
            table: [dict(row) for row in conn.execute(f'SELECT * FROM "{table}"')]
            for table in APP_TABLES
        }
        columns = {
            table: {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")')}
            for table in APP_TABLES
        }
        return data, revisions[0], columns
    finally:
        conn.close()


def scoped_rows(
    data: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    users = [
        row for row in data["users"]
        if (row.get("username") or "").casefold() in IMPORT_USERNAMES
    ]
    if {row["username"].casefold() for row in users} != IMPORT_USERNAMES:
        raise ValueError("SQLite must contain exactly one Naveen and one Alekhya account")
    user_ids = {row["id"] for row in users}

    source_groups = {row["id"]: row for row in data["groups"]}
    source_members = data["group_members"]
    group_ids = {
        group_id for group_id, group in source_groups.items()
        if group["owner_id"] in user_ids
        or any(m["group_id"] == group_id and m["user_id"] in user_ids for m in source_members)
    }
    # A mixed group would require importing an additional account. Fail closed
    # instead of silently copying or dropping another person's membership.
    for group_id in group_ids:
        group = source_groups[group_id]
        members = {m["user_id"] for m in source_members if m["group_id"] == group_id}
        if group["owner_id"] not in user_ids or not members.issubset(user_ids):
            raise ValueError("A selected group includes an account outside the approved import scope")

    tx_by_id = {row["id"]: row for row in data["transactions"]}
    tx_ids = {
        row["id"] for row in data["transactions"]
        if row["recorded_by_id"] in user_ids
        or row["payer_id"] in user_ids
        or row["group_id"] in group_ids
        or row["settlement_group_id"] in group_ids
    }
    settlement_by_id = {row["id"]: row for row in data["settlement_records"]}
    settlement_ids: set[str] = set()
    # Close both sides of the transaction/settlement link cycle.
    changed = True
    while changed:
        old = (len(tx_ids), len(settlement_ids))
        settlement_ids.update(
            row["id"] for row in data["settlement_records"]
            if row["group_id"] in group_ids
            or row["from_user_id"] in user_ids
            or row["to_user_id"] in user_ids
            or row["original_transaction_id"] in tx_ids
            or row["id"] in {tx_by_id[tid]["settlement_record_id"] for tid in tx_ids if tid in tx_by_id}
        )
        tx_ids.update(
            row["id"] for row in data["transactions"]
            if row["settlement_record_id"] in settlement_ids
        )
        tx_ids.update(
            row["original_transaction_id"] for sid, row in settlement_by_id.items()
            if sid in settlement_ids and row["original_transaction_id"] is not None
        )
        changed = old != (len(tx_ids), len(settlement_ids))

    transactions = [row for row in data["transactions"] if row["id"] in tx_ids]
    settlements = [row for row in data["settlement_records"] if row["id"] in settlement_ids]
    budgets = [
        row for row in data["budget_periods"]
        if row["group_id"] in group_ids or row["created_by_id"] in user_ids
    ]
    category_ids = {
        row[key] for row in transactions for key in ("category_id", "suggested_category_id")
        if row[key] is not None
    }
    category_ids.update(
        row["id"] for row in data["categories"]
        if row["is_global"] or row["group_id"] in group_ids
    )
    selected_categories = [row for row in data["categories"] if row["id"] in category_ids]
    for row in selected_categories:
        if not row["is_global"] and row["group_id"] not in group_ids:
            raise ValueError("A selected non-global category is not scoped to the approved group")
    group_categories = [row for row in selected_categories if not row["is_global"]]

    # Reject references that would otherwise make the partial import lossy.
    for row in transactions:
        if row["recorded_by_id"] not in user_ids or (row["payer_id"] and row["payer_id"] not in user_ids):
            raise ValueError("A selected transaction references an account outside the approved import scope")
        for column in ("group_id", "settlement_group_id"):
            if row[column] is not None and row[column] not in group_ids:
                raise ValueError("A selected transaction references a group outside the approved import scope")
    for row in settlements:
        if row["from_user_id"] not in user_ids or row["to_user_id"] not in user_ids or row["group_id"] not in group_ids:
            raise ValueError("A selected settlement references data outside the approved import scope")
    for row in budgets:
        if row["group_id"] not in group_ids or row["created_by_id"] not in user_ids:
            raise ValueError("A selected budget references data outside the approved import scope")
    for row in selected_categories:
        if row["group_id"] is not None and row["group_id"] not in group_ids:
            raise ValueError("A selected category belongs to a group outside the approved import scope")

    return {
        "users": users,
        "groups": [r for r in data["groups"] if r["id"] in group_ids],
        "group_members": [r for r in source_members if r["group_id"] in group_ids],
        "categories": group_categories,
        "budget_periods": budgets,
        "transactions": transactions,
        "settlement_records": settlements,
    }, selected_categories


async def build_category_mapping(
    conn: AsyncConnection,
    metadata: MetaData,
    source_categories: list[dict[str, Any]],
) -> tuple[dict[str, str], list[tuple[str, str, str]]]:
    """Reuse target global category IDs; retain source IDs for group categories."""
    table = metadata.tables["categories"]
    mapping: dict[str, str] = {}
    global_labels: set[str] = set()
    details: list[tuple[str, str, str]] = []
    for row in sorted(source_categories, key=lambda item: item["name"].casefold()):
        if not row["is_global"]:
            mapping[row["id"]] = row["id"]
            continue
        label = row["name"]
        if label in global_labels:
            raise ValueError("SQLite contains duplicate global category labels")
        global_labels.add(label)
        matches = (await conn.execute(
            select(table.c.id).where(
                table.c.name == label,
                table.c.is_global.is_(True),
                table.c.group_id.is_(None),
            )
        )).scalars().all()
        if len(matches) != 1:
            raise ValueError("Neon must have exactly one seeded global category for every SQLite global label")
        mapping[row["id"]] = matches[0]
        details.append((label, row["id"], matches[0]))
    return mapping, details


def normalize(value: Any, type_: Any) -> Any:
    if value is None:
        return None
    if isinstance(type_, JSON):
        return json.loads(value) if isinstance(value, str) else value
    if isinstance(type_, Boolean):
        return bool(value)
    if isinstance(type_, DateTime):
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if type_.timezone and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        if type_.timezone and dt.tzinfo is not None:
            return dt.astimezone(timezone.utc)
        if not type_.timezone and dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    if isinstance(type_, Date):
        return value if isinstance(value, date) and not isinstance(value, datetime) else date.fromisoformat(str(value)[:10])
    if isinstance(type_, Numeric):
        return value if isinstance(value, Decimal) else Decimal(str(value))
    return value


def normalize_row(row: dict[str, Any], table: Table) -> dict[str, Any]:
    return {column.name: normalize(row[column.name], column.type) for column in table.columns}


async def table_metadata(conn: AsyncConnection) -> MetaData:
    metadata = MetaData()
    await conn.run_sync(lambda sync_conn: metadata.reflect(bind=sync_conn))
    return metadata


async def check_conflicts(
    conn: AsyncConnection,
    metadata: MetaData,
    scope: dict[str, list[dict[str, Any]]],
) -> None:
    for name, rows in scope.items():
        table = metadata.tables[name]
        ids = [row["id"] for row in rows]
        if ids and (await conn.execute(select(table.c.id).where(table.c.id.in_(ids)))).first():
            raise ValueError(f"Target already contains one or more {name} IDs; no changes made")
        if name == "users":
            for row in rows:
                for column in ("username", "email"):
                    if (await conn.execute(
                        select(table.c.id).where(func.lower(table.c[column]) == row[column].casefold()).limit(1)
                    )).first():
                        raise ValueError(f"Target has a case-insensitive {column} conflict; no changes made")
        unique_sets: list[tuple[str, ...]] = []
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint):
                unique_sets.append(tuple(column.name for column in constraint.columns))
        for columns in unique_sets:
            for row in rows:
                values = [row[column] for column in columns]
                if any(value is None for value in values):
                    continue
                predicate = and_(*(table.c[column] == value for column, value in zip(columns, values)))
                if (await conn.execute(select(table.c.id).where(predicate).limit(1))).first():
                    # Never print the conflicting value (it could be an email).
                    raise ValueError(f"Target has a conflicting unique key in {name}; no changes made")


async def target_ready_state(conn: AsyncConnection, metadata: MetaData) -> tuple[bool, dict[str, int]]:
    counts = {}
    for name in ("users", "groups", "group_members", "budget_periods", "transactions", "settlement_records"):
        counts[name] = (await conn.execute(
            select(func.count()).select_from(metadata.tables[name])
        )).scalar_one()
    categories = metadata.tables["categories"]
    counts["non_global_categories"] = (await conn.execute(
        select(func.count()).select_from(categories).where(
            categories.c.is_global.is_(False) | categories.c.group_id.is_not(None)
        )
    )).scalar_one()
    return all(count == 0 for count in counts.values()), counts


async def validate_scope(
    conn: AsyncConnection,
    metadata: MetaData,
    scope: dict[str, list[dict[str, Any]]],
    source_columns: dict[str, set[str]],
) -> dict[str, list[dict[str, Any]]]:
    if conn.dialect.name != "postgresql":
        raise ValueError("Configured DATABASE_URL is not PostgreSQL")
    target_tables = set(metadata.tables)
    required = set(APP_TABLES) | {REVISION_TABLE}
    if not required.issubset(target_tables):
        raise ValueError("PostgreSQL schema is missing required application tables")
    for name in APP_TABLES:
        target_cols = set(metadata.tables[name].c.keys())
        if target_cols != source_columns[name]:
            raise ValueError(f"Column mismatch in {name}; no changes made")
    revision = (await conn.execute(select(metadata.tables[REVISION_TABLE].c.version_num))).scalars().all()
    if len(revision) != 1:
        raise ValueError("PostgreSQL must have exactly one Alembic revision")
    return {"target_revision": revision}


async def compare_copied_rows(
    conn: AsyncConnection,
    metadata: MetaData,
    scope: dict[str, list[dict[str, Any]]],
    expected: dict[str, list[dict[str, Any]]],
) -> None:
    for name, rows in scope.items():
        table = metadata.tables[name]
        ids = [row["id"] for row in rows]
        actual_rows = (
            (await conn.execute(select(table).where(table.c.id.in_(ids)))).mappings().all()
            if ids else []
        )
        actual = {row["id"]: dict(row) for row in actual_rows}
        mismatches = 0
        for wanted in expected[name]:
            got = actual.get(wanted["id"])
            if got is None:
                mismatches += 1
                continue
            for column in table.columns:
                if normalize(got[column.name], column.type) != wanted[column.name]:
                    mismatches += 1
                    break
        if mismatches:
            raise ValueError(f"Post-migration verification failed for {name}")


async def run(source_path: Path, apply: bool) -> None:
    source_data, source_revision, source_columns = read_sqlite(source_path)
    scope, selected_categories = scoped_rows(source_data)
    expected_counts = {name: len(rows) for name, rows in scope.items()}
    expected: dict[str, list[dict[str, Any]]] = {}
    applied = False

    async with engine.begin() as conn:
        metadata = await table_metadata(conn)
        target_info = await validate_scope(conn, metadata, scope, source_columns)
        target_revision = target_info["target_revision"][0]
        if source_revision != target_revision:
            raise ValueError("SQLite and PostgreSQL Alembic revisions differ; no changes made")
        await check_conflicts(conn, metadata, scope)
        category_mapping, category_mapping_details = await build_category_mapping(
            conn, metadata, selected_categories
        )
        target_ready, target_counts = await target_ready_state(conn, metadata)
        for name, rows in scope.items():
            expected[name] = [normalize_row(row, metadata.tables[name]) for row in rows]
        for row in expected["transactions"]:
            for column in ("category_id", "suggested_category_id"):
                if row[column] is not None:
                    try:
                        row[column] = category_mapping[row[column]]
                    except KeyError:
                        raise ValueError("A selected transaction category has no safe source-to-Neon mapping") from None

        print(f"source_revision={source_revision}")
        print(f"target_revision={target_revision}")
        print("scope=exact Naveen and Alekhya accounts and their connected data")
        print("Neon existing rows will be preserved; conflicting IDs/unique keys abort")
        for row in sorted(expected["users"], key=lambda item: item["username"].casefold()):
            print(f"import_user={row['username']}")
        for name in APP_TABLES:
            print(f"planned_{name}={expected_counts[name]}")
        print(f"reused_global_categories={len(category_mapping_details)}")
        print(f"imported_group_categories={expected_counts['categories']}")
        for label, source_id, target_id in category_mapping_details:
            print(f"category_mapping={label!r}:source_id={source_id}:neon_id={target_id}")
        for row in sorted(selected_categories, key=lambda item: item["name"].casefold()):
            if not row["is_global"]:
                print(f"group_category_import={row['name']!r}:source_id={row['id']}:neon_id={row['id']}")
        print(f"target_ready_for_import={target_ready}")
        for name, count in target_counts.items():
            print(f"target_preexisting_{name}={count}")
        if not apply:
            print("mode=read_only_plan; no rows written")
            return
        if not target_ready:
            print("apply_blocked=Neon still has non-seed application data; no rows written")
            return

        confirmation = input("Type MIGRATE SHAREDSPEND SQLITE DATA to apply atomically: ")
        if confirmation != "MIGRATE SHAREDSPEND SQLITE DATA":
            print("apply_cancelled; no rows written")
            return

        # Break the transaction <-> settlement_record FK cycle during insertion.
        for name in INSERT_ORDER:
            rows = expected[name]
            if name == "transactions":
                rows = [{**row, "settlement_record_id": None} for row in rows]
            if rows:
                table = metadata.tables[name]
                await conn.execute(table.insert(), rows)
        # settlement_records.original_transaction_id is safe now that the
        # selected transactions exist; restore transaction-side source links.
        tx_table = metadata.tables["transactions"]
        for row in expected["transactions"]:
            if row["settlement_record_id"] is not None:
                await conn.execute(
                    tx_table.update().where(tx_table.c.id == row["id"]).values(
                        settlement_record_id=row["settlement_record_id"]
                    )
                )

        await compare_copied_rows(conn, metadata, scope, expected)
        print("post_import_exact_row_comparison=passed")
        print("post_import_foreign_keys=passed by PostgreSQL constraints")
        print("post_import_password_hashes=preserved and matched (values not displayed)")
        print("pre_commit_verification=passed")
        applied = True
    if applied:
        print("mode=applied; transaction committed")


async def async_main(source_path: Path, apply: bool) -> None:
    try:
        await run(source_path, apply)
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "sharedspend.db",
        help="SQLite source path (default: backend/sharedspend.db)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply the import after preflight and interactive confirmation; default is read-only",
    )
    args = parser.parse_args()
    try:
        asyncio.run(async_main(args.source, args.apply))
        return 0
    except Exception as exc:
        # Avoid printing exception strings: provider/driver errors can contain
        # connection details. The engine URL is never logged by this utility.
        print(f"migration_stopped={type(exc).__name__}; no import committed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
