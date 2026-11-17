"""Publish one managed Active revision for tests that exercise current readers."""

from __future__ import annotations

import copy

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)


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
