"""
Phase 9.5 — Admin Transactions integration tests.
Tests: expanded from 5 to 13 test functions covering milestone spec.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

from tests.integration.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


@pytest.fixture(scope="session")
def admin_token():
    """Log in as admin and return JWT token."""
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    token = data.get("session", {}).get("access_token") or data.get("access_token")
    assert token, "Token not found"
    return token


# ── List transactions ──────────────────────────────────────────────────────

def test_list_transactions_returns_all_fields(admin_token):
    response = client.get(
        "/api/v1/admin/transactions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]["transactions"]
    if data:
        txn = data[0]
        expected_fields = [
            "id", "payment_id", "user_id", "username", "full_name", "email",
            "profile_image_url", "package_name", "started_on", "ends_on",
            "price", "subscription_type", "status", "created_at",
        ]
        for field in expected_fields:
            assert field in txn, f"Missing field: {field}"


def test_list_transactions_pagination(admin_token):
    response = client.get(
        "/api/v1/admin/transactions?page=1&limit=5",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "transactions" in data
    assert "total" in data
    assert "page" in data
    assert "limit" in data
    assert data["page"] == 1
    assert data["limit"] == 5
    assert len(data["transactions"]) <= 5


def test_list_transactions_ordered_by_date(admin_token):
    response = client.get(
        "/api/v1/admin/transactions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    transactions = response.json()["data"]["transactions"]
    dates = [t["created_at"] for t in transactions if t.get("created_at")]
    if dates:
        assert dates == sorted(dates, reverse=True), "Transactions not ordered by created_at DESC"


# ── Filters ────────────────────────────────────────────────────────────────

def test_list_transactions_filter_by_status(admin_token):
    response = client.get(
        "/api/v1/admin/transactions?status=completed",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    transactions = response.json()["data"]["transactions"]
    for txn in transactions:
        assert txn["status"] == "completed"


def test_list_transactions_filter_by_date_range(admin_token):
    response = client.get(
        "/api/v1/admin/transactions?date_from=2020-01-01&date_to=2099-12-31",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    transactions = response.json()["data"]["transactions"]
    for txn in transactions:
        created_date = txn["created_at"][:10]
        assert "2020-01-01" <= created_date <= "2099-12-31"


def test_list_transactions_filter_by_user_id(admin_token):
    # First get any existing user_id from the full list
    list_resp = client.get(
        "/api/v1/admin/transactions?limit=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    existing = list_resp.json()["data"]["transactions"]
    if not existing:
        pytest.skip("No transactions to extract user_id from")
    user_id = existing[0]["user_id"]

    response = client.get(
        f"/api/v1/admin/transactions?user_id={user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    for txn in response.json()["data"]["transactions"]:
        assert txn["user_id"] == user_id


def test_list_transactions_filter_by_plan(admin_token):
    # Pick a plan name from the first available transaction
    list_resp = client.get(
        "/api/v1/admin/transactions?limit=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    existing = list_resp.json()["data"]["transactions"]
    if not existing:
        pytest.skip("No transactions to extract plan name from")
    plan_name = existing[0]["package_name"]

    response = client.get(
        f"/api/v1/admin/transactions?plan={plan_name}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    for txn in response.json()["data"]["transactions"]:
        assert txn["package_name"].lower() == plan_name.lower()


def test_list_transactions_search(admin_token):
    list_resp = client.get(
        "/api/v1/admin/transactions?limit=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_resp.status_code == 200
    existing = list_resp.json()["data"]["transactions"]
    if not existing:
        pytest.skip("No transactions to search")

    target = existing[0]
    search_term = target.get("payment_id") or target.get("user_id") or target.get("package_name")
    response = client.get(
        f"/api/v1/admin/transactions?search={search_term}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    for txn in response.json()["data"]["transactions"]:
        haystack = " ".join([
            txn.get("payment_id", ""),
            txn.get("user_id", ""),
            txn.get("username", ""),
            txn.get("full_name", ""),
            txn.get("email", ""),
            txn.get("package_name", ""),
        ]).lower()
        assert search_term.lower() in haystack


# ── Field validations ──────────────────────────────────────────────────────

def test_transaction_subscription_type_values(admin_token):
    response = client.get(
        "/api/v1/admin/transactions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    transactions = response.json()["data"]["transactions"]
    for txn in transactions:
        assert txn["subscription_type"] in ("free", "monthly", "yearly")


def test_transaction_price_positive(admin_token):
    response = client.get(
        "/api/v1/admin/transactions?limit=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    transactions = response.json()["data"]["transactions"]
    if transactions:
        price = transactions[0]["price"]
        assert isinstance(price, (int, float))
        assert price >= 0


def test_transaction_status_values(admin_token):
    valid_statuses = {"completed", "expired", "pending", "past_due", "paid", "unpaid", "cancelled"}
    response = client.get(
        "/api/v1/admin/transactions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    transactions = response.json()["data"]["transactions"]
    for txn in transactions:
        assert txn["status"] in valid_statuses, f"Unexpected status: {txn['status']}"


def test_transaction_date_fields(admin_token):
    response = client.get(
        "/api/v1/admin/transactions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    transactions = response.json()["data"]["transactions"]
    for txn in transactions:
        assert txn.get("started_on") is None or isinstance(txn["started_on"], str)
        assert txn.get("ends_on") is None or isinstance(txn["ends_on"], str)
        assert isinstance(txn["created_at"], str)


def test_list_transactions_with_no_results(admin_token):
    """Use a far-future date range that should return nothing."""
    response = client.get(
        "/api/v1/admin/transactions?date_from=2099-06-01&date_to=2099-06-30",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    transactions = response.json()["data"]["transactions"]
    assert transactions == []


def test_transaction_profile_images_are_public(admin_token):
    response = client.get(
        "/api/v1/admin/transactions?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    for txn in response.json()["data"]["transactions"]:
        url = txn.get("profile_image_url")
        if url:
            assert "/storage/v1/object/public/" in url
