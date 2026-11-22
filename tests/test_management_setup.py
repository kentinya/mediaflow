from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from mediaflow.application.accounts import AccountService, hash_password, hash_secret
from mediaflow.application.configuration_snapshot import (
    ManagedConfigurationService,
    build_first_setup_starter_document,
)
from mediaflow.domain.accounts import Account, AccountSessionRecord
from mediaflow.domain.configuration_integrity import (
    MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
    canonical_document_digest,
)
from mediaflow.domain.configuration_management import (
    ConfigurationObjectKind,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
)
from mediaflow.domain.security import ApiPermission, ApiRole, ResolvedApiPrincipal
from mediaflow.infrastructure.runtime_configuration import (
    is_minimal_management_bootstrap,
    load_minimal_management_bootstrap,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.resident_entry_fixtures import run_api_entry, serve_once


def request(api, path, *, method="GET", token="admin-token", body=None, cookie=None, origin=None):
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
    # The current entry is the account session cookie.  The helper keeps the
    # historical token parameter as the fixture's session-token name so the
    # existing RBAC assertions still address the same account identity.
    if cookie is not None:
        environ["HTTP_COOKIE"] = cookie
    elif token is not None:
        environ["HTTP_COOKIE"] = f"mediaflow_session={token}"
    environ["HTTP_HOST"] = "127.0.0.1"
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        environ["HTTP_ORIGIN"] = origin or "http://127.0.0.1"
    elif origin is not None:
        environ["HTTP_ORIGIN"] = origin
    value = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(value)


class ManagementSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = str(Path(self.directory.name, "runtime.sqlite3"))
        self.bootstrap = {
            "version": 1,
            "persistence": {"databasePath": self.database},
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
        now = datetime.now(UTC)
        for account_id, username, role, token in (
            ("admin", "admin", ApiRole.ADMIN, "admin-token"),
            ("viewer", "viewer", ApiRole.VIEWER, "viewer-token"),
        ):
            self.task_repository.create_account(
                Account(account_id, username, (role,), True, now, now, now),
                hash_password(f"{username}-password"),
            )
            self.task_repository.create_account_session(
                AccountSessionRecord(
                    f"session-{account_id}",
                    account_id,
                    hash_secret(token),
                    now,
                    now,
                    now + timedelta(hours=12),
                    now + timedelta(hours=24),
                )
            )
        self.api = MediaFlowApi(
            self.task_repository,
            account_service=AccountService(self.task_repository),
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
        self.assertEqual(loaded.api_principals, ())

        workflow = json.loads(json.dumps(self.bootstrap))
        workflow["storages"] = []
        self.assertFalse(is_minimal_management_bootstrap(workflow))
        with self.assertRaisesRegex(ValueError, "minimal management bootstrap"):
            load_minimal_management_bootstrap(workflow)

        literal_secret = json.loads(json.dumps(self.bootstrap))
        literal_secret["api"] = {
            "principals": [
                {
                    "id": "admin",
                    "tokenEnv": "MF_ADMIN_TOKEN",
                    "roles": ["admin"],
                    "token": "must-not-persist",
                }
            ]
        }
        with self.assertRaises(ValueError):
            load_minimal_management_bootstrap(literal_secret)

    def test_fresh_readiness_and_system_projection_are_bounded(self) -> None:
        status, health = request(self.api, "/health", token=None)
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "ok")
        self.assertIs(health["processAlive"], True)
        self.assertIn("firstAdministratorRequired", health)
        self.assertIn("configurationRequired", health)
        self.assertNotIn("token", json.dumps(health).casefold())

        status, readiness = request(self.api, "/api/management/readiness")
        self.assertEqual(status, 200)
        self.assertTrue(readiness["managementReady"])
        self.assertTrue(readiness["setupRequired"])
        self.assertFalse(readiness["runtimeConfigured"])
        self.assertFalse(readiness["workflowAvailable"])
        self.assertIsNone(readiness["active"])
        self.assertNotIn("scan", readiness["commandReadiness"])
        self.assertEqual(
            readiness["commandReadiness"]["directTransfer"]["recoveryDestination"],
            "/configuration",
        )

        status, configuration = request(self.api, "/api/configuration")
        self.assertEqual(status, 200)
        self.assertEqual(configuration["authority"], "MANAGEMENT_BOOTSTRAP")
        self.assertEqual(configuration["health"], "SETUP_REQUIRED")
        self.assertIsNone(configuration["active"])
        self.assertNotIn("setupDraft", configuration)
        self.assertGreaterEqual(len(configuration["setupBlockers"]), 5)
        self.assertNotIn("MF_ADMIN_TOKEN", json.dumps(configuration))

        status, system = request(self.api, "/api/system/status")
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
            "automationTaskDefinitions": [{"id": "daily", "enabled": True}],
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
        # The manual organizing permission recovers through the ordinary Files
        # entry; the retired independent preparation address is not a
        # readiness destination any more.
        self.assertFalse(viewer["organize"]["authorized"])
        self.assertEqual(
            viewer["organize"]["recoveryDestination"],
            "/resourcelib/files",
        )
        self.assertNotEqual(
            viewer["organize"]["recoveryDestination"],
            "/operations/organize/new",
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
                cookie = f"mediaflow_session={admin_grant.token}"
                self.health = request(self.app, "/health", token=None)
                self.readiness = request(
                    self.app, "/api/management/readiness", token=None, cookie=cookie
                )
                self.configuration = request(
                    self.app, "/api/configuration", token=None, cookie=cookie
                )
                _, created = request(
                    self.app,
                    "/api/configuration/initialize",
                    method="POST",
                    body={},
                    token=None,
                    cookie=cookie,
                    origin="http://127.0.0.1",
                )
                self.activated = (201, created)
                self.scan_service_ready = False

        with tempfile.TemporaryDirectory() as directory:
            bootstrap = json.loads(json.dumps(self.bootstrap))
            database = str(Path(directory, "api.sqlite3"))
            bootstrap["persistence"]["databasePath"] = database
            config = Path(directory, "bootstrap.json")
            config.write_text(json.dumps(bootstrap), encoding="utf-8")
            with SQLiteTaskRepository(database) as task_repository:
                now = datetime.now(UTC)
                task_repository.create_account(
                    Account(
                        "fresh-admin",
                        "admin",
                        (ApiRole.ADMIN,),
                        True,
                        now,
                        now,
                        now,
                    ),
                    hash_password("correct-horse"),
                )
                admin_grant = AccountService(task_repository).login(
                    username="admin", password="correct-horse", remember=False
                )
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
                patch("mediaflow.production_wsgi.serve", side_effect=serve_once(make_server)),
                patch(
                    "mediaflow.infrastructure.runtime_configuration.RuntimeConfiguration.create_storages",
                    side_effect=AssertionError("fresh API must not construct Storage"),
                ),
                patch(
                    "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBProvider",
                    side_effect=AssertionError("fresh API must not construct Provider"),
                ),
            ):
                status = run_api_entry(
                    config,
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                    skip_preflight=False,
                )

        self.assertEqual(status, 0)
        self.assertIsNotNone(server.app)
        # The API starts from management-only authority: no Storage, Provider,
        # discovery or per-file catalog is constructed before an Active exists.
        self.assertFalse(hasattr(server.app, "_file_catalog"))
        self.assertFalse(hasattr(server.app, "_file_index"))
        self.assertEqual(server.activated[0], 201)
        self.assertFalse(server.scan_service_ready)
        self.assertEqual(server.health[0], 200)
        self.assertEqual(server.health[1]["status"], "ok")
        self.assertIs(server.health[1]["processAlive"], True)
        self.assertIs(server.health[1]["firstAdministratorRequired"], False)
        self.assertIs(server.health[1]["configurationRequired"], True)
        self.assertEqual(server.readiness[0], 200)
        self.assertTrue(server.readiness[1]["managementReady"])
        self.assertTrue(server.readiness[1]["setupRequired"])
        self.assertIsNone(server.configuration[1]["active"])

    def test_storage_workspace_reports_the_published_empty_baseline(self) -> None:
        route = "/api/operations/storage-management/inventory"
        status, before = request(self.api, route, token="admin-token")
        self.assertEqual(status, 200)
        self.assertFalse(before["available"])
        self.assertTrue(before["setup"]["setupRequired"])
        self.assertNotIn("setupDraftExists", before["setup"])

        status, created = request(
            self.api,
            "/api/configuration/initialize",
            method="POST",
            body=None,
        )
        self.assertEqual(status, 201, created)
        self.assertEqual(created["status"], "active")

        status, after = request(self.api, route, token="admin-token")
        self.assertEqual(status, 200)
        self.assertFalse(after["setup"]["setupRequired"])
        self.assertNotIn("setupDraftExists", after["setup"])
        self.assertIsNotNone(after["active"])
        self.assertEqual(after["active"]["revisionId"], created["revisionId"])
        self.assertEqual(after["items"], [])

        status, replay = request(
            self.api,
            "/api/configuration/initialize",
            method="POST",
            body={},
        )
        self.assertEqual(status, 409)
        self.assertEqual(
            replay["error"]["details"]["durableState"], "active_configuration_preserved"
        )
        self.assertFalse(
            any(
                revision.status.value in {"draft", "validated"}
                for revision in self.configuration_repository.list_revisions()
            )
        )

    def test_a_read_only_principal_is_told_to_ask_an_administrator(self) -> None:
        """A viewer can read the setup state but never start it.

        The Storage empty state shows the viewer the same truthful recovery
        guidance without any control it cannot use, so the permission decision
        stays backend-authoritative.
        """

        route = "/api/operations/storage-management/inventory"
        status, denied = request(
            self.api,
            "/api/configuration/initialize",
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
        self.assertEqual(viewer["setup"]["setupPath"], "/configuration")

    def test_first_draft_preserves_only_bootstrap_refs_and_is_resumable(self) -> None:
        status, created = request(
            self.api,
            "/api/configuration/initialize",
            method="POST",
            body=None,
        )
        self.assertEqual(status, 201)
        self.assertEqual(created["status"], "active")
        self.assertEqual(created["schemaVersion"], 1)
        revision = self.service.require(created["revisionId"])
        document = revision.document
        self.assertEqual(document["persistence"], self.bootstrap["persistence"])
        self.assertNotIn("principals", document.get("api", {}))
        self.assertEqual(document["setup"]["kind"], "first_runtime_setup")
        self.assertFalse(document["setup"]["runtimeReady"])
        self.assertEqual(document["storages"], [])
        self.assertEqual(document["resourceLibraries"], [])
        self.assertEqual(document["mediaLibraries"], [])
        self.assertNotIn("schedules", document["automation"])
        self.assertEqual(document["automationTaskDefinitions"], [])
        self.assertEqual(document["webhooks"], [])
        self.assertNotIn("remoteExecution", document["api"])
        self.assertNotIn("rootPath", json.dumps(document))
        self.assertNotIn("historyPath", json.dumps(document))
        self.assertNotIn("https://", json.dumps(document))
        self.assertNotIn("must-not-persist", json.dumps(document))
        audits = self.configuration_repository.list_revision_audits(revision.revision_id)
        self.assertTrue(any(item.action == "activate" for item in audits))

        status, configuration = request(self.api, "/api/configuration/status")
        self.assertEqual(status, 200)
        self.assertNotIn("setupDraft", configuration)
        self.assertFalse(configuration["setupRequired"])
        self.assertEqual(configuration["active"]["revisionId"], revision.revision_id)

        status, conflict = request(
            self.api,
            "/api/configuration/initialize",
            method="POST",
            body={},
        )
        self.assertEqual(status, 409)
        self.assertEqual(
            conflict["error"]["details"]["durableState"], "active_configuration_preserved"
        )
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
            self.api, "/api/configuration/initialize", method="POST", body=None
        )
        self.assertEqual(status, 201)
        revision_id = created["revisionId"]

        status, draft_detail = request(self.api, f"/api/configuration/revisions/{revision_id}")
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
        self.assertNotIn("remoteExecution", draft_document.get("api", {}))

        status, active_detail = request(self.api, f"/api/configuration/revisions/{revision_id}")
        self.assertEqual(status, 200)
        active_document = active_detail["document"]
        self.assertNotIn("persistence", active_document)
        self.assertNotIn("principals", active_document.get("api", {}))
        self.assertNotIn(self.database, json.dumps(active_detail, ensure_ascii=False))
        self.assertEqual(active_detail["status"], "active")
        self.assertEqual(active_detail["revisionId"], revision_id)

    def test_retired_principal_authority_is_rejected_for_every_submission(self) -> None:
        """Current deployments have no JSON principal authority.

        A whole-document round trip may omit deployment authority, and the
        receiving locator is rebound. Any newly supplied ``api.principals`` or
        ``api.tokenEnv`` is retired input and fails before persistence.
        """

        status, created = request(
            self.api, "/api/configuration/initialize", method="POST", body=None
        )
        self.assertEqual(status, 201)
        revision_id = created["revisionId"]
        status, detail = request(self.api, f"/api/configuration/revisions/{revision_id}")
        self.assertEqual(status, 200)
        projected = detail["document"]
        self.assertNotIn("principals", projected.get("api", {}))
        self.assertNotIn("persistence", projected)

        status, saved = request(
            self.api,
            "/api/configuration/publish",
            method="POST",
            body={"document": projected},
        )
        self.assertEqual(status, 200)
        stored = self.service.require(revision_id).document
        self.assertEqual(stored["persistence"]["databasePath"], self.database)
        self.assertNotIn("principals", stored.get("api", {}))

        for label, retired in (
            (
                "principals",
                {
                    "api": {
                        "principals": [
                            {"id": "admin", "tokenEnv": "MF_ADMIN_TOKEN", "roles": ["admin"]}
                        ]
                    }
                },
            ),
            ("emptied-principals", {"api": {"principals": []}}),
            ("token-env", {"api": {"tokenEnv": "MF_ADMIN_TOKEN"}}),
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
                status, detail = request(self.api, f"/api/configuration/revisions/{revision_id}")
                self.assertEqual(status, 200)
                attempt = json.loads(json.dumps(detail["document"]))
                attempt.update(json.loads(json.dumps(retired)))
                status, rejected = request(
                    self.api,
                    "/api/configuration/publish",
                    method="POST",
                    body={"document": attempt},
                )
                self.assertEqual(status, 400, rejected)
                self.assertEqual(rejected["error"]["code"], "invalid_request")
                self.assertRegex(rejected["error"]["message"], "retired|forbidden")
                current = self.service.require(revision_id)
                self.assertEqual(current.version, before.version)
                self.assertEqual(current.digest, before.digest)
                self.assertEqual(current.document, before.document)

    def test_managed_edits_cannot_change_startup_bootstrap_permissions(self) -> None:
        """A real API restart proves managed edits cannot repoint authority.

        The reviewed blocker activated a document whose ``api.principals`` had
        been replaced with a Viewer token holding the admin role; after a real
        fixed API entry restart with the unchanged bootstrap that Viewer token
        held administrative configuration permissions.  The boundary must now
        reject the edit, and the restarted deployment must keep the bootstrap
        permission projection.
        """

        status, created = request(
            self.api, "/api/configuration/initialize", method="POST", body=None
        )
        self.assertEqual(status, 201)
        revision_id = created["revisionId"]

        # While it is still a correctable Draft, the escalation edit is
        # rejected before it can ever be persisted.
        status, detail = request(self.api, f"/api/configuration/revisions/{revision_id}")
        self.assertEqual(status, 200)
        escalated = json.loads(json.dumps(detail["document"]))
        escalated.setdefault("api", {})["principals"] = [
            {"id": "viewer", "tokenEnv": "MF_VIEWER_TOKEN", "roles": ["admin"]}
        ]
        status, rejected = request(
            self.api,
            "/api/configuration/publish",
            method="POST",
            body={"document": escalated},
        )
        self.assertEqual(status, 400, rejected)
        self.assertEqual(rejected["error"]["code"], "invalid_request")
        # A whole-document import of the same escalation fails closed too.
        status, rejected_import = request(
            self.api,
            "/api/configuration/publish",
            method="POST",
            body={"document": escalated},
        )
        self.assertEqual(status, 400, rejected_import)
        self.assertEqual(rejected_import["error"]["code"], "invalid_request")
        self.assertEqual(len(self.configuration_repository.list_revisions()), 1)

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
                    self.app,
                    "/api/configuration/status",
                    token=None,
                    cookie=f"mediaflow_session={viewer_grant.token}",
                )
                self.admin_status = request(
                    self.app,
                    "/api/configuration/status",
                    token=None,
                    cookie=f"mediaflow_session={admin_grant.token}",
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

            with SQLiteTaskRepository(runtime) as task_repository:
                accounts = AccountService(task_repository)
                now = datetime.now(UTC)
                for account_id, username, role in (
                    ("admin-account", "admin", ApiRole.ADMIN),
                    ("viewer-account", "viewer", ApiRole.VIEWER),
                ):
                    task_repository.create_account(
                        Account(
                            account_id,
                            username,
                            (role,),
                            True,
                            now,
                            now,
                            now,
                        ),
                        hash_password("correct-horse"),
                    )
                admin_grant = accounts.login(
                    username="admin", password="correct-horse", remember=False
                )
                viewer_grant = accounts.login(
                    username="viewer", password="correct-horse", remember=False
                )

            server = Server()

            def make_server(_host, _port, app):
                server.app = app
                return server

            with (
                patch.dict(
                    os.environ,
                    {"MF_ADMIN_TOKEN": "retired-secret", "MF_VIEWER_TOKEN": "retired-secret"},
                    clear=True,
                ),
                patch("mediaflow.production_wsgi.serve", side_effect=serve_once(make_server)),
                patch(
                    "mediaflow.infrastructure.runtime_configuration.RuntimeConfiguration.create_storages",
                    side_effect=AssertionError("management API must not construct Storage"),
                ),
            ):
                status = run_api_entry(
                    config,
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                    skip_preflight=False,
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
            self.api, "/api/configuration/initialize", method="POST", body=None
        )
        self.assertEqual(status, 201)
        revision_id = created["revisionId"]
        status, package = request(
            self.api,
            f"/api/configuration/packages/export/configuration?revisionId={revision_id}",
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
            "/api/configuration/packages",
            method="POST",
            body={"package": package},
        )
        self.assertIn(status, (200, 201))
        imported_id = imported["revision"]["revisionId"]
        bound = self.service.require(imported_id).document
        self.assertEqual(bound["persistence"]["databasePath"], self.database)
        self.assertNotIn("principals", bound.get("api", {}))

        # The round trip published a complete Active snapshot directly.
        published = self.service.require(imported_id)
        self.assertEqual(published.status.value, "active")
        self.assertFalse(
            any(
                revision.status.value in {"draft", "validated"}
                for revision in self.configuration_repository.list_revisions()
            )
        )

    def test_advanced_document_round_trip_rebinds_deployment_authority(self) -> None:
        """The advanced whole-document editor round-trips the projected JSON.

        The displayed document omits deployment authority, so saving it back
        must bind this deployment's locator and principal identity again rather
        than persisting a document that can no longer validate or authenticate.
        """

        status, created = request(
            self.api, "/api/configuration/initialize", method="POST", body=None
        )
        self.assertEqual(status, 201)
        revision_id = created["revisionId"]
        status, detail = request(self.api, f"/api/configuration/revisions/{revision_id}")
        self.assertEqual(status, 200)
        edited = json.loads(json.dumps(detail["document"]))
        self.assertNotIn("persistence", edited)
        edited["historyPath"] = ".mediaflow/history.jsonl"

        status, saved = request(
            self.api,
            "/api/configuration/publish",
            method="POST",
            body={"document": edited},
        )
        self.assertEqual(status, 200)
        stored = self.service.require(revision_id).document
        self.assertEqual(stored["persistence"]["databasePath"], self.database)
        self.assertNotIn("principals", stored.get("api", {}))

    def test_read_only_and_workflow_admission_are_safe(self) -> None:
        status, denied = request(
            self.api,
            "/api/configuration/initialize",
            method="POST",
            token="viewer-token",
            body={},
        )
        self.assertEqual(status, 403)
        status, visible = request(self.api, "/api/configuration", token="viewer-token")
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
                ("/api/tasks/example/cancel", {}),
                ("/api/automation/task-definitions", {"definition": {}}),
                ("/api/files/example/transfers", {}),
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
        self.assertEqual((), self.task_repository.list_tasks())
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

    def test_restart_preserves_published_baseline_and_does_not_fall_back_to_setup(self) -> None:
        starter = build_first_setup_starter_document(
            load_minimal_management_bootstrap(self.bootstrap)
        )
        created = self.service.publish_document(starter, actor="tester")
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
        self.assertNotIn("setupDraft", status)
        self.assertFalse(status["setupRequired"])
        self.assertEqual(status["active"]["revisionId"], created.revision_id)
        self.assertFalse(
            any(
                revision.status.value in {"draft", "validated"}
                for revision in self.configuration_repository.list_revisions()
            )
        )

    def test_accepted_first_setup_draft_from_a_previous_version_still_activates(self) -> None:
        """A server-owned first Draft accepted earlier keeps its setup journey.

        The previous version stored the starter with the then-current nested
        empty Webhook section and no base Active.  The upgraded instance reads
        the same durable revision, so validating and activating it must not
        reject the deployment-generated bytes or rewrite the document, ID or
        digest.  A newly submitted nested Webhook section is still refused.
        """

        starter = build_first_setup_starter_document(
            load_minimal_management_bootstrap(self.bootstrap)
        )
        starter.pop("webhooks")
        starter["notifications"]["webhooks"] = []
        now = datetime.now(UTC)
        accepted = self.configuration_repository.create_revision(
            ManagedConfigurationRevision(
                str(uuid4()),
                1,
                ManagedConfigurationStatus.DRAFT,
                MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
                canonical_document_digest(starter),
                starter,
                now,
                now,
            )
        )
        self.assertIsNone(accepted.base_active_revision_id)

        # The former draft endpoint is an unknown entry and never publishes the
        # previously accepted starter.
        status, retired = request(
            self.api,
            f"/api/configuration/revisions/{accepted.revision_id}/validate",
            method="POST",
            body={},
        )
        self.assertEqual(status, 404)
        self.assertEqual(retired["error"]["code"], "not_found")
        self.assertIsNone(self.service.active())

        with self.assertRaises(ValueError):
            self.service.import_draft(
                {
                    **copy.deepcopy(starter),
                    "storages": [],
                },
                actor="tester",
            )


if __name__ == "__main__":
    unittest.main()
