from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from app.core.security import get_admin_profile
from app.services.auth.admin_auth_service import (
    login_admin,
    refresh_admin_token,
    send_admin_password_reset_otp,
    verify_admin_password_reset_otp,
    reset_admin_password,
)
from app.schemas.auth import LoginRequest, EmailRequest, RefreshTokenRequest
from app.services.auth.rate_limit_service import (
    clear_auth_rate_limit,
    enforce_auth_rate_limit,
)
from app.utils.response import api_success

router = APIRouter()
bearer_scheme = HTTPBearer()


class AdminVerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str


class AdminResetPasswordRequest(BaseModel):
    new_password: str


@router.post("/login")
async def admin_login(payload: LoginRequest):
    lease = await enforce_auth_rate_limit("admin-login", payload.email)
    data = login_admin(payload.email, payload.password)
    await clear_auth_rate_limit(lease)
    return api_success(data=data, message="Login successful")


@router.post("/refresh")
async def admin_refresh(payload: RefreshTokenRequest):
    lease = await enforce_auth_rate_limit(
        "admin-refresh",
        payload.refresh_token,
        normalize_identity=False,
    )
    data = refresh_admin_token(payload.refresh_token)
    await clear_auth_rate_limit(lease)
    return api_success(data=data, message="Token refreshed")


@router.post("/forgot-password/send-otp")
async def send_password_reset_otp(payload: EmailRequest):
    await enforce_auth_rate_limit("admin-forgot-password", payload.email)
    data = send_admin_password_reset_otp(payload.email)
    return api_success(data=None, message=data["message"])


@router.post("/forgot-password/verify-otp")
async def verify_password_reset_otp(payload: AdminVerifyOTPRequest):
    lease = await enforce_auth_rate_limit("admin-verify-recovery", payload.email)
    data = verify_admin_password_reset_otp(payload.email, payload.otp)
    await clear_auth_rate_limit(lease)
    return api_success(data=data, message="OTP verified")


@router.post("/reset-password")
async def reset_password(
    payload: AdminResetPasswordRequest,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    lease = await enforce_auth_rate_limit(
        "admin-reset-password",
        credentials.credentials,
        normalize_identity=False,
    )
    data = reset_admin_password(credentials.credentials, payload.new_password)
    await clear_auth_rate_limit(lease)
    return api_success(data=None, message=data["message"])


@router.get("/me")
async def get_current_admin(profile: dict = Depends(get_admin_profile)):
    return api_success(data=profile, message="Admin profile retrieved")
