from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import stripe
from fastapi import HTTPException, status

from app.core.config import settings
from app.db.supabase import supabase_admin


stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


PLAN_PRIORITY = {
    "foundation": 0,
    "core": 1,
    "inner_circle": 2,
}


def _create_billing_portal_session(**kwargs: Any) -> Any:
    try:
        return stripe.billing_portal.Session.create(**kwargs)
    except stripe.error.InvalidRequestError as exc:
        logger.exception("Stripe rejected the billing portal session request")
        if (
            "subscription update feature in the portal configuration is disabled"
            in str(exc).lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Subscription changes are temporarily unavailable. "
                    "Please try again later."
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create a billing portal session.",
        ) from exc
    except stripe.error.StripeError as exc:
        logger.exception("Stripe billing portal request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create a billing portal session.",
        ) from exc


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
    res = (
        supabase_admin.table("plans")
        .select("*")
        .eq("name", plan_name)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not res or not res.data or len(res.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_name}' is not available.",
        )
    return res.data[0]


def _get_plan_record_by_id(plan_id: str) -> dict[str, Any]:
    res = supabase_admin.table("plans").select("*").eq("id", plan_id).limit(1).execute()
    if not res or not res.data or len(res.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan with id '{plan_id}' is not available.",
        )
    return res.data[0]


def _plan_priority(plan_name: str) -> int:
    if plan_name not in PLAN_PRIORITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown plan '{plan_name}'.",
        )
    return PLAN_PRIORITY[plan_name]


def _subscription_plan_name(subscription: dict[str, Any]) -> str:
    plan_details = subscription.get("plans")
    if isinstance(plan_details, dict):
        name = plan_details.get("name")
        if isinstance(name, str):
            return name

    plan_id = subscription.get("plan_id")
    if isinstance(plan_id, str):
        return _get_plan_record_by_id(plan_id)["name"]

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Subscription is missing a plan reference.",
    )


def _is_checkout_eligible_subscription(subscription: dict[str, Any] | None) -> bool:
    if not subscription:
        return True
    return _subscription_plan_name(
        subscription
    ) == "foundation" and not subscription.get("stripe_sub_id")


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


