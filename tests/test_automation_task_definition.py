from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.automation import (
    AutomationTaskDefinition,
    AutomationTaskRunMode,
)
from mediaflow.domain.configuration_management import ConfigurationVersionConflict
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import ASSETS
from mediaflow.interfaces.service_api import MediaFlowApi


def _document(root: Path) -> dict:
    value = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    value["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    value["storages"][0]["rootPath"] = str(root / "source")
    value["storages"][1]["rootPath"] = str(root / "target")
    return value


def _request(
    api,
    path: str,
    *,
    method: str = "GET",
    body=None,
    token: str = "admin-token",
    query: str = "",
):
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    result = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


def _api(runtime, managed, document, *, include_viewer: bool = True):
    principals = [
        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
    ]
    if include_viewer:
        principals.append(
            ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        )
    return MediaFlowApi(
        runtime,
        None,
        principals=tuple(principals),
        configuration_service=managed,
        bootstrap_document=document,
    )


def _js_function_body(script: str, name: str) -> str:
    """Return one JavaScript function body from the served asset by brace matching."""

    opening = script.index("{", script.index(f"function {name}("))
    return _js_braced_body(script, opening)


def _js_braced_body(script: str, opening: int) -> str:
    """Return the body whose opening brace is at ``opening``."""

    depth = 0
    for index in range(opening, len(script)):
        if script[index] == "{":
            depth += 1
        elif script[index] == "}":
            depth -= 1
            if depth == 0:
                return script[opening + 1 : index]
    raise AssertionError("JavaScript block has an unbalanced body")


class AutomationTaskDefinitionDomainTests(unittest.TestCase):
    def test_interval_and_cron_are_canonical_and_scope_is_normalized(self) -> None:
        interval = AutomationTaskDefinition.from_document(
            {
                "id": "daily",
                "name": "Daily scan",
                "resourceLibraryId": "source",
                "mode": "scan",
                "sourceScope": "incoming/films",
                "intervalSeconds": 3600,
                "itemLimit": 20,
            }
        )
        self.assertEqual(interval.mode, AutomationTaskRunMode.SCAN_ONLY)
        self.assertEqual(interval.source_scope, "incoming/films")
        self.assertEqual(interval.document()["mode"], "scan-only")
        cron = AutomationTaskDefinition.from_document(
            {
                "id": "morning",
                "name": "Morning plan",
                "resourceLibraryId": "source",
                "mode": "scan-and-plan",
                "cron": "0 8 * * *",
                "timezone": "UTC",
            }
        )
        self.assertEqual(cron.schedule_type, "cron")
        self.assertEqual(cron.document()["timezone"], "UTC")

    def test_unsafe_or_policy_bearing_fields_are_rejected(self) -> None:
        base = {
            "id": "task",
            "name": "Task",
            "resourceLibraryId": "source",
            "mode": "scan-only",
            "intervalSeconds": 60,
        }
        for field, value in (
            ("sourceScope", "../outside"),
            ("sourceScope", "/absolute"),
            ("providerId", "tmdb"),
            ("itemLimit", 10_001),
        ):
            with self.subTest(field=field):
                candidate = {**base, field: value}
                with self.assertRaises(ValueError):
                    AutomationTaskDefinition.from_document(candidate)

    def test_resource_reference_must_exist_and_be_enabled(self) -> None:
        value = {
            "id": "task",
            "name": "Task",
            "resourceLibraryId": "source",
            "mode": "scan-only",
            "intervalSeconds": 60,
        }
        with self.assertRaisesRegex(ValueError, "unknown ResourceLibrary"):
            AutomationTaskDefinition.from_document(value, resource_libraries=[])
        with self.assertRaisesRegex(ValueError, "must be enabled"):
            AutomationTaskDefinition.from_document(
                value,
                resource_libraries=[{"id": "source", "enabled": False}],
            )


class AutomationTaskDefinitionManagedTests(unittest.TestCase):
    def test_lifecycle_copy_enable_reload_and_active_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = _document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(document, actor="tester")
                draft = objects.create_automation_task_definition(
                    draft.revision_id,
                    {
                        "id": "task",
                        "name": "Task",
                        "resourceLibraryId": "source",
                        "mode": "automatic-organization",
                        "sourceScope": "incoming",
                        "intervalSeconds": 60,
                        "itemLimit": 12,
                    },
                    expected_version=draft.version,
                    actor="tester",
                )
                self.assertEqual(draft.document["automationTaskDefinitions"][0]["enabled"], False)
                draft = objects.enable_automation_task_definition(
                    draft.revision_id,
                    "task",
                    expected_version=draft.version,
                    actor="tester",
                )
                draft = objects.copy_definition(
                    draft.revision_id,
                    object_id="task",
                    expected_version=draft.version,
                    actor="tester",
                )
                copied = draft.document["automationTaskDefinitions"][-1]
                self.assertEqual(copied["id"], "task-copy")
                self.assertFalse(copied["enabled"])
                validated = managed.validate(draft.revision_id, actor="tester")
                active = managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                self.assertEqual(
                    active.document["automationTaskDefinitions"][-1]["id"], "task-copy"
                )
                self.assertEqual(
                    load_runtime_configuration(active.document)
                    .automation_task_definitions[-1]
                    .definition_id,
                    "task-copy",
                )
                self.assertEqual(managed.active().digest, active.digest)
                audits = repository.list_revision_audits(active.revision_id)
                actions = [
                    item.safe_after().get("objectChange", {}).get("action") for item in audits
                ]
                self.assertIn("create", actions)
                self.assertIn("enable", actions)
                self.assertIn("copy", actions)
                validation = next(item for item in audits if item.action == "validate")
                evidence = validation.safe_after()["automationTaskDefinitions"]["items"][-1]
                self.assertEqual(evidence["resourceLibraryId"], "source")
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as reopened:
                reloaded = ManagedConfigurationService(
                    reopened,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                ).active()
                self.assertEqual(
                    reloaded.document["automationTaskDefinitions"][-1]["id"], "task-copy"
                )

    def test_edit_disable_and_immutable_active_protection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = _document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(document, actor="tester")
                draft = objects.create_automation_task_definition(
                    draft.revision_id,
                    {
                        "id": "task",
                        "name": "Task",
                        "resourceLibraryId": "source",
                        "mode": "scan-only",
                        "intervalSeconds": 60,
                        "itemLimit": 12,
                    },
                    expected_version=draft.version,
                    actor="tester",
                )
                edited = objects.edit_automation_task_definition(
                    draft.revision_id,
                    "task",
                    {
                        "id": "task",
                        "name": "Task edited",
                        "resourceLibraryId": "source",
                        "mode": "scan-and-plan",
                        "sourceScope": "incoming/films",
                        "intervalSeconds": 120,
                        "itemLimit": 5,
                    },
                    expected_version=draft.version,
                    actor="tester",
                )
                self.assertEqual(edited.version, draft.version + 1)
                self.assertEqual(
                    edited.document["automationTaskDefinitions"][0]["name"], "Task edited"
                )
                disabled = objects.disable_automation_task_definition(
                    edited.revision_id,
                    "task",
                    expected_version=edited.version,
                    actor="tester",
                )
                self.assertFalse(disabled.document["automationTaskDefinitions"][0]["enabled"])
                enabled = objects.enable_automation_task_definition(
                    disabled.revision_id,
                    "task",
                    expected_version=disabled.version,
                    actor="tester",
                )
                self.assertTrue(enabled.document["automationTaskDefinitions"][0]["enabled"])
                actions = [
                    item.safe_after().get("objectChange", {}).get("action")
                    for item in repository.list_revision_audits(enabled.revision_id)
                ]
                for action in ("create", "edit", "disable", "enable"):
                    self.assertIn(action, actions)
                validated = managed.validate(enabled.revision_id, actor="tester")
                active = managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                with self.assertRaises(ConfigurationVersionConflict):
                    objects.edit_automation_task_definition(
                        active.revision_id,
                        "task",
                        {
                            "id": "task",
                            "name": "must not mutate",
                            "resourceLibraryId": "source",
                            "mode": "scan-only",
                            "intervalSeconds": 60,
                        },
                        expected_version=active.version,
                        actor="tester",
                    )
                with self.assertRaises(ConfigurationVersionConflict):
                    objects.disable_automation_task_definition(
                        active.revision_id,
                        "task",
                        expected_version=active.version,
                        actor="tester",
                    )

                # A Draft edit made after activation must leave the prior Active
                # revision id, version, digest and document byte-identical.
                next_draft = managed.import_draft(
                    managed.current_document(document),
                    actor="tester",
                )
                before = managed.active()
                next_draft = objects.edit_automation_task_definition(
                    next_draft.revision_id,
                    "task",
                    {
                        "id": "task",
                        "name": "Next draft edit",
                        "resourceLibraryId": "source",
                        "mode": "automatic-organization",
                        "sourceScope": "incoming",
                        "intervalSeconds": 180,
                        "itemLimit": 9,
                    },
                    expected_version=next_draft.version,
                    actor="tester",
                )
                after = managed.active()
                self.assertEqual(after, before)
                self.assertEqual(after.revision_id, before.revision_id)
                self.assertEqual(after.version, before.version)
                self.assertEqual(after.digest, before.digest)
                self.assertEqual(after.document, before.document)
                self.assertEqual(
                    next_draft.document["automationTaskDefinitions"][0]["name"],
                    "Next draft edit",
                )

                # A superseded revision is equally immutable.
                next_validated = managed.validate(next_draft.revision_id, actor="tester")
                managed.activate(
                    next_validated.revision_id,
                    expected_version=next_validated.version,
                    actor="tester",
                )
                with self.assertRaises(ConfigurationVersionConflict):
                    objects.edit_automation_task_definition(
                        active.revision_id,
                        "task",
                        {
                            "id": "task",
                            "name": "must not mutate",
                            "resourceLibraryId": "source",
                            "mode": "scan-only",
                            "intervalSeconds": 60,
                        },
                        expected_version=active.version,
                        actor="tester",
                    )

    def test_service_layer_stale_version_rejects_without_overwriting_concurrent_draft(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = _document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(document, actor="tester")
                created = objects.create_automation_task_definition(
                    draft.revision_id,
                    {
                        "id": "first",
                        "name": "First",
                        "resourceLibraryId": "source",
                        "mode": "scan-only",
                        "intervalSeconds": 60,
                    },
                    expected_version=draft.version,
                    actor="tester",
                )
                concurrent = objects.edit_automation_task_definition(
                    created.revision_id,
                    "first",
                    {
                        "id": "first",
                        "name": "Concurrent edit",
                        "resourceLibraryId": "source",
                        "mode": "scan-and-plan",
                        "intervalSeconds": 90,
                    },
                    expected_version=created.version,
                    actor="tester",
                )
                with self.assertRaises(ConfigurationVersionConflict) as caught:
                    objects.create_automation_task_definition(
                        concurrent.revision_id,
                        {
                            "id": "second",
                            "name": "Second",
                            "resourceLibraryId": "source",
                            "mode": "scan-only",
                            "intervalSeconds": 30,
                        },
                        expected_version=created.version,
                        actor="tester",
                    )
                self.assertEqual(caught.exception.current_version, concurrent.version)
                self.assertEqual(caught.exception.current_digest, concurrent.digest)
                stored = managed.require(concurrent.revision_id)
                self.assertEqual(stored.version, concurrent.version)
                self.assertEqual(stored.digest, concurrent.digest)
                self.assertEqual(stored.document, concurrent.document)
                self.assertEqual(
                    [item["id"] for item in stored.document["automationTaskDefinitions"]],
                    ["first"],
                )

    def test_pre_change_configuration_database_loads_and_accepts_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            pre_change = _document(root)
            self.assertNotIn("automationTaskDefinitions", pre_change)
            with SQLiteConfigurationRepository(database) as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                draft = managed.import_draft(pre_change, actor="tester")
                self.assertNotIn("automationTaskDefinitions", draft.document)
            with SQLiteConfigurationRepository(database) as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                objects = ConfigurationObjectService(managed)
                reloaded = managed.require(draft.revision_id)
                self.assertEqual(reloaded.digest, draft.digest)
                self.assertEqual(
                    objects.inspect_automation_task_definitions(reloaded.revision_id),
                    [],
                )
                created = objects.create_automation_task_definition(
                    reloaded.revision_id,
                    {
                        "id": "task",
                        "name": "Task",
                        "resourceLibraryId": "source",
                        "mode": "scan-only",
                        "intervalSeconds": 60,
                    },
                    expected_version=reloaded.version,
                    actor="tester",
                )
                validated = managed.validate(created.revision_id, actor="tester")
                active = managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                self.assertEqual(
                    load_runtime_configuration(active.document)
                    .automation_task_definitions[-1]
                    .definition_id,
                    "task",
                )
            with SQLiteConfigurationRepository(database) as reopened:
                managed = ManagedConfigurationService(
                    reopened,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                objects = ConfigurationObjectService(managed)
                active = managed.active()
                self.assertIsNotNone(active)
                self.assertEqual(active.document["automationTaskDefinitions"][0]["id"], "task")
                self.assertEqual(
                    objects.inspect_automation_task_definitions(active.revision_id)[0]["id"],
                    "task",
                )
                self.assertEqual(
                    load_runtime_configuration(active.document)
                    .automation_task_definitions[-1]
                    .definition_id,
                    "task",
                )

    def test_api_alias_and_rbac_are_version_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = _document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as configuration,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
            ):
                managed = ManagedConfigurationService(configuration)
                api = MediaFlowApi(
                    runtime,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                    configuration_service=managed,
                    bootstrap_document=document,
                )
                draft = managed.import_draft(document, actor="tester")
                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions",
                    method="POST",
                    body={
                        "revisionId": draft.revision_id,
                        "expectedVersion": draft.version,
                        "definition": {
                            "id": "api-task",
                            "name": "API Task",
                            "resourceLibraryId": "source",
                            "mode": "scan-only",
                            "intervalSeconds": 30,
                        },
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["automationTaskDefinition"]["id"], "api-task")
                stale, _ = _request(
                    api,
                    "/api/v1/automation/task-definitions/api-task/enable",
                    method="POST",
                    body={"revisionId": draft.revision_id, "expectedVersion": draft.version},
                )
                self.assertEqual(stale, 409)
                viewer_status, _ = _request(
                    api,
                    "/api/v1/automation/task-definitions",
                    method="POST",
                    body={"revisionId": draft.revision_id, "expectedVersion": 2, "definition": {}},
                    token="viewer-token",
                )
                self.assertEqual(viewer_status, 403)

    def test_api_definition_actions_and_configuration_object_routes_share_contract(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = _document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as configuration,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
            ):
                managed = ManagedConfigurationService(
                    configuration,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                api = _api(runtime, managed, document)
                draft = managed.import_draft(document, actor="tester")
                revision_id = draft.revision_id

                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions",
                    method="POST",
                    body={
                        "revisionId": revision_id,
                        "expectedVersion": draft.version,
                        "definition": {
                            "id": "api-task",
                            "name": "API Task",
                            "resourceLibraryId": "source",
                            "mode": "scan-only",
                            "intervalSeconds": 30,
                        },
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["configurationRevisionId"], revision_id)
                self.assertEqual(body["automationTaskDefinition"]["id"], "api-task")
                self.assertFalse(body["automationTaskDefinition"]["enabled"])

                draft = managed.require(revision_id)
                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions/api-task",
                    method="PUT",
                    body={
                        "revisionId": revision_id,
                        "expectedVersion": draft.version,
                        "definition": {
                            "id": "api-task",
                            "name": "API Task edited",
                            "resourceLibraryId": "source",
                            "mode": "scan-and-plan",
                            "sourceScope": "incoming",
                            "intervalSeconds": 60,
                            "itemLimit": 5,
                        },
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["automationTaskDefinition"]["name"], "API Task edited")
                self.assertEqual(body["version"], draft.version + 1)

                draft = managed.require(revision_id)
                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions/api-task/copy",
                    method="POST",
                    body={"revisionId": revision_id, "expectedVersion": draft.version},
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["automationTaskDefinition"]["id"], "api-task-copy")
                self.assertFalse(body["automationTaskDefinition"]["enabled"])

                draft = managed.require(revision_id)
                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions/api-task/enable",
                    method="POST",
                    body={"revisionId": revision_id, "expectedVersion": draft.version},
                )
                self.assertEqual(status, 200)
                self.assertTrue(body["automationTaskDefinition"]["enabled"])

                draft = managed.require(revision_id)
                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions/api-task/disable",
                    method="POST",
                    body={"revisionId": revision_id, "expectedVersion": draft.version},
                )
                self.assertEqual(status, 200)
                self.assertFalse(body["automationTaskDefinition"]["enabled"])

                # Operator Web uses the versioned configuration-object routes for
                # create/copy/enable/disable; they must share the same contract.
                draft = managed.require(revision_id)
                status, body = _request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}"
                    "/objects/automationTaskDefinitions",
                    method="POST",
                    body={
                        "object": {
                            "id": "cfg-task",
                            "name": "Config Task",
                            "resourceLibraryId": "source",
                            "mode": "scan-only",
                            "intervalSeconds": 45,
                        },
                        "expectedVersion": draft.version,
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["automationTaskDefinition"]["id"], "cfg-task")

                draft = managed.require(revision_id)
                status, body = _request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}"
                    "/objects/automationTaskDefinitions/cfg-task",
                    method="PUT",
                    body={
                        "object": {
                            "id": "cfg-task",
                            "name": "Config Task edited",
                            "resourceLibraryId": "source",
                            "mode": "scan-and-plan",
                            "intervalSeconds": 90,
                        },
                        "expectedVersion": draft.version,
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["automationTaskDefinition"]["name"], "Config Task edited")

                draft = managed.require(revision_id)
                status, body = _request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}"
                    "/objects/automationTaskDefinitions/cfg-task/copy",
                    method="POST",
                    body={"expectedVersion": draft.version},
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["automationTaskDefinition"]["id"], "cfg-task-copy")
                self.assertFalse(body["automationTaskDefinition"]["enabled"])

                draft = managed.require(revision_id)
                status, body = _request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}"
                    "/objects/automationTaskDefinitions/cfg-task/enable",
                    method="POST",
                    body={"expectedVersion": draft.version},
                )
                self.assertEqual(status, 200)
                self.assertTrue(body["automationTaskDefinition"]["enabled"])

                draft = managed.require(revision_id)
                status, body = _request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}"
                    "/objects/automationTaskDefinitions/cfg-task/disable",
                    method="POST",
                    body={"expectedVersion": draft.version},
                )
                self.assertEqual(status, 200)
                self.assertFalse(body["automationTaskDefinition"]["enabled"])

                # List and detail projections are bounded and truthful for the Draft.
                draft = managed.require(revision_id)
                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions",
                    query=f"revisionId={revision_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["configuration"]["revisionId"], revision_id)
                self.assertEqual(body["configuration"]["digest"], draft.digest)
                self.assertEqual(body["total"], 4)
                self.assertEqual(
                    {item["id"] for item in body["items"]},
                    {"api-task", "api-task-copy", "cfg-task", "cfg-task-copy"},
                )
                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions/api-task",
                    query=f"revisionId={revision_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["definition"]["name"], "API Task edited")
                self.assertEqual(body["configuration"]["revisionId"], revision_id)
                self.assertEqual(body["configuration"]["digest"], draft.digest)

                # Viewer may read but not mutate through either route family.
                status, _ = _request(
                    api,
                    "/api/v1/automation/task-definitions",
                    query=f"revisionId={revision_id}",
                    token="viewer-token",
                )
                self.assertEqual(status, 200)
                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions/api-task/disable",
                    method="POST",
                    body={"revisionId": revision_id, "expectedVersion": draft.version},
                    token="viewer-token",
                )
                self.assertEqual(status, 403)
                self.assertEqual(body["error"]["code"], "forbidden")
                status, body = _request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}"
                    "/objects/automationTaskDefinitions/cfg-task/enable",
                    method="POST",
                    body={"expectedVersion": draft.version},
                    token="viewer-token",
                )
                self.assertEqual(status, 403)
                self.assertEqual(body["error"]["code"], "forbidden")

    def test_api_rejects_malformed_references_and_stale_versions_with_bounded_errors(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = _document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as configuration,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
            ):
                managed = ManagedConfigurationService(
                    configuration,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                api = _api(runtime, managed, document)
                draft = managed.import_draft(document, actor="tester")
                revision_id = draft.revision_id
                valid = {
                    "id": "api-task",
                    "name": "API Task",
                    "resourceLibraryId": "source",
                    "mode": "scan-only",
                    "intervalSeconds": 30,
                }

                def create(value, expected_version):
                    return _request(
                        api,
                        "/api/v1/automation/task-definitions",
                        method="POST",
                        body={
                            "revisionId": revision_id,
                            "expectedVersion": expected_version,
                            "definition": value,
                        },
                    )

                for malformed, message_part in (
                    ({key: value for key, value in valid.items() if key != "mode"}, "mode"),
                    (
                        {**valid, "id": "traversal", "sourceScope": "../escape"},
                        "Storage-relative",
                    ),
                    (
                        {**valid, "id": "absolute", "sourceScope": "/absolute"},
                        "Storage-relative",
                    ),
                    (
                        {**valid, "id": "unknown", "resourceLibraryId": "missing"},
                        "unknown ResourceLibrary",
                    ),
                ):
                    with self.subTest(id=malformed.get("id", "missing-mode")):
                        status, body = create(malformed, draft.version)
                        self.assertEqual(status, 400)
                        self.assertEqual(body["error"]["code"], "invalid_request")
                        self.assertIn(message_part, body["error"]["message"])

                disabled_document = copy.deepcopy(document)
                disabled_document["resourceLibraries"][0]["enabled"] = False
                disabled_draft = managed.import_draft(disabled_document, actor="tester")
                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions",
                    method="POST",
                    body={
                        "revisionId": disabled_draft.revision_id,
                        "expectedVersion": disabled_draft.version,
                        "definition": {
                            **valid,
                            "id": "disabled-ref",
                        },
                    },
                )
                self.assertEqual(status, 400)
                self.assertEqual(body["error"]["code"], "invalid_request")
                self.assertIn("must be enabled", body["error"]["message"])

                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions/not-a-definition",
                    query=f"revisionId={revision_id}",
                )
                self.assertEqual(status, 404)
                self.assertEqual(body["error"]["code"], "not_found")
                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions/not-a-definition/copy",
                    method="POST",
                    body={"revisionId": revision_id, "expectedVersion": draft.version},
                )
                self.assertEqual(status, 404)
                self.assertEqual(body["error"]["code"], "not_found")

                current = managed.require(revision_id)
                status, body = create({**valid, "id": "stale"}, current.version - 1)
                self.assertEqual(status, 409)
                self.assertEqual(body["error"]["code"], "configuration_version_conflict")
                self.assertEqual(body["error"]["details"]["durableState"], "draft_preserved")
                self.assertEqual(body["error"]["details"]["currentVersion"], current.version)
                self.assertEqual(body["error"]["details"]["currentDigest"], current.digest)
                self.assertEqual(body["error"]["details"]["sideEffects"], "none")
                self.assertTrue(body["error"]["details"]["retrySafe"])
                self.assertNotIn(
                    "stale",
                    {
                        item["id"]
                        for item in managed.require(revision_id).document.get(
                            "automationTaskDefinitions", []
                        )
                    },
                )

                # An Active revision is immutable through the API: the bounded
                # error must not hide a durable Draft/Active unchanged state.
                validated = managed.validate(revision_id, actor="tester")
                active = managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions/api-task",
                    method="PUT",
                    body={
                        "revisionId": active.revision_id,
                        "expectedVersion": active.version,
                        "definition": valid,
                    },
                )
                self.assertEqual(status, 409)
                self.assertEqual(body["error"]["code"], "configuration_version_conflict")
                self.assertEqual(body["error"]["details"]["durableState"], "draft_preserved")
                self.assertEqual(body["error"]["details"]["sideEffects"], "none")

    def test_api_list_and_detail_are_read_only_and_truthful_after_reload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = _document(root)
            database = root / "configuration.sqlite3"
            with (
                SQLiteConfigurationRepository(database) as configuration,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
            ):
                managed = ManagedConfigurationService(
                    configuration,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                api = _api(runtime, managed, document)
                draft = managed.import_draft(document, actor="tester")
                status, body = _request(
                    api,
                    "/api/v1/automation/task-definitions",
                    method="POST",
                    body={
                        "revisionId": draft.revision_id,
                        "expectedVersion": draft.version,
                        "definition": {
                            "id": "task",
                            "name": "Task",
                            "resourceLibraryId": "source",
                            "mode": "scan-only",
                            "intervalSeconds": 60,
                        },
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["automationTaskDefinition"]["id"], "task")
                draft = managed.require(draft.revision_id)
                validated = managed.validate(draft.revision_id, actor="tester")
                active = managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                revisions_before = len(configuration.list_revisions())
                expected = {
                    "revisionId": active.revision_id,
                    "version": active.version,
                    "digest": active.digest,
                }
                for _ in range(2):
                    status, listing = _request(api, "/api/v1/automation/task-definitions")
                    self.assertEqual(status, 200)
                    self.assertEqual(
                        {key: listing["configuration"][key] for key in expected},
                        expected,
                    )
                    self.assertEqual(listing["total"], 1)
                    self.assertEqual(listing["items"][0]["id"], "task")
                    status, detail = _request(
                        api,
                        "/api/v1/automation/task-definitions/task",
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(detail["definition"]["id"], "task")
                    self.assertEqual(detail["configuration"]["digest"], active.digest)
                self.assertEqual(len(configuration.list_revisions()), revisions_before)
                unchanged = managed.active()
                self.assertEqual(unchanged.version, active.version)
                self.assertEqual(unchanged.digest, active.digest)

            with (
                SQLiteConfigurationRepository(database) as reopened,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
            ):
                managed = ManagedConfigurationService(
                    reopened,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                api = _api(runtime, managed, document)
                status, listing = _request(api, "/api/v1/automation/task-definitions")
                self.assertEqual(status, 200)
                self.assertEqual(
                    {key: listing["configuration"][key] for key in expected},
                    expected,
                )
                self.assertEqual(listing["items"][0]["id"], "task")
                status, detail = _request(api, "/api/v1/automation/task-definitions/task")
                self.assertEqual(status, 200)
                self.assertEqual(detail["definition"]["id"], "task")
                self.assertEqual(detail["configuration"]["digest"], active.digest)


class AutomationTaskDefinitionWebTests(unittest.TestCase):
    def test_automation_surface_and_guided_actions_are_reachable(self) -> None:
        html = ASSETS["/ui"][1].decode("utf-8")
        script = ASSETS["/ui/app.js"][1].decode("utf-8")
        self.assertIn('data-view="automation"', html)
        self.assertIn("renderAutomation", script)
        self.assertIn("showAutomationDetail", script)

        automation = _js_function_body(script, "renderAutomation")
        self.assertIn("await api('/api/v1/automation/task-definitions');", automation)
        self.assertIn("'Automation Task Definitions'", automation)
        self.assertIn("'Active configuration'", automation)
        self.assertIn("'Configuration version'", automation)
        self.assertIn("'Configuration digest'", automation)
        self.assertIn("'Definitions'", automation)
        self.assertIn("'Open managed Configuration'", automation)
        for field in (
            "item.resourceLibraryId",
            "item.sourceScope",
            "item.mode || item.runMode",
            "item.intervalSeconds",
            "item.cron",
            "item.timezone",
            "item.itemLimit",
        ):
            self.assertIn(field, automation)
        for forbidden in (
            "method: 'POST'",
            "method: 'PUT'",
            "method: 'DELETE'",
            "/copy",
            "/enable",
            "/disable",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, automation)

        detail = _js_function_body(script, "showAutomationDetail")
        self.assertIn("'Automation Task Definition detail'", detail)
        self.assertIn("'Source scope'", detail)
        self.assertIn("'Run mode'", detail)
        self.assertIn("'Active configuration'", detail)
        self.assertIn("'Active configuration digest'", detail)
        self.assertIn("'Run Preview / DryRun'", detail)
        self.assertIn("confirmAutomationPreview(item)", detail)
        self.assertIn("previews?limit=10`", detail)
        self.assertIn("'No Preview has been run for this definition yet.'", detail)
        self.assertIn(
            "'Opening or refreshing this view is read-only. Preview runs only when "
            "you explicitly confirm it.'",
            detail,
        )
        self.assertNotIn("method: 'POST'", detail)
        for forbidden in ("method: 'PUT'", "method: 'DELETE'"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, detail)

        confirm = _js_function_body(script, "confirmAutomationPreview")
        self.assertIn("'Confirm Preview'", confirm)
        self.assertIn("It creates no Job, Task, grant, or configuration revision.", confirm)
        self.assertIn(
            "`/api/v1/automation/task-definitions/${encodeURIComponent(item.id)}/preview`",
            confirm,
        )
        self.assertIn("method: 'POST'", confirm)

        preview_view = _js_function_body(script, "showAutomationPreview")
        self.assertIn("'Automation Preview'", preview_view)
        self.assertIn("Stale evidence:", preview_view)
        self.assertIn("This is not execution authority.", preview_view)
        self.assertIn("'Definition fingerprint'", preview_view)
        self.assertIn("'Truncated by limit'", preview_view)
        self.assertIn("'Per-item evidence'", preview_view)
        self.assertIn("'Run a fresh Preview'", preview_view)
        self.assertIn("/previews/${encodeURIComponent(previewId)}", preview_view)
        self.assertNotIn("method: 'POST'", preview_view)

        show_revision = _js_function_body(script, "showConfigurationRevision")
        self.assertIn(
            "renderGuidedObjectList(data, guided, 'automationTaskDefinitions', "
            "'Automation Task Definitions');",
            show_revision,
        )

        object_list = _js_function_body(script, "renderGuidedObjectList")
        automation_branch_start = object_list.index("if (kind === 'automationTaskDefinitions') {")
        delete_guard = object_list.index(
            "if (kind !== 'automationTaskDefinitions') row.append(actionButton('Delete'",
            automation_branch_start,
        )
        automation_branch = object_list[automation_branch_start:delete_guard]
        self.assertIn(
            "Copy Automation Task Definition ${item.id}? The copy starts disabled.",
            automation_branch,
        )
        self.assertIn("'Confirm copy'", automation_branch)
        self.assertIn(
            "${action === 'enable' ? 'Enable' : 'Disable'} ${item.id}? "
            "This changes only the Draft.",
            automation_branch,
        )
        self.assertIn("`Confirm ${action}`", automation_branch)
        self.assertNotIn("'Delete'", automation_branch)
        self.assertIn("automationTaskDefinitions: 'AutomationTaskDefinition'", object_list)
        self.assertIn("guidedJson ? 'Add' : 'Add Local'", object_list)

        object_form = _js_function_body(script, "renderGuidedObjectForm")
        self.assertIn("automationTaskDefinition ? 'Automation Task Definition'", object_form)
        self.assertIn("'Save Automation Task Definition'", object_form)
        self.assertIn("Edit one bounded Automation Task Definition.", object_form)
        self.assertIn("policy and destination choices stay in configuration.", object_form)


if __name__ == "__main__":
    unittest.main()
