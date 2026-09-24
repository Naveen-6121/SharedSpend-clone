from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient

from tests.conftest import auth_headers, register_user


async def _make_group(client: AsyncClient, owner: dict, member_username: str, name: str):
    created = await client.post(
        "/api/v1/groups", json={"name": name}, headers=auth_headers(owner)
    )
    assert created.status_code == 201, created.text
    group_id = created.json()["id"]
    added = await client.post(
        f"/api/v1/groups/{group_id}/members",
        json={"username": member_username},
        headers=auth_headers(owner),
    )
    assert added.status_code == 201, added.text
    return group_id


async def _create_tx(client, tokens, payload):
    response = await client.post(
        "/api/v1/transactions", json=payload, headers=auth_headers(tokens)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_cross_screen_group_period_visibility_and_budget_consistency(client: AsyncClient):
    """Use real API routes and one DB fixture like a two-user/two-group app session."""
    owner = await register_user(client, "regression_owner")
    member = await register_user(client, "regression_member")
    outsider = await register_user(client, "regression_outsider")
    owner_id = (await client.get("/api/v1/users/me", headers=auth_headers(owner))).json()["id"]
    member_id = (await client.get("/api/v1/users/me", headers=auth_headers(member))).json()["id"]
    group_one = await _make_group(client, owner, "regression_member", "Primary home")
    group_two = await _make_group(client, owner, "regression_member", "Holiday home")
    today = date.today()

    groups = await client.get("/api/v1/groups", headers=auth_headers(member))
    assert {g["id"] for g in groups.json()} == {group_one, group_two}

    budget = await client.post(
        f"/api/v1/groups/{group_one}/budgets",
        json={"year": today.year, "month": today.month, "amount": "1000.00"},
        headers=auth_headers(owner),
    )
    assert budget.status_code == 201
    previous_year, previous_month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    previous = await client.post(
        f"/api/v1/groups/{group_one}/budgets",
        json={"year": previous_year, "month": previous_month, "amount": "800.00"},
        headers=auth_headers(owner),
    )
    assert previous.status_code == 201
    copied = await client.get(
        f"/api/v1/groups/{group_one}/budgets/{today.year}/{today.month}/previous",
        headers=auth_headers(owner),
    )
    assert float(copied.json()["amount"]) == 800.0
    missing_copy = await client.get(
        f"/api/v1/groups/{group_two}/budgets/{today.year}/{today.month}/previous",
        headers=auth_headers(owner),
    )
    assert missing_copy.status_code == 200 and missing_copy.json() is None

    category = (await client.get("/api/v1/categories", headers=auth_headers(owner))).json()[0]
    shared_one = await _create_tx(client, owner, {
        "date": str(today), "amount": "500.00", "description": "Primary groceries",
        "type": "SHARED", "group_id": group_one, "category_id": category["id"],
    })
    shared_two = await _create_tx(client, owner, {
        "date": str(today), "amount": "900.00", "description": "Holiday booking",
        "type": "SHARED", "group_id": group_two, "category_id": category["id"],
    })
    owner_private = await _create_tx(client, owner, {
        "date": str(today), "amount": "120.00", "description": "Owner private lunch",
        "type": "PERSONAL", "payer_id": owner_id, "category_id": category["id"],
    })
    member_private = await _create_tx(client, member, {
        "date": str(today), "amount": "90.00", "description": "Member private coffee",
        "type": "PERSONAL", "payer_id": member_id, "category_id": category["id"],
    })

    owner_rows = await client.get(
        "/api/v1/transactions",
        params={"group_id": group_one, "year": today.year, "month": today.month},
        headers=auth_headers(owner),
    )
    member_rows = await client.get(
        "/api/v1/transactions",
        params={"group_id": group_one, "year": today.year, "month": today.month},
        headers=auth_headers(member),
    )
    assert owner_rows.status_code == member_rows.status_code == 200
    assert {row["id"] for row in owner_rows.json()} == {shared_one["id"], owner_private["id"]}
    assert {row["id"] for row in member_rows.json()} == {shared_one["id"], member_private["id"]}
    assert owner_rows.headers["x-total-count"] == "2"

    # Search, date-from-only, month/year, pagination count, and the export share filtering.
    partial_range = await client.get(
        "/api/v1/transactions",
        params={"group_id": group_one, "date_from": str(today)},
        headers=auth_headers(owner),
    )
    assert {row["id"] for row in partial_range.json()} == {shared_one["id"], owner_private["id"]}
    search = await client.get(
        "/api/v1/transactions",
        params={"group_id": group_one, "search": "private lunch"},
        headers=auth_headers(owner),
    )
    assert [row["id"] for row in search.json()] == [owner_private["id"]]
    payer_filter = await client.get(
        "/api/v1/transactions",
        params={"group_id": group_one, "payer_id": owner_id},
        headers=auth_headers(owner),
    )
    assert {row["id"] for row in payer_filter.json()} == {owner_private["id"]}
    csv_response = await client.get(
        "/api/v1/transactions/export",
        params={"group_id": group_one, "year": today.year, "month": today.month,
                "search": "Primary"},
        headers=auth_headers(owner),
    )
    assert csv_response.status_code == 200
    assert "Primary groceries" in csv_response.text
    assert "Holiday booking" not in csv_response.text
    assert "Owner private lunch" not in csv_response.text
    payer_csv = await client.get(
        "/api/v1/transactions/export",
        params={"group_id": group_one, "payer_id": owner_id, "type": "PERSONAL"},
        headers=auth_headers(owner),
    )
    assert "Owner private lunch" in payer_csv.text
    assert "Member private coffee" not in payer_csv.text

    query = f"group_id={group_one}&year={today.year}&month={today.month}"
    owner_summary = await client.get(
        f"/api/v1/analytics/summary?{query}", headers=auth_headers(owner)
    )
    member_summary = await client.get(
        f"/api/v1/analytics/summary?{query}", headers=auth_headers(member)
    )
    assert float(owner_summary.json()["budget"]) == 1000.0
    assert float(member_summary.json()["budget"]) == 1000.0
    assert float(owner_summary.json()["shared_spent"]) == 500.0
    assert float(member_summary.json()["shared_spent"]) == 500.0
    assert float(owner_summary.json()["personal_by_member"][0]["personal_spent"]) == 120.0
    assert float(member_summary.json()["personal_by_member"][0]["personal_spent"]) == 90.0

    owner_day = await client.get(
        f"/api/v1/analytics/by-day?{query}", headers=auth_headers(owner)
    )
    owner_category = await client.get(
        f"/api/v1/analytics/by-category?{query}", headers=auth_headers(owner)
    )
    owner_month = await client.get(
        f"/api/v1/analytics/by-month?group_id={group_one}&year={today.year}",
        headers=auth_headers(owner),
    )
    owner_year = await client.get(
        f"/api/v1/analytics/by-year?group_id={group_one}&year={today.year}",
        headers=auth_headers(owner),
    )
    assert float(owner_day.json()[0]["shared"]) == 500.0
    assert float(owner_day.json()[0]["personal"]) == 120.0
    assert float(owner_category.json()[0]["amount"]) == 620.0
    assert float(owner_month.json()[0]["shared"]) == 500.0
    assert float(owner_month.json()[0]["personal"]) == 120.0
    assert float(owner_year.json()[0]["shared"]) == 500.0
    assert float(owner_year.json()[0]["personal"]) == 120.0

    forecast = await client.get(
        f"/api/v1/analytics/forecast?{query}", headers=auth_headers(owner)
    )
    assert float(forecast.json()["budget"]) == 1000.0
    assert float(forecast.json()["projected_spend"]) >= 500.0
    assert forecast.json()["on_track"] is False or forecast.json()["on_track"] is True

    member_stats = await client.get(
        f"/api/v1/analytics/members?{query}", headers=auth_headers(owner)
    )
    owner_row = next(row for row in member_stats.json() if row["user_id"] == owner_id)
    member_row = next(row for row in member_stats.json() if row["user_id"] == member_id)
    assert float(owner_row["personal_spent"]) == 120.0
    assert member_row["personal_spent"] is None

    source = await _create_tx(client, owner, {
        "date": str(today), "amount": "867.00", "description": "Primary movie",
        "type": "PERSONAL", "payer_id": owner_id, "add_to_settlement": True,
        "settlement_group_id": group_one,
        "settlement_participant_ids": [owner_id, member_id],
    })
    group_one_transfers = await client.get(
        f"/api/v1/settlements/groups/{group_one}/calculate?year={today.year}&month={today.month}",
        headers=auth_headers(member),
    )
    group_two_transfers = await client.get(
        f"/api/v1/settlements/groups/{group_two}/calculate?year={today.year}&month={today.month}",
        headers=auth_headers(member),
    )
    assert len(group_one_transfers.json()) == 1
    assert float(group_one_transfers.json()[0]["amount"]) == 433.50
    assert group_one_transfers.json()[0]["original_transaction_id"] == source["id"]
    assert group_two_transfers.json() == []
    created_record = await client.post(
        f"/api/v1/settlements/groups/{group_one}",
        json={"from_user_id": member_id, "original_transaction_id": source["id"]},
        headers=auth_headers(owner),
    )
    assert created_record.status_code == 201
    denied_source_edit = await client.put(
        f"/api/v1/transactions/{source['id']}",
        json={"amount": "900.00"}, headers=auth_headers(owner),
    )
    assert denied_source_edit.status_code == 409
    settled = await client.put(
        f"/api/v1/settlements/{created_record.json()['id']}/settle",
        headers=auth_headers(member),
    )
    assert settled.status_code == 200
    history = await client.get(
        f"/api/v1/settlements/groups/{group_one}", headers=auth_headers(member)
    )
    history_record = next(row for row in history.json() if row["id"] == created_record.json()["id"])
    assert history_record["original_transaction_id"] == source["id"]
    assert history_record["original_description"] == "Primary movie"
    assert history_record["payment_transaction_id"] == settled.json()["payment_transaction_id"]
    member_rows_after_payment = await client.get(
        "/api/v1/transactions", params={"group_id": group_one}, headers=auth_headers(member)
    )
    payment = next(row for row in member_rows_after_payment.json()
                   if row["id"] == settled.json()["payment_transaction_id"])
    assert payment["settlement_record_id"] == created_record.json()["id"]
    assert "Primary movie" in payment["description"]
    assert source["id"] not in {row["id"] for row in member_rows_after_payment.json()}

    # No analytics endpoint may disclose another group's data to a non-member.
    for endpoint in ["summary", "by-category", "by-day", "by-week", "by-month",
                     "by-year", "members", "insights", "forecast"]:
        denied = await client.get(
            f"/api/v1/analytics/{endpoint}", params={"group_id": group_one},
            headers=auth_headers(outsider),
        )
        assert denied.status_code == 403, (endpoint, denied.text)

    assert shared_two["id"] not in {row["id"] for row in owner_rows.json()}
