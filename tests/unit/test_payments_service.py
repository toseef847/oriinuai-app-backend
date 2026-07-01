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
        self.last_payload = None
        self.last_kwargs = None
        self.filters = []

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        self.filters.append(("eq", args, kwargs))
        return self

    def or_(self, *args, **kwargs):
        self.filters.append(("or_", args, kwargs))
        return self

    def in_(self, *args, **kwargs):
        self.filters.append(("in_", args, kwargs))
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def maybe_single(self):
        self._single = True
        return self

    def update(self, *args, **kwargs):
        self.last_payload = args[0] if args else None
        self.last_kwargs = kwargs
        self._data = [{"id": "sub-1"}]
        return self

    def insert(self, *args, **kwargs):
        self.last_payload = args[0] if args else None
        self.last_kwargs = kwargs
        self._data = [{"id": "sub-1"}]
        return self

    def upsert(self, *args, **kwargs):
        self.last_payload = args[0] if args else None
        self.last_kwargs = kwargs
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
        self.last_query_by_name = {}

    def table(self, name):
        self.calls.append(name)
        query = _FakeQuery(self.responses.get(name))
        self.last_query_by_name[name] = query
        return query


def test_invoice_subscription_snapshot_uses_invoice_line_not_current_subscription(
    monkeypatch,
):
    plans = {
        "price_core_monthly": {
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": "price_core_monthly",
            "stripe_yearly_price_id": "price_core_yearly",
        },
        "price_inner_yearly": {
            "name": "inner_circle",
            "display_name": "Inner Circle",
            "stripe_monthly_price_id": "price_inner_monthly",
            "stripe_yearly_price_id": "price_inner_yearly",
        },
    }
    monkeypatch.setattr(
        stripe_service,
        "_find_plan_by_price_id",
        lambda price_id: plans[price_id],
    )
    invoice = {
        "subscription": "sub_123",
        "lines": {
            "data": [
                {
                    "subscription": "sub_123",
                    "amount": 2900,
                    "price": {
                        "id": "price_core_monthly",
                        "recurring": {"interval": "month"},
                    },
                    "period": {"start": 1710000000, "end": 1712678400},
                }
            ]
        },
    }
    current_subscription = {
        "id": "sub_123",
        "items": {
            "data": [
                {
                    "price": {
                        "id": "price_inner_yearly",
                        "recurring": {"interval": "year"},
                    }
                }
            ]
        },
        "current_period_end": 1744214400,
    }

    snapshot = stripe_service._invoice_subscription_snapshot(
        invoice, current_subscription
    )

    assert snapshot["package_name"] == "Core"
    assert snapshot["billing_interval"] == "monthly"
    assert snapshot["stripe_subscription_id"] == "sub_123"
    assert snapshot["period_start"] == "2024-03-09T16:00:00+00:00"
    assert snapshot["period_end"] == "2024-04-09T16:00:00+00:00"


def test_create_checkout_session_requires_price_id(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-core",
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": None,
            "stripe_yearly_price_id": None,
            "is_active": True,
        }
    ]
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


def test_create_checkout_session_rejects_active_subscription(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-core",
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": "price_monthly",
            "stripe_yearly_price_id": "price_yearly",
            "is_active": True,
        }
    ]
    fake_client.responses["subscriptions"] = [
        {
            "id": "sub-row-1",
            "user_id": "user-1",
            "status": "active",
            "stripe_customer_id": "cus_123",
            "stripe_sub_id": "sub_123",
            "plan_id": "plan-core",
            "plans": {"name": "core"},
        }
    ]
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")

    with pytest.raises(stripe_service.HTTPException) as exc:
        stripe_service.create_checkout_session(
            user_id="user-1",
            email="user@example.com",
            plan_name="core",
            billing_interval="monthly",
        )

    assert exc.value.status_code == 409
    assert any(
        kind == "in_" and args and args[0] == "status"
        for kind, args, _kwargs in fake_client.last_query_by_name[
            "subscriptions"
        ].filters
    )


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
    fake_client.responses["plans"] = [
        {
            "id": "plan-core",
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": "price_monthly",
            "stripe_yearly_price_id": "price_yearly",
            "is_active": True,
        }
    ]
    fake_client.responses["subscriptions"] = [
        {"id": "row-1", "stripe_customer_id": "cus_123"}
    ]

    monkeypatch.setattr(stripe_service.stripe, "Webhook", FakeStripeWebhook)
    monkeypatch.setattr(stripe_service.stripe, "Subscription", FakeSubscription)
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    result = stripe_service.handle_webhook_event(json.dumps({"anything": True}), "sig")

    assert result["received"] is True
    assert result["event_type"] == "customer.subscription.updated"


