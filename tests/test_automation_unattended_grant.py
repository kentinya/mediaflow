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


class UnattendedGrantPersistenceTests(unittest.TestCase):
    def test_grant_revoke_restart_audit_and_idempotency(self) -> None:
        definition = _definition()
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            with SQLiteTaskRepository(database) as repository:
                service = UnattendedExecutionGrantService(
                    repository,
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
                service = UnattendedExecutionGrantService(
                    reopened,
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
            service = UnattendedExecutionGrantService(repository)
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
            service = UnattendedExecutionGrantService(repository, clock=lambda: NOW)
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
                replace(_job(definition), run_mode=AutomationTaskRunMode.SCAN_AND_PLAN),
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
            service = UnattendedExecutionGrantService(repository, clock=lambda: NOW)
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

    def test_schema_29_forward_migration_adds_grants_without_losing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            with SQLiteTaskRepository(database) as repository:
                repository.create_task(
                    PersistentTask(
                        "task-legacy",
                        "preview",
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
    def test_api_grant_state_revoke_and_rbac(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
            document["storages"][0]["rootPath"] = str(root / "source")
            document["storages"][1]["rootPath"] = str(root / "target")
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as configuration,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
            ):
                managed = ManagedConfigurationService(
                    configuration,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
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
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                api = MediaFlowApi(
                    runtime,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                        ResolvedApiPrincipal(
                            "operator", "operator-token", ROLE_PERMISSIONS[ApiRole.OPERATOR]
                        ),
                        ResolvedApiPrincipal(
                            "executor", "executor-token", ROLE_PERMISSIONS[ApiRole.EXECUTOR]
                        ),
                    ),
                    configuration_service=managed,
                    bootstrap_document=document,
                )
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
                status, state = _request(
                    api, "/api/v1/automation/task-definitions/automatic/grant-state"
                )
                self.assertEqual(status, 200)
                self.assertEqual(state["grant"]["grantId"], body["grant"]["grantId"])
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
