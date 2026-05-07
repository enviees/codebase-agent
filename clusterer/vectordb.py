"""
vectordb.py — wraps ChromaDB.

Two collections:
  chunks    → individual code chunks, used for "how does X work?" queries
  patterns  → discovered file patterns, used for "create X following conventions"

ChromaDB stores everything locally in ./.chroma by default — no server needed.
"""

import os
import chromadb
from chromadb.config import Settings
from dataclasses import dataclass

# DB path — set CHROMA_PATH in .env to override.
# Resolved against CWD so ".chroma" in .env always means
# <wherever you run the script from>/.chroma
_raw_path   = os.getenv("CHROMA_PATH", ".chroma")
CHROMA_PATH = os.path.abspath(_raw_path)

# Collection names
CHUNKS_COLLECTION    = "chunks"
PATTERNS_COLLECTION  = "patterns"

# How many chunks to retrieve per query by default
DEFAULT_N_RESULTS = 5


@dataclass
class SearchResult:
    """One result from a vector search."""
    id: str
    content: str
    metadata: dict
    score: float       # cosine distance — lower = more similar (0 = identical)
    similarity: float  # converted to 0–1 where 1 = identical


def get_db(path: str = CHROMA_PATH) -> chromadb.ClientAPI:
    """
    Get a persistent ChromaDB client.
    Always uses an absolute path so it works regardless of CWD.
    """
    os.makedirs(path, exist_ok=True)
    return chromadb.PersistentClient(
        path=path,
        settings=Settings(anonymized_telemetry=False),
    )


def get_chunks_collection(db: chromadb.ClientAPI):
    """Get or create the chunks collection."""
    return db.get_or_create_collection(
        name=CHUNKS_COLLECTION,
        metadata={"hnsw:space": "cosine"},   # use cosine similarity
    )


def get_patterns_collection(db: chromadb.ClientAPI):
    """Get or create the patterns collection."""
    return db.get_or_create_collection(
        name=PATTERNS_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def store_chunks(
    collection,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
    batch_size: int = 500,
):
    """
    Store chunks in ChromaDB in batches.
    ChromaDB recommends batching for large inserts.
    """
    total = len(ids)
    for i in range(0, total, batch_size):
        end = min(i + batch_size, total)
        collection.upsert(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end],
        )
        print(f"  [vectordb] Stored {end}/{total} chunks", end="\r")
    print(f"  [vectordb] Stored {total} chunks ✓          ")


def store_patterns(
    collection,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
):
    """Store pattern records in ChromaDB."""
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    print(f"  [vectordb] Stored {len(ids)} patterns ✓")


def search_chunks(
    collection,
    query_embedding: list[float],
    n_results: int = DEFAULT_N_RESULTS,
    where: dict = None,
) -> list[SearchResult]:
    """
    Search the chunks collection for the most relevant results.
    Returns a list of SearchResult objects sorted by relevance.
    """
    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    search_results = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]
        # Convert cosine distance (0–2) to similarity (0–1)
        similarity = 1 - (distance / 2)

        search_results.append(SearchResult(
            id=results["ids"][0][i],
            content=results["documents"][0][i],
            metadata=results["metadatas"][0][i],
            score=distance,
            similarity=similarity,
        ))

    return search_results


def search_patterns(
    collection,
    query_embedding: list[float],
    n_results: int = 3,
) -> list[SearchResult]:
    """Search the patterns collection."""
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    search_results = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]
        similarity = 1 - (distance / 2)
        search_results.append(SearchResult(
            id=results["ids"][0][i],
            content=results["documents"][0][i],
            metadata=results["metadatas"][0][i],
            score=distance,
            similarity=similarity,
        ))

    return search_results


def collection_stats(db: chromadb.ClientAPI) -> dict:
    """Return counts for both collections."""
    try:
        chunks_col = get_chunks_collection(db)
        patterns_col = get_patterns_collection(db)
        return {
            "chunks": chunks_col.count(),
            "patterns": patterns_col.count(),
        }
    except Exception:
        return {"chunks": 0, "patterns": 0}