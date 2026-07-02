from types import SimpleNamespace

import pytest

from app.services.llm import google_gemma
from app.services.llm.google_errors import FriendlyGoogleError, translate_google_error
from app.services.rag.embedder import Embedder


class FakeEmbeddingModels:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def embed_content(self, **kwargs):
        self.calls.append(kwargs)
        contents = kwargs["contents"]
        count = (
            len(contents)
            if isinstance(contents, list)
            and all(hasattr(content, "parts") for content in contents)
            else 1
        )
        embeddings = [
            SimpleNamespace(values=[float(index), 1.0]) for index in range(count)
        ]
        return SimpleNamespace(embeddings=embeddings)


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.models = FakeEmbeddingModels()


def test_google_embedder_uses_new_client_response_shape() -> None:
    client = FakeEmbeddingClient()
    embedder = Embedder()
    embedder.provider = "google"
    embedder.dimensions = 768
    embedder._google_client = client

    vectors = embedder.embed_texts(["first", "second"])

    assert vectors == [[0.0, 1.0], [1.0, 1.0]]
    call = client.models.calls[0]
    assert call["model"] == "models/gemini-embedding-2"
    assert len(call["contents"]) == 2
    assert [
        content.parts[0].text for content in call["contents"]
    ] == [
        "title: none | text: first",
        "title: none | text: second",
    ]
    assert call["config"].output_dimensionality == 768
    assert call["config"].task_type is None


def test_google_embedder_marks_queries_for_retrieval() -> None:
    client = FakeEmbeddingClient()
    embedder = Embedder()
    embedder.provider = "google"
    embedder._google_client = client

    vector = embedder.embed_query("question")

    assert vector == [0.0, 1.0]
    call = client.models.calls[0]
    assert call["contents"] == "task: search result | query: question"
    assert call["config"].task_type is None


def test_google_embedder_skips_empty_batches() -> None:
    client = FakeEmbeddingClient()
    embedder = Embedder()
    embedder.provider = "google"
    embedder._google_client = client

    assert embedder.embed_texts([]) == []
    assert client.models.calls == []


def test_google_embedder_rejects_aggregated_batch_response() -> None:
    response = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[0.0, 1.0])]
    )

    with pytest.raises(ValueError, match="expected 2, received 1"):
        Embedder._extract_google_embeddings(response, expected_count=2)


class FakeAsyncModels:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text="complete response")

    async def generate_content_stream(self, **kwargs):
        self.calls.append(kwargs)

        async def chunks():
            for text in ("first ", "second"):
                yield SimpleNamespace(text=text)

        return chunks()


class FakeGenerationClient:
    def __init__(self) -> None:
        self.aio = SimpleNamespace(models=FakeAsyncModels())


@pytest.mark.asyncio
async def test_google_provider_uses_async_generate_content(monkeypatch) -> None:
    client = FakeGenerationClient()
    monkeypatch.setattr(google_gemma.genai, "Client", lambda **kwargs: client)
    provider = google_gemma.GoogleGemmaProvider("models/gemini-test")

    response = await provider.get_response(
        "system", "current question", [{"role": "user", "content": "prior"}]
    )

    assert response == "complete response"
    call = client.aio.models.calls[0]
    assert call["model"] == "models/gemini-test"
    assert "[SYSTEM]\nsystem" in call["contents"]
    assert "User: prior" in call["contents"]
    assert "User: current question" in call["contents"]


@pytest.mark.asyncio
async def test_google_provider_uses_async_streaming(monkeypatch) -> None:
    client = FakeGenerationClient()
    monkeypatch.setattr(google_gemma.genai, "Client", lambda **kwargs: client)
    provider = google_gemma.GoogleGemmaProvider("models/gemini-test")

    chunks = [
        chunk async for chunk in provider.stream_response("system", "question", [])
    ]

    assert chunks == ["first ", "second"]
    assert client.aio.models.calls[0]["model"] == "models/gemini-test"


@pytest.mark.parametrize(
    ("code", "provider_status", "expected_status"),
    [
        (400, "INVALID_ARGUMENT", 400),
        (400, "FAILED_PRECONDITION", 403),
        (403, "PERMISSION_DENIED", 403),
        (404, "NOT_FOUND", 404),
        (429, "RESOURCE_EXHAUSTED", 429),
        (499, "CANCELLED", 499),
        (500, "INTERNAL", 500),
        (503, "UNAVAILABLE", 503),
        (504, "DEADLINE_EXCEEDED", 504),
    ],
)
def test_google_errors_are_sanitized(code, provider_status, expected_status) -> None:
    exception = SimpleNamespace(
        code=code,
        status=provider_status,
        __str__=lambda: "SECRET provider detail",
    )

    details = translate_google_error(exception)

    assert details.status_code == expected_status
    assert "SECRET" not in details.message


class FailingAsyncModels:
    async def generate_content(self, **kwargs):
        error = RuntimeError("503 UNAVAILABLE: SECRET upstream failure")
        raise error

    async def generate_content_stream(self, **kwargs):
        error = RuntimeError("400 INVALID_ARGUMENT: SECRET upstream failure")
        raise error


class FailingGenerationClient:
    def __init__(self) -> None:
        self.aio = SimpleNamespace(models=FailingAsyncModels())


@pytest.mark.asyncio
async def test_google_provider_never_exposes_raw_stream_error(monkeypatch) -> None:
    monkeypatch.setattr(
        google_gemma.genai, "Client", lambda **kwargs: FailingGenerationClient()
    )
    provider = google_gemma.GoogleGemmaProvider("models/gemini-test")

    with pytest.raises(FriendlyGoogleError) as captured:
        _ = [
            chunk async for chunk in provider.stream_response("system", "question", [])
        ]

    assert captured.value.status_code == 400
    assert "SECRET" not in captured.value.user_message
