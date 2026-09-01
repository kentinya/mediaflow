from __future__ import annotations

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


class AutomationTaskDefinitionWebTests(unittest.TestCase):
    def test_automation_surface_and_guided_actions_are_reachable(self) -> None:
        html = ASSETS["/ui"][1].decode("utf-8")
        script = ASSETS["/ui/app.js"][1].decode("utf-8")
        self.assertIn('data-view="automation"', html)
        self.assertIn("renderAutomation", script)
        for action in ("Copy", "Enable", "Disable", "Confirm copy"):
            self.assertIn(action, script)
        self.assertIn("/api/v1/automation/task-definitions", script)


if __name__ == "__main__":
    unittest.main()
