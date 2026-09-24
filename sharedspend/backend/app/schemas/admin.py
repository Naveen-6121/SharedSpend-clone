from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AdminUserOut(BaseModel):
    id: str
    username: str
    display_name: str | None
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserStatusUpdate(BaseModel):
    is_active: bool


class DatabaseStatusOut(BaseModel):
    database_connected: bool
    current_revisions: list[str]
    head_revisions: list[str]
    migrations_current: bool
