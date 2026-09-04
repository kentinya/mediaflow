"""Shared additive SQLite schema for FileIndex lifecycle state."""

from __future__ import annotations

import hashlib
import json
import sqlite3


def ensure_file_index_schema(connection: sqlite3.Connection) -> None:
    """Create or migrate FileIndex lifecycle tables without rewriting user rows."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS file_index (
            file_id TEXT PRIMARY KEY,
            storage_id TEXT NOT NULL,
            resource_library_id TEXT NOT NULL,
            path TEXT NOT NULL,
            filename TEXT NOT NULL,
            extension TEXT NOT NULL,
            size INTEGER NOT NULL,
            modified_at TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            stable_since TEXT,
            scan_status TEXT NOT NULL,
            change_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            missing_since TEXT,
            last_scan_id TEXT,
            occurrence_id TEXT,
            fingerprint TEXT,
            fingerprint_algorithm TEXT,
            fingerprint_evidence TEXT NOT NULL DEFAULT '{}',
            occurrence_state TEXT NOT NULL DEFAULT 'legacy',
            processing_disposition TEXT NOT NULL DEFAULT 'unknown',
            processing_result_id TEXT,
            processing_effect_certainty TEXT NOT NULL DEFAULT 'unknown',
            processing_retry_safety TEXT NOT NULL DEFAULT 'unknown',
            processing_next_action TEXT NOT NULL DEFAULT
                'observe a verified current occurrence, then run explicit analysis',
            processing_updated_at TEXT,
            UNIQUE(storage_id, resource_library_id, path)
        )
        """
    )
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(file_index)").fetchall()
    }
    additions = {
        "occurrence_id": "TEXT",
        "fingerprint": "TEXT",
        "fingerprint_algorithm": "TEXT",
        "fingerprint_evidence": "TEXT NOT NULL DEFAULT '{}'",
        "occurrence_state": "TEXT NOT NULL DEFAULT 'legacy'",
        "processing_disposition": "TEXT NOT NULL DEFAULT 'unknown'",
        "processing_result_id": "TEXT",
        "processing_effect_certainty": "TEXT NOT NULL DEFAULT 'unknown'",
        "processing_retry_safety": "TEXT NOT NULL DEFAULT 'unknown'",
        "processing_next_action": (
            "TEXT NOT NULL DEFAULT 'observe a verified current occurrence, then run explicit "
            "analysis'"
        ),
        "processing_updated_at": "TEXT",
    }
    for name, declaration in additions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE file_index ADD COLUMN {name} {declaration}")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS file_index_occurrences (
            occurrence_id TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            storage_id TEXT NOT NULL,
            resource_library_id TEXT NOT NULL,
            path TEXT NOT NULL,
            fingerprint TEXT,
            fingerprint_algorithm TEXT,
            fingerprint_evidence TEXT NOT NULL DEFAULT '{}',
            occurrence_state TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 1,
            superseded_at TEXT,
            processing_disposition TEXT NOT NULL DEFAULT 'unknown',
            processing_result_id TEXT,
            processing_effect_certainty TEXT NOT NULL DEFAULT 'unknown',
            processing_retry_safety TEXT NOT NULL DEFAULT 'unknown',
            processing_next_action TEXT NOT NULL DEFAULT
                'observe a verified current occurrence, then run explicit analysis',
            processing_updated_at TEXT,
            UNIQUE(file_id, occurrence_id)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS file_index_occurrences_file_time
        ON file_index_occurrences(file_id, last_seen_at DESC, occurrence_id DESC)
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS file_index_reprocess_requests (
            request_id TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            occurrence_id TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            actor TEXT NOT NULL,
            requested_at TEXT NOT NULL,
            status TEXT NOT NULL,
            next_action TEXT NOT NULL,
            error TEXT,
            UNIQUE(request_id),
            FOREIGN KEY(file_id) REFERENCES file_index(file_id)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS file_index_reprocess_active
        ON file_index_reprocess_requests(file_id, occurrence_id, status, requested_at)
        """
    )
    _backfill_legacy_occurrences(connection)


def ensure_task_occurrence_columns(connection: sqlite3.Connection) -> None:
    """Add occurrence linkage columns to TaskItem/Result tables additively."""

    for table, columns in {
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
    }.items():
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


def _backfill_legacy_occurrences(connection: sqlite3.Connection) -> None:
    """Give pre-lifecycle rows an explicit unverified historical identity."""

    rows = connection.execute(
        "SELECT * FROM file_index WHERE occurrence_id IS NULL OR occurrence_state IS NULL"
    ).fetchall()
    for row in rows:
        occurrence_id = "legacy-" + hashlib.sha256(row["file_id"].encode("utf-8")).hexdigest()[:40]
        evidence = row["fingerprint_evidence"] or "{}"
        try:
            json.loads(evidence)
        except (TypeError, json.JSONDecodeError):
            evidence = "{}"
        connection.execute(
            """
            UPDATE file_index SET occurrence_id=?, occurrence_state='legacy',
                fingerprint=NULL, fingerprint_algorithm=NULL, fingerprint_evidence=?,
                processing_disposition=COALESCE(processing_disposition, 'unknown'),
                processing_effect_certainty=COALESCE(processing_effect_certainty, 'unknown'),
                processing_retry_safety=COALESCE(processing_retry_safety, 'unknown'),
                processing_next_action=COALESCE(processing_next_action,
                    'observe a verified current occurrence, then run explicit analysis')
            WHERE file_id=?
            """,
            (occurrence_id, evidence, row["file_id"]),
        )
        _insert_occurrence_from_row(
            connection,
            {
                **{key: row[key] for key in row.keys()},
                "occurrence_id": occurrence_id,
                "occurrence_state": "legacy",
                "fingerprint": None,
                "fingerprint_algorithm": None,
                "fingerprint_evidence": evidence,
            },
        )


def _insert_occurrence_from_row(connection: sqlite3.Connection, row: dict) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO file_index_occurrences (
            occurrence_id, file_id, storage_id, resource_library_id, path,
            fingerprint, fingerprint_algorithm, fingerprint_evidence, occurrence_state,
            first_seen_at, last_seen_at, is_current, superseded_at,
            processing_disposition, processing_result_id, processing_effect_certainty,
            processing_retry_safety, processing_next_action, processing_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["occurrence_id"],
            row["file_id"],
            row["storage_id"],
            row["resource_library_id"],
            row["path"],
            row.get("fingerprint"),
            row.get("fingerprint_algorithm"),
            row.get("fingerprint_evidence") or "{}",
            row.get("occurrence_state") or "legacy",
            row["first_seen_at"],
            row["last_seen_at"],
            1,
            None,
            row.get("processing_disposition") or "unknown",
            row.get("processing_result_id"),
            row.get("processing_effect_certainty") or "unknown",
            row.get("processing_retry_safety") or "unknown",
            row.get("processing_next_action")
            or "observe a verified current occurrence, then run explicit analysis",
            row.get("processing_updated_at"),
        ),
    )
