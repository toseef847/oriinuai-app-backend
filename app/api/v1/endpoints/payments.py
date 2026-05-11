from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.security import get_current_profile
from app.schemas.payment import (
    CreateCheckoutSessionRequest,
    CreateCheckoutSessionResponse,
    CreatePortalSessionResponse,
    StripeWebhookResponse,
)
from app.services.payments.stripe_service import (
    create_checkout_session,
    create_portal_session,
    handle_webhook_event,
)

router = APIRouter()


@router.post("/checkout", response_model=CreateCheckoutSessionResponse)
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

    result = create_checkout_session(
        user_id=profile["id"],
        email=email,
        plan_name=payload.plan_name,
        billing_interval=payload.billing_interval,
    )
    return result


@router.get("/portal", response_model=CreatePortalSessionResponse)
async def portal(profile: dict = Depends(get_current_profile)):
    return create_portal_session(profile["id"])


@router.post("/webhook", response_model=StripeWebhookResponse)
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
    return handle_webhook_event(payload, stripe_signature)
