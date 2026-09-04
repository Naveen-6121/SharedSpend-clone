from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.categorizer import CategorizerService, SEED_RULES


def test_known_match_vegetables():
    svc = CategorizerService()
    assert svc._match_name("vegetables") == "Fruits & Vegetables"


def test_known_match_sabzi():
    svc = CategorizerService()
    assert svc._match_name("sabzi wali") == "Fruits & Vegetables"


def test_known_match_uber():
    svc = CategorizerService()
    assert svc._match_name("Uber ride") == "Transport"


def test_known_match_swiggy():
    svc = CategorizerService()
    assert svc._match_name("swiggy order") == "Food & Dining"


def test_known_match_grocery():
    svc = CategorizerService()
    assert svc._match_name("kirana store") == "Groceries"


def test_known_match_electricity():
    svc = CategorizerService()
    assert svc._match_name("electricity bill") == "Utilities"


def test_known_match_movie():
    svc = CategorizerService()
    assert svc._match_name("PVR movies") == "Entertainment"


def test_no_match():
    svc = CategorizerService()
    assert svc._match_name("random xyz expense") is None


def test_case_insensitive():
    svc = CategorizerService()
    assert svc._match_name("SWIGGY dinner") == "Food & Dining"


async def test_suggest_returns_category_id(client: AsyncClient):
    from tests.conftest import auth_headers, register_user
    tokens = await register_user(client, "cat_user")
    resp = await client.post(
        "/api/v1/categorize",
        json={"description": "vegetables"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence"] == "rule_match"
    assert data["category_name"] == "Fruits & Vegetables"
    assert data["category_id"] is not None


async def test_suggest_no_match(client: AsyncClient):
    from tests.conftest import auth_headers, register_user
    tokens = await register_user(client, "cat_nomatch_user")
    resp = await client.post(
        "/api/v1/categorize",
        json={"description": "zzz unknown xyz"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence"] == "no_match"
    assert data["category_id"] is None
