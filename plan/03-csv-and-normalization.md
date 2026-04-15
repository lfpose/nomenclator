# 03 — CSV Ingestion and Normalization

Reference: `spec/09-csv-spec.md`.

---

### P03-01 — Normalization function

**Deps:** P01-02
**Files:** `backend/app/csv_io/normalize.py`, `backend/tests/csv/test_normalize.py`
**Goal:** Pure function that strips accents, lowercases, drops punctuation, collapses whitespace.

**Implementation:**
```python
import unicodedata
import re

_PUNCT_RE = re.compile(r"[^a-z0-9\s\-]")

def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = " ".join(s.split())
    s = _PUNCT_RE.sub(" ", s)
    s = " ".join(s.split())
    return s
```

**Test:** `cd backend && uv run pytest tests/csv/test_normalize.py -v`

Required assertions (each as a `test_*` function, with specific input/expected):
- `test_normalize_strips_accents` — `"Señor Técnico" → "senor tecnico"`
- `test_normalize_lowercases` — `"JEFE COMPRAS" → "jefe compras"`
- `test_normalize_collapses_whitespace` — `"  jefe    compras  " → "jefe compras"`
- `test_normalize_drops_punctuation` — `"jefe, de compras!" → "jefe de compras"`
- `test_normalize_preserves_inner_hyphen` — `"co-founder" → "co-founder"`
- `test_normalize_empty_string_returns_empty` — `"" → ""`
- `test_normalize_only_punctuation_returns_empty` — `"!!!" → ""`
- `test_normalize_idempotent` — `normalize(normalize(x)) == normalize(x)` for 20 random inputs.

**Done when:**
- [ ] All 8 tests pass.
- [ ] Function has no side effects (pure).

---

### P03-02 — CSV parser

**Deps:** P01-02
**Files:** `backend/app/csv_io/parser.py`, `backend/tests/csv/test_parser.py`, `backend/tests/fixtures/csv/*.csv`
**Goal:** Parse a UTF-8 CSV with header, auto-detect delimiter, return list of first-column values.

**Implementation:**
```python
import pandas as pd
from io import BytesIO, StringIO

class CSVError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message

def parse_csv(raw: bytes) -> list[str]:
    try:
        text = raw.decode("utf-8-sig")  # strips BOM
    except UnicodeDecodeError:
        raise CSVError("encoding_invalid", "File is not UTF-8.")

    sample = text[:2048]
    comma = sample.count(",")
    semi = sample.count(";")
    if comma == 0 and semi == 0:
        raise CSVError("delimiter_unknown", "CSV delimiter must be comma or semicolon.")
    delim = "," if comma >= semi else ";"

    try:
        df = pd.read_csv(
            StringIO(text),
            sep=delim,
            dtype=str,
            keep_default_na=False,
            na_values=[],
            skip_blank_lines=True,
        )
    except Exception as e:
        raise CSVError("parse_failed", f"Failed to parse CSV: {e}")

    if df.shape[0] == 0:
        raise CSVError("input_empty", "No data rows.")
    if df.shape[0] > 50_000:
        raise CSVError("input_too_large", f"Row count {df.shape[0]} exceeds 50,000.")

    return df.iloc[:, 0].tolist()
```

Create fixture files:
- `tests/fixtures/csv/basic_comma.csv` — 5 titles, comma
- `tests/fixtures/csv/basic_semicolon.csv` — 5 titles, semicolon
- `tests/fixtures/csv/with_bom.csv` — 3 titles, UTF-8 BOM
- `tests/fixtures/csv/multi_column.csv` — 5 rows, 3 columns, title in first
- `tests/fixtures/csv/empty_data.csv` — header only, no rows
- `tests/fixtures/csv/non_utf8.csv` — Latin-1 encoded

**Test:** `cd backend && uv run pytest tests/csv/test_parser.py -v`

Required assertions:
- `test_parse_comma_csv_returns_list`
- `test_parse_semicolon_csv_returns_list`
- `test_parse_strips_bom`
- `test_parse_multi_column_reads_only_first`
- `test_parse_empty_raises_input_empty`
- `test_parse_non_utf8_raises_encoding_invalid`
- `test_parse_huge_raises_input_too_large` — synthetic > 50,000 rows
- `test_parse_unknown_delimiter_raises_delimiter_unknown`

**Done when:**
- [ ] All 8 tests pass.

---

### P03-03 — Pasted text parser

**Deps:** P01-02
**Files:** `backend/app/csv_io/parser.py` (extend), `backend/tests/csv/test_parse_text.py`
**Goal:** Parse pasted text (one title per line, no header), return list.

