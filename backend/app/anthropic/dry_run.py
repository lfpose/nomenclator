from .models import ToolOutput, TitleResult


def generate_dry_run_results(
    cluster_ids: list[int],
    titles: list[str],  # representative titles, one per cluster_id
) -> ToolOutput:
    """Generate fake deterministic responses for dry-run jobs.

    Returns a ToolOutput with the same shape as real Anthropic responses,
    but with deterministic placeholder values.
    """
    results = []
    for i, (cid, title) in enumerate(zip(cluster_ids, titles)):
        results.append(
            TitleResult(
                id=f"t{i + 1:03d}",
                male_es=f"{title} (M)",
                female_es=f"{title} (F)",
                category="DRY_RUN",
            )
        )
    return ToolOutput(results=results)
