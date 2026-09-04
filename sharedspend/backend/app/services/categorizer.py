from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category

# (keywords, category_name)
SEED_RULES: List[Tuple[List[str], str]] = [
    (["vegetable", "sabzi", "veggies", "tomato", "onion"], "Fruits & Vegetables"),
    (["fruit", "apple", "mango", "banana"], "Fruits & Vegetables"),
    (["electricity", "eb bill", "bijli", "power bill"], "Utilities"),
    (["water bill", "jal", "municipal"], "Utilities"),
    (["uber", "ola", "rapido", "auto", "cab", "taxi"], "Transport"),
    (["petrol", "diesel", "fuel"], "Transport"),
    (["swiggy", "zomato", "restaurant", "hotel", "dine"], "Food & Dining"),
    (["grocery", "kirana", "blinkit", "zepto", "instamart"], "Groceries"),
    (["movie", "cinema", "pvr", "inox", "netflix", "hotstar"], "Entertainment"),
]

_PUNCT_RE = re.compile(r"[^\w\s]")


def _normalize(text: str) -> str:
    return _PUNCT_RE.sub(" ", text.lower()).strip()


class CategorizerService:
    def __init__(self, rules: List[Tuple[List[str], str]] = SEED_RULES):
        self._rules = rules

    def _match_name(self, description: str) -> Optional[str]:
        normalized = _normalize(description)
        for keywords, category_name in self._rules:
            for kw in keywords:
                if kw in normalized:
                    return category_name
        return None

    async def suggest(self, description: str, db: AsyncSession) -> Dict:
        name = self._match_name(description)
        if name is None:
            return {"category_id": None, "category_name": None, "confidence": "no_match"}
        result = await db.execute(
            select(Category).where(Category.name == name, Category.is_global == True)  # noqa: E712
        )
        cat = result.scalar_one_or_none()
        return {
            "category_id": cat.id if cat else None,
            "category_name": name,
            "confidence": "rule_match",
        }


categorizer = CategorizerService()
