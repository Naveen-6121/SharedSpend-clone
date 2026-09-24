from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import AdminUserOut, AdminUserStatusUpdate, DatabaseStatusOut
from app.services.auth import get_current_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    result = await db.execute(select(User).order_by(User.created_at, User.username))
    return result.scalars().all()


@router.patch("/users/{user_id}/status", response_model=AdminUserOut)
async def set_user_status(
    user_id: str,
    payload: AdminUserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not payload.is_active and user.is_active and user.is_admin:
        active_admins = await db.scalar(
            select(func.count(User.id)).where(User.is_admin.is_(True), User.is_active.is_(True))
        )
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The last active administrator cannot be disabled",
            )

    user.is_active = payload.is_active
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/database", response_model=DatabaseStatusOut)
async def database_status(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    heads = sorted(ScriptDirectory.from_config(Config(str(config_path))).get_heads())

    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        await db.rollback()
        return DatabaseStatusOut(
            database_connected=False,
            current_revisions=[],
            head_revisions=heads,
            migrations_current=False,
        )

    try:
        result = await db.execute(
            text("SELECT version_num FROM alembic_version ORDER BY version_num")
        )
        current = sorted(result.scalars().all())
    except SQLAlchemyError:
        await db.rollback()
        current = []

    return DatabaseStatusOut(
        database_connected=True,
        current_revisions=current,
        head_revisions=heads,
        migrations_current=bool(current) and current == heads,
    )
