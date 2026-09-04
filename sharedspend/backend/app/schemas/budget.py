from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BudgetCreate(BaseModel):
    year: int
    month: int
    amount: Decimal


class BudgetUpdate(BaseModel):
    amount: Decimal


class BudgetOut(BaseModel):
    id: str
    group_id: str
    year: int
    month: int
    amount: Decimal
    created_by_id: str
    created_at: datetime

    model_config = {"from_attributes": True}
