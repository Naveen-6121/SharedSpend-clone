from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.category import Category
from app.models.group import GroupMember
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryDeleteRequest, CategoryOut, CategoryUpdate
from app.services.auth import get_current_user

router = APIRouter(tags=["categories"])

GLOBAL_CATEGORIES = [
    {"name": "Groceries", "icon": "🛒"},
    {"name": "Fruits & Vegetables", "icon": "🥦"},
    {"name": "Food & Dining", "icon": "🍽️"},
    {"name": "Transport", "icon": "🚗"},
    {"name": "Utilities", "icon": "💡"},
    {"name": "Entertainment", "icon": "🎬"},
    {"name": "Personal Care", "icon": "💊"},
]


async def seed_global_categories(db: AsyncSession) -> None:
    for cat_data in GLOBAL_CATEGORIES:
        result = await db.execute(
            select(Category).where(
                Category.name == cat_data["name"], Category.is_global == True  # noqa: E712
            )
        )
        if not result.scalar_one_or_none():
            db.add(Category(name=cat_data["name"], icon=cat_data["icon"], is_global=True))
    await db.commit()


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    group_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Always return global categories
    result = await db.execute(select(Category).where(Category.is_global == True))  # noqa: E712
    cats = list(result.scalars().all())

    if group_id:
        # Verify membership
        mem = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id, GroupMember.user_id == current_user.id
            )
        )
        if mem.scalar_one_or_none():
            scoped = await db.execute(
                select(Category).where(Category.group_id == group_id)
            )
            cats.extend(scoped.scalars().all())
    else:
        # Return group-scoped categories for all groups the user belongs to
        member_groups = await db.execute(
            select(GroupMember.group_id).where(GroupMember.user_id == current_user.id)
        )
        gids = [r[0] for r in member_groups.all()]
        if gids:
            scoped = await db.execute(
                select(Category).where(Category.group_id.in_(gids))
            )
            cats.extend(scoped.scalars().all())

    return cats


@router.post("/groups/{group_id}/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_group_category(
    group_id: str,
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mem = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == current_user.id
        )
    )
    if not mem.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this group")

    cat = Category(
        name=payload.name,
        icon=payload.icon,
        is_global=False,
        group_id=group_id,
        keyword_hints=payload.keyword_hints,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@router.put("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: str,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Category).where(Category.id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check permission: global categories modifiable by anyone (MVP simplification), scoped by member
    if not cat.is_global and cat.group_id:
        mem = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == cat.group_id, GroupMember.user_id == current_user.id
            )
        )
        if not mem.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a member of this group")

    if payload.name is not None:
        cat.name = payload.name
    if payload.icon is not None:
        cat.icon = payload.icon
    if payload.keyword_hints is not None:
        cat.keyword_hints = payload.keyword_hints
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: str,
    payload: CategoryDeleteRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Category).where(Category.id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check if any transactions reference this category
    txn_res = await db.execute(
        select(Transaction).where(
            Transaction.category_id == category_id,
            Transaction.is_deleted == False,  # noqa: E712
        )
    )
    txns = txn_res.scalars().all()

    if txns:
        reassign_id = payload.reassign_to_category_id if payload else None
        if not reassign_id:
            raise HTTPException(
                status_code=422,
                detail="Transactions reference this category. Provide reassign_to_category_id.",
            )
        # Verify reassign target exists
        target_res = await db.execute(select(Category).where(Category.id == reassign_id))
        if not target_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Reassign target category not found")

        await db.execute(
            update(Transaction)
            .where(Transaction.category_id == category_id)
            .values(category_id=reassign_id)
        )

    await db.delete(cat)
    await db.commit()
