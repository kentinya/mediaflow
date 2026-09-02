from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from mediaflow.application.unattended_execution import (
    UnattendedExecutionBoundaryError,
    UnattendedExecutionGrantError,
    UnattendedExecutionGrantService,
)
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
    AutomationTaskDefinition,
    AutomationTaskRunMode,
)
from mediaflow.domain.automation_task_definition_preview import (
    AutomationTaskDefinitionPreviewItemStatus,
    AutomationTaskDefinitionPreviewStatus,
)
from mediaflow.domain.security import ApiPrincipalDefinition, ApiRole
from mediaflow.final_cli import _ConfiguredPermissionAuthority
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

NOW = datetime(2026, 9, 2, tzinfo=UTC)


def _definition() -> AutomationTaskDefinition:
    return AutomationTaskDefinition(
        "definition",
        "Definition",
        "resource",
        "incoming",
        AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
        interval_seconds=60,
        item_limit=4,
        enabled=True,
    )


def _job(definition: AutomationTaskDefinition) -> AutomationJob:
    return AutomationJob(
        "job",
        AutomationCommand.ORGANIZE,
        AutomationJobStatus.PENDING,
        NOW,
        NOW,
        limit=4,
        definition_id=definition.definition_id,
        definition_fingerprint=definition.definition_fingerprint,
        definition_version=1,
        run_mode=definition.mode,
        resource_library_id=definition.resource_library_id,
        source_scope=definition.source_scope,
        configuration_snapshot_id="revision",
        configuration_snapshot_digest="a" * 64,
        configuration_snapshot_version=1,
    )


class _PreviewReader:
    def __init__(self, preview):
        self.preview = preview

    def get_readonly(self, preview_id):
        if preview_id != self.preview.preview_id:
            raise LookupError("Preview not found")
        return self.preview


class _PermissionAuthority:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.calls = []

    def has_permission(self, principal_id, permission):
        self.calls.append((principal_id, permission))
        return self.allowed


def _preview(
    definition,
    *,
    preview_id="preview-1",
    status=AutomationTaskDefinitionPreviewStatus.PREVIEWED,
    current=True,
    item_statuses=(),
):
    items = tuple(SimpleNamespace(status=value) for value in item_statuses)
    return SimpleNamespace(
        preview_id=preview_id,
        definition_id=definition.definition_id,
        definition_fingerprint=definition.definition_fingerprint,
        configuration_revision_id="revision",
        configuration_revision_digest="a" * 64,
        configuration_revision_version=1,
        resource_library_id=definition.resource_library_id,
        storage_id="storage",
        source_scope=definition.source_scope,
        run_mode=definition.mode.value,
        effective_item_limit=definition.item_limit,
        current=current,
        zero_mutation=True,
        status=status,
        boundary_errors=(),
        items=items,
    )


