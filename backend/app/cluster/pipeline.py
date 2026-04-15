from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .unionfind import UnionFind
from .similarity import len_ratio, compute_similarity
from ..csv_io.normalize import normalize

if TYPE_CHECKING:
    import numpy as np


def build_components(
    strings: list[str],
    matrix: "np.ndarray",
    threshold: int,
    min_len_ratio: float = 0.6,
) -> dict[int, list[int]]:
    """
    Build connected components from a similarity matrix.

    Pairs are merged if BOTH conditions hold:
    1. Similarity score >= threshold
    2. Length ratio >= min_len_ratio (default 0.6)

    Args:
        strings: List of normalized strings
        matrix: NxN similarity matrix from compute_similarity
        threshold: Minimum similarity score (0-100) to consider merging
        min_len_ratio: Minimum length ratio (0-1) to consider merging

    Returns:
        Dictionary mapping root index -> list of member indices
    """
    n = len(strings)
    uf = UnionFind(n)

    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j] >= threshold and len_ratio(strings[i], strings[j]) >= min_len_ratio:
                uf.union(i, j)

    return uf.components()


def pick_representative(originals: list[str]) -> str:
    """
    Pick a representative from a cluster of original (un-normalized) titles.

    Tiebreak rules (in order):
    1. Most frequent (highest count)
    2. Shortest length
    3. Alphabetical order

    Args:
        originals: List of original (un-normalized) titles in this cluster

    Returns:
        The representative title string
    """
    counts = Counter(originals)
    max_count = max(counts.values())
    candidates = [s for s, c in counts.items() if c == max_count]
    # Tiebreak: shortest length
    min_len = min(len(s) for s in candidates)
    candidates = [s for s in candidates if len(s) == min_len]
    # Tiebreak: alphabetical
    return sorted(candidates)[0]


@dataclass(frozen=True)
class ClusterResult:
    """Result of clustering a set of rows."""
    cluster_id: int  # synthetic 0-based index
    representative_original: str
    normalized_key: str
    member_row_indices: list[int]  # indices into the input rows list
    member_count: int


def run_clustering(
    rows: list[tuple[int, str, str]],  # (row_index, original, normalized)
    threshold: int,
) -> list[ClusterResult]:
    """
    Run the full clustering pipeline on ingested rows.

    Args:
        rows: List of (row_index, original, normalized) tuples from CSV ingestion
        threshold: Minimum similarity score (0-100) for clustering

    Returns:
        List of ClusterResult objects, one per cluster
    """
    # Exact dedup: map normalized -> list of row indices and originals
    by_norm: dict[str, list[int]] = {}
    by_norm_original: dict[str, list[str]] = {}
    for row_idx, original, norm in rows:
        by_norm.setdefault(norm, []).append(row_idx)
        by_norm_original.setdefault(norm, []).append(original)

    uniques = list(by_norm.keys())
    if not uniques:
        return []

    matrix = compute_similarity(uniques, score_cutoff=threshold)
    comps = build_components(uniques, matrix, threshold)

    results: list[ClusterResult] = []
    for cid, (root, indices) in enumerate(sorted(comps.items())):
        member_norms = [uniques[i] for i in indices]
        member_row_indices: list[int] = []
        all_originals: list[str] = []
        for norm in member_norms:
            member_row_indices.extend(by_norm[norm])
            all_originals.extend(by_norm_original[norm])
        rep = pick_representative(all_originals)
        results.append(ClusterResult(
            cluster_id=cid,
            representative_original=rep,
            normalized_key=normalize(rep),
            member_row_indices=sorted(member_row_indices),
            member_count=len(member_row_indices),
        ))
    return results
