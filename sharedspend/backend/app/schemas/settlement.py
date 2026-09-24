from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class SettlementRecordOut(BaseModel):
    id: str
    group_id: str
    from_user_id: str
    to_user_id: str
    amount: Decimal
    original_transaction_id: Optional[str] = None
    original_description: Optional[str] = None
    original_amount: Optional[Decimal] = None
    original_transaction_date: Optional[date] = None
    payment_transaction_id: Optional[str] = None
    status: str  # PENDING | SETTLED
    settled_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class SettlementRecordCreate(BaseModel):
    from_user_id: str
    original_transaction_id: str


class SettlementTransferOut(BaseModel):
    from_user_id: str
    to_user_id: str
    amount: Decimal
    original_transaction_id: str
    original_description: str
    original_amount: Decimal
    original_transaction_date: date


class SettleRequest(BaseModel):
    """Mark a pending settlement as settled."""
    pass
