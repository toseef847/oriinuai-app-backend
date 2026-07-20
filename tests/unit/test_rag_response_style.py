from unittest.mock import AsyncMock

import pytest

from app.services.rag import query
from app.utils.text import remove_dash_characters


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (
            "365 African Proverbs FINAL (1)\nBy A. Teacher\n"
            "DAY 1 — LAW OF BEGINNINGS\nBegin with clear intention.",
            "Begin with clear intention.",
        ),
        (
            "AFRICAN PROSPERITY BOOK\nCHAPTER 2\nTHE ROOT OF VALUE\n"
            "••••••\nValue grows through service.",
            "Value grows through service.",
        ),
        (
            "Olódùmarè UPDATED-3 (1) (1)\nWritten by A. Teacher\n"
            "Chapter III: Divine Order\nTruth restores balance.",
            "Truth restores balance.",
        ),
        (
            "OLODUMARE WORKBOOK COMPANION (1)-3 (1)\n"
            "CHAPTER FOUR — PRACTICE\nReflect before acting.",
            "Reflect before acting.",
        ),
        (
            "WEALTH_ POWER _ DESTINY- LATEST -3-1 (1)\n"
            "Author: A. Teacher\nCHAPTER 5 — PURPOSE\n"
            "Direct your resources with purpose.",
            "Direct your resources with purpose.",
        ),
    ],
)
def test_clean_retrieved_content_removes_current_book_structure(
    content: str, expected: str
) -> None:
    assert query.clean_retrieved_content(content) == expected


@pytest.mark.asyncio
async def test_build_rag_prompt_uses_only_clean_content(monkeypatch) -> None:
    monkeypatch.setattr(query.embedder, "embed_query", lambda message: [0.1])
    monkeypatch.setattr(
        query.vector_store,
        "similarity_search",
        AsyncMock(
            return_value=[
                {
                    "content": "DAY 7 — INNER POWER\nAct from inner clarity.",
                    "chunk_index": 7,
                    "metadata": {"day_number": 7, "law_name": "INNER POWER"},
                }
            ]
        ),
    )

    system_prompt, chunks = await query.build_rag_prompt("How should I act?", object())

    assert "Act from inner clarity." in system_prompt
    assert "[Day" not in system_prompt
    assert "[Excerpt" not in system_prompt
    assert "INNER POWER" not in system_prompt
    assert chunks[0]["metadata"]["day_number"] == 7


def test_system_prompt_requires_short_anonymous_answers() -> None:
    assert "2 to 4 concise sentences" in query.ORIINU_SYSTEM_PROMPT
    assert "one direct insight and one practical action" in query.ORIINU_SYSTEM_PROMPT
    assert "Never mention or identify a source" in query.ORIINU_SYSTEM_PROMPT
    assert "Do not use hyphens" in query.ORIINU_SYSTEM_PROMPT


@pytest.mark.parametrize(
    "user_message",
    [
        "Help me make a decision about the direction of my life.",
        "What is the best next step for my growth and purpose?",
        "Give me clarity on the path I should take.",
        "How do I find my path and move forward with purpose?",
    ],
)
def test_broad_life_direction_queries_are_supported(user_message: str) -> None:
    assert query.is_broad_life_direction_query(user_message)


@pytest.mark.parametrize(
    "user_message",
    [
        "Should I leave my job for another company?",
        "Should I end my relationship?",
        "What should I do about my finances?",
    ],
)
def test_specific_personal_questions_remain_strictly_grounded(
    user_message: str,
) -> None:
    assert not query.is_broad_life_direction_query(user_message)


@pytest.mark.asyncio
async def test_broad_life_direction_query_uses_framework_without_retrieval(
    monkeypatch,
) -> None:
    monkeypatch.setattr(query.embedder, "embed_query", lambda message: [0.1])
    monkeypatch.setattr(
        query.vector_store,
        "similarity_search",
        AsyncMock(return_value=[]),
    )

    system_prompt, chunks = await query.build_rag_prompt(
        "What is the best next step for my growth and purpose?", object()
    )

    assert chunks == []
    assert "clarity begins with honest reflection" in system_prompt
    assert "one small practical action" in system_prompt


@pytest.mark.asyncio
async def test_retrieved_context_precedes_life_direction_framework(monkeypatch) -> None:
    monkeypatch.setattr(query.embedder, "embed_query", lambda message: [0.1])
    monkeypatch.setattr(
        query.vector_store,
        "similarity_search",
        AsyncMock(
            return_value=[
                {
                    "content": "Choose truth before speed.",
                    "chunk_index": 1,
                    "metadata": {},
                }
            ]
        ),
    )

    system_prompt, _ = await query.build_rag_prompt(
        "Give me clarity on the path I should take.", object()
    )

    assert system_prompt.index("Choose truth before speed.") < system_prompt.index(
        "clarity begins with honest reflection"
    )


def test_remove_dash_characters_covers_common_dash_variants() -> None:
    value = "self-aware — grounded – clear ‐ focused‑action"

    assert remove_dash_characters(value) == "self aware grounded clear focused action"
