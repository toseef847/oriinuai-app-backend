from __future__ import annotations

import hashlib
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

import app.db.supabase as supabase_module
import app.core.security as security
import app.services.auth.auth_service as auth_service
import app.services.auth.rate_limit_service as rate_limit_service
import app.services.auth.reset_store as reset_store
from app.core.config import settings
from app.core.security import require_admin
from app.main import app
from app.utils.uploads import read_upload_with_limit


class _ResetQuery:
    def __init__(self, result_data: list[dict] | None = None):
        self.inserted = None
        self.filters = []
        self.result_data = result_data or []

    def insert(self, payload):
        self.inserted = payload
        return self

    def select(self, fields):
        return self

    def update(self, payload):
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def gt(self, field, value):
        self.filters.append((field, value))
        return self

    def limit(self, count):
        return self

    def execute(self):
        return SimpleNamespace(data=self.result_data)


class _ResetClient:
    def __init__(self, query: _ResetQuery):
        self.query = query

    def table(self, name):
        assert name == "password_resets"
        return self.query


class _FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.key = None

    def incr(self, key):
        self.key = key
        return self

    def expire(self, key, seconds):
        assert key == self.key
        assert seconds > 0
        return self

    async def execute(self):
        self.redis.counts[self.key] = self.redis.counts.get(self.key, 0) + 1
        return [self.redis.counts[self.key], True]


class _FakeRedis:
    def __init__(self):
        self.counts = {}
        self.deleted = []

    def pipeline(self, transaction=True):
        assert transaction is True
        return _FakePipeline(self)

    async def delete(self, key):
        self.deleted.append(key)


def test_user_postgrest_client_uses_anon_key_and_user_jwt(monkeypatch):
    captured = {}

    class _Client:
        def __init__(self, url, headers, timeout):
            captured.update(url=url, headers=headers, timeout=timeout)

    monkeypatch.setattr(supabase_module, "AsyncPostgrestClient", _Client)
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "anon-key")

    supabase_module.create_user_postgrest_client("user-jwt")

    assert captured["headers"] == {
        "apikey": "anon-key",
        "Authorization": "Bearer user-jwt",
    }
    assert settings.SUPABASE_SERVICE_ROLE_KEY not in captured["headers"].values()


def test_reset_token_is_stored_as_sha256_digest(monkeypatch):
    query = _ResetQuery()
    monkeypatch.setattr(reset_store, "supabase_admin", _ResetClient(query))
    monkeypatch.setattr(
        reset_store.secrets, "token_urlsafe", lambda _: "raw-reset-token"
    )

    token = reset_store.create_reset_token("user-1")

    assert token == "raw-reset-token"
    assert (
        query.inserted["token_hash"]
        == hashlib.sha256(token.encode("utf-8")).hexdigest()
    )
    assert token not in query.inserted.values()


def test_reset_token_lookup_hashes_incoming_token(monkeypatch):
    query = _ResetQuery(result_data=[{"user_id": "user-1"}])
    monkeypatch.setattr(reset_store, "supabase_admin", _ResetClient(query))

    assert reset_store.consume_reset_token("raw-reset-token") == "user-1"
    assert (
        "token_hash",
        hashlib.sha256(b"raw-reset-token").hexdigest(),
    ) in query.filters


@pytest.mark.asyncio
async def test_upload_limit_accepts_exact_boundary():
    upload = UploadFile(filename="image.jpg", file=io.BytesIO(b"a" * 8))
    assert await read_upload_with_limit(upload, 8, "Profile image") == b"a" * 8


