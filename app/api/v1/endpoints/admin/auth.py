from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from app.core.security import get_admin_profile
from app.services.auth.admin_auth_service import (
    login_admin,
    send_admin_password_reset_otp,
    verify_admin_password_reset_otp,
    reset_admin_password,
)
from app.schemas.auth import LoginRequest, EmailRequest
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
    data = login_admin(payload.email, payload.password)
    return api_success(data=data, message="Login successful")

@router.post("/forgot-password/send-otp")
async def send_password_reset_otp(payload: EmailRequest):
    data = send_admin_password_reset_otp(payload.email)
    return api_success(data=None, message=data["message"])

@router.post("/forgot-password/verify-otp")
async def verify_password_reset_otp(payload: AdminVerifyOTPRequest):
    data = verify_admin_password_reset_otp(payload.email, payload.otp)
    return api_success(data=data, message="OTP verified")

@router.post("/reset-password")
async def reset_password(
    payload: AdminResetPasswordRequest, 
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    data = reset_admin_password(credentials.credentials, payload.new_password)
    return api_success(data=None, message=data["message"])

@router.get("/me")
async def get_current_admin(profile: dict = Depends(get_admin_profile)):
    return api_success(data=profile, message="Admin profile retrieved")
