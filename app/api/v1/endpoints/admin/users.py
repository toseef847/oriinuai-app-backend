from fastapi import APIRouter, Depends
from app.core.security import require_admin
from app.db.supabase import supabase_admin
from app.utils.response import api_success

router = APIRouter()


@router.get("/users")
async def list_users(_: dict = Depends(require_admin)):
    data = supabase_admin.table("profiles").select("*").order("created_at", desc=True).execute().data
    return api_success(data=data, message="Users retrieved successfully")
