from fastapi import APIRouter
from app.db.supabase import supabase
from app.utils.response import api_success

router = APIRouter()


@router.get("", response_model=None)
async def list_plans():
    result = (
        supabase.table("plans")
        .select(
            "id, name, display_name, daily_message_limit, rag_chunks, llm_tier, max_chat_characters, stripe_monthly_price_id, stripe_yearly_price_id"
        )
        .eq("is_active", True)
        .order("daily_message_limit")
        .execute()
    )

    return api_success(data=result.data or [], message="Plans retrieved successfully")
