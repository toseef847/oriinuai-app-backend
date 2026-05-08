from typing import List
from app.core.config import settings


class Embedder:
    """
    Cloud-only embedding provider.
    EMBEDDING_PROVIDER=google  → Google text-embedding-004 (768 dims, free)
    EMBEDDING_PROVIDER=openai  → OpenAI text-embedding-3-small (1536 dims, paid)

    NOTE: "local" is not supported. Do not add it.
    """

    def __init__(self):
        self.provider = settings.EMBEDDING_PROVIDER
        self._google_client = None
        self._openai_client = None

    def _get_google_client(self):
        if self._google_client is None:
            import google.generativeai as genai
            genai.configure(api_key=settings.GOOGLE_AI_STUDIO_KEY)
            self._google_client = genai
        return self._google_client

    def _get_openai_client(self):
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts. Returns list of float vectors."""
        if self.provider == "google":
            genai = self._get_google_client()
            embeddings = []
            for text in texts:
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=text,
                    task_type="retrieval_document",
                )
                embeddings.append(result["embedding"])
            return embeddings

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
            genai = self._get_google_client()
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query",
            )
            return result["embedding"]
        else:
            return self.embed_texts([query])[0]


embedder = Embedder()
