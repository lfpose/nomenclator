# 09 — CSV Spec

## Input

### Accepted shapes

Two entry points, both go through the same parser after initial routing:

1. **File upload** (multipart `file` field): a `.csv` file, UTF-8 encoded, with a header row and at least one data row. The first column is the title column regardless of its header name.
2. **Pasted text** (multipart `text` field): plain text, one title per line. No header. Blank lines skipped.

Exactly one of `file` or `text` must be present on the request. Both or neither → 400 `input_malformed`.

### File constraints

| Property | Rule |
|---|---|
| Encoding | UTF-8 only. BOM allowed and stripped. Anything else → 400 `encoding_invalid`. |
| Size | No hard size limit; row count limit is 50,000 (see `FR-016`). |
| Delimiter | Comma or semicolon. Auto-detect on the header row by counting occurrences of each in the first 2KB. Tie → prefer comma. Neither found → 400 `delimiter_unknown`. |
| Quoting | Standard RFC 4180 — double quotes around fields containing delimiter, newline, or quote; quote within quoted field is doubled. |
| Header | Mandatory. Ignored except to confirm shape. |
| Columns | Only the first column is read. Additional columns are ignored silently. |

### Parsing implementation

Use pandas with explicit dtypes and strict error handling:

```python
import pandas as pd

df = pd.read_csv(
    file_obj,
    sep=detected_delimiter,
    encoding="utf-8",
    encoding_errors="strict",
    dtype=str,
    keep_default_na=False,    # "NA" stays "NA", doesn't become NaN
    na_values=[],
    skip_blank_lines=True,
)
if df.shape[0] == 0:
    raise InputEmpty()
if df.shape[0] > 50_000:
    raise InputTooLarge()

titles = df.iloc[:, 0].tolist()  # first column only
```

### Normalization (shared by both entry points)

```python
import unicodedata

def normalize(s: str) -> str:
    # Strip accents
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Lowercase
    s = s.lower()
    # Collapse inner whitespace, strip outer
    s = " ".join(s.split())
    # Drop punctuation except inner hyphens (optional; keep it simple)
    import re
    s = re.sub(r"[^a-z0-9\s\-]", " ", s)
    s = " ".join(s.split())
    return s
```

Rows that normalize to an empty string are dropped with a log warning (`dropped_empty_row row_index=N`). They still count in `total_rows` but do not appear in the output. **This is a violation of the row-count invariant, so it MUST NOT happen under normal circumstances.** Instead, the preview response includes a soft warning `empty_rows_dropped: N` and the operator is told. See `17-open-questions.md` for the hard-stop-vs-drop debate.

**Decision for v1:** if any row normalizes to empty, fail the preview with 400 `input_contains_blank_rows` and tell the operator to clean their CSV first. This preserves the invariant strictly.

## Row subset selection

After parsing, the operator may choose to process only a subset of rows. Three modes:

### `all` (default)
All parsed rows go through the pipeline. No change from baseline behavior.

### `first_n`
Take the first `n` rows in input order (preserving `row_index` 0 through n-1). Remaining rows are discarded before clustering.

### `random_n`
Randomly sample `n` rows from the full input. The random seed is derived deterministically from the job ID (`seed = int(job_id.replace('-', '')[:8], 16)`), so the same job ID always selects the same sample. Selected rows retain their original `row_index` values for ordering.

### Implementation

```python
import random

def apply_row_subset(
    rows: list[tuple[int, str, str]],
    mode: str,
    n: int | None,
    job_id: str,
) -> list[tuple[int, str, str]]:
    if mode == "all" or n is None:
        return rows
    if n >= len(rows):
        return rows  # asking for more than available → return all
    if mode == "first_n":
        return rows[:n]
    if mode == "random_n":
        seed = int(job_id.replace("-", "")[:8], 16)
        rng = random.Random(seed)
        selected = sorted(rng.sample(range(len(rows)), n))
        return [rows[i] for i in selected]
    return rows
```

### Constraints
- `n` must be ≥ 1 when mode is not `all`.
- If `n ≥ total_rows`, the system silently processes all rows (equivalent to `all`).
- The row-count invariant applies to the *selected* subset: if 100 rows are selected, exactly 100 appear in the output.
- The preview response includes both `total_rows` (full input) and `selected_rows` (after subset) to make the selection visible.

## Output

### File format

| Property | Value |
|---|---|
| Encoding | UTF-8 with BOM (`\ufeff` prepended) |
| Line endings | `\r\n` (CRLF) — Excel-friendly |
| Delimiter | Comma |
| Quoting | `csv.QUOTE_MINIMAL` — quote only when the field contains comma, quote, or newline |
| Header | Mandatory, always present |

### Column order

Exactly five columns, always in this order, always present even when empty:

1. `original` — the row's verbatim input title, untouched.
2. `male_es` — the standardized masculine Spanish title, empty for error rows.
3. `female_es` — the standardized feminine Spanish title, empty for error rows.
4. `category` — the taxonomy category, empty for error rows.
5. `error` — the error code, empty for populated rows.

### Row count and order

- **Row count** equals the input row count, enforced by the pre-write assertion (see `18-reliability-contract.md`). For partial runs (row_subset_mode != 'all'), the row count equals `row_subset_n` (or fewer if n exceeds total_rows), not the full input count.
- **Row order** matches `job_rows.row_index`, which is set at ingestion in input order.

### Export query

```sql
SELECT
  jr.original,
  COALESCE(c.male_es, '')   AS male_es,
  COALESCE(c.female_es, '') AS female_es,
  COALESCE(c.category, '')  AS category,
  COALESCE(c.error, '')     AS error
FROM job_rows jr
LEFT JOIN clusters c ON jr.cluster_id = c.id
WHERE jr.job_id = :job_id
ORDER BY jr.row_index ASC;
```

### Write implementation

```python
import csv, io

def write_csv(rows: list[tuple]) -> bytes:
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM
    writer = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["original", "male_es", "female_es", "category", "error"])
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")
```

### Filename

`nomenclator-{job_id_short}.csv` where `job_id_short` is the first 8 hex characters of the job UUID (no hyphens). Example: `nomenclator-a1b2c3d4.csv`.

Served via `Content-Disposition: attachment; filename="..."`.

## Edge cases

| Case | Behavior |
|---|---|
| File with 0 data rows | 400 `input_empty` |
| File with 1 data row | Works, creates a 1-row job. Clustering is trivial (1 cluster). |
| Title with embedded commas/quotes/newlines | Parsed via RFC 4180 quoting, preserved verbatim in `original`, re-quoted on output. |
| Very long title (> 500 chars) | Parsed normally. Logs a warning. Sent to LLM as-is; `max_tokens` gives headroom. |
| Duplicate title verbatim | Handled by exact dedup + clustering (single cluster, multiple job_rows). |
| Title that is just whitespace | Fails preview with `input_contains_blank_rows`. |
| Title with only emoji or non-Latin scripts | Preserved in `original`, goes through clustering normally (normalization reduces to empty, which triggers `input_contains_blank_rows`). Operator must clean. |
| Trailing blank line in pasted text | Skipped silently. |
| CSV with ≥ 2 columns | Only first column read; others ignored. Logged at DEBUG level. |
