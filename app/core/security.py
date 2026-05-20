from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.supabase import supabase, supabase_admin, get_public_url, get_signed_url
from app.core.config import settings

bearer_scheme = HTTPBearer()


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
    profile["profile_image_url"] = get_signed_url(
        settings.PROFILE_IMAGE_BUCKET, 
        profile.get("profile_image_path"),
        3600 * 24
    )
    return profile


def require_admin(profile: dict = Depends(get_current_profile)) -> dict:
    """
    Ensures the current user has an 'admin' role in their profile.
    """
    if profile.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required."
        )
    return profile
