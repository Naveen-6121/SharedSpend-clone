from __future__ import annotations

import csv
from datetime import date as date_type
from io import StringIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.session import get_db
from app.models.group import GroupMember
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionOut, TransactionUpdate
from app.services.auth import get_current_user
from app.services.date_filter import DateFilterParams, resolve_date_range

router = APIRouter(prefix="/transactions", tags=["transactions"])


async def _check_group_member(db: AsyncSession, group_id: str, user_id: str) -> bool:
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )
    return result.scalar_one_or_none() is not None


async def _settlement_scope(
    db: AsyncSession,
    current_user_id: str,
    payer_id: Optional[str],
    requested_group_id: Optional[str],
    requested_participant_ids: Optional[list[str]],
) -> tuple[str, list[str]]:
    if not payer_id:
        raise HTTPException(status_code=422, detail="A settlement expense requires a payer")
    group_id = requested_group_id
    if group_id is None:
        own_groups = set((await db.scalars(
            select(GroupMember.group_id).where(GroupMember.user_id == current_user_id)
        )).all())
        payer_groups = set((await db.scalars(
            select(GroupMember.group_id).where(GroupMember.user_id == payer_id)
        )).all())
        common_groups = own_groups & payer_groups
        if len(common_groups) != 1:
            raise HTTPException(
                status_code=422,
                detail="Choose the active group for this settlement expense",
            )
        group_id = next(iter(common_groups))

    result = await db.scalars(
        select(GroupMember.user_id).where(GroupMember.group_id == group_id)
    )
    group_member_ids = set(result.all())
    if current_user_id not in group_member_ids or payer_id not in group_member_ids:
        raise HTTPException(status_code=422, detail="Payer and recorder must belong to the settlement group")

    participant_ids = list(dict.fromkeys(requested_participant_ids or group_member_ids))
    if payer_id not in participant_ids:
        participant_ids.append(payer_id)
    if not participant_ids or not set(participant_ids).issubset(group_member_ids):
        raise HTTPException(status_code=422, detail="Settlement participants must be group members")
    return group_id, participant_ids


async def _reject_settlement_source_edit(db: AsyncSession, transaction_id: str) -> None:
    from app.models.settlement import SettlementRecord

    settlement_id = await db.scalar(
        select(SettlementRecord.id).where(
            SettlementRecord.original_transaction_id == transaction_id
        )
    )
    if settlement_id:
        raise HTTPException(
            status_code=409,
            detail="Delete the linked settlement before changing its source transaction",
        )


async def _filtered_transaction_query(
    db: AsyncSession,
    current_user: User,
    group_id: Optional[str],
    type: Optional[str],
    category_id: Optional[str],
    payer_id: Optional[str],
    date_from: Optional[date_type],
    date_to: Optional[date_type],
    year: Optional[int],
    month: Optional[int],
    week: Optional[int],
    date: Optional[date_type],
    search: Optional[str] = None,
):
    """Build the same visibility and filter conditions for list and export."""
    params = DateFilterParams(
        year=year, month=month, week=week,
        date_param=date, date_from=date_from, date_to=date_to,
    )
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")
    start, end = resolve_date_range(params)
    query = select(Transaction).where(
        Transaction.is_deleted == False,  # noqa: E712
        Transaction.date >= start,
        Transaction.date <= end,
    )

    if group_id:
        if not await _check_group_member(db, group_id, current_user.id):
            raise HTTPException(status_code=403, detail="Not a member of this group")
        query = query.where(
            ((Transaction.group_id == group_id) & (Transaction.type == "SHARED"))
            | ((Transaction.type == "PERSONAL") & (Transaction.recorded_by_id == current_user.id))
        )
    else:
        member_groups = select(GroupMember.group_id).where(GroupMember.user_id == current_user.id)
        query = query.where(
            ((Transaction.group_id.in_(member_groups)) & (Transaction.type == "SHARED"))
            | ((Transaction.type == "PERSONAL") & (Transaction.recorded_by_id == current_user.id))
        )

    if type:
        query = query.where(Transaction.type == type)
    if category_id:
        query = query.where(Transaction.category_id == category_id)
    if payer_id:
        query = query.where(Transaction.payer_id == payer_id)
    if search and search.strip():
        query = query.where(Transaction.description.ilike(f"%{search.strip()}%"))
    return query


