from fastapi import APIRouter, Depends
from app.core.security import get_auth_user_status, get_current_profile
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
    return signup_user(payload.email, payload.password, payload.full_name)


@router.post("/login")
async def login(payload: LoginRequest):
    return login_user(payload.email, payload.password)


@router.post("/refresh")
async def refresh(payload: RefreshTokenRequest):
    return refresh_token_service(payload.refresh_token)


@router.post("/resend-email-verification")
async def resend_email_verification_endpoint(payload: EmailRequest):
    return resend_email_verification(payload.email)


@router.post("/forgot-password")
async def forgot_password_endpoint(payload: EmailRequest):
    return forgot_password(payload.email)


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest):
    return verify_email_token(payload.email, payload.token)


@router.post("/verify-forgot-password")
async def verify_forgot_password(payload: VerifyForgotPasswordRequest):
    return verify_forgot_password_token(payload.email, payload.token)


@router.post("/reset-password")
async def reset_password_endpoint(payload: ResetPasswordRequest):
    return reset_password(payload.access_token, payload.password)


@router.get("/me")
async def get_current_user(
    profile: dict = Depends(get_current_profile),
    auth_status: dict = Depends(get_auth_user_status),
):
    
    subscription = (
        supabase_admin.table("subscriptions")
        .select("*, plans(*)")
        .eq("user_id", profile["id"])
        .eq("status", "active")
        .maybe_single()
        .execute()
        .data
    )
    profile.update(auth_status)
    return {
        "profile": profile,
        "subscription": subscription,
    }
