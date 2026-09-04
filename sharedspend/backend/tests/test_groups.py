from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, register_user


async def _create_group(client: AsyncClient, tokens: dict, name: str = "Home") -> dict:
    resp = await client.post(
        "/api/v1/groups",
        json={"name": name, "description": "Test group"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_group(client: AsyncClient):
    tokens = await register_user(client, "alice_g")
    group = await _create_group(client, tokens)
    assert group["name"] == "Home"
    assert group["currency"] == "INR"


async def test_list_groups(client: AsyncClient):
    tokens = await register_user(client, "bob_g")
    await _create_group(client, tokens, "Home")
    await _create_group(client, tokens, "Roommates")
    resp = await client.get("/api/v1/groups", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_group_detail(client: AsyncClient):
    tokens = await register_user(client, "carol_g")
    group = await _create_group(client, tokens)
    resp = await client.get(f"/api/v1/groups/{group['id']}", headers=auth_headers(tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert "members" in data
    assert len(data["members"]) == 1


async def test_non_member_cannot_see_group(client: AsyncClient):
    t1 = await register_user(client, "dave_g")
    t2 = await register_user(client, "eve_g")
    group = await _create_group(client, t1)
    resp = await client.get(f"/api/v1/groups/{group['id']}", headers=auth_headers(t2))
    assert resp.status_code == 403


async def test_add_member(client: AsyncClient):
    t_owner = await register_user(client, "frank_g")
    t_member = await register_user(client, "grace_g")
    group = await _create_group(client, t_owner)
    resp = await client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"username": "grace_g"},
        headers=auth_headers(t_owner),
    )
    assert resp.status_code == 201
    resp2 = await client.get(f"/api/v1/groups/{group['id']}", headers=auth_headers(t_owner))
    assert len(resp2.json()["members"]) == 2


async def test_non_owner_cannot_add_member(client: AsyncClient):
    t_owner = await register_user(client, "henry_g")
    t_member = await register_user(client, "iris_g")
    t_other = await register_user(client, "jack_g")
    group = await _create_group(client, t_owner)
    # Add iris as member
    await client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"username": "iris_g"},
        headers=auth_headers(t_owner),
    )
    # iris tries to add jack — should fail
    resp = await client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"username": "jack_g"},
        headers=auth_headers(t_member),
    )
    assert resp.status_code == 403


async def test_remove_member(client: AsyncClient):
    t_owner = await register_user(client, "kate_g")
    t_member = await register_user(client, "leo_g")
    group = await _create_group(client, t_owner)
    add_resp = await client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"username": "leo_g"},
        headers=auth_headers(t_owner),
    )
    assert add_resp.status_code == 201
    member_id = add_resp.json()["user_id"]
    del_resp = await client.delete(
        f"/api/v1/groups/{group['id']}/members/{member_id}",
        headers=auth_headers(t_owner),
    )
    assert del_resp.status_code == 204


async def test_owner_cannot_remove_self(client: AsyncClient):
    tokens = await register_user(client, "mike_g")
    group = await _create_group(client, tokens)
    # Get owner user_id
    me_resp = await client.get("/api/v1/users/me", headers=auth_headers(tokens))
    owner_id = me_resp.json()["id"]
    resp = await client.delete(
        f"/api/v1/groups/{group['id']}/members/{owner_id}",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 400


async def test_update_group(client: AsyncClient):
    tokens = await register_user(client, "nancy_g")
    group = await _create_group(client, tokens)
    resp = await client.put(
        f"/api/v1/groups/{group['id']}",
        json={"name": "Updated Name"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


async def test_delete_group(client: AsyncClient):
    tokens = await register_user(client, "oliver_g")
    group = await _create_group(client, tokens)
    resp = await client.delete(f"/api/v1/groups/{group['id']}", headers=auth_headers(tokens))
    assert resp.status_code == 204
