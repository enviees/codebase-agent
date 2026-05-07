"""
embedder.py — wraps OpenAI's embedding API.

Handles:
  - Batching (OpenAI max 2048 items per request)
  - Rate limit retries with exponential backoff
  - Progress reporting for large codebases
"""

import time
import os
from openai import OpenAI

# Model choice — text-embedding-3-small is the sweet spot:
# great quality, 1536 dimensions, cheapest paid option ($0.02/1M tokens)
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# OpenAI max items per embedding request
BATCH_SIZE = 256   # conservative — stays well under the 2048 limit

# Retry settings for rate limit errors
MAX_RETRIES = 5
RETRY_BASE_DELAY = 2   # seconds, doubles each retry


def get_client() -> OpenAI:
    """
    Create OpenAI client. Reads OPENAI_API_KEY from environment.
    Raises a clear error if the key is missing.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "\n[embedder] OPENAI_API_KEY not found.\n"
            "  Set it with: export OPENAI_API_KEY=sk-...\n"
            "  Or add it to a .env file and load with python-dotenv."
        )
    return OpenAI(api_key=api_key)


def embed_texts(texts: list[str], client: OpenAI, label: str = "") -> list[list[float]]:
    """
    Embed a list of texts. Returns a list of vectors (one per text).
    Handles batching and rate limit retries automatically.

    Args:
        texts:  list of strings to embed
        client: OpenAI client instance
        label:  optional label for progress output (e.g. "chunks", "summaries")
    """
    if not texts:
        return []

    all_vectors = []
    total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        batch_start = batch_idx * BATCH_SIZE
        batch_end   = min(batch_start + BATCH_SIZE, len(texts))
        batch       = texts[batch_start:batch_end]

        # Progress indicator
        progress = f"{batch_end}/{len(texts)}"
        if label:
            print(f"  [embedder] Embedding {label}: {progress}", end="\r")

        # Retry loop for rate limits
        for attempt in range(MAX_RETRIES):
            try:
                response = client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch,
                    dimensions=EMBEDDING_DIMENSIONS,
                )
                # Response items are sorted by index, safe to extend in order
                vectors = [item.embedding for item in response.data]
                all_vectors.extend(vectors)
                break  # success — exit retry loop

            except Exception as e:
                error_str = str(e).lower()
                if "rate limit" in error_str and attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    print(f"\n  [embedder] Rate limited. Waiting {delay}s...")
                    time.sleep(delay)
                else:
                    raise  # not a rate limit error, or out of retries

    if label:
        print(f"  [embedder] Embedded {len(texts)} {label} ✓          ")

    return all_vectors


def estimate_cost(texts: list[str]) -> float:
    """
    Rough token count estimate and cost for a list of texts.
    Rule of thumb: ~4 chars per token for code.
    Price: $0.02 per 1M tokens for text-embedding-3-small.
    """
    total_chars = sum(len(t) for t in texts)
    estimated_tokens = total_chars / 4
    cost = (estimated_tokens / 1_000_000) * 0.02
    return cost