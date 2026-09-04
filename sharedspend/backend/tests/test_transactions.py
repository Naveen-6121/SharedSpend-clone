from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, register_user


async def _setup_group_with_member(client: AsyncClient):
    """Returns (owner_tokens, member_tokens, group_id, owner_id, member_id)."""
    t_owner = await register_user(client, "txn_owner")
    t_member = await register_user(client, "txn_member")

    group_resp = await client.post(
        "/api/v1/groups",
        json={"name": "Test Group"},
        headers=auth_headers(t_owner),
    )
    group_id = group_resp.json()["id"]

    me_member = await client.get("/api/v1/users/me", headers=auth_headers(t_member))
    member_user_id = me_member.json()["id"]

    await client.post(
        f"/api/v1/groups/{group_id}/members",
        json={"username": "txn_member"},
        headers=auth_headers(t_owner),
    )

    me_owner = await client.get("/api/v1/users/me", headers=auth_headers(t_owner))
    owner_user_id = me_owner.json()["id"]

    return t_owner, t_member, group_id, owner_user_id, member_user_id


# ─── SHARED transaction tests ────────────────────────────────────────────────

async def test_create_shared_transaction(client: AsyncClient):
    """SHARED requires group_id and NO payer_id."""
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "500.00",
            "description": "Groceries",
            "type": "SHARED",
            "group_id": group_id,
            # no payer_id — correct for SHARED
        },
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "SHARED"
    assert data["group_id"] == group_id
    assert data["payer_id"] is None


async def test_create_shared_with_payer_fails(client: AsyncClient):
    """SHARED must NOT have a payer_id."""
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "500.00",
            "description": "Groceries",
            "type": "SHARED",
            "group_id": group_id,
            "payer_id": owner_id,  # MUST fail
        },
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 422


async def test_create_shared_without_group_fails(client: AsyncClient):
    """SHARED requires group_id."""
    t2 = await register_user(client, "txn_nogroupuser")
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "100.00",
            "description": "Test",
            "type": "SHARED",
        },
        headers=auth_headers(t2),
    )
    assert resp.status_code == 422


async def test_create_shared_empty_string_payer_treated_as_none(client: AsyncClient):
    """Frontend may send payer_id='' — backend must coerce to None and accept SHARED."""
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "200.00",
            "description": "Dinner",
            "type": "SHARED",
            "group_id": group_id,
            "payer_id": "",  # empty string → None → valid for SHARED
        },
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 201
    assert resp.json()["payer_id"] is None


# ─── PERSONAL transaction tests ──────────────────────────────────────────────

async def test_create_personal_transaction(client: AsyncClient):
    """PERSONAL requires payer_id, no group_id."""
    tokens = await register_user(client, "txn_personal_ok")
    me = await client.get("/api/v1/users/me", headers=auth_headers(tokens))
    uid = me.json()["id"]
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "75.00",
            "description": "Coffee",
            "type": "PERSONAL",
            "payer_id": uid,
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "PERSONAL"
    assert data["group_id"] is None
    assert data["payer_id"] == uid


async def test_create_personal_without_payer_fails(client: AsyncClient):
    """PERSONAL without payer_id must fail."""
    tokens = await register_user(client, "txn_personal_nopayer")
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "50.00",
            "description": "Solo spend",
            "type": "PERSONAL",
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422


async def test_create_personal_with_group_fails(client: AsyncClient):
    """PERSONAL must not have a group_id."""
    tokens = await register_user(client, "txn_personal_fail")
    me = await client.get("/api/v1/users/me", headers=auth_headers(tokens))
    uid = me.json()["id"]
    g = await client.post("/api/v1/groups", json={"name": "G"}, headers=auth_headers(tokens))
    group_id = g.json()["id"]
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "50.00",
            "description": "Personal with group",
            "type": "PERSONAL",
            "group_id": group_id,
            "payer_id": uid,
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422


async def test_create_personal_with_add_to_settlement(client: AsyncClient):
    """PERSONAL with add_to_settlement=True should be created successfully."""
    tokens = await register_user(client, "txn_settlement_ok")
    me = await client.get("/api/v1/users/me", headers=auth_headers(tokens))
    uid = me.json()["id"]
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "120.00",
            "description": "Group dinner (personal)",
            "type": "PERSONAL",
            "payer_id": uid,
            "add_to_settlement": True,
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["add_to_settlement"] is True


