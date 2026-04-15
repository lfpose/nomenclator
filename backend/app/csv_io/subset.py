import random


def apply_row_subset(
    rows: list[tuple[int, str, str]],
    mode: str,
    n: int | None,
    job_id: str,
) -> list[tuple[int, str, str]]:
    """Select a subset of rows based on mode and count.

    Args:
        rows: List of (row_index, original, normalized) tuples.
        mode: One of "all", "first_n", "random_n".
        n: Number of rows to select (for first_n/random_n modes).
        job_id: Job ID used as seed for deterministic random sampling.

    Returns:
        Subset of rows, preserving original row_index values.
    """
    if mode == "all" or n is None:
        return rows
    if n >= len(rows):
        return rows
    if mode == "first_n":
        return rows[:n]
    if mode == "random_n":
        # Use first 8 chars of job_id (without hyphens) as hex seed
        seed = int(job_id.replace("-", "")[:8], 16)
        rng = random.Random(seed)
        selected = sorted(rng.sample(range(len(rows)), n))
        return [rows[i] for i in selected]
    return rows
