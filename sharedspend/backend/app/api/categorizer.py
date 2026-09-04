from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.categorizer import CategorizeRequest, CategorizeResponse
from app.services.auth import get_current_user
from app.services.categorizer import categorizer

router = APIRouter(tags=["categorizer"])


@router.post("/categorize", response_model=CategorizeResponse)
async def categorize(
    payload: CategorizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await categorizer.suggest(payload.description, db)
    return CategorizeResponse(**result)
