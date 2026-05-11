from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import stripe
from fastapi import HTTPException, status

from app.core.config import settings
from app.db.supabase import supabase_admin


stripe.api_key = settings.STRIPE_SECRET_KEY


def _ensure_stripe_configured() -> None:
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured.",
        )


def _frontend_url(path: str) -> str:
    base_url = settings.FRONTEND_URL.rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url}{normalized_path}"


def _checkout_success_url() -> str:
    return f"{_frontend_url(settings.STRIPE_CHECKOUT_SUCCESS_PATH)}?session_id={{CHECKOUT_SESSION_ID}}"


def _checkout_cancel_url() -> str:
    return _frontend_url(settings.STRIPE_CHECKOUT_CANCEL_PATH)


def _portal_return_url() -> str:
    return _frontend_url(settings.STRIPE_PORTAL_RETURN_PATH)


def _get_plan_record(plan_name: str) -> dict[str, Any]:
    result = (
        supabase_admin.table("plans")
        .select("*")
        .eq("name", plan_name)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_name}' is not available.",
        )
    return result.data


def _billing_interval_field(billing_interval: str) -> str:
    if billing_interval == "monthly":
        return "stripe_monthly_price_id"
    if billing_interval == "yearly":
        return "stripe_yearly_price_id"
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Billing interval must be 'monthly' or 'yearly'.",
    )


def _env_price_id(plan_name: str, billing_interval: str) -> str | None:
    if plan_name == "core" and billing_interval == "monthly":
        return settings.STRIPE_CORE_MONTHLY_PRICE_ID or None
    if plan_name == "core" and billing_interval == "yearly":
        return settings.STRIPE_CORE_YEARLY_PRICE_ID or None
    if plan_name == "inner_circle" and billing_interval == "monthly":
        return settings.STRIPE_INNER_MONTHLY_PRICE_ID or None
    if plan_name == "inner_circle" and billing_interval == "yearly":
        return settings.STRIPE_INNER_YEARLY_PRICE_ID or None
    return None


def _get_price_id(plan_name: str, billing_interval: str) -> tuple[dict[str, Any], str]:
    plan = _get_plan_record(plan_name)
    price_field = _billing_interval_field(billing_interval)
    price_id = plan.get(price_field) or _env_price_id(plan_name, billing_interval)
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Plan '{plan_name}' does not have a {billing_interval} Stripe price configured "
                "in the database or environment."
            ),
        )
    return plan, price_id


def _latest_subscription_for_user(user_id: str) -> dict[str, Any] | None:
    result = (
        supabase_admin.table("subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _resolve_customer_id(user_id: str) -> str | None:
    subscription = _latest_subscription_for_user(user_id)
    if subscription and subscription.get("stripe_customer_id"):
        return subscription["stripe_customer_id"]
    return None


def create_checkout_session(
    user_id: str,
    email: str,
    plan_name: str,
    billing_interval: str,
) -> dict[str, Any]:
    _ensure_stripe_configured()
    plan, price_id = _get_price_id(plan_name, billing_interval)

    stripe_customer_id = _resolve_customer_id(user_id)
    session_kwargs: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": _checkout_success_url(),
        "cancel_url": _checkout_cancel_url(),
        "client_reference_id": user_id,
        "metadata": {
            "user_id": user_id,
            "plan_name": plan_name,
            "billing_interval": billing_interval,
        },
        "subscription_data": {
            "metadata": {
                "user_id": user_id,
                "plan_name": plan_name,
                "billing_interval": billing_interval,
            }
        },
    }

    if stripe_customer_id:
        session_kwargs["customer"] = stripe_customer_id
    else:
        session_kwargs["customer_email"] = email

    session = stripe.checkout.Session.create(**session_kwargs)

    return {
        "checkout_url": session.url,
        "session_id": session.id,
        "plan": {
            "id": plan["id"],
            "name": plan["name"],
            "display_name": plan["display_name"],
        },
    }


def create_portal_session(user_id: str) -> dict[str, Any]:
    _ensure_stripe_configured()
    subscription = _latest_subscription_for_user(user_id)

    if not subscription or not subscription.get("stripe_customer_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Stripe customer found for this account.",
        )

    session = stripe.billing_portal.Session.create(
        customer=subscription["stripe_customer_id"],
        return_url=_portal_return_url(),
    )
    return {
        "portal_url": session.url,
        "session_id": session.id,
    }


def _map_subscription_status(stripe_status: str) -> str:
    return {
        "active": "active",
        "trialing": "trialing",
        "past_due": "past_due",
        "unpaid": "past_due",
        "canceled": "cancelled",
        "incomplete": "past_due",
        "incomplete_expired": "cancelled",
    }.get(stripe_status, "active")


def _subscription_price_id(subscription: dict[str, Any]) -> str | None:
    items = subscription.get("items", {}).get("data", [])
    if not items:
        return None
    return items[0].get("price", {}).get("id")


def _subscription_billing_interval(subscription: dict[str, Any]) -> str | None:
    items = subscription.get("items", {}).get("data", [])
    if not items:
        return None
    return items[0].get("price", {}).get("recurring", {}).get("interval")


def _find_plan_by_price_id(price_id: str) -> dict[str, Any]:
    monthly_result = (
        supabase_admin.table("plans")
        .select("*")
        .eq("stripe_monthly_price_id", price_id)
        .maybe_single()
        .execute()
    )
    if monthly_result.data:
        return monthly_result.data

    yearly_result = (
        supabase_admin.table("plans")
        .select("*")
        .eq("stripe_yearly_price_id", price_id)
        .maybe_single()
        .execute()
    )
    if yearly_result.data:
        return yearly_result.data

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No plan matches the Stripe price on this subscription.",
    )


