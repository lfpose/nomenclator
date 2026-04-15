# 10 — HTTP API

FastAPI endpoints. Each task is one endpoint with one test file. Reference: `spec/06-api-contract.md`.

Shared test fixture: `client` yields a `TestClient` with a logged-in session (unless the test is about auth itself).

---

### P10-01 — App factory + error envelope + global exception handlers

**Deps:** P01-03, P02-03
**Files:** `backend/app/main.py` (extend), `backend/app/api/errors.py`, `backend/tests/api/test_error_envelope.py`
**Goal:** Standardized error envelope for all API responses; global exception handlers.

**Implementation:**
```python
# backend/app/api/errors.py
from fastapi import Request
from fastapi.responses import JSONResponse

class APIError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}

def error_response(code: str, message: str, status: int, details: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )

def register_handlers(app):
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(APIError)
    async def _api(req, exc):
        return error_response(exc.code, exc.message, exc.status, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(req, exc):
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return error_response("http_error", str(exc.detail), exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _val(req, exc):
        return error_response("bad_request", "Invalid request body", 400, {"errors": exc.errors()})

    @app.exception_handler(Exception)
    async def _unknown(req, exc):
        return error_response("internal_error", "An unexpected error occurred.", 500)
```

Wire into `main.py`.

**Test:** `cd backend && uv run pytest tests/api/test_error_envelope.py -v`

Required assertions:
- `test_api_error_produces_envelope`
- `test_http_exception_produces_envelope`
- `test_validation_error_produces_bad_request`
- `test_unknown_exception_produces_internal_error`

**Done when:**
- [ ] All 4 tests pass.

---

### P10-02 — POST /auth

**Deps:** P09-01, P09-02, P09-04, P09-05, P10-01
**Files:** `backend/app/api/auth.py`, `backend/tests/api/test_api_auth.py`
**Goal:** `POST /auth` with password → session cookie.

**Implementation:**
```python
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from ..auth.passwords import verify_password
from ..auth.sessions import create_session
from ..auth.rate_limit import AUTH_LIMITER
from ..auth.config import get_password_hash
from ..db import db_dep
from .errors import APIError

router = APIRouter()

class AuthRequest(BaseModel):
    password: str

@router.post("/auth")
def auth_login(body: AuthRequest, request: Request, response: Response, conn=Depends(db_dep)):
    ip = request.client.host or "unknown"
    if not AUTH_LIMITER.allow(ip):
        raise APIError("rate_limited", "Too many attempts.", 429)
    if not verify_password(get_password_hash(), body.password):
        raise APIError("unauthenticated", "Wrong password.", 401)
    sid = create_session(conn)
    response.set_cookie(
        "sid", sid, httponly=True, secure=True, samesite="lax",
        max_age=2592000, path="/",
    )
    return {"ok": True}
```

**Test:** `cd backend && uv run pytest tests/api/test_api_auth.py -v`

Required assertions:
- `test_auth_correct_password_sets_cookie`
- `test_auth_wrong_password_returns_401`
- `test_auth_rate_limits_after_5_attempts`
- `test_auth_cookie_flags_httponly_secure_samesite`

**Done when:**
- [ ] All 4 tests pass.

---

### P10-03 — GET /me and POST /auth/logout

**Deps:** P09-03, P10-02
**Files:** `backend/app/api/auth.py` (extend), `backend/tests/api/test_api_me.py`
**Goal:** `/me` returns 200 if logged in; `/auth/logout` deletes session.

**Implementation:**
```python
from fastapi import Depends, Request, Response
from ..auth.middleware import require_session
from ..auth.sessions import destroy_session

@router.get("/me", dependencies=[Depends(require_session)])
def me():
    return {"authenticated": True}

@router.post("/auth/logout", dependencies=[Depends(require_session)])
def logout(request: Request, response: Response, conn=Depends(db_dep)):
    raw = request.cookies.get("sid")
    if raw:
        destroy_session(conn, raw)
    response.delete_cookie("sid", path="/")
    return {"ok": True}
```

**Test:** `cd backend && uv run pytest tests/api/test_api_me.py -v`

