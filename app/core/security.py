from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.supabase import supabase, supabase_admin

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


async def get_current_profile(user_id: str = Depends(get_current_user_id)) -> dict:
    """
    Fetches the user's profile from the database.
    This is more secure than trusting the JWT payload for sensitive fields like 'role'.
    """
    result = supabase_admin.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found."
        )
    return result.data


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
