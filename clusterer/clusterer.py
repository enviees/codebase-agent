"""
clusterer.py — Phase 2b: discover and store patterns automatically.

Steps:
  1. Embed each FileSummary → get a vector representing the file's shape
  2. Cluster files whose vectors are close (cosine similarity > threshold)
  3. For each cluster, ask an LLM to name the pattern
  4. Store named patterns in ChromaDB "patterns" collection

LLM provider is configurable — defaults to DeepSeek, falls back to Anthropic.
Switch with: export LLM_PROVIDER=anthropic
"""

import os
import json
from openai import OpenAI as OpenAIClient

from patterns import FileSummary
from embedder import get_client, embed_texts
from vectordb import get_db, get_patterns_collection, store_patterns

# Similarity threshold — files this close are grouped as a pattern
SIMILARITY_THRESHOLD = 0.82

# Minimum files needed to form a pattern
MIN_CLUSTER_SIZE = 2

# Max files to show LLM per cluster
MAX_EXAMPLE_FILES = 4

# LLM provider: "deepseek" (default) or "anthropic"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")


def _get_llm_client():
    """Return an OpenAI-compatible client for the configured provider."""
    if LLM_PROVIDER == "anthropic":
        return None  # Anthropic uses its own SDK, handled separately

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "\n[clusterer] DEEPSEEK_API_KEY not found.\n"
            "  Set it with: export DEEPSEEK_API_KEY=sk-...\n"
            "  Or switch provider: export LLM_PROVIDER=anthropic"
        )
    return OpenAIClient(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )


def _name_pattern(summaries_in_cluster: list[FileSummary], llm_client) -> dict:
    """
    Ask the LLM to identify and name the pattern shared by a cluster of files.
    Returns {"name": "...", "description": "...", "when_to_use": "..."}
    """
    file_list = "\n\n".join([
        f"File: {s.file_path}\n{s.summary_text}"
        for s in summaries_in_cluster[:MAX_EXAMPLE_FILES]
    ])

    prompt = f"""You are analyzing a React/TypeScript codebase.
I found a group of files that share a similar structure and imports.

Here are the files:

{file_list}

Based on these files, identify the pattern they share.
Respond ONLY with a JSON object (no markdown, no explanation):
{{
  "name": "short-kebab-case-name",
  "description": "One sentence describing what this pattern is",
  "when_to_use": "One sentence describing when to apply this pattern"
}}"""

    try:
        if LLM_PROVIDER == "anthropic":
            from anthropic import Anthropic
            client = Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
        else:
            # DeepSeek or any OpenAI-compatible provider
            response = llm_client.chat.completions.create(
                model="deepseek-chat",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.choices[0].message.content.strip()

        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)

    except Exception as e:
        # Fallback if LLM call fails
        first_file = summaries_in_cluster[0].file_path
        return {
            "name": f"pattern-{first_file.split('/')[-1].replace('.tsx','').lower()}",
            "description": f"Files sharing structure with {first_file}",
            "when_to_use": "Follow this pattern when creating similar files",
        }


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x ** 2 for x in a) ** 0.5
    mag_b = sum(x ** 2 for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _cluster_summaries(
    summaries: list[FileSummary],
    vectors: list[list[float]],
) -> list[list[int]]:
    """
    Simple greedy clustering by cosine similarity.
    Returns a list of clusters (each cluster is a list of summary indices).
    """
    n = len(summaries)
    assigned = [False] * n
    clusters = []

    for i in range(n):
        if assigned[i]:
            continue
        cluster = [i]
        assigned[i] = True

        for j in range(i + 1, n):
            if assigned[j]:
                continue
            if _cosine_similarity(vectors[i], vectors[j]) >= SIMILARITY_THRESHOLD:
                cluster.append(j)
                assigned[j] = True

        if len(cluster) >= MIN_CLUSTER_SIZE:
            clusters.append(cluster)

    return clusters


def _centroid(vectors: list[list[float]]) -> list[float]:
    """Compute the average (centroid) vector of a cluster."""
    n   = len(vectors)
    dim = len(vectors[0])
    c   = [0.0] * dim
    for vec in vectors:
        for i, v in enumerate(vec):
            c[i] += v / n
    return c


def cluster_and_store_patterns(summaries: list[FileSummary]) -> int:
    """
    Main entry point for Phase 2b.
    Embeds summaries → clusters → names with LLM → stores in ChromaDB.
    Returns number of patterns discovered.
    """
    if not summaries:
        print("[clusterer] No summaries to cluster.")
        return 0

    provider_label = LLM_PROVIDER.capitalize()
    print(f"\n[clusterer] Embedding {len(summaries)} file summaries...")
    client = get_client()
    summary_texts = [s.summary_text for s in summaries]
    vectors = embed_texts(summary_texts, client, label="file summaries")

    print(f"\n[clusterer] Clustering by similarity (threshold={SIMILARITY_THRESHOLD})...")
    clusters = _cluster_summaries(summaries, vectors)
    print(f"            Discovered {len(clusters)} pattern groups")

    if not clusters:
        print("            No patterns found — files may be too diverse")
        return 0

    print(f"\n[clusterer] Naming patterns with {provider_label}...")
    llm_client = _get_llm_client()

    db         = get_db()
    collection = get_patterns_collection(db)

    pattern_ids       = []
    pattern_vectors   = []
    pattern_documents = []
    pattern_metadatas = []

    for idx, cluster_indices in enumerate(clusters):
        cluster_summaries = [summaries[i] for i in cluster_indices]
        cluster_vectors   = [vectors[i]   for i in cluster_indices]

        info     = _name_pattern(cluster_summaries, llm_client)
        centroid = _centroid(cluster_vectors)
        example  = cluster_summaries[0]
        files    = [s.file_path for s in cluster_summaries]

        document = (
            f"Pattern: {info['name']}\n"
            f"Description: {info['description']}\n"
            f"When to use: {info['when_to_use']}\n"
            f"Example files: {', '.join(files[:4])}\n"
            f"Example summary:\n{example.summary_text}"
        )

        metadata = {
            "pattern_name": info["name"],
            "description":  info["description"],
            "when_to_use":  info["when_to_use"],
            "file_count":   len(cluster_summaries),
            "example_file": example.file_path,
            "all_files":    ", ".join(files),
        }

        pattern_ids.append(f"pattern_{idx:03d}")
        pattern_vectors.append(centroid)
        pattern_documents.append(document)
        pattern_metadatas.append(metadata)

        print(f"  [{idx+1}/{len(clusters)}] {info['name']} ({len(cluster_summaries)} files)")

    print()
    store_patterns(collection, pattern_ids, pattern_vectors,
                   pattern_documents, pattern_metadatas)

    print(f"\n[clusterer] Phase 2b complete — {len(clusters)} patterns stored ✓")
    return len(clusters)