def _stripe_object_id(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        candidate = value.get("id")
        return candidate if isinstance(candidate, str) else None
    return None


def _timestamp_to_iso(value: Any) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _latest_subscription_for_customer(stripe_customer_id: str) -> dict[str, Any] | None:
    result = (
        supabase_admin.table("subscriptions")
        .select("*")
        .eq("stripe_customer_id", stripe_customer_id)
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _latest_subscription_for_stripe_id(stripe_sub_id: str) -> dict[str, Any] | None:
    result = (
        supabase_admin.table("subscriptions")
        .select("*")
        .eq("stripe_sub_id", stripe_sub_id)
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


def _active_subscription_for_user(user_id: str) -> dict[str, Any] | None:
    result = (
        supabase_admin.table("subscriptions")
        .select("*, plans(name, display_name)")
        .eq("user_id", user_id)
        .in_("status", ["active", "trialing", "past_due"])
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def create_checkout_session(
    user_id: str,
    email: str,
    plan_name: str,
    billing_interval: str,
) -> dict[str, Any]:
    _ensure_stripe_configured()
    plan, price_id = _get_price_id(plan_name, billing_interval)

    existing_subscription = _active_subscription_for_user(user_id)
    if not _is_checkout_eligible_subscription(existing_subscription):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This account already has an active subscription. "
                "Use the billing portal to manage or change the plan."
            ),
        )

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


def _subscription_item_id(subscription: dict[str, Any]) -> str:
    items = subscription.get("items", {}).get("data", [])
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe subscription is missing a subscription item.",
        )
    item_id = items[0].get("id")
    if not isinstance(item_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe subscription item is missing an id.",
        )
    return item_id


def _can_change_subscription_plan(
    current_plan_name: str,
    current_billing_interval: str | None,
    target_plan_name: str,
    target_billing_interval: str,
) -> bool:
    current_rank = _plan_priority(current_plan_name)
    target_rank = _plan_priority(target_plan_name)

    if target_rank > current_rank:
        return True

    if target_rank < current_rank:
        return False

    # Stripe Customer Portal handles billing-cycle changes and applies the
    # configured proration/scheduling behavior. Both monthly -> yearly and
    # yearly -> monthly are valid when the plan tier itself is unchanged.
    return current_billing_interval != target_billing_interval


def change_subscription_plan(
    user_id: str,
    email: str,
    plan_name: str,
    billing_interval: str,
) -> dict[str, Any]:
    _ensure_stripe_configured()
    target_plan, price_id = _get_price_id(plan_name, billing_interval)

    current_subscription = _active_subscription_for_user(user_id)
    if not current_subscription:
        checkout_result = create_checkout_session(
            user_id=user_id,
            email=email,
            plan_name=plan_name,
            billing_interval=billing_interval,
        )
        return {"kind": "checkout", **checkout_result}

    if _is_checkout_eligible_subscription(current_subscription):
        checkout_result = create_checkout_session(
            user_id=user_id,
            email=email,
            plan_name=plan_name,
            billing_interval=billing_interval,
        )
        return {"kind": "checkout", **checkout_result}

    if current_subscription.get("status") == "past_due":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This subscription is past due. "
                "Please update billing details in the portal before upgrading."
            ),
        )

    stripe_subscription_id = current_subscription.get("stripe_sub_id")
    if not isinstance(stripe_subscription_id, str) or not stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This subscription is not linked to Stripe and cannot be upgraded automatically."
            ),
        )

    current_plan_name = _subscription_plan_name(current_subscription)
    current_billing_interval = current_subscription.get("billing_interval")
    if not _can_change_subscription_plan(
        current_plan_name=current_plan_name,
        current_billing_interval=current_billing_interval,
        target_plan_name=plan_name,
        target_billing_interval=billing_interval,
    ):
        if _plan_priority(plan_name) < _plan_priority(current_plan_name):
            detail = "Downgrades must be handled in the billing portal."
        elif (
            current_plan_name == plan_name
            and current_billing_interval == billing_interval
        ):
            detail = "This plan is already active."
        else:
            detail = "This plan change is not allowed."

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )

    # Redirect to the Customer Portal so Stripe can confirm the change and
    # apply the configured proration or end-of-period behavior.
    session = _create_billing_portal_session(
        customer=current_subscription["stripe_customer_id"],
        return_url=_portal_return_url(),
        flow_data={
            "type": "subscription_update",
            "subscription_update": {
                "subscription": stripe_subscription_id,
            },
        },
    )

    return {
        "kind": "checkout",
        "checkout_url": session.url,
        "session_id": session.id,
        "plan": {
            "id": target_plan["id"],
            "name": target_plan["name"],
            "display_name": target_plan["display_name"],
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

    session = _create_billing_portal_session(
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
    stripe_interval = items[0].get("price", {}).get("recurring", {}).get("interval")
    if stripe_interval in {"monthly", "yearly", "free"}:
        return stripe_interval
    if stripe_interval == "month":
        return "monthly"
    if stripe_interval == "year":
        return "yearly"
    if stripe_interval is None:
        return None

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported Stripe billing interval: {stripe_interval}.",
    )


def _retrieved_invoice_from_reference(invoice_reference: Any) -> dict[str, Any]:
    if (
        isinstance(invoice_reference, dict)
        and invoice_reference.get("object") == "invoice"
    ):
        return invoice_reference

    invoice_id = _stripe_object_id(invoice_reference)
    if not invoice_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice payment event is missing an invoice reference.",
        )

    invoice = stripe.Invoice.retrieve(invoice_id)
    if not isinstance(invoice, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to load Stripe invoice for the payment event.",
        )
    return invoice


def _invoice_subscription_metadata(invoice: dict[str, Any]) -> dict[str, Any]:
    subscription_details = invoice.get("subscription_details")
    if isinstance(subscription_details, dict):
        metadata = subscription_details.get("metadata")
        if isinstance(metadata, dict):
            return metadata

    parent = invoice.get("parent")
    if isinstance(parent, dict):
        parent_subscription_details = parent.get("subscription_details")
        if isinstance(parent_subscription_details, dict):
            metadata = parent_subscription_details.get("metadata")
            if isinstance(metadata, dict):
                return metadata

    return {}


def _find_plan_by_price_id(price_id: str) -> dict[str, Any]:
    res = (
        supabase_admin.table("plans")
        .select("*")
        .or_(
            "stripe_monthly_price_id.eq.{},stripe_yearly_price_id.eq.{}".format(
                price_id, price_id
            )
        )
        .limit(1)
        .execute()
    )
    if res and res.data and len(res.data) > 0:
        return res.data[0]

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No plan matches the Stripe price on this subscription.",
    )


