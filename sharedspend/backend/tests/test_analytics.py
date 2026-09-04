from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, register_user


async def _create_shared_txn(client, tokens, group_id, payer_id, amount, description="Test"):
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": str(amount),
            "description": description,
            "type": "SHARED",
            "group_id": group_id,
            "payer_id": payer_id,
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_personal_txn(client, tokens, amount, description="Personal"):
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": str(amount),
            "description": description,
            "type": "PERSONAL",
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    return resp.json()


async def _setup(client):
    t_owner = await register_user(client, "anal_owner")
    t_member = await register_user(client, "anal_member")

    g_resp = await client.post("/api/v1/groups", json={"name": "Anal Group"}, headers=auth_headers(t_owner))
    group_id = g_resp.json()["id"]
    await client.post(f"/api/v1/groups/{group_id}/members", json={"username": "anal_member"}, headers=auth_headers(t_owner))

    me_owner = await client.get("/api/v1/users/me", headers=auth_headers(t_owner))
    owner_id = me_owner.json()["id"]

    # Set a budget
    today = date.today()
    await client.post(
        f"/api/v1/groups/{group_id}/budgets",
        json={"year": today.year, "month": today.month, "amount": "10000.00"},
        headers=auth_headers(t_owner),
    )

    return t_owner, t_member, group_id, owner_id


async def test_summary_totals(client: AsyncClient):
    t_owner, t_member, group_id, owner_id = await _setup(client)
    today = date.today()

    await _create_shared_txn(client, t_owner, group_id, owner_id, 1000)
    await _create_shared_txn(client, t_owner, group_id, owner_id, 500)

    resp = await client.get(
        f"/api/v1/analytics/summary?group_id={group_id}&year={today.year}&month={today.month}",
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["shared_spent"]) == 1500.0
    assert float(data["budget"]) == 10000.0
    assert float(data["remaining"]) == 8500.0


async def test_summary_null_budget_when_not_set(client: AsyncClient):
    tokens = await register_user(client, "anal_nobudget")
    g_resp = await client.post("/api/v1/groups", json={"name": "NoBudget"}, headers=auth_headers(tokens))
    group_id = g_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/analytics/summary?group_id={group_id}&year=2025&month=1",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["budget"] is None
    assert resp.json()["remaining"] is None


async def test_summary_shifts_after_type_change(client: AsyncClient):
    t_owner, t_member, group_id, owner_id = await _setup(client)
    today = date.today()

    txn = await _create_shared_txn(client, t_owner, group_id, owner_id, 800)

    # Verify shared_spent = 800
    resp1 = await client.get(
        f"/api/v1/analytics/summary?group_id={group_id}&year={today.year}&month={today.month}",
        headers=auth_headers(t_owner),
    )
    assert float(resp1.json()["shared_spent"]) == 800.0

    # Change to PERSONAL
    await client.put(
        f"/api/v1/transactions/{txn['id']}",
        json={"type": "PERSONAL"},
        headers=auth_headers(t_owner),
    )

    # shared_spent should now be 0
    resp2 = await client.get(
        f"/api/v1/analytics/summary?group_id={group_id}&year={today.year}&month={today.month}",
        headers=auth_headers(t_owner),
    )
    assert float(resp2.json()["shared_spent"]) == 0.0


async def test_by_category(client: AsyncClient):
    t_owner, t_member, group_id, owner_id = await _setup(client)
    # Create a category
    cat_resp = await client.post(
        f"/api/v1/groups/{group_id}/categories",
        json={"name": "Food"},
        headers=auth_headers(t_owner),
    )
    cat_id = cat_resp.json()["id"]

    await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()), "amount": "200", "description": "Pizza",
            "type": "SHARED", "group_id": group_id, "payer_id": owner_id,
            "category_id": cat_id,
        },
        headers=auth_headers(t_owner),
    )

    resp = await client.get(
        f"/api/v1/analytics/by-category?group_id={group_id}",
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    cats = resp.json()
    food_entry = next((c for c in cats if c["category_id"] == cat_id), None)
    assert food_entry is not None
    assert float(food_entry["amount"]) == 200.0
