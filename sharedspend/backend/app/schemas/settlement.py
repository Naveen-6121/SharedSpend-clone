from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class SettlementRecordOut(BaseModel):
    id: str
    group_id: str
    from_user_id: str
    to_user_id: str
    amount: Decimal
    status: str  # PENDING | SETTLED
    settled_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class SettlementRecordCreate(BaseModel):
    from_user_id: str
    to_user_id: str
    amount: Decimal


class SettleRequest(BaseModel):
    """Mark a pending settlement as settled."""
    pass
