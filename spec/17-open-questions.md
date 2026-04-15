# 17 — Open Questions

Things we chose to defer rather than decide now. Each item lists the question, the options, and what we're provisionally doing. If none of the options bite during implementation, these stay deferred; if one does, come back here and decide.

## OQ-01 — How to handle rows that normalize to empty

**Question:** What do we do if an input row normalizes to an empty string (e.g. contains only punctuation, whitespace, or non-Latin scripts)?

**Options:**
- (A) Drop the row silently. Simplest, but violates the row-count invariant.
- (B) Drop the row with a warning in the preview response. Still violates the invariant.
- (C) Fail the preview with `input_contains_blank_rows` and require the operator to clean the file. Preserves the invariant.
- (D) Keep the row, skip clustering for it, write a specific error code in output (`blank_after_normalize`). Preserves the invariant; adds complexity.

**Provisional decision (v1):** Option C. Preserving the invariant is the load-bearing promise; asking the operator to clean a file is a reasonable cost. If this turns out to be annoying in practice, switch to D.

Ans: D

## OQ-02 — Whether to expose `max_tokens` as an Advanced knob

**Question:** The `max_tokens` parameter passed to Anthropic is computed from `titles_per_request`. Should the operator be able to override it?

**Options:**
- (A) No, compute it from TPR with generous headroom.
- (B) Yes, expose it in Advanced next to TPR.
- (C) No, but log the computed value and allow overriding via env var.

**Provisional decision:** Option A. The formula `TPR * 80 + 200` has worked for every test case so far. Exposing a sharp knob for a non-expert audience adds confusion.

Ans: B

## OQ-03 — Retry strategy when stragglers are the same IDs as last round

**Question:** If the initial batch had 20 stragglers and the retry batch returns 18 of them as stragglers again, do we halve TPR and retry, or give up on those specific IDs?

**Options:**
- (A) Always halve and retry the round budget allows, regardless of overlap.
- (B) Detect "same stragglers" and skip straight to smaller TPR or terminal failure.
- (C) Apply a jitter (reorder the titles within the request) on each retry — sometimes the same title fails because of neighbor interaction.

**Provisional decision:** Option A. Simple, bounded by `retry_round < 3`, and (C) can be added later if we see the pattern in real usage.

Ans: A

## OQ-04 — Cluster representative stability across reclusters

**Question:** When the operator changes the threshold, many clusters change shape. Is it desirable for a cluster that survives the threshold change to keep the same representative, or is it fine for it to re-pick?

**Options:**
- (A) Pure re-run — pick deterministically from the new cluster, which might differ.
- (B) Preserve the previous representative if it's still in the new cluster.

**Provisional decision:** Option A. Simplicity wins; the determinism of the pick rule means small threshold changes don't cascade wildly. If the operator complains, switch to B.

## OQ-05 — Whether to store the full rapidfuzz score matrix

**Question:** The 64MB uint8 matrix at 8k uniques is computed during preview. Do we persist it to disk so re-cluster is instant even after cache eviction, or just recompute?

**Options:**
- (A) Keep it only in-memory with an LRU, recompute on cache miss.
- (B) Pickle it to `/data/tmp/{job_id}/scores.npy` and load on cache miss.

**Provisional decision:** Option A. Recomputation is ~2 seconds; disk I/O and cleanup are not worth it at v1 scale.

## OQ-06 — Error code naming scheme

**Question:** Error codes are `snake_case` today. Should they be `kebab-case`, `UPPER_CASE`, or namespaced (`input.empty`, `batch.schema_violation`)?

**Provisional decision:** Flat `snake_case`. Matches Python idiom, easy to grep, short. If the list grows beyond 30 codes, revisit namespacing.

## OQ-07 — Whether to queue a job when another is running

**Question:** V1 refuses a second concurrent job. Should we instead queue it for automatic submission when the first finishes?

**Options:**
- (A) Refuse with 409 (current).
- (B) Queue and auto-start.

**Provisional decision:** Option A. The operator is one person; "run the second one in 10 minutes" is not a hardship, and queueing adds a tangle of state management.

## OQ-08 — Whether the Docs page should be gated behind auth

**Question:** `/docs` describes the tool's internals. Is it fine to show publicly, or should it require login?

**Provisional decision:** Gate it. The content is not secret, but there's no reason to expose the error codes and internal flow to an unauthenticated scanner. All three routes require auth.

## OQ-09 — Tool name casing in the browser tab title

**Options:** `Nomenclator`, `nomenclator`, `NOMENCLATOR`.

**Provisional decision:** `Nomenclator` — title case. The lowercase wordmark is a visual choice for the header, not for browser metadata.

## OQ-10 — Anthropic batch polling interval

**Question:** 30 seconds is chosen for polling. Is that too frequent (wasting API calls) or too slow (making small jobs feel laggy)?

**Provisional decision:** 30s for v1. Anthropic doesn't rate-limit batch-status calls. If small jobs feel slow, lower to 10s.

## OQ-11 — What to do when the operator's taxonomy contains categories the LLM never uses

**Question:** If the operator lists 20 categories but the LLM only uses 5, is that a warning?

**Provisional decision:** No. The taxonomy is an *allowed list*, not a required list. Silently fine.

## OQ-12 — What to do if a cluster's representative changes between preview and commit

**Question:** The preview and commit are separate requests. If clustering is non-deterministic, the representative could change.

**Fact check:** The representative selection is strictly deterministic (see `09b-clustering.md`). Same input + same threshold → same cluster + same rep. This OQ is only relevant if a bug is introduced.

**Provisional decision:** Add a unit test asserting determinism on a fixture. Close this OQ once the test exists.

## OQ-13 — Random sampling seed stability across reclusters

**Question:** When the operator uses `random_n` mode and then reclusters (changing threshold), should the random sample stay the same or be re-drawn?

**Provisional decision:** The sample stays the same — the seed is derived from the job ID which doesn't change during recluster. Re-drawing would be confusing because the operator already approved the sample during preview.

## OQ-14 — Should prompt review block submission if unsafe?

**Question:** If the prompt review returns `safe: false`, should the UI prevent submission, or just show a warning?

**Provisional decision:** Warning only. The operator is trusted (single shared password, internal tool). A hard block would be annoying for legitimate edge cases. The `safe` field is advisory.
