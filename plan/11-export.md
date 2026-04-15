# 11 — CSV Export and Pre-Write Assertion

Reference: `spec/09-csv-spec.md`, `spec/18-reliability-contract.md` layers 6–7.

The export path is the single place the row-count invariant can break. Every task here exists to make that impossible.

---

### P11-01 — Export query function

**Deps:** P02-06, P02-07
**Files:** `backend/app/csv_io/exporter.py`, `backend/tests/csv/test_export_query.py`
**Goal:** A function that runs the JOIN query and returns rows in the correct order.

**Implementation:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ExportRow:
    original: str
    male_es: str
    female_es: str
    category: str
    error: str

def fetch_export_rows(conn, job_id: str) -> list[ExportRow]:
    sql = """
    SELECT
      jr.original,
      COALESCE(c.male_es, '')   AS male_es,
      COALESCE(c.female_es, '') AS female_es,
      COALESCE(c.category, '')  AS category,
      COALESCE(c.error, '')     AS error
    FROM job_rows jr
    LEFT JOIN clusters c ON jr.cluster_id = c.id
    WHERE jr.job_id = ?
    ORDER BY jr.row_index ASC
    """
    rows = conn.execute(sql, (job_id,)).fetchall()
    return [ExportRow(*tuple(r)) for r in rows]
```

**Test:** `cd backend && uv run pytest tests/csv/test_export_query.py -v`

Required assertions:
- `test_export_rows_in_row_index_order`
- `test_export_populated_row_has_answers`
- `test_export_unresolved_cluster_returns_empty_answers`
- `test_export_errored_cluster_returns_error_code`
- `test_export_missing_cluster_id_returns_empty_row_not_dropped` — a row whose cluster_id is NULL still appears with 4 empty strings.

**Done when:**
- [ ] All 5 tests pass.

---

### P11-02 — CSV writer (BOM + CRLF)

**Deps:** P01-02
**Files:** `backend/app/csv_io/exporter.py` (extend), `backend/tests/csv/test_csv_writer.py`
**Goal:** Write rows to bytes with UTF-8 BOM and CRLF line endings.

**Implementation:**
```python
import csv, io

COLUMN_ORDER = ["original", "male_es", "female_es", "category", "error"]

def write_csv_bytes(rows: list[ExportRow]) -> bytes:
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(COLUMN_ORDER)
    for r in rows:
        writer.writerow([r.original, r.male_es, r.female_es, r.category, r.error])
    return buf.getvalue().encode("utf-8")
```

**Test:** `cd backend && uv run pytest tests/csv/test_csv_writer.py -v`

Required assertions:
- `test_output_starts_with_bom` — bytes `\xef\xbb\xbf`.
- `test_output_has_header_row`
- `test_output_has_5_columns_in_correct_order`
- `test_output_uses_crlf_line_endings`
- `test_special_characters_quoted_correctly` — titles containing commas, quotes, newlines.
- `test_unicode_accents_preserved`

**Done when:**
- [ ] All 6 tests pass.

---

### P11-03 — Pre-write assertion

**Deps:** P11-01, P11-02
**Files:** `backend/app/csv_io/exporter.py` (extend), `backend/tests/csv/test_assertion.py`
**Goal:** Top-level export function that counts input rows, counts output rows, asserts equality, logs and raises on mismatch.

Note: for partial runs (row subset mode), `job.total_rows` reflects the subset size (set during preview), so the assertion `len(rows) != job.total_rows` correctly validates against the subset — not the original full file size.

**Implementation:**
```python
import logging

log = logging.getLogger("nomenclator.export")

class RowCountDriftError(Exception):
    def __init__(self, job_id: str, in_count: int, out_count: int):
        self.job_id = job_id
        self.in_count = in_count
        self.out_count = out_count
        super().__init__(f"Row count drift in job {job_id}: in={in_count} out={out_count}")

def export_job_to_csv(conn, job_id: str) -> bytes:
    from ..dao.jobs import get_job
    job = get_job(conn, job_id)
    if job is None:
        raise ValueError("job_not_found")
    rows = fetch_export_rows(conn, job_id)
    if len(rows) != job.total_rows:
        log.error(
            "export.row_count_drift",
            extra={"job_id": job_id, "in_count": job.total_rows, "out_count": len(rows)},
        )
        raise RowCountDriftError(job_id, job.total_rows, len(rows))
    return write_csv_bytes(rows)
```

**Test:** `cd backend && uv run pytest tests/csv/test_assertion.py -v`

Required assertions:
- `test_export_happy_path_bytes_nonzero`
- `test_export_row_count_matches_input`
- `test_export_raises_on_count_drift` — create a job with `total_rows=10`, delete one `job_row`, expect `RowCountDriftError`.
- `test_export_drift_logged_with_counts`

**Done when:**
- [ ] All 4 tests pass.

---

### P11-04 — Filename builder

**Deps:** P01-02
**Files:** `backend/app/csv_io/exporter.py` (extend), `backend/tests/csv/test_filename.py`
**Goal:** Pure function that produces the download filename from a job ID.

**Implementation:**
```python
def download_filename(job_id: str) -> str:
    short = job_id.replace("-", "")[:8]
    return f"nomenclator-{short}.csv"
```

**Test:** `cd backend && uv run pytest tests/csv/test_filename.py -v`

Required assertions:
- `test_download_filename_strips_hyphens`
- `test_download_filename_starts_with_prefix`
- `test_download_filename_uses_8_chars`

**Done when:**
- [ ] All 3 tests pass.

---

### P11-05 — Failed-job transition on drift

**Deps:** P07-02, P11-03
**Files:** `backend/app/api/jobs.py` (extend download handler), `backend/tests/api/test_download_drift.py`
**Goal:** If `export_job_to_csv` raises `RowCountDriftError` inside the download handler, the job must transition to `failed` and the response must be 500 `internal_error` — never a partial CSV.

**Implementation:** wrap the export call in try/except inside the download endpoint.

**Test:** `cd backend && uv run pytest tests/api/test_download_drift.py -v`

Required assertions:
- `test_download_drift_transitions_job_to_failed`
- `test_download_drift_returns_500`
- `test_download_drift_never_returns_csv_bytes`

**Done when:**
- [ ] All 3 tests pass.
