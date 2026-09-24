"""Settlements linked to the personal expenses that created each obligation."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.group import GroupMember
from app.models.settlement import SettlementRecord
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.settlement import (
    SettlementRecordCreate,
    SettlementRecordOut,
    SettlementTransferOut,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/settlements", tags=["settlements"])


async def _member_ids(db: AsyncSession, group_id: str) -> set[str]:
    result = await db.execute(
        select(GroupMember.user_id).where(GroupMember.group_id == group_id)
    )
    return set(result.scalars().all())


async def _check_member(db: AsyncSession, group_id: str, user_id: str) -> bool:
    return user_id in await _member_ids(db, group_id)


def _split_amount(amount: Decimal, member_ids: set[str], payer_id: str) -> dict[str, Decimal]:
    """Split cents evenly and assign any remainder pennies deterministically."""
    if not member_ids:
        return {}
    cents = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    base, remainder = divmod(cents, len(member_ids))
    shares = {user_id: base for user_id in member_ids}
    penny_order = [payer_id, *sorted(member_ids - {payer_id})]
    for user_id in penny_order[:remainder]:
        shares[user_id] += 1
    return {user_id: (Decimal(value) / 100) for user_id, value in shares.items()}


async def _record_payload(db: AsyncSession, record: SettlementRecord) -> dict:
    payment_id = await db.scalar(
        select(Transaction.id).where(Transaction.settlement_record_id == record.id)
    )
    return {
        "id": record.id,
        "group_id": record.group_id,
        "from_user_id": record.from_user_id,
        "to_user_id": record.to_user_id,
        "amount": record.amount,
        "original_transaction_id": record.original_transaction_id,
        "original_description": record.original_description,
        "original_amount": record.original_amount,
        "original_transaction_date": record.original_transaction_date,
        "payment_transaction_id": payment_id,
        "status": record.status,
        "settled_at": record.settled_at,
        "created_at": record.created_at,
    }


@router.get("/groups/{group_id}/calculate", response_model=list[SettlementTransferOut])
async def calculate_settlements(
    group_id: str,
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return each member's share of each opted-in personal expense."""
    member_ids = await _member_ids(db, group_id)
    if current_user.id not in member_ids:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    if not member_ids:
        return []

    query = select(Transaction).where(
        Transaction.type == "PERSONAL",
        Transaction.add_to_settlement.is_(True),
        Transaction.settlement_group_id == group_id,
        Transaction.is_deleted.is_(False),
        Transaction.payer_id.in_(member_ids),
        Transaction.recorded_by_id.in_(member_ids),
    )
    if year is not None:
        query = query.where(extract("year", Transaction.date) == year)
    if month is not None:
        query = query.where(extract("month", Transaction.date) == month)

    result = await db.execute(query.order_by(Transaction.date, Transaction.created_at))
    transfers: list[dict] = []
    for transaction in result.scalars():
        payer_id = transaction.payer_id
        if payer_id is None or payer_id not in member_ids:
            continue
        participant_ids = set(transaction.settlement_participant_ids or member_ids)
        if not participant_ids.issubset(member_ids) or payer_id not in participant_ids:
            continue
        shares = _split_amount(Decimal(transaction.amount), participant_ids, payer_id)
        for debtor_id, share in shares.items():
            if debtor_id == payer_id or share <= 0:
                continue
            transfers.append({
                "from_user_id": debtor_id,
                "to_user_id": payer_id,
                "amount": share,
                "original_transaction_id": transaction.id,
                "original_description": transaction.description,
                "original_amount": transaction.amount,
                "original_transaction_date": transaction.date,
            })
    return transfers


