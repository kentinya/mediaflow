from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_snapshot import (
    ManagedConfigurationService,
)
from mediaflow.domain.configuration_management import ConfigurationObjectKind
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import (
    is_minimal_management_bootstrap,
    load_minimal_management_bootstrap,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS, INDEX_HTML
from mediaflow.interfaces.service_api import MediaFlowApi


def request(api, path, *, method="GET", token="admin-token", body=None):
    raw = b"" if body is None else json.dumps(body).encode("utf-8")
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(raw)),
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(raw),
    }
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    value = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(value)


class ManagementSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = str(Path(self.directory.name, "runtime.sqlite3"))
        self.bootstrap = {
            "version": 1,
            "persistence": {"databasePath": self.database},
            "api": {
                "principals": [
                    {"id": "admin", "tokenEnv": "MF_ADMIN_TOKEN", "roles": ["admin"]},
                    {"id": "viewer", "tokenEnv": "MF_VIEWER_TOKEN", "roles": ["viewer"]},
                ]
            },
        }
        self.configuration_repository = SQLiteConfigurationRepository(self.database)
        self.task_repository = SQLiteTaskRepository(self.database)
        self.service = ManagedConfigurationService(
            self.configuration_repository,
            bootstrap_database_path=self.database,
            bootstrap_document=self.bootstrap,
            management_only=True,
        )
        self.admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
        self.viewer = ResolvedApiPrincipal(
            "viewer", "viewer-token", frozenset({ApiPermission.READ})
        )
        self.api = MediaFlowApi(
            self.task_repository,
            None,
            principals=(self.admin, self.viewer),
            configuration_service=self.service,
            bootstrap_document=self.bootstrap,
            management_only=True,
        )

    def tearDown(self) -> None:
        self.task_repository.close()
        self.configuration_repository.close()
        self.directory.cleanup()

    def test_strict_minimal_bootstrap_rejects_workflow_and_literal_secret_content(self) -> None:
        self.assertTrue(is_minimal_management_bootstrap(self.bootstrap))
        loaded = load_minimal_management_bootstrap(self.bootstrap)
        self.assertEqual(loaded.database_path, self.database)
        self.assertEqual(loaded.api_principals[0].token_env, "MF_ADMIN_TOKEN")

        workflow = json.loads(json.dumps(self.bootstrap))
        workflow["storages"] = []
        self.assertFalse(is_minimal_management_bootstrap(workflow))
        with self.assertRaisesRegex(ValueError, "minimal management bootstrap"):
            load_minimal_management_bootstrap(workflow)

        literal_secret = json.loads(json.dumps(self.bootstrap))
        literal_secret["api"]["principals"][0]["token"] = "must-not-persist"
        with self.assertRaises(ValueError):
            load_minimal_management_bootstrap(literal_secret)

    def test_fresh_readiness_and_system_projection_are_bounded(self) -> None:
        status, health = request(self.api, "/health", token=None)
        self.assertEqual(status, 200)
        self.assertEqual(health, {"processAlive": True, "status": "ok"})

        status, readiness = request(self.api, "/api/v1/management/readiness")
        self.assertEqual(status, 200)
        self.assertTrue(readiness["managementReady"])
        self.assertTrue(readiness["setupRequired"])
        self.assertFalse(readiness["runtimeConfigured"])
        self.assertFalse(readiness["workflowAvailable"])
        self.assertIsNone(readiness["active"])

        status, configuration = request(self.api, "/api/v1/configuration")
        self.assertEqual(status, 200)
        self.assertEqual(configuration["authority"], "MANAGEMENT_BOOTSTRAP")
        self.assertEqual(configuration["health"], "SETUP_REQUIRED")
        self.assertIsNone(configuration["active"])
        self.assertIsNone(configuration["setupDraft"])
        self.assertGreaterEqual(len(configuration["setupBlockers"]), 5)
        self.assertNotIn("MF_ADMIN_TOKEN", json.dumps(configuration))

        status, system = request(self.api, "/api/v1/system/status")
        self.assertEqual(status, 200)
        self.assertEqual(system["system"]["configuration_state"], "SETUP_REQUIRED")
        self.assertIsNone(system["system"]["configuration_snapshot_id"])
        self.assertEqual(system["management"]["workflowAvailable"], False)

    def test_api_serve_starts_from_minimal_bootstrap_without_runtime_objects(self) -> None:
        class Server:
            app = None
            health = None
            readiness = None
            configuration = None

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def serve_forever(self):
                self.health = request(self.app, "/health", token=None)
                self.readiness = request(self.app, "/api/v1/management/readiness")
                self.configuration = request(self.app, "/api/v1/configuration")

        with tempfile.TemporaryDirectory() as directory:
            bootstrap = json.loads(json.dumps(self.bootstrap))
            bootstrap["persistence"]["databasePath"] = str(Path(directory, "api.sqlite3"))
            config = Path(directory, "bootstrap.json")
            config.write_text(json.dumps(bootstrap), encoding="utf-8")
            server = Server()

            def make_server(_host, _port, app):
                server.app = app
                return server

            with (
                patch.dict(
                    os.environ,
                    {"MF_ADMIN_TOKEN": "admin-token", "MF_VIEWER_TOKEN": "viewer-token"},
                    clear=True,
                ),
                patch("wsgiref.simple_server.make_server", side_effect=make_server),
                patch(
                    "mediaflow.infrastructure.runtime_configuration.RuntimeConfiguration.create_storages",
                    side_effect=AssertionError("fresh API must not construct Storage"),
                ),
                patch(
                    "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBProvider",
                    side_effect=AssertionError("fresh API must not construct Provider"),
                ),
            ):
                status = final_main(
                    ["--config", str(config), "api", "serve"],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )

        self.assertEqual(status, 0)
        self.assertIsNotNone(server.app)
        self.assertEqual(server.health, (200, {"processAlive": True, "status": "ok"}))
        self.assertEqual(server.readiness[0], 200)
        self.assertTrue(server.readiness[1]["managementReady"])
        self.assertTrue(server.readiness[1]["setupRequired"])
        self.assertIsNone(server.configuration[1]["active"])

    def test_operator_web_exposes_create_resume_setup_entry(self) -> None:
        html = INDEX_HTML.decode("utf-8")
        script = APP_JS.decode("utf-8")
        self.assertIn('data-view="configuration"', html)
        self.assertIn("Create first Draft", script)
        self.assertIn("Resume setup Draft", script)
        self.assertIn("/api/v1/configuration/drafts/first", script)
        self.assertIn("/api/v1/management/readiness", script)
        self.assertIn("readiness.setupRequired || readiness.recoveryRequired", script)
        self.assertIn("setupRequired", script)

    def test_first_draft_preserves_only_bootstrap_refs_and_is_resumable(self) -> None:
        status, created = request(
            self.api,
            "/api/v1/configuration/drafts/first",
            method="POST",
            body=None,
        )
        self.assertEqual(status, 201)
        self.assertEqual(created["status"], "draft")
        self.assertEqual(created["version"], 1)
        self.assertEqual(created["schemaVersion"], 1)
        revision = self.service.require(created["revisionId"])
        document = revision.document
        self.assertEqual(document["persistence"], self.bootstrap["persistence"])
        self.assertEqual(document["api"]["principals"][0]["tokenEnv"], "MF_ADMIN_TOKEN")
        self.assertEqual(document["api"]["principals"][1]["tokenEnv"], "MF_VIEWER_TOKEN")
        self.assertEqual(document["setup"]["kind"], "first_runtime_setup")
        self.assertFalse(document["setup"]["runtimeReady"])
        self.assertEqual(document["storages"], [])
        self.assertEqual(document["resourceLibraries"], [])
        self.assertEqual(document["mediaLibraries"], [])
        self.assertEqual(document["automation"]["schedules"], [])
        self.assertEqual(document["notifications"]["webhooks"], [])
        self.assertFalse(document["api"]["remoteExecution"]["enabled"])
        self.assertNotIn("rootPath", json.dumps(document))
        self.assertNotIn("historyPath", json.dumps(document))
        self.assertNotIn("https://", json.dumps(document))
        self.assertNotIn("must-not-persist", json.dumps(document))
        audits = self.configuration_repository.list_revision_audits(revision.revision_id)
        self.assertEqual([item.action for item in audits], ["first_draft_create"])

        status, configuration = request(self.api, "/api/v1/configuration/status")
        self.assertEqual(status, 200)
        self.assertEqual(configuration["setupDraft"]["revisionId"], revision.revision_id)
        self.assertTrue(configuration["setupRequired"])

        status, conflict = request(
            self.api,
            "/api/v1/configuration/drafts/first",
            method="POST",
            body={},
        )
        self.assertEqual(status, 409)
        self.assertEqual(conflict["error"]["details"]["revisionId"], revision.revision_id)
        self.assertEqual(conflict["error"]["details"]["durableState"], "setup_draft_preserved")
        self.assertEqual(conflict["error"]["details"]["resumeAction"]["method"], "GET")
        self.assertEqual(len(self.configuration_repository.list_revisions()), 1)

    def test_read_only_and_workflow_admission_are_safe(self) -> None:
        status, denied = request(
            self.api,
            "/api/v1/configuration/drafts/first",
            method="POST",
            token="viewer-token",
            body={},
        )
        self.assertEqual(status, 403)
        status, visible = request(self.api, "/api/v1/configuration", token="viewer-token")
        self.assertEqual(status, 200)
        self.assertFalse(visible["canManageConfiguration"])

        with (
            patch(
                "mediaflow.infrastructure.runtime_configuration.RuntimeConfiguration.create_storages",
                side_effect=AssertionError("Storage must not be constructed"),
            ),
            patch(
                "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBProvider",
                side_effect=AssertionError("Provider must not be constructed"),
            ),
        ):
            for path, body in (
                ("/api/v1/jobs", {"command": "preview"}),
                ("/api/v1/manual-intents", {"source": "x"}),
                ("/api/v1/automation/task-definitions", {"definition": {}}),
                ("/api/v1/manual-executions", {"taskId": "x"}),
            ):
                with self.subTest(path=path):
                    status, response = request(self.api, path, method="POST", body=body)
                    self.assertEqual(status, 503)
                    self.assertEqual(response["error"]["code"], "runtime_not_configured")
                    self.assertEqual(response["error"]["details"]["sideEffects"], "none")
                    self.assertEqual(
                        response["error"]["details"]["durableState"],
                        "no_workflow_work_created",
                    )
        self.assertEqual(self.task_repository.list_jobs(), ())
        self.assertEqual(self.task_repository.list_tasks(), ())

    def test_concurrent_first_draft_creation_has_one_winner(self) -> None:
        repositories = [SQLiteConfigurationRepository(self.database) for _ in range(6)]
        services = [
            ManagedConfigurationService(
                repository,
                bootstrap_database_path=self.database,
                bootstrap_document=self.bootstrap,
                management_only=True,
            )
            for repository in repositories
        ]
        try:

            def create(index):
                try:
                    return ("created", services[index].create_first_draft(actor=f"worker-{index}"))
                except Exception as error:
                    return (type(error).__name__, getattr(error, "revision_id", None))

            with ThreadPoolExecutor(max_workers=len(services)) as executor:
                results = list(executor.map(create, range(len(services))))
            winners = [value for kind, value in results if kind == "created"]
            conflicts = [
                value for kind, value in results if kind == "ConfigurationFirstDraftConflict"
            ]
            self.assertEqual(len(winners), 1)
            self.assertEqual(len(conflicts), len(services) - 1)
            self.assertTrue(all(value == winners[0].revision_id for value in conflicts))
            self.assertEqual(len(self.configuration_repository.list_revisions()), 1)
        finally:
            for repository in repositories:
                repository.close()

    def test_first_draft_transaction_rolls_back_revision_and_audit(self) -> None:
        with patch.object(
            self.configuration_repository,
            "_insert_audit",
            side_effect=RuntimeError("audit persistence failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit persistence failed"):
                self.service.create_first_draft(actor="tester")
        self.assertEqual(self.configuration_repository.list_revisions(), ())
        self.assertEqual(
            self.configuration_repository.list_audits(
                ConfigurationObjectKind.SYSTEM_SETTINGS, "missing"
            ),
            (),
        )
        created = self.service.create_first_draft(actor="tester")
        self.assertEqual(created.version, 1)

    def test_restart_preserves_setup_draft_and_does_not_fall_back_to_setup_again(self) -> None:
        created = self.service.create_first_draft(actor="tester")
        self.task_repository.close()
        self.configuration_repository.close()
        self.task_repository = SQLiteTaskRepository(self.database)
        self.configuration_repository = SQLiteConfigurationRepository(self.database)
        self.service = ManagedConfigurationService(
            self.configuration_repository,
            bootstrap_database_path=self.database,
            bootstrap_document=self.bootstrap,
            management_only=True,
        )
        status = self.service.status_document()
        self.assertEqual(status["setupDraft"]["revisionId"], created.revision_id)
        with self.assertRaisesRegex(Exception, "first setup Draft already exists"):
            self.service.create_first_draft(actor="tester")


if __name__ == "__main__":
    unittest.main()