def _upsert_subscription_row(
    subscription: Any, user_id_override: str | None = None
) -> dict[str, Any]:
    # Handle both Stripe objects and dicts
    sub_data = (
        subscription
        if isinstance(subscription, dict)
        else getattr(subscription, "to_dict", lambda: {})()
    )
    if not sub_data and hasattr(subscription, "id"):
        # Fallback for Stripe objects if to_dict failed or returned empty
        sub_data = {
            "id": getattr(subscription, "id", None),
            "customer": getattr(subscription, "customer", None),
            "status": getattr(subscription, "status", None),
            "current_period_end": getattr(subscription, "current_period_end", None),
            "metadata": getattr(subscription, "metadata", {}),
            "items": getattr(subscription, "items", {}),
        }

    metadata = sub_data.get("metadata") or {}
    user_id = user_id_override or metadata.get("user_id")
    stripe_customer_id = _stripe_object_id(sub_data.get("customer"))
    stripe_sub_id = sub_data.get("id")

    # Resolve user_id if missing
    if not user_id:
        if stripe_sub_id:
            existing_by_sub = _latest_subscription_for_stripe_id(stripe_sub_id)
            if existing_by_sub:
                user_id = existing_by_sub.get("user_id")

        if not user_id and stripe_customer_id:
            existing_by_customer = _latest_subscription_for_customer(stripe_customer_id)
            if existing_by_customer:
                user_id = existing_by_customer.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe subscription is missing the user_id metadata.",
        )

    # Prepare payload with available fields
    payload: dict[str, Any] = {"user_id": user_id}

    price_id = _subscription_price_id(sub_data)
    if price_id:
        plan = _find_plan_by_price_id(price_id)
        payload["plan_id"] = plan["id"]

        billing_interval = _subscription_billing_interval(sub_data)
        if billing_interval:
            payload["billing_interval"] = billing_interval

    if sub_data.get("status"):
        payload["status"] = _map_subscription_status(sub_data["status"])

    if stripe_customer_id:
        payload["stripe_customer_id"] = stripe_customer_id

    if stripe_sub_id:
        payload["stripe_sub_id"] = stripe_sub_id

    current_period_end = sub_data.get("current_period_end")
    current_period_end_iso = _timestamp_to_iso(current_period_end)
    if current_period_end_iso:
        payload["current_period_end"] = current_period_end_iso

    # Find existing record to update
    existing = None
    if stripe_sub_id:
        existing = _latest_subscription_for_stripe_id(stripe_sub_id)
    if not existing:
        existing = _latest_subscription_for_user(user_id)

    if existing:
        result = (
            supabase_admin.table("subscriptions")
            .update(payload)
            .eq("id", existing["id"])
            .execute()
        )
    elif "plan_id" in payload:
        # Only create a new record if we have enough info (plan_id)
        result = supabase_admin.table("subscriptions").insert(payload).execute()
    else:
        # Cannot update (no existing record) and cannot create (no plan_id)
        return payload

    return result.data[0] if result.data else payload


