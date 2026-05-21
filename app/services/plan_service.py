from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.db.supabase import supabase_admin
from app.core.config import settings

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
    try:
        result = supabase_admin.table("subscriptions").select(
            "*, plans(name, llm_tier)"
        ).eq("user_id", user_id).eq("status", "active").limit(1).execute()

        if not result or not result.data or len(result.data) == 0:
            return PLAN_LIMITS["foundation"]

        plan_data = result.data[0]
        if "plans" in plan_data and plan_data["plans"]:
            return PLAN_LIMITS.get(plan_data["plans"]["name"], PLAN_LIMITS["foundation"])
        
        return PLAN_LIMITS["foundation"]
    except Exception as e:
        print(f"Error fetching user plan: {e}")
        return PLAN_LIMITS["foundation"]


def check_daily_limit(user_id: str, plan_name: str = "foundation") -> None:
    limit = PLAN_LIMITS.get(plan_name, PLAN_LIMITS["foundation"])["daily_messages"]
    
    today = datetime.now(timezone.utc).date().isoformat()
    
    try:
        result = supabase_admin.table("usage_logs").select("messages_count").eq(
            "user_id", user_id
        ).eq("date", today).limit(1).execute()
        
        count = 0
        if result and result.data and len(result.data) > 0:
            count = result.data[0].get("messages_count", 0)
            
        if count >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Daily limit of {limit} messages reached. Upgrade your plan for more.",
            )
    except Exception as e:
        # If it's already an HTTPException (the limit hit), re-raise it
        if isinstance(e, HTTPException):
            raise e
        # Otherwise, log the error and allow the message if DB is acting up (fail-open)
        # or handle as you prefer. Here we log and allow.
        print(f"Error checking daily limit: {e}")
        return