Required assertions:
- `test_me_401_without_cookie`
- `test_me_200_with_valid_cookie`
- `test_logout_destroys_session`
- `test_me_401_after_logout`

**Done when:**
- [ ] All 4 tests pass.

---

### P10-04 — POST /jobs/preview

**Deps:** P07-04, P09-03, P10-01
**Files:** `backend/app/api/jobs.py`, `backend/tests/api/test_api_preview.py`
**Goal:** Multipart endpoint that ingests + clusters + returns preview payload.

**Implementation:**
```python
from fastapi import APIRouter, Depends, File, Form, UploadFile
from ..auth.middleware import require_session
from ..jobs.service import create_preview_job
from ..csv_io.parser import CSVError
from .errors import APIError

router = APIRouter(dependencies=[Depends(require_session)])

@router.post("/jobs/preview")
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
    try:
        result = create_preview_job(
            conn, file_bytes=file_bytes, text=text,
            threshold=threshold, titles_per_request=titles_per_request,
        )
    except CSVError as e:
        raise APIError(e.code, e.message, 400)
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
```

**Test:** `cd backend && uv run pytest tests/api/test_api_preview.py -v`

Required assertions:
- `test_preview_with_csv_file_returns_payload`
- `test_preview_with_pasted_text_returns_payload`
- `test_preview_bad_threshold_400`
- `test_preview_bad_tpr_400`
- `test_preview_empty_csv_400`
- `test_preview_requires_auth`
- `test_preview_returns_job_id_in_preview_state`

**Done when:**
- [ ] All 7 tests pass.

---

### P10-05 — POST /jobs/:id/recluster

**Deps:** P07-05, P10-04
**Files:** `backend/app/api/jobs.py` (extend), `backend/tests/api/test_api_recluster.py`
**Goal:** Change threshold on an existing preview job.

**Implementation:**
```python
class ReclusterRequest(BaseModel):
    threshold: int

@router.post("/jobs/{job_id}/recluster")
def recluster(job_id: str, body: ReclusterRequest, conn=Depends(db_dep)):
    if not (50 <= body.threshold <= 100):
        raise APIError("bad_threshold", "Threshold must be 50–100.", 400)
    from ..jobs.service import recluster_job
    try:
        result = recluster_job(conn, job_id, body.threshold)
    except ValueError as e:
        if "invalid_state" in str(e):
            raise APIError("invalid_state", "Job is not in preview state.", 409)
        if "not found" in str(e):
            raise APIError("job_not_found", "No such job.", 404)
        raise
    return {...}  # same payload as preview
```

**Test:** `cd backend && uv run pytest tests/api/test_api_recluster.py -v`

Required assertions:
- `test_recluster_updates_cluster_count`
- `test_recluster_bad_threshold_400`
- `test_recluster_non_preview_409`
- `test_recluster_missing_job_404`

**Done when:**
- [ ] All 4 tests pass.

---

### P10-06 — POST /jobs/:id/commit

**Deps:** P07-06, P10-04
**Files:** `backend/app/api/jobs.py` (extend), `backend/tests/api/test_api_commit.py`
**Goal:** Commit a previewed job, returning 202 + initial status.

**Implementation:**
```python
from ..auth.rate_limit import COMMIT_LIMITER

class CommitRequest(BaseModel):
    prompt_override: str | None = None
    taxonomy: str | None = None
    titles_per_request: int | None = None

@router.post("/jobs/{job_id}/commit", status_code=202)
def commit(job_id: str, body: CommitRequest, request: Request, conn=Depends(db_dep)):
    sid = request.cookies.get("sid", "")
    if not COMMIT_LIMITER.allow(sid):
        raise APIError("rate_limited", "Too many commits.", 429)
    from ..jobs.service import commit_job, SpendCapExceeded, ConcurrencyError
    try:
        commit_job(conn, request.app.state.anthropic_client, job_id, body.dict(exclude_none=True))
    except SpendCapExceeded as e:
        raise APIError("spend_cap_exceeded", str(e), 409, details=e.details)
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
```

