import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import auth, chat
from app.services.llm.google_errors import FriendlyGoogleError, GoogleErrorDetails


class Query:
    def __init__(self, data):
        self.data = data

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def in_(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    async def execute(self):
        return SimpleNamespace(data=self.data)


class TableClient:
    def __init__(self, table_data):
        self.table_data = table_data

    def table(self, name):
        return Query(self.table_data.get(name, []))


class RecordingQuery:
    def __init__(self, calls, table_name, operation, payload):
        self.calls = calls
        self.table_name = table_name
        self.operation = operation
        self.payload = payload

    def eq(self, *args, **kwargs):
        return self

    async def execute(self):
        self.calls.append((self.operation, self.table_name, self.payload))
        return SimpleNamespace(data=[])


class RecordingTable:
    def __init__(self, calls, table_name):
        self.calls = calls
        self.table_name = table_name

    def insert(self, *args, **kwargs):
        return RecordingQuery(self.calls, self.table_name, "insert", args[0])

    def update(self, *args, **kwargs):
        return RecordingQuery(self.calls, self.table_name, "update", args[0])


class RecordingStreamClient:
    def __init__(self, calls):
        self.calls = calls

    def table(self, name):
        return RecordingTable(self.calls, name)


class SuccessfulProvider:
    async def stream_response(self, *args, **kwargs):
        yield "Ori"
        yield "inu"


@pytest.mark.asyncio
async def test_me_hydrates_subscription_plan_explicitly() -> None:
    plan_id = str(uuid4())
    client = TableClient(
        {
            "subscriptions": [{"id": "subscription-id", "plan_id": plan_id}],
            "plans": [
                {
                    "id": plan_id,
                    "name": "core",
                    "max_chat_characters": 4000,
                }
            ],
        }
    )

    response = await auth.get_current_user(
        profile={"id": "user-id"},
        auth_status={"email_verified": True},
        client=client,
    )
    payload = json.loads(response.body)

    assert payload["data"]["subscription"]["plans"]["name"] == "core"
    assert payload["data"]["subscription"]["plans"]["max_chat_characters"] == 4000


@pytest.mark.asyncio
async def test_me_sets_plan_to_none_for_invalid_reference() -> None:
    client = TableClient(
        {
            "subscriptions": [{"id": "subscription-id", "plan_id": "missing"}],
            "plans": [],
        }
    )

    response = await auth.get_current_user(
        profile={"id": "user-id"}, auth_status={}, client=client
    )
    payload = json.loads(response.body)

    assert payload["data"]["subscription"]["plans"] is None


class FailingProvider:
    async def stream_response(self, *args, **kwargs):
        if False:
            yield ""
        raise FriendlyGoogleError(
            GoogleErrorDetails(503, "The AI service is temporarily unavailable.")
        )


@pytest.mark.asyncio
async def test_stream_emits_terminal_sanitized_google_error(monkeypatch) -> None:
    monkeypatch.setattr(
        chat,
        "build_rag_prompt",
        AsyncMock(return_value=("system prompt", [])),
    )
    monkeypatch.setattr(chat, "get_llm_provider", lambda **kwargs: FailingProvider())
    increment_usage = AsyncMock()
    monkeypatch.setattr(chat, "increment_user_usage", increment_usage)
    client = TableClient({"chat_messages": []})

    response = await chat._stream_chat_response(
        user_id="user-id",
        session_id=uuid4(),
        user_message="question",
        plan={"rag_chunks": 2, "llm_tier": "free"},
        client=client,
        access_token="token",
    )
    chunks = [chunk async for chunk in response.body_iterator]
    body = "".join(
        chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in chunks
    )

    assert '"type": "error"' in body
    assert '"status": 503' in body
    assert '"type": "done"' not in body
    assert '"type": "token"' not in body
    increment_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_persists_and_increments_usage_before_done(monkeypatch) -> None:
    calls = []

    @asynccontextmanager
    async def fake_user_postgrest_client(access_token):
        assert access_token == "token"
        yield RecordingStreamClient(calls)

    async def fake_increment_user_usage(user_id, tokens=0):
        assert user_id == "user-id"
        calls.append(("usage", tokens))

    monkeypatch.setattr(
        chat,
        "build_rag_prompt",
        AsyncMock(return_value=("system prompt", [])),
    )
    monkeypatch.setattr(chat, "get_llm_provider", lambda **kwargs: SuccessfulProvider())
    monkeypatch.setattr(chat, "user_postgrest_client", fake_user_postgrest_client)
    monkeypatch.setattr(chat, "increment_user_usage", fake_increment_user_usage)

    response = await chat._stream_chat_response(
        user_id="user-id",
        session_id=uuid4(),
        user_message="question",
        plan={"rag_chunks": 2, "llm_tier": "free"},
        client=TableClient({"chat_messages": []}),
        access_token="token",
    )

    chunks = []
    async for chunk in response.body_iterator:
        text = chunk.decode() if isinstance(chunk, bytes) else chunk
        chunks.append(text)
        if '"type": "done"' in text:
            assert calls[0][0:2] == ("insert", "chat_messages")
            assert calls[0][2]["tokens_used"] > 0
            assert calls[1] == (
                "update",
                "chat_sessions",
                {"updated_at": "now()"},
            )
            assert calls[2] == ("usage", calls[0][2]["tokens_used"])

    body = "".join(chunks)
    assert '"type": "token", "content": "Ori"' in body
    assert '"type": "token", "content": "inu"' in body
    assert '"type": "done"' in body


@pytest.mark.asyncio
async def test_pre_stream_google_error_becomes_http_error(monkeypatch) -> None:
    error = FriendlyGoogleError(
        GoogleErrorDetails(429, "Please wait a moment and try again.")
    )
    monkeypatch.setattr(chat, "build_rag_prompt", AsyncMock(side_effect=error))

    with pytest.raises(HTTPException) as captured:
        await chat._stream_chat_response(
            user_id="user-id",
            session_id=uuid4(),
            user_message="question",
            plan={"rag_chunks": 2, "llm_tier": "free"},
            client=TableClient({}),
            access_token="token",
        )

    assert captured.value.status_code == 429
    assert captured.value.detail == "Please wait a moment and try again."
