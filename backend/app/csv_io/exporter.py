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