def test_subscription_update_tracks_pending_cancellation(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["subscriptions"] = [
        {"id": "row-1", "user_id": "user-1", "stripe_sub_id": "sub_123"}
    ]
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)

    stripe_service._upsert_subscription_row(
        {
            "id": "sub_123",
            "customer": "cus_123",
            "status": "active",
            "cancel_at_period_end": True,
            "cancel_at": 1712678400,
        }
    )

    payload = fake_client.last_query_by_name["subscriptions"].last_payload
    assert payload["cancel_at_period_end"] is True
    assert payload["cancel_at"] == "2024-04-09T16:00:00+00:00"


def test_subscription_schedule_tracks_future_plan_change(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["subscriptions"] = [
        {"id": "row-1", "user_id": "user-1", "stripe_sub_id": "sub_123"}
    ]
    fake_client.responses["plans"] = [
        {
            "id": "plan-inner",
            "name": "inner_circle",
            "display_name": "Inner Circle",
            "stripe_monthly_price_id": "price_inner_monthly",
            "stripe_yearly_price_id": "price_inner_yearly",
        }
    ]
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)

    stripe_service._upsert_subscription_schedule(
        {
            "id": "sub_sched_123",
            "status": "active",
            "subscription": "sub_123",
            "current_phase": {"start_date": 1681142400, "end_date": 1712678400},
            "phases": [
                {
                    "start_date": 1681142400,
                    "end_date": 1712678400,
                    "items": [{"price": "price_inner_yearly"}],
                },
                {
                    "start_date": 1712678400,
                    "end_date": 1715270400,
                    "items": [{"price": "price_inner_monthly"}],
                },
            ],
        }
    )

    payload = fake_client.last_query_by_name["subscriptions"].last_payload
    assert payload["stripe_schedule_id"] == "sub_sched_123"
    assert payload["pending_plan_id"] == "plan-inner"
    assert payload["pending_billing_interval"] == "monthly"
    assert payload["pending_effective_at"] == "2024-04-09T16:00:00+00:00"


def test_terminal_subscription_schedule_clears_pending_change(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["subscriptions"] = [
        {"id": "row-1", "user_id": "user-1", "stripe_sub_id": "sub_123"}
    ]
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)

    stripe_service._clear_subscription_schedule(
        {
            "id": "sub_sched_123",
            "status": "released",
            "released_subscription": "sub_123",
        }
    )

    payload = fake_client.last_query_by_name["subscriptions"].last_payload
    assert payload == {
        "stripe_schedule_id": None,
        "pending_plan_id": None,
        "pending_billing_interval": None,
        "pending_effective_at": None,
    }


@pytest.mark.parametrize(
    "event_type",
    ["checkout.session.completed", "checkout.session.async_payment_succeeded"],
)
def test_handle_webhook_event_serializes_checkout_subscription_timestamps(
    monkeypatch, event_type
):
    fake_event = {
        "type": event_type,
        "data": {
            "object": {
                "id": "cs_123",
                "subscription": "sub_123",
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
            return {
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

    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-core",
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": "price_monthly",
            "stripe_yearly_price_id": "price_yearly",
            "is_active": True,
        }
    ]

    monkeypatch.setattr(stripe_service.stripe, "Webhook", FakeStripeWebhook)
    monkeypatch.setattr(stripe_service.stripe, "Subscription", FakeSubscription)
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    result = stripe_service.handle_webhook_event(json.dumps({"anything": True}), "sig")

    assert result["received"] is True
    assert result["event_type"] == event_type
    assert (
        fake_client.last_query_by_name["subscriptions"].last_payload["billing_interval"]
        == "monthly"
    )
    assert (
        fake_client.last_query_by_name["subscriptions"].last_payload[
            "current_period_end"
        ]
        == "2024-03-09T16:00:00+00:00"
    )


def test_handle_webhook_event_maps_stripe_year_interval(monkeypatch):
    fake_event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_123",
                "subscription": "sub_123",
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
            return {
                "id": "sub_123",
                "status": "active",
                "customer": "cus_123",
                "current_period_end": 1710000000,
                "items": {
                    "data": [
                        {
                            "price": {
                                "id": "price_yearly",
                                "recurring": {"interval": "year"},
                            }
                        }
                    ]
                },
                "metadata": {"user_id": "user-1"},
            }

    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-core",
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": "price_monthly",
            "stripe_yearly_price_id": "price_yearly",
            "is_active": True,
        }
    ]

    monkeypatch.setattr(stripe_service.stripe, "Webhook", FakeStripeWebhook)
    monkeypatch.setattr(stripe_service.stripe, "Subscription", FakeSubscription)
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    result = stripe_service.handle_webhook_event(json.dumps({"anything": True}), "sig")

    assert result["received"] is True
    assert result["event_type"] == "checkout.session.completed"
    assert (
        fake_client.last_query_by_name["subscriptions"].last_payload["billing_interval"]
        == "yearly"
    )


