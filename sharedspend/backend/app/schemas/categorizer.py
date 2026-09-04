from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CategorizeRequest(BaseModel):
    description: str


class CategorizeResponse(BaseModel):
    category_id: Optional[str]
    category_name: Optional[str]
    confidence: str  # "rule_match" | "no_match"