def _upsert_subscription_row(subscription: dict[str, Any]) -> dict[str, Any]:
    user_id = subscription.get("metadata", {}).get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe subscription is missing the user_id metadata.",
        )

    price_id = _subscription_price_id(subscription)
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe subscription is missing a price reference.",
        )

    plan = _find_plan_by_price_id(price_id)
    billing_interval = _subscription_billing_interval(subscription)
    mapped_status = _map_subscription_status(subscription.get("status", "active"))
    current_period_end = subscription.get("current_period_end")

    payload = {
        "user_id": user_id,
        "plan_id": plan["id"],
        "billing_interval": billing_interval,
        "stripe_customer_id": subscription.get("customer"),
        "stripe_sub_id": subscription.get("id"),
        "status": mapped_status,
        "current_period_end": (
            datetime.fromtimestamp(current_period_end, tz=timezone.utc)
            if current_period_end
            else None
        ),
    }

    existing = _latest_subscription_for_user(user_id)
    if existing:
        result = (
            supabase_admin.table("subscriptions")
            .update(payload)
            .eq("id", existing["id"])
            .execute()
        )
    else:
        result = supabase_admin.table("subscriptions").insert(payload).execute()

    return result.data[0] if result.data else payload


def _upsert_payment_from_invoice(invoice: dict[str, Any]) -> dict[str, Any]:
    customer_id = invoice.get("customer")
    subscription_id = invoice.get("subscription")
    if not subscription_id or not customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is missing required Stripe subscription references.",
        )

    subscription = stripe.Subscription.retrieve(subscription_id)
    user_id = subscription.get("metadata", {}).get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to resolve user_id for the invoice payment.",
        )

    payment_payload = {
        "user_id": user_id,
        "stripe_invoice_id": invoice.get("id"),
        "stripe_customer_id": customer_id,
        "amount_cents": invoice.get("amount_paid"),
        "currency": invoice.get("currency", "usd"),
        "status": invoice.get("status"),
        "paid_at": (
            datetime.fromtimestamp(
                invoice.get("status_transitions", {}).get("paid_at"),
                tz=timezone.utc,
            )
            if invoice.get("status_transitions", {}).get("paid_at")
            else None
        ),
    }

    result = (
        supabase_admin.table("payments")
        .upsert(payment_payload, on_conflict="stripe_invoice_id")
        .execute()
    )
    return result.data[0] if result.data else payment_payload


def handle_webhook_event(payload: str, signature: str) -> dict[str, Any]:
    _ensure_stripe_configured()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook signing secret is not configured.",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook payload.",
        ) from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook signature.",
        ) from exc

    event_type = event["type"]
    event_object = event["data"]["object"]

    if event_type == "checkout.session.completed":
        subscription_id = event_object.get("subscription")
        if subscription_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            _upsert_subscription_row(subscription)
    elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        _upsert_subscription_row(event_object)
    elif event_type == "invoice.paid":
        _upsert_payment_from_invoice(event_object)

    return {"received": True, "event_type": event_type}
