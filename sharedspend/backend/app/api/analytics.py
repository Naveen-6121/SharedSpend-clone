from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.group import GroupMember
from app.models.user import User
from app.schemas.analytics import (
    CategorySpend,
    DailySpend,
    ForecastOut,
    InsightsOut,
    MemberContribution,
    MonthlySpend,
    SummaryOut,
    WeeklySpend,
    YearlySpend,
)
from app.services.analytics import (
    get_by_category,
    get_by_day,
    get_by_month,
    get_by_week,
    get_by_year,
    get_forecast,
    get_insights,
    get_members,
    get_summary,
)
from app.services.auth import get_current_user
from app.services.date_filter import DateFilterParams

async def _require_group_member(
    group_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if group_id:
        member_id = await db.scalar(
            select(GroupMember.id).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == current_user.id,
            )
        )
        if member_id is None:
            raise HTTPException(status_code=403, detail="Not a member of this group")


router = APIRouter(
    prefix="/analytics", tags=["analytics"], dependencies=[Depends(_require_group_member)]
)


def _date_params(
    group_id: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    week: Optional[int] = Query(None, ge=1, le=53),
    date: Optional[date] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
) -> tuple:
    date_params = DateFilterParams(
        year=year, month=month, week=week,
        date_param=date, date_from=date_from, date_to=date_to
    )
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")
    return group_id, date_params


@router.get("/summary", response_model=SummaryOut)
async def summary(
    params: tuple = Depends(_date_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group_id, dp = params
    data = await get_summary(db, current_user.id, group_id, dp)
    return SummaryOut(**data)


@router.get("/by-category", response_model=list[CategorySpend])
async def by_category(
    params: tuple = Depends(_date_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group_id, dp = params
    return await get_by_category(db, current_user.id, group_id, dp)


@router.get("/by-day", response_model=list[DailySpend])
async def by_day(
    params: tuple = Depends(_date_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group_id, dp = params
    return await get_by_day(db, current_user.id, group_id, dp)


@router.get("/by-week", response_model=list[WeeklySpend])
async def by_week(
    params: tuple = Depends(_date_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group_id, dp = params
    return await get_by_week(db, current_user.id, group_id, dp)


@router.get("/by-month", response_model=list[MonthlySpend])
async def by_month(
    params: tuple = Depends(_date_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group_id, dp = params
    return await get_by_month(db, current_user.id, group_id, dp)


@router.get("/by-year", response_model=list[YearlySpend])
async def by_year(
    params: tuple = Depends(_date_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group_id, dp = params
    return await get_by_year(db, current_user.id, group_id, dp)


@router.get("/members", response_model=list[MemberContribution])
async def members(
    params: tuple = Depends(_date_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group_id, dp = params
    return await get_members(db, current_user.id, group_id, dp)


@router.get("/insights", response_model=InsightsOut)
async def insights(
    params: tuple = Depends(_date_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group_id, dp = params
    data = await get_insights(db, current_user.id, group_id, dp)
    return InsightsOut(**data)


@router.get("/forecast", response_model=ForecastOut)
async def forecast(
    group_id: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import date as _date
    today = _date.today()
    y = year or today.year
    m = month or today.month
    data = await get_forecast(db, current_user.id, group_id, y, m)
    return ForecastOut(**data)
