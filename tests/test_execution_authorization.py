from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.configuration_integrity import canonical_document_digest
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
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
    def test_cli_does_not_register_ticket_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"] = {"databasePath": str(Path(directory, "runtime.sqlite3"))}
            config = Path(directory, "config.json")
            config.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(SystemExit) as raised:
                final_main(
                    ["--config", str(config), "execution-authorizations", "list"],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(2, raised.exception.code)

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

    def test_direct_cli_analysis_and_execute_remain_the_current_entrances(self):
        # The direct CLI journeys are exercised below; this assertion keeps the
        # retained current entrance visible in the retirement suite.
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        self.assertNotIn("remoteExecution", document["api"])


class RetainedDirectCliTests(unittest.TestCase):
    def test_cli_organize_execute_admits_and_executes_one_kernel_task(self) -> None:
        """Task47.3: the direct CLI execute entrance is one shared Task run.

        The admitted Task — not a parallel generic coordinator row — carries the
        run: the shared kernel admission, the claim-fenced publication, the
        settled aggregate and the honest exit code.  No Job row exists and the
        analysis-only command keeps its own zero-mutation shape.
        """

        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            source_root.mkdir()
            target_root.mkdir()
            (source_root / "Movies").mkdir()
            media = source_root / "Movies" / "One.2001.mkv"
            media.write_bytes(b"m" * 512)
            document["persistence"] = {"databasePath": str(root / "runtime.sqlite3")}
            document["historyPath"] = str(root / "history.jsonl")
            document["storages"] = [
                {
                    "id": "source",
                    "name": "Source",
                    "type": "local",
                    "rootPath": str(source_root),
                    "enabled": True,
                },
                {
                    "id": "target",
                    "name": "Target",
                    "type": "local",
                    "rootPath": str(target_root),
                    "enabled": True,
                },
            ]
            document["resourceLibraries"] = [
                {
                    "id": "library",
                    "name": "Library",
                    "storageId": "source",
                    "storagePath": "",
                    "enabled": True,
                    "extensions": ["mkv", "mp4"],
                }
            ]
            document["mediaLibraries"] = [
                {
                    "id": "movies",
                    "name": "Movies",
                    "storageId": "target",
                    "rootPath": "Organized/Movies",
                    "enabled": True,
                },
                {
                    "id": "tv",
                    "name": "TV",
                    "storageId": "target",
                    "rootPath": "Organized/TV",
                    "enabled": True,
                },
            ]
            document["automationTaskDefinitions"] = []
            document["recognitionRules"] = [
                {
                    "id": "movies",
                    "name": "Movies",
                    "priority": 100,
                    "score": 100,
                    "stopOnMatch": True,
                    "condition": {
                        "field": "extension",
                        "operator": "in",
                        "value": ["mkv", "mp4"],
                    },
                    "outputRecognitionType": "A",
                }
            ]
            config = root / "config.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            activate_managed(document)
            from mediaflow.application.metadata import MetadataProviderRegistry
            from mediaflow.application.strategy_test import SyntheticMetadataProvider
            from mediaflow.domain.metadata import MediaCandidate, MediaType

            provider = MetadataProviderRegistry(
                (
                    SyntheticMetadataProvider(
                        (MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),)
                    ),
                )
            )
            # A real older queued Run once already holds the shared queue.  The
            # direct CLI must claim its *own* newly admitted Task atomically, not
            # take the oldest Task and then reject its identity.
            from mediaflow.application.task_scheduling import (
                TaskSchedulingService,
                build_scheduled_task_admission,
            )
            from mediaflow.domain.task_scheduling import TaskTrigger

            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                scheduling = TaskSchedulingService(repository, capacity=100)
                older_task, older_state = build_scheduled_task_admission(
                    "organize",
                    execute_authorized=True,
                    trigger=TaskTrigger.RUN_ONCE,
                    principal="automation-scheduler",
                    request_id="pre-existing-run-once",
                    now=datetime.now(UTC),
                )
                repository.admit_scheduled_task(
                    older_task, older_state, capacity=scheduling.capacity
                )

            output, errors = io.StringIO(), io.StringIO()
            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                return_value=provider,
            ):
                code = final_main(
                    ["--config", str(config), "organize", "--execute", "--limit", "5"],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(0, code, errors.getvalue())
            self.assertIn("Task ID:", output.getvalue())
            self.assertFalse(media.exists())
            organized = list((target_root / "Organized" / "Movies").rglob("*.mkv"))
            self.assertEqual(1, len(organized), organized)
            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                self.assertEqual(2, len(repository.list_tasks()))
                tasks = repository.list_tasks()
                self.assertEqual(2, len(tasks), tasks)
                task = next(value for value in tasks if value.task_id != older_task.task_id)
                self.assertEqual("organize", task.command)
                self.assertTrue(task.execute_authorized)
                self.assertEqual("completed", task.status.value)
                state = repository.get_task_scheduling(task.task_id)
                self.assertIsNotNone(state)
                self.assertEqual(state.queue_state.value, "settled")
                self.assertEqual(state.admission_trigger.value, "manual")
                (item,) = repository.list_items(task.task_id)
                self.assertEqual("success", item.status.value)
                self.assertEqual(1, len(repository.list_results(task.task_id)))

                # The older Run once is untouched: still queued, never claimed by
                # the CLI, no fabricated processing or result, and no second
                # owner left behind in the shared queue.
                older = repository.get_task(older_task.task_id)
                self.assertEqual("pending", older.status.value)
                older_queue = repository.get_task_scheduling(older_task.task_id)
                self.assertEqual("queued", older_queue.queue_state.value)
                self.assertIsNone(older_queue.claim_token)
                self.assertIsNone(older_queue.claim_worker_id)
                self.assertEqual((), repository.list_items(older_task.task_id))
                self.assertEqual((), repository.list_results(older_task.task_id))
                # The transient CLI Worker identity was stopped with the run.
                workers = repository.list_workers()
                self.assertTrue(workers, workers)
                self.assertTrue(
                    all(worker.status.value == "stopped" for worker in workers), workers
                )

    def test_direct_cli_never_steals_a_task_already_owned_by_a_resident_worker(self) -> None:
        from mediaflow.application.task_scheduling import (
            TaskSchedulingService,
            build_scheduled_task_admission,
        )
        from mediaflow.domain.task_scheduling import TaskTrigger, TaskWorkerRejected
        from mediaflow.final_cli import _drive_direct_organize_claim

        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                now = datetime.now(UTC)
                scheduling = TaskSchedulingService(repository, capacity=2)
                task, state = build_scheduled_task_admission(
                    "organize",
                    execute_authorized=True,
                    trigger=TaskTrigger.MANUAL,
                    principal="cli",
                    now=now,
                )
                repository.admit_scheduled_task(task, state, capacity=scheduling.capacity)
                repository.register_worker(
                    "resident-worker",
                    "resident",
                    5.0,
                    ("organize",),
                    None,
                    None,
                    SCHEMA_VERSION,
                    now,
                )
                owned = scheduling.claim(
                    task.task_id,
                    worker_id="resident-worker",
                    now=now + timedelta(seconds=1),
                    lease_seconds=900,
                )
                self.assertIsNotNone(owned)
                with self.assertRaisesRegex(TaskWorkerRejected, "already owned"):
                    _drive_direct_organize_claim(repository, scheduling, task)
                # This process took nothing and left no live temporary Worker.
                current = repository.get_task_scheduling(task.task_id)
                self.assertEqual("resident-worker", current.claim_worker_id)
                self.assertEqual(owned.claim_token, current.claim_token)
                temporary = [
                    worker
                    for worker in repository.list_workers()
                    if worker.worker_id.startswith("direct-organize-")
                ]
                self.assertTrue(temporary, temporary)
                self.assertTrue(all(worker.status.value == "stopped" for worker in temporary))

    def test_cli_organize_without_execute_keeps_analysis_only_shape(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            source_root.mkdir()
            target_root.mkdir()
            (source_root / "Movies").mkdir()
            media = source_root / "Movies" / "One.2001.mkv"
            media.write_bytes(b"m" * 512)
            document["persistence"] = {"databasePath": str(root / "runtime.sqlite3")}
            document["historyPath"] = str(root / "history.jsonl")
            document["storages"] = [
                {
                    "id": "source",
                    "name": "Source",
                    "type": "local",
                    "rootPath": str(source_root),
                    "enabled": True,
                },
                {
                    "id": "target",
                    "name": "Target",
                    "type": "local",
                    "rootPath": str(target_root),
                    "enabled": True,
                },
            ]
            document["resourceLibraries"] = [
                {
                    "id": "library",
                    "name": "Library",
                    "storageId": "source",
                    "storagePath": "",
                    "enabled": True,
                    "extensions": ["mkv", "mp4"],
                }
            ]
            document["mediaLibraries"] = [
                {
                    "id": "movies",
                    "name": "Movies",
                    "storageId": "target",
                    "rootPath": "Organized/Movies",
                    "enabled": True,
                },
                {
                    "id": "tv",
                    "name": "TV",
                    "storageId": "target",
                    "rootPath": "Organized/TV",
                    "enabled": True,
                },
            ]
            document["automationTaskDefinitions"] = []
            document["recognitionRules"] = [
                {
                    "id": "movies",
                    "name": "Movies",
                    "priority": 100,
                    "score": 100,
                    "stopOnMatch": True,
                    "condition": {
                        "field": "extension",
                        "operator": "in",
                        "value": ["mkv", "mp4"],
                    },
                    "outputRecognitionType": "A",
                }
            ]
            config = root / "config.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            activate_managed(document)
            from mediaflow.application.metadata import MetadataProviderRegistry
            from mediaflow.application.strategy_test import SyntheticMetadataProvider
            from mediaflow.domain.metadata import MediaCandidate, MediaType

            provider = MetadataProviderRegistry(
                (
                    SyntheticMetadataProvider(
                        (MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),)
                    ),
                )
            )
            output, errors = io.StringIO(), io.StringIO()
            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                return_value=provider,
            ):
                code = final_main(
                    ["--config", str(config), "organize", "--limit", "5"],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(0, code, errors.getvalue())
            self.assertTrue(media.exists())
            self.assertEqual([], list((target_root / "Organized").rglob("*.mkv")))
            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                self.assertEqual(1, len(repository.list_tasks()))
                tasks = repository.list_tasks()
                self.assertEqual(1, len(tasks), tasks)
                task = tasks[0]
                self.assertFalse(task.execute_authorized)
                # The analysis-only run stays outside the organizing execution
                # queue: no kernel scheduling row claims it.
                self.assertIsNone(repository.get_task_scheduling(task.task_id))
                (item,) = repository.list_items(task.task_id)
                self.assertEqual("dry_run", item.status.value)


if __name__ == "__main__":
    unittest.main()


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
