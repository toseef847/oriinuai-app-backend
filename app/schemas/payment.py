from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


BillingInterval = Literal["monthly", "yearly"]
CheckoutPlanName = Literal["core", "inner_circle"]


class CreateCheckoutSessionRequest(BaseModel):
    plan_name: CheckoutPlanName
    billing_interval: BillingInterval


class CreateCheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


class CreateUpgradeRequest(BaseModel):
    plan_name: CheckoutPlanName
    billing_interval: BillingInterval


class UpgradeCheckoutResponse(CreateCheckoutSessionResponse):
    kind: Literal["checkout"] = "checkout"


class UpgradeSubscriptionUpdatedResponse(BaseModel):
    kind: Literal["subscription_updated"] = "subscription_updated"
    stripe_subscription_id: str
    status: str
    plan_name: CheckoutPlanName
    billing_interval: BillingInterval
    current_period_end: str | None = None


UpgradePaymentResponse = Annotated[
    Union[UpgradeCheckoutResponse, UpgradeSubscriptionUpdatedResponse],
    Field(discriminator="kind"),
]


class CreatePortalSessionResponse(BaseModel):
    portal_url: str


class StripeWebhookResponse(BaseModel):
    received: bool
    event_type: str
