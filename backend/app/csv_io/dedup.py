def unique_normalized(rows: list[tuple[int, str, str]]) -> list[str]:
    """Return unique normalized values from ingested rows, preserving insertion order.

    Args:
        rows: List of (row_index, original, normalized) tuples from ingest().

    Returns:
        List of unique normalized strings in order of first appearance.
    """
    seen: dict[str, None] = {}  # preserves insertion order
    for _, _, norm in rows:
        if norm not in seen:
            seen[norm] = None
    return list(seen.keys())