def _cancel_subscription_row(subscription: Any) -> dict[str, Any] | None:
    sub_data = (
        subscription
        if isinstance(subscription, dict)
        else getattr(subscription, "to_dict", lambda: {})()
    )
    metadata = sub_data.get("metadata") or {}
    user_id = metadata.get("user_id")
    stripe_customer_id = _stripe_object_id(sub_data.get("customer"))
    stripe_sub_id = _stripe_object_id(sub_data.get("id"))
    price_id = _subscription_price_id(sub_data)

    existing = None
    if stripe_sub_id:
        existing = _latest_subscription_for_stripe_id(stripe_sub_id)
    if not existing and user_id:
        existing = _latest_subscription_for_user(user_id)
    if not existing and stripe_customer_id:
        existing = _latest_subscription_for_customer(stripe_customer_id)

    if not existing and user_id and price_id:
        return _upsert_subscription_row(subscription)

    if not existing:
        return None

    payload: dict[str, Any] = {"status": "cancelled"}
    current_period_end = sub_data.get("current_period_end")
    if current_period_end:
        payload["current_period_end"] = _timestamp_to_iso(current_period_end)
    if stripe_customer_id:
        payload["stripe_customer_id"] = stripe_customer_id
    if stripe_sub_id:
        payload["stripe_sub_id"] = stripe_sub_id
    if price_id:
        plan = _find_plan_by_price_id(price_id)
        payload["plan_id"] = plan["id"]
        payload["billing_interval"] = _subscription_billing_interval(sub_data)

    result = (
        supabase_admin.table("subscriptions")
        .update(payload)
        .eq("id", existing["id"])
        .execute()
    )
    return result.data[0] if result.data else payload


def _subscription_id_from_invoice(invoice: dict[str, Any]) -> str | None:
    subscription_id = _stripe_object_id(invoice.get("subscription"))
    if subscription_id:
        return subscription_id

    parent = invoice.get("parent")
    if isinstance(parent, dict):
        details = parent.get("subscription_details")
        if isinstance(details, dict):
            return _stripe_object_id(details.get("subscription"))
    return None


def _invoice_subscription_snapshot(
    invoice: dict[str, Any], subscription: dict[str, Any]
) -> dict[str, Any]:
    """Return immutable plan details represented by this specific invoice."""
    lines = invoice.get("lines", {}).get("data", [])
    subscription_id = _subscription_id_from_invoice(invoice)

    matching_lines = []
    for line in lines:
        line_subscription_id = _stripe_object_id(line.get("subscription"))
        if not subscription_id or not line_subscription_id or line_subscription_id == subscription_id:
            matching_lines.append(line)

    # Positive subscription lines represent the purchased plan. Prefer the
    # largest one on prorated upgrade invoices, which can contain credits too.
    candidates = [line for line in matching_lines if (line.get("amount") or 0) > 0]
    selected_line = max(candidates or matching_lines, key=lambda line: line.get("amount") or 0, default={})
    price = selected_line.get("price") or {}
    if not price:
        price = selected_line.get("pricing", {}).get("price_details", {})
    price_id = _stripe_object_id(price) or price.get("price")

    if not price_id:
        price_id = _subscription_price_id(subscription)
    plan = _find_plan_by_price_id(price_id) if price_id else None

    interval = None
    if plan and price_id:
        if price_id == (
            plan.get("stripe_monthly_price_id")
            or _env_price_id(plan.get("name", ""), "monthly")
        ):
            interval = "monthly"
        elif price_id == (
            plan.get("stripe_yearly_price_id")
            or _env_price_id(plan.get("name", ""), "yearly")
        ):
            interval = "yearly"
    recurring = price.get("recurring") if isinstance(price, dict) else None
    if interval is None and isinstance(recurring, dict):
        stripe_interval = recurring.get("interval")
        interval = {"month": "monthly", "year": "yearly"}.get(stripe_interval, stripe_interval)
    if interval not in {"monthly", "yearly"}:
        interval = _subscription_billing_interval(subscription)

    period = selected_line.get("period") or {}
    period_start = _timestamp_to_iso(period.get("start"))
    period_end = _timestamp_to_iso(period.get("end"))
    if not period_end:
        period_end = _timestamp_to_iso(subscription.get("current_period_end"))

    return {
        "stripe_subscription_id": subscription_id,
        "package_name": plan.get("display_name") if plan else None,
        "billing_interval": interval,
        "period_start": period_start,
        "period_end": period_end,
    }