@pytest.mark.parametrize("event_type", ["invoice.paid", "invoice.payment_succeeded"])
def test_handle_webhook_event_processes_invoice_payment_events(monkeypatch, event_type):
    fake_event = {
        "type": event_type,
        "data": {
            "object": {
                "id": "in_123",
                "customer": "cus_123",
                "subscription": "sub_123",
                "amount_paid": 4999,
                "currency": "usd",
                "status": "paid",
                "status_transitions": {"paid_at": 1710000000},
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
            return {
                "id": "sub_123",
                "customer": "cus_123",
                "metadata": {},
            }

    fake_client = _FakeTableClient()
    fake_client.responses["subscriptions"] = [
        {
            "id": "row-1",
            "user_id": "user-1",
            "stripe_customer_id": "cus_123",
            "stripe_sub_id": "sub_123",
        }
    ]

    monkeypatch.setattr(stripe_service.stripe, "Webhook", FakeStripeWebhook)
    monkeypatch.setattr(stripe_service.stripe, "Subscription", FakeSubscription)
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    result = stripe_service.handle_webhook_event(json.dumps({"anything": True}), "sig")

    assert result["received"] is True
    assert result["event_type"] == event_type
    assert (
        fake_client.last_query_by_name["payments"].last_payload["user_id"] == "user-1"
    )


@pytest.mark.parametrize("event_type", ["invoice.paid", "invoice.payment_succeeded"])
def test_handle_webhook_event_resolves_user_from_invoice_subscription_snapshot(
    monkeypatch, event_type
):
    fake_event = {
        "type": event_type,
        "data": {
            "object": {
                "id": "in_123",
            }
        },
    }

    class FakeStripeWebhook:
        @staticmethod
        def construct_event(*args, **kwargs):
            return fake_event

    class FakeInvoice:
        @staticmethod
        def retrieve(invoice_id):
            assert invoice_id == "in_123"
            return {
                "id": "in_123",
                "customer": "cus_123",
                "subscription": "sub_123",
                "amount_paid": 4999,
                "currency": "usd",
                "status": "paid",
                "status_transitions": {"paid_at": 1710000000},
                "parent": {"subscription_details": {"metadata": {"user_id": "user-1"}}},
            }

    class FakeSubscription:
        @staticmethod
        def retrieve(subscription_id):
            assert subscription_id == "sub_123"
            return {
                "id": "sub_123",
                "customer": "cus_123",
                "metadata": {},
            }

    fake_client = _FakeTableClient()

    monkeypatch.setattr(stripe_service.stripe, "Webhook", FakeStripeWebhook)
    monkeypatch.setattr(stripe_service.stripe, "Invoice", FakeInvoice)
    monkeypatch.setattr(stripe_service.stripe, "Subscription", FakeSubscription)
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    result = stripe_service.handle_webhook_event(json.dumps({"anything": True}), "sig")

    assert result["received"] is True
    assert result["event_type"] == event_type
    assert (
        fake_client.last_query_by_name["payments"].last_payload["user_id"] == "user-1"
    )
    assert (
        fake_client.last_query_by_name["payments"].last_payload["stripe_invoice_id"]
        == "in_123"
    )


def test_handle_webhook_event_processes_invoice_payment_object_event(monkeypatch):
    fake_event = {
        "type": "invoice_payment.paid",
        "data": {
            "object": {
                "id": "ip_123",
                "invoice": "in_123",
                "amount_paid": 4999,
                "amount_requested": 4999,
                "is_default": True,
                "payment": {"payment_intent": "pi_123"},
            }
        },
    }

    class FakeStripeWebhook:
        @staticmethod
        def construct_event(*args, **kwargs):
            return fake_event

    class FakeInvoice:
        @staticmethod
        def retrieve(invoice_id):
            assert invoice_id == "in_123"
            return {
                "id": "in_123",
                "customer": "cus_123",
                "subscription": "sub_123",
                "amount_paid": 4999,
                "currency": "usd",
                "status": "paid",
                "status_transitions": {"paid_at": 1710000000},
            }

    class FakeSubscription:
        @staticmethod
        def retrieve(subscription_id):
            assert subscription_id == "sub_123"
            return {
                "id": "sub_123",
                "customer": "cus_123",
                "metadata": {},
            }

    fake_client = _FakeTableClient()
    fake_client.responses["subscriptions"] = [
        {
            "id": "row-1",
            "user_id": "user-1",
            "stripe_customer_id": "cus_123",
            "stripe_sub_id": "sub_123",
        }
    ]

    monkeypatch.setattr(stripe_service.stripe, "Webhook", FakeStripeWebhook)
    monkeypatch.setattr(stripe_service.stripe, "Invoice", FakeInvoice)
    monkeypatch.setattr(stripe_service.stripe, "Subscription", FakeSubscription)
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    result = stripe_service.handle_webhook_event(json.dumps({"anything": True}), "sig")

    assert result["received"] is True
    assert result["event_type"] == "invoice_payment.paid"
    assert (
        fake_client.last_query_by_name["payments"].last_payload["stripe_invoice_id"]
        == "in_123"
    )
    assert (
        fake_client.last_query_by_name["payments"].last_payload["user_id"] == "user-1"
    )


def test_handle_webhook_event_records_failed_invoice_payment(monkeypatch):
    fake_event = {
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_123",
                "customer": "cus_123",
                "subscription": "sub_123",
                "amount_due": 4999,
                "amount_remaining": 4999,
                "currency": "usd",
                "status": "open",
                "status_transitions": {},
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
            return {
                "id": "sub_123",
                "customer": "cus_123",
                "metadata": {},
            }

    fake_client = _FakeTableClient()
    fake_client.responses["subscriptions"] = [
        {
            "id": "row-1",
            "user_id": "user-1",
            "stripe_customer_id": "cus_123",
            "stripe_sub_id": "sub_123",
        }
    ]

    monkeypatch.setattr(stripe_service.stripe, "Webhook", FakeStripeWebhook)
    monkeypatch.setattr(stripe_service.stripe, "Subscription", FakeSubscription)
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    result = stripe_service.handle_webhook_event(json.dumps({"anything": True}), "sig")

    assert result["received"] is True
    assert result["event_type"] == "invoice.payment_failed"
    assert fake_client.last_query_by_name["payments"].last_payload["status"] == "failed"
    assert (
        fake_client.last_query_by_name["payments"].last_payload["amount_cents"] == 4999
    )


def test_handle_webhook_event_cancels_subscription_without_price_id(monkeypatch):
    fake_event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_123",
                "status": "canceled",
                "current_period_end": 1710000000,
            }
        },
    }

    class FakeStripeWebhook:
        @staticmethod
        def construct_event(*args, **kwargs):
            return fake_event

    fake_client = _FakeTableClient()
    fake_client.responses["subscriptions"] = [
        {
            "id": "row-1",
            "user_id": "user-1",
            "stripe_customer_id": "cus_123",
            "stripe_sub_id": "sub_123",
            "plan_id": "plan-core",
            "billing_interval": "monthly",
            "status": "active",
        }
    ]

    monkeypatch.setattr(stripe_service.stripe, "Webhook", FakeStripeWebhook)
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    result = stripe_service.handle_webhook_event(json.dumps({"anything": True}), "sig")

    assert result["received"] is True
    assert result["event_type"] == "customer.subscription.deleted"
    assert (
        fake_client.last_query_by_name["subscriptions"].last_payload["status"]
        == "cancelled"
    )
    assert (
        fake_client.last_query_by_name["subscriptions"].last_payload[
            "current_period_end"
        ]
        == "2024-03-09T16:00:00+00:00"
    )


def test_create_checkout_session_uses_env_price_fallback(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-core",
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": None,
            "stripe_yearly_price_id": None,
            "is_active": True,
        }
    ]
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
            return type(
                "Session", (), {"url": "https://checkout.test/session", "id": "cs_test"}
            )()

    monkeypatch.setattr(stripe_service.stripe.checkout, "Session", FakeCheckoutSession)

    result = stripe_service.create_checkout_session(
        user_id="user-1",
        email="user@example.com",
        plan_name="core",
        billing_interval="monthly",
    )

    assert result["session_id"] == "cs_test"
    assert captured["line_items"][0]["price"] == "price_env_monthly"


