from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.supabase import supabase, supabase_admin, get_public_url, get_signed_url
from app.core.config import settings

bearer_scheme = HTTPBearer()

# Use admin image bucket or fallback to profile images
ADMIN_IMAGE_BUCKET = getattr(settings, "ADMIN_IMAGE_BUCKET", settings.PROFILE_IMAGE_BUCKET)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        user = supabase.auth.get_user(credentials.credentials)
        return {"sub": user.user.id}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_id(payload: dict = Depends(verify_token)) -> str:
    return payload["sub"]


async def get_auth_user_status(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        user = supabase.auth.get_user(credentials.credentials)
        return {
            "email_verified": user.user.email_confirmed_at is not None,
            "phone_verified": user.user.phone_confirmed_at is not None,
        }
    except Exception:
        return {"email_verified": False, "phone_verified": False}


async def get_current_profile(user_id: str = Depends(get_current_user_id)) -> dict:
    """
    Fetches the user's profile from the database.
    This is more secure than trusting the JWT payload for sensitive fields like 'role'.
    """
    res = supabase_admin.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    if not res or not res.data or len(res.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found."
        )
    
    profile = res.data[0]
    
    # Check if user is blocked
    if profile.get("is_blocked"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been blocked. Contact support for assistance."
        )
    
    profile["profile_image_url"] = get_signed_url(
        settings.PROFILE_IMAGE_BUCKET, 
        profile.get("profile_image_path"),
        3600 * 24
    )
    return profile


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
    res = supabase_admin.table("admins").select("*").eq("id", admin_id).limit(1).execute()
    if not res or not res.data or len(res.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin profile not found."
        )
    
    profile = res.data[0]
    
    # Check if admin is blocked
    if profile.get("is_blocked"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account has been blocked."
        )
    
    # Add signed URL for profile image
    profile["profile_image_url"] = get_signed_url(
        ADMIN_IMAGE_BUCKET,
        profile.get("profile_image_path"),
        3600 * 24
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