def _transaction_filter_params(
    group_id: Optional[str] = None,
    type: Optional[str] = None,
    category_id: Optional[str] = None,
    payer_id: Optional[str] = None,
    date_from: Optional[date_type] = None,
    date_to: Optional[date_type] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    week: Optional[int] = None,
    date: Optional[date_type] = None,
    search: Optional[str] = None,
):
    return (group_id, type, category_id, payer_id, date_from, date_to, year, month, week, date, search)


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
        if payload.add_to_settlement:
            raise HTTPException(status_code=422, detail="Only personal transactions can be added to settlement")
        if not await _check_group_member(db, payload.group_id, current_user.id):
            raise HTTPException(status_code=403, detail="Not a member of this group")

    elif payload.type == "PERSONAL":
        # PERSONAL: group_id must be NULL, payer_id REQUIRED
        if payload.group_id is not None:
            raise HTTPException(status_code=422, detail="group_id must be null for PERSONAL transactions")
        if not payload.payer_id:
            raise HTTPException(status_code=422, detail="payer_id required for PERSONAL transactions")

    settlement_group_id = None
    settlement_participant_ids = None
    if payload.type == "PERSONAL" and payload.add_to_settlement:
        settlement_group_id, settlement_participant_ids = await _settlement_scope(
            db,
            current_user.id,
            payload.payer_id,
            payload.settlement_group_id,
            payload.settlement_participant_ids,
        )

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
        settlement_group_id=settlement_group_id,
        settlement_participant_ids=settlement_participant_ids,
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
    month: Optional[int] = Query(None, ge=1, le=12),
    week: Optional[int] = Query(None, ge=1, le=53),
    date: Optional[date_type] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    response: Response = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = await _filtered_transaction_query(db, current_user, *_transaction_filter_params(
        group_id, type, category_id, payer_id, date_from, date_to, year, month, week, date, search
    ))
    q = q.order_by(Transaction.date.desc(), Transaction.created_at.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    offset = (page - 1) * page_size
    q = q.offset(offset).limit(page_size)

    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total or 0)
    return result.scalars().all()


@router.get("/export")
async def export_transactions(
    group_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    payer_id: Optional[str] = Query(None),
    date_from: Optional[date_type] = Query(None),
    date_to: Optional[date_type] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    week: Optional[int] = Query(None, ge=1, le=53),
    date: Optional[date_type] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payer = aliased(User)
    recorder = aliased(User)
    query = await _filtered_transaction_query(db, current_user, *_transaction_filter_params(
        group_id, type, category_id, payer_id, date_from, date_to, year, month, week, date, search
    ))
    query = (
        query.add_columns(Category.name, payer.display_name, payer.username,
                          recorder.display_name, recorder.username)
        .outerjoin(Category, Transaction.category_id == Category.id)
        .outerjoin(payer, Transaction.payer_id == payer.id)
        .outerjoin(recorder, Transaction.recorded_by_id == recorder.id)
        .order_by(Transaction.date.desc(), Transaction.created_at.desc())
    )
    result = await db.execute(query)

    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "id", "date", "amount", "type", "description", "category", "category_id",
        "payer", "payer_id", "recorded_by", "recorded_by_id", "group_id", "notes",
        "add_to_settlement", "created_at", "updated_at",
    ])
    for txn, category_name, payer_display, payer_username, recorder_display, recorder_username in result:
        writer.writerow([
            txn.id, txn.date.isoformat(), format(txn.amount, "f"), txn.type, txn.description,
            category_name or "", txn.category_id or "",
            payer_display or payer_username or "", txn.payer_id or "",
            recorder_display or recorder_username or "", txn.recorded_by_id,
            txn.group_id or "", txn.notes or "", str(txn.add_to_settlement).lower(),
            txn.created_at.isoformat(), txn.updated_at.isoformat(),
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="transactions.csv"'},
    )


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

    if txn.settlement_record_id is not None:
        raise HTTPException(status_code=409, detail="Settlement payment records cannot be edited")

    await _reject_settlement_source_edit(db, txn.id)

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
    new_add_to_settlement = (
        payload.add_to_settlement
        if payload.add_to_settlement is not None
        else txn.add_to_settlement
    )

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

    if new_type == "PERSONAL" and new_add_to_settlement:
        scope_group_id = (
            payload.settlement_group_id
            if "settlement_group_id" in payload.model_fields_set
            else txn.settlement_group_id
        )
        participants = (
            payload.settlement_participant_ids
            if "settlement_participant_ids" in payload.model_fields_set
            else txn.settlement_participant_ids
        )
        txn.settlement_group_id, txn.settlement_participant_ids = await _settlement_scope(
            db, current_user.id, txn.payer_id, scope_group_id, participants
        )
        txn.add_to_settlement = True
    else:
        txn.add_to_settlement = False
        txn.settlement_group_id = None
        txn.settlement_participant_ids = None

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

    if txn.settlement_record_id is not None:
        raise HTTPException(status_code=409, detail="Settlement payment records cannot be deleted")

    await _reject_settlement_source_edit(db, txn.id)

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
