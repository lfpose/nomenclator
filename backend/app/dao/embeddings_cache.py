from __future__ import annotations
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from sqlite3 import Connection


def save(conn: "Connection", job_id: str, unique_titles: list[str], embeddings: "np.ndarray") -> None:
    import numpy as np
    blob = embeddings.astype(np.float32).tobytes()
    dim = int(embeddings.shape[1]) if embeddings.ndim == 2 else 0
    conn.execute(
        """
        INSERT OR REPLACE INTO job_embeddings
            (job_id, unique_titles_json, embeddings_blob, embedding_dim)
        VALUES (?, ?, ?, ?)
        """,
        (job_id, json.dumps(unique_titles), blob, dim),
    )


def load(conn: "Connection", job_id: str) -> "tuple[list[str], np.ndarray] | None":
    import numpy as np
    row = conn.execute(
        "SELECT unique_titles_json, embeddings_blob, embedding_dim FROM job_embeddings WHERE job_id = ?",
        (job_id,),
    ).fetchone()
    if row is None:
        return None
    titles: list[str] = json.loads(row[0])
    dim: int = row[2]
    if not titles or dim == 0:
        return None
    arr = np.frombuffer(bytes(row[1]), dtype=np.float32).reshape(len(titles), dim)
    return titles, arr
