"""Smoke-test the configured Google or OpenAI embedding provider.

Run from the repository root:

    PYTHONPATH=. python3 scripts/test_embeddings.py --provider google
    PYTHONPATH=. python3 scripts/test_embeddings.py --provider openai
"""

import argparse
import math
import sys
import time
from typing import List, Sequence

from app.core.config import settings
from app.services.rag.embedder import Embedder


DEFAULT_QUERY = "How can I make a clear and aligned decision?"
DEFAULT_RELATED_TEXT = (
    "Clarity comes from slowing down, examining your values, and choosing the "
    "action that is most aligned with them."
)
DEFAULT_UNRELATED_TEXT = (
    "A solar eclipse occurs when the Moon passes between Earth and the Sun."
)


def cosine_similarity(first: Sequence[float], second: Sequence[float]) -> float:
    """Return cosine similarity for two vectors with equal dimensions."""
    if len(first) != len(second):
        raise ValueError(
            "Cannot compare vectors with different dimensions: "
            f"{len(first)} and {len(second)}."
        )

    dot_product = sum(left * right for left, right in zip(first, second))
    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))
    if first_norm == 0 or second_norm == 0:
        raise ValueError("The embedding provider returned a zero-length vector.")

    return dot_product / (first_norm * second_norm)


def validate_vectors(vectors: Sequence[Sequence[float]]) -> int:
    """Validate returned vectors and return their shared dimension."""
    if not vectors:
        raise ValueError("The embedding provider returned no vectors.")

    dimensions = len(vectors[0])
    if dimensions == 0:
        raise ValueError("The embedding provider returned an empty vector.")

    for index, vector in enumerate(vectors):
        if len(vector) != dimensions:
            raise ValueError(
                f"Vector {index} has {len(vector)} dimensions; expected {dimensions}."
            )
        if not all(math.isfinite(value) for value in vector):
            raise ValueError(f"Vector {index} contains a non-finite value.")

    return dimensions


def require_api_key(provider: str) -> None:
    """Fail with a useful message when the selected provider has no API key."""
    key_name = "GOOGLE_AI_STUDIO_KEY" if provider == "google" else "OPENAI_API_KEY"
    if not getattr(settings, key_name):
        raise ValueError(f"{key_name} is not set in the environment or .env file.")


def test_provider(
    provider: str,
    query: str,
    related_text: str,
    unrelated_text: str,
) -> None:
    """Call one provider and print basic shape and similarity diagnostics."""
    require_api_key(provider)

    embedder = Embedder()
    embedder.provider = provider
    if provider == "google":
        embedder.dimensions = 768

    started_at = time.perf_counter()
    query_vector = embedder.embed_query(query)
    document_vectors = embedder.embed_texts([related_text, unrelated_text])
    elapsed_seconds = time.perf_counter() - started_at

    vectors: List[Sequence[float]] = [query_vector, *document_vectors]
    dimensions = validate_vectors(vectors)
    related_score = cosine_similarity(query_vector, document_vectors[0])
    unrelated_score = cosine_similarity(query_vector, document_vectors[1])
    model = (
        "models/gemini-embedding-2"
        if provider == "google"
        else "text-embedding-3-small"
    )

    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"Dimensions: {dimensions}")
    print(f"Request time: {elapsed_seconds:.2f}s")
    print(f"First 5 values: {query_vector[:5]}")
    print(f"Related-text similarity: {related_score:.4f}")
    print(f"Unrelated-text similarity: {unrelated_score:.4f}")

    if related_score <= unrelated_score:
        print(
            "Warning: the related text did not score above the unrelated text. "
            "The API call worked, but inspect the test inputs or model behavior."
        )
    else:
        print("Embedding smoke test passed.")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Test Google or OpenAI embeddings using the project's Embedder."
    )
    parser.add_argument(
        "--provider",
        choices=("google", "openai", "both"),
        default=settings.EMBEDDING_PROVIDER,
        help="Provider to test (default: EMBEDDING_PROVIDER).",
    )
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--related-text", default=DEFAULT_RELATED_TEXT)
    parser.add_argument("--unrelated-text", default=DEFAULT_UNRELATED_TEXT)
    return parser.parse_args()


def main() -> int:
    """Run the requested provider smoke tests."""
    args = parse_args()
    providers = ("google", "openai") if args.provider == "both" else (args.provider,)
    failures = 0

    for index, provider in enumerate(providers):
        if index:
            print()
        try:
            test_provider(
                provider,
                args.query,
                args.related_text,
                args.unrelated_text,
            )
        except Exception as exc:
            failures += 1
            print(f"{provider} embedding test failed: {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
