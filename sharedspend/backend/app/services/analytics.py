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


async def _get_budget(db: AsyncSession, group_id: str, year: int, month: int) -> Optional[BudgetPeriod]:
    result = await db.execute(
        select(BudgetPeriod).where(
            BudgetPeriod.group_id == group_id,
            BudgetPeriod.year == year,
            BudgetPeriod.month == month,
        )
    )
    return result.scalar_one_or_none()


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

    shared_spent = Decimal(str((await db.execute(shared_q)).scalar()))

    # budget
    budget_amount: Optional[Decimal] = None
    if group_id and params.year and params.month:
        bp = await _get_budget(db, group_id, params.year, params.month)
        if bp:
            budget_amount = Decimal(str(bp.amount))

    remaining = (budget_amount - shared_spent) if budget_amount is not None else None
    utilization = (
        (shared_spent / budget_amount * 100).quantize(Decimal("0.01"))
        if budget_amount
        else None
    )

    # personal_by_member – current user only (personal is private)
    personal_q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.type == "PERSONAL",
        Transaction.recorded_by_id == current_user_id,
        Transaction.is_deleted == False,  # noqa: E712
        Transaction.date >= start,
        Transaction.date <= end,
    )
    personal_total = Decimal(str((await db.execute(personal_q)).scalar()))

    # user display name
    user_result = await db.execute(select(User).where(User.id == current_user_id))
    user = user_result.scalar_one_or_none()
    personal_by_member = [
        {
            "user_id": current_user_id,
            "display_name": user.display_name if user else None,
            "personal_spent": personal_total,
        }
    ]

    # paid_by_member — personal transactions marked add_to_settlement, aggregated by payer
    # (SHARED transactions no longer have a payer under the new model)
    paid_q = (
        select(Transaction.payer_id, func.sum(Transaction.amount).label("paid"))
        .where(
            Transaction.type == "PERSONAL",
            Transaction.add_to_settlement == True,  # noqa: E712
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
            Transaction.payer_id.isnot(None),
        )
        .group_by(Transaction.payer_id)
    )
    if group_id:
        # only personal txns paid by group members
        member_ids_q = select(GroupMember.user_id).where(GroupMember.group_id == group_id)
        paid_q = paid_q.where(Transaction.payer_id.in_(member_ids_q))
    else:
        member_groups2 = select(GroupMember.group_id).where(GroupMember.user_id == current_user_id)
        member_ids_q2 = select(GroupMember.user_id).where(GroupMember.group_id.in_(member_groups2))
        paid_q = paid_q.where(Transaction.payer_id.in_(member_ids_q2))

    paid_rows = (await db.execute(paid_q)).all()
    paid_by_member = []
    for row in paid_rows:
        u = (await db.execute(select(User).where(User.id == row.payer_id))).scalar_one_or_none()
        paid_by_member.append(
            {
                "user_id": row.payer_id,
                "display_name": u.display_name if u else None,
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
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(Transaction.category_id, Category.name)
    )
    if group_id:
        q = q.where(Transaction.group_id == group_id, Transaction.type == "SHARED")
    else:
        member_groups = select(GroupMember.group_id).where(GroupMember.user_id == current_user_id)
        q = q.where(
            (Transaction.group_id.in_(member_groups) & (Transaction.type == "SHARED"))
            | (Transaction.recorded_by_id == current_user_id)
        )
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

    # members of the group
    members_res = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id)
    )
    members = members_res.scalars().all()

    result = []
    for m in members:
        user_res = await db.execute(select(User).where(User.id == m.user_id))
        user = user_res.scalar_one_or_none()

        # Under new model: SHARED has no payer.
        # "paid" = personal transactions by this member that are marked add_to_settlement
        paid_res = await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.type == "PERSONAL",
                Transaction.add_to_settlement == True,  # noqa: E712
                Transaction.payer_id == m.user_id,
                Transaction.is_deleted == False,  # noqa: E712
                Transaction.date >= start,
                Transaction.date <= end,
            )
        )
        paid = Decimal(str(paid_res.scalar()))

        personal_res = await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.type == "PERSONAL",
                Transaction.recorded_by_id == m.user_id,
                Transaction.is_deleted == False,  # noqa: E712
                Transaction.date >= start,
                Transaction.date <= end,
            )
        )
        personal = Decimal(str(personal_res.scalar()))

        result.append(
            {
                "user_id": m.user_id,
                "display_name": user.display_name if user else None,
                "paid": paid,
                "personal_spent": personal,
            }
        )
    return result


async def get_insights(
    db: AsyncSession,
    current_user_id: str,
    group_id: Optional[str],
    params: DateFilterParams,
) -> dict:
    start, end = resolve_date_range(params)

    # highest category
    cat_q = (
        select(
            Category.name,
            func.sum(Transaction.amount).label("total"),
        )
        .outerjoin(Category, Transaction.category_id == Category.id)
        .where(
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(Category.name)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(1)
    )
    cat_q = _apply_visibility(cat_q, current_user_id, group_id)
    cat_row = (await db.execute(cat_q)).first()
    highest_category = (
        {"name": cat_row.name, "amount": Decimal(str(cat_row.total))} if cat_row else None
    )

    # highest day
    day_q = (
        select(
            Transaction.date,
            func.sum(Transaction.amount).label("total"),
        )
        .where(
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(Transaction.date)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(1)
    )
    day_q = _apply_visibility(day_q, current_user_id, group_id)
    day_row = (await db.execute(day_q)).first()
    highest_day = (
        {"date": day_row.date, "amount": Decimal(str(day_row.total))} if day_row else None
    )

    # largest transactions (top 5)
    txn_q = (
        select(Transaction)
        .where(
            Transaction.is_deleted == False,  # noqa: E712
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

    # trend: compare current month spend vs previous month
    trend = None
    if params.month and params.year:
        prev_month = params.month - 1 if params.month > 1 else 12
        prev_year = params.year if params.month > 1 else params.year - 1
        curr_q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.is_deleted == False,  # noqa: E712
            extract("year", Transaction.date) == params.year,
            extract("month", Transaction.date) == params.month,
        )
        prev_q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.is_deleted == False,  # noqa: E712
            extract("year", Transaction.date) == prev_year,
            extract("month", Transaction.date) == prev_month,
        )
        if group_id:
            curr_q = curr_q.where(Transaction.group_id == group_id)
            prev_q = prev_q.where(Transaction.group_id == group_id)
        curr_total = Decimal(str((await db.execute(curr_q)).scalar()))
        prev_total = Decimal(str((await db.execute(prev_q)).scalar()))
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

    shared_spent = Decimal(str((await db.execute(shared_q)).scalar()))

    projected: Optional[Decimal] = None
    if days_elapsed > 0:
        projected = (shared_spent / days_elapsed * days_in_month).quantize(Decimal("0.01"))

    budget_amount: Optional[Decimal] = None
    on_track: Optional[bool] = None
    if group_id:
        bp = await _get_budget(db, group_id, year, month)
        if bp:
            budget_amount = Decimal(str(bp.amount))
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
    """Apply the standard visibility filter: shared txns in user's groups + own personal."""
    if group_id:
        # Only shared transactions of the specific group (and user's own personal)
        return q.where(
            (Transaction.group_id == group_id) | (Transaction.recorded_by_id == current_user_id)
        )
    else:
        member_groups = select(GroupMember.group_id).where(GroupMember.user_id == current_user_id)
        return q.where(
            (Transaction.group_id.in_(member_groups) & (Transaction.type == "SHARED"))
            | (Transaction.recorded_by_id == current_user_id)
        )
