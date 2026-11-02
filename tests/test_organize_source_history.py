"""Slice 47 RO-6 — the shared per-source organizing-history admission.

The behaviors this module pins, through real production entrances only:

* the repository finds one concrete source version's **latest formal organizing
  outcome** from the complete matching durable population — canonical
  Storage/path identity, comparable version evidence, admission/attempt order
  (a late publication of an older attempt is never "the newest attempt"), no
  recent-page truncation, analysis-only/non-organizing/exclusion records never
  mistaken for formal outcomes, and a durable failed item without a Result is
  never missed;
* a definition due / Run once pass **excludes** a file whose same-version
  latest formal outcome is failed/partial — one honest not-processed item, no
  Provider call, no Result, no Storage effect, an aggregate that never reads as
  a healthy completed run, free siblings processed normally, and a later manual
  success lifting the exclusion;
* a deliberate manual request is **never excluded** by that history: the same
  source reaches the real plan summary (with the bounded server-generated
  warning projected into the item document) and executes normally;
* a file item already recorded failed/partial is **history, not an active
  owner**: it no longer vetoes new manual organizing, while a queued/processing
  item without its own terminal outcome keeps the normal mutual exclusion.
"""

from __future__ import annotations

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

from mediaflow.application.automation_run_once import AutomationRunOnceService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.media_discovery import MediaDiscoveryService
from mediaflow.application.organize_source_history import (
    latest_applicable_outcome,
)
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.application.task_scheduling import TaskSchedulingService
from mediaflow.domain.manual_organize_preview import ManualPreviewItemStatus
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.security import (
    ROLE_PERMISSIONS,
    ApiPermission,
    ApiRole,
    ResolvedApiPrincipal,
)
from mediaflow.domain.task_persistence import (
    HISTORY_EXCLUDED_ITEM_STAGE,
    HISTORY_UNAVAILABLE_ITEM_STAGE,
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    TaskItemStatus,
)
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.source_fixtures import source_identity_from_storage

ADMIN_TOKEN = "source-history-admin"
OPERATOR_TOKEN = "source-history-operator"


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