**Test:** `cd backend && uv run pytest tests/api/test_api_commit.py -v`

Required assertions:
- `test_commit_happy_path_returns_202`
- `test_commit_spend_cap_returns_409`
- `test_commit_concurrent_returns_409`
- `test_commit_non_preview_returns_409`
- `test_commit_missing_job_returns_404`
- `test_commit_rate_limited_after_10`

**Done when:**
- [ ] All 6 tests pass.

---

### P10-07 — POST /jobs/:id/cancel

**Deps:** P07-07, P10-04
**Files:** `backend/app/api/jobs.py` (extend), `backend/tests/api/test_api_cancel.py`
**Goal:** Cancel endpoint.

**Implementation:** thin wrapper around `cancel_job`.

**Test:** `cd backend && uv run pytest tests/api/test_api_cancel.py -v`

Required assertions:
- `test_cancel_transitions_to_cancelled`
- `test_cancel_terminal_returns_409`
- `test_cancel_missing_job_404`

**Done when:**
- [ ] All 3 pass.

---

### P10-08 — GET /jobs

**Deps:** P02-05, P09-03
**Files:** `backend/app/api/jobs.py` (extend), `backend/tests/api/test_api_list_jobs.py`
**Goal:** Return all jobs newest first.

**Implementation:**
```python
@router.get("/jobs")
def list_jobs(conn=Depends(db_dep)):
    from ..dao.jobs import list_jobs as dao_list
    jobs = dao_list(conn)
    return {"jobs": [serialize_job(j) for j in jobs]}

def serialize_job(j) -> dict:
    from datetime import datetime, timezone
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
        "finished_at": datetime.fromtimestamp(j.finished_at, tz=timezone.utc).isoformat() if j.finished_at else None,
    }
```

**Test:** `cd backend && uv run pytest tests/api/test_api_list_jobs.py -v`

Required assertions:
- `test_list_jobs_empty_returns_empty_array`
- `test_list_jobs_after_creation_returns_one`
- `test_list_jobs_ordered_newest_first`
- `test_list_jobs_requires_auth`

**Done when:**
- [ ] All 4 tests pass.

---

### P10-09 — GET /jobs/:id

**Deps:** P02-05, P02-07, P02-08, P10-08
**Files:** `backend/app/api/jobs.py` (extend), `backend/tests/api/test_api_get_job.py`
**Goal:** Single job with live progress: clusters_resolved, clusters_error, retry_round, batches summary.

**Implementation:**
```python
@router.get("/jobs/{job_id}")
def get_job(job_id: str, conn=Depends(db_dep)):
    from ..dao.jobs import get_job as dao_get
    from ..dao.clusters import list_clusters
    from ..dao.batches import list_batches_for_job
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
            {"id": b.id, "status": b.status, "request_count": b.request_count, "retry_round": b.retry_round}
            for b in batches
        ],
    }
```

**Test:** `cd backend && uv run pytest tests/api/test_api_get_job.py -v`

Required assertions:
- `test_get_job_returns_progress_counts`
- `test_get_job_returns_batches_array`
- `test_get_job_retry_round_reflects_max`
- `test_get_job_missing_404`

**Done when:**
- [ ] All 4 tests pass.

---

### P10-10 — GET /jobs/:id/download

**Deps:** P11-02 (wired in export phase; reserved here as stub if needed)
**Files:** `backend/app/api/jobs.py` (extend), `backend/tests/api/test_api_download.py`
**Goal:** Stream CSV. See phase 11 for full export implementation.

**Implementation:** placeholder that calls `export_job_to_csv(conn, job_id) -> bytes` from phase 11, returns as `StreamingResponse` with correct content type and filename.

**Test:** `cd backend && uv run pytest tests/api/test_api_download.py -v`

Required assertions:
- `test_download_completed_job_returns_csv`
- `test_download_starts_with_utf8_bom`
- `test_download_filename_header_set`
- `test_download_non_completed_returns_409`
- `test_download_missing_404`

**Done when:**
- [ ] All 5 tests pass (phase 11 must also be complete).

---

### P10-11 — GET /spend

