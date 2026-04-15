# 04 — Clustering Pipeline

Reference: `spec/09b-clustering.md`. Every task here is pure logic — no I/O, no DB, no network. Fully unit-testable.

---

### P04-01 — Union-Find data structure

**Deps:** P01-02
**Files:** `backend/app/cluster/unionfind.py`, `backend/tests/cluster/test_unionfind.py`
**Goal:** Hand-rolled union-find with path compression and union-by-rank.

**Implementation:**
```python
class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def components(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = {}
        for i in range(len(self.parent)):
            out.setdefault(self.find(i), []).append(i)
        return out
```

**Test:** `cd backend && uv run pytest tests/cluster/test_unionfind.py -v`

Required assertions:
- `test_find_on_singleton_returns_self`
- `test_union_merges_roots`
- `test_components_on_disjoint_graph` — 5 singletons → 5 components.
- `test_components_on_chain` — `union(0,1); union(1,2); union(2,3)` → 1 component of size 4.
- `test_union_idempotent` — `union(0,1); union(0,1)` → 1 component.
- `test_components_deterministic_output` — same input → same dict.
- `test_large_union_find_1000_elements_under_10ms`

**Done when:**
- [ ] All 7 tests pass.

---

### P04-02 — Length ratio helper

**Deps:** P01-02
**Files:** `backend/app/cluster/similarity.py`, `backend/tests/cluster/test_similarity.py`
**Goal:** Pure function `len_ratio(a: str, b: str) -> float`.

**Implementation:**
```python
def len_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    la, lb = len(a), len(b)
    return min(la, lb) / max(la, lb)
```

**Test:** `cd backend && uv run pytest tests/cluster/test_similarity.py::test_len_ratio -v`

Required assertions:
- `test_len_ratio_identical_strings_returns_1`
- `test_len_ratio_half_length_returns_half`
- `test_len_ratio_empty_string_returns_0`
- `test_len_ratio_symmetric` — `len_ratio(a, b) == len_ratio(b, a)` for 20 random pairs.

**Done when:**
- [ ] All 4 tests pass.

---

### P04-03 — Similarity matrix with rapidfuzz

**Deps:** P04-02
**Files:** `backend/app/cluster/similarity.py` (extend), `backend/tests/cluster/test_similarity.py` (extend)
**Goal:** Compute the token_set_ratio similarity matrix for a list of normalized strings.

**Implementation:**
```python
import numpy as np
from rapidfuzz import process, fuzz

def compute_similarity(
    strings: list[str], score_cutoff: int = 0
) -> np.ndarray:
    return process.cdist(
        strings,
        strings,
        scorer=fuzz.token_set_ratio,
        score_cutoff=score_cutoff,
        dtype=np.uint8,
    )
```

**Test:** `cd backend && uv run pytest tests/cluster/test_similarity.py::test_compute_similarity -v`

Required assertions:
- `test_compute_similarity_shape_is_NxN`
- `test_diagonal_is_100` — `matrix[i][i] == 100` for all i.
- `test_symmetric` — `matrix[i][j] == matrix[j][i]` for all pairs.
- `test_jefe_compras_scores_above_90` — `["jefe compras", "jefe de compras"]` → `matrix[0][1] >= 90`.
- `test_product_vs_project_manager_scores_below_85` — distinct titles should not trip threshold 90.

**Done when:**
- [ ] All 5 tests pass.

---

### P04-04 — Connected components from similarity

**Deps:** P04-01, P04-03
**Files:** `backend/app/cluster/pipeline.py`, `backend/tests/cluster/test_pipeline.py`
**Goal:** Given a similarity matrix and a threshold, build connected components with the length-ratio gate.

**Implementation:**
```python
from .unionfind import UnionFind
from .similarity import len_ratio

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
```

**Test:** `cd backend && uv run pytest tests/cluster/test_pipeline.py::test_build_components -v`

Required assertions:
- `test_build_components_singleton_input` — 1 string → 1 component of size 1.
- `test_build_components_two_similar_merged` — `["jefe compras", "jefe de compras"]` → 1 component.
- `test_build_components_two_unrelated_separate` — `["jefe compras", "director ventas"]` → 2 components.
- `test_build_components_length_ratio_blocks_merge` — `["jefe", "jefe de operaciones internacionales"]` → 2 components even if token_set_ratio > threshold.
- `test_build_components_transitive_merging` — `a~b, b~c → {a,b,c}` one component.

**Done when:**
- [ ] All 5 tests pass.

---

### P04-05 — Representative selection

**Deps:** P01-02
**Files:** `backend/app/cluster/pipeline.py` (extend), `backend/tests/cluster/test_pipeline.py` (extend)
**Goal:** Deterministic representative picker.