@router.get("/groups/{group_id}", response_model=list[SettlementRecordOut])
async def list_settlements(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List settlement history with the expense and payment references."""
    if not await _check_member(db, group_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a member of this group")
    result = await db.execute(
        select(SettlementRecord)
        .where(SettlementRecord.group_id == group_id)
        .order_by(SettlementRecord.created_at.desc())
    )
    return [await _record_payload(db, record) for record in result.scalars()]


@router.post(
    "/groups/{group_id}",
    response_model=SettlementRecordOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_settlement(
    group_id: str,
    payload: SettlementRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create one pending obligation from an opted-in personal expense."""
    member_ids = await _member_ids(db, group_id)
    if current_user.id not in member_ids:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    if payload.from_user_id not in member_ids:
        raise HTTPException(status_code=400, detail="Debtor is not a member of this group")

    transaction = await db.get(Transaction, payload.original_transaction_id)
    if (
        transaction is None
        or transaction.is_deleted
        or transaction.type != "PERSONAL"
        or not transaction.add_to_settlement
        or transaction.payer_id not in member_ids
        or transaction.recorded_by_id not in member_ids
    ):
        raise HTTPException(status_code=404, detail="Settlement expense not found")
    if payload.from_user_id == transaction.payer_id:
        raise HTTPException(status_code=400, detail="The payer does not owe their own expense")

    participant_ids = set(transaction.settlement_participant_ids or member_ids)
    if not participant_ids.issubset(member_ids) or transaction.payer_id not in participant_ids:
        raise HTTPException(status_code=409, detail="Settlement participants are no longer valid")
    amount = _split_amount(Decimal(transaction.amount), participant_ids, transaction.payer_id).get(
        payload.from_user_id, Decimal("0.00")
    )
    if amount <= 0:
        raise HTTPException(status_code=400, detail="This member has no share to settle")

    existing = await db.scalar(
        select(SettlementRecord).where(
            SettlementRecord.group_id == group_id,
            SettlementRecord.original_transaction_id == transaction.id,
            SettlementRecord.from_user_id == payload.from_user_id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Settlement already exists for this expense")

    record = SettlementRecord(
        group_id=group_id,
        from_user_id=payload.from_user_id,
        to_user_id=transaction.payer_id,
        amount=amount,
        original_transaction_id=transaction.id,
        original_description=transaction.description,
        original_amount=transaction.amount,
        original_transaction_date=transaction.date,
        status="PENDING",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return await _record_payload(db, record)


@router.put("/{settlement_id}/settle", response_model=SettlementRecordOut)
async def mark_settled(
    settlement_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record the debtor's payment as a linked, private transaction."""
    record = await db.get(SettlementRecord, settlement_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Settlement not found")
    if not await _check_member(db, record.group_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a member of this group")
    if current_user.id != record.from_user_id:
        raise HTTPException(status_code=403, detail="Only the debtor can record this payment")
    if record.status == "SETTLED":
        return await _record_payload(db, record)

    original = (
        await db.get(Transaction, record.original_transaction_id)
        if record.original_transaction_id
        else None
    )
    payee = await db.get(User, record.to_user_id)
    settled_at = datetime.now(timezone.utc)
    original_title = record.original_description or (original.description if original else "expense")
    payment = Transaction(
        date=settled_at.date(),
        amount=record.amount,
        description=f"Payment to {payee.display_name or payee.username} · {original_title}",
        type="PERSONAL",
        payer_id=record.from_user_id,
        recorded_by_id=record.from_user_id,
        group_id=None,
        category_id=None,
        notes=f"Settlement payment for record {record.id}",
        add_to_settlement=False,
        settlement_record_id=record.id,
        is_deleted=False,
    )
    record.status = "SETTLED"
    record.settled_at = settled_at
    db.add_all([record, payment])
    await db.commit()
    await db.refresh(record)
    await db.refresh(payment)
    return await _record_payload(db, record)


@router.delete("/{settlement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_settlement(
    settlement_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a settlement and its generated payment row, if any."""
    record = await db.get(SettlementRecord, settlement_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Settlement not found")
    if not await _check_member(db, record.group_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a member of this group")
    payment = await db.scalar(
        select(Transaction).where(Transaction.settlement_record_id == record.id)
    )
    if payment:
        await db.delete(payment)
    await db.delete(record)
    await db.commit()
