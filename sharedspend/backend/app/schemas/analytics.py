from datetime import date as DateType
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class MemberPersonal(BaseModel):
    user_id: str
    display_name: Optional[str]
    personal_spent: Decimal


class MemberPaid(BaseModel):
    user_id: str
    display_name: Optional[str]
    paid: Decimal


class SummaryOut(BaseModel):
    budget: Optional[Decimal]
    shared_spent: Decimal
    remaining: Optional[Decimal]
    utilization_pct: Optional[Decimal]
    personal_by_member: List[MemberPersonal]
    paid_by_member: List[MemberPaid]


class CategorySpend(BaseModel):
    category_id: Optional[str]
    category_name: Optional[str]
    amount: Decimal
    count: int


class DailySpend(BaseModel):
    date: DateType
    shared: Decimal
    personal: Decimal


class WeeklySpend(BaseModel):
    year: int
    week: int
    shared: Decimal
    personal: Decimal


class MonthlySpend(BaseModel):
    year: int
    month: int
    shared: Decimal
    personal: Decimal


class YearlySpend(BaseModel):
    year: int
    shared: Decimal
    personal: Decimal


class MemberContribution(BaseModel):
    user_id: str
    display_name: Optional[str]
    paid: Decimal
    personal_spent: Decimal


class HighestItem(BaseModel):
    name: Optional[str] = None
    amount: Decimal
    date: Optional[DateType] = None


class InsightsOut(BaseModel):
    highest_category: Optional[HighestItem]
    highest_day: Optional[HighestItem]
    largest_transactions: list
    trend: Optional[str]


class ForecastOut(BaseModel):
    projected_spend: Optional[Decimal]
    budget: Optional[Decimal]
    on_track: Optional[bool]
    days_elapsed: int
    days_in_month: int
