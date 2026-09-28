from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
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
    query = ""
    if "?" in path:
        path, query = path.split("?", 1)
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
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
        self.assertEqual(
            readiness["commandReadiness"]["scan"]["condition"],
            "no_active_configuration",
        )
        self.assertEqual(
            readiness["commandReadiness"]["directTransfer"]["recoveryDestination"],
            "/ui-v2/configuration",
        )

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

    def test_command_readiness_respects_scope_permissions_after_configuration(self) -> None:
        document = {
            "storages": [{"id": "local", "enabled": True}],
            "resourceLibraries": [{"id": "incoming", "storageId": "local", "enabled": True}],
            "mediaLibraries": [],
            "recognitionTypes": [],
            "recognitionRules": [],
            "recognitionTypePolicies": [],
            "metadataPolicies": [],
            "namingPolicies": [],
            "classificationPolicies": [],
            "organizePolicies": [],
            "automation": {"schedules": [{"id": "daily", "enabled": True}]},
            "notifications": {
                "webhooks": [{"id": "ops", "enabled": True}],
            },
        }
        active = SimpleNamespace(document=document)
        status = {
            "active": {"revisionId": "active-1"},
            "setupRequired": False,
        }
        with patch.object(self.service, "active", return_value=active):
            viewer = self.api._command_readiness_document(self.viewer, status)
            admin = self.api._command_readiness_document(self.admin, status)
        self.assertTrue(viewer["libraryBrowse"]["ready"])
        self.assertTrue(viewer["libraryBrowse"]["authorized"])
        for key in ("directTransfer", "scheduling", "notification"):
            self.assertFalse(viewer[key]["ready"])
            self.assertEqual(viewer[key]["condition"], "unauthorized")
            self.assertFalse(viewer[key]["authorized"])
            self.assertIn("permission denied", viewer[key]["durableState"])
            self.assertEqual(
                viewer[key]["nextAction"],
                "contact an administrator for the required permission",
            )
        for key in ("directTransfer", "scheduling", "notification"):
            self.assertTrue(admin[key]["ready"])
            self.assertTrue(admin[key]["authorized"])

    def test_api_serve_starts_from_minimal_bootstrap_without_runtime_objects(self) -> None:
        class Server:
            app = None
            health = None
            readiness = None
            configuration = None
            activated = None
            scan_service_ready = False

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def serve_forever(self):
                self.health = request(self.app, "/health", token=None)
                self.readiness = request(self.app, "/api/v1/management/readiness")
                self.configuration = request(self.app, "/api/v1/configuration")
                _, created = request(
                    self.app,
                    "/api/v1/configuration/drafts/first",
                    method="POST",
                    body={},
                )
                revision_id = created["revisionId"]
                _, validated = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{revision_id}/validate",
                    method="POST",
                    body={},
                )
                self.activated = request(
                    self.app,
                    f"/api/v1/configuration/revisions/{revision_id}/activate",
                    method="POST",
                    body={"expectedVersion": validated["version"], "checked": True},
                )
                self.scan_service_ready = self.app._runtime_binding.manual_scans is not None

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
        # FileIndex is durable infrastructure and is opened before business
        # Active exists, so later publication can install Scan without an API
        # restart. No Storage or Provider is constructed by this assertion.
        self.assertIsNotNone(server.app._file_index)
        self.assertEqual(server.activated[0], 200)
        self.assertTrue(server.scan_service_ready)
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

    def test_operator_web_offers_a_return_to_the_storage_workspace(self) -> None:
        """The setup journey can hand the operator back to Storage.

        Completing setup inside Settings must not strand the operator
        there: once a managed Active exists, the Configuration view offers a
        return to the V2 Storage workspace that reads that exact Active. The
        link is a fixed same-origin application route, so it cannot become an
        arbitrary redirect, and it carries no token or revision identifier.
        """

        script = APP_JS.decode("utf-8")
        self.assertIn("backToStorageLink", script)
        self.assertIn("Return to Storage management", script)
        self.assertIn("'/ui-v2/storage'", script)

    def test_storage_workspace_reports_a_resumable_setup_draft(self) -> None:
        """An unfinished setup is resumable, and Storage reports it honestly.

        The V2 Storage empty state needs to distinguish "no setup Draft yet"
        from "a setup Draft exists to resume", so a return visit or reconnect
        never invites a second initialization that would conflict with the one
        already in flight.
        """

        route = "/api/v1/operations/storage-management/inventory"
        status, before = request(self.api, route, token="admin-token")
        self.assertEqual(status, 200)
        self.assertFalse(before["available"])
        self.assertTrue(before["setup"]["setupRequired"])
        self.assertFalse(before["setup"]["setupDraftExists"])

        status, created = request(
            self.api,
            "/api/v1/configuration/drafts/first",
            method="POST",
            body=None,
        )
        self.assertEqual(status, 201)

        # The existing setup Draft is advertised for resumption rather than
        # replaced, and nothing was activated or started by reading.
        status, after = request(self.api, route, token="admin-token")
        self.assertEqual(status, 200)
        self.assertTrue(after["setup"]["setupRequired"])
        self.assertTrue(after["setup"]["setupDraftExists"])
        self.assertIsNone(after["active"])
        self.assertEqual(after["items"], [])
        # The Draft identity stays in the configuration authority that owns it;
        # the Storage projection carries only the presence fact.
        self.assertNotIn(created["revisionId"], json.dumps(after, ensure_ascii=False))

        # Navigating or reading again is idempotent: it does not create a
        # competing first Draft.
        status, replay = request(
            self.api,
            "/api/v1/configuration/drafts/first",
            method="POST",
            body={},
        )
        self.assertEqual(status, 409)
        self.assertEqual(replay["error"]["details"]["durableState"], "setup_draft_preserved")
        status, again = request(self.api, route, token="admin-token")
        self.assertEqual(again["setup"]["setupDraftExists"], True)

    def test_a_read_only_principal_is_told_to_ask_an_administrator(self) -> None:
        """A viewer can read the setup state but never start it.

        The Storage empty state shows the viewer the same truthful recovery
        guidance without any control it cannot use, so the permission decision
        stays backend-authoritative.
        """

        route = "/api/v1/operations/storage-management/inventory"
        status, denied = request(
            self.api,
            "/api/v1/configuration/drafts/first",
            method="POST",
            body=None,
            token="viewer-token",
        )
        self.assertEqual(status, 403)
        status, viewer = request(self.api, route, token="viewer-token")
        self.assertEqual(status, 200)
        self.assertTrue(viewer["setup"]["setupRequired"])
        self.assertFalse(viewer["canStartSetup"])
        self.assertFalse(viewer["canManage"])
        # The viewer still gets the recovery route so the guidance is actionable.
        self.assertEqual(viewer["setup"]["setupPath"], "/ui-v2/configuration")

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

    def test_settings_json_excludes_deployment_authority_for_draft_and_active(self) -> None:
        """The Draft/Active JSON shown in Settings carries no deployment authority.

        Reproduction of the reviewed blocker: on the fresh management-only
        instance, create the first Draft and read the revision JSON; then
        activate the empty baseline and read the Active JSON.  Both must
        preserve the immutable revision identity and every managed family while
        excluding ``persistence.databasePath`` and ``api.principals``.
        """

        status, created = request(
            self.api, "/api/v1/configuration/drafts/first", method="POST", body=None
        )
        self.assertEqual(status, 201)
        revision_id = created["revisionId"]

        status, draft_detail = request(self.api, f"/api/v1/configuration/revisions/{revision_id}")
        self.assertEqual(status, 200)
        draft_document = draft_detail["document"]
        self.assertNotIn("persistence", draft_document)
        self.assertNotIn("principals", draft_document.get("api", {}))
        encoded = json.dumps(draft_detail, ensure_ascii=False)
        self.assertNotIn(self.database, encoded)
        self.assertNotIn("MF_ADMIN_TOKEN", encoded)
        self.assertNotIn("MF_VIEWER_TOKEN", encoded)
        # The immutable revision identity is preserved separately.
        self.assertEqual(draft_detail["revisionId"], revision_id)
        self.assertEqual(draft_detail["version"], created["version"])
        self.assertEqual(draft_detail["digest"], created["digest"])
        # Every managed family is preserved, including managed System Settings
        # that live inside ``api``.
        self.assertEqual(draft_document["setup"]["kind"], "first_runtime_setup")
        self.assertEqual(draft_document["storages"], [])
        self.assertEqual(draft_document["resourceLibraries"], [])
        self.assertEqual(draft_document["mediaLibraries"], [])
        self.assertEqual(draft_document["recognitionTypes"], [])
        self.assertEqual(draft_document["automationTaskDefinitions"], [])
        self.assertFalse(draft_document["api"]["remoteExecution"]["enabled"])

        status, validated = request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}/validate",
            method="POST",
            body={},
        )
        self.assertEqual(status, 200)
        status, activated = request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}/activate",
            method="POST",
            body={"expectedVersion": validated["version"], "checked": True},
        )
        self.assertEqual(status, 200)

        status, active_detail = request(
            self.api, f"/api/v1/configuration/revisions/{activated['revisionId']}"
        )
        self.assertEqual(status, 200)
        active_document = active_detail["document"]
        self.assertNotIn("persistence", active_document)
        self.assertNotIn("principals", active_document.get("api", {}))
        self.assertNotIn(self.database, json.dumps(active_detail, ensure_ascii=False))
        self.assertEqual(active_detail["status"], "active")
        self.assertEqual(active_detail["revisionId"], activated["revisionId"])

    def test_supplied_deployment_authority_is_validated_and_conflicts_rejected(self) -> None:
        """The shared boundary validates supplied authority instead of normalizing it.

        Deployment bootstrap authority is immutable: a managed edit/import may
        omit it (and then receives this deployment's own identity) or repeat it
        verbatim, but it must never be able to replace the principal/role/token
        identity that the next runtime startup reads, and malformed ``api``
        types must stay correctable errors rather than becoming a different,
        apparently valid document.
        """

        status, created = request(
            self.api, "/api/v1/configuration/drafts/first", method="POST", body=None
        )
        self.assertEqual(status, 201)
        revision_id = created["revisionId"]
        status, detail = request(self.api, f"/api/v1/configuration/revisions/{revision_id}")
        self.assertEqual(status, 200)
        projected = detail["document"]

        # Omitted authority (the supported projected round trip) is bound to
        # this deployment and stays validatable.
        status, saved = request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}",
            method="PUT",
            body={"document": projected, "expectedVersion": detail["version"]},
        )
        self.assertEqual(status, 200)
        stored = self.service.require(revision_id).document
        self.assertEqual(
            [item["tokenEnv"] for item in stored["api"]["principals"]],
            ["MF_ADMIN_TOKEN", "MF_VIEWER_TOKEN"],
        )

        # Authority that repeats this deployment's own identity verbatim is
        # accepted, so a whole-document round trip keeps working.
        version = saved["version"]
        status, detail = request(self.api, f"/api/v1/configuration/revisions/{revision_id}")
        self.assertEqual(status, 200)
        matching = json.loads(json.dumps(detail["document"]))
        matching["api"]["principals"] = json.loads(json.dumps(self.bootstrap["api"]["principals"]))
        status, saved = request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}",
            method="PUT",
            body={"document": matching, "expectedVersion": detail["version"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(saved["version"], detail["version"] + 1)
        self.assertEqual(version + 1, saved["version"])

        # Conflicting principal/role/token authority is rejected: a Viewer
        # token environment must not be able to claim the admin role.
        for label, conflicting in (
            (
                "escalated-role",
                {
                    "api": {
                        "principals": [
                            {"id": "viewer", "tokenEnv": "MF_VIEWER_TOKEN", "roles": ["admin"]}
                        ]
                    }
                },
            ),
            (
                "emptied-principals",
                {"api": {"principals": []}},
            ),
            (
                "foreign-token-env",
                {
                    "api": {
                        "principals": [
                            {"id": "admin", "tokenEnv": "OTHER_ADMIN_TOKEN", "roles": ["admin"]}
                        ]
                    }
                },
            ),
            (
                "legacy-token-env",
                {"api": {"tokenEnv": "MF_ADMIN_TOKEN"}},
            ),
            (
                "malformed-api-list",
                {"api": []},
            ),
            (
                "malformed-api-string",
                {"api": "MF_ADMIN_TOKEN"},
            ),
            (
                "malformed-principals-object",
                {"api": {"principals": {"id": "admin"}}},
            ),
            (
                "malformed-roles",
                {
                    "api": {
                        "principals": [{"id": "admin", "tokenEnv": "MF_ADMIN_TOKEN", "roles": []}]
                    }
                },
            ),
            (
                "literal-secret",
                {
                    "api": {
                        "principals": [
                            {
                                "id": "admin",
                                "tokenEnv": "MF_ADMIN_TOKEN",
                                "roles": ["admin"],
                                "token": "must-not-persist",
                            }
                        ]
                    }
                },
            ),
        ):
            with self.subTest(case=label):
                before = self.service.require(revision_id)
                status, detail = request(self.api, f"/api/v1/configuration/revisions/{revision_id}")
                self.assertEqual(status, 200)
                self.assertEqual(detail["version"], before.version)
                attempt = json.loads(json.dumps(detail["document"]))
                attempt.update(json.loads(json.dumps(conflicting)))
                status, rejected = request(
                    self.api,
                    f"/api/v1/configuration/revisions/{revision_id}",
                    method="PUT",
                    body={"document": attempt, "expectedVersion": detail["version"]},
                )
                self.assertEqual(status, 400, rejected)
                self.assertEqual(rejected["error"]["code"], "invalid_request")
                # The Draft is preserved unchanged and still correctable.
                current = self.service.require(revision_id)
                self.assertEqual(current.version, before.version)
                self.assertEqual(current.digest, before.digest)
                self.assertEqual(current.document, before.document)

        # The escalation attempt never reached persisted authority, so the
        # stored document still carries the bootstrap identity.
        stored = self.service.require(revision_id).document
        self.assertEqual(
            [(item["id"], item["tokenEnv"], item["roles"]) for item in stored["api"]["principals"]],
            [
                ("admin", "MF_ADMIN_TOKEN", ["admin"]),
                ("viewer", "MF_VIEWER_TOKEN", ["viewer"]),
            ],
        )

    def test_managed_edits_cannot_change_startup_bootstrap_permissions(self) -> None:
        """A real API restart proves managed edits cannot repoint authority.

        The reviewed blocker activated a document whose ``api.principals`` had
        been replaced with a Viewer token holding the admin role; after a real
        ``api serve`` restart with the unchanged bootstrap that Viewer token
        held administrative configuration permissions.  The boundary must now
        reject the edit, and the restarted deployment must keep the bootstrap
        permission projection.
        """

        status, created = request(
            self.api, "/api/v1/configuration/drafts/first", method="POST", body=None
        )
        self.assertEqual(status, 201)
        revision_id = created["revisionId"]

        # While it is still a correctable Draft, the escalation edit is
        # rejected before it can ever be persisted.
        status, detail = request(self.api, f"/api/v1/configuration/revisions/{revision_id}")
        self.assertEqual(status, 200)
        escalated = json.loads(json.dumps(detail["document"]))
        escalated["api"]["principals"] = [
            {"id": "viewer", "tokenEnv": "MF_VIEWER_TOKEN", "roles": ["admin"]}
        ]
        status, rejected = request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}",
            method="PUT",
            body={"document": escalated, "expectedVersion": detail["version"]},
        )
        self.assertEqual(status, 400, rejected)
        self.assertEqual(rejected["error"]["code"], "invalid_request")
        # A whole-document import of the same escalation fails closed too.
        status, rejected_import = request(
            self.api,
            "/api/v1/configuration/drafts",
            method="POST",
            body={"document": escalated},
        )
        self.assertEqual(status, 400, rejected_import)
        self.assertEqual(rejected_import["error"]["code"], "invalid_request")
        self.assertEqual(len(self.configuration_repository.list_revisions()), 1)

        status, validated = request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}/validate",
            method="POST",
            body={},
        )
        self.assertEqual(status, 200)
        self.assertEqual(validated["validationErrors"], [])
        status, _activated = request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}/activate",
            method="POST",
            body={"expectedVersion": validated["version"], "checked": True},
        )
        self.assertEqual(status, 200)

        class Server:
            app = None
            viewer_status = None
            admin_status = None

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def serve_forever(self):
                self.viewer_status = request(
                    self.app, "/api/v1/configuration/status", token="viewer-token"
                )
                self.admin_status = request(
                    self.app, "/api/v1/configuration/status", token="admin-token"
                )

        with tempfile.TemporaryDirectory() as directory:
            # A separate deployment whose bootstrap file is the unchanged
            # authority, started through the real CLI entry point.
            runtime = str(Path(directory, "runtime.sqlite3"))
            bootstrap = json.loads(json.dumps(self.bootstrap))
            bootstrap["persistence"]["databasePath"] = runtime
            config = Path(directory, "bootstrap.json")
            config.write_text(json.dumps(bootstrap), encoding="utf-8")

            repository = SQLiteConfigurationRepository(runtime)
            service = ManagedConfigurationService(
                repository,
                bootstrap_database_path=runtime,
                bootstrap_document=bootstrap,
                management_only=True,
            )
            draft = service.create_first_draft(actor="operator")
            with self.assertRaises(ValueError):
                service.edit_draft(
                    draft.revision_id,
                    {
                        **service.require(draft.revision_id).document,
                        "api": {
                            "principals": [
                                {
                                    "id": "viewer",
                                    "tokenEnv": "MF_VIEWER_TOKEN",
                                    "roles": ["admin"],
                                }
                            ]
                        },
                    },
                    expected_version=service.require(draft.revision_id).version,
                    actor="attacker",
                )
            validated = service.validate(draft.revision_id, actor="operator")
            service.activate(
                validated.revision_id,
                expected_version=validated.version,
                actor="operator",
            )
            repository.close()

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
                    side_effect=AssertionError("management API must not construct Storage"),
                ),
            ):
                status = final_main(
                    ["--config", str(config), "api", "serve"],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(status, 0)
            self.assertIsNotNone(server.app)
            self.assertEqual(server.viewer_status[0], 200, server.viewer_status[1])
            self.assertFalse(server.viewer_status[1]["canManageConfiguration"])
            self.assertFalse(server.viewer_status[1]["canActivateConfiguration"])
            self.assertEqual(server.admin_status[0], 200, server.admin_status[1])
            self.assertTrue(server.admin_status[1]["canManageConfiguration"])
            self.assertTrue(server.admin_status[1]["canActivateConfiguration"])

    def test_portable_export_excludes_authority_and_rebinds_on_import(self) -> None:
        """Export excludes deployment authority; import binds it back.

        A portable package must not carry this deployment's database locator or
        API principal identity, and importing it must bind the receiving
        deployment's own authority instead of failing validation or adopting
        foreign identity.
        """

        status, created = request(
            self.api, "/api/v1/configuration/drafts/first", method="POST", body=None
        )
        self.assertEqual(status, 201)
        revision_id = created["revisionId"]
        status, validated = request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}/validate",
            method="POST",
            body={},
        )
        self.assertEqual(status, 200)
        status, _active = request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}/activate",
            method="POST",
            body={"expectedVersion": validated["version"], "checked": True},
        )
        self.assertEqual(status, 200)

        status, package = request(
            self.api,
            f"/api/v1/configuration/packages/export/configuration?revisionId={revision_id}",
        )
        self.assertEqual(status, 200)
        exported = package["payload"]["document"]
        self.assertNotIn("persistence", exported)
        self.assertNotIn("principals", exported.get("api", {}))
        encoded = json.dumps(package, ensure_ascii=False)
        self.assertNotIn(self.database, encoded)
        self.assertNotIn("MF_ADMIN_TOKEN", encoded)

        status, imported = request(
            self.api,
            "/api/v1/configuration/packages",
            method="POST",
            body={"package": package},
        )
        self.assertEqual(status, 201)
        imported_id = imported["revision"]["revisionId"]
        bound = self.service.require(imported_id).document
        self.assertEqual(bound["persistence"]["databasePath"], self.database)
        self.assertEqual(
            [item["tokenEnv"] for item in bound["api"]["principals"]],
            ["MF_ADMIN_TOKEN", "MF_VIEWER_TOKEN"],
        )

        # The round trip stays validatable and activatable on this deployment.
        status, revalidated = request(
            self.api,
            f"/api/v1/configuration/revisions/{imported_id}/validate",
            method="POST",
            body={},
        )
        self.assertEqual(status, 200)
        self.assertEqual(revalidated["validationErrors"], [])
        status, reactivated = request(
            self.api,
            f"/api/v1/configuration/revisions/{imported_id}/activate",
            method="POST",
            body={"expectedVersion": revalidated["version"], "checked": True},
        )
        self.assertEqual(status, 200)
        self.assertEqual(reactivated["status"], "active")

    def test_advanced_document_round_trip_rebinds_deployment_authority(self) -> None:
        """The advanced whole-document editor round-trips the projected JSON.

        The displayed document omits deployment authority, so saving it back
        must bind this deployment's locator and principal identity again rather
        than persisting a document that can no longer validate or authenticate.
        """

        status, created = request(
            self.api, "/api/v1/configuration/drafts/first", method="POST", body=None
        )
        self.assertEqual(status, 201)
        revision_id = created["revisionId"]
        status, detail = request(self.api, f"/api/v1/configuration/revisions/{revision_id}")
        self.assertEqual(status, 200)
        edited = json.loads(json.dumps(detail["document"]))
        self.assertNotIn("persistence", edited)
        edited["historyPath"] = ".mediaflow/history.jsonl"

        status, saved = request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}",
            method="PUT",
            body={"document": edited, "expectedVersion": detail["version"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(saved["version"], detail["version"] + 1)
        stored = self.service.require(revision_id).document
        self.assertEqual(stored["persistence"]["databasePath"], self.database)
        self.assertEqual(
            [item["tokenEnv"] for item in stored["api"]["principals"]],
            ["MF_ADMIN_TOKEN", "MF_VIEWER_TOKEN"],
        )
        # Bound authority keeps the edited Draft validatable and activatable.
        status, validated = request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}/validate",
            method="POST",
            body={},
        )
        self.assertEqual(status, 200)
        self.assertEqual(validated["validationErrors"], [])

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
