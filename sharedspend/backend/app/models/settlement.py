from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SettlementRecord(Base):
    """Persisted settlement between two group members."""
    __tablename__ = "settlement_records"
    __table_args__ = (
        UniqueConstraint(
            "group_id", "original_transaction_id", "from_user_id",
            name="uq_settlement_original_debtor",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"), nullable=False)
    from_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    to_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    original_transaction_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )
    original_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    original_transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    # Status: PENDING or SETTLED
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "SETTLED", name="settlement_status"),
        nullable=False,
        default="PENDING",
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
