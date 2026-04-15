from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..auth.middleware import require_session
from ..auth.rate_limit import COMMIT_LIMITER
from ..csv_io.exporter import (
    RowCountDriftError,
    download_filename,
    export_job_to_csv,
)
from ..csv_io.parser import CSVError
from ..db import db_dep
from ..jobs.service import (
    ConcurrencyError,
    SpendCapExceeded,
    cancel_job,
    commit_job,
    create_preview_job,
    recluster_job,
    transition,
)
from .errors import APIError

router = APIRouter(dependencies=[Depends(require_session)])


class ReclusterRequest(BaseModel):
    threshold: int


class CommitRequest(BaseModel):
    prompt_override: str | None = None
    taxonomy: str | None = None
    titles_per_request: int | None = None
    is_dry_run: bool = False


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


@router.post("/{job_id}/commit", status_code=202)
def commit(job_id: str, body: CommitRequest, request: Request, conn=Depends(db_dep)):
    sid = request.cookies.get("sid", "")
    if not COMMIT_LIMITER.allow(sid):
        raise APIError("rate_limited", "Too many commits.", 429)
    try:
        commit_job(
            conn,
            request.app.state.anthropic_client,
            job_id,
            **body.model_dump(exclude_none=True),
        )
    except SpendCapExceeded as e:
        raise APIError("spend_cap_exceeded", str(e), 409)
    except ConcurrencyError:
        raise APIError("job_already_running", "Another job is in flight.", 409)
    except ValueError as e:
        msg = str(e)
        if "invalid_state" in msg:
            raise APIError("invalid_state", "Job is not in preview state.", 409)
        if "not found" in msg:
            raise APIError("job_not_found", "No such job.", 404)
        raise
    return {"job_id": job_id, "status": "submitted"}


@router.get("")
def list_jobs(conn=Depends(db_dep)):
    from ..dao.jobs import list_jobs as dao_list

    jobs = dao_list(conn)
    return {"jobs": [serialize_job(j) for j in jobs]}


def serialize_job(j) -> dict:
    return {
        "id": j.id,
        "status": j.status,
        "total_rows": j.total_rows,
        "cluster_count": j.cluster_count,
        "completed_rows": j.completed_rows,
        "error_rows": j.error_rows,
        "est_cost_usd": round(j.est_cost_usd, 4),
        "actual_cost_usd": round(j.actual_cost_usd, 4),
        "created_at": datetime.fromtimestamp(j.created_at, tz=timezone.utc).isoformat(),
        "finished_at": (
            datetime.fromtimestamp(j.finished_at, tz=timezone.utc).isoformat()
            if j.finished_at
            else None
        ),
    }


@router.post("/{job_id}/cancel")
def cancel(job_id: str, request: Request, conn=Depends(db_dep)):
    """Cancel a job in a cancellable state.

    Jobs can only be cancelled when they are in queued, submitted, polling,
    or retrying states. Terminal states (completed, failed, cancelled) cannot
    be cancelled.
    """
    try:
        cancel_job(conn, request.app.state.anthropic_client, job_id)
    except ValueError as e:
        msg = str(e)
        if "job_not_found" in msg:
            raise APIError("job_not_found", "No such job.", 404)
        if "invalid_state" in msg:
            raise APIError("invalid_state", "Job is not in a cancellable state.", 409)
        raise
    return {"ok": True}


@router.get("/{job_id}")
def get_job(job_id: str, conn=Depends(db_dep)):
    """Get details for a single job including progress and batch information.

    Returns the job details along with live progress information about cluster
    resolution and batch processing status.
    """
    from ..dao.batches import list_batches_for_job
    from ..dao.clusters import list_clusters
    from ..dao.jobs import get_job as dao_get

    job = dao_get(conn, job_id)
    if job is None:
        raise APIError("job_not_found", "No such job.", 404)

    clusters = list_clusters(conn, job_id)
    resolved = sum(1 for c in clusters if c.male_es)
    errored = sum(1 for c in clusters if c.error)
    pending = len(clusters) - resolved - errored

    batches = list_batches_for_job(conn, job_id)

    return {
        **serialize_job(job),
        "retry_round": max((b.retry_round for b in batches), default=0),
        "progress": {
            "clusters_total": len(clusters),
            "clusters_resolved": resolved,
            "clusters_pending": pending,
            "clusters_error": errored,
        },
        "batches": [
            {
                "id": b.id,
                "status": b.status,
                "request_count": b.request_count,
                "retry_round": b.retry_round,
            }
            for b in batches
        ],
    }


@router.get("/{job_id}/download")
def download_job(job_id: str, conn=Depends(db_dep)):
    """Download the CSV export of a completed job.

    Returns the processed job titles as a CSV file with standardized forms.
    Only completed jobs can be downloaded.

    If row count drift is detected, the job is transitioned to failed and
    an internal error is returned (never a partial CSV).
    """
    from ..dao.jobs import get_job as dao_get

    job = dao_get(conn, job_id)
    if job is None:
        raise APIError("job_not_found", "No such job.", 404)
    if job.status != "completed":
        raise APIError("invalid_state", "Job is not in completed state.", 409)

    try:
        csv_bytes = export_job_to_csv(conn, job_id)
    except RowCountDriftError as e:
        # Transition job to failed state and return 500 error
        transition(conn, job_id, "failed", reason="row_count_drift")
        raise APIError("internal_error", "Row count drift detected.", 500)

    filename = download_filename(job_id)

    def iter_bytes():
        yield csv_bytes

    return StreamingResponse(
        iter_bytes(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
