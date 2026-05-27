import numpy as np
from openai import OpenAI

_EMBED_MODEL = "text-embedding-3-small"
_BATCH_SIZE = 2048


def embed_titles(titles: list[str], api_key: str) -> np.ndarray:
    """Embed a list of titles using OpenAI text-embedding-3-small.

    Returns an (N, D) float32 array of embeddings.
    """
    client = OpenAI(api_key=api_key)
    all_embeddings: list[list[float]] = []
    for i in range(0, len(titles), _BATCH_SIZE):
        batch = titles[i : i + _BATCH_SIZE]
        response = client.embeddings.create(model=_EMBED_MODEL, input=batch)
        ordered = sorted(response.data, key=lambda e: e.index)
        all_embeddings.extend(e.embedding for e in ordered)
    return np.array(all_embeddings, dtype=np.float32)


def cosine_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """Compute an NxN cosine similarity matrix scaled to 0–100 (float32)."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    normed = embeddings / norms
    return (normed @ normed.T * 100).astype(np.float32)
