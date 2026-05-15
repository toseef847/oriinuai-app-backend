from __future__ import annotations

import app.db.supabase as supabase_module
import app.services.auth.auth_service as auth_service


class _FakeAuth:
    def __init__(self):
        self.calls = []

    def sign_in_with_password(self, payload):
        self.calls.append(("sign_in_with_password", payload))

        class _Result:
            user = None
            session = None

        return _Result()


class _FakeClient:
    def __init__(self):
        self.auth = _FakeAuth()


def test_create_auth_supabase_client_disables_session_persistence(monkeypatch):
    captured = {}

    def fake_create_client(url, key, options=None):
        captured["url"] = url
        captured["key"] = key
        captured["options"] = options
        return _FakeClient()

    monkeypatch.setattr(supabase_module, "create_client", fake_create_client)
    monkeypatch.setattr(supabase_module.settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(supabase_module.settings, "SUPABASE_ANON_KEY", "anon-key")

    client = supabase_module.create_auth_supabase_client()

    assert isinstance(client, _FakeClient)
    assert captured["url"] == "https://example.supabase.co"
    assert captured["key"] == "anon-key"
    assert captured["options"].persist_session is False
    assert captured["options"].auto_refresh_token is False


def test_login_user_uses_auth_client_not_admin_client(monkeypatch):
    auth_client = _FakeClient()
    admin_client = _FakeClient()

    monkeypatch.setattr(auth_service, "create_auth_supabase_client", lambda: auth_client)
    monkeypatch.setattr(auth_service, "supabase_admin", admin_client)

    auth_service.login_user("user@example.com", "secret")

    assert auth_client.auth.calls == [
        ("sign_in_with_password", {"email": "user@example.com", "password": "secret"})
    ]
    assert admin_client.auth.calls == []
