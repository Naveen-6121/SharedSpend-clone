from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, register_user


async def _setup_group_with_member(client: AsyncClient):
    """Returns (owner_tokens, member_tokens, group_id)."""
    t_owner = await register_user(client, "txn_owner")
    t_member = await register_user(client, "txn_member")

    group_resp = await client.post(
        "/api/v1/groups",
        json={"name": "Test Group"},
        headers=auth_headers(t_owner),
    )
    group_id = group_resp.json()["id"]

    me_resp = await client.get("/api/v1/users/me", headers=auth_headers(t_member))
    member_user_id = me_resp.json()["id"]

    await client.post(
        f"/api/v1/groups/{group_id}/members",
        json={"username": "txn_member"},
        headers=auth_headers(t_owner),
    )

    me_owner = await client.get("/api/v1/users/me", headers=auth_headers(t_owner))
    owner_user_id = me_owner.json()["id"]

    return t_owner, t_member, group_id, owner_user_id, member_user_id


async def test_create_shared_transaction(client: AsyncClient):
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "500.00",
            "description": "Groceries",
            "type": "SHARED",
            "group_id": group_id,
            "payer_id": owner_id,
        },
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "SHARED"
    assert data["group_id"] == group_id


async def test_create_shared_without_group_fails(client: AsyncClient):
    t_owner, *_ = await _setup_group_with_member(client)
    # Use fresh user to avoid duplicate username issue
    t2 = await register_user(client, "txn_nogroupuser")
    me = await client.get("/api/v1/users/me", headers=auth_headers(t2))
    uid = me.json()["id"]
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "100.00",
            "description": "Test",
            "type": "SHARED",
            "payer_id": uid,
        },
        headers=auth_headers(t2),
    )
    assert resp.status_code == 422


async def test_create_personal_with_group_fails(client: AsyncClient):
    tokens = await register_user(client, "txn_personal_fail")
    # Create a group to have a valid group_id
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
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422


async def test_create_personal_transaction(client: AsyncClient):
    tokens = await register_user(client, "txn_personal_ok")
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "75.00",
            "description": "Coffee",
            "type": "PERSONAL",
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["type"] == "PERSONAL"
    assert resp.json()["group_id"] is None


async def test_personal_not_visible_to_other_user(client: AsyncClient):
    t1 = await register_user(client, "txn_priv1")
    t2 = await register_user(client, "txn_priv2")

    # t1 creates a personal transaction
    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"date": str(date.today()), "amount": "50", "description": "Private", "type": "PERSONAL"},
        headers=auth_headers(t1),
    )
    txn_id = txn_resp.json()["id"]

    # t2 cannot see it
    resp = await client.get(f"/api/v1/transactions/{txn_id}", headers=auth_headers(t2))
    assert resp.status_code == 403


async def test_type_change_personal_to_shared_valid(client: AsyncClient):
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)

    # Create personal
    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"date": str(date.today()), "amount": "200", "description": "Test", "type": "PERSONAL"},
        headers=auth_headers(t_owner),
    )
    txn_id = txn_resp.json()["id"]

    # Change to SHARED
    resp = await client.put(
        f"/api/v1/transactions/{txn_id}",
        json={"type": "SHARED", "group_id": group_id, "payer_id": owner_id},
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "SHARED"
    assert data["group_id"] == group_id
    assert data["payer_id"] == owner_id


async def test_type_change_personal_to_shared_invalid_payer(client: AsyncClient):
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)
    t_outsider = await register_user(client, "txn_outsider")
    me_out = await client.get("/api/v1/users/me", headers=auth_headers(t_outsider))
    outsider_id = me_out.json()["id"]

    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"date": str(date.today()), "amount": "200", "description": "Test", "type": "PERSONAL"},
        headers=auth_headers(t_owner),
    )
    txn_id = txn_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/transactions/{txn_id}",
        json={"type": "SHARED", "group_id": group_id, "payer_id": outsider_id},
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 422


async def test_type_change_shared_to_personal(client: AsyncClient):
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)

    txn_resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()), "amount": "300", "description": "Shared",
            "type": "SHARED", "group_id": group_id, "payer_id": owner_id,
        },
        headers=auth_headers(t_owner),
    )
    txn_id = txn_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/transactions/{txn_id}",
        json={"type": "PERSONAL"},
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "PERSONAL"
    assert data["group_id"] is None
    assert data["payer_id"] is None


async def test_soft_delete(client: AsyncClient):
    tokens = await register_user(client, "txn_delete")
    txn_resp = await client.post(
        "/api/v1/transactions",
        json={"date": str(date.today()), "amount": "99", "description": "Del me", "type": "PERSONAL"},
        headers=auth_headers(tokens),
    )
    txn_id = txn_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/transactions/{txn_id}", headers=auth_headers(tokens))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/transactions/{txn_id}", headers=auth_headers(tokens))
    assert get_resp.status_code == 404
