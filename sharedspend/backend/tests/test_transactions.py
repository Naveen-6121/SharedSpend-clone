from __future__ import annotations

import csv
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
    """Opted-in personal expense needs an unambiguous group settlement context."""
    tokens, _, group_id, uid, _ = await _setup_group_with_member(client)
    resp = await client.post(
        "/api/v1/transactions",
        json={
            "date": str(date.today()),
            "amount": "120.00",
            "description": "Group dinner (personal)",
            "type": "PERSONAL",
            "payer_id": uid,
            "add_to_settlement": True,
            "settlement_group_id": group_id,
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["add_to_settlement"] is True
    assert resp.json()["settlement_group_id"] == group_id
    assert len(resp.json()["settlement_participant_ids"]) == 2


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


async def test_transaction_export_requires_authentication(client: AsyncClient):
    response = await client.get("/api/v1/transactions/export")
    assert response.status_code == 401


async def test_transaction_export_csv_headers_amount_and_date(client: AsyncClient):
    tokens = await register_user(client, "txn_export_csv")
    me = await client.get("/api/v1/users/me", headers=auth_headers(tokens))
    user_id = me.json()["id"]
    await client.post(
        "/api/v1/transactions",
        json={
            "date": "2025-02-03", "amount": "123.45", "description": "Coffee, beans",
            "type": "PERSONAL", "payer_id": user_id, "notes": "  exact note  ",
        },
        headers=auth_headers(tokens),
    )

    response = await client.get(
        "/api/v1/transactions/export", params={"year": 2025, "month": 2},
        headers=auth_headers(tokens),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="transactions.csv"' in response.headers["content-disposition"]
    rows = list(csv.DictReader(response.text.splitlines()))
    assert list(rows[0]) == [
        "id", "date", "amount", "type", "description", "category", "category_id",
        "payer", "payer_id", "recorded_by", "recorded_by_id", "group_id", "notes",
        "add_to_settlement", "created_at", "updated_at",
    ]
    assert rows[0]["date"] == "2025-02-03"
    assert rows[0]["amount"] == "123.45"
    assert rows[0]["type"] == "PERSONAL"
    assert rows[0]["description"] == "Coffee, beans"
    assert rows[0]["payer_id"] == user_id
    assert rows[0]["notes"] == "  exact note  "


async def test_transaction_export_filters_and_authorization(client: AsyncClient):
    owner, member, group_id, owner_id, member_id = await _setup_group_with_member(client)
    category_response = await client.get("/api/v1/categories", headers=auth_headers(owner))
    category_id = category_response.json()[0]["id"]
    for payload in [
        {"date": "2025-03-01", "amount": "10.00", "description": "matching",
         "type": "SHARED", "group_id": group_id, "category_id": category_id},
        {"date": "2025-04-01", "amount": "20.00", "description": "other month",
         "type": "SHARED", "group_id": group_id, "category_id": category_id},
    ]:
        created = await client.post("/api/v1/transactions", json=payload, headers=auth_headers(owner))
        assert created.status_code == 201

    filtered = await client.get(
        "/api/v1/transactions/export",
        params={"group_id": group_id, "type": "SHARED", "category_id": category_id,
                "date_from": "2025-03-01", "date_to": "2025-03-31"},
        headers=auth_headers(member),
    )
    rows = list(csv.DictReader(filtered.text.splitlines()))
    assert filtered.status_code == 200
    assert len(rows) == 1
    assert rows[0]["description"] == "matching"
    assert rows[0]["category"]

    unauthorized = await client.get(
        "/api/v1/transactions/export", params={"group_id": group_id},
        headers=auth_headers(await register_user(client, "txn_export_outsider")),
    )
    assert unauthorized.status_code == 403


async def test_transaction_export_empty_result_has_headers_only(client: AsyncClient):
    tokens = await register_user(client, "txn_export_empty")
    response = await client.get(
        "/api/v1/transactions/export", params={"year": 1990}, headers=auth_headers(tokens)
    )
    rows = list(csv.DictReader(response.text.splitlines()))
    assert response.status_code == 200
    assert rows == []
    assert response.text.startswith("id,date,amount,type,description,")


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
    original = await client.post(
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
    assert abs(float(t["amount"]) - 100.0) < 0.01
    assert t["original_transaction_id"] == original.json()["id"]
    assert t["original_description"] == "Group dinner"
    assert abs(float(t["original_amount"]) - 200.0) < 0.01


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
    """Owner-paid expense: preserve source/history and record a private debtor payment."""
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)
    original = await client.post(
        "/api/v1/transactions",
        json={"date": str(date.today()), "amount": "867.00", "description": "Movie",
              "type": "PERSONAL", "payer_id": owner_id, "add_to_settlement": True},
        headers=auth_headers(t_owner),
    )
    assert original.status_code == 201
    original_id = original.json()["id"]

    create_resp = await client.post(
        f"/api/v1/settlements/groups/{group_id}",
        json={"from_user_id": member_id, "original_transaction_id": original_id},
        headers=auth_headers(t_owner),
    )
    assert create_resp.status_code == 201
    record = create_resp.json()
    assert record["status"] == "PENDING"
    assert record["from_user_id"] == member_id
    assert record["to_user_id"] == owner_id
    assert abs(float(record["amount"]) - 433.50) < 0.001
    assert record["original_transaction_id"] == original_id
    assert record["original_description"] == "Movie"
    assert abs(float(record["original_amount"]) - 867.0) < 0.001
    record_id = record["id"]

    # The creditor's personal expense must not appear in the debtor's list.
    debtor_transactions = await client.get(
        "/api/v1/transactions", params={"group_id": group_id}, headers=auth_headers(t_member)
    )
    assert debtor_transactions.status_code == 200
    assert all(row["id"] != original_id for row in debtor_transactions.json())

    list_resp = await client.get(
        f"/api/v1/settlements/groups/{group_id}",
        headers=auth_headers(t_owner),
    )
    assert list_resp.status_code == 200
    assert any(r["id"] == record_id for r in list_resp.json())

    # Only the debtor can record payment.
    forbidden = await client.put(
        f"/api/v1/settlements/{record_id}/settle", headers=auth_headers(t_owner)
    )
    assert forbidden.status_code == 403

    settle_resp = await client.put(
        f"/api/v1/settlements/{record_id}/settle",
        headers=auth_headers(t_member),
    )
    assert settle_resp.status_code == 200
    settled = settle_resp.json()
    assert settled["status"] == "SETTLED"
    assert settled["settled_at"] is not None
    assert settled["payment_transaction_id"]

    # History retains the same direction and original expense after settlement.
    history = await client.get(
        f"/api/v1/settlements/groups/{group_id}", headers=auth_headers(t_owner)
    )
    history_item = next(row for row in history.json() if row["id"] == record_id)
    assert history_item["from_user_id"] == member_id
    assert history_item["to_user_id"] == owner_id
    assert history_item["original_transaction_id"] == original_id
    assert history_item["original_description"] == "Movie"
    assert history_item["payment_transaction_id"] == settled["payment_transaction_id"]

    debtor_transactions = await client.get(
        "/api/v1/transactions", params={"group_id": group_id}, headers=auth_headers(t_member)
    )
    payment = next(row for row in debtor_transactions.json()
                   if row["id"] == settled["payment_transaction_id"])
    assert float(payment["amount"]) == 433.50
    assert payment["settlement_record_id"] == record_id
    assert "Movie" in payment["description"]
    assert all(row["id"] != original_id for row in debtor_transactions.json())
    creditor_transactions = await client.get(
        "/api/v1/transactions", params={"group_id": group_id}, headers=auth_headers(t_owner)
    )
    assert all(row["id"] != payment["id"] for row in creditor_transactions.json())


async def test_settlement_reverse_direction(client: AsyncClient):
    """Member-paid expense reverses debtor/creditor and payment visibility correctly."""
    t_owner, t_member, group_id, owner_id, member_id = await _setup_group_with_member(client)
    original = await client.post(
        "/api/v1/transactions",
        json={"date": str(date.today()), "amount": "867.00", "description": "Hotel",
              "type": "PERSONAL", "payer_id": member_id, "add_to_settlement": True},
        headers=auth_headers(t_member),
    )
    original_id = original.json()["id"]
    calculated = await client.get(
        f"/api/v1/settlements/groups/{group_id}/calculate", headers=auth_headers(t_owner)
    )
    transfer = next(row for row in calculated.json()
                    if row["original_transaction_id"] == original_id)
    assert transfer["from_user_id"] == owner_id
    assert transfer["to_user_id"] == member_id
    assert float(transfer["amount"]) == 433.50

    created = await client.post(
        f"/api/v1/settlements/groups/{group_id}",
        json={"from_user_id": owner_id, "original_transaction_id": original_id},
        headers=auth_headers(t_member),
    )
    record_id = created.json()["id"]
    settled = await client.put(
        f"/api/v1/settlements/{record_id}/settle", headers=auth_headers(t_owner)
    )
    assert settled.status_code == 200
    assert settled.json()["from_user_id"] == owner_id
    assert settled.json()["to_user_id"] == member_id
    assert settled.json()["original_description"] == "Hotel"

    owner_transactions = await client.get(
        "/api/v1/transactions", params={"group_id": group_id}, headers=auth_headers(t_owner)
    )
    payment = next(row for row in owner_transactions.json()
                   if row["id"] == settled.json()["payment_transaction_id"])
    assert payment["settlement_record_id"] == record_id
    assert "Hotel" in payment["description"]
    assert all(row["id"] != original_id for row in owner_transactions.json())

    history = await client.get(
        f"/api/v1/settlements/groups/{group_id}", headers=auth_headers(t_member)
    )
    history_record = next(row for row in history.json() if row["id"] == record_id)
    assert history_record["from_user_id"] == owner_id
    assert history_record["to_user_id"] == member_id
    assert history_record["original_transaction_id"] == original_id
    assert history_record["payment_transaction_id"] == payment["id"]
