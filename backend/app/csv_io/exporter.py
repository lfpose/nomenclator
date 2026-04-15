from dataclasses import dataclass
import csv
import io
import logging


log = logging.getLogger("nomenclator.export")


@dataclass(frozen=True)
class ExportRow:
    original: str
    male_es: str
    female_es: str
    category: str
    error: str


COLUMN_ORDER = ["original", "male_es", "female_es", "category", "error"]


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


def write_csv_bytes(rows: list[ExportRow]) -> bytes:
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(COLUMN_ORDER)
    for r in rows:
        writer.writerow([r.original, r.male_es, r.female_es, r.category, r.error])
    return buf.getvalue().encode("utf-8")


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


def download_filename(job_id: str) -> str:
    short = job_id.replace("-", "")[:8]
    return f"nomenclator-{short}.csv"
