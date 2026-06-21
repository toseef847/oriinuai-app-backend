from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from app.core.config import settings
from app.db.supabase import create_auth_supabase_client, get_public_url, get_signed_url, supabase_admin
from app.services.auth.reset_store import create_reset_token, consume_reset_token

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _auth_client():
    return create_auth_supabase_client()


def signup_user(email: str, password: str, full_name: str | None = None) -> dict:
    try:
        result = _auth_client().auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {
                    "data": {"full_name": full_name} if full_name else {},
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
        result = _auth_client().auth.sign_in_with_password(
            {
                "email": email,
                "password": password,
            }
        )

        # Reset admin auth header in case sign_in_with_password corrupted it
        from app.core.config import settings
        supabase_admin.options.headers["Authorization"] = f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"

        if not result.user or not result.user.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        # Check if user is blocked
        profile_res = (
            supabase_admin.table("profiles")
            .select("is_blocked")
            .eq("id", result.user.id)
            .limit(1)
            .execute()
        )
        if profile_res and profile_res.data and profile_res.data[0].get("is_blocked"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been blocked. Contact support for assistance.",
            )

        return {
            "user": result.user.dict(exclude_none=True) if result.user else None,
            "session": result.session.dict(exclude_none=True) if result.session else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def refresh_token(refresh_token: str) -> dict:
    try:
        result = _auth_client().auth.refresh_session(refresh_token)
        return {
            "user": result.user.dict(exclude_none=True) if result.user else None,
            "session": result.session.dict(exclude_none=True) if result.session else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def resend_email_verification(email: str) -> dict:
    try:
        _auth_client().auth.resend({"type": "signup", "email": email})
        return {"message": "Verification email resent."}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def forgot_password(email: str) -> dict:
    try:
        _auth_client().auth.reset_password_for_email(email)
        return {"message": "Password reset email sent."}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def verify_email_token(email: str, token: str) -> dict:
    try:
        result = _auth_client().auth.verify_otp({"email": email, "token": token, "type": "signup"})
        return {
            "message": "Email verified successfully.",
            "user": result.user.dict(exclude_none=True) if result.user else None,
            "session": result.session.dict(exclude_none=True) if result.session else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def verify_forgot_password_token(email: str, otp_token: str) -> dict:
    try:
        result = _auth_client().auth.verify_otp({"email": email, "token": otp_token, "type": "recovery"})
        if not result.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP.",
            )

        user_id = getattr(result.user, "id", None)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to identify user from OTP verification.",
            )

        access_token = create_reset_token(user_id)
        return {"message": "OTP verified.", "access_token": access_token}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def update_user_password(user_id: str, current_password: str, new_password: str) -> dict:
    try:
        profile_res = (
            supabase_admin.table("profiles")
            .select("email")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        
        if not profile_res or not profile_res.data or len(profile_res.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found.",
            )
            
        profile = profile_res.data[0]
        if not profile.get("email"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User email not found.",
            )

        try:
            _auth_client().auth.sign_in_with_password(
                {"email": profile["email"], "password": current_password}
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )
            
        supabase_admin.auth.admin.update_user_by_id(user_id, {"password": new_password})
        
        return {
            "message": "Password updated successfully. Please sign in again with your new password."
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _resolve_image_extension(filename: str, content_type: str | None) -> str:
    extension = Path(filename).suffix.lower()
    if extension in ALLOWED_IMAGE_EXTENSIONS:
        return extension
    if content_type and content_type.lower() in ALLOWED_IMAGE_CONTENT_TYPES:
        return ALLOWED_IMAGE_CONTENT_TYPES[content_type.lower()]
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported image file type. Allowed formats are JPG, PNG, WEBP, and GIF.",
    )


def update_user_profile(
    user_id: str,
    full_name: str | None = None,
    bio: str | None = None,
    image: UploadFile | None = None,
) -> dict:
    try:
        updates: dict = {}

        if full_name is not None:
            updates["full_name"] = full_name
            supabase_admin.auth.admin.update_user_by_id(user_id, {"data": {"full_name": full_name}})

        if bio is not None:
            updates["bio"] = bio

        if image is not None:
            if not image.content_type or not image.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded file must be an image.",
                )

            image_bytes = image.file.read()
            extension = _resolve_image_extension(image.filename, image.content_type)
            storage_path = f"profiles/{user_id}/{uuid4().hex}{extension}"
            supabase_admin.storage.from_(settings.PROFILE_IMAGE_BUCKET).upload(storage_path, image_bytes)
            updates["profile_image_path"] = storage_path

        if updates:
            supabase_admin.table("profiles").update(updates).eq("id", user_id).execute()
            
            if "profile_image_path" in updates:
                updates["profile_image_url"] = get_signed_url(
                    settings.PROFILE_IMAGE_BUCKET, 
                    updates["profile_image_path"],
                    3600 * 24
                )
                
            return {"message": "Profile updated successfully.", "profile": updates}

        return {"message": "No profile changes provided."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def reset_password(access_token: str, password: str) -> dict:
    try:
        user_id = consume_reset_token(access_token)
        supabase_admin.auth.admin.update_user_by_id(user_id, {"password": password})
        return {"message": "Password has been reset successfully."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
