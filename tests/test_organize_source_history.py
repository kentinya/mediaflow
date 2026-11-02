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
import threading
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from mediaflow.application.automation_run_once import AutomationRunOnceService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.media_discovery import MediaDiscoveryService
from mediaflow.application.organize_source_history import (
    latest_applicable_outcome,
)
from mediaflow.application.strategy_test import SyntheticMetadataProvider
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
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.domain.task_persistence import (
    HISTORY_EXCLUDED_ITEM_STAGE,
    HISTORY_UNAVAILABLE_ITEM_STAGE,
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.domain.task_scheduling import (
    ScheduledTaskClaim,
    TaskClaimFenceLost,
    TaskQueueState,
    TaskSchedulingError,
)
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.source_fixtures import source_identity_from_storage
from tests.test_media_discovery import _DiscoveryFixture

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
def history_journey(
    case,
    *,
    operation: str = "COPY",
    definitions: str | None = "nightly",
    task_scheduling: bool = False,
):
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
                task_scheduling_enabled=task_scheduling,
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

    def _seed_manual_outcome(
        self,
        *,
        created_at: datetime,
        result_status: str = "PARTIAL",
        completed_operations: tuple[str, ...] = ("CREATE_DIRECTORY",),
        effect_certainty: str = "attempted_unverified",
        uncertain_effects: tuple[str, ...] = ("mutation_outcome",),
        fingerprint: str | None = "f" * 64,
    ) -> tuple[PersistentTask, PersistentTaskItem, PersistentResultRecord]:
        """One real manual-organize outcome: a UUID Result linked through the
        durable ``manual_execution_items.result_id`` edge, exactly like the
        production Files execution writes it."""

        coordinator = PersistentTaskCoordinator(self.repository, self.repository)
        task = coordinator.create("manual_organize", execute_authorized=True)
        item = PersistentTaskItem(
            f"manual-item-{created_at.timestamp()}",
            task.task_id,
            "source",
            "library",
            "One.2001.mkv",
            "One.2001.mkv",
            TaskItemStatus.PARTIAL,
            "uncertain_effects",
            1,
            created_at,
            created_at,
            source_storage_path="One.2001.mkv",
            source_fingerprint=fingerprint,
            source_fingerprint_state="verified" if fingerprint else "unverified",
        )
        self.repository.upsert_item(item)
        result = PersistentResultRecord(
            str(uuid4()),
            task.task_id,
            item.item_id,
            "source",
            "One.2001.mkv",
            "target",
            "Organized/One (2001)/One (2001).mkv",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "COPY",
            result_status,
            created_at,
            error="injected mid-write failure",
            completed_operations=completed_operations,
            effect_certainty=effect_certainty,
            uncertain_effects=uncertain_effects,
        )
        self.repository.append_result(result)
        self.repository._connection.execute(
            "INSERT INTO manual_execution_items ("
            "execution_item_id, execution_id, preview_id, preview_item_id, intent_id, "
            "item_id, task_id, task_item_id, item_version, source_fingerprint, "
            "plan_fingerprint, source_json, choice_json, plan_json, status, stage, "
            "result_id, effect_certainty, completed_operations, uncertain_effects, "
            "error, next_action, created_at, updated_at"
            ") VALUES (?, 'execution', 'preview', 'preview-item', 'intent', 'intent-item', "
            "?, ?, 1, ?, 'plan-fingerprint', '{}', '{}', '{}', 'failed', "
            "'uncertain_effects', ?, ?, ?, ?, ?, 'inspect the recorded effects', ?, ?)",
            (
                f"exec-item-{created_at.timestamp()}",
                task.task_id,
                item.item_id,
                fingerprint or "",
                result.result_id,
                effect_certainty,
                json.dumps(list(completed_operations)),
                json.dumps(list(uncertain_effects)),
                "injected mid-write failure",
                created_at.isoformat(),
                created_at.isoformat(),
            ),
        )
        return task, item, result

    def test_manual_uuid_result_evidence_is_read_not_dropped(self):
        """The manual Result edge carries the real effect facts (AC-T3/T5)."""

        base = datetime(2026, 1, 1, tzinfo=UTC)
        _task, item, _result = self._seed_manual_outcome(created_at=base)
        outcome = self._query_outcome()
        self.assertIsNotNone(outcome)
        self.assertEqual("result", outcome.outcome_kind)
        self.assertEqual("partial", outcome.status, "status case is unified")
        self.assertTrue(outcome.excludes_automatically)
        self.assertEqual(item.item_id, outcome.outcome_id)
        self.assertEqual(("CREATE_DIRECTORY",), outcome.completed_operations)
        self.assertEqual("attempted_unverified", outcome.effect_certainty)
        self.assertEqual(("mutation_outcome",), outcome.uncertain_effects)
        self.assertEqual("target", outcome.destination_storage_id)

    def test_population_beyond_400_rows_still_reaches_the_latest_applicable(self):
        """No display-page or single-batch bound replaces the real population."""

        base = datetime(2026, 1, 1, tzinfo=UTC)
        # 449 newer attempts of genuinely replaced versions...
        for index in range(449):
            self._seed_outcome(
                item_status=TaskItemStatus.SUCCESS,
                result_status="success",
                fingerprint=f"{index:064x}",
                created_at=base + timedelta(minutes=1000 + index),
            )
        # ...and the only applicable failed outcome, older than every one.
        self._seed_outcome(
            item_status=TaskItemStatus.FAILED,
            result_status="failed",
            created_at=base,
        )
        outcome = self._query_outcome()
        self.assertIsNotNone(outcome, "the complete matching population is read across batches")
        self.assertEqual("failed", outcome.status)

    def test_manual_result_beyond_the_first_batch_is_still_found(self):
        """Keyset pagination reaches a manual UUID outcome past row 400."""

        base = datetime(2026, 1, 1, tzinfo=UTC)
        for index in range(405):
            self._seed_outcome(
                item_status=TaskItemStatus.SUCCESS,
                result_status="success",
                fingerprint=f"{index:064x}",
                created_at=base + timedelta(minutes=1000 + index),
            )
        _task, item, _result = self._seed_manual_outcome(created_at=base)
        outcome = self._query_outcome()
        self.assertIsNotNone(outcome)
        self.assertEqual("result", outcome.outcome_kind)
        self.assertEqual(item.item_id, outcome.outcome_id)
        self.assertEqual(("CREATE_DIRECTORY",), outcome.completed_operations)


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

            # The same facts reach the operator through the real authenticated
            # Preview GET: the bounded projection publishes them, so the Web
            # summary banner is fed by the actual API, not by client invention.
            status, document = self.request(
                value, "GET", f"/api/v1/operations/organize/previews/{preview.preview_id}"
            )
            self.assertEqual(200, status, document)
            (api_item,) = document["items"]
            api_history = (api_item.get("plan") or {}).get("history")
            self.assertIsInstance(api_history, dict, api_item.get("plan"))
            self.assertEqual("failed", api_history["status"])
            self.assertEqual(failed_result.created_at.isoformat(), api_history["recordedAt"])
            self.assertIn("请核对来源", api_history["warning"])
            self.assertTrue(api_history["versionApplicable"])

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


class AutomaticAdmissionHistoryRaceTests(_SourceHistoryJourneyTests):
    """The decisive automatic admission re-reads history inside its transaction.

    B review of ``3fb10500`` reproduced the gap: the automatic pass read "no
    applicable history", a deliberate Files organize of the same version then
    recorded a real ``PARTIAL``/``attempted_unverified`` outcome, and the resumed
    automatic pass still copied the file.  The synchronization point here is the
    real admission boundary (``begin_scheduled_item_with_ownership``), which is
    the only remaining gap before the decisive transaction; the manual work is a
    real Files admission → analysis → exact summary → selected confirmation over
    real LocalStorage whose write fails for real.
    """

    def test_manual_partial_recorded_before_the_automatic_admission_excludes_the_source(self):
        self.media("One.2001.mkv")
        self.media("Two.2002.mkv")
        with history_journey(self, operation="COPY", task_scheduling=True) as value:
            from mediaflow.application.manual_task_engine import ManualTaskEngineWorker

            status, automatic = self.admit_run_once(value, "automatic-history-race")
            self.assertEqual(202, status, automatic)
            auto_id = automatic["taskId"]

            at_admission = threading.Event()
            resume = threading.Event()
            errors: list[BaseException] = []
            boundary = value.repository.begin_scheduled_item_with_ownership

            def held_admission(fence, item, **kwargs):
                if (
                    threading.current_thread().name == "automatic-race-worker"
                    and item.source_path == "One.2001.mkv"
                    and not at_admission.is_set()
                ):
                    at_admission.set()
                    if not resume.wait(20):
                        raise AssertionError("the manual request never released the boundary")
                return boundary(fence, item, **kwargs)

            provider = value.provider_registry.resolve("tmdb")
            real_search = provider.search_movie
            searches: list[str] = []

            def recording_search(query, *args, **kwargs):
                searches.append(str(getattr(query, "title", query)))
                return real_search(query, *args, **kwargs)

            def automatic_worker():
                try:
                    self.execute_run_once(value)
                except BaseException as error:  # noqa: BLE001 - reported below
                    errors.append(error)

            with (
                patch.object(
                    value.repository,
                    "begin_scheduled_item_with_ownership",
                    side_effect=held_admission,
                ),
                patch.object(provider, "search_movie", side_effect=recording_search),
            ):
                thread = threading.Thread(
                    target=automatic_worker, name="automatic-race-worker", daemon=True
                )
                thread.start()
                try:
                    self.assertTrue(at_admission.wait(10), errors)
                    # The automatic pass has run everything before this file's
                    # decisive admission, but has not registered its item yet.
                    self.assertNotIn(
                        "One.2001.mkv",
                        {item.source_path for item in value.repository.list_items(auto_id)},
                    )

                    # A deliberate Files request for the same version, through
                    # the real API and the real manual Task engine.
                    value.api._manual_execution._clock = self.clock
                    status, admitted = self.request(
                        value,
                        "POST",
                        "/api/v1/resource-libraries/library/files/discoveries",
                        {
                            "paths": ["One.2001.mkv"],
                            "autoPrepare": True,
                            "requestId": "11111111-1111-4111-8111-111111111111",
                        },
                    )
                    self.assertEqual(202, status, admitted)
                    manual_id = admitted["organizeTaskId"]
                    value.repository.register_worker(
                        "manual-race-worker",
                        "manual-race-worker",
                        60.0,
                        ("manual_organize",),
                        None,
                        None,
                        SCHEMA_VERSION,
                        self.clock.now,
                    )
                    worker = ManualTaskEngineWorker(
                        value.repository,
                        TaskSchedulingService(
                            value.repository, capacity=100, locks=value.repository
                        ),
                        value.discovery,
                        value.api._manual_execution,
                        worker_id="manual-race-worker",
                        clock=self.clock,
                        notice=lambda line: None,
                    )
                    for _ in range(12):
                        worker.run_next()
                        state = value.repository.get_task_scheduling(manual_id)
                        if state is not None and state.queue_state in {
                            TaskQueueState.WAITING_HUMAN,
                            TaskQueueState.SETTLED,
                        }:
                            break
                    discovery = value.repository.get_media_discovery_for_task(manual_id)
                    self.assertIsNotNone(discovery, "the manual request reached its summary")
                    status, preview = self.request(
                        value,
                        "GET",
                        f"/api/v1/operations/organize/previews/{discovery.preview_id}",
                    )
                    self.assertEqual(200, status, preview)
                    status, _confirmed = self.request(
                        value,
                        "POST",
                        f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
                        {
                            "confirmation": True,
                            "itemIds": [
                                item["itemId"]
                                for item in preview["items"]
                                if item["status"] == "previewed"
                            ],
                            "expectedIntentVersion": preview["intentVersion"],
                            "allowOverwrite": False,
                            "allowSourceCleanup": False,
                        },
                    )
                    self.assertIn(status, (200, 202))

                    def fail_write(path, *args, **kwargs):
                        raise StorageError(
                            StorageErrorCode.PERMISSION_DENIED,
                            "write",
                            path,
                            "injected write failure during the automatic admission gap",
                        )

                    with patch.object(value.target, "write", side_effect=fail_write):
                        for _ in range(4):
                            worker.run_next()
                    (manual_result,) = value.repository.list_results(manual_id)
                    self.assertEqual("PARTIAL", manual_result.status)
                    self.assertEqual("attempted_unverified", manual_result.effect_certainty)
                    self.assertFalse(list(value.target_root.rglob("*.mkv")))
                    manual_task = value.repository.get_task(manual_id)
                    searches_before_resume = tuple(searches)
                finally:
                    resume.set()
                    thread.join(20)
            self.assertFalse(thread.is_alive())
            self.assertEqual([], errors, errors)

            # The automatic admission now re-reads the same version's latest
            # formal outcome inside its transaction: the manual PARTIAL that
            # landed in the gap excludes the file with one terminal row.
            by_path = {item.source_path: item for item in value.repository.list_items(auto_id)}
            self.assertEqual({"One.2001.mkv", "Two.2002.mkv"}, set(by_path), by_path)
            excluded = by_path["One.2001.mkv"]
            self.assertIs(TaskItemStatus.SKIPPED, excluded.status)
            self.assertEqual(HISTORY_EXCLUDED_ITEM_STAGE, excluded.stage)
            self.assertIn("partial", excluded.error or "")
            sibling = by_path["Two.2002.mkv"]
            self.assertIs(TaskItemStatus.SUCCESS, sibling.status)

            # The excluded file consumed no Provider call and produced no
            # formal Result or media; the free sibling was processed normally.
            new_searches = tuple(searches[len(searches_before_resume) :])
            self.assertNotIn("One", new_searches)
            (automatic_result,) = value.repository.list_results(auto_id)
            self.assertEqual("Two.2002.mkv", automatic_result.source_path)
            self.assertEqual(
                ["Two (2002).mkv"],
                sorted(path.name for path in value.target_root.rglob("*.mkv")),
            )
            automatic_task = value.repository.get_task(auto_id)
            self.assertEqual("partial_success", automatic_task.status.value)
            self.assertIn("not processed by the automatic history gate", automatic_task.error or "")

            # The manual run's own recorded facts are untouched by the new work.
            self.assertEqual((manual_result,), value.repository.list_results(manual_id))
            self.assertEqual(manual_task, value.repository.get_task(manual_id))

    def test_unreadable_history_fails_closed_and_processes_nothing(self):
        self.media("One.2001.mkv")
        with history_journey(self, operation="COPY") as value:
            status, automatic = self.admit_run_once(value, "automatic-history-unreadable")
            self.assertEqual(202, status, automatic)
            auto_id = automatic["taskId"]
            provider = value.provider_registry.resolve("tmdb")
            with (
                patch.object(
                    value.repository,
                    "latest_organize_source_outcome",
                    side_effect=RuntimeError("injected history read failure"),
                ),
                patch.object(
                    provider,
                    "search_movie",
                    side_effect=AssertionError("a fail-closed file must not query its Provider"),
                ),
            ):
                finished = self.execute_run_once(value)
            (item,) = value.repository.list_items(auto_id)
            self.assertIs(TaskItemStatus.SKIPPED, item.status)
            self.assertEqual(HISTORY_UNAVAILABLE_ITEM_STAGE, item.stage)
            self.assertIn("fail-closed", item.error or "")
            self.assertEqual((), value.repository.list_results(auto_id))
            self.assertFalse(list(value.target_root.rglob("*.mkv")))
            self.assertEqual("partial_success", finished.status.value)
            self.assertIn("not processed by the automatic history gate", finished.error or "")


class _SupersededHandoffFixture(_DiscoveryFixture):
    """The real Files → Task engine fixture with COPY policies, shared by the
    per-file hand-off journeys (AC-T4/AC-23).  The admission/summary/execute
    helpers are the production entrance helpers of the Files manual journeys.
    """

    def document(self, **kwargs):
        doc = super().document(**kwargs)
        for policy in doc["organizePolicies"]:
            policy["operation"] = "COPY"
        return doc

    def _admit(self, value, paths, *, auto_prepare=True, request_id="handoff-request"):
        return self.request(
            value,
            "/api/v1/resource-libraries/library/files/discoveries",
            "POST",
            {"paths": list(paths), "autoPrepare": auto_prepare, "requestId": request_id},
        )

    def _drive(self, value, task_id, *, steps=12):
        from mediaflow.domain.task_scheduling import TaskQueueState as _TQS

        for _ in range(steps):
            value.task_engine.run_next()
            discovery = value.repository.get_media_discovery_for_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            if discovery is None or state is None:
                continue
            if state.queue_state in {
                _TQS.WAITING_HUMAN,
                _TQS.PAUSED,
                _TQS.SETTLED,
            }:
                return discovery
        return value.repository.get_media_discovery_for_task(task_id)

    def _execute(self, value, task_id, preview, item_ids, *, steps=8):
        from mediaflow.domain.task_persistence import PersistentTaskStatus as _PTS

        self.confirm(value, preview, item_ids)
        for _ in range(steps):
            value.task_engine.run_next()
            task = value.repository.get_task(task_id)
            if task.status in {
                _PTS.COMPLETED,
                _PTS.PARTIAL_SUCCESS,
                _PTS.FAILED,
                _PTS.CANCELLED,
            }:
                break
        return value.repository.get_task(task_id)

    def confirm(self, value, preview, item_ids=None):
        """The ordinary selected confirmation through the real authenticated API."""

        selected = item_ids or [
            item["itemId"] for item in preview["items"] if item["status"] == "previewed"
        ]
        status, reply = self.request(
            value,
            f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
            "POST",
            {
                "confirmation": True,
                "itemIds": selected,
                "expectedIntentVersion": preview["intentVersion"],
                "allowOverwrite": False,
                "allowSourceCleanup": False,
            },
        )
        self.assertIn(status, (200, 202), reply)
        return reply

    def summary(self, value, paths, request_id):
        """One real Files admission through its analysis to the exact summary."""

        status, admitted = self._admit(value, paths, request_id=request_id)
        self.assertEqual(202, status, admitted)
        task_id = admitted["organizeTaskId"]
        discovery = self._drive(value, task_id)
        status, preview = self.request(
            value, f"/api/v1/operations/organize/previews/{discovery.preview_id}"
        )
        self.assertEqual(200, status, preview)
        return task_id, preview

    def scheduling(self, value):
        from mediaflow.application.task_scheduling import TaskSchedulingService

        return TaskSchedulingService(value.repository, capacity=100, locks=value.repository)

    def superseded_marker(self, value, item_id):
        row = value.repository._connection.execute(
            "SELECT superseded_by_task_id FROM task_items WHERE item_id=?", (item_id,)
        ).fetchone()
        return None if row is None else row["superseded_by_task_id"]


class SupersededSingleFileOwnerHandoffTests(_SupersededHandoffFixture):
    def test_finished_failed_batch_releases_its_slot_before_any_new_manual_work(self):
        """One failed file ends the batch: the recorded unknown effect is
        history, so the slot is released at once and a later manual organize
        starts new work without rewriting a single recorded fact."""

        self.media("Movies/One.2001.mkv")
        provider = SyntheticMetadataProvider(
            (MediaCandidate("tmdb", "201", MediaType.MOVIE, "One", year=2001),)
        )
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            old_id, _preview = self.summary(
                value, ["Movies/One.2001.mkv"], "11111111-1111-4111-8111-111111111111"
            )

            def fail_write(path, *args, **kwargs):
                raise StorageError(
                    StorageErrorCode.PERMISSION_DENIED, "write", path, "injected write failure"
                )

            with patch.object(value.target, "write", side_effect=fail_write):
                self._execute(
                    value,
                    old_id,
                    _preview,
                    [item["itemId"] for item in _preview["items"] if item["status"] == "previewed"],
                )
            old_task = value.repository.get_task(old_id)
            self.assertEqual(PersistentTaskStatus.FAILED, old_task.status)
            (old_item,) = value.repository.list_items(old_id)
            (old_result,) = value.repository.list_results(old_id)
            self.assertEqual("PARTIAL", old_result.status)
            self.assertEqual(("CREATE_DIRECTORY",), old_result.completed_operations)
            self.assertEqual("attempted_unverified", old_result.effect_certainty)
            old_state = value.repository.get_task_scheduling(old_id)
            # Every file of the pass is terminal and its own call returned, so
            # the batch no longer occupies a slot merely because the recorded
            # effect is unknown.  The Result, its steps and its uncertainty are
            # the only facts that stay.
            self.assertEqual(TaskQueueState.SETTLED, old_state.queue_state)
            self.assertIsNone(old_state.mutation_state)
            self.assertFalse(old_state.holds_capacity)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            # The old execution eligibility is closed: the released state owns
            # no claim, so a stale owner frame can only be rejected.
            self.assertIsNone(old_state.claim_token)
            stale_claim = ScheduledTaskClaim(
                old_task,
                replace(
                    old_state,
                    queue_state=TaskQueueState.CLAIMED,
                    claim_worker_id="old-worker",
                    claim_token="old-token",
                    claimed_at=self.clock.now,
                    claim_expires_at=self.clock.now + timedelta(seconds=30),
                    heartbeat_at=self.clock.now,
                ),
            )
            with self.assertRaises(TaskClaimFenceLost):
                self.scheduling(value).heartbeat(stale_claim, now=self.clock.now)

            # The deliberate new Files organize of the same file reaches the
            # real summary with the server-generated history warning.
            _new_id, fresh = self.summary(
                value, ["Movies/One.2001.mkv"], "22222222-2222-4222-8222-222222222222"
            )
            (fresh_item,) = fresh["items"]
            history = (fresh_item.get("plan") or {}).get("history")
            self.assertIsInstance(history, dict, fresh_item.get("plan"))
            self.assertEqual("partial", history["status"])
            self.assertEqual(("CREATE_DIRECTORY",), tuple(history["completedOperations"]))
            self.assertEqual(("mutation_outcome",), tuple(history["uncertainEffects"]))
            self.assertIn("请核对", history["warning"])

            # The ordinary selected confirmation starts genuinely new work.
            self.confirm(value, fresh)
            for _ in range(4):
                value.task_engine.run_next()
            new_state = value.repository.get_task_scheduling(_new_id)
            self.assertIsNotNone(new_state)
            self.assertEqual(
                PersistentTaskStatus.COMPLETED,
                value.repository.get_task(_new_id).status.value,
            )
            self.assertTrue(
                any(path.name == "One (2001).mkv" for path in self.target_root.rglob("*.mkv"))
            )

            # A settled owner is pure history: no hand-off marker is needed to
            # release anything, and the old batch was already off the slot
            # before the operator asked again.
            self.assertIsNone(self.superseded_marker(value, old_item.item_id))
            settled_state = value.repository.get_task_scheduling(old_id)
            self.assertEqual(TaskQueueState.SETTLED, settled_state.queue_state)
            self.assertIsNone(settled_state.mutation_state)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            # Every recorded fact of the old run is untouched.
            (kept_result,) = value.repository.list_results(old_id)
            self.assertEqual(old_result, kept_result)
            (kept_item,) = value.repository.list_items(old_id)
            self.assertEqual(
                (TaskItemStatus.PARTIAL, "uncertain_effects", 1),
                (kept_item.status, kept_item.stage, kept_item.attempts),
            )


class SupersededOwnerWithRemainingWorkTests(_SupersededHandoffFixture):
    def test_owner_with_remaining_machine_work_keeps_its_slot_and_is_fenced_per_file(self):
        """A batch [One, Two] with One failed and Two still undecided: the new
        organize of One hands the file over, the old owner keeps its one slot
        and its live claim, its late One-publication is refused, and Two's
        legitimate work continues on the same Task."""

        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate("tmdb", "201", MediaType.MOVIE, "One", year=2001),
                MediaCandidate("tmdb", "202", MediaType.MOVIE, "Two", year=2002),
            )
        )
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            old_id, preview = self.summary(
                value,
                ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"],
                "11111111-1111-4111-8111-111111111111",
            )
            items_by_name = {
                item["source"]["filename"]: item["itemId"] for item in preview["items"]
            }

            def fail_write(path, *args, **kwargs):
                raise StorageError(
                    StorageErrorCode.PERMISSION_DENIED, "write", path, "injected write failure"
                )

            with patch.object(value.target, "write", side_effect=fail_write):
                # Both sources are confirmed in one execution: One's mid-write
                # failure records its terminal uncertain outcome, and Two's
                # own write then fails mid-mutation, leaving its unverified
                # boundary retained — the batch's genuinely unfinished call.
                self._execute(
                    value,
                    old_id,
                    preview,
                    [items_by_name["One.2001.mkv"], items_by_name["Two.2002.mkv"]],
                )
            (old_one,) = [
                item
                for item in value.repository.list_items(old_id)
                if item.stage == "uncertain_effects"
            ]
            # Two is the batch's still-queued machine work: it never recorded
            # its own terminal outcome, so the hand-off must not touch it.
            (old_two,) = [
                item
                for item in value.repository.list_items(old_id)
                if item.status is TaskItemStatus.PROCESSING
            ]
            self.assertEqual("Movies/Two.2002.mkv", old_two.source_path)
            (old_one_result,) = value.repository.list_results(old_id)
            old_state = value.repository.get_task_scheduling(old_id)
            self.assertEqual(TaskQueueState.CLAIMED, old_state.queue_state)
            self.assertIsNotNone(old_state.mutation_state)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())
            old_claim = ScheduledTaskClaim(value.repository.get_task(old_id), old_state)

            # The new Files organize of One: warned summary, ordinary confirm.
            _new_id, fresh = self.summary(
                value, ["Movies/One.2001.mkv"], "22222222-2222-4222-8222-222222222222"
            )
            (fresh_item,) = fresh["items"]
            self.assertIsInstance((fresh_item.get("plan") or {}).get("history"), dict)
            self.confirm(value, fresh)

            # Immediately at the hand-off instant, before any further engine
            # pass: the old owner keeps its one slot and its live claim (the
            # second slot is the new Task's own queued execution).
            kept_state = value.repository.get_task_scheduling(old_id)
            self.assertEqual(TaskQueueState.CLAIMED, kept_state.queue_state)
            self.assertIsNone(kept_state.mutation_state, "One's boundary is resolved")
            self.assertIsNotNone(kept_state.claim_token)
            self.assertEqual(2, value.repository.count_scheduled_capacity_use())
            self.assertEqual(_new_id, self.superseded_marker(value, old_one.item_id))
            # The old owner's heartbeat stays valid: it still legitimately
            # owns its remaining work, so the whole batch is never fenced.
            self.scheduling(value).heartbeat(old_claim, now=self.clock.now)

            # The old owner's live claim cannot publish One any more: the
            # per-file fence refuses the late outcome while the claim itself
            # is still valid.
            late_frame = replace(
                old_one,
                status=TaskItemStatus.PROCESSING,
                stage="organizing",
            )
            with self.assertRaises(TaskSchedulingError) as refused:
                self.scheduling(value).complete_item(
                    ScheduledTaskClaim(value.repository.get_task(old_id), kept_state),
                    late_frame,
                    result=PersistentResultRecord(
                        f"{old_one.item_id}:{old_one.attempts}",
                        old_id,
                        old_one.item_id,
                        "source",
                        old_one.source_path,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        "COPY",
                        "FAILED",
                        self.clock.now,
                    ),
                    now=self.clock.now,
                )
            self.assertIn("handed off", str(refused.exception))

            # The new work itself completed.
            for _ in range(4):
                value.task_engine.run_next()
            self.assertEqual(
                PersistentTaskStatus.COMPLETED, value.repository.get_task(_new_id).status.value
            )

            # Two's unfinished call keeps the original safety boundary: the
            # old batch still holds its own slot (its takeover/recovery is the
            # existing interrupted-execution path, untouched here), and One is
            # never replayed by the old owner.
            after = value.repository.get_task_scheduling(old_id)
            self.assertEqual(TaskQueueState.CLAIMED, after.queue_state)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())
            self.assertEqual(
                (old_one_result,),
                value.repository.list_results(old_id)[:1],
                "One's original failure Result stays first and unchanged",
            )
            self.assertEqual(
                {"One (2001).mkv"},
                {path.name for path in self.target_root.rglob("*.mkv")},
                "only the new confirmed organize produced media",
            )