**Implementation:**
```python
def parse_text(raw: str) -> list[str]:
    lines = [line.strip() for line in raw.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise CSVError("input_empty", "No titles found.")
    if len(lines) > 50_000:
        raise CSVError("input_too_large", f"Line count {len(lines)} exceeds 50,000.")
    return lines
```

**Test:** `cd backend && uv run pytest tests/csv/test_parse_text.py -v`

Required assertions:
- `test_parse_text_one_per_line`
- `test_parse_text_skips_blank_lines`
- `test_parse_text_strips_whitespace`
- `test_parse_text_empty_raises_input_empty`
- `test_parse_text_too_large_raises`

**Done when:**
- [ ] All 5 tests pass.

---

### P03-04 — Ingestion validation: blank rows

**Deps:** P03-01, P03-02, P03-03
**Files:** `backend/app/csv_io/ingest.py`, `backend/tests/csv/test_ingest.py`
**Goal:** Combine parsing + normalization + validation into a single entry point. Reject any input whose normalized form contains blank entries (enforces `spec/OQ-01` decision C).

**Implementation:**
```python
from .normalize import normalize
from .parser import CSVError, parse_csv, parse_text

def ingest(
    *, file_bytes: bytes | None = None, text: str | None = None
) -> list[tuple[int, str, str]]:
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
```

**Test:** `cd backend && uv run pytest tests/csv/test_ingest.py -v`

Required assertions:
- `test_ingest_csv_bytes_returns_indexed_triples`
- `test_ingest_text_returns_indexed_triples`
- `test_ingest_blank_row_raises_input_contains_blank_rows`
- `test_ingest_preserves_original_untouched`
- `test_ingest_both_sources_raises_input_malformed`
- `test_ingest_neither_source_raises_input_malformed`

**Done when:**
- [ ] All 6 tests pass.

---

### P03-05 — Exact dedup helper

**Deps:** P03-01
**Files:** `backend/app/csv_io/dedup.py`, `backend/tests/csv/test_dedup.py`
**Goal:** Given ingested rows, return the unique normalized values.

**Implementation:**
```python
def unique_normalized(rows: list[tuple[int, str, str]]) -> list[str]:
    seen: dict[str, None] = {}  # preserves insertion order
    for _, _, norm in rows:
        if norm not in seen:
            seen[norm] = None
    return list(seen.keys())
```

**Test:** `cd backend && uv run pytest tests/csv/test_dedup.py -v`

Required assertions:
- `test_dedup_removes_exact_duplicates`
- `test_dedup_preserves_first_occurrence_order`
- `test_dedup_on_empty_returns_empty`
- `test_dedup_on_already_unique_returns_same_length`

**Done when:**
- [ ] All 4 tests pass.

---

### P03-06 — CSV integration smoke test

**Deps:** P03-04, P03-05
**Files:** `backend/tests/csv/test_csv_smoke.py`, `backend/tests/fixtures/csv/realistic_13k.csv.gz`
**Goal:** End-to-end ingestion on a realistic 13k-row fixture, asserting correct counts.

**Implementation:**
- Generate a synthetic 13,000-row CSV with ~40% intentional exact duplicates and various accent/case variants.
- Gzip it for repo size.
- Write a test that decompresses, ingests, dedups, asserts counts are in expected ranges.

**Test:** `cd backend && uv run pytest tests/csv/test_csv_smoke.py -v`

Required assertions:
- `test_smoke_ingests_13k_under_2s`
- `test_smoke_dedup_reduces_by_at_least_30_percent`
- `test_smoke_all_originals_preserved`

**Done when:**
- [ ] All 3 tests pass.

---

### P03-07 — Row subset selection

**Deps:** P03-04
**Files:** `backend/app/csv_io/subset.py`, `backend/tests/csv/test_subset.py`
**Goal:** Pure function to select a subset of rows by mode (all, first_n, random_n) with deterministic seeding.

**Implementation:**
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
        return rows
    if mode == "first_n":
        return rows[:n]
    if mode == "random_n":
        seed = int(job_id.replace("-", "")[:8], 16)
        rng = random.Random(seed)
        selected = sorted(rng.sample(range(len(rows)), n))
        return [rows[i] for i in selected]
    return rows
```

**Test:** `cd backend && uv run pytest tests/csv/test_subset.py -v`

Required assertions:
- `test_subset_all_returns_all_rows`
- `test_subset_first_n_returns_first_n`
- `test_subset_first_n_preserves_row_index`
- `test_subset_random_n_returns_exactly_n`
- `test_subset_random_n_deterministic_with_same_job_id` — same job_id → same selection twice.
- `test_subset_random_n_different_job_id_different_selection`
- `test_subset_n_greater_than_total_returns_all`
- `test_subset_preserves_original_row_indices`

**Done when:**
- [ ] All 8 tests pass.
