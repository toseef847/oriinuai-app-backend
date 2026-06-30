from types import SimpleNamespace

import pytest

from app.services.llm import google_gemma
from app.services.rag.embedder import Embedder


class FakeEmbeddingModels:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def embed_content(self, **kwargs):
        self.calls.append(kwargs)
        contents = kwargs["contents"]
        count = len(contents) if isinstance(contents, list) else 1
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
    assert call["contents"] == ["first", "second"]
    assert call["config"].output_dimensionality == 768
    assert call["config"].task_type == "RETRIEVAL_DOCUMENT"


def test_google_embedder_marks_queries_for_retrieval() -> None:
    client = FakeEmbeddingClient()
    embedder = Embedder()
    embedder.provider = "google"
    embedder._google_client = client

    vector = embedder.embed_query("question")

    assert vector == [0.0, 1.0]
    assert client.models.calls[0]["config"].task_type == "RETRIEVAL_QUERY"


def test_google_embedder_skips_empty_batches() -> None:
    client = FakeEmbeddingClient()
    embedder = Embedder()
    embedder.provider = "google"
    embedder._google_client = client

    assert embedder.embed_texts([]) == []
    assert client.models.calls == []


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
