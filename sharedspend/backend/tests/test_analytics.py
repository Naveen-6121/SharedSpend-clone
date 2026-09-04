from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, register_user


async def _create_shared_txn(client, tokens, group_id, amount, description="Test"):
    """Create a SHARED transaction — no payer_id required."""
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": str(amount),
            "description": description,
            "type": "SHARED",
            "group_id": group_id,
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_personal_txn(client, tokens, payer_id, amount, description="Personal"):
    """Create a PERSONAL transaction — payer_id required."""
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": str(amount),
            "description": description,
            "type": "PERSONAL",
            "payer_id": payer_id,
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

    await _create_shared_txn(client, t_owner, group_id, 1000)
    await _create_shared_txn(client, t_owner, group_id, 500)

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

    txn = await _create_shared_txn(client, t_owner, group_id, 800)

    # Verify shared_spent = 800
    resp1 = await client.get(
        f"/api/v1/analytics/summary?group_id={group_id}&year={today.year}&month={today.month}",
        headers=auth_headers(t_owner),
    )
    assert float(resp1.json()["shared_spent"]) == 800.0

    # Change to PERSONAL — must supply payer_id
    await client.put(
        f"/api/v1/transactions/{txn['id']}",
        json={"type": "PERSONAL", "payer_id": owner_id},
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
            "type": "SHARED", "group_id": group_id,
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


async def test_dashboard_returns_budget_and_shared_spent(client: AsyncClient):
    """Dashboard (analytics/summary) returns correct budget and shared_spent."""
    t_owner, t_member, group_id, owner_id = await _setup(client)
    today = date.today()

    # Create two shared transactions
    await _create_shared_txn(client, t_owner, group_id, 2000, "Rent split")
    await _create_shared_txn(client, t_owner, group_id, 3500, "Utilities")

    resp = await client.get(
        f"/api/v1/analytics/summary?group_id={group_id}&year={today.year}&month={today.month}",
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["shared_spent"]) == 5500.0
    assert float(data["budget"]) == 10000.0
    assert float(data["remaining"]) == 4500.0
    assert data["personal_by_member"] is not None
    assert data["paid_by_member"] is not None


async def test_dashboard_no_transactions_returns_zero(client: AsyncClient):
    """Dashboard shows zero shared spent when no transactions exist."""
    t_owner, t_member, group_id, owner_id = await _setup(client)
    today = date.today()

    resp = await client.get(
        f"/api/v1/analytics/summary?group_id={group_id}&year={today.year}&month={today.month}",
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["shared_spent"]) == 0.0
    assert float(data["budget"]) == 10000.0


async def test_group_members_returned_correctly(client: AsyncClient):
    """Group members endpoint returns all members with display_name and username."""
    t_owner, t_member, group_id, owner_id = await _setup(client)

    resp = await client.get(f"/api/v1/groups/{group_id}", headers=auth_headers(t_owner))
    assert resp.status_code == 200
    data = resp.json()
    members = data["members"]
    assert len(members) == 2  # owner + member
    user_ids = [m["user_id"] for m in members]
    assert owner_id in user_ids
    # Each member has required fields
    for m in members:
        assert "user_id" in m
        assert "display_name" in m
        assert "role" in m


async def test_settlement_calculate_returns_array(client: AsyncClient):
    """Settlement calculate endpoint always returns a list (array), never an object."""
    t_owner, t_member, group_id, owner_id = await _setup(client)

    resp = await client.get(
        f"/api/v1/settlements/groups/{group_id}/calculate",
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list), f"Expected list, got {type(data)}"


async def test_settlement_list_returns_array(client: AsyncClient):
    """Settlement list endpoint always returns a list (array), never an object."""
    t_owner, t_member, group_id, owner_id = await _setup(client)

    resp = await client.get(
        f"/api/v1/settlements/groups/{group_id}",
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list), f"Expected list, got {type(data)}"


async def test_settlement_calculate_with_personal_settlement_txn(client: AsyncClient):
    """Settlement calculation uses PERSONAL + add_to_settlement transactions only."""
    t_owner, t_member, group_id, owner_id = await _setup(client)
    today = date.today()

    me_member = await client.get("/api/v1/users/me", headers=auth_headers(t_member))
    member_id = me_member.json()["id"]

    # Owner pays 300 for a dinner — marked for settlement
    await client.post(
        "/api/v1/transactions",
        json={
            "date": str(today),
            "amount": "300.00",
            "description": "Team dinner",
            "type": "PERSONAL",
            "payer_id": owner_id,
            "add_to_settlement": True,
        },
        headers=auth_headers(t_owner),
    )

    resp = await client.get(
        f"/api/v1/settlements/groups/{group_id}/calculate"
        f"?year={today.year}&month={today.month}",
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    transfers = resp.json()
    assert isinstance(transfers, list)
    assert len(transfers) == 1
    t = transfers[0]
    assert t["from_user_id"] == member_id
    assert t["to_user_id"] == owner_id
    assert abs(float(t["amount"]) - 150.0) < 0.01


async def test_budget_accepts_standard_monetary_values(client: AsyncClient):
    """Budget endpoint accepts 15000, 15000.50, 1, 0.01 etc."""
    t_owner, t_member, group_id, owner_id = await _setup(client)
    today = date.today()

    for amount in [15000, 15000.50, 14999, 1, 0.01]:
        resp = await client.post(
            f"/api/v1/groups/{group_id}/budgets",
            json={"year": today.year, "month": today.month, "amount": str(amount)},
            headers=auth_headers(t_owner),
        )
        assert resp.status_code in (200, 201), f"Failed for amount={amount}: {resp.text}"
        assert float(resp.json()["amount"]) == float(amount)
