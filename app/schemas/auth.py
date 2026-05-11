from pydantic import BaseModel, EmailStr


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class EmailRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    token: str


class VerifyForgotPasswordRequest(BaseModel):
    email: EmailStr
    token: str


class ResetPasswordRequest(BaseModel):
    access_token: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str
