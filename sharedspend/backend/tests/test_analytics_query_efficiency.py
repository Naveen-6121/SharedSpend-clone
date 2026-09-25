from __future__ import annotations

from datetime import date

from sqlalchemy import event

from tests.conftest import auth_headers, register_user


async def test_member_and_insight_routes_have_bounded_round_trips(client, db_engine):
    """Guard against per-member and per-metric SQL round-trips on remote DBs."""
    owner = await register_user(client, "perf_owner")
    member = await register_user(client, "perf_member")
    group_response = await client.post(
        "/api/v1/groups", json={"name": "Two member test"}, headers=auth_headers(owner)
    )
    assert group_response.status_code == 201
    group_id = group_response.json()["id"]
    added = await client.post(
        f"/api/v1/groups/{group_id}/members",
        json={"username": "perf_member"}, headers=auth_headers(owner),
    )
    assert added.status_code == 201
    owner_id = (await client.get("/api/v1/users/me", headers=auth_headers(owner))).json()["id"]
    category = (await client.get("/api/v1/categories", headers=auth_headers(owner))).json()[0]
    today = date.today()
    for token, amount, description in (
        (owner, "250.00", "Owner shared expense"),
        (member, "125.00", "Member shared expense"),
    ):
        created = await client.post(
            "/api/v1/transactions",
            json={
                "date": str(today), "amount": amount, "description": description,
                "type": "SHARED", "group_id": group_id, "category_id": category["id"],
            },
            headers=auth_headers(token),
        )
        assert created.status_code == 201

    statements: list[str] = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(db_engine.sync_engine, "before_cursor_execute", record_statement)
    try:
        query = {"group_id": group_id, "year": today.year, "month": today.month}
        members = await client.get("/api/v1/analytics/members", params=query,
                                   headers=auth_headers(owner))
        assert members.status_code == 200, members.text
        member_rows = members.json()
        assert len(member_rows) == 2
        assert all(row["personal_spent"] is None for row in member_rows
                   if row["user_id"] != owner_id)
        # Authentication + membership authorization + one joined/aggregated query,
        # independent of the number of group members.
        assert len(statements) <= 3

        statements.clear()
        insights = await client.get("/api/v1/analytics/insights", params=query,
                                    headers=auth_headers(owner))
        assert insights.status_code == 200, insights.text
        assert float(insights.json()["highest_category"]["amount"]) == 375.0
        # Authentication, membership authorization, scalar summary, top-five list.
        assert len(statements) <= 4

        statements.clear()
        forecast = await client.get("/api/v1/analytics/forecast", params=query,
                                   headers=auth_headers(owner))
        assert forecast.status_code == 200, forecast.text
        assert forecast.json()["budget"] is None
        # Authentication, membership authorization, then shared spend + budget.
        assert len(statements) <= 3
    finally:
        event.remove(db_engine.sync_engine, "before_cursor_execute", record_statement)