def test_change_subscription_plan_uses_checkout_for_foundation_users(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-core",
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": "price_monthly",
            "stripe_yearly_price_id": "price_yearly",
            "is_active": True,
        }
    ]
    fake_client.responses["subscriptions"] = [
        {
            "id": "sub-row-1",
            "user_id": "user-1",
            "status": "active",
            "billing_interval": "free",
            "plan_id": "plan-foundation",
            "plans": {"name": "foundation"},
        }
    ]

    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")

    captured = {}

    class FakeCheckoutSession:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return type(
                "Session",
                (),
                {"url": "https://checkout.test/session", "id": "cs_test"},
            )()

    monkeypatch.setattr(stripe_service.stripe.checkout, "Session", FakeCheckoutSession)

    result = stripe_service.change_subscription_plan(
        user_id="user-1",
        email="user@example.com",
        plan_name="core",
        billing_interval="yearly",
    )

    assert result["kind"] == "checkout"
    assert result["checkout_url"] == "https://checkout.test/session"
    assert result["session_id"] == "cs_test"
    assert captured["customer_email"] == "user@example.com"
    assert captured["line_items"][0]["price"] == "price_yearly"
    assert captured["metadata"]["plan_name"] == "core"
    assert captured["metadata"]["billing_interval"] == "yearly"


