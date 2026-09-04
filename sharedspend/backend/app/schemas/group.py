from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class GroupCreate(BaseModel):
    name: str
    description: str | None = None
    currency: str = "INR"


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class MemberOut(BaseModel):
    id: str
    user_id: str
    display_name: str | None = None
    username: str | None = None
    group_id: str
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class GroupOut(BaseModel):
    id: str
    name: str
    description: str | None
    currency: str
    owner_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupDetailOut(GroupOut):
    members: list[MemberOut] = []


class AddMemberRequest(BaseModel):
    username: str
