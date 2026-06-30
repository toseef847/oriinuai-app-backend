from app.api.v1.endpoints.admin.transactions import _matches_transaction_search


def test_transaction_search_uses_payment_plan_snapshot() -> None:
    profile = {
        "id": "user-1",
        "full_name": "Toseef Hassan",
        "email": "toseef@example.com",
    }
    old_payment = {
        "id": "payment-core",
        "user_id": "user-1",
        "package_name": "Core",
        "billing_interval": "monthly",
    }
    upgraded_payment = {
        "id": "payment-inner",
        "user_id": "user-1",
        "package_name": "Inner Circle",
        "billing_interval": "yearly",
    }

    assert _matches_transaction_search(old_payment, profile, "core") is True
    assert _matches_transaction_search(old_payment, profile, "inner circle") is False
    assert _matches_transaction_search(upgraded_payment, profile, "inner circle") is True

