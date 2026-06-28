import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from app.db.supabase import supabase_admin

TOKEN_EXPIRE_MINUTES = 15


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_reset_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)

    supabase_admin.table("password_resets").insert(
        {
            "user_id": user_id,
            "token_hash": _hash_token(token),
            "expires_at": expires_at.isoformat(),
        }
    ).execute()

    return token


def consume_reset_token(token: str) -> str:
    now = datetime.now(timezone.utc).isoformat()

    result = (
        supabase_admin.table("password_resets")
        .update({"used": True})
        .eq("token_hash", _hash_token(token))
        .eq("used", False)
        .gt("expires_at", now)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    return result.data[0]["user_id"]