@contextmanager
def history_journey(case, *, operation: str = "COPY", definitions: str | None = "nightly"):
    """One production-shaped managed layout for the source-history journeys.

    The managed revision store and the runtime work share one SQLite file, the
    real API routes and the real application services are bound exactly like a
    deployment, and the source library uses the given real organize operation
    (COPY keeps sources in place so a later manual success can lift an
    exclusion without moving the file away).
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
    document["organizePolicies"][0]["operation"] = operation
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
    document["recognitionRules"] = [
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
    if definitions is not None:
        document["automationTaskDefinitions"] = [
            {
                "id": "nightly",
                "name": "Nightly",
                "resourceLibraryId": "library",
                "mode": "automatic-organization",
                "intervalSeconds": 3600,
                "itemLimit": 10,
                "enabled": False,
            }
        ]
    else:
        document["automationTaskDefinitions"] = []
    document["api"]["principals"] = [
        {"id": "admin", "tokenEnv": "MEDIAFLOW_API_TOKEN", "roles": ["admin"], "enabled": True}
    ]
    document["api"]["remoteExecution"] = {"enabled": True, "maximumTtlSeconds": 900}
    config = root / "bootstrap.json"
    config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    provider_registry = case.provider_registry()
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
            intents = ManualOrganizeIntentService(
                repository,
                managed,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storage_factory=lambda value, ids: {"source": source, "target": target},
            )
            previews = ManualOrganizePreviewService(
                repository,
                intents,
                configuration=runtime,
                storages={"source": source, "target": target},
                providers=provider_registry,
                clock=case.clock,
            )
            discovery = MediaDiscoveryService(
                repository,
                intents,
                configuration=runtime,
                preview_service=previews,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storages={"source": source, "target": target},
                clock=case.clock,
            )
            run_once = AutomationRunOnceService(discovery, previews, clock=case.clock)
            api = MediaFlowApi(
                repository,
                None,
                principals=(
                    ResolvedApiPrincipal("admin", ADMIN_TOKEN, frozenset(ApiPermission)),
                    ResolvedApiPrincipal(
                        "operator", OPERATOR_TOKEN, ROLE_PERMISSIONS[ApiRole.OPERATOR]
                    ),
                ),
                configuration_service=managed,
                bootstrap_document=document,
                manual_intent_service=intents,
                manual_preview_service=previews,
                media_discovery_service=discovery,
                automation_run_once_service=run_once,
                metadata_provider_registry_factory=lambda ids: provider_registry,
            )
            yield SimpleNamespace(
                api=api,
                repository=repository,
                managed=managed,
                runtime=runtime,
                intents=intents,
                previews=previews,
                discovery=discovery,
                run_once=run_once,
                clock=case.clock,
                source=source,
                target=target,
                source_root=source_root,
                target_root=target_root,
                revision=revision,
                config=config,
                provider_registry=provider_registry,
            )


class OrganizeSourceOutcomeRepositoryTests(unittest.TestCase):
    """The complete-population history query and its identity/version rules."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "runtime.sqlite3"
        self.repository = SQLiteTaskRepository(str(self.database))
        self.addCleanup(self.repository.close)

    def _seed_outcome(
        self,
        *,
        command: str = "organize",
        source_path: str = "One.2001.mkv",
        storage_path: str | None = "One.2001.mkv",
        resource_library_id: str = "library",
        item_status: TaskItemStatus = TaskItemStatus.FAILED,
        item_stage: str = "completed",
        result_status: str | None = "failed",
        fingerprint: str | None = "f" * 64,
        created_at: datetime | None = None,
        attempts: int = 1,
        result_created_at: datetime | None = None,
        task: PersistentTask | None = None,
        with_result: bool = True,
    ) -> tuple[PersistentTask, PersistentTaskItem]:
        created_at = created_at or datetime.now(UTC)
        result_created_at = result_created_at or created_at
        coordinator = PersistentTaskCoordinator(self.repository, self.repository)
        task = task or coordinator.create(command, execute_authorized=True)
        item = PersistentTaskItem(
            f"item-{source_path}-{created_at.timestamp()}-{attempts}",
            task.task_id,
            "source",
            resource_library_id,
            source_path,
            source_path,
            item_status,
            item_stage,
            attempts,
            created_at,
            created_at,
            source_storage_path=storage_path,
            source_fingerprint=fingerprint,
            source_fingerprint_state=("verified" if fingerprint is not None else "unverified"),
        )
        self.repository.upsert_item(item)
        if with_result and result_status is not None:
            self.repository.append_result(
                PersistentResultRecord(
                    f"{item.item_id}:{attempts}",
                    task.task_id,
                    item.item_id,
                    "source",
                    source_path,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "MOVE",
                    result_status,
                    result_created_at,
                    error="injected failure" if result_status == "failed" else None,
                )
            )
        return task, item

    def _query_outcome(self, **kwargs):
        return latest_applicable_outcome(
            self.repository,
            storage_id="source",
            source_path=kwargs.pop("source_path", "One.2001.mkv"),
            storage_path=kwargs.pop("storage_path", "One.2001.mkv"),
            resource_library_id=kwargs.pop("resource_library_id", "library"),
            source_fingerprint=kwargs.pop("source_fingerprint", "f" * 64),
            source_version=None,
            exclude_task_id=kwargs.pop("exclude_task_id", None),
        )

    def test_latest_failed_outcome_is_found_beyond_recent_page_limits(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        task = None
        # Forty older formal successes for the same concrete source...
        for index in range(40):
            _task, _item = self._seed_outcome(
                item_status=TaskItemStatus.SUCCESS,
                result_status="success",
                created_at=base + timedelta(minutes=index),
                task=task,
            )
        # ...and one newer failed attempt: a recent-page window (32/100) over
        # the whole population would still contain it, but a per-page display
        # limit on the *source query* would not; the complete population must.
        _task, _item = self._seed_outcome(
            item_status=TaskItemStatus.FAILED,
            result_status="failed",
            created_at=base + timedelta(minutes=90),
        )
        outcome = self._query_outcome()
        self.assertIsNotNone(outcome)
        self.assertEqual("failed", outcome.status)
        self.assertTrue(outcome.excludes_automatically)

    def test_later_success_lifts_the_earlier_failure_exclusion(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        self._seed_outcome(
            item_status=TaskItemStatus.FAILED,
            result_status="failed",
            created_at=base,
        )
        self._seed_outcome(
            item_status=TaskItemStatus.SUCCESS,
            result_status="success",
            created_at=base + timedelta(minutes=5),
        )
        outcome = self._query_outcome()
        self.assertIsNotNone(outcome)
        self.assertEqual("success", outcome.status)
        self.assertFalse(outcome.excludes_automatically)

    def test_late_publication_of_an_older_attempt_is_not_the_latest(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        # An older attempt admitted first whose Result was published late...
        self._seed_outcome(
            item_status=TaskItemStatus.FAILED,
            result_status="failed",
            created_at=base,
            result_created_at=base + timedelta(minutes=30),
        )
        # ...and a newer attempt admitted later, published earlier, succeeded.
        self._seed_outcome(
            item_status=TaskItemStatus.SUCCESS,
            result_status="success",
            created_at=base + timedelta(minutes=10),
            result_created_at=base + timedelta(minutes=12),
        )
        outcome = self._query_outcome()
        self.assertIsNotNone(outcome)
        self.assertEqual("success", outcome.status)

    def test_replaced_file_is_not_held_by_the_old_failure(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        self._seed_outcome(
            item_status=TaskItemStatus.FAILED,
            result_status="failed",
            fingerprint="a" * 64,
            created_at=base,
        )
        outcome = self._query_outcome(source_fingerprint="b" * 64)
        self.assertIsNone(outcome, "a genuinely replaced file is a new version")

    def test_analysis_only_and_non_organizing_rows_are_not_formal_outcomes(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        self._seed_outcome(
            item_status=TaskItemStatus.DRY_RUN,
            result_status="dry_run",
            created_at=base,
        )
        self.assertIsNone(self._query_outcome(), "analysis-only records are not organizing")
        self._seed_outcome(
            command="files_transfer",
            item_status=TaskItemStatus.FAILED,
            result_status="failed",
            created_at=base + timedelta(minutes=1),
        )
        self.assertIsNone(self._query_outcome(), "ordinary file commands are not organizing")
        self._seed_outcome(
            item_status=TaskItemStatus.IGNORED,
            result_status=None,
            with_result=False,
            created_at=base + timedelta(minutes=2),
        )
        self.assertIsNone(self._query_outcome(), "an ignored item is an admission decision")

    def test_exclusion_stage_rows_never_become_the_recorded_history(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        self._seed_outcome(
            item_status=TaskItemStatus.SKIPPED,
            item_stage=HISTORY_EXCLUDED_ITEM_STAGE,
            result_status=None,
            with_result=False,
            created_at=base,
        )
        self._seed_outcome(
            item_status=TaskItemStatus.SKIPPED,
            item_stage=HISTORY_UNAVAILABLE_ITEM_STAGE,
            result_status=None,
            with_result=False,
            created_at=base + timedelta(minutes=1),
        )
        self.assertIsNone(
            self._query_outcome(),
            "an automatic exclusion records why nothing ran, never an outcome",
        )

    def test_durable_failed_item_without_result_is_not_missed(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        self._seed_outcome(
            item_status=TaskItemStatus.FAILED,
            item_stage="analysis_failed",
            result_status=None,
            with_result=False,
            created_at=base,
        )
        outcome = self._query_outcome()
        self.assertIsNotNone(outcome)
        self.assertEqual("failed", outcome.status)
        self.assertEqual("item", outcome.outcome_kind)

    def test_legacy_identity_and_distinct_paths_do_not_collide(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        self._seed_outcome(
            storage_path=None,
            created_at=base,
        )
        outcome = self._query_outcome()
        self.assertIsNotNone(outcome, "a pre-change row keeps its legacy identity")
        self.assertEqual("failed", outcome.status)
        self.assertIsNone(
            self._query_outcome(source_path="Other.2001.mkv", storage_path="Other.2001.mkv"),
            "equal names under distinct real paths are different sources",
        )

    def test_unreadable_history_is_fail_closed_not_history_free(self):
        class _ExplodingRepository:
            def latest_organize_source_outcome(self, **_kwargs):
                raise RuntimeError("injected history read failure")

        with self.assertRaises(RuntimeError):
            latest_applicable_outcome(
                _ExplodingRepository(),
                storage_id="source",
                source_path="One.2001.mkv",
                storage_path="One.2001.mkv",
                resource_library_id="library",
                source_fingerprint="f" * 64,
            )


class _SourceHistoryJourneyTests(unittest.TestCase):
    """Shared fixture for the real-entrance journeys."""

    def provider_registry(self):
        from mediaflow.application.metadata import MetadataProviderRegistry
        from mediaflow.application.strategy_test import SyntheticMetadataProvider

        return MetadataProviderRegistry(
            (
                SyntheticMetadataProvider(
                    (
                        MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
                        MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
                    )
                ),
            )
        )

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.clock = _Clock()
        self.environment = patch.dict(
            os.environ,
            {"TMDB_ACCESS_TOKEN": "sentinel-tmdb", "MEDIAFLOW_API_TOKEN": ADMIN_TOKEN},
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

    def request(self, value, method, path, body=None, *, token=ADMIN_TOKEN):
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
        result = b"".join(value.api(environ, lambda status, _h: statuses.append(status)))
        return int(statuses[0].split()[0]), (json.loads(result) if result else {})

    def admit_run_once(self, value, request_id="run-once-1"):
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
        }
        return self.request(
            value, "POST", "/api/v1/operations/automation/task-definitions/nightly/run-once", body
        )

    def execute_run_once(self, value):
        """Advance one admitted Run once through the real definition pipeline."""

        from mediaflow.application.automation_definition_execution import (
            DefinitionScopedExecutionService,
        )
        from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
        from mediaflow.application.strategy_test import strategy_runner_from_configuration
        from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository

        service = DefinitionScopedExecutionService(
            value.repository,
            value.runtime,
            storage_factory=lambda **kwargs: {"source": value.source, "target": value.target},
            provider_factory=lambda ids: value.provider_registry,
            strategy_factory=strategy_runner_from_configuration,
            history_factory=JsonLinesOperationHistoryRepository,
            unattended_grant_service=value.api._unattended_grants,
        )
        scheduling = TaskSchedulingService(value.repository, capacity=10)
        worker_id = f"run-once-worker-{len(value.repository.list_tasks())}"
        value.repository.register_worker(
            worker_id,
            "run-once-worker",
            60.0,
            ("organize",),
            None,
            None,
            SCHEMA_VERSION,
            self.clock.now,
        )

        def runner(task, claim, clock=None, heartbeat=None):
            state = scheduling.state(task.task_id)
            service.run(
                task,
                scheduling,
                claim,
                run_once=state.admission_trigger.value == "run_once",
                cancellation_check=lambda: False,
                clock=clock,
                heartbeat=heartbeat,
            )
            return task

        worker = ManualTaskEngineWorker(
            value.repository,
            scheduling,
            None,
            None,
            worker_id=worker_id,
            clock=self.clock,
            automatic_runner=runner,
        )
        finished = worker.run_next()
        self.assertIsNotNone(finished)
        return value.repository.get_task(finished.task_id)

    def cli_organize_execute(self, value, path: Path) -> tuple[int, str, str]:
        output, errors = io.StringIO(), io.StringIO()
        with patch(
            "mediaflow.final_cli.metadata_provider_registry_from_environment",
            return_value=value.provider_registry,
        ):
            code = final_main(
                [
                    "--config",
                    str(value.config),
                    "organize",
                    str(path),
                    "--execute",
                    "--limit",
                    "5",
                ],
                stdout=output,
                stderr=errors,
            )
        return code, output.getvalue(), errors.getvalue()


class RunOnceHistoryExclusionJourneyTests(_SourceHistoryJourneyTests):
    def test_run_once_excludes_failed_source_and_a_later_manual_success_lifts_it(self):
        """One real failure, then due-style exclusion, then manual success."""
        one = self.media("One.2001.mkv")
        two = self.media("Two.2002.mkv")
        with history_journey(self, operation="COPY") as value:
            # 1. A real Run once fails at the real OrganizerExecutor boundary
            #    before any mutation; both files record failed attempts.
            from mediaflow.application.organizer import OrganizerExecutor

            class _ExplodingExecutor(OrganizerExecutor):
                def execute(self, plan, storages, **kwargs):
                    raise RuntimeError("injected executor failure before any mutation")

            status, run = self.admit_run_once(value, "request-fail")
            self.assertEqual(202, status, run)
            with patch(
                "mediaflow.application.automation_definition_execution.OrganizerExecutor",
                _ExplodingExecutor,
            ):
                failed = self.execute_run_once(value)
            self.assertEqual("failed", failed.status.value, failed.error)
            failed_items = value.repository.list_items(failed.task_id)
            self.assertEqual(
                {TaskItemStatus.FAILED},
                {item.status for item in failed_items},
                failed_items,
            )

            # 2. The next Run once excludes both same-version failed files with
            #    one honest not-processed item each: no Result, no destination,
            #    no Provider call, no Storage mutation — and the aggregate never
            #    reads as a healthy completed run.
            status, second = self.admit_run_once(value, "request-exclude")
            self.assertEqual(202, status, second)
            with patch.object(
                value.provider_registry.resolve("tmdb"),
                "search_movie",
                side_effect=AssertionError("an excluded file must not query its Provider"),
            ) as provider_calls:
                excluded_run = self.execute_run_once(value)
            provider_calls.assert_not_called()
            self.assertEqual("partial_success", excluded_run.status.value, excluded_run.error)
            self.assertIn(
                "not processed by the automatic history gate",
                excluded_run.error or "",
                excluded_run,
            )
            self.assertIn("2 excluded", excluded_run.error or "")
            items = value.repository.list_items(excluded_run.task_id)
            self.assertEqual(2, len(items), items)
            for item in items:
                self.assertEqual(TaskItemStatus.SKIPPED, item.status, item)
                self.assertEqual(HISTORY_EXCLUDED_ITEM_STAGE, item.stage, item)
                self.assertIn("history gate", item.error or "", item)
            self.assertEqual((), value.repository.list_results(excluded_run.task_id))
            self.assertTrue(one.exists())
            self.assertTrue(two.exists())

            # 3. A deliberate manual CLI organize is never excluded by that
            #    history: the same file organizes normally under a new pin.
            code, output, errors = self.cli_organize_execute(value, one)
            self.assertEqual(0, code, errors + output)
            self.assertTrue(one.exists(), "COPY keeps the source in place")
            copied = [path for path in value.target_root.rglob("*.mkv")]
            self.assertEqual(1, len(copied), copied)

            # 4. The manual success is now the same version's latest formal
            #    outcome: the next Run once no longer excludes that file.
            status, third = self.admit_run_once(value, "request-lift")
            self.assertEqual(202, status, third)
            lifted = self.execute_run_once(value)
            lifted_items = value.repository.list_items(lifted.task_id)
            by_path = {item.source_path: item for item in lifted_items}
            self.assertIn("One.2001.mkv", by_path)
            self.assertNotEqual(
                HISTORY_EXCLUDED_ITEM_STAGE,
                by_path["One.2001.mkv"].stage,
                by_path["One.2001.mkv"],
            )
            # Two keeps its own failed history and stays excluded.
            self.assertEqual(
                HISTORY_EXCLUDED_ITEM_STAGE,
                by_path["Two.2002.mkv"].stage,
                by_path["Two.2002.mkv"],
            )
            # The original failure record was never rewritten by any of this.
            original = value.repository.get_task(failed.task_id)
            self.assertEqual("failed", original.status.value)
            self.assertEqual(
                2,
                len(value.repository.list_results(failed.task_id)),
                "the original failed results stay exactly as recorded",
            )


class DueOccurrenceHistoryExclusionJourneyTests(_SourceHistoryJourneyTests):
    def test_due_occurrence_excludes_the_failed_source_and_records_honest_no_work(self):
        from mediaflow.application.automation import IntervalScheduler
        from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
        from mediaflow.domain.automation import AutomationCommand, IntervalSchedule
        from mediaflow.final_cli import _automatic_task_runner

        one = self.media("One.2001.mkv")
        with history_journey(self, operation="COPY", definitions=None) as value:
            scheduling = TaskSchedulingService(value.repository, capacity=10)
            scheduler = IntervalScheduler(
                value.repository,
                (IntervalSchedule("legacy-interval", AutomationCommand.ORGANIZE, 60, 5),),
                scheduling_service=scheduling,
            )
            emitted = list(scheduler.tick(self.clock.now))
            self.assertEqual(1, len(emitted))

            from mediaflow.application.organizer import OrganizerExecutor

            class _ExplodingExecutor(OrganizerExecutor):
                def execute(self, plan, storages, **kwargs):
                    raise RuntimeError("injected executor failure before any mutation")

            value.repository.register_worker(
                "due-worker",
                "due-worker",
                60.0,
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
                worker_id="due-worker",
                clock=self.clock,
                automatic_runner=runner,
            )
            with (
                patch("mediaflow.final_cli._configuration", return_value=value.runtime),
                patch(
                    "mediaflow.application.automation_definition_execution.OrganizerExecutor",
                    _ExplodingExecutor,
                ),
            ):
                worker.run_next()
            (failed_task,) = [
                task
                for task in value.repository.list_tasks()
                if task.command == "organize" and task.item_limit == 5
            ]
            self.assertEqual("failed", failed_task.status.value, failed_task.error)
            (failed_item,) = value.repository.list_items(failed_task.task_id)
            self.assertEqual(TaskItemStatus.FAILED, failed_item.status)

            # The next due occurrence excludes the same-version failed source:
            # one honest not-processed item, zero effects, honest aggregate.
            self.clock.advance(60)
            emitted = list(scheduler.tick(self.clock.now))
            self.assertEqual(1, len(emitted))
            with patch("mediaflow.final_cli._configuration", return_value=value.runtime):
                worker.run_next()
            (excluded_task,) = [
                task
                for task in value.repository.list_tasks()
                if task.task_id not in {failed_task.task_id} and task.command == "organize"
            ]
            self.assertEqual("partial_success", excluded_task.status.value, excluded_task.error)
            self.assertIn("not processed by the automatic history gate", excluded_task.error or "")
            (excluded_item,) = value.repository.list_items(excluded_task.task_id)
            self.assertEqual(TaskItemStatus.SKIPPED, excluded_item.status, excluded_item)
            self.assertEqual(HISTORY_EXCLUDED_ITEM_STAGE, excluded_item.stage, excluded_item)
            self.assertEqual((), value.repository.list_results(excluded_task.task_id))
            self.assertTrue(one.exists())
            # The first due pass's real failure stays exactly as recorded.
            self.assertEqual(
                (failed_item,),
                value.repository.list_items(failed_task.task_id),
            )


class ManualHistoryWarningJourneyTests(_SourceHistoryJourneyTests):
    def test_failed_history_reaches_the_plan_summary_and_the_manual_request_executes(self):
        """The same failed file warns in the real Preview and organizes manually."""
        one = self.media("One.2001.mkv")
        with history_journey(self, operation="COPY") as value:
            # One real failed organize of this exact source version.
            from mediaflow.application.organizer import OrganizerExecutor

            class _ExplodingExecutor(OrganizerExecutor):
                def execute(self, plan, storages, **kwargs):
                    raise RuntimeError("injected executor failure before any mutation")

            with patch("mediaflow.final_cli.OrganizerExecutor", _ExplodingExecutor):
                code, _output, _errors = self.cli_organize_execute(value, one)
            self.assertEqual(1, code)
            (failed_task,) = value.repository.list_tasks()
            (failed_item,) = value.repository.list_items(failed_task.task_id)
            self.assertEqual(TaskItemStatus.FAILED, failed_item.status)
            (failed_result,) = value.repository.list_results(failed_task.task_id)

            # The deliberate new manual request reaches the real plan summary:
            # the item document carries the server-generated bounded warning.
            from tests.source_fixtures import source_identity_from_storage as identity_from

            identity = identity_from(value.source, "One.2001.mkv")
            intent = value.intents.create((identity,), actor="operator")
            intent = value.intents.update_choice(
                intent.intent_id,
                intent.items[0].item_id,
                {
                    "recognitionTypeId": "A",
                    "namingPolicyId": "A",
                    "classificationPolicyId": "A",
                    "organizePolicyId": "A",
                },
                expected_version=1,
                actor="operator",
            )
            preview = value.previews.create(
                intent.intent_id,
                expected_version=intent.version,
                expected_item_versions={intent.items[0].item_id: intent.items[0].version},
                actor="operator",
            )
            (item,) = preview.items
            self.assertEqual(ManualPreviewItemStatus.PREVIEWED, item.status, item.error)
            history = (item.plan or {}).get("history")
            self.assertIsInstance(history, dict, item.plan)
            self.assertEqual("failed", history["status"])
            self.assertIn("请核对来源、目标与存储实际效果后再确认本次整理", history["warning"])
            self.assertEqual(failed_result.created_at.isoformat(), history["recordedAt"])

            # A file without applicable history carries no history document.
            self.media("Two.2002.mkv")
            identity_two = identity_from(value.source, "Two.2002.mkv")
            intent_two = value.intents.create((identity_two,), actor="operator")
            intent_two = value.intents.update_choice(
                intent_two.intent_id,
                intent_two.items[0].item_id,
                {
                    "recognitionTypeId": "A",
                    "namingPolicyId": "A",
                    "classificationPolicyId": "A",
                    "organizePolicyId": "A",
                },
                expected_version=1,
                actor="operator",
            )
            preview_two = value.previews.create(
                intent_two.intent_id,
                expected_version=intent_two.version,
                expected_item_versions={intent_two.items[0].item_id: intent_two.items[0].version},
                actor="operator",
            )
            (item_two,) = preview_two.items
            self.assertIsNone((item_two.plan or {}).get("history"))

            # The manual request is not vetoed by the failed history: the same
            # file executes normally under its new exact plan.
            code, output, errors = self.cli_organize_execute(value, one)
            self.assertEqual(0, code, errors + output)
            # The old record keeps its exact facts; the new work records its own.
            self.assertEqual(
                (failed_result,),
                value.repository.list_results(failed_task.task_id),
                "the original failure Result is never rewritten or replayed",
            )
            self.assertEqual("failed", value.repository.get_task(failed_task.task_id).status.value)


class PartialItemIsHistoryNotOwnerTests(_SourceHistoryJourneyTests):
    def test_recorded_failed_or_partial_item_no_longer_blocks_new_manual_work(self):
        """A decided file item is history; an unfinished sibling still owns its source.

        The durable states are published through the production publication
        boundary (claim → recorded outcome), so the ownership answer here is
        the same one every entrance reads.
        """

        with history_journey(self, operation="COPY") as value:
            repository = value.repository
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("organize", execute_authorized=True)
            self.media("One.2001.mkv")
            identity = source_identity_from_storage(value.source, "One.2001.mkv")
            item = coordinator.begin_item(
                task.task_id,
                identity.storage_id,
                identity.resource_library_id,
                identity.path,
                identity.filename,
                source_occurrence_id=identity.occurrence_id,
                source_fingerprint=identity.fingerprint,
                source_fingerprint_state=identity.occurrence_state,
                source_storage_path=identity.path,
            )
            # Still processing: the normal mutual exclusion holds.
            owner = repository.find_owned_source_work(
                storage_id=identity.storage_id,
                source_path=identity.path,
                storage_path=identity.path,
                resource_library_id=identity.resource_library_id,
                source_fingerprint=identity.fingerprint,
            )
            self.assertIsNotNone(owner)
            self.assertEqual(task.task_id, owner["taskId"])

            # The item records its own terminal PARTIAL outcome through the
            # production publication boundary (an attachment failure shape:
            # primary completed, uncertain effect recorded).
            from dataclasses import replace as dataclass_replace
            from datetime import datetime as _datetime

            now = _datetime.now(UTC)
            partial = dataclass_replace(
                item,
                status=TaskItemStatus.PARTIAL,
                stage="failed",
                updated_at=now,
                destination_storage_id="target",
                destination_path="Organized/Movies/One (2001)/One (2001).mkv",
            )
            repository.append_result(
                PersistentResultRecord(
                    f"{item.item_id}:{item.attempts}",
                    task.task_id,
                    item.item_id,
                    identity.storage_id,
                    identity.path,
                    "target",
                    "Organized/Movies/One (2001)/One (2001).mkv",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "COPY",
                    "partial",
                    now,
                    completed_operations=("copy_primary",),
                    effect_certainty="attempted_unverified",
                    uncertain_effects=("source_cleanup",),
                    primary_completed=True,
                )
            )
            repository.upsert_item(partial)
            self.assertIsNone(
                repository.find_owned_source_work(
                    storage_id=identity.storage_id,
                    source_path=identity.path,
                    storage_path=identity.path,
                    resource_library_id=identity.resource_library_id,
                    source_fingerprint=identity.fingerprint,
                ),
                "a recorded partial file item is history, never a permanent veto",
            )
            # The parent Task still running cannot reclassify the decided file.
            history = latest_applicable_outcome(
                repository,
                storage_id=identity.storage_id,
                source_path=identity.path,
                storage_path=identity.path,
                resource_library_id=identity.resource_library_id,
                source_fingerprint=identity.fingerprint,
            )
            self.assertIsNotNone(history)
            self.assertEqual("partial", history.status)
            self.assertTrue(history.excludes_automatically)
            self.assertEqual(("source_cleanup",), history.uncertain_effects)


if __name__ == "__main__":
    unittest.main()
