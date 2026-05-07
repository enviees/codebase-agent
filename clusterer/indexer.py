"""
indexer.py — Phase 2a: embed all chunks and store in ChromaDB.

Takes the chunks produced by Phase 1 and:
  1. Builds a text representation of each chunk
  2. Embeds them in batches via OpenAI
  3. Stores (vector + text + metadata) in ChromaDB "chunks" collection
"""

from chunker import Chunk
from embedder import get_client, embed_texts, estimate_cost
from vectordb import get_db, get_chunks_collection, store_chunks


def _chunk_to_text(chunk: Chunk) -> str:
    """
    Build the text we'll embed for a chunk.
    We prepend metadata so the embedding captures context beyond just the code.

    Example:
      File: src/features/auth/LoginForm.tsx (TypeScript React)
      Component: component LoginForm
      ---
      export default function LoginForm() {
        ...
      }
    """
    header = (
        f"File: {chunk.file_path} ({chunk.language})\n"
        f"Component: {chunk.label}\n"
        f"Lines: {chunk.start_line}–{chunk.end_line}\n"
        f"---\n"
    )
    return header + chunk.content


def _chunk_to_metadata(chunk: Chunk) -> dict:
    """
    Build the metadata dict stored alongside each vector in ChromaDB.
    This is what the agent reads when it retrieves a chunk.
    ChromaDB requires all metadata values to be str, int, float, or bool.
    """
    imports = getattr(chunk, 'imports', [])
    return {
        "file_path":  chunk.file_path,
        "language":   chunk.language,
        "start_line": chunk.start_line,
        "end_line":   chunk.end_line,
        "label":      chunk.label,
        "imports":    ", ".join(imports) if imports else "",
    }


def index_chunks(chunks: list[Chunk], repo_path: str, reset: bool = False, update: bool = False) -> int:
    """
    Main entry point for Phase 2a.
    Embeds all chunks and stores them in ChromaDB.

    Args:
        chunks:    list of Chunk objects from Phase 1
        repo_path: path to the repo (used for DB naming)
        reset:     if True, clears existing chunks before indexing

    Returns:
        number of chunks stored
    """
    if not chunks:
        print("[indexer] No chunks to index.")
        return 0

    # Estimate cost before doing anything
    texts = [_chunk_to_text(c) for c in chunks]
    estimated_cost = estimate_cost(texts)
    print(f"\n[indexer] Preparing to embed {len(chunks)} chunks")
    print(f"          Estimated cost: ${estimated_cost:.4f} (text-embedding-3-small)")

    # Set up DB
    db = get_db()
    collection = get_chunks_collection(db)

    if reset:
        print("          Clearing existing chunks...")
        db.delete_collection("chunks")
        collection = get_chunks_collection(db)

    if update:
        # Only embed chunks not already in the DB
        existing_ids = get_indexed_ids(collection)
        chunks = [c for c in chunks if c.chunk_id not in existing_ids]
        if not chunks:
            print("  Nothing new to index.")
            return collection.count()
        print(f"  {len(chunks)} new chunks to add")

    existing = collection.count()
    if existing > 0 and not reset:
        print(f"          {existing} chunks already indexed.")
        print("          Use reset=True to re-index from scratch.")
        print("          Skipping embedding — already up to date.")
        return existing

    # Embed all chunks
    print()
    client = get_client()
    vectors = embed_texts(texts, client, label="chunks")

    # Prepare data for ChromaDB
    ids       = [c.chunk_id for c in chunks]
    documents = [c.content for c in chunks]   # store raw content, not the prefixed text
    metadatas = [_chunk_to_metadata(c) for c in chunks]

    # Store in ChromaDB
    print()
    store_chunks(collection, ids, vectors, documents, metadatas)

    final_count = collection.count()
    print(f"\n[indexer] Phase 2a complete — {final_count} chunks in ChromaDB ✓")
    return final_count



def get_indexed_ids(collection) -> set[str]:
    """Return all chunk IDs already in the DB."""
    result = collection.get(include=[])
    return set(result["ids"])