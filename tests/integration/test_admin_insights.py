"""
Phase 9.6 — Admin Analytics / Insights integration tests.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

from tests.integration.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


@pytest.fixture(scope="session")
def admin_token():
    """Obtain a JWT token for admin."""
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    token = data.get("session", {}).get("access_token") or data.get("access_token")
    assert token, "Token not found"
    return token


def test_dashboard_metrics_returned(admin_token):
    response = client.get(
        "/api/v1/admin/insights/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    expected_keys = [
        "total_users", "free_users", "premium_users", "total_earnings",
        "plan_distribution", "earnings_over_time", "recent_users",
    ]
    for key in expected_keys:
        assert key in data, f"Missing dashboard metric: {key}"


def test_total_users_count(admin_token):
    response = client.get(
        "/api/v1/admin/insights/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data["total_users"], int)
    assert data["total_users"] >= 0


def test_plan_distribution_structure(admin_token):
    response = client.get(
        "/api/v1/admin/insights/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    dist = response.json()["data"]["plan_distribution"]
    for plan_name in ("foundation", "core", "inner_circle"):
        assert plan_name in dist, f"Missing plan in distribution: {plan_name}"
        assert isinstance(dist[plan_name], int)


def test_recent_users_limited_to_six(admin_token):
    response = client.get(
        "/api/v1/admin/insights/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    recent = response.json()["data"]["recent_users"]
    assert isinstance(recent, list)
    assert len(recent) <= 6
    for u in recent:
        for field in ("id", "email", "full_name", "created_at"):
            assert field in u, f"Missing user field: {field}"


def test_earnings_over_time_structure(admin_token):
    response = client.get(
        "/api/v1/admin/insights/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    earnings = response.json()["data"]["earnings_over_time"]
    assert isinstance(earnings, list)
    for entry in earnings:
        assert "period" in entry
        assert "amount" in entry
        assert isinstance(entry["amount"], (int, float))