def _resolve_user_id_for_invoice(
    invoice: dict[str, Any], subscription: dict[str, Any] | None
) -> str | None:
    invoice_metadata = _invoice_subscription_metadata(invoice)
    user_id = invoice_metadata.get("user_id")
    if user_id:
        return user_id

    if subscription:
        metadata = subscription.get("metadata") or {}
        user_id = metadata.get("user_id")
        if user_id:
            return user_id

        stripe_sub_id = _stripe_object_id(subscription.get("id"))
        if stripe_sub_id:
            existing_by_subscription = _latest_subscription_for_stripe_id(stripe_sub_id)
            if existing_by_subscription:
                return existing_by_subscription.get("user_id")

        customer_id = _stripe_object_id(subscription.get("customer"))
        if customer_id:
            existing_by_customer = _latest_subscription_for_customer(customer_id)
            if existing_by_customer:
                return existing_by_customer.get("user_id")

    customer_id = _stripe_object_id(invoice.get("customer"))
    if customer_id:
        existing_by_customer = _latest_subscription_for_customer(customer_id)
        if existing_by_customer:
            return existing_by_customer.get("user_id")

    invoice_id = _stripe_object_id(invoice.get("id"))
    if invoice_id:
        refreshed_invoice = _retrieved_invoice_from_reference(invoice_id)
        if refreshed_invoice != invoice:
            return _resolve_user_id_for_invoice(refreshed_invoice, subscription)

    return None


def _upsert_payment_from_invoice(
    invoice: dict[str, Any],
    *,
    status_override: str | None = None,
    amount_cents_override: int | None = None,
) -> dict[str, Any]:
    resolved_invoice = invoice
    customer_id = _stripe_object_id(resolved_invoice.get("customer"))
    subscription_id = _subscription_id_from_invoice(resolved_invoice)

    if not customer_id or not subscription_id:
        invoice_id = _stripe_object_id(resolved_invoice.get("id"))
        if invoice_id:
            refreshed_invoice = _retrieved_invoice_from_reference(invoice_id)
            resolved_invoice = refreshed_invoice
            customer_id = _stripe_object_id(resolved_invoice.get("customer"))
            subscription_id = _subscription_id_from_invoice(resolved_invoice)

    if not subscription_id or not customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is missing required Stripe subscription references.",
        )

    subscription = stripe.Subscription.retrieve(subscription_id)
    user_id = _resolve_user_id_for_invoice(resolved_invoice, subscription)
    if user_id:
        _upsert_subscription_row(subscription, user_id_override=user_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to resolve user_id for the invoice payment.",
        )

    payment_payload = {
        "user_id": user_id,
        "stripe_invoice_id": resolved_invoice.get("id"),
        "stripe_customer_id": customer_id,
        "amount_cents": (
            amount_cents_override
            if amount_cents_override is not None
            else resolved_invoice.get("amount_paid")
        ),
        "currency": resolved_invoice.get("currency", "usd"),
        "status": status_override or resolved_invoice.get("status"),
        "paid_at": _timestamp_to_iso(
            resolved_invoice.get("status_transitions", {}).get("paid_at")
        ),
        **_invoice_subscription_snapshot(resolved_invoice, subscription),
    }

    result = (
        supabase_admin.table("payments")
        .upsert(payment_payload, on_conflict="stripe_invoice_id")
        .execute()
    )
    return result.data[0] if result.data else payment_payload


def _upsert_failed_payment_from_invoice(invoice: dict[str, Any]) -> dict[str, Any]:
    failed_amount = invoice.get("amount_due")
    if failed_amount is None:
        failed_amount = invoice.get("amount_remaining")
    if failed_amount is None:
        failed_amount = invoice.get("amount_paid")

    return _upsert_payment_from_invoice(
        invoice,
        status_override="failed",
        amount_cents_override=failed_amount,
    )


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

    if event_type in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }:
        subscription_id = event_object.get("subscription")
        if subscription_id:
            if isinstance(subscription_id, dict):
                subscription_id = subscription_id.get("id")
            if isinstance(subscription_id, str):
                subscription = stripe.Subscription.retrieve(subscription_id)
                _upsert_subscription_row(subscription)
    elif event_type == "checkout.session.async_payment_failed":
        pass
    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
    }:
        _upsert_subscription_row(event_object)
    elif event_type == "customer.subscription.deleted":
        _cancel_subscription_row(event_object)
    elif event_type in {"invoice.paid", "invoice.payment_succeeded"}:
        _upsert_payment_from_invoice(event_object)
    elif event_type == "invoice_payment.paid":
        invoice = _retrieved_invoice_from_reference(event_object.get("invoice"))
        _upsert_payment_from_invoice(invoice)
    elif event_type == "invoice.payment_failed":
        _upsert_failed_payment_from_invoice(event_object)

    return {"received": True, "event_type": event_type}
