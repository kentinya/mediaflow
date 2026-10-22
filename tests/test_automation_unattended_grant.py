from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediaflow.application.automation_definition_occurrence import (
    AutomationDefinitionOccurrenceService,
)
from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.unattended_execution import (
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
from mediaflow.domain.manual_organize_preview import ManualPreviewStatus
from mediaflow.domain.security import (
    ROLE_PERMISSIONS,
    ApiPermission,
    ApiRole,
    ResolvedApiPrincipal,
)
from mediaflow.domain.task_persistence import PersistentTask, PersistentTaskStatus
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import ASSETS
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _definition(
    definition_id: str = "definition",
    *,
    scope: str | None = "incoming/library",
    mode: AutomationTaskRunMode = AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
    limit: int = 4,
    enabled: bool = True,
) -> AutomationTaskDefinition:
    return AutomationTaskDefinition(
        definition_id,
        definition_id,
        "resource",
        scope,
        mode,
        interval_seconds=60,
        item_limit=limit,
        enabled=enabled,
    )


def _principal(
    name: str = "admin",
    permission: ApiPermission = ApiPermission.GRANT_UNATTENDED_EXECUTION,
):
    return SimpleNamespace(principal_id=name, permissions=frozenset({permission}))


def _job(definition: AutomationTaskDefinition, *, limit: int | None = None) -> AutomationJob:
    return AutomationJob(
        "job-1",
        AutomationCommand.ORGANIZE,
        AutomationJobStatus.PENDING,
        NOW,
        NOW,
        limit=definition.item_limit if limit is None else limit,
        definition_id=definition.definition_id,
        definition_fingerprint=definition.definition_fingerprint,
        definition_version=1,
        run_mode=definition.mode,
        resource_library_id=definition.resource_library_id,
        source_scope=definition.source_scope,
        configuration_snapshot_id="revision-1",
        configuration_snapshot_digest="a" * 64,
        configuration_snapshot_version=1,
    )


def _request(api, path: str, *, method: str = "GET", body=None, token: str = "admin-token"):
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    result = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


def _shared_analysis_stub(definition):
    """A passing shared-analysis double matching the exact definition bounds.

    The independent Preview product is retired; an unattended grant now requires
    a real shared zero-mutation analysis of the exact definition scope.  These
    unit tests exercise the grant service's own admission, revoke and projection
    logic, so they supply a passing shared-analysis double rather than running a
    full Run-once journey.  The double matches the exact definition identity,
    fingerprint, configuration pin, ResourceLibrary, source scope, run mode,
    Storage and workload bound, and returns a current, zero-mutation,
    completed Preview with no blocked items.
    """
    origin = SimpleNamespace(
        definition_id=definition.definition_id,
        definition_name=definition.definition_id,
        definition_fingerprint=definition.definition_fingerprint,
        configuration_revision_id="revision-1",
        configuration_revision_version=1,
        configuration_revision_digest="a" * 64,
        resource_library_id=definition.resource_library_id,
        source_scope=definition.source_scope,
        definition_item_limit=definition.item_limit,
        effective_primary_limit=definition.item_limit,
        run_mode=definition.mode.value,
    )
    discovery = SimpleNamespace(
        discovery_id="disc-1",
        definition_origin=origin,
        storage_id=None,
        frozen=True,
        preview_id="preview-1",
    )
    preview = SimpleNamespace(
        preview_id="preview-1",
        current=True,
        zero_mutation=True,
        status=ManualPreviewStatus.PREVIEWED,
        items=(),
    )
    discovery_service = SimpleNamespace(
        latest_definition_analysis=lambda *args, **kwargs: discovery
    )
    preview_service = SimpleNamespace(latest_readonly=lambda intent_id: preview)
    return discovery_service, preview_service


def _passing_grant_service(repository, definition, **kwargs):
    """A grant service whose shared-analysis gate is satisfied by the stub."""

    discovery_service, preview_service = _shared_analysis_stub(definition)
    return UnattendedExecutionGrantService(
        repository,
        discovery_service=discovery_service,
        preview_service=preview_service,
        **kwargs,
    )


def _provider_registry_factory(*_requested):
    """A synthetic Provider registry so exact analysis needs no external service."""

    from mediaflow.application.metadata import MetadataProviderRegistry
    from mediaflow.application.strategy_test import SyntheticMetadataProvider
    from mediaflow.domain.metadata import MediaCandidate, MediaType

    return MetadataProviderRegistry(
        (
            SyntheticMetadataProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "129",
                        MediaType.MOVIE,
                        "One",
                        year=2001,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )
            ),
        )
    )