**Implementation:**
```python
from collections import Counter

def pick_representative(originals: list[str]) -> str:
    """originals: list of original (un-normalized) titles in this cluster."""
    counts = Counter(originals)
    max_count = max(counts.values())
    candidates = [s for s, c in counts.items() if c == max_count]
    # tiebreak: shortest length
    min_len = min(len(s) for s in candidates)
    candidates = [s for s in candidates if len(s) == min_len]
    # tiebreak: alphabetical
    return sorted(candidates)[0]
```

**Test:** `cd backend && uv run pytest tests/cluster/test_pipeline.py::test_pick_representative -v`

Required assertions:
- `test_pick_representative_most_frequent_wins`
- `test_pick_representative_tiebreak_shortest` — two items at same count → shorter wins.
- `test_pick_representative_tiebreak_alphabetical` — same count same length → alphabetical.
- `test_pick_representative_determinism` — running twice on same input gives same result.
- `test_pick_representative_singleton` — single-item cluster returns that item.

**Done when:**
- [ ] All 5 tests pass.

---

### P04-06 — Full cluster pipeline wrapper

**Deps:** P04-01..P04-05, P03-04
**Files:** `backend/app/cluster/pipeline.py` (extend), `backend/tests/cluster/test_pipeline.py` (extend)
**Goal:** Top-level `run_clustering` function that takes ingested rows and a threshold, returns cluster assignments.

**Implementation:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ClusterResult:
    cluster_id: int  # synthetic 0-based index
    representative_original: str
    normalized_key: str
    member_row_indices: list[int]  # indices into the input rows list
    member_count: int

def run_clustering(
    rows: list[tuple[int, str, str]],  # (row_index, original, normalized)
    threshold: int,
) -> list[ClusterResult]:
    # Exact dedup: map normalized -> list of row indices
    by_norm: dict[str, list[int]] = {}
    by_norm_original: dict[str, list[str]] = {}
    for row_idx, original, norm in rows:
        by_norm.setdefault(norm, []).append(row_idx)
        by_norm_original.setdefault(norm, []).append(original)

    uniques = list(by_norm.keys())
    if not uniques:
        return []

    matrix = compute_similarity(uniques, score_cutoff=0)
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
        # normalized_key = normalized form of the rep
        from ..csv_io.normalize import normalize
        results.append(ClusterResult(
            cluster_id=cid,
            representative_original=rep,
            normalized_key=normalize(rep),
            member_row_indices=sorted(member_row_indices),
            member_count=len(member_row_indices),
        ))
    return results
```

**Test:** `cd backend && uv run pytest tests/cluster/test_pipeline.py::test_run_clustering -v`

Required assertions:
- `test_run_clustering_empty_returns_empty`
- `test_run_clustering_all_identical_returns_one_cluster` — 5 rows, all same normalized → 1 cluster with member_count=5.
- `test_run_clustering_jefe_compras_variants_merged` — fixture with 3 variants at threshold 90 → 1 cluster.
- `test_run_clustering_unrelated_titles_separate` — 3 unrelated → 3 clusters.
- `test_run_clustering_assigns_all_rows_to_some_cluster` — sum of member_counts == len(input).
- `test_run_clustering_row_indices_complete_and_non_overlapping`

**Done when:**
- [ ] All 6 tests pass.

---

### P04-07 — Determinism guarantee

**Deps:** P04-06
**Files:** `backend/tests/cluster/test_determinism.py`
**Goal:** Prove determinism on a realistic input.

**Implementation:**
Generate 500 synthetic Spanish job titles with variants. Run `run_clustering` twice. Assert the two results are byte-identical (same clusters, same representatives, same order).

**Test:** `cd backend && uv run pytest tests/cluster/test_determinism.py -v`

Required assertions:
- `test_run_clustering_deterministic_same_input` — run twice, compare `list[ClusterResult]` equal.
- `test_run_clustering_deterministic_shuffled_input` — shuffle the input rows (preserving row_index), re-run, assert same clusters (members may differ in order inside each cluster but the partition is identical).

**Done when:**
- [ ] Both tests pass.

---

### P04-08 — Performance guard

**Deps:** P04-06
**Files:** `backend/tests/cluster/test_performance.py`
**Goal:** Ensure clustering latency is within budget.

**Implementation:**
Generate 8,000 unique synthetic Spanish job titles. Time `run_clustering`. Assert under 5 seconds.

**Test:** `cd backend && uv run pytest tests/cluster/test_performance.py -v`

Required assertions:
- `test_clustering_8k_uniques_under_5s`

**Done when:**
- [ ] Test passes on the CI/dev machine.
