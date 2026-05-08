from fastapi import APIRouter, Depends
from app.core.security import require_admin
from app.db.supabase import supabase_admin

router = APIRouter()


@router.get("/plans")
async def list_admin_plans(_: dict = Depends(require_admin)):
    return supabase_admin.table("plans").select("*").order("created_at", desc=True).execute().data
