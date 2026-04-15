# 09 — Auth

Password, sessions, rate limits. Reference: `spec/12-security.md`.

---

### P09-01 — Argon2 password verify

**Deps:** P01-02
**Files:** `backend/app/auth/passwords.py`, `backend/tests/auth/test_passwords.py`
**Goal:** Wrap `argon2-cffi` with hash-and-verify helpers.

**Implementation:**
```python
from argon2 import PasswordHasher, exceptions

_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

def hash_password(plain: str) -> str:
    return _ph.hash(plain)

def verify_password(hash_str: str, plain: str) -> bool:
    try:
        _ph.verify(hash_str, plain)
        return True
    except exceptions.VerifyMismatchError:
        return False
    except exceptions.InvalidHashError:
        return False
```

**Test:** `cd backend && uv run pytest tests/auth/test_passwords.py -v`

Required assertions:
- `test_hash_is_not_plaintext`
- `test_verify_correct_password_returns_true`
- `test_verify_wrong_password_returns_false`
- `test_verify_malformed_hash_returns_false`
- `test_hash_twice_produces_different_hashes` — argon2 uses random salt.

**Done when:**
- [ ] All 5 tests pass.

---

### P09-02 — Session token + DB storage

**Deps:** P02-11, P09-01
**Files:** `backend/app/auth/sessions.py`, `backend/tests/auth/test_sessions.py`
**Goal:** Generate secure session tokens, hash them, store only the hash.

**Implementation:**
```python
import secrets
import hashlib
from ..dao import sessions as sessions_dao

def create_session(conn, ttl_seconds: int = 2592000) -> str:
    """Returns the raw session id to set on the cookie."""
    raw = secrets.token_hex(32)  # 64 chars, 256 bits
    id_hash = hashlib.sha256(raw.encode()).hexdigest()
    sessions_dao.create_session(conn, session_id_hash=id_hash, ttl_seconds=ttl_seconds)
    return raw

def validate_session(conn, raw_sid: str | None) -> bool:
    if not raw_sid:
        return False
    id_hash = hashlib.sha256(raw_sid.encode()).hexdigest()
    return sessions_dao.get_valid_session(conn, id_hash) is not None

def destroy_session(conn, raw_sid: str) -> None:
    id_hash = hashlib.sha256(raw_sid.encode()).hexdigest()
    sessions_dao.delete_session(conn, id_hash)
```

**Test:** `cd backend && uv run pytest tests/auth/test_sessions.py -v`

Required assertions:
- `test_create_session_returns_raw_id`
- `test_validate_session_accepts_valid_cookie`
- `test_validate_session_rejects_none_or_empty`
- `test_validate_session_rejects_unknown`
- `test_destroy_session_invalidates`
- `test_db_stores_hash_not_raw` — query directly, assert row id is 64 hex chars and != raw.

**Done when:**
- [ ] All 6 tests pass.

---

### P09-03 — Auth middleware / dependency

**Deps:** P09-02
**Files:** `backend/app/auth/middleware.py`, `backend/tests/auth/test_middleware.py`
**Goal:** FastAPI dependency `require_session` that returns 401 if no valid session.

**Implementation:**
```python
from fastapi import Request, HTTPException, Depends
from ..db import db_dep
from .sessions import validate_session

def require_session(request: Request, conn=Depends(db_dep)) -> None:
    raw = request.cookies.get("sid")
    if not validate_session(conn, raw):
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthenticated", "message": "Session required."}})
```

**Test:** `cd backend && uv run pytest tests/auth/test_middleware.py -v`

Required assertions:
- `test_require_session_allows_valid_cookie`
- `test_require_session_raises_on_missing_cookie`
- `test_require_session_raises_on_invalid_cookie`
- `test_require_session_error_envelope_shape`

**Done when:**
- [ ] All 4 tests pass.

---

### P09-04 — Rate limiter (in-memory token bucket)

**Deps:** P01-02
**Files:** `backend/app/auth/rate_limit.py`, `backend/tests/auth/test_rate_limit.py`
**Goal:** A tiny in-process rate limiter keyed by a string (IP or session id) with (count, window_seconds) rules.

**Implementation:**
```python
from collections import deque
from time import time

class RateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = time()
        bucket = self._hits.setdefault(key, deque())
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True

AUTH_LIMITER = RateLimiter(limit=5, window_seconds=60.0)
COMMIT_LIMITER = RateLimiter(limit=10, window_seconds=3600.0)
GENERAL_LIMITER = RateLimiter(limit=60, window_seconds=60.0)
```

**Test:** `cd backend && uv run pytest tests/auth/test_rate_limit.py -v`

Required assertions:
- `test_allows_under_limit`
- `test_blocks_at_limit`
- `test_resets_after_window` — monkeypatch `time` to fast-forward.
- `test_independent_per_key`

**Done when:**
- [ ] All 4 tests pass.

---

### P09-05 — Auth configuration and loader

**Deps:** P09-01
**Files:** `backend/app/auth/config.py`, `backend/tests/auth/test_config.py`, `backend/.env.example`
**Goal:** Load `AUTH_PASSWORD_HASH` from env, validate it's argon2-shaped, expose it via settings.

**Implementation:**
```python
from ..settings import settings

def get_password_hash() -> str:
    h = settings.auth_password_hash
    if not h or not h.startswith("$argon2"):
        raise RuntimeError("AUTH_PASSWORD_HASH is not set or not an argon2 hash")
    return h
```

Add `AUTH_PASSWORD_HASH=` to `.env.example`.

**Test:** `cd backend && uv run pytest tests/auth/test_config.py -v`

Required assertions:
- `test_valid_hash_returned`
- `test_missing_hash_raises`
- `test_non_argon2_hash_raises`

**Done when:**
- [ ] All 3 tests pass.