**Deps:** P06-02, P09-03
**Files:** `backend/app/api/spend.py`, `backend/tests/api/test_api_spend.py`
**Goal:** Rolling spend + cap info.

**Implementation:**
```python
from ..jobs.estimator import check_cap
from datetime import datetime, timezone

@router.get("/spend")
def spend(conn=Depends(db_dep)):
    cap = check_cap(conn, estimated_usd=0.0)
    return {
        "used_usd": round(cap.used_usd, 4),
        "cap_usd": cap.cap_usd,
        "window_days": 30,
        "reset_date": datetime.fromtimestamp(cap.reset_date_unix, tz=timezone.utc).date().isoformat()
            if cap.reset_date_unix else None,
    }
```

**Test:** `cd backend && uv run pytest tests/api/test_api_spend.py -v`

Required assertions:
- `test_spend_empty_returns_zero`
- `test_spend_after_entries_returns_sum`
- `test_spend_reset_date_when_entries_exist`

**Done when:**
- [ ] All 3 pass.

---

### P10-12 — GET /health

**Deps:** P02-01, P08-01
**Files:** `backend/app/api/health.py`, `backend/tests/api/test_api_health.py`
**Goal:** Public health endpoint, no auth.

**Implementation:**
```python
from fastapi import Request
from datetime import datetime, timezone
import time
from ..settings import settings

@router.get("/health")
def health(request: Request, conn=Depends(db_dep)):
    try:
        conn.execute("SELECT 1").fetchone()
        db_ok = "ok"
    except Exception:
        db_ok = "error"
    worker = getattr(request.app.state, "worker", None)
    heartbeat = worker.last_tick_at if worker else 0
    seconds_ago = time.time() - heartbeat if heartbeat else None
    ok = db_ok == "ok" and (seconds_ago is None or seconds_ago < 120)
    return {
        "ok": ok,
        "db": db_ok,
        "worker_heartbeat": datetime.fromtimestamp(heartbeat, tz=timezone.utc).isoformat() if heartbeat else None,
        "worker_last_tick_seconds_ago": seconds_ago,
        "version": settings.version,
    }
```

**Test:** `cd backend && uv run pytest tests/api/test_api_health.py -v`

Required assertions:
- `test_health_returns_200`
- `test_health_reports_db_ok`
- `test_health_reports_worker_heartbeat_when_set`
- `test_health_no_auth_required`

**Done when:**
- [ ] All 4 tests pass.

---

### P10-16 — POST /jobs/review-prompt

**Deps:** P07-10, P09-03, P10-01
**Files:** `backend/app/api/jobs.py` (extend), `backend/tests/api/test_api_review_prompt.py`
**Goal:** Endpoint that sends the operator's prompt to Claude for review.

**Implementation:**
```python
from pydantic import BaseModel
from ..jobs.service import review_operator_prompt
from ..settings import settings

class ReviewPromptRequest(BaseModel):
    prompt: str
    few_shots: str  # JSON string

@router.post("/jobs/review-prompt")
def review_prompt_endpoint(body: ReviewPromptRequest, request: Request, conn=Depends(db_dep)):
    sid = request.cookies.get("sid", "")
    if not REVIEW_LIMITER.allow(sid):
        raise APIError("rate_limited", "Too many review requests.", 429)
    try:
        review = review_operator_prompt(settings.anthropic_api_key, body.prompt, body.few_shots)
    except Exception as e:
        raise APIError("prompt_review_failed", f"Prompt review failed: {e}", 500)
    return {
        "safe": review.safe,
        "quality_score": review.quality_score,
        "issues": review.issues,
        "suggestions": review.suggestions,
        "summary": review.summary,
    }
```

Add `REVIEW_LIMITER = RateLimiter(limit=10, window_seconds=60.0)` to `rate_limit.py`.

**Test:** `cd backend && uv run pytest tests/api/test_api_review_prompt.py -v`

Required assertions:
- `test_review_prompt_returns_structured_review`
- `test_review_prompt_requires_auth`
- `test_review_prompt_rate_limited`
- `test_review_prompt_handles_api_failure_gracefully`

