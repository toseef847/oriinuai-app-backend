from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from app.core.security import get_current_profile
from app.schemas.payment import (
    CreateCheckoutSessionRequest,
    CreateUpgradeRequest,
)
from app.services.payments.stripe_service import (
    create_checkout_session,
    create_portal_session,
    change_subscription_plan,
    handle_webhook_event,
)
from app.utils.response import api_success

router = APIRouter()


@router.post("/checkout", response_model=None)
async def checkout(
    payload: CreateCheckoutSessionRequest,
    profile: dict = Depends(get_current_profile),
):
    email = profile.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User email is required to create a checkout session.",
        )

    data = create_checkout_session(
        user_id=profile["id"],
        email=email,
        plan_name=payload.plan_name,
        billing_interval=payload.billing_interval,
    )
    return api_success(data=data, message="Checkout session created")


@router.post("/upgrade", response_model=None)
async def upgrade(
    payload: CreateUpgradeRequest,
    profile: dict = Depends(get_current_profile),
):
    email = profile.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User email is required to upgrade a subscription.",
        )

    data = change_subscription_plan(
        user_id=profile["id"],
        email=email,
        plan_name=payload.plan_name,
        billing_interval=payload.billing_interval,
    )
    return api_success(data=data, message="Subscription plan update initiated")


@router.get("/portal", response_model=None)
async def portal(profile: dict = Depends(get_current_profile)):
    data = create_portal_session(profile["id"])
    return api_success(data=data, message="Portal session created")


@router.post("/webhook", response_model=None)
async def webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
):
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header.",
        )

    payload = (await request.body()).decode("utf-8")
    data = handle_webhook_event(payload, stripe_signature)
    return api_success(data=data, message="Webhook processed")
