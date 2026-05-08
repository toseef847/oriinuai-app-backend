from fastapi import APIRouter, Depends
from app.core.security import require_admin
from app.db.supabase import supabase_admin

router = APIRouter()


@router.get("/users")
async def list_users(_: dict = Depends(require_admin)):
    return supabase_admin.table("profiles").select("*").order("created_at", desc=True).execute().data