@pytest.mark.asyncio
async def test_upload_limit_rejects_one_byte_over_boundary():
    upload = UploadFile(filename="image.jpg", file=io.BytesIO(b"a" * 9))
    with pytest.raises(HTTPException) as exc_info:
        await read_upload_with_limit(upload, 8, "Profile image")
    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_auth_rate_limit_rejects_sixth_attempt(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(rate_limit_service, "_redis_client", fake_redis)
    monkeypatch.setattr(rate_limit_service.time, "time", lambda: 1_000)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ATTEMPTS", 5)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 900)

    leases = [
        await rate_limit_service.enforce_auth_rate_limit("login", "User@example.com")
        for _ in range(5)
    ]

    assert len({lease.key for lease in leases}) == 1
    with pytest.raises(HTTPException) as exc_info:
        await rate_limit_service.enforce_auth_rate_limit("login", "user@example.com")
    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "800"


@pytest.mark.asyncio
async def test_auth_rate_limit_fails_open_on_redis_error(monkeypatch):
    broken_redis = SimpleNamespace(
        pipeline=lambda transaction=True: SimpleNamespace(
            incr=lambda key: None,
            expire=lambda key, seconds: None,
            execute=AsyncMock(side_effect=RedisError("offline")),
        )
    )
    monkeypatch.setattr(rate_limit_service, "_redis_client", broken_redis)

    lease = await rate_limit_service.enforce_auth_rate_limit(
        "login", "user@example.com"
    )

    assert lease is None


def test_validation_details_hidden_in_production(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)
    response = TestClient(app).post("/api/v1/auth/signup", json={})
    assert response.status_code == 422
    assert response.json()["data"] is None


def test_validation_details_available_in_debug(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)
    response = TestClient(app).post("/api/v1/auth/signup", json={})
    assert response.status_code == 422
    assert response.json()["data"]


def test_oversized_book_is_rejected_before_database_work(monkeypatch):
    monkeypatch.setattr(settings, "MAX_BOOK_UPLOAD_BYTES", 8)
    app.dependency_overrides[require_admin] = lambda: {"id": "admin-1"}
    try:
        response = TestClient(app).post(
            "/api/v1/admin/books/upload",
            files={"file": ("large.pdf", b"a" * 9, "application/pdf")},
        )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 413
    assert response.json()["data"] is None


@pytest.mark.asyncio
async def test_oversized_profile_image_causes_no_profile_side_effects(monkeypatch):
    monkeypatch.setattr(settings, "MAX_PROFILE_IMAGE_UPLOAD_BYTES", 8)
    upload = UploadFile(
        filename="large.jpg",
        file=io.BytesIO(b"a" * 9),
        headers={"content-type": "image/jpeg"},
    )
    admin_client = SimpleNamespace(
        auth=SimpleNamespace(
            admin=SimpleNamespace(
                update_user_by_id=lambda *args: pytest.fail(
                    "auth metadata changed before upload validation"
                )
            )
        )
    )
    monkeypatch.setattr(auth_service, "supabase_admin", admin_client)

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.update_user_profile(
            "user-1",
            SimpleNamespace(),
            full_name="Changed Name",
            image=upload,
        )

    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_blocked_profile_is_rejected_before_user_endpoint_access():
    query = _ResetQuery(result_data=[{"id": "user-1", "is_blocked": True}])
    query.execute = AsyncMock(
        return_value=SimpleNamespace(data=[{"id": "user-1", "is_blocked": True}])
    )
    client = SimpleNamespace(table=lambda name: query)

    with pytest.raises(HTTPException) as exc_info:
        await security.get_current_profile(
            payload={"sub": "user-1"},
            client=client,
        )

    assert exc_info.value.status_code == 403


def test_blocked_user_cannot_refresh_and_new_session_is_revoked(monkeypatch):
    query = _ResetQuery(result_data=[{"is_blocked": True}])
    signed_out = []
    admin_client = SimpleNamespace(
        table=lambda name: query,
        auth=SimpleNamespace(
            admin=SimpleNamespace(sign_out=lambda token: signed_out.append(token))
        ),
    )
    result = SimpleNamespace(
        user=SimpleNamespace(id="user-1"),
        session=SimpleNamespace(access_token="new-access-token"),
    )
    auth_client = SimpleNamespace(
        auth=SimpleNamespace(refresh_session=lambda token: result)
    )
    monkeypatch.setattr(auth_service, "_auth_client", lambda: auth_client)
    monkeypatch.setattr(auth_service, "supabase_admin", admin_client)
    monkeypatch.setattr(auth_service, "reset_admin_auth_header", lambda: None)

    with pytest.raises(HTTPException) as exc_info:
        auth_service.refresh_token("refresh-token")

    assert exc_info.value.status_code == 403
    assert signed_out == ["new-access-token"]


@pytest.mark.asyncio
async def test_password_update_restores_admin_header_before_admin_call(monkeypatch):
    query = _ResetQuery()
    query.execute = AsyncMock(
        return_value=SimpleNamespace(data=[{"email": "user@example.com"}])
    )
    events = []
    admin_client = SimpleNamespace(
        auth=SimpleNamespace(
            admin=SimpleNamespace(
                update_user_by_id=lambda user_id, payload: events.append("update")
            )
        )
    )
    auth_client = SimpleNamespace(
        auth=SimpleNamespace(sign_in_with_password=lambda payload: object())
    )
    monkeypatch.setattr(auth_service, "_auth_client", lambda: auth_client)
    monkeypatch.setattr(auth_service, "supabase_admin", admin_client)
    monkeypatch.setattr(
        auth_service,
        "reset_admin_auth_header",
        lambda: events.append("reset"),
    )

    await auth_service.update_user_password(
        "user-1",
        "current-password",
        "new-password",
        SimpleNamespace(table=lambda name: query),
    )

    assert events == ["reset", "update"]
