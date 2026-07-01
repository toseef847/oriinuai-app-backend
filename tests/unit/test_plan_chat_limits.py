from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.plan_service import (
    PLAN_LIMITS,
    check_chat_input_length,
    estimate_chat_tokens,
    get_user_plan,
)


def test_chat_input_accepts_exact_plan_limit() -> None:
    plan = PLAN_LIMITS["foundation"]

    check_chat_input_length("x" * 2000, plan, "message")


def test_chat_input_rejects_limit_plus_one() -> None:
    plan = PLAN_LIMITS["core"]

    with pytest.raises(HTTPException) as captured:
        check_chat_input_length("x" * 4001, plan, "content")

    assert captured.value.status_code == 422
    assert "4000-character limit" in captured.value.detail
    assert "core plan" in captured.value.detail


def test_estimate_chat_tokens_counts_prompt_history_and_completion() -> None:
    tokens = estimate_chat_tokens(
        system_prompt="system prompt",
        user_message="question",
        conversation_history=[
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
        ],
        assistant_response="current answer",
    )

    assert tokens > 0


@pytest.mark.asyncio
async def test_user_plan_falls_back_to_foundation_without_subscription() -> None:
    client = MagicMock()
    query = client.table.return_value.select.return_value
    execute = AsyncMock(return_value=SimpleNamespace(data=[]))
    query.eq.return_value.eq.return_value.limit.return_value.execute = execute

    plan = await get_user_plan("user-id", client)

    assert plan == PLAN_LIMITS["foundation"]
