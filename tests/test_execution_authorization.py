from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.configuration_integrity import canonical_document_digest
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi


def activate_managed(document: dict) -> None:
    database = document["persistence"]["databasePath"]
    with SQLiteConfigurationRepository(database) as repository:
        service = ManagedConfigurationService(
            repository,
            bootstrap_database_path=database,
            bootstrap_document=document,
        )
        draft = service.import_draft(document, actor="tester")
        validated = service.validate(draft.revision_id, actor="tester")
        service.activate(
            validated.revision_id,
            expected_version=validated.version,
            actor="tester",
        )


def request(api, path, method="POST", document=None):
    body = json.dumps(document).encode() if document is not None else b""
    status = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(body)),
        "HTTP_AUTHORIZATION": "Bearer admin-token",
        "wsgi.input": io.BytesIO(body),
    }
    result = b"".join(api(environ, lambda value, headers: status.append(value)))
    return int(status[0].split()[0]), json.loads(result)


class RetiredRemoteExecutionTests(unittest.TestCase):
    def test_no_cli_or_dispatch_carries_ticket_commands(self):
        # The general CLI and its ticket-era commands are retired entirely, so
        # there is no dispatch surface that could accept one.
        for module in ("mediaflow.cli", "mediaflow.final_cli"):
            with self.subTest(module=module):
                with self.assertRaises(ModuleNotFoundError):
                    __import__(module)

    def test_api_ticket_submission_is_an_unknown_route_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteTaskRepository(Path(directory, "runtime.sqlite3"))
            try:
                api = MediaFlowApi(
                    repository,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                )
                status, document = request(
                    api,
                    "/api/tasks",
                    document={"command": "organize", "execute": True, "limit": 1},
                )
                self.assertIn(status, (404, 405), document)
                self.assertNotIn("taskId", document)
                self.assertEqual((), repository.list_tasks())
                tables = {
                    row[0]
                    for row in repository._connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                self.assertNotIn("execution_authorizations", tables)
                self.assertNotIn("execution_authorization_audit", tables)
            finally:
                repository.close()

    def test_historical_remote_execution_setting_stays_readable_without_authority(self):
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            document["persistence"] = {"databasePath": str(Path(directory, "runtime.sqlite3"))}
            document["api"]["remoteExecution"] = {
                "enabled": True,
                "maximumTtlSeconds": 900,
            }
            loaded = load_runtime_configuration(document)
            self.assertFalse(hasattr(loaded, "remote_execution_enabled"))
            from mediaflow.domain.system_settings import (
                SystemSettingsEdit,
                validate_settings_edit,
            )

            errors = validate_settings_edit(
                (SystemSettingsEdit("api.remoteExecution.enabled", False),),
                bootstrap_database_path=str(Path(directory, "runtime.sqlite3")),
            )
            self.assertEqual("field_retired", errors[0]["code"])


class RetiredRemoteExecutionConfigurationTests(unittest.TestCase):
    """A newly submitted ticket setting is refused; history stays readable."""

    def _service(self, database: Path, document: dict):
        from mediaflow.application.configuration_snapshot import ManagedConfigurationService
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )

        repository = SQLiteConfigurationRepository(database)
        self.addCleanup(repository.close)
        return ManagedConfigurationService(repository), repository

    def _api(self, database: Path, document: dict, service):
        repository = SQLiteTaskRepository(database)
        self.addCleanup(repository.close)
        return (
            MediaFlowApi(
                repository,
                principals=(
                    ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                ),
                configuration_service=service,
                bootstrap_document=document,
            ),
            repository,
        )

    @staticmethod
    def _document(database: Path) -> dict:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["persistence"] = {"databasePath": str(database)}
        root = database.parent
        for path in (
            root / "source" / "incoming",
            root / "target" / "Movies",
        ):
            path.mkdir(parents=True, exist_ok=True)
        for storage in document.get("storages", []):
            if storage.get("id") == document["storages"][0]["id"]:
                storage["rootPath"] = str(root / "source")
            else:
                storage["rootPath"] = str(root / "target")
        return document

    def test_new_document_with_ticket_setting_is_refused_and_publishes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            document = self._document(database)
            service, _ = self._service(database, document)
            api, repository = self._api(database, document, service)
            submitted = json.loads(json.dumps(document))
            submitted["api"]["remoteExecution"] = {
                "enabled": True,
                "maximumTtlSeconds": 900,
            }

            status, body = request(
                api,
                "/api/configuration/publish",
                method="POST",
                document={"document": submitted},
            )
            self.assertEqual(400, status, body)
            self.assertIn("retired", body["error"]["message"])
            self.assertIsNone(service.active())
            self.assertEqual((), repository.list_tasks())

            status, imported = request(
                api,
                "/api/configuration/publish",
                method="POST",
                document={"document": document},
            )
            self.assertEqual(200, status, imported)
            self.assertEqual("active", imported["status"])
            active = service.active()
            self.assertIsNotNone(active)
            self.assertEqual(
                [item["id"] for item in active.document["resourceLibraries"]],
                [item["id"] for item in document["resourceLibraries"]],
            )
            # A subsequent direct publication of the retired field is refused
            # before any new Active or Task is created.
            status, refused = request(
                api,
                "/api/configuration/publish",
                method="POST",
                document={"document": submitted},
            )
            self.assertEqual(400, status, refused)
            self.assertEqual(service.active().revision_id, active.revision_id)
            self.assertEqual((), repository.list_tasks())

    def test_existing_unpublished_revision_with_ticket_setting_is_retired(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            document = self._document(database)
            service, repository = self._service(database, document)
            api, tasks = self._api(database, document, service)
            draft = service.import_draft(document, actor="admin")
            historical = json.loads(json.dumps(draft.document))
            historical["api"]["remoteExecution"] = {"enabled": True}
            digest = canonical_document_digest(historical)
            with repository._connection:
                repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=?, digest=? "
                    "WHERE revision_id=?",
                    (
                        json.dumps(historical, sort_keys=True, separators=(",", ":")),
                        digest,
                        draft.revision_id,
                    ),
                )

            # The draft lifecycle entry points are unknown; the unpublished
            # historical row cannot become Active through them.
            for action in ("validate", "activate"):
                status, refused = request(
                    api,
                    f"/api/configuration/revisions/{draft.revision_id}/{action}",
                    method="POST",
                    document={"expectedVersion": draft.version} if action == "activate" else {},
                )
                self.assertEqual(404, status, refused)
                self.assertEqual(refused["error"]["code"], "not_found")
            self.assertIsNone(service.active())
            self.assertEqual((), tasks.list_tasks())

    def test_historical_active_stays_readable_and_successor_strips_the_setting(self):
        from mediaflow.application.system_settings import SystemSettingsService
        from mediaflow.domain.system_settings import SystemSettingsEdit

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            document = self._document(database)
            service, repository = self._service(database, document)
            api, _tasks = self._api(database, document, service)
            draft = service.import_draft(document, actor="admin")
            validated = service.validate(draft.revision_id, actor="admin")
            active = service.activate(
                validated.revision_id, expected_version=validated.version, actor="admin"
            )

            # A real accepted V2 revision that still carries the historical
            # setting: its original bytes, ID and digest stay untouched.
            historical = json.loads(json.dumps(active.document))
            historical["api"]["remoteExecution"] = {
                "enabled": True,
                "maximumTtlSeconds": 900,
            }
            digest = canonical_document_digest(historical)
            with repository._connection:
                repository._connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=?, digest=? "
                    "WHERE revision_id=?",
                    (
                        json.dumps(historical, sort_keys=True, separators=(",", ":")),
                        digest,
                        active.revision_id,
                    ),
                )

            loaded = load_runtime_configuration(repository.get_active_revision().document)
            self.assertFalse(hasattr(loaded, "remote_execution_enabled"))

            # The typed System Settings Save derives a successor from that same
            # historical Active; the successor drops the retired setting rather
            # than forcing the operator to rebuild the whole configuration.
            settings = SystemSettingsService(service)
            settings.edit(
                edits=(SystemSettingsEdit("automation.maximumActiveJobs", 120),),
                actor="admin",
            )
            successor = (
                service.latest_open_draft_containing("automationTaskDefinitions", "")
                or service.open_draft_revisions()[0]
            )
            self.assertNotIn("remoteExecution", successor.document.get("api", {}))
            self.assertEqual(120, successor.document["automation"]["maximumActiveJobs"])
            successor = service.validate(successor.revision_id, actor="admin")
            self.assertEqual("validated", successor.status.value, successor.validation_errors)
            activated = service.activate(
                successor.revision_id, expected_version=successor.version, actor="admin"
            )
            self.assertEqual("active", activated.status.value)
            original = repository.get_revision(active.revision_id)
            self.assertEqual(digest, original.digest)
            self.assertIn(
                "remoteExecution",
                original.document["api"],
                "the accepted historical revision keeps its original bytes",
            )
