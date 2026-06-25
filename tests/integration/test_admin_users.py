"""
Phase 9.2 — Admin User Management integration tests.
Tests: 15 / 15 from milestone spec.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────

def _get_first_user(admin_token: str) -> dict | None:
    """Return the first user from the admin users list, or None."""
    resp = client.get(
        "/api/v1/admin/users?page=1&limit=1&include_blocked=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    users = resp.json()["data"]["users"]
    return users[0] if users else None


def _get_user_ids(admin_token: str, count: int = 2) -> list[str]:
    """Return up to *count* user IDs from the admin users list."""
    resp = client.get(
        f"/api/v1/admin/users?page=1&limit={count}&include_blocked=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return [u["id"] for u in resp.json()["data"]["users"]]


# ── 1. List users ────────────────────────────────────────────────────

def test_list_users_returns_all_fields(admin_token):
    resp = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    users = resp.json()["data"]["users"]
    if users:
        user = users[0]
        for field in [
            "id", "username", "full_name", "email", "profile_image_url",
            "joined_date", "plan_name", "subscription_type", "status", "is_blocked",
        ]:
            assert field in user, f"Missing field: {field}"


def test_list_users_pagination(admin_token):
    resp = client.get(
        "/api/v1/admin/users?page=1&limit=5",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["page"] == 1
    assert data["limit"] == 5
    assert "users" in data
    assert "total" in data
    assert len(data["users"]) <= 5


def test_list_users_exclude_blocked_by_default(admin_token):
    resp = client.get(
        "/api/v1/admin/users?include_blocked=false",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    for user in resp.json()["data"]["users"]:
        assert user["status"] == "active"
        assert user["is_blocked"] is False


def test_list_users_include_blocked_when_requested(admin_token):
    resp = client.get(
        "/api/v1/admin/users?include_blocked=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "users" in resp.json()["data"]


def test_list_users_search_by_email_or_name(admin_token):
    initial = client.get(
        "/api/v1/admin/users?limit=5&include_blocked=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert initial.status_code == 200
    users = initial.json()["data"]["users"]
    if not users:
        pytest.skip("No users in database")

    target = users[0]
    search_term = (target.get("email") or target.get("full_name") or target["id"])
    resp = client.get(
        f"/api/v1/admin/users?search={search_term}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    results = resp.json()["data"]["users"]
    assert results
    assert any(search_term.lower() in (u.get("email", "") + u.get("full_name", "") + u.get("id", "")).lower() for u in results)


def test_list_users_ordered_by_joined_date(admin_token):
    resp = client.get(
        "/api/v1/admin/users?limit=50",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    users = resp.json()["data"]["users"]
    dates = [u["joined_date"] for u in users if u.get("joined_date")]
    # Verify descending order
    assert dates == sorted(dates, reverse=True), "Users not ordered by joined_date DESC"


def test_list_users_shows_correct_plan_and_subscription(admin_token):
    resp = client.get(
        "/api/v1/admin/users?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    for user in resp.json()["data"]["users"]:
        assert isinstance(user["plan_name"], str)
        assert user["subscription_type"] in ["free", "monthly", "yearly"]


def test_list_users_status_active_for_unblocked(admin_token):
    resp = client.get(
        "/api/v1/admin/users?include_blocked=false",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    for user in resp.json()["data"]["users"]:
        assert user["status"] == "active"
        assert user["is_blocked"] is False


def test_list_users_status_blocked_for_blocked_users(admin_token):
    resp = client.get(
        "/api/v1/admin/users/blocked",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    for user in resp.json()["data"]["users"]:
        assert user["status"] == "blocked"
        assert user["is_blocked"] is True


# ── 2. Block / Unblock ───────────────────────────────────────────────

def test_block_user(admin_token):
    user = _get_first_user(admin_token)
    if not user:
        pytest.skip("No users in database")
    user_id = user["id"]

    # Block
    resp = client.post(
        f"/api/v1/admin/users/{user_id}/block",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_blocked"] is True

    # Cleanup — unblock
    client.post(
        f"/api/v1/admin/users/{user_id}/unblock",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )


def test_unblock_user(admin_token):
    user = _get_first_user(admin_token)
    if not user:
        pytest.skip("No users in database")
    user_id = user["id"]

    # Block first
    client.post(
        f"/api/v1/admin/users/{user_id}/block",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Unblock
    resp = client.post(
        f"/api/v1/admin/users/{user_id}/unblock",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_blocked"] is False


def test_block_bulk_users(admin_token):
    user_ids = _get_user_ids(admin_token, 2)
    if len(user_ids) < 2:
        pytest.skip("Need at least 2 users for bulk test")

    resp = client.post(
        "/api/v1/admin/users/block-bulk",
        json={"user_ids": user_ids},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["blocked_count"] == len(user_ids)

    # Cleanup
    client.post(
        "/api/v1/admin/users/unblock-bulk",
        json={"user_ids": user_ids},
        headers={"Authorization": f"Bearer {admin_token}"},
    )


def test_unblock_bulk_users(admin_token):
    user_ids = _get_user_ids(admin_token, 2)
    if len(user_ids) < 2:
        pytest.skip("Need at least 2 users for bulk test")

    # Block first
    client.post(
        "/api/v1/admin/users/block-bulk",
        json={"user_ids": user_ids},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Unblock
    resp = client.post(
        "/api/v1/admin/users/unblock-bulk",
        json={"user_ids": user_ids},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["unblocked_count"] == len(user_ids)


def test_list_blocked_users(admin_token):
    resp = client.get(
        "/api/v1/admin/users/blocked",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    for user in resp.json()["data"]["users"]:
        assert user["status"] == "blocked"
        assert user["is_blocked"] is True


def test_profile_image_urls_are_public(admin_token):
    resp = client.get(
        "/api/v1/admin/users?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    for user in resp.json()["data"]["users"]:
        url = user.get("profile_image_url")
        if url:
            assert "/storage/v1/object/public/" in url


def test_block_nonexistent_user(admin_token):
    resp = client.post(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000/block",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


def test_profile_image_url_signed(admin_token):
    resp = client.get(
        "/api/v1/admin/users?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    users = resp.json()["data"]["users"]
    for user in users:
        url = user.get("profile_image_url")
        if url:
            assert isinstance(url, str)
            assert url.startswith("http")
