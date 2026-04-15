# 13 — Cost Model

## Pricing assumptions (confirm at build time)

Anthropic Claude Haiku 4.5 standard pricing (as of the time this spec is written; validate on the pricing page before deploy):

- Input: ~$0.80 / million tokens
- Output: ~$4.00 / million tokens

Batch API is 50% off:

- Input (batch): ~$0.40 / million tokens
- Output (batch): ~$2.00 / million tokens

These numbers are stored as constants in `backend/app/pricing.py`:

```python
HAIKU_BATCH_IN_USD_PER_MTOK = 0.40
HAIKU_BATCH_OUT_USD_PER_MTOK = 2.00
```

Updating rates is a one-line change. All cost math reads from these constants.

## Token budgets

| Quantity | Estimate |
|---|---|
| System prompt (incl. few-shots) | ~1,300 tokens |
| User message preamble (taxonomy + scaffolding) | ~200 tokens |
| Per-title input | ~10 tokens (id + short title) |
| Per-title output | ~50 tokens (id + 3 Spanish strings + JSON overhead) |

## Estimation formula

```
request_count = ceil(cluster_count / titles_per_request)

tokens_in_per_req  = 1300 + 200 + titles_per_request * 10
tokens_out_per_req = titles_per_request * 50 + 50   # +50 JSON overhead

total_in  = request_count * tokens_in_per_req
total_out = request_count * tokens_out_per_req

est_cost_usd = (total_in  / 1_000_000 * HAIKU_BATCH_IN_USD_PER_MTOK) +
               (total_out / 1_000_000 * HAIKU_BATCH_OUT_USD_PER_MTOK)
```

### Worked example

2,500 clusters, `titles_per_request = 25`:

- request_count = 100
- tokens_in_per_req = 1300 + 200 + 250 = 1,750
- tokens_out_per_req = 1,250 + 50 = 1,300
- total_in = 175,000 = 0.175 M
- total_out = 130,000 = 0.130 M
- cost = 0.175 × 0.40 + 0.130 × 2.00 = 0.07 + 0.26 = **$0.33**

### Sanity bounds

| Cluster count | TPR | Est cost |
|---|---|---|
| 1,000 | 25 | ~$0.14 |
| 2,500 | 25 | ~$0.33 |
| 5,000 | 25 | ~$0.65 |
| 10,000 | 25 | ~$1.30 |
| 2,500 | 10 | ~$0.50 |
| 2,500 | 50 | ~$0.25 |

All within the $20/month cap with room to spare.

## Actual cost recording

When Anthropic returns batch results, each result line includes usage statistics (`input_tokens`, `output_tokens`) per request. The worker sums these across all requests in a batch, applies the per-token rates, and writes a `spend_log` row:

```sql
INSERT INTO spend_log (job_id, batch_id, usd, at)
VALUES (?, ?, ?, ?);
```

One row per batch (initial or retry). The `at` is the time of batch completion, not submission — we want the cap to reflect actual usage, and a cancelled-before-completion batch should contribute $0.

## Monthly cap enforcement

### Where it runs

1. **At commit** (HTTP handler): `est_cost` is computed from cluster count and the formula above. Sum of `spend_log.usd WHERE at > now - 30d` is fetched. If sum + est > $20, return 409 `spend_cap_exceeded`.
2. **At retry submission** (background worker): same check. If it would exceed, don't submit; flag remaining stragglers with `error = spend_cap_exceeded` and transition the job to `completed`.

### The 30-day window

Rolling. Uses a `WHERE at > :thirty_days_ago` filter, not calendar months. Simpler to reason about, no edge-of-month surprises. The error message includes the `reset_date` as "the date when the oldest contributing row drops out of the window" — approximately `min(spend_log.at) + 30d` for rows still within the window.

### Hard $20 ceiling

Defined as `MONTHLY_SPEND_CAP_USD = 20.0` in `settings.py`. Overridable via env var `MONTHLY_SPEND_CAP_USD`. Default stays 20 in v1.

### What the cap does NOT protect against

- Anthropic changing prices mid-month without us updating constants. The estimate becomes stale; the recorded actual cost uses our constants too, so `spend_log` could under-report. **Mitigation:** a periodic manual review of the Anthropic billing dashboard.
- Batch requests with runaway outputs (e.g. model ignores `max_tokens`). Unlikely with forced tool use, but possible. **Mitigation:** per-request `max_tokens` is always set explicitly.
- A bug in our estimation formula that makes commits incorrectly approved. **Mitigation:** unit tests on `estimate_cost` with known fixtures.

## Estimation accuracy

Estimate vs actual typically within ±20% for our use case. The estimate is intentionally conservative on both sides so the cap is not gamed.

## Prompt review cost

The prompt review endpoint makes a single non-batch call to Claude Haiku:
- Input: ~800 tokens (meta-prompt + operator prompt + few-shots)
- Output: ~200 tokens (structured review)
- Cost per review: ~$0.001 at standard Haiku rates ($0.80/MTok in, $4/MTok out)

This cost is **not** tracked in `spend_log` and does **not** count toward the $20 monthly cap. It's negligible and independent of the batch pipeline.

## Dry-run cost

Dry-run jobs incur zero Anthropic cost. No API calls are made. The spend log records $0 for dry-run batches. Dry-run jobs are excluded from the cap check entirely — they don't even run the check.

## Row subset cost

Partial runs (row_subset_mode != 'all') cost proportionally less since fewer clusters are processed. The cost estimate shown in the preview panel reflects the actual subset size, not the full input.

## Cost visibility in the UI

- Preview panel shows the estimate prominently next to the cluster count.
- Job status panel shows both `est` and `actual` once any batch completes.
- History list shows `actual` for completed jobs and `est` for in-flight ones.
- A footer line on the Tool page shows the rolling spend: "Spent this month: $3.42 / $20.00" pulled from `GET /spend`.

## `/spend` endpoint (additional)

```
GET /spend
→ {
  "used_usd": 3.42,
  "cap_usd": 20.00,
  "window_days": 30,
  "reset_date": "2026-05-04"
}
```

Public via session; no sensitive data. Called on Tool page load and after each job completes.
