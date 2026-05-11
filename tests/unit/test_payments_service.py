from __future__ import annotations

import json

import pytest

from app.services.payments import stripe_service


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, data=None):
        self._data = data
        self._single = False

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def or_(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def maybe_single(self):
        self._single = True
        return self

    def update(self, *args, **kwargs):
        self._data = [{"id": "sub-1"}]
        return self

    def insert(self, *args, **kwargs):
        self._data = [{"id": "sub-1"}]
        return self

    def upsert(self, *args, **kwargs):
        self._data = [{"id": "payment-1"}]
        return self

    def execute(self):
        if self._single and isinstance(self._data, list):
            return _FakeResponse(self._data[0] if self._data else None)
        return _FakeResponse(self._data)


class _FakeTableClient:
    def __init__(self):
        self.calls = []
        self.responses = {}

    def table(self, name):
        self.calls.append(name)
        return _FakeQuery(self.responses.get(name))


def test_create_checkout_session_requires_price_id(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = {
        "id": "plan-core",
        "name": "core",
        "display_name": "Core",
        "stripe_monthly_price_id": None,
        "stripe_yearly_price_id": None,
        "is_active": True,
    }
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_CORE_MONTHLY_PRICE_ID", "")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_CORE_YEARLY_PRICE_ID", "")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_INNER_MONTHLY_PRICE_ID", "")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_INNER_YEARLY_PRICE_ID", "")

    with pytest.raises(stripe_service.HTTPException) as exc:
        stripe_service.create_checkout_session(
            user_id="user-1",
            email="user@example.com",
            plan_name="core",
            billing_interval="monthly",
        )

    assert exc.value.status_code == 400


def test_handle_webhook_event_accepts_signed_payload(monkeypatch):
    fake_event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_123",
                "status": "active",
                "customer": "cus_123",
                "current_period_end": 1710000000,
                "items": {
                    "data": [
                        {
                            "price": {
                                "id": "price_monthly",
                                "recurring": {"interval": "monthly"},
                            }
                        }
                    ]
                },
                "metadata": {"user_id": "user-1"},
            }
        },
    }

    class FakeStripeWebhook:
        @staticmethod
        def construct_event(*args, **kwargs):
            return fake_event

    class FakeSubscription:
        @staticmethod
        def retrieve(subscription_id):
            assert subscription_id == "sub_123"
            return fake_event["data"]["object"]

    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = {
        "id": "plan-core",
        "name": "core",
        "display_name": "Core",
        "stripe_monthly_price_id": "price_monthly",
        "stripe_yearly_price_id": "price_yearly",
        "is_active": True,
    }
    fake_client.responses["subscriptions"] = [{"id": "row-1", "stripe_customer_id": "cus_123"}]

    monkeypatch.setattr(stripe_service.stripe, "Webhook", FakeStripeWebhook)
    monkeypatch.setattr(stripe_service.stripe, "Subscription", FakeSubscription)
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    result = stripe_service.handle_webhook_event(json.dumps({"anything": True}), "sig")

    assert result["received"] is True
    assert result["event_type"] == "customer.subscription.updated"


def test_create_checkout_session_uses_env_price_fallback(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = {
        "id": "plan-core",
        "name": "core",
        "display_name": "Core",
        "stripe_monthly_price_id": None,
        "stripe_yearly_price_id": None,
        "is_active": True,
    }
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(
        stripe_service.settings,
        "STRIPE_CORE_MONTHLY_PRICE_ID",
        "price_env_monthly",
    )

    captured = {}

    class FakeCheckoutSession:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return type("Session", (), {"url": "https://checkout.test/session", "id": "cs_test"})()

    monkeypatch.setattr(stripe_service.stripe.checkout, "Session", FakeCheckoutSession)

    result = stripe_service.create_checkout_session(
        user_id="user-1",
        email="user@example.com",
        plan_name="core",
        billing_interval="monthly",
    )

    assert result["session_id"] == "cs_test"
    assert captured["line_items"][0]["price"] == "price_env_monthly"
