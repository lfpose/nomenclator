from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .unionfind import UnionFind
from .similarity import len_ratio, compute_similarity
from .embeddings import embed_titles, cosine_similarity_matrix
from ..csv_io.normalize import normalize

if TYPE_CHECKING:
    import numpy as np


def build_components(
    strings: list[str],
    matrix: "np.ndarray",
    threshold: int,
    min_len_ratio: float = 0.6,
) -> dict[int, list[int]]:
    n = len(strings)
    uf = UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j] >= threshold and len_ratio(strings[i], strings[j]) >= min_len_ratio:
                uf.union(i, j)
    return uf.components()


def build_components_embeddings(
    matrix: "np.ndarray",
    threshold: int,
) -> dict[int, list[int]]:
    """Like build_components but without the len_ratio guard (not meaningful for embeddings)."""
    n = matrix.shape[0]
    uf = UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j] >= threshold:
                uf.union(i, j)
    return uf.components()


def pick_representative(originals: list[str]) -> str:
    """
    Pick a representative from a cluster of original (un-normalized) titles.

    Tiebreak rules (in order):
    1. Most frequent (highest count)
    2. Shortest length
    3. Alphabetical order
    """
    counts = Counter(originals)
    max_count = max(counts.values())
    candidates = [s for s, c in counts.items() if c == max_count]
    min_len = min(len(s) for s in candidates)
    candidates = [s for s in candidates if len(s) == min_len]
    return sorted(candidates)[0]


def _sim_to_rep(norm: str, rep_norm: str, strings: list[str], matrix: "np.ndarray | None") -> float:
    """Return similarity (0-100) of `norm` to `rep_norm` using the precomputed matrix or rapidfuzz."""
    if norm == rep_norm:
        return 100.0
    if matrix is not None:
        try:
            i = strings.index(norm)
            j = strings.index(rep_norm)
            return float(matrix[i][j])
        except ValueError:
            pass
    from rapidfuzz import fuzz
    return float(fuzz.token_set_ratio(norm, rep_norm))


@dataclass(frozen=True)
class ClusterResult:
    """Result of clustering a set of rows."""
    cluster_id: int
    representative_original: str
    normalized_key: str
    member_row_indices: list[int]
    member_count: int
    norm_to_sim: dict[str, float] = field(default_factory=dict)
    """Maps normalized unique title → similarity to representative (0–100)."""


def compute_embeddings_for_rows(
    rows: list[tuple[int, str, str]],
    openai_api_key: str,
) -> tuple[list[str], "np.ndarray"]:
    """Extract unique normalized titles from rows and embed them. Returns (uniques, embeddings)."""
    seen: dict[str, None] = {}
    for _, _, norm in rows:
        seen[norm] = None
    uniques = list(seen.keys())
    if not uniques:
        import numpy as np
        return [], np.empty((0, 0), dtype="float32")
    emb = embed_titles(uniques, openai_api_key)
    return uniques, emb


def _free_cluster_results(
    free_uniques: list[str],
    by_norm: dict[str, list[int]],
    by_norm_original: dict[str, list[str]],
    threshold: int,
    openai_api_key: str,
    free_emb: "np.ndarray | None",
    start_cid: int,
) -> list[ClusterResult]:
    if not free_uniques:
        return []

    if openai_api_key and free_emb is not None:
        import numpy as np
        n_f = np.linalg.norm(free_emb, axis=1, keepdims=True)
        normed_f = free_emb / np.where(n_f == 0, 1.0, n_f)
        free_matrix = (normed_f @ normed_f.T * 100).astype(np.float32)
        comps = build_components_embeddings(free_matrix, threshold)
    else:
        free_matrix = compute_similarity(free_uniques, score_cutoff=0)
        comps = build_components(free_uniques, free_matrix, threshold)

    results: list[ClusterResult] = []
    cid = start_cid
    norm_to_idx = {u: i for i, u in enumerate(free_uniques)}
    for _, indices in sorted(comps.items()):
        member_norms = [free_uniques[i] for i in indices]
        member_row_indices: list[int] = []
        all_originals: list[str] = []
        for norm in member_norms:
            member_row_indices.extend(by_norm[norm])
            all_originals.extend(by_norm_original[norm])
        rep = pick_representative(all_originals)
        rep_norm = normalize(rep)
        rep_idx = norm_to_idx.get(rep_norm)
        norm_to_sim: dict[str, float] = {}
        for i in indices:
            n = free_uniques[i]
            if rep_idx is not None and free_matrix is not None:
                norm_to_sim[n] = float(free_matrix[i][rep_idx])
            else:
                from rapidfuzz import fuzz
                norm_to_sim[n] = 100.0 if n == rep_norm else float(fuzz.token_set_ratio(n, rep_norm))
        results.append(ClusterResult(
            cluster_id=cid,
            representative_original=rep,
            normalized_key=normalize(rep),
            member_row_indices=sorted(member_row_indices),
            member_count=len(member_row_indices),
            norm_to_sim=norm_to_sim,
        ))
        cid += 1
    return results


