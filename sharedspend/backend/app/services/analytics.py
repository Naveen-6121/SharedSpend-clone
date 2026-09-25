from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import BudgetPeriod
from app.models.category import Category
from app.models.group import GroupMember
from app.models.transaction import Transaction
from app.models.user import User
from app.services.date_filter import DateFilterParams, resolve_date_range


async def get_summary(
    db: AsyncSession,
    current_user_id: str,
    group_id: Optional[str],
    params: DateFilterParams,
) -> dict:
    start, end = resolve_date_range(params)

    # shared_spent
    shared_q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.type == "SHARED",
        Transaction.is_deleted == False,  # noqa: E712
        Transaction.date >= start,
        Transaction.date <= end,
    )
    if group_id:
        shared_q = shared_q.where(Transaction.group_id == group_id)
    else:
        # Only groups the user belongs to
        member_groups = select(GroupMember.group_id).where(GroupMember.user_id == current_user_id)
        shared_q = shared_q.where(Transaction.group_id.in_(member_groups))

    # budget
    budget_q = select(BudgetPeriod.amount).where(
        BudgetPeriod.group_id == group_id,
        BudgetPeriod.year == params.year,
        BudgetPeriod.month == params.month,
    ) if group_id and params.year and params.month else None

    # Fetch the dashboard totals and current user's display name in one round-trip.
    # Scalar subqueries retain the original visibility/date rules while avoiding
    # separate network round-trips to a remote PostgreSQL database.
    personal_q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.type == "PERSONAL",
        Transaction.settlement_record_id.is_(None),
        Transaction.recorded_by_id == current_user_id,
        Transaction.is_deleted == False,  # noqa: E712
        Transaction.date >= start,
        Transaction.date <= end,
    )
    totals_q = select(
        shared_q.scalar_subquery().label("shared_spent"),
        personal_q.scalar_subquery().label("personal_total"),
        select(User.display_name).where(User.id == current_user_id).scalar_subquery().label("display_name"),
    )
    if budget_q is not None:
        totals_q = totals_q.add_columns(budget_q.scalar_subquery().label("budget_amount"))
    totals = (await db.execute(totals_q)).one()
    shared_spent = Decimal(str(totals.shared_spent))
    personal_total = Decimal(str(totals.personal_total))
    budget_amount: Optional[Decimal] = None
    if group_id and params.year and params.month:
        if totals.budget_amount is not None:
            budget_amount = Decimal(str(totals.budget_amount))

    remaining = (budget_amount - shared_spent) if budget_amount is not None else None
    utilization = (
        (shared_spent / budget_amount * 100).quantize(Decimal("0.01"))
        if budget_amount
        else None
    )

    # personal_by_member – current user only (personal is private)
    personal_by_member = [
        {
            "user_id": current_user_id,
            "display_name": totals.display_name,
            "personal_spent": personal_total,
        }
    ]

    # paid_by_member — personal transactions marked add_to_settlement, aggregated by payer
    # (SHARED transactions no longer have a payer under the new model)
    paid_q = (
        select(Transaction.payer_id, User.display_name, func.sum(Transaction.amount).label("paid"))
        .join(User, User.id == Transaction.payer_id)
        .where(
            Transaction.type == "PERSONAL",
            Transaction.add_to_settlement == True,  # noqa: E712
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
            Transaction.payer_id.isnot(None),
        )
        .group_by(Transaction.payer_id, User.display_name)
    )
    if group_id:
        member_ids_q = select(GroupMember.user_id).where(GroupMember.group_id == group_id)
        paid_q = paid_q.where(
            Transaction.payer_id.in_(member_ids_q),
            Transaction.settlement_group_id == group_id,
        )
    else:
        member_groups2 = select(GroupMember.group_id).where(GroupMember.user_id == current_user_id)
        member_ids_q2 = select(GroupMember.user_id).where(GroupMember.group_id.in_(member_groups2))
        paid_q = paid_q.where(Transaction.payer_id.in_(member_ids_q2))

    paid_rows = (await db.execute(paid_q)).all()
    paid_by_member = []
    for row in paid_rows:
        paid_by_member.append(
            {
                "user_id": row.payer_id,
                "display_name": row.display_name,
                "paid": Decimal(str(row.paid)),
            }
        )

    return {
        "budget": budget_amount,
        "shared_spent": shared_spent,
        "remaining": remaining,
        "utilization_pct": utilization,
        "personal_by_member": personal_by_member,
        "paid_by_member": paid_by_member,
    }