def _run_shared_analysis_api(api, *, definition_id: str = "automatic") -> str:
    """Drive a definition-bound Run once to a frozen, analyzed shared plan.

    Returns the linked exact Preview id: the shared zero-mutation organize
    analysis that an unattended grant now requires for the exact definition
    scope and bounds.  Mirrors the production Run-once journey the Web and API
    expose; only Storage reads and a zero-mutation analysis, never a mutation.
    """
    discovery = api._media_discovery.admit_definition_run_once(
        definition_id=definition_id, actor="local-admin"
    )
    for index in range(16):
        result = api._media_discovery.claim_and_run(
            worker_id=f"analysis-worker-{index}", claim_token=f"analysis-token-{index}"
        )
        if result is None:
            raise AssertionError("shared analysis discovery was not claimable")
        if result.terminal:
            break
    current = api._media_discovery.get(discovery.discovery_id)
    _analyzing, _plan = api._automation_run_once.finalize(
        discovery.discovery_id, actor="local-admin", expected_version=current.version
    )
    assert _plan is None
    # The exact plan is durable Worker work of this same run.
    analyzed = api._media_discovery.claim_and_run(
        worker_id="analysis-worker-final", claim_token="analysis-token-final"
    )
    assert analyzed is not None and analyzed.preview_id is not None
    preview = api._manual_previews.get_readonly(analyzed.preview_id)
    assert preview.status.value == "previewed"
    return preview.preview_id

    def test_grant_revoke_restart_audit_and_idempotency(self) -> None:
        definition = _definition()
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            with SQLiteTaskRepository(database) as repository:
                service = _passing_grant_service(
                    repository,
                    definition,
                    clock=lambda: NOW,
                    id_factory=iter(("grant-1", "audit-1", "audit-2")).__next__,
                )
                grant = service.grant(
                    definition,
                    configuration_snapshot_id="revision-1",
                    configuration_snapshot_digest="a" * 64,
                    configuration_snapshot_version=1,
                    principal=_principal(),
                    confirmation=True,
                    reason="approved bounded run",
                )
                self.assertEqual(grant.source_scope, "incoming/library")
                self.assertEqual(grant.status.value, "active")
                self.assertEqual(len(service.list_audit(grant.grant_id)), 1)
            with SQLiteTaskRepository(database) as reopened:
                service = _passing_grant_service(
                    reopened,
                    definition,
                    clock=lambda: NOW,
                    id_factory=lambda: "unused",
                )
                persisted = service.get_for_definition(definition.definition_id)
                self.assertEqual(persisted, grant)
                revoked = service.revoke(grant.grant_id, principal=_principal(), reason="stop")
                repeated = service.revoke(grant.grant_id, principal=_principal(), reason="ignored")
                self.assertEqual(revoked.status.value, "revoked")
                self.assertEqual(repeated, revoked)
                self.assertEqual(
                    [item.action for item in service.list_audit(grant.grant_id)],
                    ["granted", "revoked"],
                )

    def test_permission_sets_and_confirmation_are_fail_closed(self) -> None:
        self.assertEqual(ROLE_PERMISSIONS[ApiRole.VIEWER], frozenset({ApiPermission.READ}))
        self.assertNotIn(
            ApiPermission.GRANT_UNATTENDED_EXECUTION, ROLE_PERMISSIONS[ApiRole.OPERATOR]
        )
        self.assertNotIn(
            ApiPermission.GRANT_UNATTENDED_EXECUTION, ROLE_PERMISSIONS[ApiRole.EXECUTOR]
        )
        self.assertNotIn(
            ApiPermission.GRANT_UNATTENDED_EXECUTION, ROLE_PERMISSIONS[ApiRole.AUDITOR]
        )
        self.assertIn(ApiPermission.GRANT_UNATTENDED_EXECUTION, ROLE_PERMISSIONS[ApiRole.ADMIN])
        definition = _definition()
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory) / "runtime.sqlite3") as repository,
        ):
            service = _passing_grant_service(repository, definition)
            with self.assertRaises(UnattendedExecutionGrantError) as denied:
                service.grant(
                    definition,
                    configuration_snapshot_id="revision-1",
                    configuration_snapshot_digest="a" * 64,
                    configuration_snapshot_version=1,
                    principal=_principal("operator", ApiPermission.READ),
                    confirmation=True,
                )
            self.assertEqual((denied.exception.code, denied.exception.status), ("forbidden", 403))
            for confirmation in (False, None):
                with (
                    self.subTest(confirmation=confirmation),
                    self.assertRaises(UnattendedExecutionGrantError),
                ):
                    service.grant(
                        definition,
                        configuration_snapshot_id="revision-1",
                        configuration_snapshot_digest="a" * 64,
                        configuration_snapshot_version=1,
                        principal=_principal(),
                        confirmation=confirmation,
                    )
            with self.assertRaises(UnattendedExecutionGrantError):
                service.grant(
                    definition,
                    configuration_snapshot_id="revision-1",
                    configuration_snapshot_digest="a" * 64,
                    configuration_snapshot_version=1,
                    principal=_principal(),
                    confirmation=True,
                    max_items_per_run=definition.item_limit + 1,
                )

    def test_exact_authority_tuple_and_definition_changed_evidence(self) -> None:
        definition = _definition(limit=4)
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory) / "runtime.sqlite3") as repository,
        ):
            service = _passing_grant_service(repository, definition, clock=lambda: NOW)
            grant = service.grant(
                definition,
                configuration_snapshot_id="revision-1",
                configuration_snapshot_digest="a" * 64,
                configuration_snapshot_version=1,
                principal=_principal(),
                confirmation=True,
            )
            self.assertEqual(service.authorize(_job(definition), definition).grant, grant)
            mismatches = (
                replace(_job(definition), definition_id="other"),
                replace(_job(definition), resource_library_id="other"),
                replace(_job(definition), source_scope="incoming"),
                replace(
                    _job(definition),
                    run_mode="unknown-mode",
                ),
                replace(_job(definition), limit=5),
            )
            for candidate in mismatches:
                with (
                    self.subTest(candidate=candidate),
                    self.assertRaises(UnattendedExecutionGrantError),
                ):
                    service.authorize(candidate, definition)
            changed = replace(definition, name="changed")
            with self.assertRaises(UnattendedExecutionGrantError) as evidence:
                service.authorize(_job(changed), changed)
            self.assertEqual(
                evidence.exception.code,
                "unattended_execution_grant_definition_changed",
            )
            projected = service.project(
                changed,
                configuration={
                    "revisionId": "revision-1",
                    "digest": "a" * 64,
                    "version": 1,
                },
            )
            self.assertTrue(projected["definitionChangedSinceGrant"])

    def test_enable_disable_does_not_invalidate_grant(self) -> None:
        definition = _definition(enabled=True)
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory) / "runtime.sqlite3") as repository,
        ):
            service = _passing_grant_service(repository, definition, clock=lambda: NOW)
            grant = service.grant(
                definition,
                configuration_snapshot_id="revision-1",
                configuration_snapshot_digest="a" * 64,
                configuration_snapshot_version=1,
                principal=_principal(),
                confirmation=True,
            )
            disabled = replace(definition, enabled=False)
            self.assertEqual(service.get_for_definition(definition.definition_id), grant)
            self.assertFalse(service.project(disabled)["definitionChangedSinceGrant"])
            self.assertEqual(service.project(replace(disabled, enabled=True))["status"], "active")

    def test_bulk_projection_prefers_active_regrant_like_single_definition_projection(self) -> None:
        definition = _definition()
        clock = iter((NOW, NOW.replace(second=1), NOW.replace(second=2))).__next__
        identifiers = iter(("grant-1", "audit-1", "audit-2", "grant-2", "audit-3")).__next__
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory) / "runtime.sqlite3") as repository,
        ):
            service = _passing_grant_service(
                repository,
                definition,
                clock=clock,
                id_factory=identifiers,
            )
            first = service.grant(
                definition,
                configuration_snapshot_id="revision-1",
                configuration_snapshot_digest="a" * 64,
                configuration_snapshot_version=1,
                principal=_principal(),
                confirmation=True,
            )
            service.revoke(first.grant_id, principal=_principal())
            second = service.grant(
                definition,
                configuration_snapshot_id="revision-1",
                configuration_snapshot_digest="a" * 64,
                configuration_snapshot_version=1,
                principal=_principal(),
                confirmation=True,
            )

            batched = service.project_many((definition,))[definition.definition_id]
            single = service.project(definition)
            self.assertEqual(batched["status"], "active")
            self.assertEqual(batched["grantId"], second.grant_id)
            self.assertEqual(batched["grantId"], single["grantId"])
            self.assertEqual(service.get_for_definition(definition.definition_id), second)

    def test_bulk_projection_chunks_definition_page_and_does_not_hide_read_failure(self) -> None:
        definitions = tuple(_definition(f"definition-{index:03d}") for index in range(101))
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory) / "runtime.sqlite3") as repository,
        ):
            service = _passing_grant_service(repository, definitions[0], clock=lambda: NOW)
            grant = service.grant(
                definitions[0],
                configuration_snapshot_id="revision-1",
                configuration_snapshot_digest="a" * 64,
                configuration_snapshot_version=1,
                principal=_principal(),
                confirmation=True,
            )
            projected = service.project_many(definitions)
            self.assertEqual(projected[definitions[0].definition_id]["status"], "active")
            self.assertEqual(
                projected[definitions[0].definition_id]["grantId"],
                grant.grant_id,
            )

            occurrences = AutomationDefinitionOccurrenceService(repository)
            occurrences.attach_unattended_grant_service(service)
            page = occurrences.project_definitions(definitions)
            self.assertEqual(len(page), 101)
            self.assertEqual(page[0]["unattendedExecutionGrant"]["status"], "active")
            self.assertEqual(
                page[0]["unattendedExecutionGrant"]["grantId"],
                grant.grant_id,
            )

        class BrokenGrantRepository:
            def list_unattended_execution_grants(self, *, definition_ids, limit):
                raise RuntimeError("private grant database details")

        broken_service = UnattendedExecutionGrantService(BrokenGrantRepository())
        broken_occurrences = AutomationDefinitionOccurrenceService(BrokenGrantRepository())
        broken_occurrences.attach_unattended_grant_service(broken_service)
        with self.assertRaises(UnattendedExecutionGrantError) as failure:
            broken_occurrences.project_definitions((definitions[0],))
        self.assertEqual(
            (failure.exception.code, failure.exception.status),
            ("unattended_execution_grant_state_unavailable", 503),
        )
        self.assertTrue(failure.exception.next_action)
        self.assertNotIn("private grant database details", str(failure.exception))

    def test_schema_29_forward_migration_adds_grants_without_losing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            with SQLiteTaskRepository(database) as repository:
                repository.create_task(
                    PersistentTask(
                        "task-legacy",
                        "organize",
                        PersistentTaskStatus.COMPLETED,
                        False,
                        NOW,
                        NOW,
                        completed_at=NOW,
                        total_items=1,
                        completed_items=1,
                    )
                )
            with sqlite3.connect(database) as connection:
                connection.execute("UPDATE schema_version SET version=29 WHERE component='runtime'")
                connection.commit()
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.schema_version, SCHEMA_VERSION)
                self.assertIsNotNone(reopened.get_task("task-legacy"))
                tables = {
                    row[0]
                    for row in reopened._connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                self.assertIn("unattended_execution_grants", tables)
                self.assertIn("unattended_execution_grant_audit", tables)


class UnattendedGrantApiAndWebTests(unittest.TestCase):
    """The Automation grant stays definition/config/permission bound.

    The retired independent Preview product is not a prerequisite: the grant
    binds the exact definition identity, the exact managed configuration
    revision and the reviewed workload bound, and it never authorizes overwrite
    or any extra Storage effect.
    """

    def _api(self, directory, document):

        root = Path(directory)
        configuration_repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        runtime = SQLiteTaskRepository(root / "runtime.sqlite3")
        managed = ManagedConfigurationService(
            configuration_repository, bootstrap_database_path=str(root / "runtime.sqlite3")
        )
        objects = ConfigurationObjectService(managed)
        draft = managed.import_draft(document, actor="tester")
        draft = objects.create_automation_task_definition(
            draft.revision_id,
            {
                "id": "automatic",
                "name": "Automatic",
                "resourceLibraryId": "source",
                "sourceScope": "incoming",
                "mode": "automatic-organization",
                "intervalSeconds": 60,
                "itemLimit": 3,
            },
            expected_version=draft.version,
            actor="tester",
        )
        draft = objects.enable_automation_task_definition(
            draft.revision_id,
            "automatic",
            expected_version=draft.version,
            actor="tester",
        )
        validated = managed.validate(draft.revision_id, actor="tester")
        active = managed.activate(
            validated.revision_id, expected_version=validated.version, actor="tester"
        )
        api = MediaFlowApi(
            runtime,
            None,
            principals=(
                ResolvedApiPrincipal("local-admin", "admin-token", frozenset(ApiPermission)),
                ResolvedApiPrincipal(
                    "operator", "operator-token", ROLE_PERMISSIONS[ApiRole.OPERATOR]
                ),
                ResolvedApiPrincipal(
                    "executor", "executor-token", ROLE_PERMISSIONS[ApiRole.EXECUTOR]
                ),
            ),
            configuration_service=managed,
            bootstrap_document=document,
            metadata_provider_registry_factory=_provider_registry_factory,
        )
        return api, managed, objects, runtime, configuration_repository, active

    def test_api_grant_state_revoke_and_rbac(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
            document["storages"][0]["rootPath"] = str(root / "source")
            document["storages"][1]["rootPath"] = str(root / "target")
            (root / "source" / "Media" / "incoming").mkdir(parents=True)
            (root / "source" / "Media" / "incoming" / "One.2001.mkv").write_bytes(b"x" * 32)
            (root / "target").mkdir(parents=True)
            (
                api,
                managed,
                _objects,
                runtime,
                configuration_repository,
                active,
            ) = self._api(directory, document)
            try:
                # The unattended grant now requires a shared zero-mutation analysis
                # of the exact definition scope before it is eligible or admissible.
                _run_shared_analysis_api(api)
                status, eligibility = _request(
                    api, "/api/v1/automation/task-definitions/automatic/grant-state"
                )
                self.assertEqual(status, 200, eligibility)
                self.assertTrue(eligibility["grantEligibility"]["eligible"])
                self.assertIsNone(eligibility["grant"]["grantId"])

                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions/automatic/grant",
                    method="POST",
                    body={
                        "revisionId": active.revision_id,
                        "expectedVersion": active.version,
                        "maxItemsPerRun": 3,
                        "confirmation": True,
                    },
                )
                self.assertEqual(status, 201, body)
                self.assertEqual(body["grant"]["status"], "active")
                self.assertEqual(body["grant"]["currentPermission"]["status"], "valid")
                self.assertTrue(body["grantEligibility"]["eligible"])
                status, state = _request(
                    api, "/api/v1/automation/task-definitions/automatic/grant-state"
                )
                self.assertEqual(status, 200)
                self.assertEqual(state["grant"]["grantId"], body["grant"]["grantId"])
                self.assertTrue(state["grantEligibility"]["eligible"])
                status, denied = _request(
                    api,
                    "/api/v1/automation/task-definitions/automatic/grant",
                    method="POST",
                    body={"confirmation": True},
                    token="operator-token",
                )
                self.assertEqual(status, 403)
                self.assertEqual(denied["error"]["code"], "forbidden")
                status, denied = _request(
                    api,
                    "/api/v1/automation/task-definitions/automatic/grant/revoke",
                    method="POST",
                    body={},
                    token="executor-token",
                )
                self.assertEqual(status, 403)
                status, revoked = _request(
                    api,
                    "/api/v1/automation/task-definitions/automatic/grant/revoke",
                    method="POST",
                    body={"reason": "operator stop"},
                )
                self.assertEqual(status, 200)
                self.assertEqual(revoked["grant"]["status"], "revoked")
                status, audit = _request(
                    api, "/api/v1/automation/task-definitions/automatic/grant/audit"
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    [item["action"] for item in audit["items"]], ["granted", "revoked"]
                )
                status, regranted = _request(
                    api,
                    "/api/v1/automation/task-definitions/automatic/grant",
                    method="POST",
                    body={
                        "revisionId": active.revision_id,
                        "expectedVersion": active.version,
                        "maxItemsPerRun": 3,
                        "confirmation": True,
                    },
                )
                self.assertEqual(status, 201, regranted)
                status, listed = _request(api, "/api/v1/automation/task-definitions")
                self.assertEqual(status, 200)
                status, detailed = _request(api, "/api/v1/automation/task-definitions/automatic")
                self.assertEqual(status, 200)
                status, state = _request(
                    api, "/api/v1/automation/task-definitions/automatic/grant-state"
                )
                self.assertEqual(status, 200)
                list_grant = listed["items"][0]["unattendedExecutionGrant"]
                detail_grant = detailed["definition"]["unattendedExecutionGrant"]
                state_grant = state["grant"]
                for projected in (list_grant, detail_grant, state_grant):
                    self.assertEqual(projected["status"], "active")
                    self.assertEqual(projected["grantId"], regranted["grant"]["grantId"])

                # A disabled granting principal makes the live eligibility
                # ineligible without creating a Task or mutation.
                active_document = json.loads(json.dumps(active.document))
                disabled_document = json.loads(json.dumps(active_document))
                disabled_document["api"]["principals"][0]["enabled"] = False
                disabled_draft = managed.import_draft(disabled_document, actor="tester")
                disabled_validated = managed.validate(disabled_draft.revision_id, actor="tester")
                managed.activate(
                    disabled_validated.revision_id,
                    expected_version=disabled_validated.version,
                    actor="tester",
                )
                status, disabled_state = _request(
                    api, "/api/v1/automation/task-definitions/automatic/grant-state"
                )
                self.assertEqual(status, 200, disabled_state)
                self.assertFalse(disabled_state["grantEligibility"]["eligible"])
                self.assertEqual(
                    disabled_state["grantEligibility"]["error"]["code"],
                    "unattended_permission_invalid",
                )
                self.assertEqual(disabled_state["grant"]["currentPermission"]["status"], "invalid")

                authority = api._unattended_grants._permission_authority
                with patch.object(
                    type(authority),
                    "_current_principals",
                    side_effect=RuntimeError("managed authority unavailable"),
                ):
                    status, unavailable_state = _request(
                        api, "/api/v1/automation/task-definitions/automatic/grant-state"
                    )
                self.assertEqual(status, 200, unavailable_state)
                self.assertFalse(unavailable_state["grantEligibility"]["eligible"])
                self.assertEqual(
                    unavailable_state["grantEligibility"]["error"]["code"],
                    "unattended_permission_authority_unavailable",
                )
            finally:
                runtime.close()
                configuration_repository.close()

    def test_web_grant_confirmation_is_distinct_and_explicit(self) -> None:
        script = ASSETS["/ui/app.js"][1].decode("utf-8")
        self.assertIn("confirmAutomationGrant", script)
        self.assertIn("confirmAutomationGrantRevoke", script)
        self.assertIn("Confirm unattended grant", script)
        self.assertIn("scope ${scope}", script)
        self.assertIn("It does not authorize overwrite", script)
        self.assertIn("Future eligible mutations will stop at a safe item boundary", script)
        self.assertIn("/grant/revoke", script)


if __name__ == "__main__":
    unittest.main()