**Done when:**
- [ ] All 4 tests pass.

---

### P10-17 — Dry-run and row-subset params in commit and preview

**Deps:** P07-09, P07-11, P10-04, P10-06
**Files:** `backend/app/api/jobs.py` (extend), `backend/tests/api/test_api_dry_run.py`, `backend/tests/api/test_api_row_subset.py`
**Goal:** Wire the new params into the existing preview and commit endpoints.

**Implementation:**

Update `POST /jobs/preview` to accept:
```python
row_subset_mode: str = Form("all"),
row_subset_n: int | None = Form(None),
```
Validate: mode must be one of 'all', 'first_n', 'random_n'. If not 'all', n must be ≥ 1.

Update `POST /jobs/:id/commit` to accept:
```python
class CommitRequest(BaseModel):
    prompt_override: str | None = None
    taxonomy: str | None = None
    titles_per_request: int | None = None
    is_dry_run: bool = False
```

Update response of `GET /jobs` and `GET /jobs/:id` to include `row_subset_mode`, `row_subset_n`, `is_dry_run`.

**Test:** `cd backend && uv run pytest tests/api/test_api_dry_run.py tests/api/test_api_row_subset.py -v`

Required assertions (test_api_dry_run.py):
- `test_commit_dry_run_returns_202`
- `test_dry_run_job_shows_is_dry_run_in_detail`
- `test_dry_run_job_shows_zero_cost`
- `test_dry_run_completes_without_worker`

Required assertions (test_api_row_subset.py):
- `test_preview_first_n_returns_subset_count`
- `test_preview_random_n_returns_subset_count`
- `test_preview_bad_row_subset_mode_400`
- `test_preview_missing_n_when_not_all_400`

**Done when:**
- [ ] All 8 tests pass.

---

### P10-13 — Router wiring + test fixture for authenticated client

**Deps:** P10-01..P10-12, P10-16, P10-17
**Files:** `backend/app/main.py` (extend), `backend/tests/conftest.py` (extend)
**Goal:** Wire all routers into the app factory. Add a `logged_in_client` fixture.

**Implementation:**
```python
# in create_app()
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(spend_router)
app.include_router(health_router)
```

```python
# conftest.py addition
@pytest.fixture
def logged_in_client(client, conn):
    # Monkeypatch the password hash env, post /auth, get cookie
    ...
```

**Test:** `cd backend && uv run pytest tests/api -v`

Required assertions:
- All API tests from P10-02..P10-12, P10-16, P10-17 pass.

Note: P10-16 (`POST /jobs/review-prompt`) and P10-17 (dry-run and row-subset params) are wired in the same jobs router.

**Done when:**
- [ ] Full API test suite green.

---

### P10-14 — HTTP request logging middleware

**Deps:** P10-01
**Files:** `backend/app/api/logging_mw.py`, `backend/tests/api/test_request_logging.py`
**Goal:** Log every request with method, path, status, duration_ms.

**Implementation:**
```python
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("nomenclator.http")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)
        log.info(
            "http.request",
            extra={"method": request.method, "path": request.url.path, "status": response.status_code, "duration_ms": duration_ms},
        )
        return response
```

**Test:** `cd backend && uv run pytest tests/api/test_request_logging.py -v`

Required assertions:
- `test_logs_contain_method_path_status` — via `caplog`.

**Done when:**
- [ ] Test passes.

---

### P10-15 — General rate-limit dependency

**Deps:** P09-04, P10-01
**Files:** `backend/app/auth/middleware.py` (extend), `backend/tests/api/test_general_rate_limit.py`
**Goal:** Apply `GENERAL_LIMITER` (60/min/session) to all authenticated endpoints via a dependency.

**Implementation:** wrap `require_session` to also call `GENERAL_LIMITER.allow(sid)` and raise `APIError("rate_limited", ..., 429)` on deny.

**Test:** `cd backend && uv run pytest tests/api/test_general_rate_limit.py -v`

Required assertions:
- `test_general_rate_limit_blocks_after_60`
- `test_general_rate_limit_separate_per_session`

**Done when:**
- [ ] Both tests pass.
