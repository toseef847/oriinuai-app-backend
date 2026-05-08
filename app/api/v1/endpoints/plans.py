from fastapi import APIRouter
from app.db.supabase import supabase_admin

router = APIRouter()


@router.get("")
async def list_plans():
    return supabase_admin.table("plans").select("*").order("daily_message_limit", asc=True).execute().data
