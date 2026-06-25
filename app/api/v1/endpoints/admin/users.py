from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from app.core.security import require_admin
from app.db.supabase import supabase_admin, get_public_url
from app.core.config import settings
from app.utils.response import api_success

router = APIRouter()

class BlockReasonPayload(BaseModel):
    reason: str | None = None

class BulkUserIdsPayload(BaseModel):
    user_ids: list[UUID]

def _log_admin_action(admin_id: UUID, action: str, target_type: str, target_id: UUID, metadata: dict = None):
    try:
        supabase_admin.table("admin_logs").insert({
            "admin_id": str(admin_id),
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id) if target_id else None,
            "metadata": metadata or {}
        }).execute()
    except Exception as e:
        print(f"Failed to log admin action: {e}")


def _format_profile(profile: dict) -> dict:
    subscription = None
    if profile.get("subscriptions") and len(profile["subscriptions"]) > 0:
        subscription = profile["subscriptions"][0]

    return {
        "id": profile["id"],
        "username": profile.get("full_name") or (profile.get("email").split("@")[0] if profile.get("email") else "user"),
        "full_name": profile.get("full_name"),
        "email": profile.get("email"),
        "profile_image_url": get_public_url(
            settings.PROFILE_IMAGE_BUCKET,
            profile.get("profile_image_path"),
        ),
        "joined_date": profile.get("created_at"),
        "plan_name": subscription.get("plans", {}).get("display_name") if subscription else "Foundation",
        "subscription_type": subscription.get("billing_interval", "free") if subscription else "free",
        "status": "blocked" if profile.get("is_blocked") else "active",
        "is_blocked": profile.get("is_blocked", False),
    }


def _matches_user_search(profile: dict, search: str | None) -> bool:
    if not search:
        return True

    normalized = search.strip().lower()
    return any(
        normalized in field
        for field in (
            str(profile.get("id", "")).lower(),
            str(profile.get("email", "")).lower(),
            str(profile.get("full_name", "")).lower(),
        )
    )

@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    include_blocked: bool = Query(True),
    search: str | None = Query(None, min_length=1),
    _: dict = Depends(require_admin)
):
    query = supabase_admin.table("profiles").select(
        "id, email, full_name, profile_image_path, created_at, is_blocked, subscriptions(billing_interval, plans(display_name))"
    ).eq("role", "user")
    
    if not include_blocked:
        query = query.eq("is_blocked", False)

    result = query.order("created_at", desc=True).execute()
    filtered_profiles = [profile for profile in (result.data or []) if _matches_user_search(profile, search)]
    total = len(filtered_profiles)
    offset = (page - 1) * limit
    users_data = [_format_profile(profile) for profile in filtered_profiles[offset:offset + limit]]

    return api_success(data={
        "users": users_data,
        "total": total,
        "page": page,
        "limit": limit
    }, message="Users retrieved successfully")


@router.get("/users/blocked")
async def list_blocked_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, min_length=1),
    _: dict = Depends(require_admin)
):
    result = supabase_admin.table("profiles").select(
        "id, email, full_name, created_at, is_blocked, subscriptions(billing_interval, plans(display_name))"
    ).eq("role", "user").eq("is_blocked", True).order("created_at", desc=True).execute()

    filtered_profiles = [profile for profile in (result.data or []) if _matches_user_search(profile, search)]
    total = len(filtered_profiles)
    offset = (page - 1) * limit
    users_data = [_format_profile(profile) for profile in filtered_profiles[offset:offset + limit]]

    return api_success(data={
        "users": users_data,
        "total": total,
        "page": page,
        "limit": limit
    }, message="Blocked users retrieved successfully")


@router.post("/users/{user_id}/block")
async def block_user(
    user_id: UUID,
    payload: BlockReasonPayload | None = None,
    admin: dict = Depends(require_admin)
):
    # Verify user exists
    user_res = supabase_admin.table("profiles").select("id, is_blocked").eq("id", user_id).limit(1).execute()
    if not user_res or not user_res.data or len(user_res.data) == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    reason = payload.reason if payload else None
    
    # Update is_blocked
    supabase_admin.table("profiles").update({"is_blocked": True}).eq("id", user_id).execute()
    
    # Log admin action
    _log_admin_action(
        admin_id=admin["id"],
        action="user_blocked",
        target_type="user",
        target_id=user_id,
        metadata={"reason": reason}
    )
    
    return api_success(data={"user_id": user_id, "is_blocked": True}, message="User blocked")


@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: UUID,
    admin: dict = Depends(require_admin)
):
    # Verify user exists
    user_res = supabase_admin.table("profiles").select("id, is_blocked").eq("id", user_id).limit(1).execute()
    if not user_res or not user_res.data or len(user_res.data) == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Update is_blocked
    supabase_admin.table("profiles").update({"is_blocked": False}).eq("id", user_id).execute()
    
    # Log admin action
    _log_admin_action(
        admin_id=admin["id"],
        action="user_unblocked",
        target_type="user",
        target_id=user_id
    )
    
    return api_success(data={"user_id": user_id, "is_blocked": False}, message="User unblocked")


@router.post("/users/block-bulk")
async def block_users_bulk(
    payload: BulkUserIdsPayload,
    admin: dict = Depends(require_admin)
):
    if not payload.user_ids:
        raise HTTPException(status_code=400, detail="No user IDs provided")
        
    supabase_admin.table("profiles").update({"is_blocked": True}).in_("id", payload.user_ids).execute()
    
    # Log bulk block action
    _log_admin_action(
        admin_id=admin["id"],
        action="user_blocked_bulk",
        target_type="user",
        target_id=None,
        metadata={"user_ids": payload.user_ids, "reason": "Bulk block"}
    )
        
    return api_success(data={"blocked_count": len(payload.user_ids)}, message="Users blocked")


@router.post("/users/unblock-bulk")
async def unblock_users_bulk(
    payload: BulkUserIdsPayload,
    admin: dict = Depends(require_admin)
):
    if not payload.user_ids:
        raise HTTPException(status_code=400, detail="No user IDs provided")
        
    supabase_admin.table("profiles").update({"is_blocked": False}).in_("id", payload.user_ids).execute()
    
    # Log bulk unblock action
    _log_admin_action(
        admin_id=admin["id"],
        action="user_unblocked_bulk",
        target_type="user",
        target_id=None,
        metadata={"user_ids": payload.user_ids, "reason": "Bulk unblock"}
    )
        
    return api_success(data={"unblocked_count": len(payload.user_ids)}, message="Users unblocked")
