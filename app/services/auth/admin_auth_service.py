from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from app.core.config import settings
from app.db.supabase import (
    create_auth_supabase_client,
    get_public_url,
    reset_admin_auth_header,
    supabase_admin,
)
from app.services.auth.reset_store import create_reset_token, consume_reset_token
from app.utils.uploads import read_upload_with_limit

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# Use admin image bucket or fallback to profile images
ADMIN_IMAGE_BUCKET = getattr(
    settings, "ADMIN_IMAGE_BUCKET", settings.PROFILE_IMAGE_BUCKET
)


def _auth_client():
    return create_auth_supabase_client()


def _reset_admin_auth_header():
    """Reset supabase_admin auth header after user-auth operations overwrite it."""
    reset_admin_auth_header()


def login_admin(email: str, password: str) -> dict:
    """
    Authenticate admin with email/password.
    Never reveals admin email existence for security.
    """
    try:
        result = _auth_client().auth.sign_in_with_password(
            {
                "email": email,
                "password": password,
            }
        )

        _reset_admin_auth_header()

        if not result.user or not result.user.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        # Verify admin exists and is not blocked
        admin_profile = (
            supabase_admin.table("admins")
            .select("*")
            .eq("id", result.user.id)
            .limit(1)
            .execute()
        )
        if not admin_profile or not admin_profile.data or len(admin_profile.data) == 0:
            # Admin user exists in auth but no metadata in admins table
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        admin_data = admin_profile.data[0]
        if admin_data.get("is_blocked"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account has been blocked.",
            )

        return {
            "user": result.user.dict(exclude_none=True) if result.user else None,
            "session": (
                result.session.dict(exclude_none=True) if result.session else None
            ),
        }
    except HTTPException:
        raise
    except Exception:
        # Generic error response - never reveal email exists or password wrong
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )


def refresh_admin_token(refresh_token: str) -> dict:
    """
    Refresh admin auth session and verify the refreshed user is still a valid admin.
    """
    try:
        result = _auth_client().auth.refresh_session(refresh_token)
        _reset_admin_auth_header()

        if not result.user or not result.user.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token.",
            )

        admin_profile = (
            supabase_admin.table("admins")
            .select("*")
            .eq("id", result.user.id)
            .limit(1)
            .execute()
        )
        if not admin_profile or not admin_profile.data or len(admin_profile.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token.",
            )

        admin_data = admin_profile.data[0]
        if admin_data.get("is_blocked"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account has been blocked.",
            )

        return {
            "user": result.user.dict(exclude_none=True) if result.user else None,
            "session": (
                result.session.dict(exclude_none=True) if result.session else None
            ),
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )


def send_admin_password_reset_otp(email: str) -> dict:
    """
    Send OTP to admin email for password reset.
    Always returns success regardless of email existence (no email enumeration).
    """
    try:
        # Verify admin exists (silently, without revealing to caller)
        (
            supabase_admin.table("admins")
            .select("id")
            .eq("email", email)
            .limit(1)
            .execute()
        )

        # Send OTP via Supabase Auth regardless of whether admin exists
        try:
            _auth_client().auth.reset_password_for_email(email)
        except Exception:
            # Silently ignore errors (admin might not exist in auth)
            pass

        # Always return success response
        return {
            "message": "If an admin account exists with that email, a password reset OTP has been sent."
        }
    except Exception:
        # Log error internally but return generic success
        # In production, you'd log this to a monitoring system
        return {
            "message": "If an admin account exists with that email, a password reset OTP has been sent."
        }


def verify_admin_password_reset_otp(email: str, otp_token: str) -> dict:
    """
    Verify reset OTP and return reset token (same as user flow).
    """
    try:
        result = _auth_client().auth.verify_otp(
            {"email": email, "token": otp_token, "type": "recovery"}
        )

        _reset_admin_auth_header()

        if not result.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP.",
            )

        user_id = getattr(result.user, "id", None)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to identify admin from OTP.",
            )

        access_token = create_reset_token(user_id)
        return {"message": "OTP verified.", "access_token": access_token}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP."
        )


