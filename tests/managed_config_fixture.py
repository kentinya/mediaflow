"""Publish one managed Active revision for tests that exercise current readers."""

from __future__ import annotations

import copy
import sqlite3

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.configuration_management import ManagedConfigurationRevision
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)


def seed_configuration_schema_11_store(
    document: dict,
) -> tuple[ManagedConfigurationRevision, ManagedConfigurationRevision]:
    """Reproduce a previous build's draft-era store at configuration schema 11.

    The current repository still writes the same unpublished rows for tests
    that cover the explicit draft-retirement switch.  The marker is lowered and
    the current build's ``store_origin`` record removed afterwards, so the file
    has the layout and provenance of a store created by the earlier build.
    Returns ``(active, unpublished)``.
    """

    value = copy.deepcopy(document)
    database = str(value["persistence"]["databasePath"])
    with SQLiteConfigurationRepository(database) as repository:
        service = ManagedConfigurationService(
            repository,
            bootstrap_database_path=database,
            bootstrap_document=value,
        )
        draft = service.import_draft(value, actor="tester")
        validated = service.validate(draft.revision_id, actor="tester")
        if validated.status.value != "validated":
            raise AssertionError(validated.validation_errors)
        active = service.activate(
            validated.revision_id,
            expected_version=validated.version,
            actor="tester",
        )
        unpublished = service.import_draft(value, actor="tester")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE schema_version SET version=11 WHERE component='configuration_management'"
        )
        connection.execute("DELETE FROM schema_version WHERE component='store_origin'")
        connection.commit()
    return active, unpublished


def publish_managed_document(document: dict) -> dict:
    """Import, validate and activate one canonical document on its own database.

    Returns the stored Active document.  Tests that need a full business
    runtime use this instead of relying on the retired complete-JSON startup
    fallback.  The input is not mutated.
    """

    value = copy.deepcopy(document)
    database = str(value["persistence"]["databasePath"])
    with SQLiteConfigurationRepository(database) as repository:
        service = ManagedConfigurationService(
            repository,
            bootstrap_database_path=database,
            bootstrap_document=value,
        )
        draft = service.import_draft(value, actor="tester")
        validated = service.validate(draft.revision_id, actor="tester")
        if validated.status.value != "validated":
            raise AssertionError(validated.validation_errors)
        active = service.activate(
            validated.revision_id,
            expected_version=validated.version,
            actor="tester",
        )
    return active.document
