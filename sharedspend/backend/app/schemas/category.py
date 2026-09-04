from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    icon: str | None = None
    keyword_hints: List[str] | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    keyword_hints: List[str] | None = None


class CategoryDeleteRequest(BaseModel):
    reassign_to_category_id: str | None = None


class CategoryOut(BaseModel):
    id: str
    name: str
    icon: str | None
    is_global: bool
    group_id: str | None
    keyword_hints: List[str] | None
    created_at: datetime

    model_config = {"from_attributes": True}
