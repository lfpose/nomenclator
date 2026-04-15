"""Pricing and cost estimation for Anthropic batch API."""

import math

HAIKU_BATCH_IN_USD_PER_MTOK = 0.40
HAIKU_BATCH_OUT_USD_PER_MTOK = 2.00

SYSTEM_PROMPT_TOKENS = 1300
USER_PREAMBLE_TOKENS = 200
IN_TOKENS_PER_TITLE = 10
OUT_TOKENS_PER_TITLE = 50
OUTPUT_OVERHEAD_TOKENS = 50

MONTHLY_SPEND_CAP_USD = 20.0


def estimate_cost(cluster_count: int, titles_per_request: int) -> float:
    """Estimate cost in USD for processing cluster_count titles via Anthropic batch API.

    Args:
        cluster_count: Number of unique clusters to process
        titles_per_request: Number of titles per batch request (titles_per_request in DB)

    Returns:
        Estimated cost in USD
    """
    if cluster_count <= 0 or titles_per_request <= 0:
        return 0.0

    request_count = math.ceil(cluster_count / titles_per_request)
    tokens_in_per_req = SYSTEM_PROMPT_TOKENS + USER_PREAMBLE_TOKENS + titles_per_request * IN_TOKENS_PER_TITLE
    tokens_out_per_req = titles_per_request * OUT_TOKENS_PER_TITLE + OUTPUT_OVERHEAD_TOKENS
    total_in = request_count * tokens_in_per_req
    total_out = request_count * tokens_out_per_req

    return (
        total_in / 1_000_000 * HAIKU_BATCH_IN_USD_PER_MTOK
        + total_out / 1_000_000 * HAIKU_BATCH_OUT_USD_PER_MTOK
    )
