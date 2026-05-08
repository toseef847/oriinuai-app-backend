from app.db.supabase import supabase_admin
from app.core.config import settings
from fastapi import HTTPException, status

PLAN_LIMITS = {
    "foundation": {
        "plan_name":      "foundation",
        "daily_messages": settings.FOUNDATION_DAILY_MESSAGES,
        "rag_chunks":     settings.FOUNDATION_RAG_CHUNKS,
        "llm_tier":       "free",
    },
    "core": {
        "plan_name":      "core",
        "daily_messages": settings.CORE_DAILY_MESSAGES,
        "rag_chunks":     settings.CORE_RAG_CHUNKS,
        "llm_tier":       "pro",
    },
    "inner_circle": {
        "plan_name":      "inner_circle",
        "daily_messages": settings.INNER_CIRCLE_DAILY_MESSAGES,
        "rag_chunks":     settings.INNER_CIRCLE_RAG_CHUNKS,
        "llm_tier":       "elite",
    },
}


def get_user_plan(user_id: str) -> dict:
    result = supabase_admin.table("subscriptions").select(
        "*, plans(name, llm_tier)"
    ).eq("user_id", user_id).eq("status", "active").maybe_single().execute()

    if not result.data:
        return PLAN_LIMITS["foundation"]

    return PLAN_LIMITS.get(result.data["plans"]["name"], PLAN_LIMITS["foundation"])


def check_daily_limit(user_id: str, plan_name: str = "foundation") -> None:
    limit = PLAN_LIMITS.get(plan_name, PLAN_LIMITS["foundation"])["daily_messages"]
    result = supabase_admin.table("usage_logs").select("messages_count").eq(
        "user_id", user_id
    ).eq("date", "now()::date").maybe_single().execute()
    count = result.data["messages_count"] if result.data else 0
    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily limit of {limit} messages reached. Upgrade your plan for more.",
        )