def _run_seeded_clustering(
    uniques: list[str],
    by_norm: dict[str, list[int]],
    by_norm_original: dict[str, list[str]],
    canonical_titles: list[str],
    threshold: int,
    openai_api_key: str,
    uniq_emb: "np.ndarray | None" = None,
) -> list[ClusterResult]:
    canonical_norms = [normalize(c) for c in canonical_titles]
    n_can = len(canonical_norms)
    free_emb: "np.ndarray | None" = None

    if openai_api_key:
        import numpy as np
        if uniq_emb is None:
            all_emb = embed_titles(canonical_norms + uniques, openai_api_key)
            can_emb = all_emb[:n_can]
            uniq_emb = all_emb[n_can:]
        else:
            # Only embed canonicals; reuse cached uniq_emb
            can_emb = embed_titles(canonical_norms, openai_api_key)

        norms_u = np.linalg.norm(uniq_emb, axis=1, keepdims=True)
        norms_c = np.linalg.norm(can_emb, axis=1, keepdims=True)
        normed_u = uniq_emb / np.where(norms_u == 0, 1.0, norms_u)
        normed_c = can_emb / np.where(norms_c == 0, 1.0, norms_c)
        sim = (normed_u @ normed_c.T * 100).astype(np.float32)  # (n_uniq, n_can)

        best_can_indices = sim.argmax(axis=1).tolist()
        best_sims = sim.max(axis=1).tolist()
    else:
        from rapidfuzz import process, fuzz
        best_can_indices = []
        best_sims = []
        for unique in uniques:
            result = process.extractOne(
                unique,
                canonical_norms,
                scorer=fuzz.token_set_ratio,
            )
            if result is not None:
                best_can_indices.append(result[2])
                best_sims.append(float(result[1]))
            else:
                best_can_indices.append(0)
                best_sims.append(0.0)

    canonical_members: dict[int, list[int]] = {}
    free_indices: list[int] = []
    for u_idx, (can_idx, s) in enumerate(zip(best_can_indices, best_sims)):
        if s >= threshold:
            canonical_members.setdefault(can_idx, []).append(u_idx)
        else:
            free_indices.append(u_idx)

    results: list[ClusterResult] = []
    cid = 0

    for can_idx, u_indices in sorted(canonical_members.items()):
        member_row_indices: list[int] = []
        norm_to_sim: dict[str, float] = {}
        for u_idx in u_indices:
            member_row_indices.extend(by_norm[uniques[u_idx]])
            norm_to_sim[uniques[u_idx]] = round(float(best_sims[u_idx]), 1)
        results.append(ClusterResult(
            cluster_id=cid,
            representative_original=canonical_titles[can_idx],
            normalized_key=normalize(canonical_titles[can_idx]),
            member_row_indices=sorted(member_row_indices),
            member_count=len(member_row_indices),
            norm_to_sim=norm_to_sim,
        ))
        cid += 1

    free_uniques = [uniques[i] for i in free_indices]
    if uniq_emb is not None and free_indices:
        import numpy as np
        free_emb = uniq_emb[np.array(free_indices)]
    free_results = _free_cluster_results(
        free_uniques, by_norm, by_norm_original, threshold, openai_api_key, free_emb, cid
    )
    results.extend(free_results)
    return results


def run_clustering(
    rows: list[tuple[int, str, str]],  # (row_index, original, normalized)
    threshold: int,
    openai_api_key: str = "",
    canonical_titles: list[str] | None = None,
    precomputed_uniques: list[str] | None = None,
    precomputed_embeddings: "np.ndarray | None" = None,
) -> list[ClusterResult]:
    """
    Run the full clustering pipeline on ingested rows.

    Args:
        rows: (row_index, original, normalized) tuples from ingestion
        threshold: Minimum similarity score (0-100) for clustering
        openai_api_key: If set, use OpenAI embeddings instead of rapidfuzz
        canonical_titles: If provided, use seeded clustering
        precomputed_uniques: Cached unique normalized titles (from prior preview)
        precomputed_embeddings: Cached embedding matrix matching precomputed_uniques
    """
    by_norm: dict[str, list[int]] = {}
    by_norm_original: dict[str, list[str]] = {}
    for row_idx, original, norm in rows:
        by_norm.setdefault(norm, []).append(row_idx)
        by_norm_original.setdefault(norm, []).append(original)

    uniques = list(by_norm.keys())
    if not uniques:
        return []

    # Resolve embeddings — use cache if it matches current uniques
    uniq_emb: "np.ndarray | None" = None
    if openai_api_key:
        if precomputed_uniques == uniques and precomputed_embeddings is not None:
            uniq_emb = precomputed_embeddings
        else:
            uniq_emb = embed_titles(uniques, openai_api_key)

    if canonical_titles:
        return _run_seeded_clustering(
            uniques, by_norm, by_norm_original,
            canonical_titles, threshold, openai_api_key, uniq_emb=uniq_emb,
        )

    # Free clustering
    if openai_api_key and uniq_emb is not None:
        matrix = cosine_similarity_matrix(uniq_emb)
        comps = build_components_embeddings(matrix, threshold)
    else:
        matrix = compute_similarity(uniques, score_cutoff=0)
        comps = build_components(uniques, matrix, threshold)

    norm_to_idx = {u: i for i, u in enumerate(uniques)}
    results: list[ClusterResult] = []
    for cid, (root, indices) in enumerate(sorted(comps.items())):
        member_norms = [uniques[i] for i in indices]
        member_row_indices: list[int] = []
        all_originals: list[str] = []
        for norm in member_norms:
            member_row_indices.extend(by_norm[norm])
            all_originals.extend(by_norm_original[norm])
        rep = pick_representative(all_originals)
        rep_norm = normalize(rep)
        rep_idx = norm_to_idx.get(rep_norm)
        norm_to_sim: dict[str, float] = {}
        for i in indices:
            n = uniques[i]
            if rep_idx is not None:
                norm_to_sim[n] = round(float(matrix[i][rep_idx]), 1)
            else:
                from rapidfuzz import fuzz
                norm_to_sim[n] = 100.0 if n == rep_norm else round(float(fuzz.token_set_ratio(n, rep_norm)), 1)
        results.append(ClusterResult(
            cluster_id=cid,
            representative_original=rep,
            normalized_key=normalize(rep),
            member_row_indices=sorted(member_row_indices),
            member_count=len(member_row_indices),
            norm_to_sim=norm_to_sim,
        ))
    return results
