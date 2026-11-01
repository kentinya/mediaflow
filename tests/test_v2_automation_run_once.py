"""Task 43.2 — definition-bound Run once over the real V2 Automation API.

These tests drive the real ``MediaFlowApi`` against a real managed configuration
runtime, real Local Storage and the real application services.  They prove the
operator-facing journey the Contract promises:

* ``运行一次`` is an explicit action on a *published* definition and sends no
  file selection: the backend derives the whole scope from the definition;
* a disabled published schedule is runnable once, and the run never enables the
  schedule, grants/revives/consumes unattended authority or advances due state;
* the prompt durable admission is read back by its own identity across reload;
* a removed mode, an over-bound ceiling and a Draft-only definition are refused
  with a bounded next action instead of being converted or truncated;
* reads and denials create no work and no Storage mutation.
"""

from __future__ import annotations

import copy
import io
import json
import os
import re
import tempfile
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediaflow.application.automation_run_once import AutomationRunOnceService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.media_discovery import MediaDiscoveryService
from mediaflow.domain.media_discovery import DiscoveryBudgets
from mediaflow.domain.security import (
    ROLE_PERMISSIONS,
    ApiPermission,
    ApiRole,
    ResolvedApiPrincipal,
)
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

ADMIN_TOKEN = "automation-run-once-admin"
OPERATOR_TOKEN = "automation-run-once-operator"
VIEWER_TOKEN = "automation-run-once-viewer"


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


class _RecordingStorage:
    def __init__(self, storage) -> None:
        self._storage = storage
        self.reads: list[tuple[str, str]] = []
        self.mutations: list[tuple[str, str]] = []
        self._unreadable: set[str] = set()

    def fail_listing(self, prefix: str) -> None:
        """Make one subtree unreadable after admission."""

        self._unreadable.add(prefix.strip("/"))

    @property
    def storage_id(self) -> str:
        return self._storage.storage_id

    @property
    def name(self) -> str:
        return self._storage.name

    @property
    def read_only(self) -> bool:
        return self._storage.read_only

    @property
    def capabilities(self):
        return self._storage.capabilities

    def list(self, path: str):
        self.reads.append(("list", path))
        if any(path == prefix or path.startswith(prefix + "/") for prefix in self._unreadable):
            raise StorageError(
                StorageErrorCode.PERMISSION_DENIED, "list", path, "unreadable fixture subtree"
            )
        return self._storage.list(path)

    def list_page(self, path: str, *, limit: int, cursor: str | None = None):
        self.reads.append(("list_page", path))
        for prefix in self._unreadable:
            if path == prefix or path.startswith(prefix + "/"):
                raise StorageError(
                    StorageErrorCode.PERMISSION_DENIED,
                    "list",
                    path,
                    "synthetic permission denial for one subtree",
                )
        return self._storage.list_page(path, limit=limit, cursor=cursor)

    def stat(self, path: str):
        self.reads.append(("stat", path))
        return self._storage.stat(path)

    def exists(self, path: str) -> bool:
        self.reads.append(("exists", path))
        return self._storage.exists(path)

    def read(self, path: str):
        return self._storage.read(path)

    def write(self, path: str, data, *, overwrite: bool = False) -> None:
        self.mutations.append(("write", path))
        return self._storage.write(path, data, overwrite=overwrite)

    def create_directory(self, path: str) -> None:
        self.mutations.append(("create_directory", path))
        return self._storage.create_directory(path)

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutations.append(("move", source))
        return self._storage.move(source, target, overwrite=overwrite)

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutations.append(("copy", source))
        return self._storage.copy(source, target, overwrite=overwrite)

    def delete(self, path: str) -> None:
        self.mutations.append(("delete", path))
        return self._storage.delete(path)

    def hard_link(self, source: str, target: str) -> None:
        self.mutations.append(("hard_link", source))
        return self._storage.hard_link(source, target)

    def soft_link(self, source: str, target: str) -> None:
        self.mutations.append(("soft_link", source))
        return self._storage.soft_link(source, target)


def _task_run_view(task, captured):
    """Bounded view of one Task-admitted execution for the existing assertions."""

    evidence = captured.get("evidence")
    return SimpleNamespace(
        task_id=task.task_id,
        status=task.status,
        error=task.error,
        failure_category=evidence.category if evidence is not None else None,
        failure_durable_state=evidence.durable_state if evidence is not None else None,
        failure_side_effects=evidence.side_effects if evidence is not None else None,
        failure_retry_safe=evidence.retry_safe if evidence is not None else None,
        failure_next_action=evidence.next_action if evidence is not None else None,
        cancelled=bool(captured.get("cancelled")),
    )


class RunOnceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source_root = self.root / "source"
        self.source_root.mkdir(parents=True)
        self.target_root = self.root / "target"
        self.target_root.mkdir(parents=True)
        self.clock = _Clock()
        self.environment = patch.dict(
            os.environ,
            {"TMDB_ACCESS_TOKEN": "sentinel-tmdb", "OPENLIST_TOKEN": "sentinel-openlist"},
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def media(self, relative: str) -> Path:
        path = self.source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"m" * 512)
        stamp = (self.clock.now - timedelta(hours=1)).timestamp()
        os.utime(path, (stamp, stamp))
        return path

    def document(self, *, definitions=None, item_limit: int = 10, source_scope=None) -> dict:
        value = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        value["persistence"]["databasePath"] = str(self.root / "runtime.sqlite3")
        value["historyPath"] = str(self.root / "history.jsonl")
        value["storages"] = [
            {
                "id": "source",
                "name": "Source",
                "type": "local",
                "rootPath": str(self.source_root),
                "enabled": True,
            },
            {
                "id": "target",
                "name": "Target",
                "type": "local",
                "rootPath": str(self.target_root),
                "enabled": True,
            },
        ]
        value["resourceLibraries"] = [
            {
                "id": "library",
                "name": "Library",
                "storageId": "source",
                "storagePath": "",
                "enabled": True,
                "extensions": ["mkv", "mp4"],
            }
        ]
        value["mediaLibraries"] = [
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
        if definitions is None:
            definition = {
                "id": "nightly",
                "name": "Nightly",
                "resourceLibraryId": "library",
                "mode": "automatic-organization",
                "intervalSeconds": 3600,
                "itemLimit": item_limit,
                "enabled": False,
            }
            if source_scope is not None:
                definition["sourceScope"] = source_scope
            definitions = [definition]
        value["api"]["principals"] = [
            {"id": "admin", "tokenEnv": "MEDIAFLOW_API_TOKEN", "roles": ["admin"], "enabled": True}
        ]
        value["recognitionRules"] = [
            {
                "id": "movies",
                "name": "Movies",
                "priority": 100,
                "score": 100,
                "stopOnMatch": True,
                "condition": {"field": "extension", "operator": "in", "value": ["mkv", "mp4"]},
                "outputRecognitionType": "A",
            }
        ]
        value["automationTaskDefinitions"] = definitions
        if hasattr(self, "stability"):
            value["resourceLibraries"][0]["stability"] = self.stability
        if hasattr(self, "change_document"):
            self.change_document(value)
        return value

    @contextmanager
    def journey(self, *, definitions=None, item_limit: int = 10, source_scope=None):
        document = self.document(
            definitions=definitions, item_limit=item_limit, source_scope=source_scope
        )
        source = _RecordingStorage(LocalStorage("source", self.source_root))
        target = _RecordingStorage(LocalStorage("target", self.target_root))
        storages = {"source": source, "target": target}
        with (
            SQLiteConfigurationRepository(self.root / "configuration.sqlite3") as configuration,
            SQLiteTaskRepository(str(self.root / "runtime.sqlite3")) as repository,
        ):
            managed = ManagedConfigurationService(
                configuration,
                bootstrap_database_path=str(self.root / "runtime.sqlite3"),
            )
            # The production Scheduler reads the publication principal of an
            # Enabled definition and re-checks its current permission.  Bind
            # the fixture's publication to the configured admin principal so a
            # scheduled occurrence can reach its real preflight/execution path.
            draft = managed.import_draft(document, actor="admin")
            validated = managed.validate(draft.revision_id, actor="admin")
            if validated.status.value != "validated":
                raise AssertionError(validated.validation_errors)
            revision = managed.activate(
                validated.revision_id, expected_version=validated.version, actor="admin"
            )
            from mediaflow.infrastructure.runtime_configuration import (
                load_managed_runtime_configuration,
                with_managed_snapshot,
            )

            runtime = with_managed_snapshot(
                load_managed_runtime_configuration(
                    revision.document, bootstrap_database_path=managed.bootstrap_database_path
                ),
                snapshot_id=revision.revision_id,
                digest=revision.digest,
                version=revision.version,
            )
            intents = ManualOrganizeIntentService(
                repository,
                managed,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storage_factory=lambda value, ids: dict(storages),
            )
            previews = ManualOrganizePreviewService(
                repository,
                intents,
                configuration=runtime,
                storages=dict(storages),
                clock=self.clock,
            )
            discovery = MediaDiscoveryService(
                repository,
                intents,
                configuration=runtime,
                preview_service=previews,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storages=dict(storages),
                clock=self.clock,
                budgets=DiscoveryBudgets(),
            )
            run_once = AutomationRunOnceService(discovery, previews, clock=self.clock)
            api = MediaFlowApi(
                repository,
                None,
                principals=(
                    ResolvedApiPrincipal("admin", ADMIN_TOKEN, frozenset(ApiPermission)),
                    ResolvedApiPrincipal(
                        "operator", OPERATOR_TOKEN, ROLE_PERMISSIONS[ApiRole.OPERATOR]
                    ),
                    ResolvedApiPrincipal("viewer", VIEWER_TOKEN, frozenset({ApiPermission.READ})),
                ),
                configuration_service=managed,
                bootstrap_document=document,
                manual_intent_service=intents,
                manual_preview_service=previews,
                media_discovery_service=discovery,
                automation_run_once_service=run_once,
                storage_adapters=dict(storages),
            )
            yield SimpleNamespace(
                api=api,
                repository=repository,
                managed=managed,
                runtime=runtime,
                discovery=discovery,
                run_once=run_once,
                intents=intents,
                previews=previews,
                clock=self.clock,
                source=source,
                target=target,
                revision=revision,
            )

    def request(self, value, method, path, body=None, *, token=ADMIN_TOKEN):
        payload = b"" if body is None else json.dumps(body).encode("utf-8")
        statuses: list[str] = []
        path_info, _, query_string = path.partition("?")
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path_info,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(payload)),
            "wsgi.input": io.BytesIO(payload),
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        result = b"".join(value.api(environ, lambda status, _headers: statuses.append(status)))
        return int(statuses[0].split()[0]), (json.loads(result) if result else {})

    def drive(self, value, *, steps: int = 12):
        result = None
        for index in range(steps):
            result = value.discovery.claim_and_run(
                worker_id=f"worker-{index}", claim_token=f"token-{index}"
            )
            if result is None:
                raise AssertionError("Run-once discovery was not claimable")
            if result.terminal:
                break
        else:
            raise AssertionError("Run-once discovery did not settle")
        return result

    def admit(self, value, request_id="request-1", **overrides):
        active = value.managed.active()
        from mediaflow.domain.automation import AutomationTaskDefinition

        definition = AutomationTaskDefinition.from_document(
            active.document["automationTaskDefinitions"][0]
        )
        body = {
            "admissionRequestId": request_id,
            "expectedRevisionId": active.revision_id,
            "expectedRevisionVersion": active.revision_sequence or active.version,
            "expectedRevisionDigest": active.digest,
            "expectedDefinitionFingerprint": definition.definition_fingerprint,
            **overrides,
        }
        return self.request(
            value, "POST", "/api/v1/operations/automation/task-definitions/nightly/run-once", body
        )

    @staticmethod
    def scheduled(value):
        """Build the production Scheduler over the fixture's Active snapshot."""

        from mediaflow.application.automation import IntervalScheduler
        from mediaflow.domain.automation import (
            AutomationTaskDefinition,
            SchedulerConfigurationSnapshot,
        )

        active = value.managed.active()
        definitions = tuple(
            AutomationTaskDefinition.from_document(item)
            for item in active.document["automationTaskDefinitions"]
        )
        resources = tuple(
            item["id"]
            for item in active.document["resourceLibraries"]
            if isinstance(item, dict) and item.get("id")
        )
        snapshot = SchedulerConfigurationSnapshot(
            active.revision_id,
            active.digest,
            (),
            100,
            definitions,
            active.version,
            resources,
            resources,
        )
        return IntervalScheduler(
            value.repository,
            (),
            configuration_snapshot_resolver=lambda: snapshot,
        )

    @staticmethod
    def stable_records_document(page: dict, *, revision_id: str) -> dict:
        """Replace only volatile identities/times in a real records response.

        The shared browser fixture is captured from this exact API document;
        the substitution lets the test prove the real response shape without
        pinning generated UUIDs or wall-clock completion times.
        """

        document = copy.deepcopy(page)
        identities: dict[str, str] = {revision_id: "revision-active"}
        for record in document["items"]:
            definition_id = record["historyContext"]["definitionId"]
            for field in ("recordId", "run_id", "job_id"):
                value = record.get(field)
                if isinstance(value, str) and value:
                    identities[value] = f"record-{definition_id}"
            task_id = record.get("task_id")
            if isinstance(task_id, str) and task_id:
                identities[task_id] = f"task-{definition_id}"
            worker_id = record.get("worker_id")
            if isinstance(worker_id, str) and worker_id:
                identities[worker_id] = "worker-harness"
        text = json.dumps(document, sort_keys=True)
        for identity, stable in sorted(identities.items(), key=lambda item: -len(item[0])):
            text = text.replace(identity, stable)
        text = re.sub(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
            "2026-01-01T12:00:00+00:00",
            text,
        )
        document = json.loads(text)
        document["items"].sort(key=lambda item: item["historyContext"]["definitionId"])
        return document

    def _run_once_service(self, value, provider_factory):
        from mediaflow.application.automation_definition_execution import (
            DefinitionScopedExecutionService,
        )
        from mediaflow.application.strategy_test import strategy_runner_from_configuration
        from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository

        return DefinitionScopedExecutionService(
            value.repository,
            value.runtime,
            storage_factory=lambda **kwargs: {"source": value.source, "target": value.target},
            provider_factory=provider_factory,
            strategy_factory=strategy_runner_from_configuration,
            history_factory=JsonLinesOperationHistoryRepository,
            unattended_grant_service=value.api._unattended_grants,
        )

    def execute(self, value):
        """Run the next admitted Run once through its real durable identity.

        A Task-admitted run is advanced by the resident Task engine with the
        same definition-scoped service a Worker uses; a historical Job-backed
        run keeps its legacy consumer.
        """

        from mediaflow.application.automation import (
            AutomationCancelled,
            AutomationWorkflowFailed,
        )
        from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
        from mediaflow.application.metadata import MetadataProviderRegistry
        from mediaflow.application.strategy_test import SyntheticMetadataProvider
        from mediaflow.application.task_scheduling import TaskSchedulingService
        from mediaflow.domain.metadata import MediaCandidate, MediaType
        from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

        provider = SyntheticMetadataProvider(
            (
                MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
                MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
            )
        )
        provider_registry = MetadataProviderRegistry((provider,))
        service = self._run_once_service(value, lambda ids: provider_registry)
        scheduling = TaskSchedulingService(value.repository, capacity=100)
        worker_id = f"run-once-test-{len(value.repository.list_tasks())}"
        value.repository.register_worker(
            worker_id,
            worker_id,
            5.0,
            ("organize",),
            None,
            None,
            SCHEMA_VERSION,
            value.clock.now,
        )
        captured = {}

        def runner(task, claim, clock=None, heartbeat=None):
            state = scheduling.state(task.task_id)
            if value.repository.list_items(task.task_id):
                # A continuation pass: the Task's own saved decision re-entered
                # its zero-mutation analysis through the same kernel claim.
                from mediaflow.application.automatic_task_continuation import (
                    AutomaticTaskContinuationService,
                )
                from mediaflow.application.manual_organize import (
                    ManualOrganizeIntentService,
                )
                from mediaflow.application.manual_organize_preview import (
                    ManualOrganizePreviewService,
                )
                from mediaflow.application.processing_checkpoint import (
                    ProcessingCheckpointService,
                )

                intents = ManualOrganizeIntentService(
                    value.repository,
                    value.managed,
                    runtime_resolver=lambda snapshot_id, digest: value.runtime,
                    storage_factory=lambda runtime, ids: dict(
                        {"source": value.source, "target": value.target}
                    ),
                )
                previews = ManualOrganizePreviewService(
                    value.repository,
                    intents,
                    configuration_service=value.managed,
                    storages={"source": value.source, "target": value.target},
                    providers=provider_registry,
                    clock=value.clock,
                )
                continuation = AutomaticTaskContinuationService(
                    value.repository,
                    intent_service=intents,
                    preview_service=previews,
                    checkpoint_service=ProcessingCheckpointService(
                        value.repository,
                        snapshot_validator=value.managed.validate_runtime_snapshot,
                    ),
                )
                continuation.run_pass(task, scheduling, claim, clock=clock, heartbeat=heartbeat)
                return
            try:
                service.run(
                    task,
                    scheduling,
                    claim,
                    run_once=state.admission_trigger.value == "run_once",
                    cancellation_check=lambda: False,
                    clock=clock,
                    heartbeat=heartbeat,
                )
            except AutomationWorkflowFailed as error:
                captured["evidence"] = error.evidence
                raise
            except AutomationCancelled:
                captured["cancelled"] = True
                raise

        worker = ManualTaskEngineWorker(
            value.repository,
            scheduling,
            None,
            None,
            worker_id=worker_id,
            clock=value.clock,
            automatic_runner=runner,
        )
        task = worker.run_next()
        if task is None:
            return None
        return _task_run_view(task, captured)

    def test_scheduled_prestart_failure_is_a_complete_read_only_record(self):
        # A healthy empty scope completes as real no-work, while a missing
        # source scope fails the Worker preflight before any formal Task is
        # created.  Both are produced by the production Scheduler and Worker.
        (self.source_root / "Movies").mkdir()
        definitions = [
            {
                "id": "healthy",
                "name": "Healthy automation",
                "resourceLibraryId": "library",
                "mode": "automatic-organization",
                "intervalSeconds": 3600,
                "itemLimit": 10,
                "enabled": True,
                "sourceScope": "Movies",
            },
            {
                "id": "missing",
                "name": "Missing automation",
                "resourceLibraryId": "library",
                "mode": "automatic-organization",
                "intervalSeconds": 3600,
                "itemLimit": 10,
                "enabled": True,
                "sourceScope": "DoesNotExist",
            },
        ]
        with self.journey(definitions=definitions) as value:
            revision = value.managed.active()
            emitted = self.scheduled(value).tick(self.clock.now)
            self.assertEqual(
                {
                    value.repository.get_run_display_context(task.task_id).origin_definition_id
                    for task in emitted
                },
                {"healthy", "missing"},
            )
            for _ in emitted:
                self.assertIsNotNone(self.execute(value))

            tasks = {
                value.repository.get_run_display_context(task.task_id).origin_definition_id: task
                for task in (value.repository.get_task(task.task_id) for task in emitted)
            }
            self.assertEqual("failed", tasks["missing"].status.value)
            self.assertEqual("completed", tasks["healthy"].status.value)

            def counts():
                return (
                    len(value.repository.list_tasks()),
                    len(()),
                    len(value.repository.list_unattended_execution_grants()),
                    len(value.discovery.list()),
                    value.managed.active().revision_id,
                )

            before_refresh = counts()
            status, page = self.request(
                value, "GET", "/api/v1/operations/automation/records?limit=20"
            )
            self.assertEqual(200, status, page)
            self.assertEqual(2, page["total"])
            records = {record["historyContext"]["definitionId"]: record for record in page["items"]}
            failure = records["missing"]
            self.assertEqual("failed", failure["status"])
            self.assertIsNotNone(failure["task_id"])
            self.assertFalse(failure["result"]["organized"])
            self.assertFalse(failure["result"]["noWork"])
            stage = failure["failureStage"]
            self.assertEqual("linked_task_stage", stage["stage"])
            self.assertEqual([], stage["items"])
            self.assertEqual(
                {"none": 0, "known": 0, "uncertain": 0, "partial": 0},
                stage["effects"],
            )

            healthy = records["healthy"]
            self.assertEqual("completed", healthy["status"])
            self.assertTrue(healthy["result"]["noWork"])
            self.assertIsNotNone(healthy["task_id"])
            self.assertIsNone(healthy["failureStage"])
            self.assertEqual("task_center", healthy["handoff"]["ownership"])

            # A refresh is the same bounded read: it creates no Task/Job/grant/
            # discovery and never re-executes the settled failure.
            status, refreshed = self.request(
                value, "GET", "/api/v1/operations/automation/records?limit=20"
            )
            self.assertEqual(200, status, refreshed)
            self.assertEqual(page["total"], refreshed["total"])
            self.assertEqual(before_refresh, counts())
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual(
                self.stable_records_document(page, revision_id=revision.revision_id),
                self.stable_records_document(refreshed, revision_id=revision.revision_id),
            )

            fixture_path = (
                Path(__file__).resolve().parents[1]
                / "web"
                / "tests"
                / "fixtures"
                / "automation-records-prestart.json"
            )
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            self.assertEqual(
                self.stable_records_document(page, revision_id=revision.revision_id),
                fixture,
            )

    def test_disabled_definition_admits_task_before_worker_and_executes_without_confirmation(self):
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            before = value.managed.active()
            status, run = self.admit(value)
            self.assertEqual(202, status, run)
            self.assertEqual("organizing", run["executionKind"])
            self.assertEqual("pending", value.repository.get_task(run["taskId"]).status.value)
            self.assertEqual([], value.source.mutations)
            finished = self.execute(value)
            self.assertEqual("completed", finished.status.value)
            task = value.repository.get_task(run["taskId"])
            self.assertEqual("completed", task.status.value)
            self.assertEqual(1, task.completed_items)
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            self.assertEqual(before.revision_id, value.managed.active().revision_id)
            self.assertIsNone(value.repository.get_automation_definition_due_state("nightly"))
            self.assertEqual((), value.repository.list_unattended_execution_grants())
            self.assertEqual((), value.discovery.list())
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual(0, len(()))
            # The first automatic stage ended at the terminal settlement, so its
            # write-once evidence records the completed outcome and real window
            # the Automation record publishes.
            window = value.repository.operations_runs_window(
                limit=20, automation_admissions=True, record_evidence=True
            )
            (item,) = window.page
            evidence = item.automation_record_evidence
            self.assertEqual(task.task_id, item.task_id)
            self.assertEqual("completed", evidence["record_outcome"], evidence)
            self.assertEqual(1, evidence["success_count"], evidence)
            self.assertEqual(0, evidence["waiting_count"], evidence)
            self.assertIsNotNone(evidence["record_started_at"], evidence)
            self.assertIsNotNone(evidence["record_finished_at"], evidence)
            status, runs = self.request(
                value, "GET", "/api/v1/operations/runs?view=all&trigger=manual"
            )
            self.assertEqual(200, status, runs)
            linked = [v for v in runs["items"] if v["task_id"] == task.task_id]
            self.assertEqual(1, len(linked))
            self.assertEqual("manual", linked[0]["trigger"])
            self.assertEqual("nightly", linked[0]["definition_id"])

    def test_duplicate_and_exact_lost_response_reconcile_without_replay(self):
        self.media("One.2001.mkv")
        with self.journey() as value:
            status, first = self.admit(value)
            self.assertEqual(202, status, first)
            status, second = self.admit(value)
            self.assertEqual(first["taskId"], second["taskId"])
            self.execute(value)
            status, read = self.request(
                value,
                "GET",
                "/api/v1/operations/automation/task-definitions/nightly/run-once?admissionRequestId=request-1",
            )
            self.assertEqual(200, status, read)
            self.assertEqual(first["taskId"], read["taskId"])
            self.assertEqual("completed", read["status"])
            self.assertIsNone(self.execute(value))
            self.assertEqual(1, len(value.repository.list_tasks()))

    def test_empty_is_no_work_but_unreadable_and_overflow_never_execute_prefix(self):
        with self.journey() as value:
            status, run = self.admit(value)
            self.assertEqual(202, status, run)
            self.execute(value)
            self.assertEqual(
                "no_work", value.run_once.document(value.run_once.get(run["taskId"]))["phase"]
            )
            # A healthy empty run freezes its own completed no-work stage.
            window = value.repository.operations_runs_window(
                limit=20, automation_admissions=True, record_evidence=True
            )
            (item,) = [entry for entry in window.page if entry.task_id == run["taskId"]]
            evidence = item.automation_record_evidence
            self.assertEqual("completed", evidence["record_outcome"], evidence)
            self.assertEqual(0, evidence["item_count"], evidence)
            self.assertEqual(0, evidence["waiting_count"], evidence)
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey(item_limit=1) as value:
            self.admit(value, "overflow")
            result = self.execute(value)
            self.assertEqual("failed", result.status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
        with self.journey() as value:
            value.source.fail_listing("Movies")
            self.admit(value, "unreadable")
            result = self.execute(value)
            self.assertEqual("failed", result.status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            # A failed first automatic stage freezes its own failed outcome;
            # the record never upgrades it to success after the fact.
            window = value.repository.operations_runs_window(
                limit=20, automation_admissions=True, record_evidence=True
            )
            (item,) = [entry for entry in window.page if entry.task_id == result.task_id]
            evidence = item.automation_record_evidence
            self.assertEqual("failed", evidence["record_outcome"], evidence)
            self.assertEqual(0, evidence["success_count"], evidence)
            self.assertIsNotNone(evidence["record_finished_at"], evidence)

    def test_effective_ceiling_is_one_hundred_and_small_scope_completes(self):
        self.media("One.2001.mkv")
        with self.journey(item_limit=150) as value:
            status, run = self.admit(value)
            self.assertEqual(202, status, run)
            self.assertEqual(100, run["effectivePrimaryLimit"])
            result = self.execute(value)
            self.assertEqual("completed", result.status.value)
            self.assertEqual(1, value.repository.get_task(run["taskId"]).completed_items)

    def test_stale_malformed_missing_and_read_only_commands_create_nothing(self):
        with self.journey() as value:
            for body, token in [
                ({"admissionRequestId": "bad", "paths": ["One.mkv"]}, ADMIN_TOKEN),
                ({"admissionRequestId": "denied"}, VIEWER_TOKEN),
            ]:
                status, _ = self.request(
                    value,
                    "POST",
                    "/api/v1/operations/automation/task-definitions/nightly/run-once",
                    body,
                    token=token,
                )
                self.assertIn(status, (400, 403))
            status, _ = self.admit(value, expectedRevisionId="stale")
            self.assertEqual(409, status)
            status, _ = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/missing/run-once",
                {"admissionRequestId": "missing"},
            )
            self.assertEqual(404, status)
            self.assertEqual((), value.repository.list_tasks())
            self.assertEqual((), ())
            self.assertEqual([], value.source.mutations)

    def test_automatic_folder_filtering_keeps_images_and_sidecars_out_of_primaries(self):
        self.media("One.2001.mkv")
        self.media("advert.jpg")
        self.media("One.2001.en.srt")
        with self.journey() as value:
            self.admit(value)
            result = self.execute(value)
            self.assertEqual("completed", result.status.value)
            self.assertEqual(1, len(value.repository.list_items(result.task_id)))
            self.assertTrue((self.source_root / "advert.jpg").exists())
            self.assertTrue((self.source_root / "One.2001.en.srt").exists())

    def test_business_readiness_is_inside_the_admitted_task(self):
        self.media("Unknown.2024.mkv")
        with self.journey() as value:
            self.admit(value)
            result = self.execute(value)
            self.assertEqual("running", result.status.value)
            items = value.repository.list_items(result.task_id)
            self.assertEqual(1, len(items))
            self.assertIn(
                items[0].status.value, ("waiting_metadata", "waiting_metadata_correction")
            )
            self.assertEqual([], value.source.mutations)

    def test_old_analysis_records_remain_analysis_only_on_plain_read(self):
        self.media("One.2001.mkv")
        with self.journey() as value:
            legacy = value.run_once.admit(
                "nightly",
                actor="admin",
                admission_request_id="00000000-0000-4000-8000-000000000001",
            )
            status, read = self.request(
                value, "GET", f"/api/v1/operations/automation/run-once/{legacy.discovery_id}"
            )
            self.assertEqual(200, status)
            self.assertTrue(read["zeroMutation"])
            self.assertNotIn("executionKind", read)
            self.assertEqual((), ())
            self.assertEqual((), value.repository.list_tasks())

    def test_real_positive_size_interval_waits_once_and_reobserves(self):
        import time

        self.stability = {
            "minimumAgeSeconds": 0,
            "modifiedThresholdSeconds": 0,
            "stableSizeDurationSeconds": 1,
        }
        self.media("One.2001.mkv")
        with self.journey() as value:
            self.admit(value)
            start = time.monotonic()
            result = self.execute(value)
            self.assertGreaterEqual(time.monotonic() - start, 1)
            self.assertEqual("completed", value.repository.get_task(result.task_id).status.value)
            self.assertEqual(1, value.repository.get_task(result.task_id).completed_items)

    def test_ready_sibling_avoids_wait_and_unstable_sibling_is_failure_not_attention(self):
        import time

        self.stability = {
            "minimumAgeSeconds": 10,
            "modifiedThresholdSeconds": 20,
            "stableSizeDurationSeconds": 0,
        }
        self.media("One.2001.mkv")
        fresh = self.media("Two.2002.mkv")
        os.utime(fresh, (time.time(), time.time()))
        with self.journey() as value:
            self.admit(value)
            with patch(
                "mediaflow.application.media_organizer.time.sleep",
                side_effect=AssertionError("ready sources must avoid wait"),
            ):
                result = self.execute(value)
            task = value.repository.get_task(result.task_id)
            self.assertEqual("partial_success", task.status.value)
            self.assertEqual((1, 1), (task.completed_items, task.failed_items))
            self.assertTrue(fresh.exists())
            status, page = self.request(value, "GET", "/api/v1/operations/runs?view=attention")
            self.assertEqual(200, status, page)
            self.assertEqual(0, page["total"])

    def test_over_sixty_interval_has_no_wait_and_only_instability_is_failed(self):
        import time

        self.stability = {
            "minimumAgeSeconds": 0,
            "modifiedThresholdSeconds": 70,
            "stableSizeDurationSeconds": 0,
        }
        fresh = self.media("One.2001.mkv")
        os.utime(fresh, (time.time(), time.time()))
        with self.journey() as value:
            self.admit(value)
            with patch(
                "mediaflow.application.media_organizer.time.sleep",
                side_effect=AssertionError("over 60 seconds must not wait"),
            ):
                result = self.execute(value)
            self.assertEqual("failed", value.repository.get_task(result.task_id).status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_source_change_during_single_short_wait_does_not_fake_stability(self):
        import time

        actual_sleep = time.sleep
        self.stability = {
            "minimumAgeSeconds": 0,
            "modifiedThresholdSeconds": 0,
            "stableSizeDurationSeconds": 1,
        }
        source = self.media("One.2001.mkv")
        calls = []

        def change_during_wait(seconds):
            calls.append(seconds)
            source.write_bytes(b"changed while being observed")
            actual_sleep(seconds)

        with self.journey() as value:
            self.admit(value)
            with patch(
                "mediaflow.application.media_organizer.time.sleep", side_effect=change_during_wait
            ):
                result = self.execute(value)
            self.assertEqual(1, len(calls))
            self.assertEqual("failed", value.repository.get_task(result.task_id).status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_concurrent_exact_request_has_one_job_and_one_task(self):
        from concurrent.futures import ThreadPoolExecutor

        with self.journey() as value:
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: self.admit(value), range(2)))
            self.assertTrue(all(status == 202 for status, body in responses), responses)
            self.assertEqual(responses[0][1]["taskId"], responses[1][1]["taskId"])
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual(0, len(()))
            status, listing = self.request(
                value, "GET", "/api/v1/operations/automation/run-once", token=VIEWER_TOKEN
            )
            self.assertEqual(200, status, listing)
            self.assertEqual([], listing["items"])

    def test_queue_capacity_and_failed_insert_do_not_leave_orphan_tasks(self):
        self.change_document = lambda document: document["automation"].update(
            {"maximumActiveJobs": 1}
        )
        with self.journey() as value:
            with patch.object(
                value.repository,
                "_insert_run_display_locked",
                side_effect=RuntimeError("write failed"),
            ):
                status, _ = self.admit(value)
                self.assertEqual(500, status)
            self.assertEqual((), value.repository.list_tasks())
            self.assertEqual((), ())
            status, run = self.admit(value)
            self.assertEqual(202, status, run)
            status, _ = self.admit(value, "second")
            self.assertEqual(409, status)
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual(0, len(()))

    def test_recognition_and_classification_block_inside_real_task_and_center(self):
        # Each case uses a fresh fixture database, not a manually invented Task.
        self.media("One.2001.mkv")
        self.change_document = lambda document: document.update({"recognitionRules": []})
        with self.journey() as value:
            status, admitted = self.admit(value)
            self.assertEqual(202, status, admitted)
            result = self.execute(value)
            (item,) = value.repository.list_items(result.task_id)
            self.assertEqual("waiting_recognition", item.status.value)
            status, page = self.request(value, "GET", "/api/v1/operations/runs?view=recognition")
            self.assertEqual(200, status, page)
            self.assertEqual(1, page["total"])
            self.assertEqual([], value.source.mutations)

    def test_classification_block_inside_real_task(self):
        self.media("One.2001.mkv")

        def no_matching_destination(document):
            document["classificationPolicies"][0]["rules"] = [
                {
                    "id": "tv-only",
                    "priority": 1,
                    "conditions": {"mediaType": ["tv"]},
                    "result": {"mediaLibraryId": "movies", "path": ["TV"]},
                }
            ]

        self.change_document = no_matching_destination
        with self.journey() as value:
            self.admit(value)
            result = self.execute(value)
            (item,) = value.repository.list_items(result.task_id)
            self.assertEqual("waiting_classification", item.status.value)
            status, page = self.request(value, "GET", "/api/v1/operations/runs?view=classification")
            self.assertEqual(200, status, page)
            self.assertEqual(1, page["total"])
            self.assertEqual([], value.source.mutations)

    def test_recognition_decision_continues_analysis_summary_and_execution_on_one_task(self):
        """Task47.3: the automatic Task's saved decision completes its own journey.

        A real Run once admits one Task whose real Worker parks its only source
        at a Recognition review.  The operator saves the decision, the same Task
        re-enters its own zero-mutation analysis through the kernel re-entry
        boundary, the fresh plan summary becomes the item's own confirmable
        preparation, and the explicit confirmation executes the allowed subset
        on the same Task — with zero Jobs, zero analysis mutations and one
        honest Result.
        """

        self.media("One.2001.mkv")
        self.change_document = lambda document: document.update({"recognitionRules": []})
        with self.journey() as value:
            status, admitted = self.admit(value)
            self.assertEqual(202, status, admitted)
            result = self.execute(value)
            task_id = result.task_id
            (item,) = value.repository.list_items(task_id)
            self.assertEqual("waiting_recognition", item.status.value)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual(state.queue_state.value, "waiting_human")
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual((), ())

            status, detail = self.request(
                value, "GET", f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            self.assertEqual("business_problem", detail["recoveryKind"])
            self.assertIsNone(detail["manualRecoveryPreparation"])

            status, decided = self.request(
                value,
                "POST",
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
                {
                    "kind": "recognition",
                    "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
                    "recognitionTypeId": "A",
                },
            )
            self.assertEqual(200, status, decided)

            status, continued = self.request(
                value,
                "POST",
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/continue",
                {"expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"]},
            )
            self.assertEqual(202, status, continued)
            self.assertTrue(continued["nativeAnalysis"]["taskId"], continued)
            self.assertNotIn("discoveryId", continued["nativeAnalysis"])
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual(state.queue_state.value, "queued")
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())
            self.assertEqual((), ())
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            # A duplicate continue while the analysis is queued is a bounded
            # refusal that changes nothing.
            status, repeat = self.request(
                value,
                "POST",
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/continue",
                {"expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"]},
            )
            self.assertEqual(409, status, repeat)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

            result = self.execute(value)
            self.assertIsNotNone(result)
            (item,) = value.repository.list_items(task_id)
            self.assertEqual("waiting_confirm", item.status.value, item)
            self.assertEqual("continuation_planned", item.stage)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual(state.queue_state.value, "waiting_human")
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            status, detail = self.request(
                value, "GET", f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            preparation = detail["manualRecoveryPreparation"]
            self.assertIsNotNone(preparation, detail)
            self.assertEqual("prepared", preparation["status"])
            # The summary belongs to the authenticated operator who continued
            # the analysis, not to the Run once admission principal.  A foreign
            # operator cannot confirm another operator's exact selection.
            self.assertEqual("admin", preparation["actor"])
            self.assertTrue(detail["manualRecoveryAvailable"])
            self.assertTrue(detail["manualRecoveryAnalysisReady"])

            status, preview = self.request(
                value, "GET", f"/api/v1/manual-previews/{preparation['preview_id']}"
            )
            self.assertEqual(200, status, preview)
            ready = [
                entry["itemId"] for entry in preview["items"] if entry["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview)

            status, refused = self.request(
                value,
                "POST",
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                {"itemIds": ready, "confirmation": True},
                token=OPERATOR_TOKEN,
            )
            self.assertEqual(403, status, refused)
            self.assertEqual("preparation_actor_mismatch", refused["error"]["code"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            status, confirmed = self.request(
                value,
                "POST",
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                {"itemIds": ready, "confirmation": True},
            )
            self.assertEqual(202, status, confirmed)
            self.assertEqual(ready, confirmed["selectedItemIds"], confirmed)
            self.assertEqual(task_id, confirmed["taskId"], confirmed)
            self.assertEqual((), ())

            # The confirmed execution runs on the same Task through the resident
            # engine's manual-execution branch.
            from mediaflow.application.manual_organize_execution import (
                ManualOrganizeExecutionService,
            )
            from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
            from mediaflow.application.task_scheduling import TaskSchedulingService
            from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

            scheduling = TaskSchedulingService(value.repository, capacity=100)
            from mediaflow.application.manual_organize_preview import (
                ManualOrganizePreviewService,
            )
            from mediaflow.application.metadata import MetadataProviderRegistry
            from mediaflow.application.strategy_test import SyntheticMetadataProvider
            from mediaflow.domain.metadata import MediaCandidate, MediaType

            provider_registry = MetadataProviderRegistry(
                (
                    SyntheticMetadataProvider(
                        (
                            MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
                            MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
                        )
                    ),
                )
            )
            previews = ManualOrganizePreviewService(
                value.repository,
                value.intents,
                configuration=value.runtime,
                storages={"source": value.source, "target": value.target},
                providers=provider_registry,
                clock=value.clock,
            )
            execution_service = ManualOrganizeExecutionService(
                value.repository,
                previews,
                value.intents,
                configuration=value.runtime,
                storages={"source": value.source, "target": value.target},
                clock=value.clock,
            )
            worker_id = f"continuation-test-{len(value.repository.list_tasks())}"
            value.repository.register_worker(
                worker_id,
                worker_id,
                5.0,
                ("organize",),
                None,
                None,
                SCHEMA_VERSION,
                value.clock.now,
            )
            worker = ManualTaskEngineWorker(
                value.repository,
                scheduling,
                None,
                execution_service,
                worker_id=worker_id,
                clock=value.clock,
            )
            settled = worker.run_next()
            self.assertIsNotNone(settled)
            self.assertEqual("completed", settled.status.value, settled.error)
            self.assertEqual((), ())
            self.assertFalse((self.source_root / "One.2001.mkv").exists())
            organized = list((self.target_root / "Organized" / "Movies").rglob("*.mkv"))
            self.assertEqual(1, len(organized), organized)
            results = value.repository.list_results(task_id)
            self.assertEqual(1, len(results), results)
            self.assertEqual("SUCCESS", results[0].status)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual(state.queue_state.value, "settled")
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())

            # The original execution facts survive a reload; the confirmed
            # summary reads back as confirmed with its linked execution.
            status, detail = self.request(
                value, "GET", f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            confirmed_summary = detail["manualRecoveryPreparation"]
            self.assertIsNotNone(confirmed_summary, detail)
            self.assertEqual("confirmed", confirmed_summary["status"])
            self.assertEqual(confirmed["executionId"], confirmed_summary["execution_id"])

    def test_conflict_recovery_keeps_the_original_automation_record(self):
        """Task47.3: same-Task recovery keeps the one original Automation run.

        A real Run once admits one Task for two files; the shared Worker
        organizes Two and parks One at a real target conflict.  The operator
        saves the rename decision, the same Task re-analyzes, the fresh summary
        is confirmed and the resident engine completes the remaining file on
        the same Task.  The Automation records page must keep showing that ONE
        original admitted run at every stage — before the decision, after the
        analysis, immediately after the confirmation, after the recovery
        execution and after a reopen — with its admission-written identity
        unchanged, counted exactly once, the already-successful sibling never
        replayed, and the first execution's own durable facts still provable.
        """

        self.media("One.2001.mkv")
        self.media("Two.2002.mkv")
        conflict_target = (
            self.target_root
            / "Organized/Movies/Movies/其他电影/One (2001) [tmdbid-1]/One (2001).mkv"
        )
        conflict_target.parent.mkdir(parents=True, exist_ok=True)
        conflict_target.write_bytes(b"old-target")
        records_route = "/api/v1/operations/automation/records?limit=20"

        with self.journey() as value:
            status, admitted = self.admit(value)
            self.assertEqual(202, status, admitted)
            task_id = admitted["taskId"]
            self.execute(value)
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            self.assertEqual("waiting_confirm", items["One.2001.mkv"].status.value)
            self.assertEqual("success", items["Two.2002.mkv"].status.value)
            two_result = next(
                result
                for result in value.repository.list_results(task_id)
                if result.item_id == items["Two.2002.mkv"].item_id
            )

            def original_record(label):
                status, page = self.request(value, "GET", records_route)
                self.assertEqual(200, status, page)
                self.assertEqual(1, page["total"], (label, page["items"]))
                self.assertEqual(1, sum(page["statusCounts"].values()), label)
                (record,) = page["items"]
                self.assertEqual(task_id, record["task_id"], label)
                return record

            before = original_record("before recovery")
            self.assertEqual("definition-run-once", before["origin"]["kind"])
            self.assertEqual("nightly", before["origin"]["definitionId"])
            self.assertEqual("manual", before["trigger"])
            started_at = before["executionStartedAt"]
            self.assertIsNotNone(started_at)
            # The first automatic stage really ended here: it organized Two,
            # parked One at the conflict and handed the work to the operator.
            # The record freezes that stage's own outcome and real window, so a
            # later same-Task recovery can never rewrite them.
            finished_at = before["executionFinishedAt"]
            self.assertIsNotNone(finished_at)
            original_outcome = before["recordOutcome"]
            self.assertEqual("failed", original_outcome["status"], original_outcome)
            self.assertFalse(original_outcome["noWork"])
            self.assertEqual(1, original_outcome["successItems"], original_outcome)
            self.assertIn("等待人工决定", original_outcome["failureReason"], original_outcome)
            self.assertIn("任务中心", original_outcome["nextStep"], original_outcome)

            # The operator returns an hour later: every later write uses the
            # advanced fixture clock, so the frozen original stage must stay
            # exactly as captured above across the whole recovery.
            self.clock.advance(3600)

            route = f"/api/v1/tasks/{task_id}/items/{items['One.2001.mkv'].item_id}/recovery"
            status, detail = self.request(value, "GET", route)
            self.assertEqual(200, status, detail)
            status, decided = self.request(
                value,
                "POST",
                route + "/decision",
                {
                    "kind": "conflict",
                    "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
                    "strategy": "rename",
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                route + "/continue",
                {"expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"]},
            )
            self.assertEqual(202, status, continued)
            self.execute(value)
            analyzed = original_record("after analysis")
            self.assertEqual(started_at, analyzed["executionStartedAt"])
            self.assertEqual(finished_at, analyzed["executionFinishedAt"])
            self.assertEqual(original_outcome, analyzed["recordOutcome"])

            status, detail = self.request(value, "GET", route)
            self.assertEqual(200, status, detail)
            preparation = detail["manualRecoveryPreparation"]
            self.assertIsNotNone(preparation, detail)
            status, preview = self.request(
                value, "GET", f"/api/v1/manual-previews/{preparation['preview_id']}"
            )
            self.assertEqual(200, status, preview)
            ready = [
                entry["itemId"] for entry in preview["items"] if entry["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview)
            status, confirmed = self.request(
                value,
                "POST",
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                {"itemIds": ready, "confirmation": True},
            )
            self.assertEqual(202, status, confirmed)
            self.assertEqual(task_id, confirmed["taskId"], confirmed)

            # The exact P1 counterexample: the same-Task confirmation must not
            # exclude the original admitted run from its own records page.
            after_confirm = original_record("immediately after confirm")
            self.assertEqual(started_at, after_confirm["executionStartedAt"])
            self.assertEqual(finished_at, after_confirm["executionFinishedAt"])
            self.assertEqual(original_outcome, after_confirm["recordOutcome"])

            worker = self._run_manual_execution_worker(value, prefix="conflict-recovery")
            settled = worker.run_next()
            self.assertIsNotNone(settled)
            self.assertEqual("completed", settled.status.value, settled.error)
            self.assertEqual((), ())
            self.assertFalse((self.source_root / "One.2001.mkv").exists())
            organized = sorted(
                str(path.relative_to(self.target_root))
                for path in (self.target_root / "Organized" / "Movies").rglob("*.mkv")
            )
            self.assertEqual(
                [
                    "Organized/Movies/Movies/其他电影/One (2001) [tmdbid-1]/One (2001) (1).mkv",
                    "Organized/Movies/Movies/其他电影/One (2001) [tmdbid-1]/One (2001).mkv",
                    "Organized/Movies/Movies/其他电影/Two (2002) [tmdbid-2]/Two (2002).mkv",
                ],
                organized,
            )
            # The successful sibling was never replayed: exactly one delete of
            # Two and one target copy exist.
            self.assertEqual(
                1,
                len(
                    [item for item in value.source.mutations if item == ("delete", "Two.2002.mkv")]
                ),
                value.source.mutations,
            )
            results = value.repository.list_results(task_id)
            self.assertEqual(2, len(results), results)
            self.assertEqual(
                two_result.created_at,
                next(
                    result.created_at
                    for result in results
                    if result.item_id == items["Two.2002.mkv"].item_id
                ),
                "the first execution's own result fact was rewritten",
            )

            after = original_record("after recovery")
            self.assertEqual(before["recordId"], after["recordId"])
            self.assertEqual(before["origin"], after["origin"])
            self.assertEqual(before["trigger"], after["trigger"])
            self.assertEqual(
                before["historyContext"]["definitionId"],
                after["historyContext"]["definitionId"],
            )
            # The original stage's own frozen facts: the first execution's real
            # start and end and its "1 success, 1 unresolved" outcome survive
            # the later same-Task recovery unchanged, on the API document, the
            # outcome filter and a reopen alike.
            self.assertEqual(started_at, after["executionStartedAt"])
            self.assertEqual(finished_at, after["executionFinishedAt"])
            self.assertEqual(original_outcome, after["recordOutcome"])
            status, failed_only = self.request(value, "GET", records_route + "&outcome=failed")
            self.assertEqual(200, status, failed_only)
            self.assertEqual(1, failed_only["total"], failed_only["items"])
            status, completed_only = self.request(
                value, "GET", records_route + "&outcome=completed"
            )
            self.assertEqual(200, status, completed_only)
            self.assertEqual(0, completed_only["total"], completed_only["items"])
            # The run's current aggregate stays the Task's own live truth: the
            # same Task really completed both files, while the original record
            # above kept the first stage's facts and the recovery progress is
            # reported separately.
            self.assertEqual("completed", after["result"]["status"])
            self.assertTrue(after["result"]["organized"])
            self.assertEqual(2, after["result"]["successItems"])
            self.assertFalse(after["recovered_completion"])
            # The recovery progress is reported separately from the outcome.
            self.assertEqual("resolved", after["handling"]["state"], after["handling"])
            self.assertEqual(1, after["handling"]["resolvedItems"], after["handling"])

            # The original run is counted exactly once in the metric cohorts
            # around the fixture's own clock, and stays the definition's latest
            # original admitted run after the same-Task recovery.
            metrics = value.repository.automation_run_metrics(
                current_start=value.clock.now - timedelta(days=1),
                current_end=value.clock.now + timedelta(days=1),
                previous_start=value.clock.now - timedelta(days=2),
                previous_end=value.clock.now - timedelta(days=1),
            )
            self.assertEqual(1, metrics["currentAdmitted"], metrics)
            self.assertEqual(1, metrics["currentTerminal"], metrics)
            self.assertEqual(1, metrics["currentCompleted"], metrics)
            latest = value.repository.automation_latest_admitted_runs()
            self.assertEqual(["nightly"], list(latest), latest)
            self.assertEqual(task_id, latest["nightly"]["runId"])
            self.assertEqual(task_id, latest["nightly"]["taskId"])

        with SQLiteTaskRepository(str(self.root / "runtime.sqlite3")) as reopened:
            window = reopened.operations_runs_window(
                limit=20, automation_admissions=True, record_evidence=True
            )
            self.assertEqual(1, window.total, [item.task_id for item in window.page])
            self.assertEqual(1, sum(window.status_counts.values()))
            (item,) = window.page
            self.assertEqual(task_id, item.task_id)
            evidence = item.automation_record_evidence
            self.assertEqual("failed", evidence["record_outcome"], evidence)
            self.assertEqual("failed", evidence["original_status"], evidence)
            self.assertEqual(2, evidence["item_count"], evidence)
            self.assertEqual(1, evidence["success_count"], evidence)
            self.assertEqual(1, evidence["waiting_count"], evidence)
            self.assertEqual(started_at, evidence["record_started_at"], evidence)
            self.assertEqual(finished_at, evidence["record_finished_at"], evidence)

    def _run_manual_execution_worker(self, value, *, prefix: str):
        """The real resident Worker branch that executes a confirmed exact subset."""

        from mediaflow.application.manual_organize_execution import (
            ManualOrganizeExecutionService,
        )
        from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
        from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
        from mediaflow.application.metadata import MetadataProviderRegistry
        from mediaflow.application.strategy_test import SyntheticMetadataProvider
        from mediaflow.application.task_scheduling import TaskSchedulingService
        from mediaflow.domain.metadata import MediaCandidate, MediaType
        from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

        scheduling = TaskSchedulingService(value.repository, capacity=100)
        provider_registry = MetadataProviderRegistry(
            (
                SyntheticMetadataProvider(
                    (
                        MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
                        MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
                    )
                ),
            )
        )
        previews = ManualOrganizePreviewService(
            value.repository,
            value.intents,
            configuration=value.runtime,
            storages={"source": value.source, "target": value.target},
            providers=provider_registry,
            clock=value.clock,
        )
        execution_service = ManualOrganizeExecutionService(
            value.repository,
            previews,
            value.intents,
            configuration=value.runtime,
            storages={"source": value.source, "target": value.target},
            clock=value.clock,
        )
        worker_id = f"{prefix}-{len(value.repository.list_tasks())}"
        value.repository.register_worker(
            worker_id,
            worker_id,
            5.0,
            ("organize",),
            None,
            None,
            SCHEMA_VERSION,
            value.clock.now,
        )
        return ManualTaskEngineWorker(
            value.repository,
            scheduling,
            None,
            execution_service,
            worker_id=worker_id,
            clock=value.clock,
        )

    def test_scheduled_decision_summary_belongs_to_the_continuing_operator(self):
        """A real Scheduler due Task keeps the operator's own recovery authority.

        The due Task is admitted by the Scheduler principal, but its saved
        decision is continued by an authenticated operator.  The fresh summary
        must belong to that operator (not ``automation-scheduler``), a different
        permitted operator cannot confirm it, and the original operator's
        explicit confirmation executes the allowed subset on the same Task.
        """

        from mediaflow.application.automation import IntervalScheduler
        from mediaflow.application.task_scheduling import TaskSchedulingService
        from mediaflow.domain.automation import (
            AutomationTaskDefinition,
            SchedulerConfigurationSnapshot,
        )

        self.media("Movies/One.2001.mkv")
        self.change_document = lambda document: document.update({"recognitionRules": []})
        with self.journey(definitions=self._kernel_definition_document()) as value:
            active = value.managed.active()
            definition = AutomationTaskDefinition.from_document(
                active.document["automationTaskDefinitions"][0]
            )
            scheduling = TaskSchedulingService(value.repository, capacity=10)
            version = getattr(value.runtime, "configuration_snapshot_version", active.version)
            snapshot = SchedulerConfigurationSnapshot(
                active.revision_id,
                active.digest,
                (),
                100,
                (definition,),
                version,
                ("library",),
                ("library",),
            )
            emitted = IntervalScheduler(
                value.repository,
                (),
                configuration_snapshot_resolver=lambda: snapshot,
                scheduling_service=scheduling,
            ).tick(value.clock.now)
            self.assertEqual(1, len(emitted))
            task_id = emitted[0].task_id
            self.assertFalse(hasattr(value.repository, "list_jobs"))
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual("automation-scheduler", state.admission_principal)
            self.assertEqual("schedule", state.admission_trigger.value)

            result = self.execute(value)
            self.assertIsNotNone(result)
            (item,) = value.repository.list_items(task_id)
            self.assertEqual("waiting_recognition", item.status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            # The due run's first automatic stage really ended here: it handed
            # the unresolved source to the operator.  Freeze that stage's own
            # facts, then advance the clock so every later recovery write uses
            # a later time the frozen record must never adopt.
            status, first_record = self.request(
                value, "GET", "/api/v1/operations/automation/records?limit=20"
            )
            self.assertEqual(200, status, first_record)
            self.assertEqual(1, first_record["total"], first_record["items"])
            (first_record,) = first_record["items"]
            first_outcome = first_record["recordOutcome"]
            self.assertEqual("failed", first_outcome["status"], first_outcome)
            self.assertEqual(0, first_outcome["successItems"], first_outcome)
            self.assertIn("等待人工决定", first_outcome["failureReason"], first_outcome)
            first_started = first_record["executionStartedAt"]
            first_finished = first_record["executionFinishedAt"]
            self.assertIsNotNone(first_started)
            self.assertIsNotNone(first_finished)
            self.clock.advance(3600)

            status, detail = self.request(
                value, "GET", f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            status, decided = self.request(
                value,
                "POST",
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
                {
                    "kind": "recognition",
                    "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
                    "recognitionTypeId": "A",
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/continue",
                {"expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"]},
            )
            self.assertEqual(202, status, continued)
            self.assertEqual(task_id, continued["nativeAnalysis"]["taskId"])
            # The authenticated operator is durably recorded for this re-entry;
            # the Scheduler principal remains the Task's original provenance.
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual("admin", state.continuation_actor)
            self.assertEqual("automation-scheduler", state.admission_principal)

            self.assertIsNotNone(self.execute(value))
            (item,) = value.repository.list_items(task_id)
            self.assertEqual("waiting_confirm", item.status.value, item)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            status, detail = self.request(
                value, "GET", f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            preparation = detail["manualRecoveryPreparation"]
            self.assertIsNotNone(preparation, detail)
            self.assertEqual("prepared", preparation["status"])
            self.assertEqual("admin", preparation["actor"])
            # A refresh/reopen reads the same durable summary and actor.
            status, refreshed = self.request(
                value, "GET", f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, refreshed)
            self.assertEqual(
                preparation["preparation_id"],
                refreshed["manualRecoveryPreparation"]["preparation_id"],
            )

            status, preview = self.request(
                value, "GET", f"/api/v1/manual-previews/{preparation['preview_id']}"
            )
            self.assertEqual(200, status, preview)
            ready = [
                entry["itemId"] for entry in preview["items"] if entry["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview)
            status, refused = self.request(
                value,
                "POST",
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                {"itemIds": ready, "confirmation": True},
                token=OPERATOR_TOKEN,
            )
            self.assertEqual(403, status, refused)
            self.assertEqual("preparation_actor_mismatch", refused["error"]["code"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            status, confirmed = self.request(
                value,
                "POST",
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                {"itemIds": ready, "confirmation": True},
            )
            self.assertEqual(202, status, confirmed)
            self.assertEqual(task_id, confirmed["taskId"])
            self.assertFalse(hasattr(value.repository, "list_jobs"))

            settled = self._run_manual_execution_worker(
                value, prefix="scheduled-recovery"
            ).run_next()
            self.assertIsNotNone(settled)
            self.assertEqual(task_id, settled.task_id)
            self.assertEqual("completed", settled.status.value, settled.error)
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            organized = list((self.target_root / "Organized" / "Movies").rglob("*.mkv"))
            self.assertEqual(1, len(organized), organized)
            results = value.repository.list_results(task_id)
            self.assertEqual(1, len(results), results)
            self.assertEqual("SUCCESS", results[0].status)
            self.assertFalse(hasattr(value.repository, "list_jobs"))

            # The due run stays the one original Automation record after its
            # same-Task recovery completed it: same identity, scheduled
            # trigger, real outcome, and the recovery reported separately.
            status, page = self.request(
                value, "GET", "/api/v1/operations/automation/records?limit=20"
            )
            self.assertEqual(200, status, page)
            self.assertEqual(1, page["total"], page["items"])
            (record,) = page["items"]
            self.assertEqual(task_id, record["task_id"])
            self.assertEqual("scheduled", record["trigger"], record)
            self.assertEqual("definition-scheduled", record["origin"]["kind"], record)
            self.assertEqual("completed", record["result"]["status"], record)
            self.assertTrue(record["result"]["organized"], record)
            self.assertEqual("resolved", record["handling"]["state"], record["handling"])
            # The original record still expresses the due run's FIRST automatic
            # stage — the handoff to the operator — with its own real window,
            # never the later recovery's success or settlement time.
            self.assertEqual(first_outcome, record["recordOutcome"], record)
            self.assertEqual(first_started, record["executionStartedAt"], record)
            self.assertEqual(first_finished, record["executionFinishedAt"], record)
            status, failed_only = self.request(
                value,
                "GET",
                "/api/v1/operations/automation/records?limit=20&outcome=failed",
            )
            self.assertEqual(200, status, failed_only)
            self.assertEqual(1, failed_only["total"], failed_only["items"])
            status, filtered = self.request(
                value,
                "GET",
                "/api/v1/operations/automation/records?limit=20&trigger=scheduled",
            )
            self.assertEqual(200, status, filtered)
            self.assertEqual(1, filtered["total"], filtered["items"])
            status, manual_only = self.request(
                value,
                "GET",
                "/api/v1/operations/automation/records?limit=20&trigger=manual",
            )
            self.assertEqual(200, status, manual_only)
            self.assertEqual(0, manual_only["total"], manual_only["items"])

    def test_recognition_decision_reaching_classification_stays_a_business_problem(self):
        """A fresh four-type finding during recovery stays on the same Task.

        Recognition A is saved on a Run once Task; the zero-mutation re-analysis
        then finds that the pinned ClassificationPolicy selects no MediaLibrary.
        That is a Classification decision, not a technical failure: the item and
        Task wait for that decision, the Classification list shows it, and the
        operator can continue through summary and explicit execution.
        """

        self.media("One.2001.mkv")

        def no_matching_destination(document):
            document["recognitionRules"] = []
            document["classificationPolicies"][0]["rules"] = [
                {
                    "id": "tv-only",
                    "priority": 1,
                    "conditions": {"mediaType": ["tv"]},
                    "result": {"mediaLibraryId": "movies", "path": ["TV"]},
                }
            ]

        self.change_document = no_matching_destination
        with self.journey() as value:
            status, admitted = self.admit(value)
            self.assertEqual(202, status, admitted)
            task_id = admitted["taskId"]
            self.assertEqual((), value.repository.list_items(task_id))
            self.assertIsNotNone(self.execute(value))
            (item,) = value.repository.list_items(task_id)
            self.assertEqual("waiting_recognition", item.status.value)

            status, detail = self.request(
                value, "GET", f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            status, decided = self.request(
                value,
                "POST",
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
                {
                    "kind": "recognition",
                    "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
                    "recognitionTypeId": "A",
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/continue",
                {"expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"]},
            )
            self.assertEqual(202, status, continued)
            self.assertIsNotNone(self.execute(value))

            (item,) = value.repository.list_items(task_id)
            self.assertEqual("waiting_classification", item.status.value, item)
            self.assertEqual("waiting_classification", item.stage)
            task = value.repository.get_task(task_id)
            self.assertEqual("running", task.status.value, task)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual("waiting_human", state.queue_state.value)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            status, listing = self.request(
                value, "GET", "/api/v1/operations/runs?view=classification"
            )
            self.assertEqual(200, status, listing)
            self.assertEqual(1, listing["total"], listing)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertFalse(hasattr(value.repository, "list_jobs"))

            status, detail = self.request(
                value, "GET", f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            self.assertEqual("business_problem", detail["recoveryKind"])
            choices = detail["decision"]["choices"]
            self.assertEqual(["tv-only"], [choice["rule_id"] for choice in choices])
            status, decided = self.request(
                value,
                "POST",
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
                {
                    "kind": "classification",
                    "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
                    "choiceRank": choices[0]["rank"],
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/continue",
                {"expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"]},
            )
            self.assertEqual(202, status, continued)
            self.assertIsNotNone(self.execute(value))
            (item,) = value.repository.list_items(task_id)
            self.assertEqual("waiting_confirm", item.status.value, item)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            status, detail = self.request(
                value, "GET", f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            preparation = detail["manualRecoveryPreparation"]
            self.assertEqual("admin", preparation["actor"])
            status, preview = self.request(
                value, "GET", f"/api/v1/manual-previews/{preparation['preview_id']}"
            )
            self.assertEqual(200, status, preview)
            ready = [
                entry["itemId"] for entry in preview["items"] if entry["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview)
            status, confirmed = self.request(
                value,
                "POST",
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                {"itemIds": ready, "confirmation": True},
            )
            self.assertEqual(202, status, confirmed)
            settled = self._run_manual_execution_worker(
                value, prefix="classification-recovery"
            ).run_next()
            self.assertIsNotNone(settled)
            self.assertEqual(task_id, settled.task_id)
            self.assertEqual("completed", settled.status.value, settled.error)
            self.assertFalse((self.source_root / "One.2001.mkv").exists())
            organized = list(self.target_root.rglob("*.mkv"))
            self.assertEqual(1, len(organized), organized)
            self.assertFalse(hasattr(value.repository, "list_jobs"))

    def test_cancel_pending_run_once_settles_its_admitted_task(self):
        with self.journey() as value:
            status, body = self.admit(value)
            self.assertEqual(202, status, body)
            task_id = body["taskId"]
            self.assertEqual((), ())
            status, response = self.request(
                value, "POST", f"/api/v1/tasks/{task_id}/cancel", token=ADMIN_TOKEN
            )
            self.assertEqual(200, status, response)
            task = value.repository.get_task(task_id)
            self.assertEqual("cancelled", task.status.value)
            self.assertIsNotNone(task.completed_at)
            self.assertEqual("cancelled", response["task"]["status"])
            self.assertEqual([], value.source.mutations)

    def test_complete_walk_budget_and_unsafe_entries_fail_before_effects(self):
        from dataclasses import replace

        from mediaflow.application.automation_execution_intent import BoundedScopeReader

        self.media("One.2001.mkv")
        self.media("Two.2002.mkv")
        with self.journey() as value:
            self.admit(value)
            with patch(
                "mediaflow.application.automation_execution_intent.BoundedScopeReader",
                side_effect=lambda storage, **kwargs: BoundedScopeReader(
                    storage, maximum_entries=1, **kwargs
                ),
            ):
                result = self.execute(value)
            self.assertEqual("scope_unreadable", result.failure_category)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
        with self.journey() as value:
            self.admit(value, request_id="unsafe-2")
            original = value.source.list_page

            def unsafe(path, **kwargs):
                page = original(path, **kwargs)
                return replace(page, entries=[replace(page.entries[0], path="../outside.mkv")])

            with patch.object(value.source, "list_page", side_effect=unsafe):
                result = self.execute(value)
            self.assertEqual("scope_unreadable", result.failure_category)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_current_permission_loss_after_admission_settles_task_without_effects(self):
        import copy

        self.media("One.2001.mkv")
        with self.journey() as value:
            self.admit(value)
            document = copy.deepcopy(value.managed.active().document)
            document["api"]["principals"][0]["roles"] = ["viewer"]
            draft = value.managed.import_draft(document, actor="admin")
            validated = value.managed.validate(draft.revision_id, actor="admin")
            value.managed.activate(
                validated.revision_id, expected_version=validated.version, actor="admin"
            )
            result = self.execute(value)
            self.assertEqual("failed", result.status.value)
            self.assertEqual("failed", value.repository.get_task(result.task_id).status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_scheduled_definition_runs_as_one_kernel_task_without_a_job(self) -> None:
        from mediaflow.application.automation import IntervalScheduler
        from mediaflow.application.automation_definition_execution import (
            DefinitionScopedExecutionService,
        )
        from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
        from mediaflow.application.metadata import MetadataProviderRegistry
        from mediaflow.application.strategy_test import (
            SyntheticMetadataProvider,
            strategy_runner_from_configuration,
        )
        from mediaflow.application.task_scheduling import TaskSchedulingService
        from mediaflow.domain.automation import (
            AutomationTaskDefinition,
            SchedulerConfigurationSnapshot,
        )
        from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
        from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

        (self.source_root / "Empty").mkdir()
        definitions = [
            {
                "id": "nightly-kernel",
                "name": "Nightly kernel",
                "resourceLibraryId": "library",
                "mode": "automatic-organization",
                "intervalSeconds": 3600,
                "itemLimit": 10,
                "enabled": True,
                "sourceScope": "Empty",
            }
        ]
        with self.journey(definitions=definitions) as value:
            active = value.managed.active()
            definition = AutomationTaskDefinition.from_document(
                active.document["automationTaskDefinitions"][0]
            )
            scheduling = TaskSchedulingService(value.repository, capacity=10)
            version = getattr(value.runtime, "configuration_snapshot_version", active.version)
            snapshot = SchedulerConfigurationSnapshot(
                active.revision_id,
                active.digest,
                (),
                100,
                (definition,),
                version,
                ("library",),
                ("library",),
            )
            scheduler = IntervalScheduler(
                value.repository,
                (),
                configuration_snapshot_resolver=lambda: snapshot,
                scheduling_service=scheduling,
            )
            emitted = scheduler.tick(value.clock.now)
            self.assertEqual(1, len(emitted))
            task_id = emitted[0].task_id
            # No Job row exists; the durable work identity is the Task.
            self.assertFalse(hasattr(value.repository, "list_jobs"))
            self.assertIsNotNone(value.repository.get_task_scheduling(task_id))

            value.repository.register_worker(
                "auto-worker",
                "auto worker",
                5.0,
                ("organize",),
                active.revision_id,
                active.digest,
                SCHEMA_VERSION,
                value.clock.now,
            )
            provider = SyntheticMetadataProvider(())
            service = DefinitionScopedExecutionService(
                value.repository,
                value.runtime,
                storage_factory=lambda **kwargs: {
                    "source": value.source,
                    "target": value.target,
                },
                provider_factory=lambda ids: MetadataProviderRegistry((provider,)),
                strategy_factory=strategy_runner_from_configuration,
                history_factory=JsonLinesOperationHistoryRepository,
                unattended_grant_service=value.api._unattended_grants,
            )

            def runner(task, claim, clock=None, heartbeat=None):
                service.run(
                    task,
                    scheduling,
                    claim,
                    run_once=False,
                    cancellation_check=lambda: False,
                    clock=clock,
                    heartbeat=heartbeat,
                )

            worker = ManualTaskEngineWorker(
                value.repository,
                scheduling,
                None,
                None,
                worker_id="auto-worker",
                clock=value.clock,
                automatic_runner=runner,
            )
            worker.run_next()

            task = value.repository.get_task(task_id)
            self.assertEqual("completed", task.status.value)
            self.assertFalse(hasattr(value.repository, "list_jobs"))
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_scheduled_definition_organizes_a_ready_file_on_one_task(self) -> None:
        from mediaflow.application.automation import IntervalScheduler
        from mediaflow.application.automation_definition_execution import (
            DefinitionScopedExecutionService,
        )
        from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
        from mediaflow.application.metadata import MetadataProviderRegistry
        from mediaflow.application.strategy_test import (
            SyntheticMetadataProvider,
            strategy_runner_from_configuration,
        )
        from mediaflow.application.task_scheduling import TaskSchedulingService
        from mediaflow.domain.automation import (
            AutomationTaskDefinition,
            SchedulerConfigurationSnapshot,
        )
        from mediaflow.domain.metadata import MediaCandidate, MediaType
        from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
        from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

        self.media("Movies/One.2001.mkv")
        definitions = [
            {
                "id": "nightly-file",
                "name": "Nightly file",
                "resourceLibraryId": "library",
                "mode": "automatic-organization",
                "intervalSeconds": 3600,
                "itemLimit": 10,
                "enabled": True,
                "sourceScope": "Movies",
            }
        ]
        with self.journey(definitions=definitions) as value:
            active = value.managed.active()
            definition = AutomationTaskDefinition.from_document(
                active.document["automationTaskDefinitions"][0]
            )
            scheduling = TaskSchedulingService(value.repository, capacity=10)
            version = getattr(value.runtime, "configuration_snapshot_version", active.version)
            snapshot = SchedulerConfigurationSnapshot(
                active.revision_id,
                active.digest,
                (),
                100,
                (definition,),
                version,
                ("library",),
                ("library",),
            )
            emitted = IntervalScheduler(
                value.repository,
                (),
                configuration_snapshot_resolver=lambda: snapshot,
                scheduling_service=scheduling,
            ).tick(value.clock.now)
            self.assertEqual(1, len(emitted))
            task_id = emitted[0].task_id
            self.assertFalse(hasattr(value.repository, "list_jobs"))
            value.repository.register_worker(
                "auto-worker",
                "auto worker",
                5.0,
                ("organize",),
                active.revision_id,
                active.digest,
                SCHEMA_VERSION,
                value.clock.now,
            )
            provider = SyntheticMetadataProvider(
                (MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),)
            )
            service = DefinitionScopedExecutionService(
                value.repository,
                value.runtime,
                storage_factory=lambda **kwargs: {
                    "source": value.source,
                    "target": value.target,
                },
                provider_factory=lambda ids: MetadataProviderRegistry((provider,)),
                strategy_factory=strategy_runner_from_configuration,
                history_factory=JsonLinesOperationHistoryRepository,
                unattended_grant_service=value.api._unattended_grants,
            )

            def runner(task, claim, clock=None, heartbeat=None):
                service.run(
                    task,
                    scheduling,
                    claim,
                    run_once=False,
                    cancellation_check=lambda: False,
                    clock=clock,
                    heartbeat=heartbeat,
                )

            worker = ManualTaskEngineWorker(
                value.repository,
                scheduling,
                None,
                None,
                worker_id="auto-worker",
                clock=value.clock,
                automatic_runner=runner,
            )
            worker.run_next()

            task = value.repository.get_task(task_id)
            self.assertEqual("completed", task.status.value)
            self.assertEqual(1, task.completed_items)
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            self.assertTrue(value.target.mutations)
            self.assertFalse(hasattr(value.repository, "list_jobs"))

    def _kernel_file_journey(self, value, *, provider):
        """Build the real Scheduler + definition service for one ready file."""

        from mediaflow.application.automation import IntervalScheduler
        from mediaflow.application.automation_definition_execution import (
            DefinitionScopedExecutionService,
        )
        from mediaflow.application.metadata import MetadataProviderRegistry
        from mediaflow.application.strategy_test import strategy_runner_from_configuration
        from mediaflow.application.task_scheduling import TaskSchedulingService
        from mediaflow.domain.automation import (
            AutomationTaskDefinition,
            SchedulerConfigurationSnapshot,
        )
        from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
        from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

        active = value.managed.active()
        definition = AutomationTaskDefinition.from_document(
            active.document["automationTaskDefinitions"][0]
        )
        scheduling = TaskSchedulingService(value.repository, capacity=10)
        version = getattr(value.runtime, "configuration_snapshot_version", active.version)
        snapshot = SchedulerConfigurationSnapshot(
            active.revision_id,
            active.digest,
            (),
            100,
            (definition,),
            version,
            ("library",),
            ("library",),
        )
        emitted = IntervalScheduler(
            value.repository,
            (),
            configuration_snapshot_resolver=lambda: snapshot,
            scheduling_service=scheduling,
        ).tick(value.clock.now)
        self.assertEqual(1, len(emitted))
        task_id = emitted[0].task_id
        self.assertEqual((), ())
        value.repository.register_worker(
            "auto-worker",
            "auto worker",
            5.0,
            ("organize",),
            active.revision_id,
            active.digest,
            SCHEMA_VERSION,
            value.clock.now,
        )
        service = DefinitionScopedExecutionService(
            value.repository,
            value.runtime,
            storage_factory=lambda **kwargs: {
                "source": value.source,
                "target": value.target,
            },
            provider_factory=lambda ids: MetadataProviderRegistry((provider,)),
            strategy_factory=strategy_runner_from_configuration,
            history_factory=JsonLinesOperationHistoryRepository,
            unattended_grant_service=value.api._unattended_grants,
        )

        def runner(task, claim, clock=None, heartbeat=None):
            service.run(
                task,
                scheduling,
                claim,
                run_once=False,
                cancellation_check=lambda: False,
                clock=clock,
                heartbeat=heartbeat,
            )

        from mediaflow.application.manual_task_engine import ManualTaskEngineWorker

        worker = ManualTaskEngineWorker(
            value.repository,
            scheduling,
            None,
            None,
            worker_id="auto-worker",
            clock=value.clock,
            automatic_runner=runner,
        )
        return task_id, worker

    @staticmethod
    def _kernel_definition_document(scope: str = "Movies") -> list[dict]:
        return [
            {
                "id": "nightly-kernel",
                "name": "Nightly kernel",
                "resourceLibraryId": "library",
                "mode": "automatic-organization",
                "intervalSeconds": 3600,
                "itemLimit": 10,
                "enabled": True,
                "sourceScope": scope,
            }
        ]

    def test_slow_provider_keeps_claim_and_commits_a_verified_effect(self) -> None:
        from mediaflow.application.strategy_test import SyntheticMetadataProvider
        from mediaflow.domain.metadata import MediaCandidate, MediaType
        from mediaflow.domain.task_persistence import TaskItemStatus

        self.media("Movies/One.2001.mkv")
        with self.journey(definitions=self._kernel_definition_document()) as value:
            provider = SyntheticMetadataProvider(
                (MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),)
            )
            task_id, worker = self._kernel_file_journey(value, provider=provider)
            observed = []
            original_search = SyntheticMetadataProvider.search_movie
            original_mkdir = value.target.create_directory

            def search(self, *args, **kwargs):
                # The real Provider call takes longer than one whole lease.  The
                # owner must renew across it rather than dispatch a mutation
                # under an already-expired claim.
                value.clock.advance(301)
                return original_search(self, *args, **kwargs)

            def mkdir(path):
                state = value.repository.get_task_scheduling(task_id)
                observed.append(
                    (
                        state.mutation_in_flight,
                        state.claim_expires_at,
                        value.clock.now,
                    )
                )
                return original_mkdir(path)

            with (
                patch.object(SyntheticMetadataProvider, "search_movie", search),
                patch.object(value.target, "create_directory", mkdir),
            ):
                worker.run_next()

            task = value.repository.get_task(task_id)
            self.assertEqual("completed", task.status.value)
            self.assertEqual(1, task.completed_items)
            self.assertFalse((self.source_root / "Movies" / "One.2001.mkv").exists())
            self.assertTrue(value.target.mutations)
            self.assertEqual(1, len(observed))
            in_flight, expires_at, now = observed[0]
            self.assertTrue(in_flight)
            self.assertGreater(expires_at, now)
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            self.assertIs(
                value.repository.list_items(task_id)[0].status,
                TaskItemStatus.SUCCESS,
            )

    def test_lost_claim_before_dispatch_stops_every_effect(self) -> None:
        from mediaflow.application.strategy_test import SyntheticMetadataProvider
        from mediaflow.domain.metadata import MediaCandidate, MediaType

        self.media("Movies/One.2001.mkv")
        with self.journey(definitions=self._kernel_definition_document()) as value:
            provider = SyntheticMetadataProvider(
                (MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),)
            )
            task_id, worker = self._kernel_file_journey(value, provider=provider)
            original_search = SyntheticMetadataProvider.search_movie

            def search(self, *args, **kwargs):
                # Fault injection at the real repository boundary: a successor
                # owns the Task generation before the long call returns.
                with value.repository._lock:
                    value.repository._connection.execute(
                        "UPDATE task_scheduling SET claim_token='successor', "
                        "claim_generation=claim_generation+1 WHERE task_id=?",
                        (task_id,),
                    )
                    value.repository._connection.commit()
                return original_search(self, *args, **kwargs)

            with patch.object(SyntheticMetadataProvider, "search_movie", search):
                worker.run_next()

            self.assertEqual([], value.target.mutations)
            self.assertEqual([], value.source.mutations)
            self.assertEqual((), value.repository.list_results(task_id))
            task = value.repository.get_task(task_id)
            self.assertEqual("running", task.status.value)
            self.assertTrue((self.source_root / "Movies" / "One.2001.mkv").exists())

    def test_interrupted_dispatch_keeps_the_nonreplayable_marker(self) -> None:
        from mediaflow.application.strategy_test import SyntheticMetadataProvider
        from mediaflow.domain.metadata import MediaCandidate, MediaType
        from mediaflow.domain.storage import StorageError, StorageErrorCode

        self.media("Movies/One.2001.mkv")
        with self.journey(definitions=self._kernel_definition_document()) as value:
            provider = SyntheticMetadataProvider(
                (MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),)
            )
            task_id, worker = self._kernel_file_journey(value, provider=provider)

            def interrupted_write(path, data, *, overwrite=False):
                value.target.mutations.append(("write", path))
                raise StorageError(
                    StorageErrorCode.IO_ERROR, "write", path, "simulated interrupted dispatch"
                )

            with patch.object(value.target, "write", interrupted_write):
                worker.run_next()

            task = value.repository.get_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual("running", task.status.value)
            self.assertTrue(state.mutation_in_flight)
            (result,) = value.repository.list_results(task_id)
            self.assertEqual("attempted_unverified", result.effect_certainty)
            self.assertIn("mutation_outcome", result.uncertain_effects)
            self.assertTrue((self.source_root / "Movies" / "One.2001.mkv").exists())
            effects_before = tuple(value.target.mutations)
            # A second claim/pass cannot replay the unproved effect.
            self.assertIsNone(worker.run_next())
            self.assertEqual(effects_before, tuple(value.target.mutations))
            self.assertTrue(value.repository.get_task_scheduling(task_id).mutation_in_flight)

    def test_legacy_interval_and_cron_schedules_run_as_kernel_tasks(self) -> None:
        from mediaflow.application.automation import IntervalScheduler
        from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
        from mediaflow.application.task_scheduling import TaskSchedulingService
        from mediaflow.domain.automation import (
            AutomationCommand,
            CronSchedule,
            IntervalSchedule,
        )
        from mediaflow.final_cli import _automatic_task_runner
        from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

        (self.source_root / "Empty").mkdir()
        with self.journey(definitions=[]) as value:
            scheduling = TaskSchedulingService(value.repository, capacity=10)
            scheduler = IntervalScheduler(
                value.repository,
                (
                    IntervalSchedule("legacy-interval", AutomationCommand.ORGANIZE, 60, 5),
                    CronSchedule("legacy-cron", AutomationCommand.ORGANIZE, "* * * * *", "UTC", 5),
                ),
                scheduling_service=scheduling,
            )
            # The first tick initializes both due states and may emit the
            # interval; one minute later both a legacy interval and a
            # timezone-aware Cron occurrence are due.
            emitted = list(scheduler.tick(self.clock.now))
            self.clock.advance(60)
            emitted.extend(scheduler.tick(self.clock.now))
            names = {
                value.repository.get_run_display_context(item.task_id).origin_definition_name
                for item in emitted
            }
            self.assertEqual({"legacy-interval", "legacy-cron"}, names)
            self.assertFalse(hasattr(value.repository, "list_jobs"))
            for item in emitted:
                self.assertEqual(
                    "legacy-schedule",
                    value.repository.get_run_display_context(item.task_id).origin_kind,
                )
                self.assertIsNotNone(value.repository.get_task_scheduling(item.task_id))
            value.repository.register_worker(
                "legacy-worker",
                "legacy worker",
                5.0,
                ("organize",),
                None,
                None,
                SCHEMA_VERSION,
                self.clock.now,
            )
            runner = _automatic_task_runner(value.repository, None, scheduling)
            worker = ManualTaskEngineWorker(
                value.repository,
                scheduling,
                None,
                None,
                worker_id="legacy-worker",
                clock=self.clock,
                automatic_runner=runner,
            )
            with patch("mediaflow.final_cli._configuration", return_value=value.runtime):
                for _ in emitted:
                    worker.run_next()
            for item in emitted:
                task = value.repository.get_task(item.task_id)
                self.assertEqual("completed", task.status.value)
                self.assertEqual(0, task.total_items)
            self.assertFalse(hasattr(value.repository, "list_jobs"))

    def test_repeated_storage_cursor_cannot_be_reported_as_empty_scope(self):
        from mediaflow.domain.storage import StoragePage

        with self.journey() as value:
            self.admit(value)
            with patch.object(value.source, "list_page", return_value=StoragePage((), "repeat")):
                result = self.execute(value)
            self.assertEqual("scope_unreadable", result.failure_category)
            self.assertEqual("failed", value.repository.get_task(result.task_id).status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_scope_beyond_existing_depth_budget_never_executes_a_prefix(self):
        self.media("One.2001.mkv")
        self.media("/".join(["nested"] * 33 + ["Two.2002.mkv"]))
        with self.journey() as value:
            self.admit(value)
            result = self.execute(value)
            self.assertEqual("scope_unreadable", result.failure_category)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_pending_task_cancellation_is_honored_before_any_claim(self):
        self.media("One.2001.mkv")
        with self.journey() as value:
            status, body = self.admit(value)
            self.assertEqual(202, status, body)
            task_id = body["taskId"]
            status, response = self.request(
                value, "POST", f"/api/v1/tasks/{task_id}/cancel", token=ADMIN_TOKEN
            )
            self.assertEqual(200, status, response)
            self.assertIsNone(self.execute(value))
            self.assertEqual("cancelled", value.repository.get_task(task_id).status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
