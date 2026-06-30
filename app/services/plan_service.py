from datetime import datetime, timezone
from fastapi import HTTPException, status
from postgrest import AsyncPostgrestClient

from app.db.supabase import get_async_admin_client
from app.core.config import settings

PLAN_LIMITS = {
    "foundation": {
        "plan_name": "foundation",
        "daily_messages": settings.FOUNDATION_DAILY_MESSAGES,
        "rag_chunks": settings.FOUNDATION_RAG_CHUNKS,
        "llm_tier": "free",
        "max_chat_characters": 2000,
    },
    "core": {
        "plan_name": "core",
        "daily_messages": settings.CORE_DAILY_MESSAGES,
        "rag_chunks": settings.CORE_RAG_CHUNKS,
        "llm_tier": "pro",
        "max_chat_characters": 4000,
    },
    "inner_circle": {
        "plan_name": "inner_circle",
        "daily_messages": settings.INNER_CIRCLE_DAILY_MESSAGES,
        "rag_chunks": settings.INNER_CIRCLE_RAG_CHUNKS,
        "llm_tier": "elite",
        "max_chat_characters": 8000,
    },
}


async def get_user_plan(user_id: str, client: AsyncPostgrestClient) -> dict:
    try:
        result = (
            await client.table("subscriptions")
            .select("plan_id")
            .eq("user_id", user_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )

        if not result or not result.data or len(result.data) == 0:
            return PLAN_LIMITS["foundation"]

        plan_id = result.data[0].get("plan_id")
        if not plan_id:
            return PLAN_LIMITS["foundation"]

        plan_result = (
            await client.table("plans")
            .select(
                "name, daily_message_limit, rag_chunks, llm_tier, max_chat_characters"
            )
            .eq("id", plan_id)
            .limit(1)
            .execute()
        )
        if plan_result and plan_result.data:
            database_plan = plan_result.data[0]
            fallback = PLAN_LIMITS.get(
                database_plan.get("name"), PLAN_LIMITS["foundation"]
            )
            return {
                "plan_name": database_plan.get("name", fallback["plan_name"]),
                "daily_messages": database_plan.get(
                    "daily_message_limit", fallback["daily_messages"]
                ),
                "rag_chunks": database_plan.get("rag_chunks", fallback["rag_chunks"]),
                "llm_tier": database_plan.get("llm_tier", fallback["llm_tier"]),
                "max_chat_characters": database_plan.get("max_chat_characters")
                or fallback["max_chat_characters"],
            }

        return PLAN_LIMITS["foundation"]
    except Exception as e:
        print(f"Error fetching user plan: {e}")
        return PLAN_LIMITS["foundation"]


async def check_daily_limit(
    user_id: str,
    client: AsyncPostgrestClient,
    plan_name: str = "foundation",
) -> None:
    limit = PLAN_LIMITS.get(plan_name, PLAN_LIMITS["foundation"])["daily_messages"]

    today = datetime.now(timezone.utc).date().isoformat()

    try:
        result = (
            await client.table("usage_logs")
            .select("messages_count")
            .eq("user_id", user_id)
            .eq("date", today)
            .limit(1)
            .execute()
        )

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


def check_chat_input_length(text: str, plan: dict, field_name: str) -> None:
    """Reject user-authored chat text that exceeds the active plan limit."""
    limit = (
        plan.get("max_chat_characters")
        or PLAN_LIMITS["foundation"]["max_chat_characters"]
    )
    if len(text) > limit:
        plan_name = plan.get("plan_name", "foundation")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Field '{field_name}' exceeds the {limit}-character limit "
                f"for the {plan_name} plan."
            ),
        )


async def increment_user_usage(user_id: str, tokens: int = 0) -> None:
    """Increment server-controlled usage with the privileged database client."""
    client = await get_async_admin_client()
    await client.rpc(
        "increment_usage",
        {"p_user_id": user_id, "p_tokens": tokens},
    ).execute()
