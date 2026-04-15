-- 001_initial.sql

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE task_templates (
    id                            TEXT    PRIMARY KEY,
    name                          TEXT    NOT NULL,
    system_prompt                 TEXT    NOT NULL,
    few_shots                     TEXT    NOT NULL,   -- JSON
    output_columns                TEXT    NOT NULL,   -- JSON array
    default_titles_per_request    INTEGER NOT NULL DEFAULT 25,
    created_at                    INTEGER NOT NULL
);

CREATE TABLE jobs (
    id                      TEXT    PRIMARY KEY,           -- uuid4
    task_template_id        TEXT    NOT NULL REFERENCES task_templates(id),
    status                  TEXT    NOT NULL CHECK (status IN (
                                'draft','preview','queued','submitted',
                                'polling','retrying','completed','failed','cancelled')),
    user_prompt_override    TEXT,                          -- nullable
    user_taxonomy           TEXT,                          -- nullable, newline-separated
    fuzzy_threshold         INTEGER NOT NULL DEFAULT 90 CHECK (fuzzy_threshold BETWEEN 50 AND 100),
    titles_per_request      INTEGER NOT NULL DEFAULT 25 CHECK (titles_per_request BETWEEN 1 AND 50),
    row_subset_mode         TEXT    NOT NULL DEFAULT 'all' CHECK (row_subset_mode IN ('all','first_n','random_n')),
    row_subset_n            INTEGER,
    is_dry_run              INTEGER NOT NULL DEFAULT 0,
    total_rows              INTEGER NOT NULL DEFAULT 0,
    exact_unique_rows       INTEGER NOT NULL DEFAULT 0,
    cluster_count           INTEGER NOT NULL DEFAULT 0,
    completed_rows          INTEGER NOT NULL DEFAULT 0,
    error_rows              INTEGER NOT NULL DEFAULT 0,
    est_cost_usd            REAL    NOT NULL DEFAULT 0,
    actual_cost_usd         REAL    NOT NULL DEFAULT 0,
    created_at              INTEGER NOT NULL,
    finished_at             INTEGER
);

CREATE INDEX idx_jobs_status_created ON jobs(status, created_at DESC);

CREATE TABLE job_rows (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id            TEXT    NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    cluster_id        INTEGER REFERENCES clusters(id) ON DELETE SET NULL,
    row_index         INTEGER NOT NULL,
    original          TEXT    NOT NULL,
    normalized        TEXT    NOT NULL,
    is_representative INTEGER NOT NULL DEFAULT 0  -- SQLite has no bool
);

CREATE INDEX idx_job_rows_job_order ON job_rows(job_id, row_index);
CREATE INDEX idx_job_rows_cluster    ON job_rows(cluster_id);

CREATE TABLE clusters (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                 TEXT    NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    representative_original TEXT   NOT NULL,
    normalized_key         TEXT    NOT NULL,
    member_count           INTEGER NOT NULL,
    retry_count            INTEGER NOT NULL DEFAULT 0,
    male_es                TEXT,
    female_es              TEXT,
    category               TEXT,
    error                  TEXT                        -- nullable, error code
);

CREATE INDEX idx_clusters_job ON clusters(job_id);

CREATE TABLE batches (
    id               TEXT    PRIMARY KEY,               -- Anthropic batch_id
    job_id           TEXT    NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    retry_round      INTEGER NOT NULL DEFAULT 0,
    parent_batch_id  TEXT    REFERENCES batches(id),    -- nullable self-FK
    status           TEXT    NOT NULL,                  -- mirrors Anthropic status
    request_count    INTEGER NOT NULL,
    submitted_at     INTEGER NOT NULL,
    polled_at        INTEGER,
    completed_at     INTEGER
);

CREATE INDEX idx_batches_job ON batches(job_id);

CREATE TABLE batch_requests (
    id            TEXT    PRIMARY KEY,                  -- Anthropic custom_id
    batch_id      TEXT    NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    cluster_ids   TEXT    NOT NULL,                     -- JSON array of ints
    status        TEXT    NOT NULL CHECK (status IN ('pending','completed','failed','missing')),
    raw_response  TEXT,
    error         TEXT
);

CREATE INDEX idx_batch_requests_batch ON batch_requests(batch_id);

CREATE TABLE spend_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id    TEXT    NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    batch_id  TEXT    REFERENCES batches(id),           -- nullable
    usd       REAL    NOT NULL,
    at        INTEGER NOT NULL
);

CREATE INDEX idx_spend_log_at ON spend_log(at DESC);

CREATE TABLE sessions (
    id          TEXT    PRIMARY KEY,    -- hex of random 32 bytes
    created_at  INTEGER NOT NULL,
    expires_at  INTEGER NOT NULL
);

CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- Seed the v1 task template (content spec'd in 08-prompt-spec.md)
INSERT INTO task_templates (id, name, system_prompt, few_shots, output_columns, default_titles_per_request, created_at)
VALUES ('job_titles_es', 'Spanish job title standardizer', 'PLACEHOLDER', '[]', '["male_es","female_es","category"]', 25, unixepoch());
