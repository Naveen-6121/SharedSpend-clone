from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from httpx import AsyncClient

from app.config import Settings
from app.models.user import User
from tests.conftest import auth_headers, register_user


async def _promote(db_session, username: str) -> User:
    result = await db_session.execute(select(User).where(User.username == username))
    user = result.scalar_one()
    user.is_admin = True
    await db_session.commit()
    return user


async def test_admin_endpoints_reject_anonymous_and_non_admin(client: AsyncClient):
    anonymous = await client.get("/api/v1/admin/users")
    tokens = await register_user(client, "admin_test_regular")
    non_admin = await client.get("/api/v1/admin/users", headers=auth_headers(tokens))

    assert anonymous.status_code == 401
    assert non_admin.status_code == 403


async def test_newly_registered_users_are_not_global_admins(client: AsyncClient):
    tokens = await register_user(client, "admin_test_default_role")
    profile = await client.get("/api/v1/users/me", headers=auth_headers(tokens))

    assert profile.status_code == 200
    assert profile.json()["is_admin"] is False


async def test_admin_lists_users_without_sensitive_fields(client: AsyncClient, db_session):
    admin_tokens = await register_user(client, "admin_test_root")
    await _promote(db_session, "admin_test_root")
    await register_user(client, "admin_test_member")

    response = await client.get("/api/v1/admin/users", headers=auth_headers(admin_tokens))

    assert response.status_code == 200
    assert {user["username"] for user in response.json()} == {
        "admin_test_root", "admin_test_member"
    }
    assert all("hashed_password" not in user and "password" not in user for user in response.json())
    assert all("DATABASE_URL" not in user and "SECRET_KEY" not in user for user in response.json())


async def test_admin_can_disable_and_enable_user(client: AsyncClient, db_session):
    admin_tokens = await register_user(client, "admin_test_status_root")
    await _promote(db_session, "admin_test_status_root")
    member_tokens = await register_user(client, "admin_test_status_member")
    member = await client.get("/api/v1/users/me", headers=auth_headers(member_tokens))
    member_id = member.json()["id"]

    disabled = await client.patch(
        f"/api/v1/admin/users/{member_id}/status",
        json={"is_active": False}, headers=auth_headers(admin_tokens),
    )
    denied_login = await client.post(
        "/api/v1/auth/login", json={"username": "admin_test_status_member", "password": "test1234"}
    )
    enabled = await client.patch(
        f"/api/v1/admin/users/{member_id}/status",
        json={"is_active": True}, headers=auth_headers(admin_tokens),
    )
    allowed_login = await client.post(
        "/api/v1/auth/login", json={"username": "admin_test_status_member", "password": "test1234"}
    )

    assert disabled.status_code == 200 and disabled.json()["is_active"] is False
    assert denied_login.status_code == 403
    assert enabled.status_code == 200 and enabled.json()["is_active"] is True
    assert allowed_login.status_code == 200


async def test_admin_cannot_disable_last_active_admin(client: AsyncClient, db_session):
    tokens = await register_user(client, "admin_test_last")
    admin = await _promote(db_session, "admin_test_last")

    response = await client.patch(
        f"/api/v1/admin/users/{admin.id}/status",
        json={"is_active": False}, headers=auth_headers(tokens),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "The last active administrator cannot be disabled"


async def test_admin_database_status_is_protected_and_redacted(client: AsyncClient, db_session):
    admin_tokens = await register_user(client, "admin_test_database")
    await _promote(db_session, "admin_test_database")
    regular_tokens = await register_user(client, "admin_test_database_regular")

    regular_response = await client.get(
        "/api/v1/admin/database", headers=auth_headers(regular_tokens)
    )
    response = await client.get("/api/v1/admin/database", headers=auth_headers(admin_tokens))

    assert regular_response.status_code == 403
    assert response.status_code == 200
    assert response.json()["database_connected"] is True
    assert response.json()["head_revisions"]
    assert "DATABASE_URL" not in response.text
    assert "SECRET_KEY" not in response.text


def test_postgresql_urls_use_asyncpg_and_sqlite_remains_unchanged():
    neon_url = "postgresql://app:secret@ep-example.neon.tech/sharedspend?sslmode=require"
    assert Settings(DATABASE_URL=neon_url).async_database_url == (
        "postgresql+asyncpg://app:secret@ep-example.neon.tech/sharedspend?ssl=require"
    )
    sqlite_url = "sqlite+aiosqlite:///./sharedspend.db"
    settings = Settings(DATABASE_URL=sqlite_url)
    expected_path = str((Path(__file__).resolve().parents[1] / "sharedspend.db").resolve())
    assert settings.async_database_url.endswith(expected_path)
    assert settings.is_sqlite is True
