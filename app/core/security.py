from typing import AsyncIterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from postgrest import AsyncPostgrestClient

from app.db.supabase import (
    get_public_url,
    supabase,
    supabase_admin,
    user_postgrest_client,
)
from app.core.config import settings

bearer_scheme = HTTPBearer()

# Use admin image bucket or fallback to profile images
ADMIN_IMAGE_BUCKET = getattr(
    settings, "ADMIN_IMAGE_BUCKET", settings.PROFILE_IMAGE_BUCKET
)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        user = supabase.auth.get_user(credentials.credentials)
        return {
            "sub": user.user.id,
            "access_token": credentials.credentials,
            "user": user.user,
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_access_token(payload: dict = Depends(verify_token)) -> str:
    return payload["access_token"]


async def get_user_db(
    payload: dict = Depends(verify_token),
) -> AsyncIterator[AsyncPostgrestClient]:
    async with user_postgrest_client(payload["access_token"]) as client:
        yield client


async def get_auth_user_status(payload: dict = Depends(verify_token)) -> dict:
    user = payload["user"]
    return {
        "email_verified": user.email_confirmed_at is not None,
        "phone_verified": user.phone_confirmed_at is not None,
    }


async def get_current_profile(
    payload: dict = Depends(verify_token),
    client: AsyncPostgrestClient = Depends(get_user_db),
) -> dict:
    """
    Fetches the user's profile from the database.
    This is more secure than trusting the JWT payload for sensitive fields like 'role'.
    """
    user_id = payload["sub"]
    res = (
        await client.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    )
    if not res or not res.data or len(res.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found."
        )

    profile = res.data[0]

    # Check if user is blocked
    if profile.get("is_blocked"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been blocked. Contact support for assistance.",
        )

    profile["profile_image_url"] = get_public_url(
        settings.PROFILE_IMAGE_BUCKET,
        profile.get("profile_image_path"),
    )
    return profile


def get_current_user_id(profile: dict = Depends(get_current_profile)) -> str:
    """Return the authenticated user's ID only after block-status enforcement."""
    return profile["id"]


# ============================================================================
# Admin-specific authentication dependencies (separate admins table)
# ============================================================================


def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Verifies admin JWT token and extracts admin user ID.
    """
    try:
        user = supabase.auth.get_user(credentials.credentials)
        return {"sub": user.user.id}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_admin_user_id(payload: dict = Depends(verify_admin_token)) -> str:
    """
    Extracts and returns the admin user ID from the verified token.
    """
    return payload["sub"]


async def get_admin_profile(admin_id: str = Depends(get_admin_user_id)) -> dict:
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


def require_admin(profile: dict = Depends(get_admin_profile)) -> dict:
    """
    Ensures the current admin is active (not blocked).
    Always called after get_admin_profile, so blocking is already verified.
    """
    return profile


def require_admin_user(profile: dict = Depends(get_admin_profile)) -> dict:
    """
    Ensures the current admin is active (not blocked).
    Always called after get_admin_profile, so blocking is already verified.
    Returns the admin profile for use in endpoint handlers.
    """
    return profile
