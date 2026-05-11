from fastapi import HTTPException, status
from app.db.supabase import supabase_admin


def signup_user(email: str, password: str, full_name: str | None = None) -> dict:
    try:
        result = supabase_admin.auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {
                    "data": {"full_name": full_name or ""},
                },
            }
        )
        return {
            "user": result.user.dict(exclude_none=True) if result.user else None,
            "session": result.session.dict(exclude_none=True) if result.session else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def login_user(email: str, password: str) -> dict:
    try:
        result = supabase_admin.auth.sign_in_with_password(
            {
                "email": email,
                "password": password,
            }
        )
        return {
            "user": result.user.dict(exclude_none=True) if result.user else None,
            "session": result.session.dict(exclude_none=True) if result.session else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def refresh_token(refresh_token: str) -> dict:
    try:
        result = supabase_admin.auth.refresh_session(refresh_token)
        return {
            "user": result.user.dict(exclude_none=True) if result.user else None,
            "session": result.session.dict(exclude_none=True) if result.session else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def resend_email_verification(email: str) -> dict:
    try:
        supabase_admin.auth.resend({"type": "signup", "email": email})
        return {"message": "Verification email resent."}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def forgot_password(email: str) -> dict:
    try:
        supabase_admin.auth.reset_password_for_email(email)
        return {"message": "Password reset email sent."}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def verify_email_token(email: str, token: str) -> dict:
    try:
        result = supabase_admin.auth.verify_otp({"email": email, "token": token, "type": "signup"})
        return {
            "message": "Email verified successfully.",
            "user": result.user.dict(exclude_none=True) if result.user else None,
            "session": result.session.dict(exclude_none=True) if result.session else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def verify_forgot_password_token(email: str, token: str) -> dict:
    try:
        result = supabase_admin.auth.verify_otp({"email": email, "token": token, "type": "recovery"})
        return {
            "message": "Password reset otp verified.",
            "user": result.user.dict(exclude_none=True) if result.user else None,
            "session": result.session.dict(exclude_none=True) if result.session else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def reset_password(access_token: str, password: str) -> dict:
    try:
        result = supabase_admin.auth.get_user(access_token)
        if not result.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired recovery session.",
            )

        user_id = getattr(result.user, "id", None)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user information returned during session verification.",
            )

        updated = supabase_admin.auth.admin.update_user_by_id(user_id, {"password": password})
        return {
            "message": "Password has been reset successfully.",
            "user": getattr(updated, "user", None) and updated.user.dict(exclude_none=True),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