async def get_by_category(
    db: AsyncSession,
    current_user_id: str,
    group_id: Optional[str],
    params: DateFilterParams,
) -> list:
    start, end = resolve_date_range(params)
    q = (
        select(
            Transaction.category_id,
            Category.name.label("category_name"),
            func.sum(Transaction.amount).label("amount"),
            func.count(Transaction.id).label("count"),
        )
        .outerjoin(Category, Transaction.category_id == Category.id)
        .where(
            Transaction.settlement_record_id.is_(None),
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(Transaction.category_id, Category.name)
    )
    q = _apply_visibility(q, current_user_id, group_id)
    rows = (await db.execute(q)).all()
    return [
        {
            "category_id": r.category_id,
            "category_name": r.category_name,
            "amount": Decimal(str(r.amount)),
            "count": r.count,
        }
        for r in rows
    ]


async def get_by_day(
    db: AsyncSession,
    current_user_id: str,
    group_id: Optional[str],
    params: DateFilterParams,
) -> list:
    start, end = resolve_date_range(params)
    q = (
        select(
            Transaction.date,
            func.sum(case((Transaction.type == "SHARED", Transaction.amount), else_=0)).label("shared"),
            func.sum(case((Transaction.type == "PERSONAL", Transaction.amount), else_=0)).label("personal"),
        )
        .where(
            Transaction.settlement_record_id.is_(None),
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(Transaction.date)
        .order_by(Transaction.date)
    )
    q = _apply_visibility(q, current_user_id, group_id)
    rows = (await db.execute(q)).all()
    return [
        {"date": r.date, "shared": Decimal(str(r.shared)), "personal": Decimal(str(r.personal))}
        for r in rows
    ]


async def get_by_week(
    db: AsyncSession,
    current_user_id: str,
    group_id: Optional[str],
    params: DateFilterParams,
) -> list:
    start, end = resolve_date_range(params)
    q = (
        select(
            extract("year", Transaction.date).label("year"),
            extract("week", Transaction.date).label("week"),
            func.sum(case((Transaction.type == "SHARED", Transaction.amount), else_=0)).label("shared"),
            func.sum(case((Transaction.type == "PERSONAL", Transaction.amount), else_=0)).label("personal"),
        )
        .where(
            Transaction.settlement_record_id.is_(None),
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by("year", "week")
        .order_by("year", "week")
    )
    q = _apply_visibility(q, current_user_id, group_id)
    rows = (await db.execute(q)).all()
    return [
        {
            "year": int(r.year),
            "week": int(r.week),
            "shared": Decimal(str(r.shared)),
            "personal": Decimal(str(r.personal)),
        }
        for r in rows
    ]


async def get_by_month(
    db: AsyncSession,
    current_user_id: str,
    group_id: Optional[str],
    params: DateFilterParams,
) -> list:
    start, end = resolve_date_range(params)
    q = (
        select(
            extract("year", Transaction.date).label("year"),
            extract("month", Transaction.date).label("month"),
            func.sum(case((Transaction.type == "SHARED", Transaction.amount), else_=0)).label("shared"),
            func.sum(case((Transaction.type == "PERSONAL", Transaction.amount), else_=0)).label("personal"),
        )
        .where(
            Transaction.settlement_record_id.is_(None),
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by("year", "month")
        .order_by("year", "month")
    )
    q = _apply_visibility(q, current_user_id, group_id)
    rows = (await db.execute(q)).all()
    return [
        {
            "year": int(r.year),
            "month": int(r.month),
            "shared": Decimal(str(r.shared)),
            "personal": Decimal(str(r.personal)),
        }
        for r in rows
    ]


async def get_by_year(
    db: AsyncSession,
    current_user_id: str,
    group_id: Optional[str],
    params: DateFilterParams,
) -> list:
    start, end = resolve_date_range(params)
    q = (
        select(
            extract("year", Transaction.date).label("year"),
            func.sum(case((Transaction.type == "SHARED", Transaction.amount), else_=0)).label("shared"),
            func.sum(case((Transaction.type == "PERSONAL", Transaction.amount), else_=0)).label("personal"),
        )
        .where(
            Transaction.settlement_record_id.is_(None),
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by("year")
        .order_by("year")
    )
    q = _apply_visibility(q, current_user_id, group_id)
    rows = (await db.execute(q)).all()
    return [
        {
            "year": int(r.year),
            "shared": Decimal(str(r.shared)),
            "personal": Decimal(str(r.personal)),
        }
        for r in rows
    ]


async def get_members(
    db: AsyncSession,
    current_user_id: str,
    group_id: Optional[str],
    params: DateFilterParams,
) -> list:
    start, end = resolve_date_range(params)

    if not group_id:
        return []

    paid_by_user = (
        select(
            Transaction.payer_id.label("user_id"),
            func.sum(Transaction.amount).label("paid"),
        )
        .where(
            Transaction.type == "PERSONAL",
            Transaction.settlement_group_id == group_id,
            Transaction.settlement_record_id.is_(None),
            Transaction.add_to_settlement == True,  # noqa: E712
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(Transaction.payer_id)
        .subquery()
    )
    personal_by_user = (
        select(
            Transaction.recorded_by_id.label("user_id"),
            func.sum(Transaction.amount).label("personal"),
        )
        .where(
            Transaction.type == "PERSONAL",
            Transaction.settlement_record_id.is_(None),
            Transaction.recorded_by_id == current_user_id,
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(Transaction.recorded_by_id)
        .subquery()
    )
    rows = (await db.execute(
        select(
            GroupMember.user_id,
            User.display_name,
            func.coalesce(paid_by_user.c.paid, 0).label("paid"),
            personal_by_user.c.personal,
        )
        .join(User, User.id == GroupMember.user_id)
        .outerjoin(paid_by_user, paid_by_user.c.user_id == GroupMember.user_id)
        .outerjoin(personal_by_user, personal_by_user.c.user_id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
    )).all()
    return [
        {
            "user_id": row.user_id,
            "display_name": row.display_name,
            "paid": Decimal(str(row.paid)),
            # Preserve privacy: only the requesting member sees their personal spend.
            "personal_spent": Decimal(str(row.personal))
            if row.user_id == current_user_id and row.personal is not None else
            (Decimal("0") if row.user_id == current_user_id else None),
        }
        for row in rows
    ]


async def get_insights(
    db: AsyncSession,
    current_user_id: str,
    group_id: Optional[str],
    params: DateFilterParams,
) -> dict:
    start, end = resolve_date_range(params)

    visible_base = (
        Transaction.settlement_record_id.is_(None),
        Transaction.is_deleted == False,  # noqa: E712
        Transaction.date >= start,
        Transaction.date <= end,
    )
    category_total = func.sum(Transaction.amount)
    category_base = (
        select(Category.name)
        .select_from(Transaction)
        .outerjoin(Category, Transaction.category_id == Category.id)
        .where(*visible_base)
        .group_by(Category.name)
        .order_by(category_total.desc())
        .limit(1)
    )
    category_name_q = _apply_visibility(category_base, current_user_id, group_id)
    category_amount_q = _apply_visibility(
        select(category_total)
        .select_from(Transaction)
        .outerjoin(Category, Transaction.category_id == Category.id)
        .where(*visible_base)
        .group_by(Category.name)
        .order_by(category_total.desc())
        .limit(1),
        current_user_id,
        group_id,
    )
    day_total = func.sum(Transaction.amount)
    highest_day_q = _apply_visibility(
        select(Transaction.date)
        .where(*visible_base)
        .group_by(Transaction.date)
        .order_by(day_total.desc())
        .limit(1),
        current_user_id,
        group_id,
    )
    highest_day_amount_q = _apply_visibility(
        select(day_total)
        .where(*visible_base)
        .group_by(Transaction.date)
        .order_by(day_total.desc())
        .limit(1),
        current_user_id,
        group_id,
    )

    # largest transactions (top 5)
    txn_q = (
        select(Transaction)
        .where(
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.settlement_record_id.is_(None),
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .order_by(Transaction.amount.desc())
        .limit(5)
    )
    txn_q = _apply_visibility(txn_q, current_user_id, group_id)
    txns = (await db.execute(txn_q)).scalars().all()
    largest = [
        {
            "id": t.id,
            "description": t.description,
            "amount": Decimal(str(t.amount)),
            "date": t.date,
            "type": t.type,
        }
        for t in txns
    ]

    # Keep all analytics scalars on one PostgreSQL round-trip. This matters for
    # Neon latency, where four small sequential SELECTs cost more than the work.
    trend = None
    previous_month_total_q = None
    current_month_total_q = None
    if params.month and params.year:
        prev_month = params.month - 1 if params.month > 1 else 12
        prev_year = params.year if params.month > 1 else params.year - 1
        curr_q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.settlement_record_id.is_(None),
            extract("year", Transaction.date) == params.year,
            extract("month", Transaction.date) == params.month,
        )
        prev_q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.settlement_record_id.is_(None),
            extract("year", Transaction.date) == prev_year,
            extract("month", Transaction.date) == prev_month,
        )
        current_month_total_q = _apply_visibility(curr_q, current_user_id, group_id)
        previous_month_total_q = _apply_visibility(prev_q, current_user_id, group_id)

    scalar_q = select(
        category_name_q.scalar_subquery().label("category_name"),
        category_amount_q.scalar_subquery().label("category_amount"),
        highest_day_q.scalar_subquery().label("highest_day"),
        highest_day_amount_q.scalar_subquery().label("highest_day_amount"),
    )
    if current_month_total_q is not None and previous_month_total_q is not None:
        scalar_q = scalar_q.add_columns(
            current_month_total_q.scalar_subquery().label("current_month_total"),
            previous_month_total_q.scalar_subquery().label("previous_month_total"),
        )
    summary = (await db.execute(scalar_q)).one()
    highest_category = (
        {"name": summary.category_name, "amount": Decimal(str(summary.category_amount))}
        if summary.category_amount is not None else None
    )
    highest_day = (
        {"date": summary.highest_day, "amount": Decimal(str(summary.highest_day_amount))}
        if summary.highest_day is not None else None
    )
    if current_month_total_q is not None and previous_month_total_q is not None:
        curr_total = Decimal(str(summary.current_month_total))
        prev_total = Decimal(str(summary.previous_month_total))
        if prev_total > 0:
            pct = ((curr_total - prev_total) / prev_total * 100).quantize(Decimal("0.1"))
            if pct > 0:
                trend = f"spending_up_{abs(pct)}_pct_vs_last_month"
            elif pct < 0:
                trend = f"spending_down_{abs(pct)}_pct_vs_last_month"
            else:
                trend = "spending_unchanged_vs_last_month"

    return {
        "highest_category": highest_category,
        "highest_day": highest_day,
        "largest_transactions": largest,
        "trend": trend,
    }


async def get_forecast(
    db: AsyncSession,
    current_user_id: str,
    group_id: Optional[str],
    year: int,
    month: int,
) -> dict:
    today = date.today()
    days_in_month = calendar.monthrange(year, month)[1]
    days_elapsed = today.day if today.year == year and today.month == month else days_in_month

    # shared_spent this month
    shared_q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.type == "SHARED",
        Transaction.is_deleted == False,  # noqa: E712
        extract("year", Transaction.date) == year,
        extract("month", Transaction.date) == month,
    )
    if group_id:
        shared_q = shared_q.where(Transaction.group_id == group_id)
    else:
        member_groups = select(GroupMember.group_id).where(GroupMember.user_id == current_user_id)
        shared_q = shared_q.where(Transaction.group_id.in_(member_groups))

    forecast_q = select(shared_q.scalar_subquery().label("shared_spent"))
    if group_id:
        forecast_q = forecast_q.add_columns(
            select(BudgetPeriod.amount).where(
                BudgetPeriod.group_id == group_id,
                BudgetPeriod.year == year,
                BudgetPeriod.month == month,
            ).scalar_subquery().label("budget_amount")
        )
    totals = (await db.execute(forecast_q)).one()
    shared_spent = Decimal(str(totals.shared_spent))

    projected: Optional[Decimal] = None
    if days_elapsed > 0:
        projected = (shared_spent / days_elapsed * days_in_month).quantize(Decimal("0.01"))

    budget_amount: Optional[Decimal] = None
    on_track: Optional[bool] = None
    if group_id:
        if totals.budget_amount is not None:
            budget_amount = Decimal(str(totals.budget_amount))
            if projected is not None and budget_amount:
                on_track = projected <= budget_amount

    return {
        "projected_spend": projected,
        "budget": budget_amount,
        "on_track": on_track,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
    }


def _apply_visibility(q, current_user_id: str, group_id: Optional[str]):
    """Show this group's shared spend and only the authenticated user's private spend."""
    if group_id:
        return q.where(
            ((Transaction.group_id == group_id) & (Transaction.type == "SHARED"))
            | ((Transaction.type == "PERSONAL") & (Transaction.recorded_by_id == current_user_id))
        )
    else:
        member_groups = select(GroupMember.group_id).where(GroupMember.user_id == current_user_id)
        return q.where(
            (Transaction.group_id.in_(member_groups) & (Transaction.type == "SHARED"))
            | ((Transaction.type == "PERSONAL") & (Transaction.recorded_by_id == current_user_id))
        )
