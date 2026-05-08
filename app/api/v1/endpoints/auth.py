from fastapi import APIRouter, Depends
from app.core.security import get_current_user_id
from app.db.supabase import supabase_admin

router = APIRouter()


@router.get("/me")
async def get_current_user(user_id: str = Depends(get_current_user_id)):
    profile = supabase_admin.table("profiles").select("*").eq("id", user_id).maybe_single().execute().data
    subscription = supabase_admin.table("subscriptions").select("*, plans(*)").eq("user_id", user_id).eq("status", "active").maybe_single().execute().data
    return {"profile": profile, "subscription": subscription}
