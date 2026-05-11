from typing import List

from fastapi import APIRouter
from app.db.supabase import supabase_admin
from app.schemas.plans import PlanResponse

router = APIRouter()


@router.get("", response_model=List[PlanResponse])
async def list_plans():
    result = supabase_admin.table("plans").select(
        "id, name, display_name, daily_message_limit, rag_chunks, llm_tier, stripe_monthly_price_id, stripe_yearly_price_id"
    ).eq("is_active", True).order("daily_message_limit").execute()
    
    return result.data or []
