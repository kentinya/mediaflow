"""Read one exact managed Active revision without creating or upgrading a database.

The ordinary managed configuration repository opens its SQLite file read-write and
runs its additive schema initialization on construction.  That is correct for
management and workflow commands, but a *read-only* operator read (for example
``mediaflow files list``) must not create a database, upgrade a schema or take a
write lock just to answer "what is Active right now?".

This module therefore opens the database with ``mode=ro`` and reads only the two
existing tables it needs.  It never writes, never creates and never migrates:

* a missing database file is reported as "no Active revision yet", which is the
  truthful first-deployment answer;
* an unreadable or newer schema is reported as an explicit, actionable failure
  instead of being silently repaired;
* a corrupt document digest is reported as corrupt, never trusted.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.parse
from datetime import datetime
from pathlib import Path

from mediaflow.domain.configuration_management import (
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.manual_safety import redact_manual_value


def read_active_revision_read_only(
    database_path: str | Path,
) -> ManagedConfigurationRevision | None:
    """Return the exact persisted Active revision, or ``None`` when none exists."""

    path = Path(database_path)
    if not path.exists():
        return None
    uri = f"file:{urllib.parse.quote(str(path), safe='/')}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as error:
        raise RuntimeSnapshotUnavailable(
            "the Active configuration store could not be opened read-only",
            reason="database_unavailable",
        ) from error
    connection.row_factory = sqlite3.Row
    try:
        if not _table_exists(connection, "managed_configuration_revisions"):
            # A store that has never published managed authority simply has no
            # Active revision; that is not a failure and nothing is created.
            return None
        rows = connection.execute(
            "SELECT * FROM managed_configuration_revisions WHERE status=? ORDER BY version DESC",
            (ManagedConfigurationStatus.ACTIVE.value,),
        ).fetchall()
        if not rows:
            return None
        if len(rows) > 1:
            raise RuntimeSnapshotUnavailable(
                "managed configuration has more than one Active revision",
                reason="active_ambiguous",
            )
        return _revision(rows[0])
    except sqlite3.Error as error:
        raise RuntimeSnapshotUnavailable(
            "the Active configuration store is unreadable",
            reason="database_unreadable",
        ) from error
    finally:
        connection.close()


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _revision(row: sqlite3.Row) -> ManagedConfigurationRevision:
    try:
        document = json.loads(row["payload"])
        status = ManagedConfigurationStatus(row["status"])
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeSnapshotUnavailable(
            "the persisted Active revision is not readable",
            reason="active_unreadable",
        ) from error
    if not isinstance(document, dict):
        raise RuntimeSnapshotUnavailable(
            "the persisted Active revision document is not an object",
            reason="active_unreadable",
        )
    try:
        return ManagedConfigurationRevision(
            row["revision_id"],
            int(row["version"]),
            status,
            int(row["schema_version"]),
            row["digest"],
            document,
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            tuple(json.loads(row["validation_errors"])),
            datetime.fromisoformat(row["validated_at"]) if row["validated_at"] else None,
            datetime.fromisoformat(row["activated_at"]) if row["activated_at"] else None,
            row["base_active_revision_id"],
            int(row["revision_sequence"]) if row["revision_sequence"] is not None else None,
        )
    except (TypeError, ValueError, KeyError) as error:
        raise RuntimeSnapshotUnavailable(
            "the persisted Active revision is incomplete",
            reason="active_unreadable",
        ) from error


_FAILURE_NEXT_ACTIONS = {
    "database_unavailable": (
        "check the configured persistence.databasePath and file permissions, then retry"
    ),
    "database_unreadable": (
        "restore a readable configuration database, or point persistence.databasePath at an "
        "isolated new data directory"
    ),
    "active_ambiguous": "inspect the configuration store and publish exactly one Active revision",
    "active_unreadable": (
        "restore the last published snapshot, or stage and activate a new Draft in Settings"
    ),
}


def active_revision_failure_document(error: RuntimeSnapshotUnavailable) -> dict[str, object]:
    """One bounded, secret-free description of why Active could not be read."""

    reason = getattr(error, "reason", None) or "active_unavailable"
    return redact_manual_value(
        {
            "reason": reason,
            "durableState": "no configuration was created, changed or upgraded",
            "sideEffects": "none",
            "nextAction": _FAILURE_NEXT_ACTIONS.get(
                reason, "complete first setup in the Web Settings page and activate a revision"
            ),
        }
    )


class ReadOnlyActiveRevisionSource:
    """A minimal ``require(revision_id)`` source over one already-read Active revision.

    ``StorageBrowserService`` only calls this for a Draft/Validated storage-picker
    route.  A live library read has already resolved the exact Active revision and
    passes it directly, so this source answers exactly that one revision and
    refuses everything else instead of re-reading a mutable store.
    """

    def __init__(self, active: ManagedConfigurationRevision) -> None:
        self._active = active

    def require(self, revision_id: str) -> ManagedConfigurationRevision:
        if revision_id != self._active.revision_id:
            raise RuntimeSnapshotUnavailable(
                "only the current Active revision can be browsed read-only",
                revision_id=revision_id,
                reason="revision_not_active",
            )
        return self._active


__all__ = [
    "ReadOnlyActiveRevisionSource",
    "active_revision_failure_document",
    "read_active_revision_read_only",
]
