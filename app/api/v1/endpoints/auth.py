from fastapi import APIRouter, Depends, status
from postgrest import AsyncPostgrestClient

from app.core.security import get_auth_user_status, get_current_profile, get_user_db
from app.utils.response import api_success
from app.services.auth.auth_service import (
    forgot_password,
    login_user,
    refresh_token as refresh_token_service,
    resend_email_verification,
    reset_password,
    signup_user,
    verify_email_token,
    verify_forgot_password_token,
)
from app.schemas.auth import (
    EmailRequest,
    LoginRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    SignUpRequest,
    VerifyEmailRequest,
    VerifyForgotPasswordRequest,
)
from app.services.auth.rate_limit_service import (
    clear_auth_rate_limit,
    enforce_auth_rate_limit,
)

router = APIRouter()


@router.post("/signup")
async def signup(payload: SignUpRequest):
    await enforce_auth_rate_limit("user-signup", payload.email)
    data = signup_user(payload.email, payload.password, payload.full_name)
    return api_success(
        data=data,
        message="Registration successful. Please check your email for verification.",
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/login")
async def login(payload: LoginRequest):
    lease = await enforce_auth_rate_limit("user-login", payload.email)
    data = login_user(payload.email, payload.password)
    await clear_auth_rate_limit(lease)
    return api_success(data=data, message="Login successful")


@router.post("/refresh")
async def refresh(payload: RefreshTokenRequest):
    lease = await enforce_auth_rate_limit(
        "user-refresh",
        payload.refresh_token,
        normalize_identity=False,
    )
    data = refresh_token_service(payload.refresh_token)
    await clear_auth_rate_limit(lease)
    return api_success(data=data, message="Token refreshed")


@router.post("/resend-email-verification")
async def resend_email_verification_endpoint(payload: EmailRequest):
    await enforce_auth_rate_limit("user-resend-verification", payload.email)
    data = resend_email_verification(payload.email)
    return api_success(data=data, message="Verification email resent")


@router.post("/forgot-password")
async def forgot_password_endpoint(payload: EmailRequest):
    await enforce_auth_rate_limit("user-forgot-password", payload.email)
    data = forgot_password(payload.email)
    return api_success(data=data, message="Password reset email sent")


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest):
    lease = await enforce_auth_rate_limit("user-verify-email", payload.email)
    data = verify_email_token(payload.email, payload.token)
    await clear_auth_rate_limit(lease)
    return api_success(data=data, message="Email verified successfully")


@router.post("/verify-forgot-password")
async def verify_forgot_password(payload: VerifyForgotPasswordRequest):
    lease = await enforce_auth_rate_limit("user-verify-recovery", payload.email)
    data = verify_forgot_password_token(payload.email, payload.token)
    await clear_auth_rate_limit(lease)
    return api_success(data=data, message="OTP verified")


@router.post("/reset-password")
async def reset_password_endpoint(payload: ResetPasswordRequest):
    lease = await enforce_auth_rate_limit(
        "user-reset-password",
        payload.access_token,
        normalize_identity=False,
    )
    data = reset_password(payload.access_token, payload.password)
    await clear_auth_rate_limit(lease)
    return api_success(data=data, message="Password has been reset successfully")


@router.get("/me")
async def get_current_user(
    profile: dict = Depends(get_current_profile),
    auth_status: dict = Depends(get_auth_user_status),
    client: AsyncPostgrestClient = Depends(get_user_db),
):
    sub_res = (
        client.table("subscriptions")
        .select("*, plans(*)")
        .eq("user_id", profile["id"])
        .eq("status", "active")
        .limit(1)
    )
    sub_res = await sub_res.execute()

    subscription = None
    if sub_res and sub_res.data and len(sub_res.data) > 0:
        subscription = sub_res.data[0]

    profile.update(auth_status)
    return api_success(
        data={
            "profile": profile,
            "subscription": subscription,
        },
        message="User profile retrieved",
    )
