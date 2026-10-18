"""Additive Task-owned source-evidence columns.

A durable TaskItem/Result keeps the exact observed source occurrence and
fingerprint it was admitted under.  Those two columns are the Task's own
immutable evidence: they let a continuation, a recovery or a reopened Result
compare against the source it actually reviewed instead of against whatever a
later directory listing happens to show at the same path.

This is not a file catalog.  There is no table here, no reconciliation and no
per-file row: the columns live on the work record itself.
"""

from __future__ import annotations

import sqlite3

_TASK_SOURCE_COLUMNS: dict[str, dict[str, str]] = {
    "task_items": {
        "source_occurrence_id": "TEXT",
        "source_fingerprint": "TEXT",
        "source_fingerprint_state": "TEXT NOT NULL DEFAULT 'unverified'",
    },
    "task_results": {
        "source_occurrence_id": "TEXT",
        "source_fingerprint": "TEXT",
        "source_fingerprint_state": "TEXT NOT NULL DEFAULT 'unverified'",
    },
}


def ensure_task_occurrence_columns(connection: sqlite3.Connection) -> None:
    """Add occurrence linkage columns to TaskItem/Result tables additively."""

    for table, columns in _TASK_SOURCE_COLUMNS.items():
        existing = {
            row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for name, declaration in columns.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS task_items_source_occurrence "
        "ON task_items(storage_id, source_path, source_occurrence_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS task_results_source_occurrence "
        "ON task_results(source_storage_id, source_path, source_occurrence_id)"
    )


__all__ = ["ensure_task_occurrence_columns"]
