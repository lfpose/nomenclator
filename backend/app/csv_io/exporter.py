from dataclasses import dataclass
import csv
import io


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
