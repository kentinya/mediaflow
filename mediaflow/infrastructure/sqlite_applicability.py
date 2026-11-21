"""Decide whether an existing SQLite file is a supported MediaFlow database.

The decision is read-only and runs before a repository creates a table, writes
a schema marker or registers a publishing authority.  A current empty path, a
zero-table SQLite file, a current V2 runtime/configuration database and a
configuration-only first-setup database are supported.  A retired V1 Job
schema, a newer schema, a foreign file and a partially written store are not.

Repositories repeat the same decision on their own connection inside the
``BEGIN IMMEDIATE`` transaction that creates the current structure, so two
resident services racing on one empty path observe exactly one committed
layout: the first process creates tables, indexes and the version mark
together; the second waits for that commit and opens the committed store as an
existing database instead of writing a second marker or seeing half a schema.

The caller receives one bounded :class:`DatabaseApplicabilityError`; the file is
left byte-for-byte unchanged, so the operator can inspect the configured path or
restore a verified supported backup.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

#: The first runtime schema whose Task flow/structure this build can use.  Any
#: lower marker is the retired V1 Job schema.
MIN_RUNTIME_SCHEMA_VERSION = 58

#: The immediately previous managed-configuration schema.  It contains the same
#: current tables plus unpublished draft revisions that this build retires
#: only through the explicit operator-confirmed data switch.  Any older marker
#: remains unsupported.
MIN_CONFIGURATION_SCHEMA_VERSION = 11

#: Tables that prove a pre-V2 database even when its runtime marker is absent.
RETIRED_TABLE_NAMES = frozenset(
    {
        "jobs",
        "schedules",
        "execution_tickets",
        "execution_authorizations",
        "recovery_continuations",
    }
)

#: Tables owned by the current configuration repository.  Their presence
#: without the configuration marker proves an interrupted/foreign store.
CONFIGURATION_TABLES = frozenset(
    {
        "configuration_objects",
        "configuration_references",
        "configuration_change_audits",
        "managed_configuration_revisions",
        "managed_local_setup_checks",
        "managed_storage_setup_checks",
        "managed_recognition_strategy_tests",
        "managed_naming_previews",
        "managed_classification_previews",
        "managed_organize_authority_previews",
        "managed_destination_previews",
        "managed_destination_prechecks",
        "managed_internal_keys",
        "managed_configuration_authority",
    }
)


class DatabaseApplicabilityError(ValueError):
    """A bounded refusal that names the safe next step without raw SQL."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(
            f"the configured database is not usable by this MediaFlow version: {reason}. "
            "The file was not modified; check the configured database path or restore a "
            "verified supported backup"
        )


@dataclass(frozen=True)
class DatabaseMarkers:
    runtime_version: int | None
    configuration_version: int | None
    tables: frozenset[str]


def read_database_markers_from_connection(
    connection: sqlite3.Connection,
) -> DatabaseMarkers:
    """Read markers on a caller-owned connection, including inside its transaction.

    Repositories use this immediately after acquiring their write transaction so
    the supported-layout decision reads only committed state, never a table or
    marker another process has not committed yet.
    """

    try:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    except sqlite3.DatabaseError as error:
        raise DatabaseApplicabilityError("the file is not a readable SQLite database") from error
    tables = frozenset(str(row[0]) for row in rows)
    if "schema_version" not in tables:
        return DatabaseMarkers(None, None, tables)
    try:
        version_rows = connection.execute(
            "SELECT component, version FROM schema_version"
        ).fetchall()
    except sqlite3.DatabaseError as error:
        raise DatabaseApplicabilityError(
            "the schema marker cannot be read as a current MediaFlow database"
        ) from error
    versions = {str(row[0]): int(row[1]) for row in version_rows if isinstance(row[0], str)}
    return DatabaseMarkers(
        versions.get("runtime"),
        versions.get("configuration_management"),
        tables,
    )


def read_database_markers(database_path: str | Path) -> DatabaseMarkers:
    """Read schema markers and table names through one read-only connection."""

    path = Path(database_path)
    if not path.exists() or path.stat().st_size == 0:
        return DatabaseMarkers(None, None, frozenset())
    try:
        connection = sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro",
            uri=True,
        )
    except sqlite3.DatabaseError as error:
        raise DatabaseApplicabilityError("the file is not a readable SQLite database") from error
    try:
        connection.row_factory = sqlite3.Row
        return read_database_markers_from_connection(connection)
    finally:
        connection.close()


def evaluate_database_applicability(
    markers: DatabaseMarkers,
    *,
    current_runtime_version: int,
    current_configuration_version: int,
) -> DatabaseMarkers:
    """Refuse a marker/table layout this build cannot use as a current store."""

    tables = markers.tables
    if markers.runtime_version is not None:
        if markers.runtime_version > current_runtime_version:
            raise DatabaseApplicabilityError(
                "its runtime schema is newer than this MediaFlow version"
            )
        if markers.runtime_version < MIN_RUNTIME_SCHEMA_VERSION:
            raise DatabaseApplicabilityError("its runtime schema is the retired V1 Job schema")
    elif tables & RETIRED_TABLE_NAMES:
        raise DatabaseApplicabilityError(
            "it contains the retired V1 Job schema without a current runtime marker"
        )
    if markers.configuration_version is not None:
        if markers.configuration_version > current_configuration_version:
            raise DatabaseApplicabilityError(
                "its configuration schema is newer than this MediaFlow version"
            )
        if markers.configuration_version < MIN_CONFIGURATION_SCHEMA_VERSION:
            raise DatabaseApplicabilityError(
                "its configuration schema predates the current supported V2 configuration"
            )
    elif tables & CONFIGURATION_TABLES:
        raise DatabaseApplicabilityError(
            "it contains configuration tables without a current configuration marker"
        )
    if markers.runtime_version is None and markers.configuration_version is None and tables:
        # A file with tables but no MediaFlow schema marker is another
        # application's SQLite database (or an interrupted foreign write).  It
        # must never be adopted as a new store: doing so would add MediaFlow
        # tables to a file the operator only aimed at by mistake.
        raise DatabaseApplicabilityError(
            "it contains tables but no current MediaFlow schema marker"
        )
    return markers


def assert_supported_database(
    database_path: str | Path,
    *,
    current_runtime_version: int,
    current_configuration_version: int,
) -> DatabaseMarkers:
    """Refuse an unsupported existing file before the caller writes anything."""

    markers = read_database_markers(database_path)
    return evaluate_database_applicability(
        markers,
        current_runtime_version=current_runtime_version,
        current_configuration_version=current_configuration_version,
    )