def test_change_subscription_plan_upgrades_paid_subscription_via_portal(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-core",
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": "price_monthly",
            "stripe_yearly_price_id": "price_yearly",
            "is_active": True,
        }
    ]
    fake_client.responses["subscriptions"] = [
        {
            "id": "sub-row-1",
            "user_id": "user-1",
            "status": "active",
            "billing_interval": "monthly",
            "plan_id": "plan-core",
            "stripe_customer_id": "cus_123",
            "stripe_sub_id": "sub_123",
            "plans": {"name": "core"},
        }
    ]

    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")

    captured = {}

    class FakePortalSession:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return type(
                "Session",
                (),
                {"url": "https://billing.test/session", "id": "bps_test"},
            )()

    monkeypatch.setattr(
        stripe_service.stripe.billing_portal, "Session", FakePortalSession
    )

    result = stripe_service.change_subscription_plan(
        user_id="user-1",
        email="user@example.com",
        plan_name="core",
        billing_interval="yearly",
    )

    assert result["kind"] == "checkout"
    assert result["checkout_url"] == "https://billing.test/session"
    assert result["session_id"] == "bps_test"
    assert captured["customer"] == "cus_123"
    assert captured["flow_data"]["type"] == "subscription_update"
    assert captured["flow_data"]["subscription_update"]["subscription"] == "sub_123"


def test_change_subscription_plan_allows_yearly_to_monthly_for_same_plan(
    monkeypatch,
):
    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-inner",
            "name": "inner_circle",
            "display_name": "Inner Circle",
            "stripe_monthly_price_id": "price_inner_monthly",
            "stripe_yearly_price_id": "price_inner_yearly",
            "is_active": True,
        }
    ]
    fake_client.responses["subscriptions"] = [
        {
            "id": "sub-row-1",
            "user_id": "user-1",
            "status": "active",
            "billing_interval": "yearly",
            "plan_id": "plan-inner",
            "stripe_customer_id": "cus_123",
            "stripe_sub_id": "sub_123",
            "plans": {"name": "inner_circle"},
        }
    ]

    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    captured = {}

    class FakePortalSession:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return type(
                "Session",
                (),
                {"url": "https://billing.test/session", "id": "bps_test"},
            )()

    monkeypatch.setattr(
        stripe_service.stripe.billing_portal, "Session", FakePortalSession
    )

    result = stripe_service.change_subscription_plan(
        user_id="user-1",
        email="user@example.com",
        plan_name="inner_circle",
        billing_interval="monthly",
    )

    assert result["kind"] == "checkout"
    assert result["checkout_url"] == "https://billing.test/session"
    assert result["plan"]["name"] == "inner_circle"
    assert captured["flow_data"]["type"] == "subscription_update"
    assert captured["flow_data"]["subscription_update"]["subscription"] == "sub_123"


