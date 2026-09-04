from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.budget import BudgetPeriod
from app.models.group import GroupMember
from app.models.user import User
from app.schemas.budget import BudgetCreate, BudgetOut, BudgetUpdate
from app.services.auth import get_current_user

router = APIRouter(tags=["budgets"])


async def _require_member(db: AsyncSession, group_id: str, user_id: str) -> GroupMember:
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    return m


@router.get("/groups/{group_id}/budgets", response_model=list[BudgetOut])  # noqa - keep as-is
async def list_budgets(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_member(db, group_id, current_user.id)
    result = await db.execute(
        select(BudgetPeriod).where(BudgetPeriod.group_id == group_id)
    )
    return result.scalars().all()


@router.post("/groups/{group_id}/budgets", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
async def set_budget(
    group_id: str,
    payload: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_member(db, group_id, current_user.id)

    existing = await db.execute(
        select(BudgetPeriod).where(
            BudgetPeriod.group_id == group_id,
            BudgetPeriod.year == payload.year,
            BudgetPeriod.month == payload.month,
        )
    )
    bp = existing.scalar_one_or_none()
    if bp:
        bp.amount = payload.amount
    else:
        bp = BudgetPeriod(
            group_id=group_id,
            year=payload.year,
            month=payload.month,
            amount=payload.amount,
            created_by_id=current_user.id,
        )
        db.add(bp)
    await db.commit()
    await db.refresh(bp)
    return bp


@router.put("/groups/{group_id}/budgets/{year}/{month}", response_model=BudgetOut)
async def update_budget(
    group_id: str,
    year: int,
    month: int,
    payload: BudgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_member(db, group_id, current_user.id)
    result = await db.execute(
        select(BudgetPeriod).where(
            BudgetPeriod.group_id == group_id,
            BudgetPeriod.year == year,
            BudgetPeriod.month == month,
        )
    )
    bp = result.scalar_one_or_none()
    if not bp:
        raise HTTPException(status_code=404, detail="Budget period not found")
    bp.amount = payload.amount
    db.add(bp)
    await db.commit()
    await db.refresh(bp)
    return bp
