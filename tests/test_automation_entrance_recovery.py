"""Files organizing completes its recovery on one Task through the live surfaces.

Every assertion starts from the real authenticated Files admission API
(``POST /api/resource-libraries/{id}/files/discoveries``) that the Files page
uses.  The production ``ManualTaskEngineWorker`` advances the admitted Task
through the real bounded discovery, the real Task Center decision/continue
routes and the real Preview confirmation; the confirmed work executes through
``ManualOrganizeExecutionService`` and the real ``OrganizerExecutor``.  One
SQLite file holds the managed configuration revisions and the runtime work, and
only temporary Local Storage roots carry media.  No retired CLI, synthetic
route or second engine establishes the work.
"""

from __future__ import annotations

import errno
import io
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
from mediaflow.application.media_discovery import MediaDiscoveryService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.application.task_scheduling import TaskSchedulingService
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.processing_checkpoint import CheckpointConfiguration, EffectCertainty
from mediaflow.domain.security import ApiRole
from mediaflow.domain.task_persistence import PersistentTaskStatus
from mediaflow.domain.task_scheduling import TaskQueueState
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.account_fixtures import AccountSessions

ADMIN_TOKEN = "entrance-recovery-admin"
OPERATOR_TOKEN = "entrance-recovery-operator"
REQUEST_ID = "11111111-1111-4111-8111-111111111111"


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


@contextmanager
def entrance_journey(
    case,
    *,
    movie_rule: bool = False,
    candidates: tuple | None = None,
    organize_operation: str | None = None,
    recognition_rules: list[dict] | None = None,
    provider_registry: MetadataProviderRegistry | None = None,
    viewer_token: str | None = None,
    max_provider_requests: int | None = None,
):
    """One production-shaped managed layout for one Files organizing journey.

    The managed revision store and the runtime work share one SQLite file and
    the JSON bootstrap names exactly that database, so the real API binding,
    the pinned Worker services and the durable Task read back the same authority
    a deployment uses.
    """

    root = case.root
    source_root = root / "source"
    target_root = root / "target"
    source_root.mkdir(parents=True, exist_ok=True)
    target_root.mkdir(parents=True, exist_ok=True)
    source = LocalStorage("source", source_root)
    target = LocalStorage("target", target_root)
    database = root / "runtime.sqlite3"
    document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    document["persistence"] = {"databasePath": str(database)}
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
            "displayRootPath": str(source_root),
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
    document["recognitionRules"] = []
    if organize_operation is not None:
        # The policy the movie rule resolves to, when the journey needs a
        # specific real OrganizerExecutor operation (for example COPY to prove
        # an unverified target write keeps its source).
        document["organizePolicies"][0]["operation"] = organize_operation
    if recognition_rules is not None:
        document["recognitionRules"] = recognition_rules
    elif movie_rule:
        # One legal movie rule over the whole library, so the Files discovery
        # resolves a type through the real rule engine instead of waiting for
        # an operator decision.
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
    if max_provider_requests is not None:
        for policy in document.get("metadataPolicies", ()):
            policy["maxProviderRequests"] = max_provider_requests
    document["automationTaskDefinitions"] = []
    config = root / "bootstrap.json"
    config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    if provider_registry is None:
        provider_registry = MetadataProviderRegistry(
            (
                SyntheticMetadataProvider(
                    candidates
                    if candidates is not None
                    else (
                        MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
                        MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
                    )
                ),
            )
        )
    with SQLiteConfigurationRepository(database) as configuration_repository:
        managed = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(database),
        )
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
                revision.document,
                bootstrap_database_path=managed.bootstrap_database_path,
            ),
            snapshot_id=revision.revision_id,
            digest=revision.digest,
            version=revision.version,
        )
        with SQLiteTaskRepository(str(database)) as repository:
            accounts = AccountSessions(repository)
            accounts.add("admin", (ApiRole.ADMIN,))
            accounts.add("operator", (ApiRole.OPERATOR,))
            if viewer_token is not None:
                accounts.add("viewer", (ApiRole.VIEWER,))
            storages = {"source": source, "target": target}
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
                providers=provider_registry,
                clock=case.clock,
            )
            executions = ManualOrganizeExecutionService(
                repository,
                previews,
                intents,
                checkpoint_service=ProcessingCheckpointService(repository),
                configuration=runtime,
                storages=dict(storages),
                clock=case.clock,
            )
            discovery = MediaDiscoveryService(
                repository,
                intents,
                configuration=runtime,
                preview_service=previews,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storages=dict(storages),
                clock=case.clock,
            )
            repository.register_worker(
                "files-task-engine",
                "Files task engine",
                5.0,
                ("manual_organize",),
                None,
                None,
                SCHEMA_VERSION,
                case.clock.now,
            )
            task_engine = ManualTaskEngineWorker(
                repository,
                TaskSchedulingService(repository, capacity=100),
                discovery,
                executions,
                worker_id="files-task-engine",
                clock=case.clock,
                notice=lambda line: None,
            )
            api = MediaFlowApi(
                repository,
                account_service=accounts.service,
                configuration_service=managed,
                bootstrap_document=document,
                manual_intent_service=intents,
                manual_preview_service=previews,
                manual_execution_service=executions,
                media_discovery_service=discovery,
                storage_adapters=dict(storages),
                metadata_provider_registry_factory=lambda ids: provider_registry,
            )
            api._fixture_session_cookies = {
                ADMIN_TOKEN: accounts.cookie("admin"),
                OPERATOR_TOKEN: accounts.cookie("operator"),
            }
            if viewer_token is not None:
                api._fixture_session_cookies[viewer_token] = accounts.cookie("viewer")
            yield SimpleNamespace(
                api=api,
                repository=repository,
                managed=managed,
                runtime=runtime,
                intents=intents,
                previews=previews,
                executions=executions,
                discovery=discovery,
                task_engine=task_engine,
                clock=case.clock,
                source=source,
                target=target,
                source_root=source_root,
                target_root=target_root,
                revision=revision,
                config=config,
                provider_registry=provider_registry,
            )