def test_change_subscription_plan_handles_disabled_portal_updates(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-core",
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": "price_monthly",
            "stripe_yearly_price_id": "price_yearly",
            "is_active": True,
        }
    ]
    fake_client.responses["subscriptions"] = [
        {
            "id": "sub-row-1",
            "user_id": "user-1",
            "status": "active",
            "billing_interval": "monthly",
            "plan_id": "plan-core",
            "stripe_customer_id": "cus_123",
            "stripe_sub_id": "sub_123",
            "plans": {"name": "core"},
        }
    ]

    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")

    class FakePortalSession:
        @staticmethod
        def create(**kwargs):
            raise stripe_service.stripe.error.InvalidRequestError(
                "This subscription cannot be updated because the subscription "
                "update feature in the portal configuration is disabled.",
                param=None,
            )

    monkeypatch.setattr(
        stripe_service.stripe.billing_portal, "Session", FakePortalSession
    )

    with pytest.raises(stripe_service.HTTPException) as exc:
        stripe_service.change_subscription_plan(
            user_id="user-1",
            email="user@example.com",
            plan_name="core",
            billing_interval="yearly",
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == (
        "Subscription changes are temporarily unavailable. Please try again later."
    )
    assert "portal configuration" not in exc.value.detail


def test_change_subscription_plan_allows_higher_tier_across_intervals(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-inner",
            "name": "inner_circle",
            "display_name": "Inner Circle",
            "stripe_monthly_price_id": "price_inner_monthly",
            "stripe_yearly_price_id": "price_inner_yearly",
            "is_active": True,
        }
    ]
    fake_client.responses["subscriptions"] = [
        {
            "id": "sub-row-1",
            "user_id": "user-1",
            "status": "active",
            "billing_interval": "yearly",
            "plan_id": "plan-core",
            "stripe_customer_id": "cus_123",
            "stripe_sub_id": "sub_123",
            "plans": {"name": "core"},
        }
    ]

    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")

    captured = {}

    class FakePortalSession:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return type(
                "Session",
                (),
                {"url": "https://billing.test/session", "id": "bps_test"},
            )()

    monkeypatch.setattr(
        stripe_service.stripe.billing_portal, "Session", FakePortalSession
    )

    result = stripe_service.change_subscription_plan(
        user_id="user-1",
        email="user@example.com",
        plan_name="inner_circle",
        billing_interval="monthly",
    )

    assert result["kind"] == "checkout"
    assert result["checkout_url"] == "https://billing.test/session"
    assert captured["customer"] == "cus_123"
    assert captured["flow_data"]["type"] == "subscription_update"


def test_change_subscription_plan_rejects_downgrades(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-core",
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": "price_monthly",
            "stripe_yearly_price_id": "price_yearly",
            "is_active": True,
        }
    ]
    fake_client.responses["subscriptions"] = [
        {
            "id": "sub-row-1",
            "user_id": "user-1",
            "status": "active",
            "billing_interval": "yearly",
            "plan_id": "plan-inner",
            "stripe_customer_id": "cus_123",
            "stripe_sub_id": "sub_123",
            "plans": {"name": "inner_circle"},
        }
    ]

    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")

    class FakeSubscription:
        @staticmethod
        def retrieve(subscription_id):
            raise AssertionError("Stripe should not be called for a downgrade")

        @staticmethod
        def modify(subscription_id, **kwargs):
            raise AssertionError("Stripe should not be called for a downgrade")

    monkeypatch.setattr(stripe_service.stripe, "Subscription", FakeSubscription)

    with pytest.raises(stripe_service.HTTPException) as exc:
        stripe_service.change_subscription_plan(
            user_id="user-1",
            email="user@example.com",
            plan_name="core",
            billing_interval="monthly",
        )

    assert exc.value.status_code == 409
    assert "Downgrades" in exc.value.detail


