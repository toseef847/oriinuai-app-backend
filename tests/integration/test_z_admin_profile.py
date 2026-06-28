"""
Phase 9.4 — Admin Profile Management integration tests.
Tests: expanded from 11 to 17 test functions covering milestone spec.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

from tests.integration.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


@pytest.fixture(scope="function")
def admin_token():
    """Log in as admin and return JWT token (fresh per test)."""
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    token = data.get("session", {}).get("access_token") or data.get("access_token")
    assert token, "Token not found"
    return token


def _reset_admin_name(admin_token):
    """Restore the admin full_name after tests that mutate it."""
    client.put(
        "/api/v1/admin/profile",
        data={"full_name": "Admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )


# ── GET profile ────────────────────────────────────────────────────────────

def test_get_admin_profile(admin_token):
    response = client.get(
        "/api/v1/admin/profile",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    for field in ["id", "email", "full_name", "bio", "profile_image_url"]:
        assert field in data


# ── Update full_name only ──────────────────────────────────────────────────

def test_update_full_name_only(admin_token):
    new_name = "New Admin Name"
    response = client.put(
        "/api/v1/admin/profile",
        data={"full_name": new_name},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["full_name"] == new_name
    assert "full_name" in data["updates_applied"]
    _reset_admin_name(admin_token)


# ── Update bio only ────────────────────────────────────────────────────────

def test_update_bio_only(admin_token):
    new_bio = "New bio here"
    response = client.put(
        "/api/v1/admin/profile",
        data={"bio": new_bio},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["bio"] == new_bio
    assert "bio" in data["updates_applied"]


# ── Update full_name and bio together ──────────────────────────────────────

def test_update_full_name_and_bio(admin_token):
    new_name = "Name Bio Combo"
    new_bio = "Combined bio update"
    response = client.put(
        "/api/v1/admin/profile",
        data={"full_name": new_name, "bio": new_bio},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["full_name"] == new_name
    assert data["bio"] == new_bio
    assert "full_name" in data["updates_applied"]
    assert "bio" in data["updates_applied"]
    _reset_admin_name(admin_token)


# ── Profile image ──────────────────────────────────────────────────────────

def test_upload_profile_image(admin_token, tmp_path):
    img_path = tmp_path / "test_image.jpg"
    img_path.write_bytes(b"\xff\xd8\xff\xd9")
    with open(img_path, "rb") as f:
        response = client.put(
            "/api/v1/admin/profile",
            files={"profile_image": ("test_image.jpg", f, "image/jpeg")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "profile_image_url" in data
    assert "profile_image" in data["updates_applied"]


def test_upload_invalid_image_type(admin_token, tmp_path):
    txt_path = tmp_path / "test_file.txt"
    txt_path.write_text("not an image")
    with open(txt_path, "rb") as f:
        response = client.put(
            "/api/v1/admin/profile",
            files={"profile_image": ("test_file.txt", f, "text/plain")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert response.status_code == 400
    assert "must be an image" in response.json()["message"].lower()


def test_upload_image_too_large(admin_token, tmp_path):
    """Profile images larger than 5 MiB are rejected."""
    img_path = tmp_path / "large.jpg"
    # ~6 MB file
    img_path.write_bytes(b"\xff\xd8\xff\xd9" * (6 * 1024 * 1024 // 3 + 1))
    with open(img_path, "rb") as f:
        response = client.put(
            "/api/v1/admin/profile",
            files={"profile_image": ("large.jpg", f, "image/jpeg")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert response.status_code == 413
    assert "must not exceed 5 MiB" in response.json()["message"]


# ── Password change ────────────────────────────────────────────────────────

def test_change_password_success(admin_token):
    new_pass = "new_secure_password"
    response = client.put(
        "/api/v1/admin/profile",
        data={
            "old_password": ADMIN_PASSWORD,
            "new_password": new_pass,
            "confirm_new_password": new_pass,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "password" in data["updates_applied"]
    # Verify login works with new password
    login_resp = client.post(
        "/api/v1/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": new_pass},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()["data"]
    new_token = data.get("session", {}).get("access_token") or data.get("access_token")
    assert new_token

    # Restore original password
    restore_resp = client.put(
        "/api/v1/admin/profile",
        data={
            "old_password": new_pass,
            "new_password": ADMIN_PASSWORD,
            "confirm_new_password": ADMIN_PASSWORD,
        },
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert restore_resp.status_code == 200


def test_change_password_wrong_old(admin_token):
    response = client.put(
        "/api/v1/admin/profile",
        data={
            "old_password": "wrong_password",
            "new_password": "new_pass",
            "confirm_new_password": "new_pass",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 401
    assert "current password is incorrect" in response.json()["message"].lower()


def test_change_password_mismatch(admin_token):
    response = client.put(
        "/api/v1/admin/profile",
        data={
            "old_password": ADMIN_PASSWORD,
            "new_password": "new_pass",
            "confirm_new_password": "different_pass",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400
    assert "do not match" in response.json()["message"].lower()


def test_change_password_too_short(admin_token):
    short_pass = "123"
    response = client.put(
        "/api/v1/admin/profile",
        data={
            "old_password": ADMIN_PASSWORD,
            "new_password": short_pass,
            "confirm_new_password": short_pass,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400
    assert "must be at least" in response.json()["message"].lower()


def test_change_password_missing_fields(admin_token):
    response = client.put(
        "/api/v1/admin/profile",
        data={"old_password": ADMIN_PASSWORD},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400
    assert "all three fields are required" in response.json()["message"].lower()


# ── Combined updates ───────────────────────────────────────────────────────

def test_update_all_fields(admin_token, tmp_path):
    new_name = "Updated Name"
    new_bio = "Updated bio"
    new_pass = "new_secure_password2"
    img_path = tmp_path / "test_image.jpg"
    img_path.write_bytes(b"\xff\xd8\xff\xd9")
    with open(img_path, "rb") as f:
        response = client.put(
            "/api/v1/admin/profile",
            data={
                "full_name": new_name,
                "bio": new_bio,
                "old_password": ADMIN_PASSWORD,
                "new_password": new_pass,
                "confirm_new_password": new_pass,
            },
            files={"profile_image": ("test_image.jpg", f, "image/jpeg")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert response.status_code == 200
    data = response.json()["data"]
    for field in ["full_name", "bio", "profile_image", "password"]:
        assert field in data["updates_applied"]
    # Verify new password works
    login_resp = client.post(
        "/api/v1/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": new_pass},
    )
    assert login_resp.status_code == 200
    # Restore original password
    client.put(
        "/api/v1/admin/profile",
        data={
            "old_password": new_pass,
            "new_password": ADMIN_PASSWORD,
            "confirm_new_password": ADMIN_PASSWORD,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    _reset_admin_name(admin_token)