async def test_personal_not_visible_to_other_user(client: AsyncClient):
    t1 = await register_user(client, "txn_priv1")
    t2 = await register_user(client, "txn_priv2")

    me1 = await client.get("/api/v1/users/me", headers=auth_headers(t1))
    uid1 = me1.json()["id"]

    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"date": str(date.today()), "amount": "50", "description": "Private",
              "type": "PERSONAL", "payer_id": uid1},
        headers=auth_headers(t1),
    )
    txn_id = txn_resp.json()["id"]

    resp = await client.get(f"/api/v1/transactions/{txn_id}", headers=auth_headers(t2))
    assert resp.status_code == 403


# ─── Type-change tests ────────────────────────────────────────────────────────

async def test_type_change_personal_to_shared_valid(client: AsyncClient):
    """Change PERSONAL → SHARED (must supply group_id, no payer_id)."""
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)

    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"date": str(date.today()), "amount": "200", "description": "Test",
              "type": "PERSONAL", "payer_id": owner_id},
        headers=auth_headers(t_owner),
    )
    txn_id = txn_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/transactions/{txn_id}",
        json={"type": "SHARED", "group_id": group_id},
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "SHARED"
    assert data["group_id"] == group_id
    assert data["payer_id"] is None


async def test_type_change_shared_to_personal(client: AsyncClient):
    """Change SHARED → PERSONAL (must supply payer_id, group_id cleared)."""
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)

    txn_resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()), "amount": "300", "description": "Shared",
            "type": "SHARED", "group_id": group_id,
        },
        headers=auth_headers(t_owner),
    )
    txn_id = txn_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/transactions/{txn_id}",
        json={"type": "PERSONAL", "payer_id": owner_id},
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "PERSONAL"
    assert data["group_id"] is None
    assert data["payer_id"] == owner_id


async def test_soft_delete(client: AsyncClient):
    tokens = await register_user(client, "txn_delete")
    me = await client.get("/api/v1/users/me", headers=auth_headers(tokens))
    uid = me.json()["id"]
    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"date": str(date.today()), "amount": "99", "description": "Del me",
              "type": "PERSONAL", "payer_id": uid},
        headers=auth_headers(tokens),
    )
    txn_id = txn_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/transactions/{txn_id}", headers=auth_headers(tokens))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/transactions/{txn_id}", headers=auth_headers(tokens))
    assert get_resp.status_code == 404


# ─── Settlement endpoint tests ────────────────────────────────────────────────

async def test_settlement_calculate_empty(client: AsyncClient):
    """No settlement transactions → empty list."""
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)
    resp = await client.get(
        f"/api/v1/settlements/groups/{group_id}/calculate",
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_settlement_calculate_with_transactions(client: AsyncClient):
    """One member pays for both → other member owes half."""
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)

    # Owner pays 200 for a dinner that both share via settlement
    await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "200.00",
            "description": "Group dinner",
            "type": "PERSONAL",
            "payer_id": owner_id,
            "add_to_settlement": True,
        },
        headers=auth_headers(t_owner),
    )

    resp = await client.get(
        f"/api/v1/settlements/groups/{group_id}/calculate",
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    transfers = resp.json()
    assert len(transfers) == 1
    t = transfers[0]
    assert t["from_user_id"] == member_id
    assert t["to_user_id"] == owner_id
    assert abs(t["amount"] - 100.0) < 0.01


async def test_settlement_not_in_settlement_ignored(client: AsyncClient):
    """Transactions with add_to_settlement=False are excluded from calculation."""
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)

    await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "500.00",
            "description": "Personal only",
            "type": "PERSONAL",
            "payer_id": owner_id,
            "add_to_settlement": False,
        },
        headers=auth_headers(t_owner),
    )

    resp = await client.get(
        f"/api/v1/settlements/groups/{group_id}/calculate",
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_settlement_record_lifecycle(client: AsyncClient):
    """Create, list, and mark-settled a settlement record."""
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)

    # Create record
    create_resp = await client.post(
        f"/api/v1/settlements/groups/{group_id}",
        params={"from_user_id": member_id, "to_user_id": owner_id, "amount": "100.00"},
        headers=auth_headers(t_owner),
    )
    assert create_resp.status_code == 201
    record = create_resp.json()
    assert record["status"] == "PENDING"
    record_id = record["id"]

    # List records
    list_resp = await client.get(
        f"/api/v1/settlements/groups/{group_id}",
        headers=auth_headers(t_owner),
    )
    assert list_resp.status_code == 200
    assert any(r["id"] == record_id for r in list_resp.json())

    # Mark as settled
    settle_resp = await client.put(
        f"/api/v1/settlements/{record_id}/settle",
        headers=auth_headers(t_owner),
    )
    assert settle_resp.status_code == 200
    assert settle_resp.json()["status"] == "SETTLED"
    assert settle_resp.json()["settled_at"] is not None
