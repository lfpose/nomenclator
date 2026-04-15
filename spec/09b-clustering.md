# 09b — Clustering

Reference: diagram 6 (pipeline) and 6b (internals) in `solution-overview.md`. This file is the complete algorithm spec, including why each choice was made, defaults, tunables, guardrails, and expected performance.

## Why clustering exists

The LLM is not deterministic across batches. Sending "Jefe Compras" in one batch and "Jefe de Compras" in another will produce divergent Spanish standardizations, silently defeating the whole point of the tool (producing a canonical smaller space). Clustering resolves each group of near-duplicates as a single representative, then propagates that answer to every member. Consistency is the dominant reason. Cost reduction is a secondary benefit.

## Pipeline

```
input rows
  → normalize
  → exact dedup (bucket by normalized string)
  → fuzzy similarity (token_set_ratio, all-vs-all on unique normalized strings)
  → threshold + length-ratio gate
  → union-find connected components
  → pick representative per component
  → write clusters table + cluster_id onto job_rows
```

## Normalization (already specified in 09-csv-spec.md)

Strip accents, lowercase, drop punctuation except inner hyphens, collapse whitespace. Result stored on `job_rows.normalized`.

## Exact dedup

Group `job_rows` by `normalized`. Every group becomes a single input to the fuzzy comparison step. After this, clustering operates on **unique normalized strings**, not rows.

In practice this reduces 16,000 raw rows to ~8,000 unique normalized strings before any expensive computation.

## Similarity computation

```python
from rapidfuzz import process, fuzz, utils

unique_normalized: list[str] = [...]    # after exact dedup
N = len(unique_normalized)

scores = process.cdist(
    unique_normalized,
    unique_normalized,
    scorer=fuzz.token_set_ratio,
    processor=None,    # we already normalized
    score_cutoff=threshold,
    dtype=np.uint8,
)
# scores is an NxN uint8 matrix, 0 where below threshold
```

At N=8,000: 64 million comparisons. rapidfuzz's C backend handles this in ~2 seconds on a modest Fly machine. Memory: 64 MB for the uint8 matrix. Both within budget.

For N > 20,000 the all-vs-all cost grows quadratically. V1 simply accepts the cost up to the 50k hard cap. If performance becomes a problem, switch to `process.extract` with a blocking step (first 2 characters as a hash bucket).

## Threshold gate

A pair `(i, j)` is considered for merging iff **both** conditions hold:

1. `scores[i][j] >= threshold` (default 90, configurable 50–100)
2. `len_ratio(unique_normalized[i], unique_normalized[j]) >= 0.6`

Where `len_ratio(a, b) = min(len(a), len(b)) / max(len(a), len(b))`.

The length-ratio guard is mandatory. Without it, `"Jefe"` and `"Jefe de Compras Internacionales del Grupo Sura"` can pass `token_set_ratio` because both contain "jefe" and the set comparison is asymmetric in the shorter string's favor. The guard is 0.6, not 0.5, because 0.5 still admits some uncomfortable pairs in testing.

## Connected components (union-find)

```python
class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # path compression
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

uf = UnionFind(N)
for i in range(N):
    for j in range(i + 1, N):
        if scores[i][j] >= threshold and len_ratio(unique_normalized[i], unique_normalized[j]) >= 0.6:
            uf.union(i, j)

components: dict[int, list[int]] = {}
for i in range(N):
    components.setdefault(uf.find(i), []).append(i)
```

Union-find is chosen over `networkx` for zero dependencies and tight performance. `networkx` is an 8 MB package; union-find is 20 lines.

## Representative selection (deterministic)

For each component, we pick the representative as follows:

1. Within the component, look at all original (un-normalized) titles from `job_rows` mapped to this component.
2. Count occurrences of each distinct `original`. **Highest count wins.**
3. Tie-break: **shortest length** of `original`.
4. Tie-break: **alphabetically first** `original`.

This is fully deterministic. Same input, same threshold → same representative every time. Critical because the cluster preview the operator approves must be the same cluster structure that runs.

## Writing clusters

```python
# For each component:
rep = pick_representative(component)
cursor.execute("""
  INSERT INTO clusters (job_id, representative_original, normalized_key, member_count, retry_count)
  VALUES (?, ?, ?, ?, 0)
""", (job_id, rep.original, rep.normalized, len(component_row_ids)))
cluster_id = cursor.lastrowid

# Update all job_rows in this component to point at cluster_id
cursor.executemany("""
  UPDATE job_rows SET cluster_id = ?, is_representative = (id == ?) WHERE id = ?
""", [(cluster_id, rep.row_id, row_id) for row_id in component_row_ids])
```

## Re-clustering on threshold change

`POST /jobs/:id/recluster { threshold }`:

1. Validate state == `preview` and threshold in [50, 100].
2. `DELETE FROM clusters WHERE job_id = :job_id`.
3. `UPDATE job_rows SET cluster_id = NULL, is_representative = 0 WHERE job_id = :job_id`.
4. Re-run the similarity + union-find + representative pick with the new threshold. The `unique_normalized` list is still in-memory from the previous run (cached per-job), so step is fast.
5. Re-compute cost estimate from the new cluster count.
6. Respond with updated preview payload.

The cached `unique_normalized` (and optionally the scores matrix if RAM allows) lives in an in-process LRU keyed by `job_id`, evicted after 1 hour or on server restart. If a re-cluster arrives for an evicted cache, re-normalize from `job_rows` — still fast.

## Cost estimation

```python
titles_per_request = job.titles_per_request  # default 25
request_count = math.ceil(cluster_count / titles_per_request)
tokens_per_request_in = SYSTEM_PROMPT_TOKENS + FEW_SHOT_TOKENS + titles_per_request * IN_TOKENS_PER_TITLE
tokens_per_request_out = titles_per_request * OUT_TOKENS_PER_TITLE + OVERHEAD
total_in = request_count * tokens_per_request_in
total_out = request_count * tokens_per_request_out

cost_usd = (total_in / 1_000_000 * HAIKU_BATCH_IN_USD_PER_MTOK
          + total_out / 1_000_000 * HAIKU_BATCH_OUT_USD_PER_MTOK)
```

Constants live in a single `pricing.py` module and are easy to update when Anthropic changes rates. See `13-cost-model.md`.

## Preview output

The preview response returns:

- `total_rows` — raw input count.
- `exact_unique_rows` — count after exact dedup.
- `cluster_count` — count after fuzzy clustering.
- `largest_cluster_size` — max `member_count`.
- `est_cost_usd` — from the formula above.
- `top_clusters` — the 10 largest clusters, each with `representative`, `member_count`, and the full `members` list (capped at 50 members shown per cluster).

If any cluster has `member_count > 50`, the preview response carries a `warnings` array with entries like `{"type": "large_cluster", "cluster_id": ..., "member_count": 87}`.

## Expected numbers (for sanity)

Starting from a real 13,600-row LinkedIn dump in Spanish:

| Stage | Count |
|---|---|
| Input rows | 13,600 |
| After exact dedup | ~8,000 |
| At threshold 90 | ~2,500 clusters |
| At threshold 95 | ~4,000 clusters |
| Largest cluster | typically 40–100 members for top Spanish titles |

Clustering latency: ~2s total at 8k uniques. Under 10s is the hard ceiling for the preview UI to feel instant.
