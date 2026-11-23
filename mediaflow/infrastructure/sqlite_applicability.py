"""Decide whether an existing SQLite file is a supported MediaFlow database.

The decision is read-only and runs before a repository creates a table, writes
a schema marker or registers a publishing authority.  A current empty path, a
zero-table SQLite file, and a database created by this build are supported.
Creation records a ``store_origin`` marker with the creating runtime schema, so
a configuration-only first-setup store is accepted only when this build wrote
that marker.  A configuration-only store from an earlier build (its
configuration marker can equal the current number), a runtime database created
by any other MediaFlow version, a retired V1 Job schema, a newer schema, a
foreign file and a partially written store are not.

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

#: The first current-generation runtime schema.  Any lower marker is the
#: retired V1 Job schema; any older current-generation marker is a previous
#: MediaFlow version and is refused by the exact-version check below.
MIN_RUNTIME_SCHEMA_VERSION = 58

#: The marker a build writes when it first creates a database file.
#: Its value is the creating build's runtime schema.  Configuration-only
#: stores from earlier builds have no such marker even when their
#: configuration marker already equals the current number.
STORE_ORIGIN_COMPONENT = "store_origin"

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
            "The file was not modified; keep it for the version that created it if you "
            "still need its data, start this version with a new empty data directory, check "
            "the configured database path, or restore a backup created by this MediaFlow "
            "version"
        )


@dataclass(frozen=True)
class DatabaseMarkers:
    runtime_version: int | None
    configuration_version: int | None
    origin_version: int | None
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
        return DatabaseMarkers(None, None, None, tables)
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
        versions.get(STORE_ORIGIN_COMPONENT),
        tables,
    )


def read_database_markers(database_path: str | Path) -> DatabaseMarkers:
    """Read schema markers and table names through one read-only connection."""

    path = Path(database_path)
    if not path.exists() or path.stat().st_size == 0:
        return DatabaseMarkers(None, None, None, frozenset())
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
        if markers.runtime_version < current_runtime_version:
            raise DatabaseApplicabilityError(
                "its runtime schema was created by a previous MediaFlow version "
                f"(found {markers.runtime_version}, expected {current_runtime_version}); "
                "this version only opens an empty database or one it created"
            )
    elif tables & RETIRED_TABLE_NAMES:
        raise DatabaseApplicabilityError(
            "it contains the retired V1 Job schema without a current runtime marker"
        )
    if markers.origin_version is not None:
        if markers.origin_version > current_runtime_version:
            raise DatabaseApplicabilityError(
                "its store origin marker is newer than this MediaFlow version"
            )
        if markers.origin_version < current_runtime_version:
            raise DatabaseApplicabilityError(
                "its store origin marker was written by a previous MediaFlow version "
                f"(found {markers.origin_version}, expected {current_runtime_version}); "
                "this version only opens an empty database or one it created"
            )
    elif (
        markers.runtime_version is None
        and markers.configuration_version == current_configuration_version
    ):
        # The configuration-only layout has been unchanged across versions, so
        # its marker alone cannot prove this build created the file.  Only a
        # store that explicitly records this build's origin is a first-setup
        # database; an earlier `config initialize`/`config publish` store has
        # the same configuration marker but no origin marker.
        raise DatabaseApplicabilityError(
            "it is a configuration-only database created by a previous MediaFlow "
            f"version (configuration schema {markers.configuration_version}, no store "
            f"origin marker; expected origin {current_runtime_version}); this version "
            "only opens an empty database or one it created"
        )
    if markers.configuration_version is not None:
        if markers.configuration_version > current_configuration_version:
            raise DatabaseApplicabilityError(
                "its configuration schema is newer than this MediaFlow version"
            )
        if markers.configuration_version < current_configuration_version:
            raise DatabaseApplicabilityError(
                "its configuration schema was created by a previous MediaFlow version "
                f"(found {markers.configuration_version}, expected "
                f"{current_configuration_version}); this version only opens an empty "
                "database or one it created"
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
