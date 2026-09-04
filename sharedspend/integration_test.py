"""
Live integration test for SharedSpend API.
Tests all 21 scenarios from the handoff spec.
"""
import json
import sys
import httpx

BASE = "http://localhost:8002/api/v1"
PASS = []
FAIL = []

def ok(label):
    PASS.append(label)
    print(f"  ✓  {label}")

def fail(label, detail=""):
    FAIL.append(label)
    print(f"  ✗  {label}: {detail}")

def section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")

def post(client, path, data=None, expected=None):
    r = client.post(f"{BASE}{path}", json=data)
    return r

def get(client, path, params=None):
    r = client.get(f"{BASE}{path}", params=params)
    return r

def put(client, path, data=None):
    r = client.put(f"{BASE}{path}", json=data)
    return r

def delete(client, path, data=None):
    if data is not None:
        r = client.request("DELETE", f"{BASE}{path}", json=data)
    else:
        r = client.delete(f"{BASE}{path}")
    return r


def run():
    client = httpx.Client(timeout=10)

    # ─── 1. REGISTER ─────────────────────────────────────────────────────────
    section("1. Register")
    r = post(client, "/auth/register", {
        "username": "itest_user1", "email": "itest1@test.com", "password": "Pass123!"
    })
    if r.status_code == 201:
        d = r.json()
        if "access_token" in d and "refresh_token" in d:
            ok("Register returns 201 with access_token + refresh_token")
            token1 = d["access_token"]
            refresh1 = d["refresh_token"]
        else:
            fail("Register response missing tokens", str(d))
            return
    elif r.status_code == 400 and "already exists" in r.text:
        # User already exists from a previous run — just log in
        print("  (user already exists, logging in instead)")
        r2 = post(client, "/auth/login", {"username": "itest_user1", "password": "Pass123!"})
        if r2.status_code == 200:
            d = r2.json()
            token1 = d["access_token"]
            refresh1 = d["refresh_token"]
            ok("Register (existing user) — login fallback OK")
        else:
            fail("Register + login fallback", r2.text)
            return
    else:
        fail("Register", f"status={r.status_code} body={r.text[:200]}")
        return

    # Register second user
    r = post(client, "/auth/register", {
        "username": "itest_user2", "email": "itest2@test.com", "password": "Pass456!"
    })
    if r.status_code in (201, 400):
        ok("Register second user (or already exists)")
        # Log in as user2
        r2 = post(client, "/auth/login", {"username": "itest_user2", "password": "Pass456!"})
        token2 = r2.json().get("access_token") if r2.status_code == 200 else None
    else:
        fail("Register user2", r.text[:100])
        token2 = None

    # ─── 2. LOGIN ─────────────────────────────────────────────────────────────
    section("2. Login")
    r = post(client, "/auth/login", {"username": "itest_user1", "password": "Pass123!"})
    if r.status_code == 200 and "access_token" in r.json():
        ok("Login returns 200 with access_token")
        token1 = r.json()["access_token"]
        refresh1 = r.json()["refresh_token"]
    else:
        fail("Login", r.text[:100])
        return

    r = post(client, "/auth/login", {"username": "itest_user1", "password": "wrongpass"})
    if r.status_code == 401:
        ok("Login with wrong password returns 401")
    else:
        fail("Login wrong password", f"expected 401, got {r.status_code}")

    # ─── 3. PERSISTENT LOGIN / GET /users/me ─────────────────────────────────
    section("3. Persistent login / GET /users/me")
    c1 = httpx.Client(timeout=10, headers={"Authorization": f"Bearer {token1}"})
    r = get(c1, "/users/me")
    if r.status_code == 200:
        me = r.json()
        if me.get("username") == "itest_user1":
            ok("GET /users/me returns correct user")
        else:
            fail("GET /users/me username mismatch", str(me))
        user1_id = me["id"]
    else:
        fail("GET /users/me", f"status={r.status_code}")
        return

    r = get(c1, "/users/me")
    if r.status_code == 200 and r.json()["id"] == user1_id:
        ok("Persistent login: same token reusable on second request")
    else:
        fail("Persistent login", r.text[:100])

    # ─── 4. TOKEN REFRESH ────────────────────────────────────────────────────
    section("4. Token refresh")
    r = post(client, "/auth/refresh", {"refresh_token": refresh1})
    if r.status_code == 200 and "access_token" in r.json():
        ok("POST /auth/refresh returns new tokens")
        new_token1 = r.json()["access_token"]
        new_refresh1 = r.json()["refresh_token"]
        c1 = httpx.Client(timeout=10, headers={"Authorization": f"Bearer {new_token1}"})
    else:
        fail("Token refresh", r.text[:100])
        new_token1 = token1

    # Test using access token as refresh token should fail
    r = post(client, "/auth/refresh", {"refresh_token": new_token1})
    if r.status_code == 401:
        ok("Using access token as refresh token returns 401")
    else:
        fail("Access token as refresh token should 401", f"got {r.status_code}")

    # ─── 5. CREATE + SELECT GROUP ─────────────────────────────────────────────
    section("5. Create / select group")
    r = post(c1, "/groups", {"name": "Integration Test Home", "description": "Test group"})
    if r.status_code == 201:
        g = r.json()
        ok(f"Create group: id={g['id'][:8]}...")
        group_id = g["id"]
        assert g["owner_id"] == user1_id, f"owner_id mismatch: {g['owner_id']} != {user1_id}"
        ok("Group owner_id matches creator user_id")
    else:
        # Group may already exist; list and pick first
        existing = get(c1, "/groups")
        if existing.status_code == 200 and existing.json():
            group_id = existing.json()[0]["id"]
            ok(f"Group already exists, using {group_id[:8]}...")
        else:
            fail("Create group", r.text[:100])
            return

    # GET /groups/{id} — detail with members
    r = get(c1, f"/groups/{group_id}")
    if r.status_code == 200:
        gd = r.json()
        if "members" in gd and isinstance(gd["members"], list):
            ok(f"GET /groups/{{id}} returns detail with members list (count={len(gd['members'])})")
        else:
            fail("GET /groups/{id} missing members field", str(gd)[:100])
    else:
        fail("GET /groups/{id}", r.text[:100])

    # ─── 6. RENAME GROUP ─────────────────────────────────────────────────────
    section("6. Rename group")
    r = put(c1, f"/groups/{group_id}", {"name": "Renamed Home", "description": "Updated"})
    if r.status_code == 200 and r.json()["name"] == "Renamed Home":
        ok("PUT /groups/{id} renames group")
    else:
        fail("Rename group", f"status={r.status_code} body={r.text[:100]}")

    # ─── 7. MEMBERS / INVITATIONS ────────────────────────────────────────────
    section("7. Members / invitations")
    r = post(c1, f"/groups/{group_id}/members", {"username": "itest_user2"})
    if r.status_code in (201, 400):
        if r.status_code == 201:
            ok("POST /groups/{id}/members adds member (201)")
        else:
            ok("Member already added (400 already member — OK for re-run)")
    else:
        fail("Add member", f"status={r.status_code} body={r.text[:100]}")

    # GET members via group detail
    r = get(c1, f"/groups/{group_id}")
    if r.status_code == 200:
        members = r.json().get("members", [])
        user_ids = [m["user_id"] for m in members]
        if user1_id in user_ids:
            ok(f"Member list contains creator user1 (members: {len(members)})")
        else:
            fail("Member list missing creator", str(user_ids))
    else:
        fail("GET /groups/{id} for members", r.text[:100])

    # Get user2 id
    c2 = httpx.Client(timeout=10, headers={"Authorization": f"Bearer {token2}"}) if token2 else None
    if c2:
        r2 = get(c2, "/users/me")
        user2_id = r2.json()["id"] if r2.status_code == 200 else None
    else:
        user2_id = None
        fail("user2 token unavailable — skipping user2 tests", "")

    # ─── 8. BUDGET CREATE / UPDATE ───────────────────────────────────────────
    section("8. Budget create/update")
    import datetime
    cy = datetime.date.today().year
    cm = datetime.date.today().month

    r = post(c1, f"/groups/{group_id}/budgets", {"year": cy, "month": cm, "amount": 20000})
    if r.status_code in (200, 201):
        b = r.json()
        ok(f"POST /groups/{{id}}/budgets creates budget: amount={b['amount']}")
        budget_id = b["id"]
    else:
        fail("Create budget", f"status={r.status_code} {r.text[:100]}")
        budget_id = None

    # Upsert (POST again same period = update)
    r = post(c1, f"/groups/{group_id}/budgets", {"year": cy, "month": cm, "amount": 25000})
    if r.status_code in (200, 201) and float(r.json().get("amount", 0)) == 25000:
        ok("POST budget upsert (same period) updates amount")
    else:
        fail("Budget upsert", f"status={r.status_code} amount={r.json().get('amount')}")

    # List budgets
    r = get(c1, f"/groups/{group_id}/budgets")
    if r.status_code == 200 and isinstance(r.json(), list):
        ok(f"GET /groups/{{id}}/budgets returns list (count={len(r.json())})")
    else:
        fail("List budgets", r.text[:100])

    # ─── 9. CATEGORIES CRUD ──────────────────────────────────────────────────
    section("9. Categories CRUD")
    r = get(c1, "/categories")
    if r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0:
        ok(f"GET /categories returns {len(r.json())} categories (global seeded)")
        global_cat_id = r.json()[0]["id"]
    else:
        fail("GET /categories", r.text[:100])
        global_cat_id = None

    r = post(c1, f"/groups/{group_id}/categories", {
        "name": "Test Category", "icon": "🧪", "keyword_hints": ["test", "sample"]
    })
    if r.status_code == 201:
        test_cat = r.json()
        ok(f"POST /groups/{{id}}/categories creates group category: {test_cat['name']}")
        test_cat_id = test_cat["id"]
    else:
        fail("Create category", f"status={r.status_code} {r.text[:100]}")
        test_cat_id = None

    if test_cat_id:
        r = put(c1, f"/categories/{test_cat_id}", {"name": "Updated Category", "icon": "🔬"})
        if r.status_code == 200 and r.json()["name"] == "Updated Category":
            ok("PUT /categories/{id} updates name/icon")
        else:
            fail("Update category", f"status={r.status_code}")

    # ─── 10. REASSIGN-BEFORE-DELETE ──────────────────────────────────────────
    section("10. Category reassign-before-delete")
    # Create a TX referencing test_cat_id first
    if test_cat_id and global_cat_id:
        r = post(c1, "/transactions", {
            "description": "Test TX for category delete",
            "amount": 100,
            "date": str(datetime.date.today()),
            "type": "PERSONAL",
            "category_id": test_cat_id,
            "group_id": None,
            "payer_id": None
        })
        if r.status_code == 201:
            ok("Created TX referencing test_cat for delete test")
            # Try delete without reassign — should 422
            r_del = delete(c1, f"/categories/{test_cat_id}")
            if r_del.status_code == 422:
                ok("DELETE /categories/{id} without reassign returns 422 when transactions reference it")
            else:
                fail("Delete without reassign should 422", f"got {r_del.status_code}")

            # Delete with reassign
            r_del = delete(c1, f"/categories/{test_cat_id}", {"reassign_to_category_id": global_cat_id})
            if r_del.status_code == 204:
                ok("DELETE /categories/{id} with reassign_to_category_id returns 204")
                test_cat_id = None
            else:
                fail("Delete with reassign", f"status={r_del.status_code} {r_del.text[:100]}")
        else:
            fail("Create TX for category delete test", r.text[:100])

    # ─── 11. CREATE SHARED TRANSACTION ───────────────────────────────────────
    section("11. Create SHARED transaction")
    r = post(c1, "/transactions", {
        "description": "Groceries shared",
        "amount": 500.00,
        "date": str(datetime.date.today()),
        "type": "SHARED",
        "group_id": group_id,
        "payer_id": user1_id,
        "category_id": global_cat_id,
        "notes": "Test shared transaction"
    })
    if r.status_code == 201:
        tx_shared = r.json()
        ok(f"Create SHARED transaction: id={tx_shared['id'][:8]}...")
        shared_id = tx_shared["id"]
        assert tx_shared["type"] == "SHARED"
        assert tx_shared["group_id"] == group_id
        assert tx_shared["payer_id"] == user1_id
        ok("SHARED TX has correct type/group_id/payer_id")
    else:
        fail("Create SHARED transaction", f"status={r.status_code} {r.text[:200]}")
        shared_id = None

    # SHARED without group_id should 422
    r = post(c1, "/transactions", {
        "description": "Bad shared", "amount": 100, "date": str(datetime.date.today()),
        "type": "SHARED", "group_id": None, "payer_id": user1_id
    })
    if r.status_code == 422:
        ok("SHARED without group_id returns 422")
    else:
        fail("SHARED without group_id should 422", f"got {r.status_code}")

    # ─── 12. CREATE PERSONAL TRANSACTION ─────────────────────────────────────
    section("12. Create PERSONAL transaction")
    r = post(c1, "/transactions", {
        "description": "Coffee personal",
        "amount": 80.00,
        "date": str(datetime.date.today()),
        "type": "PERSONAL",
        "group_id": None,
        "payer_id": None,
        "category_id": global_cat_id
    })
    if r.status_code == 201:
        tx_personal = r.json()
        ok(f"Create PERSONAL transaction: id={tx_personal['id'][:8]}...")
        personal_id = tx_personal["id"]
        assert tx_personal["type"] == "PERSONAL"
        assert tx_personal["group_id"] is None
        assert tx_personal["payer_id"] is None
        ok("PERSONAL TX has null group_id and payer_id")
    else:
        fail("Create PERSONAL transaction", f"status={r.status_code} {r.text[:200]}")
        personal_id = None

    # PERSONAL with group_id should 422
    r = post(c1, "/transactions", {
        "description": "Bad personal", "amount": 100, "date": str(datetime.date.today()),
        "type": "PERSONAL", "group_id": group_id, "payer_id": None
    })
    if r.status_code == 422:
        ok("PERSONAL with group_id returns 422")
    else:
        fail("PERSONAL with group_id should 422", f"got {r.status_code}")

    # User2 cannot see user1's personal transaction
    if c2 and personal_id:
        r = get(c2, f"/transactions/{personal_id}")
        if r.status_code == 403:
            ok("User2 cannot GET user1's personal transaction (403)")
        else:
            fail("Personal TX visibility", f"user2 got {r.status_code} instead of 403")

    # ─── 13. EDIT PERSONAL → SHARED ──────────────────────────────────────────
    section("13. Edit PERSONAL → SHARED")
    if personal_id:
        r = put(c1, f"/transactions/{personal_id}", {
            "type": "SHARED",
            "group_id": group_id,
            "payer_id": user1_id
        })
        if r.status_code == 200:
            updated = r.json()
            ok("Edit PERSONAL → SHARED returns 200")
            if updated["type"] == "SHARED" and updated["group_id"] == group_id:
                ok("Type changed to SHARED, group_id set correctly")
            else:
                fail("Type change PERSONAL→SHARED fields", str(updated))
            # Revert back to personal for next test
            r2 = put(c1, f"/transactions/{personal_id}", {"type": "PERSONAL"})
            if r2.status_code == 200 and r2.json()["type"] == "PERSONAL":
                ok("Reverted SHARED→PERSONAL for next test")
            else:
                fail("Revert SHARED→PERSONAL", r2.text[:100])
        else:
            fail("Edit PERSONAL→SHARED", f"status={r.status_code} {r.text[:200]}")
    else:
        fail("Edit PERSONAL→SHARED", "no personal_id available")

    # ─── 14. EDIT SHARED → PERSONAL ──────────────────────────────────────────
    section("14. Edit SHARED → PERSONAL")
    if shared_id:
        r = put(c1, f"/transactions/{shared_id}", {"type": "PERSONAL"})
        if r.status_code == 200:
            updated = r.json()
            ok("Edit SHARED → PERSONAL returns 200")
            if updated["type"] == "PERSONAL" and updated["group_id"] is None and updated["payer_id"] is None:
                ok("group_id and payer_id are null after SHARED→PERSONAL")
            else:
                fail("SHARED→PERSONAL fields not cleared", str(updated))
        else:
            fail("Edit SHARED→PERSONAL", f"status={r.status_code} {r.text[:200]}")

    # ─── 15. DELETE TRANSACTION ───────────────────────────────────────────────
    section("15. Delete transaction")
    # Create a disposable transaction
    r = post(c1, "/transactions", {
        "description": "To be deleted", "amount": 50, "date": str(datetime.date.today()),
        "type": "PERSONAL", "group_id": None, "payer_id": None
    })
    if r.status_code == 201:
        del_id = r.json()["id"]
        r_del = delete(c1, f"/transactions/{del_id}")
        if r_del.status_code == 204:
            ok("DELETE /transactions/{id} returns 204")
            # Verify soft-deleted (should 404 now)
            r_get = get(c1, f"/transactions/{del_id}")
            if r_get.status_code == 404:
                ok("Soft-deleted TX returns 404 on subsequent GET")
            else:
                fail("Soft-deleted TX should 404", f"got {r_get.status_code}")
        else:
            fail("DELETE transaction", f"status={r_del.status_code}")
    else:
        fail("Create TX for delete test", r.text[:100])

    # ─── 16. TRANSACTION LIST / FILTERS ───────────────────────────────────────
    section("16. Transaction list + filters")
    r = get(c1, "/transactions")
    if r.status_code == 200 and isinstance(r.json(), list):
        ok(f"GET /transactions returns list ({len(r.json())} items)")
    else:
        fail("GET /transactions", r.text[:100])

    # Filter by type=PERSONAL
    r = get(c1, "/transactions", params={"type": "PERSONAL"})
    if r.status_code == 200:
        items = r.json()
        types = set(t["type"] for t in items)
        if types <= {"PERSONAL"}:
            ok(f"Filter type=PERSONAL works ({len(items)} items, all PERSONAL)")
        else:
            fail("Filter type=PERSONAL returned SHARED items", str(types))
    else:
        fail("Filter type=PERSONAL", r.text[:100])

    # Filter by group_id
    r = get(c1, "/transactions", params={"group_id": group_id, "type": "SHARED"})
    if r.status_code == 200:
        ok(f"Filter group_id+type=SHARED works ({len(r.json())} items)")
    else:
        fail("Filter group_id + type=SHARED", r.text[:100])

    # ─── 17. ANALYTICS ENDPOINTS ─────────────────────────────────────────────
    section("17. Analytics")
    import datetime
    cy = datetime.date.today().year
    cm = datetime.date.today().month

    base_params = {"group_id": group_id, "year": cy, "month": cm}

    # Summary
    r = get(c1, "/analytics/summary", params=base_params)
    if r.status_code == 200:
        s = r.json()
        required = {"shared_spent", "personal_by_member", "paid_by_member"}
        if required <= set(s.keys()):
            ok(f"GET /analytics/summary: shared_spent={s['shared_spent']}, budget={s.get('budget')}")
        else:
            fail("Analytics summary missing fields", str(set(s.keys())))
    else:
        fail("Analytics summary", f"status={r.status_code} {r.text[:200]}")

    # by-category
    r = get(c1, "/analytics/by-category", params=base_params)
    if r.status_code == 200 and isinstance(r.json(), list):
        ok(f"GET /analytics/by-category: {len(r.json())} categories")
    else:
        fail("Analytics by-category", r.text[:100])

    # by-day
    r = get(c1, "/analytics/by-day", params=base_params)
    if r.status_code == 200 and isinstance(r.json(), list):
        ok(f"GET /analytics/by-day: {len(r.json())} days")
        if r.json():
            day = r.json()[0]
            if "date" in day and "shared" in day and "personal" in day:
                ok("by-day response shape: date/shared/personal ✓")
            else:
                fail("by-day response shape", str(day))
    else:
        fail("Analytics by-day", r.text[:100])

    # by-week
    r = get(c1, "/analytics/by-week", params={"group_id": group_id, "year": cy})
    if r.status_code == 200 and isinstance(r.json(), list):
        ok(f"GET /analytics/by-week: {len(r.json())} weeks")
    else:
        fail("Analytics by-week", r.text[:100])

    # by-month
    r = get(c1, "/analytics/by-month", params={"group_id": group_id, "year": cy})
    if r.status_code == 200 and isinstance(r.json(), list):
        ok(f"GET /analytics/by-month: {len(r.json())} months")
    else:
        fail("Analytics by-month", r.text[:100])

    # by-year
    r = get(c1, "/analytics/by-year", params={"group_id": group_id})
    if r.status_code == 200 and isinstance(r.json(), list):
        ok(f"GET /analytics/by-year: {len(r.json())} years")
    else:
        fail("Analytics by-year", r.text[:100])

    # members
    r = get(c1, "/analytics/members", params=base_params)
    if r.status_code == 200 and isinstance(r.json(), list):
        ok(f"GET /analytics/members: {len(r.json())} members")
        if r.json():
            m = r.json()[0]
            if "user_id" in m and "paid" in m:
                ok("members response shape: user_id/paid ✓")
            else:
                fail("members response shape", str(m))
    else:
        fail("Analytics members", r.text[:100])

    # insights
    r = get(c1, "/analytics/insights", params=base_params)
    if r.status_code == 200:
        ins = r.json()
        if "highest_category" in ins and "largest_transactions" in ins:
            ok("GET /analytics/insights response shape ✓")
        else:
            fail("Insights response shape", str(ins.keys()))
    else:
        fail("Analytics insights", r.text[:100])

    # forecast
    r = get(c1, "/analytics/forecast", params={"group_id": group_id, "year": cy, "month": cm})
    if r.status_code == 200:
        fc = r.json()
        if "projected_spend" in fc and "days_elapsed" in fc:
            ok("GET /analytics/forecast response shape ✓")
        else:
            fail("Forecast response shape", str(fc.keys()))
    else:
        fail("Analytics forecast", r.text[:100])

    # ─── 18. ANALYTICS FILTERS ───────────────────────────────────────────────
    section("18. Analytics date filters")
    # date filter
    r = get(c1, "/analytics/summary", params={"group_id": group_id, "date": str(datetime.date.today())})
    if r.status_code == 200:
        ok("Analytics summary with date= filter works")
    else:
        fail("Analytics summary with date= filter", r.text[:100])

    # custom range
    d_from = str(datetime.date.today().replace(day=1))
    d_to = str(datetime.date.today())
    r = get(c1, "/analytics/summary", params={"group_id": group_id, "date_from": d_from, "date_to": d_to})
    if r.status_code == 200:
        ok("Analytics summary with date_from/date_to filter works")
    else:
        fail("Analytics summary with custom range", r.text[:100])

    # ─── 19. PROFILE UPDATE ──────────────────────────────────────────────────
    section("19. Profile update")
    r = put(c1, "/users/me", {"display_name": "Integration Test User"})
    if r.status_code == 200 and r.json()["display_name"] == "Integration Test User":
        ok("PUT /users/me updates display_name")
    else:
        fail("Profile update", f"status={r.status_code} body={r.text[:100]}")

    # ─── 20. PASSWORD CHANGE ─────────────────────────────────────────────────
    section("20. Password change")
    r = put(c1, "/users/me/password", {"old_password": "Pass123!", "new_password": "NewPass789!"})
    if r.status_code == 200:
        ok("PUT /users/me/password returns 200")
        # Verify new password works
        r2 = post(client, "/auth/login", {"username": "itest_user1", "password": "NewPass789!"})
        if r2.status_code == 200:
            ok("New password accepted at login")
            # Reset back
            new_c1 = httpx.Client(timeout=10, headers={"Authorization": f"Bearer {r2.json()['access_token']}"})
            put(new_c1, "/users/me/password", {"old_password": "NewPass789!", "new_password": "Pass123!"})
        else:
            fail("New password not accepted at login", r2.text[:100])
    else:
        fail("Password change", f"status={r.status_code} {r.text[:100]}")

    # ─── 21. LOGOUT ──────────────────────────────────────────────────────────
    section("21. Logout")
    r = post(c1, "/auth/logout")
    if r.status_code == 200:
        ok("POST /auth/logout returns 200")
    else:
        fail("Logout", f"status={r.status_code}")

    # ─── CATEGORIZER ─────────────────────────────────────────────────────────
    section("Bonus: Categorizer")
    r = post(c1, "/categorize", {"description": "vegetables from market"})
    if r.status_code == 200:
        res = r.json()
        if "category_id" in res and "category_name" in res and "confidence" in res:
            ok(f"POST /categorize: category={res['category_name']}, confidence={res['confidence']}")
        else:
            fail("Categorizer response shape", str(res))
    else:
        fail("POST /categorize", r.text[:100])

    r = post(c1, "/categorize", {"description": "xyzzy random unknown item"})
    if r.status_code == 200 and r.json()["category_id"] is None:
        ok("POST /categorize no match returns null category_id")
    else:
        fail("Categorizer no match", f"status={r.status_code}")

    # ─── SUMMARY ─────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  RESULTS: {len(PASS)} passed, {len(FAIL)} failed")
    print(f"{'='*60}")
    if FAIL:
        print("\n  FAILED:")
        for f in FAIL:
            print(f"    ✗ {f}")
    return len(FAIL) == 0


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