def reset_admin_password(reset_token: str, new_password: str) -> dict:
    """
    Reset admin password using reset token.
    """
    try:
        admin_id = consume_reset_token(reset_token)
        _reset_admin_auth_header()
        supabase_admin.auth.admin.update_user_by_id(
            admin_id, {"password": new_password}
        )
        return {
            "message": "Password reset successfully. Please sign in with your new password."
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password reset failed."
        )


def get_admin_profile(admin_id: str) -> dict:
    """
    Fetches the admin's profile from admins table.
    Verifies admin is not blocked before returning profile.
    """
    res = (
        supabase_admin.table("admins").select("*").eq("id", admin_id).limit(1).execute()
    )
    if not res or not res.data or len(res.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Admin profile not found."
        )

    profile = res.data[0]

    # Check if admin is blocked
    if profile.get("is_blocked"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account has been blocked.",
        )

    # Add signed URL for profile image
    profile["profile_image_url"] = get_public_url(
        ADMIN_IMAGE_BUCKET,
        profile.get("profile_image_path"),
    )

    return profile


def _resolve_image_extension(filename: str, content_type: str | None) -> str:
    """Resolve image file extension from filename or content type."""
    extension = Path(filename).suffix.lower()
    if extension in ALLOWED_IMAGE_EXTENSIONS:
        return extension
    if content_type and content_type.lower() in ALLOWED_IMAGE_CONTENT_TYPES:
        return ALLOWED_IMAGE_CONTENT_TYPES[content_type.lower()]
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported image file type. Allowed formats are JPG, PNG, WEBP, and GIF.",
    )


async def update_admin_profile(
    admin_id: str,
    full_name: str | None = None,
    bio: str | None = None,
    image: UploadFile | None = None,
) -> dict:
    """
    Update admin profile (name, bio, image).
    """
    try:
        updates: dict = {}
        image_upload: tuple[str, bytes] | None = None

        if image is not None:
            if not image.content_type or not image.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded file must be an image.",
                )

            image_bytes = await read_upload_with_limit(
                image,
                settings.MAX_PROFILE_IMAGE_UPLOAD_BYTES,
                "Profile image",
            )
            extension = _resolve_image_extension(image.filename, image.content_type)
            storage_path = f"admins/{admin_id}/{uuid4().hex}{extension}"
            image_upload = (storage_path, image_bytes)

        if full_name is not None:
            updates["full_name"] = full_name
            # Also update in auth metadata
            _reset_admin_auth_header()
            supabase_admin.auth.admin.update_user_by_id(
                admin_id, {"data": {"full_name": full_name}}
            )

        if bio is not None:
            updates["bio"] = bio

        if image_upload is not None:
            storage_path, image_bytes = image_upload
            supabase_admin.storage.from_(ADMIN_IMAGE_BUCKET).upload(
                storage_path, image_bytes
            )
            updates["profile_image_path"] = storage_path

        if updates:
            supabase_admin.table("admins").update(updates).eq("id", admin_id).execute()

            if "profile_image_path" in updates:
                updates["profile_image_url"] = get_public_url(
                    ADMIN_IMAGE_BUCKET,
                    updates["profile_image_path"],
                )

            return {"message": "Profile updated successfully.", "profile": updates}

        return {"message": "No profile changes provided."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def change_admin_password(
    admin_id: str, current_password: str, new_password: str
) -> dict:
    """
    Change admin password with current password verification.
    """
    try:
        # Get admin email from database
        profile_res = (
            supabase_admin.table("admins")
            .select("email")
            .eq("id", admin_id)
            .limit(1)
            .execute()
        )

        if not profile_res or not profile_res.data or len(profile_res.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin profile not found.",
            )

        profile = profile_res.data[0]
        if not profile.get("email"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin email not found.",
            )

        # Verify current password
        try:
            _auth_client().auth.sign_in_with_password(
                {"email": profile["email"], "password": current_password}
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )

        _reset_admin_auth_header()

        # Update password via admin API
        supabase_admin.auth.admin.update_user_by_id(
            admin_id, {"password": new_password}
        )

        return {
            "message": "Password updated successfully. Please sign in again with your new password."
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
