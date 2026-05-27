CREATE TABLE IF NOT EXISTS job_embeddings (
    job_id          TEXT    PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    unique_titles_json TEXT NOT NULL,
    embeddings_blob BLOB    NOT NULL,
    embedding_dim   INTEGER NOT NULL,
    created_at      INTEGER NOT NULL DEFAULT (unixepoch())
);
