import json

from sqlite3 import Connection
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskTemplate:
    id: str
    name: str
    system_prompt: str
    few_shots: list
    output_columns: list[str]
    default_titles_per_request: int


def get_template(conn: Connection, template_id: str) -> TaskTemplate | None:
    """Fetch a task template by ID, or None if not found."""
    row = conn.execute(
        "SELECT * FROM task_templates WHERE id = ?",
        (template_id,)
    ).fetchone()
    if row is None:
        return None
    return TaskTemplate(
        id=row["id"],
        name=row["name"],
        system_prompt=row["system_prompt"],
        few_shots=json.loads(row["few_shots"]),
        output_columns=json.loads(row["output_columns"]),
        default_titles_per_request=row["default_titles_per_request"],
    )
