from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from ..auth.middleware import require_session
from ..csv_io.parser import CSVError
from ..db import db_dep
from ..jobs.service import create_preview_job, recluster_job
from .errors import APIError

router = APIRouter(dependencies=[Depends(require_session)])


class ReclusterRequest(BaseModel):
    threshold: int


@router.post("/preview")
async def preview(
    threshold: int = Form(90),
    titles_per_request: int = Form(25),
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    conn=Depends(db_dep),
):
    if not (50 <= threshold <= 100):
        raise APIError("bad_threshold", "Threshold must be 50–100.", 400)
    if not (1 <= titles_per_request <= 50):
        raise APIError("bad_titles_per_request", "Titles per request must be 1–50.", 400)
    file_bytes = await file.read() if file else None
    # Keep text as None (not empty string) so ingest validation works correctly
    text_value = text
    try:
        result = create_preview_job(
            conn,
            file_bytes=file_bytes,
            text=text_value,
            threshold=threshold,
            titles_per_request=titles_per_request,
        )
    except CSVError as e:
        raise APIError(e.code, e.message, 400)
    except Exception as e:
        raise APIError("internal_error", str(e), 500)
    return {
        "job_id": result.job_id,
        "total_rows": result.total_rows,
        "exact_unique_rows": result.exact_unique_rows,
        "cluster_count": result.cluster_count,
        "largest_cluster_size": result.largest_cluster_size,
        "est_cost_usd": round(result.est_cost_usd, 4),
        "top_clusters": result.top_clusters,
        "warnings": result.warnings,
    }


@router.post("/{job_id}/recluster")
def recluster(job_id: str, body: ReclusterRequest, conn=Depends(db_dep)):
    if not (50 <= body.threshold <= 100):
        raise APIError("bad_threshold", "Threshold must be 50–100.", 400)
    try:
        result = recluster_job(conn, job_id, body.threshold)
    except ValueError as e:
        msg = str(e)
        if "invalid_state" in msg:
            raise APIError("invalid_state", "Job is not in preview state.", 409)
        if "not found" in msg:
            raise APIError("job_not_found", "No such job.", 404)
        raise
    return {
        "job_id": result.job_id,
        "total_rows": result.total_rows,
        "exact_unique_rows": result.exact_unique_rows,
        "cluster_count": result.cluster_count,
        "largest_cluster_size": result.largest_cluster_size,
        "est_cost_usd": round(result.est_cost_usd, 4),
        "top_clusters": result.top_clusters,
        "warnings": result.warnings,
    }