class EntranceRecoveryJourneyTests(unittest.TestCase):
    """The Files organizing entrance completes its own recovery on one Task."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.clock = _Clock()
        self.environment = patch.dict(
            os.environ,
            {"TMDB_ACCESS_TOKEN": "sentinel-tmdb"},
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def media(self, relative: str) -> Path:
        path = self.root / "source" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"m" * 512)
        stamp = (self.clock.now - timedelta(hours=1)).timestamp()
        os.utime(path, (stamp, stamp))
        return path

    def request(self, value, method, path, body=None, *, token=ADMIN_TOKEN, headers=None):
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
            "HTTP_HOST": "127.0.0.1",
            "HTTP_ORIGIN": "http://127.0.0.1",
        }
        session = getattr(value.api, "_fixture_session_cookies", {}).get(token)
        if session is not None:
            environ["HTTP_COOKIE"] = session
        else:
            environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        environ.update(headers or {})
        result = b"".join(value.api(environ, lambda status, _h: statuses.append(status)))
        return int(statuses[0].split()[0]), (json.loads(result) if result else {})

    def _admit_files(self, value, paths, *, request_id=REQUEST_ID):
        """The real Files page admission of one bounded selection."""

        return self.request(
            value,
            "POST",
            "/api/resource-libraries/library/files/discoveries",
            {"paths": list(paths), "autoPrepare": True, "requestId": request_id},
        )

    def _drive(self, value, task_id, *, steps: int = 16):
        """Advance the admitted Task through the production Worker until human wait."""

        for _ in range(steps):
            value.task_engine.run_next()
            state = value.repository.get_task_scheduling(task_id)
            discovery = value.repository.get_media_discovery_for_task(task_id)
            if discovery is not None and state is not None:
                if state.queue_state in {TaskQueueState.WAITING_HUMAN, TaskQueueState.SETTLED}:
                    return discovery
                task = value.repository.get_task(task_id)
                if task is not None and task.status in {
                    PersistentTaskStatus.COMPLETED,
                    PersistentTaskStatus.FAILED,
                    PersistentTaskStatus.CANCELLED,
                }:
                    return discovery
        return value.repository.get_media_discovery_for_task(task_id)

    def _decide_and_analyze(self, value, task_id, *, recognition_type_id="A"):
        """Decide every waiting item, then re-run the same Task's analysis."""

        discovery = self._drive(value, task_id)
        self.assertIsNotNone(discovery, "the Files discovery never reached the worker")
        for item in value.repository.list_items(task_id):
            if item.status.value != "waiting_recognition":
                continue
            status, detail = self.request(
                value, "GET", f"/api/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            self.assertEqual("business_problem", detail["recoveryKind"])
            status, decided = self.request(
                value,
                "POST",
                f"/api/tasks/{task_id}/items/{item.item_id}/recovery/decision",
                {
                    "kind": "recognition",
                    "recognitionTypeId": recognition_type_id,
                    "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                f"/api/tasks/{task_id}/items/{item.item_id}/recovery/continue",
                {"expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"]},
            )
            self.assertEqual(202, status, continued)
            self.assertEqual(task_id, continued["nativeAnalysis"]["taskId"])
        return self._drive(value, task_id)

    def _ready_preview(self, value, discovery):
        status, preview = self.request(
            value, "GET", f"/api/operations/organize/previews/{discovery.preview_id}"
        )
        self.assertEqual(200, status, preview)
        ready = [entry["itemId"] for entry in preview["items"] if entry["status"] == "previewed"]
        return preview, ready

    def _execute(self, value, task_id, preview, item_ids, *, steps: int = 16):
        status, admitted = self.request(
            value,
            "POST",
            f"/api/operations/organize/previews/{preview['previewId']}/execute",
            {
                "confirmation": True,
                "itemIds": list(item_ids),
                "expectedIntentVersion": preview["intentVersion"],
                "allowOverwrite": False,
                "allowSourceCleanup": False,
            },
        )
        self.assertIn(status, (200, 202), admitted)
        for _ in range(steps):
            value.task_engine.run_next()
            task = value.repository.get_task(task_id)
            if task is not None and task.status in {
                PersistentTaskStatus.COMPLETED,
                PersistentTaskStatus.FAILED,
                PersistentTaskStatus.CANCELLED,
            }:
                return task
        return value.repository.get_task(task_id)

    def _target_disk_full(self, target_root: Path, *, contains: str | None = None):
        """Inject one real ENOSPC at a target Storage write, never at business state."""

        original_open = Path.open
        root = target_root.resolve()

        def disk_full(path, mode="r", *args, **kwargs):
            candidate = Path(path)
            if (
                "w" in mode
                and candidate.resolve().is_relative_to(root)
                and (contains is None or contains in str(candidate))
            ):
                raise OSError(errno.ENOSPC, "No space left on device", str(candidate))
            return original_open(path, mode, *args, **kwargs)

        return disk_full

    def test_files_decision_summary_confirmation_executes_on_one_task(self):
        """The Files Task's saved decision finishes on the same Task."""

        self.media("Movies/One.2001.mkv")
        with entrance_journey(
            self,
            candidates=(MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),),
        ) as value:
            status, admitted = self._admit_files(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            self.assertEqual(1, len(value.repository.list_tasks()))

            discovery = self._drive(value, task_id)
            self.assertIsNotNone(discovery)
            self.assertEqual(
                "waiting_human", value.repository.get_task_scheduling(task_id).queue_state.value
            )
            (item,) = value.repository.list_items(task_id)
            self.assertEqual("waiting_recognition", item.status.value)
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertFalse((value.target_root / "Organized").exists())

            discovery = self._decide_and_analyze(value, task_id)
            self.assertEqual(task_id, discovery.organize_task_id)
            self.assertIsNotNone(discovery.preview_id)
            preview, ready = self._ready_preview(value, discovery)
            self.assertEqual(1, len(ready), preview)
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertFalse(
                any((value.target_root / "Organized").rglob("*.mkv")),
                "the analysis must stay zero-mutation",
            )

            settled = self._execute(value, task_id, preview, ready)
            self.assertIsNotNone(settled)
            self.assertEqual("completed", settled.status.value, settled.error)
            self.assertFalse((value.source_root / "Movies/One.2001.mkv").exists())
            organized = list((value.target_root / "Organized" / "Movies").rglob("*.mkv"))
            self.assertEqual(1, len(organized), organized)
            results = value.repository.list_results(task_id)
            self.assertEqual(1, len(results), results)
            self.assertEqual("SUCCESS", results[0].status)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual("settled", state.queue_state.value)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual(1, len(value.repository.list_tasks()))

            # The original execution facts survive the reload; the confirmed
            # summary reads back with its linked execution.
            status, detail = self.request(
                value, "GET", f"/api/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            confirmed_summary = detail["manualRecoveryPreparation"]
            self.assertIsNotNone(confirmed_summary, detail)
            self.assertEqual("confirmed", confirmed_summary["status"])

    def test_files_partial_target_write_keeps_unknown_effect_across_reopen(self):
        """One real ENOSPC leaves a partial item whose effect is read back, not replayed."""

        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        candidates = (
            MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
            MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
        )
        with entrance_journey(
            self,
            organize_operation="COPY",
            candidates=candidates,
        ) as value:
            status, admitted = self._admit_files(
                value, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"]
            )
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]

            discovery = self._decide_and_analyze(value, task_id)
            preview, ready = self._ready_preview(value, discovery)
            self.assertEqual(2, len(ready), preview)

            with patch.object(
                Path, "open", self._target_disk_full(value.target_root, contains="Two (2002)")
            ):
                settled = self._execute(value, task_id, preview, ready)

            self.assertIsNotNone(settled)
            self.assertEqual("completed", settled.status.value, settled.error)
            items = {
                Path(item.source_path).name: item for item in value.repository.list_items(task_id)
            }
            self.assertEqual("success", items["One.2001.mkv"].status.value)
            self.assertEqual("partial", items["Two.2002.mkv"].status.value)
            self.assertEqual("uncertain_effects", items["Two.2002.mkv"].stage)
            self.assertTrue(items["Two.2002.mkv"].error)
            results = {
                Path(result.source_path).name: result
                for result in value.repository.list_results(task_id)
            }
            self.assertEqual("verified_complete", results["One.2001.mkv"].effect_certainty)
            self.assertEqual("attempted_unverified", results["Two.2002.mkv"].effect_certainty)
            self.assertEqual(("CREATE_DIRECTORY",), results["Two.2002.mkv"].completed_operations)
            self.assertEqual(("mutation_outcome",), results["Two.2002.mkv"].uncertain_effects)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual("settled", state.queue_state.value)
            self.assertFalse(state.mutation_in_flight)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            # COPY keeps both sources in place; only the successful sibling
            # published its target bytes.
            self.assertTrue((value.source_root / "Movies/One.2001.mkv").exists())
            self.assertTrue((value.source_root / "Movies/Two.2002.mkv").exists())
            organized = list((value.target_root / "Organized" / "Movies").rglob("*.mkv"))
            self.assertEqual(1, len(organized), organized)

            # A same-version reopen keeps the honest A/B endings.  The uncertain
            # effect is never converted into success and the settled Task is not
            # claimed again.
            with SQLiteTaskRepository(value.runtime.database_path) as reopened:
                reopened_task = reopened.get_task(task_id)
                self.assertEqual("completed", reopened_task.status.value)
                self.assertEqual(
                    {item.item_id: item.status for item in items.values()},
                    {item.item_id: item.status for item in reopened.list_items(task_id)},
                )
                self.assertEqual(
                    {
                        record.source_path: (record.status, record.effect_certainty)
                        for record in results.values()
                    },
                    {
                        record.source_path: (record.status, record.effect_certainty)
                        for record in reopened.list_results(task_id)
                    },
                )
                reopened_state = reopened.get_task_scheduling(task_id)
                self.assertEqual("settled", reopened_state.queue_state.value)
                self.assertFalse(reopened_state.mutation_in_flight)
                self.assertEqual(0, reopened.count_scheduled_capacity_use())
            self.assertIsNone(value.task_engine.run_next())
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual(2, len(value.repository.list_results(task_id)))

    def test_manual_task_without_organizing_origin_keeps_the_bounded_refusal(self):
        """A manual Task without a proved organizing origin is never continued.

        The kernel continuation is granted to a manual Task only when its durable
        display origin proves a supported organizing admission. A missing or
        foreign origin keeps the bounded ``no_linked_preparation`` refusal
        instead of granting every manual Task a continuation.
        """

        from mediaflow.application.manual_task_continuation import (
            ManualTaskContinuationError,
            ManualTaskContinuationService,
        )
        from mediaflow.domain.task_scheduling import TaskTrigger

        class _Repository:
            def __init__(self, origin):
                self._origin = origin

            def get_task_scheduling(self, task_id):
                return SimpleNamespace(admission_trigger=TaskTrigger.MANUAL)

            def get_run_display_context(self, task_id):
                if self._origin is None:
                    return None
                return SimpleNamespace(origin_kind=self._origin)

            def get_media_discovery_for_task(self, task_id):
                return None

        class _Checkpoints:
            def get(self, item_id, task_id=None):
                return SimpleNamespace(
                    task_id="task-1",
                    checkpoint_version="v1",
                    effect_certainty=EffectCertainty.NONE,
                    permitted_action_ids=("retry",),
                    active_recovery_request=None,
                    configuration=CheckpointConfiguration("snap-1", "digest-1", True, None),
                )

        class _Scheduling:
            def state(self, task_id):
                return SimpleNamespace(admission_trigger=TaskTrigger.MANUAL)

        for origin in (None, "definition-run-once", "legacy-schedule"):
            with self.subTest(origin=origin):
                service = ManualTaskContinuationService(
                    _Repository(origin),
                    discovery_service=None,
                    checkpoint_service=_Checkpoints(),
                    scheduling=lambda: _Scheduling(),
                )
                with self.assertRaises(ManualTaskContinuationError) as raised:
                    service.continue_analysis(
                        "task-1",
                        "item-1",
                        expected_checkpoint_version="v1",
                        actor="admin",
                    )
                self.assertEqual("no_linked_preparation", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
