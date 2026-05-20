from fastapi import APIRouter, Depends, status
from app.core.security import get_auth_user_status, get_current_profile
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
from app.db.supabase import supabase_admin

router = APIRouter()


@router.post("/signup")
async def signup(payload: SignUpRequest):
    data = signup_user(payload.email, payload.password, payload.full_name)
    return api_success(
        data=data,
        message="Registration successful. Please check your email for verification.",
        status_code=status.HTTP_201_CREATED
    )


@router.post("/login")
async def login(payload: LoginRequest):
    data = login_user(payload.email, payload.password)
    return api_success(data=data, message="Login successful")


@router.post("/refresh")
async def refresh(payload: RefreshTokenRequest):
    data = refresh_token_service(payload.refresh_token)
    return api_success(data=data, message="Token refreshed")


@router.post("/resend-email-verification")
async def resend_email_verification_endpoint(payload: EmailRequest):
    data = resend_email_verification(payload.email)
    return api_success(data=data, message="Verification email resent")


@router.post("/forgot-password")
async def forgot_password_endpoint(payload: EmailRequest):
    data = forgot_password(payload.email)
    return api_success(data=data, message="Password reset email sent")


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest):
    data = verify_email_token(payload.email, payload.token)
    return api_success(data=data, message="Email verified successfully")


@router.post("/verify-forgot-password")
async def verify_forgot_password(payload: VerifyForgotPasswordRequest):
    data = verify_forgot_password_token(payload.email, payload.token)
    return api_success(data=data, message="OTP verified")


@router.post("/reset-password")
async def reset_password_endpoint(payload: ResetPasswordRequest):
    data = reset_password(payload.access_token, payload.password)
    return api_success(data=data, message="Password has been reset successfully")


@router.get("/me")
async def get_current_user(
    profile: dict = Depends(get_current_profile),
    auth_status: dict = Depends(get_auth_user_status),
):
    sub_res = (
        supabase_admin.table("subscriptions")
        .select("*, plans(*)")
        .eq("user_id", profile["id"])
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    
    subscription = None
    if sub_res and sub_res.data and len(sub_res.data) > 0:
        subscription = sub_res.data[0]

    profile.update(auth_status)
    return api_success(
        data={
            "profile": profile,
            "subscription": subscription,
        },
        message="User profile retrieved"
    )
