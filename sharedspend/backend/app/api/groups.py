from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.group import Group, GroupMember
from app.models.user import User
from app.schemas.group import AddMemberRequest, GroupCreate, GroupDetailOut, GroupOut, GroupUpdate, MemberOut
from app.services.auth import get_current_user

router = APIRouter(prefix="/groups", tags=["groups"])


async def _require_member(db: AsyncSession, group_id: str, user_id: str) -> GroupMember:
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    return m


async def _require_owner(db: AsyncSession, group_id: str, user_id: str) -> GroupMember:
    m = await _require_member(db, group_id, user_id)
    if m.role != "OWNER":
        raise HTTPException(status_code=403, detail="Owner only")
    return m


@router.get("", response_model=list[GroupOut])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = Group(
        name=payload.name,
        description=payload.description,
        currency=payload.currency,
        owner_id=current_user.id,
    )
    db.add(group)
    await db.flush()  # get id

    member = GroupMember(group_id=group.id, user_id=current_user.id, role="OWNER")
    db.add(member)
    await db.commit()
    await db.refresh(group)
    return group


@router.get("/{group_id}", response_model=GroupDetailOut)
async def get_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_member(db, group_id, current_user.id)
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    members_res = await db.execute(
        select(GroupMember, User)
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
    )
    rows = members_res.all()

    return GroupDetailOut(
        id=group.id,
        name=group.name,
        description=group.description,
        currency=group.currency,
        owner_id=group.owner_id,
        created_at=group.created_at,
        members=[
            MemberOut(
                id=m.id,
                user_id=m.user_id,
                display_name=u.display_name,
                username=u.username,
                group_id=m.group_id,
                role=m.role,
                joined_at=m.joined_at,
            )
            for m, u in rows
        ],
    )


@router.put("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: str,
    payload: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_owner(db, group_id, current_user.id)
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if payload.name is not None:
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_owner(db, group_id, current_user.id)
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    await db.delete(group)
    await db.commit()


@router.post("/{group_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def add_member(
    group_id: str,
    payload: AddMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_owner(db, group_id, current_user.id)

    user_res = await db.execute(select(User).where(User.username == payload.username))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check already member
    existing = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user.id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is already a member")

    member = GroupMember(group_id=group_id, user_id=user.id, role="MEMBER")
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return MemberOut(
        id=member.id,
        user_id=member.user_id,
        display_name=user.display_name,
        username=user.username,
        group_id=member.group_id,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_owner(db, group_id, current_user.id)
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Owner cannot remove themselves")

    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.delete(member)
    await db.commit()