def test_change_subscription_plan_rejects_same_tier_same_interval(monkeypatch):
    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-core",
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": "price_monthly",
            "stripe_yearly_price_id": "price_yearly",
            "is_active": True,
        }
    ]
    fake_client.responses["subscriptions"] = [
        {
            "id": "sub-row-1",
            "user_id": "user-1",
            "status": "active",
            "billing_interval": "monthly",
            "plan_id": "plan-core",
            "stripe_customer_id": "cus_123",
            "stripe_sub_id": "sub_123",
            "plans": {"name": "core"},
        }
    ]

    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")

    class FakeSubscription:
        @staticmethod
        def retrieve(subscription_id):
            raise AssertionError("Stripe should not be called for a no-op change")

        @staticmethod
        def modify(subscription_id, **kwargs):
            raise AssertionError("Stripe should not be called for a no-op change")

    monkeypatch.setattr(stripe_service.stripe, "Subscription", FakeSubscription)

    with pytest.raises(stripe_service.HTTPException) as exc:
        stripe_service.change_subscription_plan(
            user_id="user-1",
            email="user@example.com",
            plan_name="core",
            billing_interval="monthly",
        )

    assert exc.value.status_code == 409
    assert "already active" in exc.value.detail


def test_handle_webhook_event_updates_subscription_and_logs_invoice_payment(
    monkeypatch,
):
    events = [
        {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_123",
                    "status": "active",
                    "customer": "cus_123",
                    "current_period_end": 1715184000,
                    "items": {
                        "data": [
                            {
                                "price": {
                                    "id": "price_yearly",
                                    "recurring": {"interval": "year"},
                                }
                            }
                        ]
                    },
                    "metadata": {"user_id": "user-1"},
                }
            },
        },
        {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_123",
                    "customer": "cus_123",
                    "subscription": "sub_123",
                    "amount_paid": 9999,
                    "currency": "usd",
                    "status": "paid",
                    "status_transitions": {"paid_at": 1715184000},
                }
            },
        },
    ]

    class FakeStripeWebhook:
        @staticmethod
        def construct_event(*args, **kwargs):
            return events.pop(0)

    class FakeSubscription:
        @staticmethod
        def retrieve(subscription_id):
            assert subscription_id == "sub_123"
            return {
                "id": "sub_123",
                "customer": "cus_123",
                "metadata": {"user_id": "user-1"},
            }

    fake_client = _FakeTableClient()
    fake_client.responses["plans"] = [
        {
            "id": "plan-core",
            "name": "core",
            "display_name": "Core",
            "stripe_monthly_price_id": "price_monthly",
            "stripe_yearly_price_id": "price_yearly",
            "is_active": True,
        }
    ]
    fake_client.responses["subscriptions"] = [
        {
            "id": "row-1",
            "user_id": "user-1",
            "stripe_customer_id": "cus_123",
            "stripe_sub_id": "sub_123",
        }
    ]

    monkeypatch.setattr(stripe_service.stripe, "Webhook", FakeStripeWebhook)
    monkeypatch.setattr(stripe_service.stripe, "Subscription", FakeSubscription)
    monkeypatch.setattr(stripe_service, "supabase_admin", fake_client)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    updated_result = stripe_service.handle_webhook_event(
        json.dumps({"anything": True}), "sig"
    )
    subscription_update_query = fake_client.last_query_by_name["subscriptions"]
    payment_result = stripe_service.handle_webhook_event(
        json.dumps({"anything": True}), "sig"
    )

    assert updated_result["received"] is True
    assert updated_result["event_type"] == "customer.subscription.updated"
    assert payment_result["received"] is True
    assert payment_result["event_type"] == "invoice.paid"
    assert subscription_update_query.last_payload["plan_id"] == "plan-core"
    assert subscription_update_query.last_payload["billing_interval"] == "yearly"
    assert (
        fake_client.last_query_by_name["payments"].last_payload["user_id"] == "user-1"
    )
    assert fake_client.last_query_by_name["payments"].last_payload["status"] == "paid"
