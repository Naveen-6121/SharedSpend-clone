from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


class TransactionCreate(BaseModel):
    date: date
    amount: Decimal
    description: str
    type: str  # SHARED | PERSONAL
    payer_id: Optional[str] = None
    group_id: Optional[str] = None
    category_id: Optional[str] = None
    suggested_category_id: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("SHARED", "PERSONAL"):
            raise ValueError("type must be SHARED or PERSONAL")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class TransactionUpdate(BaseModel):
    date: Optional[date] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None
    type: Optional[str] = None
    payer_id: Optional[str] = None
    group_id: Optional[str] = None
    category_id: Optional[str] = None
    suggested_category_id: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ("SHARED", "PERSONAL"):
            raise ValueError("type must be SHARED or PERSONAL")
        return v


class TransactionOut(BaseModel):
    id: str
    date: date
    amount: Decimal
    description: str
    type: str
    payer_id: Optional[str]
    recorded_by_id: str
    group_id: Optional[str]
    category_id: Optional[str]
    suggested_category_id: Optional[str]
    notes: Optional[str]
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransactionListParams(BaseModel):
    group_id: Optional[str] = None
    type: Optional[str] = None
    category_id: Optional[str] = None
    payer_id: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    year: Optional[int] = None
    month: Optional[int] = None
    week: Optional[int] = None
    date: Optional[date] = None
    page: int = 1
    page_size: int = 20
