import logging
from typing import Any, List

from app.core.config import settings
from app.services.llm.google_errors import FriendlyGoogleError, translate_google_error

logger = logging.getLogger(__name__)


class Embedder:
    """
    Cloud-only embedding provider.
    EMBEDDING_PROVIDER=google  → Google gemini-embedding-2 (768 dims, free)
    EMBEDDING_PROVIDER=openai  → OpenAI text-embedding-3-small (1536 dims, paid)

    NOTE: "local" is not supported. Do not add it.
    """

    def __init__(self):
        self.provider = settings.EMBEDDING_PROVIDER
        self.dimensions = settings.EMBEDDING_DIMENSIONS
        self._google_client = None
        self._openai_client = None

    def _get_google_client(self):
        if self._google_client is None:
            from google import genai

            self._google_client = genai.Client(api_key=settings.GOOGLE_AI_STUDIO_KEY)
        return self._google_client

    def _get_openai_client(self):
        if self._openai_client is None:
            from openai import OpenAI

            self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts. Returns list of float vectors."""
        if self.provider == "google":
            if not texts:
                return []

            from google.genai import types

            client = self._get_google_client()
            # Use gemini-embedding-2 for better performance and lower quota usage
            try:
                response = client.models.embed_content(
                    model="models/gemini-embedding-2",
                    contents=texts,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=self.dimensions,
                    ),
                )
                return self._extract_google_embeddings(response, len(texts))
            except FriendlyGoogleError:
                raise
            except Exception as exception:
                logger.exception("Google embedding batch failed")
                raise FriendlyGoogleError(
                    translate_google_error(exception)
                ) from exception

        elif self.provider == "openai":
            client = self._get_openai_client()
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
            )
            return [item.embedding for item in response.data]

        else:
            raise ValueError(
                f"Unknown EMBEDDING_PROVIDER: '{self.provider}'. "
                f"Supported values: 'google' | 'openai'. "
                f"Note: 'local' is not supported."
            )

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string for similarity search."""
        if self.provider == "google":
            from google.genai import types

            client = self._get_google_client()
            try:
                response = client.models.embed_content(
                    model="models/gemini-embedding-2",
                    contents=query,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_QUERY",
                        output_dimensionality=self.dimensions,
                    ),
                )
                return self._extract_google_embeddings(response, 1)[0]
            except FriendlyGoogleError:
                raise
            except Exception as exception:
                logger.exception("Google query embedding failed")
                raise FriendlyGoogleError(
                    translate_google_error(exception)
                ) from exception
        else:
            return self.embed_texts([query])[0]

    @staticmethod
    def _extract_google_embeddings(
        response: Any, expected_count: int
    ) -> List[List[float]]:
        embeddings = response.embeddings or []
        if len(embeddings) != expected_count:
            raise ValueError(
                "Google returned an unexpected number of embeddings: "
                f"expected {expected_count}, received {len(embeddings)}."
            )

        vectors: List[List[float]] = []
        for index, embedding in enumerate(embeddings):
            if embedding.values is None:
                raise ValueError(f"Google returned no values for embedding {index}.")
            vectors.append(embedding.values)
        return vectors


embedder = Embedder()
