"""
Settlements API
---------------
Computes who owes whom based on PERSONAL transactions with add_to_settlement=True.
Persists settlement records for a group so "Mark as Settled" survives page reloads.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.group import GroupMember
from app.models.settlement import SettlementRecord
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.settlement import SettlementRecordOut
from app.services.auth import get_current_user

router = APIRouter(prefix="/settlements", tags=["settlements"])


# ── helpers ──────────────────────────────────────────────────────────────────

async def _check_member(db: AsyncSession, group_id: str, user_id: str) -> bool:
    r = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
    )
    return r.scalar_one_or_none() is not None


def _calc_transfers(
    balances: dict[str, float],
) -> list[dict]:
    """
    Minimum-transfer debt-simplification.
    balances: {user_id: net_balance}  positive = owed money, negative = owes money
    """
    creditors = sorted(
        [(uid, bal) for uid, bal in balances.items() if bal > 0.005],
        key=lambda x: -x[1],
    )
    debtors = sorted(
        [(uid, -bal) for uid, bal in balances.items() if bal < -0.005],
        key=lambda x: -x[1],
    )

    transfers: list[dict] = []
    ci, di = 0, 0
    c_bal = [b for _, b in creditors]
    d_bal = [b for _, b in debtors]

    while ci < len(creditors) and di < len(debtors):
        amount = min(c_bal[ci], d_bal[di])
        if amount > 0.005:
            transfers.append({
                "from_user_id": debtors[di][0],
                "to_user_id": creditors[ci][0],
                "amount": round(amount, 2),
            })
        c_bal[ci] -= amount
        d_bal[di] -= amount
        if c_bal[ci] < 0.005:
            ci += 1
        if d_bal[di] < 0.005:
            di += 1

    return transfers


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/groups/{group_id}/calculate", response_model=list[dict])
async def calculate_settlements(
    group_id: str,
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the minimum transfers needed to settle personal expenses
    for the group that have add_to_settlement=True.
    """
    if not await _check_member(db, group_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a member of this group")

    # Fetch all group members
    members_r = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id)
    )
    members = members_r.scalars().all()
    member_ids = {m.user_id for m in members}

    if not member_ids:
        return []

    # Build query for personal transactions with add_to_settlement=True
    q = select(Transaction).where(
        Transaction.type == "PERSONAL",
        Transaction.add_to_settlement == True,  # noqa: E712
        Transaction.is_deleted == False,  # noqa: E712
        Transaction.payer_id.in_(member_ids),
        Transaction.recorded_by_id.in_(member_ids),
    )

    if year is not None:
        from sqlalchemy import extract
        q = q.where(extract("year", Transaction.date) == year)
    if month is not None:
        from sqlalchemy import extract
        q = q.where(extract("month", Transaction.date) == month)

    result = await db.execute(q)
    txns = result.scalars().all()

    if not txns:
        return []

    # Each settlement transaction: payer paid for everyone equally
    # net balance per member: positive = others owe them
    n = len(member_ids)
    balances: dict[str, float] = {uid: 0.0 for uid in member_ids}

    for txn in txns:
        amount = float(txn.amount)
        share = amount / n
        # payer gets credit for the full amount they paid
        balances[txn.payer_id] = round(balances[txn.payer_id] + amount - share, 6)
        # everyone else owes their share
        for uid in member_ids:
            if uid != txn.payer_id:
                balances[uid] = round(balances[uid] - share, 6)

    return _calc_transfers(balances)


@router.get("/groups/{group_id}", response_model=list[SettlementRecordOut])
async def list_settlements(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all persisted settlement records for a group."""
    if not await _check_member(db, group_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a member of this group")

    r = await db.execute(
        select(SettlementRecord)
        .where(SettlementRecord.group_id == group_id)
        .order_by(SettlementRecord.created_at.desc())
    )
    return r.scalars().all()


@router.post("/groups/{group_id}", response_model=SettlementRecordOut, status_code=status.HTTP_201_CREATED)
async def create_settlement(
    group_id: str,
    from_user_id: str,
    to_user_id: str,
    amount: Decimal,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist a settlement record (PENDING)."""
    if not await _check_member(db, group_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a member of this group")

    record = SettlementRecord(
        group_id=group_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        amount=amount,
        status="PENDING",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.put("/{settlement_id}/settle", response_model=SettlementRecordOut)
async def mark_settled(
    settlement_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a settlement record as SETTLED."""
    r = await db.execute(
        select(SettlementRecord).where(SettlementRecord.id == settlement_id)
    )
    record = r.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Settlement not found")

    if not await _check_member(db, record.group_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a member of this group")

    record.status = "SETTLED"
    record.settled_at = datetime.now(timezone.utc)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/{settlement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_settlement(
    settlement_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a settlement record."""
    r = await db.execute(
        select(SettlementRecord).where(SettlementRecord.id == settlement_id)
    )
    record = r.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Settlement not found")

    if not await _check_member(db, record.group_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a member of this group")

    await db.delete(record)
    await db.commit()