class AutomationPreviewGrantGateTests(unittest.TestCase):
    def test_missing_preview_is_rejected_without_grant_or_audit(self):
        definition = _definition()
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory) / "runtime.sqlite3") as repository:
                service = UnattendedExecutionGrantService(
                    repository,
                    preview_service=_PreviewReader(_preview(definition)),
                    clock=lambda: NOW,
                )
                with self.assertRaisesRegex(
                    UnattendedExecutionGrantError, "exact Automation Preview is required"
                ):
                    service.grant(
                        definition,
                        configuration_snapshot_id="revision",
                        configuration_snapshot_digest="a" * 64,
                        configuration_snapshot_version=1,
                        actor="principal",
                        confirmation=True,
                        storage_id="storage",
                    )
                self.assertIsNone(service.get_for_definition(definition.definition_id))
                self.assertEqual(repository.list_unattended_execution_grant_audit("missing"), ())

    def test_exact_preview_linkage_survives_reload_and_different_preview_cannot_replace(self):
        definition = _definition()
        preview = _preview(definition)
        reader = _PreviewReader(preview)
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            with SQLiteTaskRepository(database) as repository:
                service = UnattendedExecutionGrantService(
                    repository,
                    preview_service=reader,
                    clock=lambda: NOW,
                    id_factory=iter(("grant", "audit")).__next__,
                )
                grant = service.grant(
                    definition,
                    configuration_snapshot_id="revision",
                    configuration_snapshot_digest="a" * 64,
                    configuration_snapshot_version=1,
                    actor="principal",
                    confirmation=True,
                    preview_id=preview.preview_id,
                    storage_id="storage",
                )
                self.assertEqual(grant.preview_id, preview.preview_id)
                self.assertEqual(grant.document()["previewId"], preview.preview_id)
            with SQLiteTaskRepository(database) as reopened:
                loaded = reopened.get_unattended_execution_grant(grant.grant_id)
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded.preview_id, preview.preview_id)
                reader.preview = _preview(definition, preview_id="preview-2")
                with self.assertRaisesRegex(
                    UnattendedExecutionGrantError, "already exists for different exact bounds"
                ):
                    UnattendedExecutionGrantService(
                        reopened,
                        preview_service=reader,
                        clock=lambda: NOW,
                    ).grant(
                        definition,
                        configuration_snapshot_id="revision",
                        configuration_snapshot_digest="a" * 64,
                        configuration_snapshot_version=1,
                        actor="principal",
                        confirmation=True,
                        preview_id="preview-2",
                        storage_id="storage",
                    )

    def test_blocked_preview_is_rejected_before_persistence(self):
        definition = _definition()
        preview = _preview(
            definition,
            item_statuses=(AutomationTaskDefinitionPreviewItemStatus.BLOCKED,),
        )
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory) / "runtime.sqlite3") as repository:
                service = UnattendedExecutionGrantService(
                    repository,
                    preview_service=_PreviewReader(preview),
                )
                with self.assertRaisesRegex(UnattendedExecutionGrantError, "blocked or failed"):
                    service.grant(
                        definition,
                        configuration_snapshot_id="revision",
                        configuration_snapshot_digest="a" * 64,
                        configuration_snapshot_version=1,
                        actor="principal",
                        confirmation=True,
                        preview_id=preview.preview_id,
                        storage_id="storage",
                    )
                self.assertIsNone(service.get_for_definition(definition.definition_id))

    def test_current_permission_is_resolved_at_admission_and_each_effect_boundary(self):
        definition = _definition()
        preview = _preview(definition)
        authority = _PermissionAuthority()
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory) / "runtime.sqlite3") as repository:
                service = UnattendedExecutionGrantService(
                    repository,
                    preview_service=_PreviewReader(preview),
                    permission_authority=authority,
                    clock=lambda: NOW,
                )
                grant = service.grant(
                    definition,
                    configuration_snapshot_id="revision",
                    configuration_snapshot_digest="a" * 64,
                    configuration_snapshot_version=1,
                    actor="principal",
                    confirmation=True,
                    preview_id=preview.preview_id,
                    storage_id="storage",
                )
                service.authorize(_job(definition), definition)
                self.assertGreaterEqual(len(authority.calls), 1)
                authority.allowed = False
                with self.assertRaises(UnattendedExecutionBoundaryError) as failure:
                    service.assert_live(_job(definition), definition)
                self.assertEqual(failure.exception.category, "unattended_permission_invalid")
                current = service.get_for_definition(definition.definition_id)
                self.assertEqual(grant.grant_id, current.grant_id)

    def test_production_permission_authority_reloads_roles_and_enabled_state(self):
        state = SimpleNamespace(
            api_principals=(
                ApiPrincipalDefinition("principal", "UNUSED_TOKEN_ENV", (ApiRole.ADMIN,)),
            ),
            api_token_env=None,
        )
        authority = _ConfiguredPermissionAuthority(lambda: state)
        self.assertTrue(authority.has_permission("principal", "grant_unattended_execution"))
        state.api_principals = (
            ApiPrincipalDefinition("principal", "UNUSED_TOKEN_ENV", (ApiRole.OPERATOR,)),
        )
        self.assertFalse(authority.has_permission("principal", "grant_unattended_execution"))
        state.api_principals = (
            ApiPrincipalDefinition("principal", "UNUSED_TOKEN_ENV", (ApiRole.ADMIN,), False),
        )
        self.assertFalse(authority.has_permission("principal", "grant_unattended_execution"))


if __name__ == "__main__":
    unittest.main()
