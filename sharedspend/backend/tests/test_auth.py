from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, register_user


async def test_register_success(client: AsyncClient):
    tokens = await register_user(client, "alice")
    assert "access_token" in tokens
    assert "refresh_token" in tokens


async def test_register_duplicate_username(client: AsyncClient):
    await register_user(client, "bob")
    resp = await client.post("/api/v1/auth/register", json={
        "username": "bob",
        "email": "bob2@test.com",
        "password": "pass1234",
    })
    assert resp.status_code == 400


async def test_register_duplicate_email(client: AsyncClient):
    await register_user(client, "carol", email="carol@test.com")
    resp = await client.post("/api/v1/auth/register", json={
        "username": "carol2",
        "email": "carol@test.com",
        "password": "pass1234",
    })
    assert resp.status_code == 400


async def test_login_success(client: AsyncClient):
    await register_user(client, "dave")
    resp = await client.post("/api/v1/auth/login", json={"username": "dave", "password": "test1234"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


async def test_login_wrong_password(client: AsyncClient):
    await register_user(client, "eve")
    resp = await client.post("/api/v1/auth/login", json={"username": "eve", "password": "wrongpass"})
    assert resp.status_code == 401


async def test_login_unknown_user(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401


async def test_refresh_token(client: AsyncClient):
    tokens = await register_user(client, "frank")
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_refresh_with_access_token_fails(client: AsyncClient):
    tokens = await register_user(client, "grace")
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


async def test_logout(client: AsyncClient):
    tokens = await register_user(client, "henry")
    resp = await client.post("/api/v1/auth/logout", headers=auth_headers(tokens))
    assert resp.status_code == 200


async def test_get_me(client: AsyncClient):
    tokens = await register_user(client, "iris")
    resp = await client.get("/api/v1/users/me", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["username"] == "iris"
