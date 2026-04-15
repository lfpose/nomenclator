from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from .unionfind import UnionFind
from .similarity import len_ratio

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
