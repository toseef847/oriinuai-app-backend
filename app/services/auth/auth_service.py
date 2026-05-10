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


def resend_forgot_password(email: str) -> dict:
    return forgot_password(email)


def verify_email_token(token: str) -> dict:
    try:
        result = supabase_admin.auth.verify_otp({"token": token, "type": "signup"})
        return {
            "message": "Email verification successful.",
            "user": result.user.dict(exclude_none=True) if result.user else None,
            "session": result.session.dict(exclude_none=True) if result.session else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def verify_forgot_password_token(token: str) -> dict:
    try:
        result = supabase_admin.auth.verify_otp({"token": token, "type": "recovery"})
        return {
            "message": "Password reset token verified.",
            "user": result.user.dict(exclude_none=True) if result.user else None,
            "session": result.session.dict(exclude_none=True) if result.session else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def reset_password(token: str, password: str) -> dict:
    try:
        result = supabase_admin.auth.verify_otp({"token": token, "type": "recovery"})
        if not result.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to verify recovery token.",
            )

        user_id = getattr(result.user, "id", None)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user information returned during token verification.",
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
