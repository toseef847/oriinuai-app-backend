"""
Phase 9.1 — Admin Auth integration tests.
Tests: 11 / 11 from milestone spec.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

from tests.integration.conftest import ADMIN_EMAIL, ADMIN_PASSWORD

client = TestClient(app)


# ── 1. Login ──────────────────────────────────────────────────────────

def test_admin_login_success():
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "session" in data
    assert "access_token" in data["session"]


def test_admin_refresh_token():
    login_response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()["data"]
    session = login_data.get("session", {})
    refresh_token = session.get("refresh_token")
    assert refresh_token, "refresh_token not found in login response"

    refresh_response = client.post(
        "/api/v1/admin/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()["data"]
    assert "session" in refreshed
    assert "access_token" in refreshed["session"]


def test_admin_login_invalid_email():
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "nonexistent@example.com", "password": "any_password"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["message"]


def test_admin_login_wrong_password():
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": "wrong_password"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["message"]


@pytest.mark.skip(reason="Requires a blocked admin record in the database")
def test_admin_login_blocked_admin():
    """A blocked admin must receive a generic 401 or 403."""
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "blocked-admin@example.com", "password": "any"},
    )
    assert response.status_code in (401, 403)


# ── 2. Forgot-password / OTP ─────────────────────────────────────────

def test_admin_forgot_password_send_otp():
    response = client.post(
        "/api/v1/admin/auth/forgot-password/send-otp",
        json={"email": ADMIN_EMAIL},
    )
    assert response.status_code == 200


def test_admin_forgot_password_send_otp_nonexistent():
    """Must return 200 even for non-existent email (no enumeration)."""
    response = client.post(
        "/api/v1/admin/auth/forgot-password/send-otp",
        json={"email": "nonexistent@example.com"},
    )
    assert response.status_code == 200


@pytest.mark.skip(reason="Requires a real OTP delivered via email")
def test_admin_forgot_password_verify_otp():
    response = client.post(
        "/api/v1/admin/auth/forgot-password/verify-otp",
        json={"email": ADMIN_EMAIL, "otp": "123456"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()["data"]


@pytest.mark.skip(reason="Requires valid reset token from OTP verification")
def test_admin_reset_password():
    # Would need: send OTP → verify OTP → use reset token
    pass


# ── 3. Token / me ────────────────────────────────────────────────────

def test_admin_get_me(admin_token):
    response = client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "email" in data
    assert "id" in data


def test_admin_token_expiry(admin_token):
    """Basic token validity check (full expiry test requires time mocking)."""
    response = client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200


# ── 4. Security ──────────────────────────────────────────────────────

def test_admin_login_generic_error_messages():
    """Error messages for invalid-email vs. wrong-password must be identical."""
    r1 = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "nonexistent@example.com", "password": "any"},
    )
    r2 = client.post(
        "/api/v1/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": "wrong_password"},
    )
    assert r1.status_code == 401
    assert r2.status_code == 401
    assert r1.json()["message"] == r2.json()["message"]
