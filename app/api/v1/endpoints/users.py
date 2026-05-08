from fastapi import APIRouter, Depends
from app.core.security import get_current_user_id
from app.db.supabase import supabase_admin

router = APIRouter()


@router.get("/me/usage")
async def usage_me(user_id: str = Depends(get_current_user_id)):
    usage = supabase_admin.table("usage_logs").select("*").eq("user_id", user_id).order("date", desc=True).limit(7).execute().data
    return {"usage": usage}
