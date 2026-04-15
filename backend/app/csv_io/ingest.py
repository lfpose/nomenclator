from .normalize import normalize
from .parser import CSVError, parse_csv, parse_text


def ingest(
    *, file_bytes: bytes | None = None, text: str | None = None
) -> list[tuple[int, str, str]]:
    """Parse and normalize input from either a CSV file or pasted text.

    Args:
        file_bytes: Raw bytes of a CSV file (optional).
        text: Pasted text with one title per line (optional).

    Returns:
        List of tuples (index, original, normalized) for each non-blank row.

    Raises:
        CSVError: If exactly one of file_bytes or text is not provided,
                  if parsing fails, or if any row normalizes to empty.
    """
    if (file_bytes is None) == (text is None):
        raise CSVError("input_malformed", "Exactly one of file or text must be provided.")

    originals = parse_csv(file_bytes) if file_bytes else parse_text(text)
    rows: list[tuple[int, str, str]] = []
    for i, orig in enumerate(originals):
        norm = normalize(orig)
        if not norm:
            raise CSVError(
                "input_contains_blank_rows",
                f"Row {i} normalizes to empty (original: {orig!r}). Please clean your input.",
            )
        rows.append((i, orig, norm))
    return rows
