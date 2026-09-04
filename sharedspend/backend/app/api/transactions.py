from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.group import GroupMember
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionOut, TransactionUpdate
from app.services.auth import get_current_user
from app.services.date_filter import DateFilterParams, resolve_date_range
from datetime import date as date_type

router = APIRouter(prefix="/transactions", tags=["transactions"])


async def _check_group_member(db: AsyncSession, group_id: str, user_id: str) -> bool:
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )
    return result.scalar_one_or_none() is not None


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.type == "SHARED":
        # SHARED: requires group_id, payer_id must be NULL
        if not payload.group_id:
            raise HTTPException(status_code=422, detail="group_id required for SHARED transactions")
        if payload.payer_id is not None:
            raise HTTPException(status_code=422, detail="payer_id must be null for SHARED transactions")
        if not await _check_group_member(db, payload.group_id, current_user.id):
            raise HTTPException(status_code=403, detail="Not a member of this group")

    elif payload.type == "PERSONAL":
        # PERSONAL: group_id must be NULL, payer_id REQUIRED
        if payload.group_id is not None:
            raise HTTPException(status_code=422, detail="group_id must be null for PERSONAL transactions")
        if not payload.payer_id:
            raise HTTPException(status_code=422, detail="payer_id required for PERSONAL transactions")

    txn = Transaction(
        date=payload.date,
        amount=payload.amount,
        description=payload.description,
        type=payload.type,
        payer_id=payload.payer_id,
        recorded_by_id=current_user.id,
        group_id=payload.group_id,
        category_id=payload.category_id,
        suggested_category_id=payload.suggested_category_id,
        notes=payload.notes,
        add_to_settlement=payload.add_to_settlement,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    group_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    payer_id: Optional[str] = Query(None),
    date_from: Optional[date_type] = Query(None),
    date_to: Optional[date_type] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    week: Optional[int] = Query(None),
    date: Optional[date_type] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    params = DateFilterParams(
        year=year, month=month, week=week,
        date_param=date, date_from=date_from, date_to=date_to
    )
    start, end = resolve_date_range(params)

    q = select(Transaction).where(
        Transaction.is_deleted == False,  # noqa: E712
        Transaction.date >= start,
        Transaction.date <= end,
    )

    # Visibility: shared in user's groups + own personal
    if group_id:
        if not await _check_group_member(db, group_id, current_user.id):
            raise HTTPException(status_code=403, detail="Not a member of this group")
        q = q.where(
            (Transaction.group_id == group_id) & (Transaction.type == "SHARED")
            | (Transaction.recorded_by_id == current_user.id)
        )
    else:
        member_groups = select(GroupMember.group_id).where(GroupMember.user_id == current_user.id)
        q = q.where(
            (Transaction.group_id.in_(member_groups) & (Transaction.type == "SHARED"))
            | (Transaction.recorded_by_id == current_user.id)
        )

    if type:
        q = q.where(Transaction.type == type)
    if category_id:
        q = q.where(Transaction.category_id == category_id)
    if payer_id:
        q = q.where(Transaction.payer_id == payer_id)

    q = q.order_by(Transaction.date.desc(), Transaction.created_at.desc())
    offset = (page - 1) * page_size
    q = q.offset(offset).limit(page_size)

    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{transaction_id}", response_model=TransactionOut)
async def get_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.is_deleted == False  # noqa: E712
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Visibility check
    if txn.type == "SHARED":
        if not await _check_group_member(db, txn.group_id, current_user.id):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        if txn.recorded_by_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

    return txn


@router.put("/{transaction_id}", response_model=TransactionOut)
async def update_transaction(
    transaction_id: str,
    payload: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.is_deleted == False  # noqa: E712
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Authorization: recorded_by or group owner
    can_edit = txn.recorded_by_id == current_user.id
    if not can_edit and txn.group_id:
        mem_res = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == txn.group_id,
                GroupMember.user_id == current_user.id,
                GroupMember.role == "OWNER",
            )
        )
        can_edit = mem_res.scalar_one_or_none() is not None
    if not can_edit:
        raise HTTPException(status_code=403, detail="Not authorized to edit this transaction")

    new_type = payload.type if payload.type is not None else txn.type

    if new_type == "SHARED":
        # SHARED: group required, payer must be null
        new_group_id = payload.group_id if payload.group_id is not None else txn.group_id
        if not new_group_id:
            raise HTTPException(status_code=422, detail="group_id required for SHARED")
        # If payload explicitly sends payer_id it must be None for SHARED
        if payload.payer_id is not None:
            raise HTTPException(status_code=422, detail="payer_id must be null for SHARED transactions")
        if not await _check_group_member(db, new_group_id, current_user.id):
            raise HTTPException(status_code=403, detail="Not a member of the group")
        txn.group_id = new_group_id
        txn.payer_id = None  # SHARED never has a payer

    elif new_type == "PERSONAL":
        # PERSONAL: no group, payer required
        # Use payload payer_id if provided, else keep existing payer for PERSONAL
        new_payer_id = payload.payer_id if payload.payer_id is not None else txn.payer_id
        if not new_payer_id:
            raise HTTPException(status_code=422, detail="payer_id required for PERSONAL transactions")
        txn.group_id = None
        txn.payer_id = new_payer_id

    txn.type = new_type

    if payload.date is not None:
        txn.date = payload.date
    if payload.amount is not None:
        txn.amount = payload.amount
    if payload.description is not None:
        txn.description = payload.description
    if payload.category_id is not None:
        txn.category_id = payload.category_id
    elif "category_id" in (payload.model_fields_set or set()):
        # explicitly set to None
        txn.category_id = None
    if payload.suggested_category_id is not None:
        txn.suggested_category_id = payload.suggested_category_id
    if payload.notes is not None:
        txn.notes = payload.notes
    if payload.add_to_settlement is not None:
        txn.add_to_settlement = payload.add_to_settlement

    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.is_deleted == False  # noqa: E712
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Authorization
    can_delete = txn.recorded_by_id == current_user.id
    if not can_delete and txn.group_id:
        mem_res = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == txn.group_id,
                GroupMember.user_id == current_user.id,
                GroupMember.role == "OWNER",
            )
        )
        can_delete = mem_res.scalar_one_or_none() is not None
    if not can_delete:
        raise HTTPException(status_code=403, detail="Not authorized")

    txn.is_deleted = True
    db.add(txn)
    await db.commit()
