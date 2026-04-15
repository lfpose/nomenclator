# 06 — Cost Estimation and Monthly Cap

Thin glue between `pricing.py` (P05-01) and the `spend_log` DAO (P02-10). All functions are pure or take an explicit DB connection.

Reference: `spec/13-cost-model.md`, `spec/18-reliability-contract.md`.

---

### P06-01 — Cost estimator bound to template

**Deps:** P02-04, P05-01
**Files:** `backend/app/jobs/estimator.py`, `backend/tests/jobs/test_estimator.py`
**Goal:** A higher-level estimator that takes a job's cluster count and template default, returns est USD.

**Implementation:**
```python
from ..pricing import estimate_cost

def estimate_job_cost(cluster_count: int, titles_per_request: int) -> float:
    return estimate_cost(cluster_count, titles_per_request)
```

(Yes, it's a trivial passthrough — but lives in the jobs namespace for discoverability and can be extended in v2.)

**Test:** `cd backend && uv run pytest tests/jobs/test_estimator.py -v`

Required assertions:
- `test_estimate_job_cost_delegates_to_pricing`
- `test_estimate_job_cost_zero_clusters_is_zero`

**Done when:**
- [ ] Both tests pass.

---

### P06-02 — Cap check

**Deps:** P02-10, P05-01
**Files:** `backend/app/jobs/estimator.py` (extend), `backend/tests/jobs/test_cap.py`
**Goal:** A function that returns `(ok: bool, used: float, cap: float, reset_date: int | None)` given a DB connection and an estimated new cost.

**Implementation:**
```python
from dataclasses import dataclass
from ..dao.spend_log import sum_last_30_days, reset_date_approx
from ..pricing import MONTHLY_SPEND_CAP_USD

@dataclass(frozen=True)
class CapCheckResult:
    ok: bool
    used_usd: float
    estimated_usd: float
    cap_usd: float
    reset_date_unix: int | None

def check_cap(conn, estimated_usd: float, *, now: int | None = None, is_dry_run: bool = False) -> CapCheckResult:
    if is_dry_run:
        return CapCheckResult(ok=True, used_usd=0, estimated_usd=0, cap_usd=MONTHLY_SPEND_CAP_USD, reset_date_unix=None)
    used = sum_last_30_days(conn, now)
    ok = (used + estimated_usd) <= MONTHLY_SPEND_CAP_USD
    reset = reset_date_approx(conn, now)
    return CapCheckResult(
        ok=ok,
        used_usd=used,
        estimated_usd=estimated_usd,
        cap_usd=MONTHLY_SPEND_CAP_USD,
        reset_date_unix=reset,
    )
```

Note: dry-run jobs skip the cap check entirely — `is_dry_run=True` returns `ok=True` regardless of spend level, with $0 cost figures.

**Test:** `cd backend && uv run pytest tests/jobs/test_cap.py -v`

Required assertions:
- `test_cap_ok_when_empty_spend_log`
- `test_cap_blocked_when_used_plus_est_over_20`
- `test_cap_ok_when_used_plus_est_exactly_20`
- `test_cap_ignores_old_entries` — `at < now - 30d`.
- `test_cap_returns_reset_date_when_entries_exist`
- `test_cap_check_skipped_for_dry_run` — when `is_dry_run=True` is passed, `check_cap` returns `ok=True` regardless of spend level.

**Done when:**
- [ ] All 6 tests pass.

---

### P06-03 — Record actual spend

**Deps:** P02-10, P05-01
**Files:** `backend/app/jobs/estimator.py` (extend), `backend/tests/jobs/test_record_spend.py`
**Goal:** Helper that takes input+output token counts, computes actual USD, inserts into `spend_log`.

**Implementation:**
```python
from ..dao.spend_log import insert_spend
from ..pricing import HAIKU_BATCH_IN_USD_PER_MTOK, HAIKU_BATCH_OUT_USD_PER_MTOK
import time

def record_actual_spend(
    conn, *, job_id: str, batch_id: str | None, input_tokens: int, output_tokens: int
) -> float:
    usd = (
        input_tokens / 1_000_000 * HAIKU_BATCH_IN_USD_PER_MTOK
        + output_tokens / 1_000_000 * HAIKU_BATCH_OUT_USD_PER_MTOK
    )
    insert_spend(conn, job_id=job_id, batch_id=batch_id, usd=usd, at=int(time.time()))
    return usd
```

**Test:** `cd backend && uv run pytest tests/jobs/test_record_spend.py -v`

Required assertions:
- `test_record_actual_spend_inserts_row`
- `test_record_actual_spend_returns_correct_usd`
- `test_record_actual_spend_zero_tokens_returns_zero`

**Done when:**
- [ ] All 3 tests pass.

---

### P06-04 — Cap-check integration test (with jobs DAO)

**Deps:** P02-05, P02-10, P06-02
**Files:** `backend/tests/jobs/test_cap_integration.py`
**Goal:** End-to-end cap scenario: create a job, record spend across multiple batches, verify cap calculation.

**Implementation:**
Test scenario:
1. Create 3 jobs with varying costs.
2. Record spend: `$5`, `$10`, `$4` across them.
3. `check_cap(est=$2)` → ok (sum=$19, +2=21 → NOT ok since > 20).
4. `check_cap(est=$1)` → ok ($20 exactly).
5. Advance simulated time by 31 days for the oldest spend.
6. `check_cap(est=$2)` → ok again.

**Test:** `cd backend && uv run pytest tests/jobs/test_cap_integration.py -v`

Required assertions:
- `test_cap_multi_spend_scenario_pass_and_fail_boundary`
- `test_cap_recovers_when_entries_age_out`

**Done when:**
- [ ] Both tests pass.
