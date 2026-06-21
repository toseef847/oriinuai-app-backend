"""
Shared fixtures for admin API integration tests.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

# ── Admin credentials (must exist in Supabase Auth + admins table) ──
ADMIN_EMAIL = "toseefhasan@gmail.com"
ADMIN_PASSWORD = "secure_password"

# ── Module-level client ──
client = TestClient(app)


@pytest.fixture(scope="session")
def admin_token():
    """
    Obtain a JWT token for an active admin.

    The session-scoped fixture logs in once and reuses the token
    across every test in every file that depends on it.
    """
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200, (
        f"Admin login failed ({response.status_code}): {response.text}"
    )
    data = response.json()["data"]
    # The login endpoint wraps the Supabase session object
    token = (
        data.get("session", {}).get("access_token")
        or data.get("access_token")
    )
    assert token, "access_token not found in login response"
    return token
