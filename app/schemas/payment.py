from pydantic import BaseModel
from typing import Literal


BillingInterval = Literal["monthly", "yearly"]
CheckoutPlanName = Literal["core", "inner_circle"]


class CreateCheckoutSessionRequest(BaseModel):
    plan_name: CheckoutPlanName
    billing_interval: BillingInterval


class CreateCheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


class CreatePortalSessionResponse(BaseModel):
    portal_url: str


class StripeWebhookResponse(BaseModel):
    received: bool
    event_type: str