class FinishedBatchCapacityTests(_SupersededHandoffFixture):
    """Slice 47 capacity rule: one Task holds at most one slot, and a finished
    batch gives it back even when a recorded effect stays unknown.

    Every journey goes through the real Files admission → analysis → selected
    confirmation → Task engine → LocalStorage boundary; failures are injected at
    the real Storage call, never by hand-writing Task/Result rows.  A batch that
    still owns queued/processing machine work is covered by
    ``SupersededOwnerWithRemainingWorkTests``.
    """

    def _confirmed_batch(self, value, paths, request_id):
        task_id, preview = self.summary(value, paths, request_id)
        return (
            task_id,
            preview,
            [item["itemId"] for item in preview["items"] if item["status"] == "previewed"],
        )

    def _drive_until_terminal(self, value, task_id):
        for _ in range(8):
            value.task_engine.run_next()
            task = value.repository.get_task(task_id)
            if task.status in {
                PersistentTaskStatus.COMPLETED,
                PersistentTaskStatus.PARTIAL_SUCCESS,
                PersistentTaskStatus.FAILED,
                PersistentTaskStatus.CANCELLED,
            }:
                return task
        return value.repository.get_task(task_id)

    def test_all_success_batch_releases_its_single_slot(self):
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate("tmdb", "301", MediaType.MOVIE, "One", year=2001),
                MediaCandidate("tmdb", "302", MediaType.MOVIE, "Two", year=2002),
            )
        )
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            task_id, preview, selected = self._confirmed_batch(
                value,
                ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"],
                "33333333-3333-4333-8333-333333333333",
            )
            self.assertEqual(2, len(selected))
            observed = []
            original_write = value.target.write

            def one_slot_per_task(path, data, **kwargs):
                observed.append(value.repository.count_scheduled_capacity_use())
                return original_write(path, data, **kwargs)

            with patch.object(value.target, "write", one_slot_per_task):
                self.confirm(value, preview)
                task = self._drive_until_terminal(value, task_id)
            self.assertEqual(PersistentTaskStatus.COMPLETED, task.status)
            # Two files of one Task never occupy two slots.
            self.assertEqual({1}, set(observed))
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual(TaskQueueState.SETTLED, state.queue_state)
            self.assertIsNone(state.claim_token)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual(
                {TaskItemStatus.SUCCESS},
                {item.status for item in value.repository.list_items(task_id)},
            )

    def test_failure_before_any_effect_releases_its_single_slot(self):
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate("tmdb", "311", MediaType.MOVIE, "One", year=2001),
                MediaCandidate("tmdb", "312", MediaType.MOVIE, "Two", year=2002),
            )
        )
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            task_id, preview, _selected = self._confirmed_batch(
                value,
                ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"],
                "44444444-4444-4444-8444-444444444444",
            )
            # A zero-effect failure injected at the real executor boundary: the
            # last item's own call returns a definite ``none`` outcome, so no
            # mutation boundary is ever left behind and the finished batch must
            # give its one slot back.
            from mediaflow.domain.organizer import (
                ExecutionEffectCertainty,
                ExecutionResult,
                ExecutionStatus,
            )

            original_execute = value.executions._execute_plan

            def fail_two_without_effect(plan, storages):
                if "Two" in plan.source:
                    return ExecutionResult(
                        ExecutionStatus.FAILED,
                        plan.operation,
                        plan.source,
                        plan.target,
                        plan_id=plan.plan_id,
                        resolved_destination=plan.target,
                        errors=("injected zero-effect executor failure",),
                        effect_certainty=ExecutionEffectCertainty.NONE,
                    )
                return original_execute(plan, storages)

            with patch.object(value.executions, "_execute_plan", fail_two_without_effect):
                self.confirm(value, preview)
                task = self._drive_until_terminal(value, task_id)
            self.assertEqual(PersistentTaskStatus.PARTIAL_SUCCESS, task.status)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual(TaskQueueState.SETTLED, state.queue_state)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            statuses = {
                item.source_path: item.status for item in value.repository.list_items(task_id)
            }
            self.assertEqual(TaskItemStatus.SUCCESS, statuses["Movies/One.2001.mkv"])
            self.assertEqual(TaskItemStatus.FAILED, statuses["Movies/Two.2002.mkv"])
            (failed,) = [
                result
                for result in value.repository.list_results(task_id)
                if result.source_path == "Movies/Two.2002.mkv"
            ]
            self.assertEqual("none", failed.effect_certainty)
            self.assertEqual((), failed.uncertain_effects)

    def test_terminal_partial_unknown_batch_releases_and_keeps_its_evidence(self):
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate("tmdb", "321", MediaType.MOVIE, "One", year=2001),
                MediaCandidate("tmdb", "322", MediaType.MOVIE, "Two", year=2002),
            )
        )
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            task_id, preview, _selected = self._confirmed_batch(
                value,
                ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"],
                "55555555-5555-4555-8555-555555555555",
            )
            original_write = value.target.write

            def fail_two_write(path, data, **kwargs):
                if "Two" in path:
                    raise StorageError(
                        StorageErrorCode.IO_ERROR,
                        "write",
                        path,
                        "injected write failure",
                    )
                return original_write(path, data, **kwargs)

            with patch.object(value.target, "write", fail_two_write):
                self.confirm(value, preview)
                task = self._drive_until_terminal(value, task_id)
            self.assertEqual(PersistentTaskStatus.PARTIAL_SUCCESS, task.status)
            state = value.repository.get_task_scheduling(task_id)
            # All files of the batch are terminal and the pass returned: the
            # recorded unknown effect no longer occupies the Task's one slot.
            self.assertEqual(TaskQueueState.SETTLED, state.queue_state)
            self.assertIsNone(state.mutation_state)
            self.assertFalse(state.holds_capacity)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            (uncertain,) = [
                result
                for result in value.repository.list_results(task_id)
                if result.source_path == "Movies/Two.2002.mkv"
            ]
            # The evidence itself is never rewritten into a certainty.
            self.assertEqual("attempted_unverified", uncertain.effect_certainty)
            self.assertIn("mutation_outcome", uncertain.uncertain_effects)
            self.assertEqual(("CREATE_DIRECTORY",), uncertain.completed_operations)
            # The successful sibling keeps its own result and effect.
            (successful,) = [
                result
                for result in value.repository.list_results(task_id)
                if result.source_path == "Movies/One.2001.mkv"
            ]
            self.assertEqual("SUCCESS", successful.status)
            self.assertEqual("verified_complete", successful.effect_certainty)


if __name__ == "__main__":
    unittest.main()
