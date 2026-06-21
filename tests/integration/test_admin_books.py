"""
Phase 9.3 — Admin Books Management integration tests.
Tests: expanded from 5 to 14 test functions covering milestone spec.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

from tests.integration.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


@pytest.fixture(scope="session")
def admin_token():
    """Obtain a JWT token for admin."""
    response = client.post("/api/v1/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert response.status_code == 200
    data = response.json()["data"]
    token = data.get("session", {}).get("access_token") or data.get("access_token")
    assert token, "Token not found"
    return token


def _get_first_book(admin_token, status=None):
    """Helper: return the first book matching an optional status filter."""
    url = "/api/v1/admin/books?page=1&limit=1"
    if status:
        url += f"&status={status}"
    resp = client.get(url, headers={"Authorization": f"Bearer {admin_token}"})
    books = resp.json()["data"]["books"]
    return books[0] if books else None


# ── Dashboard ──────────────────────────────────────────────────────────────

def test_books_dashboard(admin_token):
    response = client.get(
        "/api/v1/admin/books/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    for field in ["total_books_uploaded", "total_books_published", "total_books_failed"]:
        assert field in data, f"Missing field: {field}"


# ── List books ─────────────────────────────────────────────────────────────

def test_list_books_returns_all_fields(admin_token):
    response = client.get(
        "/api/v1/admin/books?page=1&limit=5",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert "books" in result
    assert "total" in result
    assert "page" in result
    assert "limit" in result
    assert result["page"] == 1
    assert result["limit"] == 5
    if result["books"]:
        book = result["books"][0]
        for field in ["id", "title", "author", "ingestion_status", "created_at"]:
            assert field in book, f"Missing book field: {field}"


def test_list_books_pagination(admin_token):
    response = client.get(
        "/api/v1/admin/books?page=1&limit=5",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["page"] == 1
    assert result["limit"] == 5
    assert isinstance(result["books"], list)
    assert len(result["books"]) <= 5


def test_list_books_ordered_by_date(admin_token):
    response = client.get(
        "/api/v1/admin/books?limit=50",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    books = response.json()["data"]["books"]
    dates = [b["created_at"] for b in books if b.get("created_at")]
    if dates:
        assert dates == sorted(dates, reverse=True), "Books not ordered by created_at DESC"


def test_list_books_filter_by_status(admin_token):
    for status in ("pending", "processing", "ready", "failed"):
        response = client.get(
            f"/api/v1/admin/books?status={status}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        books = response.json()["data"]["books"]
        for book in books:
            assert book["ingestion_status"] == status, (
                f"Expected status={status}, got {book['ingestion_status']}"
            )


# ── Re-trigger ingestion ───────────────────────────────────────────────────

def test_trigger_ingestion_invalid_book(admin_token):
    response = client.post(
        "/api/v1/admin/books/00000000-0000-0000-0000-000000000000/ingest",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


@pytest.mark.skip(reason="Requires a pending book in the database")
def test_trigger_ingestion_pending_book(admin_token):
    book = _get_first_book(admin_token, status="pending")
    if not book:
        pytest.skip("No pending books in the database")
    response = client.post(
        f"/api/v1/admin/books/{book['id']}/ingest",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "processing"


@pytest.mark.skip(reason="Requires a failed book in the database")
def test_trigger_ingestion_failed_book(admin_token):
    book = _get_first_book(admin_token, status="failed")
    if not book:
        pytest.skip("No failed books in the database")
    response = client.post(
        f"/api/v1/admin/books/{book['id']}/ingest",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "processing"


def test_trigger_ingestion_ready_book_fails(admin_token):
    book = _get_first_book(admin_token, status="ready")
    if not book:
        pytest.skip("No ready books in the database")
    response = client.post(
        f"/api/v1/admin/books/{book['id']}/ingest",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 400
    assert "Cannot ingest" in response.json()["message"]


def test_trigger_ingestion_processing_book_fails(admin_token):
    book = _get_first_book(admin_token, status="processing")
    if not book:
        pytest.skip("No processing books in the database")
    response = client.post(
        f"/api/v1/admin/books/{book['id']}/ingest",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 400


# ── Publish / unpublish ────────────────────────────────────────────────────

def test_update_book_status_invalid_book(admin_token):
    response = client.put(
        "/api/v1/admin/books/00000000-0000-0000-0000-000000000000/status",
        json={"published": True},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


def test_update_book_published_status(admin_token):
    book = _get_first_book(admin_token, status="ready")
    if not book:
        pytest.skip("No ready books in the database")

    # Toggle on
    response = client.put(
        f"/api/v1/admin/books/{book['id']}/status",
        json={"published": True},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["published"] is True

    # Toggle off
    response = client.put(
        f"/api/v1/admin/books/{book['id']}/status",
        json={"published": False},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["published"] is False


def test_publish_unpublished_book_fails(admin_token):
    book = _get_first_book(admin_token, status="pending")
    if not book:
        book = _get_first_book(admin_token, status="failed")
    if not book:
        pytest.skip("No pending or failed books in the database")
    response = client.put(
        f"/api/v1/admin/books/{book['id']}/status",
        json={"published": True},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 400
    assert "Cannot publish" in response.json()["message"]


# ── Delete ─────────────────────────────────────────────────────────────────

def test_delete_book_invalid(admin_token):
    response = client.delete(
        "/api/v1/admin/books/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404
