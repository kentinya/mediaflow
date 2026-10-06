#!/usr/bin/env python3
"""Isolated real-Python browser harness for V2 Operations (Tasks 42.1–42.3).

One process serves both the built V2 artifact (``/ui-v2/*`` through the
production static-serving boundary) and the real ``MediaFlowApi`` over one
temporary SQLite runtime database, so Playwright drives the exact packaged
Python stack instead of a Node fake. Every seeded run is created through a
real supported producer or the real Worker claim/linkage path:

- ``POST /api/v1/jobs`` admits a durable pending Job (pre-Task admission);
- ``PersistentTaskCoordinator.create`` creates standalone durable Tasks, the
  same coordinator every production task producer uses;
- ``repository.admit_job`` admits one definition-pinned Job the way the
  scheduler does, giving the scheduled trigger real evidence;
- ``AutomationWorker.run_next`` claims the pending Job and links its Task
  through the real ``complete_claimed_job`` write path.

One of those coordinator-created Tasks also carries a rich, fully durable
detail population for the selected-run journey (Task 42.2): six ``TaskItem``
rows across five dispositions, two ``PersistentResultRecord`` rows (one
verified, one whose effects stay unverified), two operational logs and one
captured ``PipelineEvidence`` row, each written through the repository write
path its real producer uses — so 任务详情 progress, the server-filtered item
pages, 操作记录, one item's evidence and the result package export all serve
only durable SQLite rows, never fixture JSON.

Four test-only control routes exist for the browser journey (they are harness
infrastructure, not product endpoints, and never touch product documents):

- ``POST /__harness__/run-worker`` runs one real Worker claim + linkage;
- ``POST /__harness__/run-manual-organize`` admits one exact Preview through
  the real API and completes its MOVE through ``ManualOrganizeExecutionWorker``;
- ``POST /__harness__/register-manual-worker`` makes the real Worker readiness
  projection available to a browser-admitted organize run;
- ``POST /__harness__/run-manual-worker`` claims and completes one already
  admitted browser execution through ``ManualOrganizeExecutionWorker``;
- ``POST /__harness__/run-standalone-pipeline`` executes one file through the
  real standalone ``PersistentTaskCoordinator → MediaOrganizerService →
  OrganizerExecutor`` assembly (the supported `organize --execute` shape, with
  no Manual preview/plan linkage), over temporary Local Storage and a local
  synthetic MetadataProvider;
- ``POST /__harness__/restart`` closes and reopens the runtime database and
  API object over the same file, which is exactly what a process restart does
  to durable state.

The run-detail result-package export is served by the shared package-exchange
authority; it reads durable Task/Result rows and writes one best-effort audit
row. The Manual Organize proof uses a checked temporary Active configuration,
temporary Local Storage and a synthetic MetadataProvider; no production
configuration or external service is involved. One additional bounded read
exists for the browser journeys: ``GET /__harness__/manual-file-state`` reports
the source/destination state of one synthetic fixture file (``file=``, default
``Three.2003.mkv``), relative to the temporary roots only.

No production media, credential, Storage adapter, Provider or external service
is involved. The script fails fast when the built artifact is missing.
"""

from __future__ import annotations

import argparse
import dataclasses
import io
import json
import os
import socketserver
import sys
import threading
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mediaflow.application.automation import AutomationWorker  # noqa: E402
from mediaflow.application.configuration_objects import ConfigurationObjectService  # noqa: E402
from mediaflow.application.configuration_snapshot import ManagedConfigurationService  # noqa: E402
from mediaflow.application.file_catalog import FileCatalogService  # noqa: E402
from mediaflow.application.manual_organize_worker import (  # noqa: E402
    ManualOrganizeExecutionWorker,
)
from mediaflow.application.media_organizer import (  # noqa: E402
    MediaOrganizerBatchResult,
    MediaOrganizerService,
)
from mediaflow.application.metadata import MetadataProviderRegistry  # noqa: E402
from mediaflow.application.organizer import OrganizerExecutor  # noqa: E402
from mediaflow.application.package_exchange import PackageExchangeService  # noqa: E402
from mediaflow.application.recognition_review import RecognitionReviewService  # noqa: E402
from mediaflow.application.scanner import StorageScanner  # noqa: E402
from mediaflow.application.strategy_test import (  # noqa: E402
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.application.task_runtime import PersistentTaskCoordinator  # noqa: E402
from mediaflow.domain.automation import (  # noqa: E402
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
)
from mediaflow.domain.configuration_management import (  # noqa: E402
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
)
from mediaflow.domain.failure import FailureExplanation  # noqa: E402
from mediaflow.domain.logging import LogLevel, OperationalLogRecord  # noqa: E402
from mediaflow.domain.media_evidence import EvidenceSection, PipelineEvidence  # noqa: E402
from mediaflow.domain.metadata import MediaCandidate, MediaType  # noqa: E402
from mediaflow.domain.organizer import (  # noqa: E402
    ExecutionEffectCertainty,
    ExecutionResult,
    ExecutionStatus,
)
from mediaflow.domain.recognition import RecognitionResult, RecognitionStatus  # noqa: E402
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal  # noqa: E402
from mediaflow.domain.task_persistence import (  # noqa: E402
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.infrastructure.configuration_snapshot import (  # noqa: E402
    build_configuration_snapshot,
)
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository  # noqa: E402
from mediaflow.infrastructure.local_storage import LocalStorage  # noqa: E402
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository  # noqa: E402
from mediaflow.infrastructure.runtime_configuration import (  # noqa: E402
    load_managed_runtime_configuration,
    load_runtime_configuration,
    with_managed_snapshot,
)
from mediaflow.infrastructure.sqlite_configuration_management import (  # noqa: E402
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository  # noqa: E402
from mediaflow.infrastructure.sqlite_runtime import (  # noqa: E402
    SCHEMA_VERSION,
    SQLiteTaskRepository,
)
from mediaflow.interfaces.service_api import MediaFlowApi  # noqa: E402
from mediaflow.interfaces.v2_ui import asset_root  # noqa: E402

HARNESS_TOKEN = "harness-viewer-token"
HARNESS_ADMIN_TOKEN = "harness-admin-token"
WORKER_ID = "harness-inventory-worker"

PRINCIPAL = ResolvedApiPrincipal(
    "harness",
    HARNESS_TOKEN,
    frozenset(
        {
            ApiPermission.READ,
            ApiPermission.SUBMIT_DRY_RUN,
            ApiPermission.CANCEL_JOB,
        }
    ),
)

ADMIN_PRINCIPAL = ResolvedApiPrincipal(
    "harness-admin",
    HARNESS_ADMIN_TOKEN,
    frozenset(ApiPermission),
)


def configured_harness_admin(principal_id: str) -> ResolvedApiPrincipal:
    """Resolve a synthetic test principal through production config validation."""

    document = json.loads(
        (REPO_ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8")
    )
    document["api"] = {
        "principals": [
            {
                "id": principal_id,
                "tokenEnv": "MEDIAFLOW_HARNESS_ADMIN_TOKEN",
                "roles": ["admin"],
            }
        ]
    }
    with patch.dict(os.environ, {"MEDIAFLOW_HARNESS_ADMIN_TOKEN": HARNESS_ADMIN_TOKEN}):
        resolved = load_runtime_configuration(document).resolve_api_principals()
    if len(resolved) != 1 or resolved[0].principal_id != principal_id:
        raise RuntimeError("harness principal configuration did not retain its identity")
    return resolved[0]


@dataclasses.dataclass(frozen=True)
class ManagedHarnessContext:
    """Temporary Active configuration used by the real Manual Organize proof."""

    root: Path
    configuration_repository: SQLiteConfigurationRepository
    configuration_service: ManagedConfigurationService
    bootstrap_document: dict[str, object]
    active: object
    runtime: object
    metadata_registry: MetadataProviderRegistry
    #: The exact JSON document path the resident Worker is given as
    #: ``--config``.  The Worker resolves the continuation's immutable pin
    #: through managed authority from this file, so it must point at the same
    #: managed store the browser's API serves.
    config_path: Path | None = None


def build_api(
    repository: SQLiteTaskRepository,
    *,
    managed: ManagedHarnessContext | None = None,
    file_index: SQLiteFileIndexRepository | None = None,
) -> MediaFlowApi:
    """One real API object over the runtime repository and optional Active pin.

    The repository-only export authority reads durable Task/Result rows and
    writes one best-effort audit row.  When this isolated harness owns a
    temporary managed fixture, the same API also serves the real Manual
    Organize admission and execution endpoints against its temporary Local
    Storage and synthetic MetadataProvider.
    """

    managed_options: dict[str, object] = {}
    if managed is not None:
        if file_index is None:
            raise ValueError("managed browser harness requires its SQLite FileIndex")
        managed_options = {
            "configuration_service": managed.configuration_service,
            "bootstrap_document": managed.bootstrap_document,
            "system_status": build_configuration_snapshot(managed.runtime),
            "file_index": file_index,
            "file_catalog": FileCatalogService(
                file_index,
                ("source",),
                ("source-storage", "media-target"),
                task_repository=repository,
            ),
            "metadata_provider_registry_factory": lambda _policies: managed.metadata_registry,
        }
    api = MediaFlowApi(
        repository,
        None,
        principals=(PRINCIPAL, ADMIN_PRINCIPAL),
        **managed_options,
    )
    api._package_exchange = PackageExchangeService(None, repository)
    return api


def build_managed_fixture(
    database: Path, root: Path
) -> tuple[
    SQLiteTaskRepository,
    SQLiteFileIndexRepository,
    ManagedHarnessContext,
    MediaFlowApi,
]:
    """Create the real checked Active/Storage/FileIndex path in temp roots."""

    root.mkdir(parents=True, exist_ok=True)
    source_root = root / "source"
    destination_root = root / "destination"
    (destination_root / "Movies").mkdir(parents=True, exist_ok=True)
    source_root.mkdir(parents=True, exist_ok=True)
    source_file = source_root / "One.2001.mkv"
    source_file.write_bytes(b"synthetic browser media")
    (source_root / "Two.2002.mkv").write_bytes(b"second synthetic browser media")
    (source_root / "Three.2003.mkv").write_bytes(b"new-task synthetic browser media")
    (source_root / "Four.2004.mkv").write_bytes(b"default-origin synthetic browser media")

    document = json.loads(
        (REPO_ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8")
    )
    # The resident Worker opens the runtime Task database from the resolved
    # configuration's own ``databasePath``, so the managed bootstrap store and
    # the runtime rows must be the same SQLite file — exactly the production
    # shape.  Keeping them apart would make the Worker read a different database
    # than the browser and silently invalidate every Worker-driven journey.
    document["persistence"]["databasePath"] = str(database)
    document["storages"][0]["rootPath"] = str(source_root)
    document["storages"][1]["rootPath"] = str(destination_root)
    document["resourceLibraries"][0]["storagePath"] = ""
    document["mediaLibraries"][0]["rootPath"] = "Movies"

    configuration_repository = SQLiteConfigurationRepository(database)
    configuration_service = ManagedConfigurationService(
        configuration_repository,
        bootstrap_database_path=str(database),
    )
    objects = ConfigurationObjectService(
        configuration_service,
        storage_browser_cursor_secret="operations-inventory-harness-secret",
    )
    draft = configuration_service.import_draft(document, actor="harness")
    validated = configuration_service.validate(draft.revision_id, actor="harness")
    for storage_id in ("source-storage", "media-target"):
        checked = objects.storage_check(
            validated.revision_id,
            storage_id=storage_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="harness",
        )
        if checked.status is not ConfigurationStorageCheckStatus.PASSED:
            raise RuntimeError(f"temporary Storage check failed for {storage_id}")
    strategy = objects.recognition_strategy_test(
        validated.revision_id,
        expected_version=validated.version,
        expected_digest=validated.digest,
        actor="harness",
        resource_library_id="source",
        synthetic_path="Example.Movie.2024.1080p.mkv",
    )
    if strategy.status is not ConfigurationStrategyTestStatus.COMPLETED:
        raise RuntimeError("temporary recognition strategy test did not complete")
    destination = objects.destination_precheck(
        validated.revision_id,
        expected_version=validated.version,
        expected_digest=validated.digest,
        actor="harness",
        recognition_type="C",
        sample={
            "title": "One",
            "mediaType": "movie",
            "year": 2001,
            "genres": ["Animation"],
            "countries": ["JP"],
            "extension": "mkv",
        },
    )
    if destination.status is not ConfigurationDestinationPrecheckStatus.COMPLETED:
        raise RuntimeError("temporary destination precheck did not complete")
    active = objects.activate_checked(
        validated.revision_id,
        expected_version=validated.version,
        actor="harness",
    )
    runtime = with_managed_snapshot(
        load_managed_runtime_configuration(
            active.document,
            bootstrap_database_path=str(database),
        ),
        snapshot_id=active.revision_id,
        digest=active.digest,
        version=active.version,
    )
    repository = SQLiteTaskRepository(database)
    file_index = SQLiteFileIndexRepository(database)
    scan = StorageScanner(
        runtime.create_storages(),
        file_index,
        clock=lambda: datetime.now(UTC) + timedelta(hours=2),
    ).scan(runtime.resource_libraries[0])
    if scan.status.value != "completed":
        raise RuntimeError("temporary ResourceLibrary scan did not complete")
    registry = MetadataProviderRegistry(
        (
            SyntheticMetadataProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "101",
                        MediaType.MOVIE,
                        "One",
                        year=2001,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                    MediaCandidate(
                        "tmdb",
                        "102",
                        MediaType.MOVIE,
                        "Two",
                        year=2002,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                    MediaCandidate(
                        "tmdb",
                        "103",
                        MediaType.MOVIE,
                        "Three",
                        year=2003,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                    MediaCandidate(
                        "tmdb",
                        "104",
                        MediaType.MOVIE,
                        "Four",
                        year=2004,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                    # The authority-refusal fixture's own remaining sources, so
                    # its exact Preview really produces an actionable plan.
                    MediaCandidate(
                        "tmdb",
                        "107",
                        MediaType.MOVIE,
                        "Seven",
                        year=2007,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                    MediaCandidate(
                        "tmdb",
                        "108",
                        MediaType.MOVIE,
                        "Eight",
                        year=2008,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )
            ),
        )
    )
    config_path = root / "harness-config.json"
    config_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    managed = ManagedHarnessContext(
        root=root,
        configuration_repository=configuration_repository,
        configuration_service=configuration_service,
        bootstrap_document=document,
        active=active,
        runtime=runtime,
        config_path=config_path,
        metadata_registry=registry,
    )
    api = build_api(repository, managed=managed, file_index=file_index)
    return repository, file_index, managed, api


class AppState:
    """The swap-able runtime objects; restart replaces both under one lock."""

    def __init__(
        self,
        database: Path,
        *,
        repository: SQLiteTaskRepository,
        api: MediaFlowApi,
        managed: ManagedHarnessContext,
        file_index: SQLiteFileIndexRepository,
    ) -> None:
        self._database = database
        self._lock = threading.Lock()
        self._manual_lock = threading.Lock()
        self._pipeline_lock = threading.Lock()
        self.repository = repository
        self.api = api
        self.managed = managed
        self.file_index = file_index
        self.manual_run: dict[str, str] | None = None
        self.pipeline_run: dict[str, str] | None = None
        #: The paused scan Task of the AC-T7 continuation journey.
        self.continuation_task_id: str | None = None
        self.recovery_run: dict[str, str] | None = None
        self.recovery_batch_run: dict[str, object] | None = None

    @property
    def database(self) -> Path:
        return self._database

    def restart(self) -> None:
        """Close and reopen the runtime database + API over the same file.

        Durable rows, pins, links and Worker registration survive exactly as
        they do across a process restart of the resident services.
        """

        with self._lock:
            self.file_index.close()
            self.repository.close()
            self.repository = SQLiteTaskRepository(self._database)
            self.file_index = SQLiteFileIndexRepository(self._database)
            self.api = build_api(
                self.repository,
                managed=self.managed,
                file_index=self.file_index,
            )
            # The registered Worker's heartbeat must stay claimable across a
            # harness restart; a real resident worker heartbeats continuously.
            worker = (
                self.repository.get_worker(WORKER_ID)
                if hasattr(self.repository, "get_worker")
                else None
            )
            if worker is not None:
                self.repository.heartbeat_worker(WORKER_ID, datetime.now(UTC))


STATE: AppState | None = None


def wsgi_request(
    app,
    method: str,
    path: str,
    *,
    query: str = "",
    body: dict | None = None,
    token: str = HARNESS_TOKEN,
) -> tuple[int, dict]:
    payload = json.dumps(body).encode("utf-8") if body is not None else b""
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(payload)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(payload),
    }
    raw = b"".join(app(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(raw)


def seed(
    repository: SQLiteTaskRepository, api: MediaFlowApi
) -> tuple[SQLiteTaskRepository, MediaFlowApi]:
    """Create one deterministic run population through real producers."""

    # 1. A real durable Job admission: pending, pre-Task, no Worker yet.
    status, job_document = wsgi_request(api, "POST", "/api/v1/jobs", body={"command": "preview"})
    if status != 202:
        raise SystemExit(f"harness: job admission failed with {status}: {job_document}")

    # 2. A second Job, definition-pinned the way the scheduler admits one, so
    #    the scheduled trigger carries real admission evidence.
    now = datetime.now(UTC)
    scheduled = AutomationJob(
        "harness-scheduled-job",
        AutomationCommand.SCAN,
        AutomationJobStatus.PENDING,
        now + timedelta(seconds=1),
        now + timedelta(seconds=1),
        definition_id="harness-definition",
        resource_library_id="harness-library",
        source_scope="Movies",
    )
    repository.admit_job(scheduled, 100)

    # 3. Standalone durable Tasks through the production coordinator.
    coordinator = PersistentTaskCoordinator(repository, repository)
    coordinator.create(
        "scan",
        execute_authorized=False,
        scope_path="Movies/Harness",
    )
    failed_task = coordinator.create(
        "manual_organize",
        execute_authorized=True,
        scope_path="Movies/Harness/Failed",
    )
    # The Task ends FAILED after one bounded item failed before the rest, and
    # its admission counters describe the full durable item population the
    # detail journey reads, so the progress facts and the Task facts agree.
    repository.update_task(
        dataclasses.replace(
            failed_task,
            status=PersistentTaskStatus.FAILED,
            completed_at=now + timedelta(seconds=2),
            total_items=len(RICH_ITEMS),
            completed_items=2,
            failed_items=1,
        )
    )
    # 4. The rich selected-run detail population (RO-3) on that same real
    #    Task: items, Results, operational logs and captured evidence, every
    #    row written through its producer's own repository write path.
    seed_run_detail_population(repository, failed_task, now)
    return repository, api


#: One durable primary item of the rich run-detail population.  The six rows
#: together cover the dispositions an operator diagnoses in 任务详情: a
#: verified success, a success whose storage effect stayed unverified, a
#: failure with a bounded explanation, a waiting decision, a skip and the
#: untouched pending work of a Task that already failed.
@dataclasses.dataclass(frozen=True)
class RichItem:
    suffix: str
    status: TaskItemStatus
    stage: str
    attempts: int
    source_path: str
    destination_path: str | None
    plan_id: str | None
    error: str | None = None
    execution_status: str | None = None


#: Source/destination identities of the rich population: Storage-relative
#: only, so the Operations projection publishes them unchanged.
RICH_ITEMS: tuple[RichItem, ...] = (
    RichItem(
        "01",
        TaskItemStatus.SUCCESS,
        "completed",
        2,
        "Movies/Harness/Failed/Arrival 2016/Arrival.2016.2160p.mkv",
        "Movies/Arrival 2016/Arrival 2016.mkv",
        "harness-plan-01",
        execution_status="SUCCESS",
    ),
    RichItem(
        "02",
        TaskItemStatus.SUCCESS,
        "completed",
        1,
        "Movies/Harness/Failed/Blade Runner 1982/Blade.Runner.1982.1080p.mkv",
        "Movies/Blade Runner 1982/Blade Runner 1982.mkv",
        "harness-plan-02",
        execution_status="SUCCESS",
    ),
    RichItem(
        "03",
        TaskItemStatus.FAILED,
        "failed",
        2,
        "Movies/Harness/Failed/Dune 2021/Dune.2021.2160p.mkv",
        None,
        "harness-plan-03",
        error=FailureExplanation(
            category="destination_collision",
            message="the reviewed destination already exists",
            durable_state="no_media_moved",
            side_effects="none",
            retry_safe=True,
            next_action="resolve the destination conflict, then retry this item",
        ).encode(),
    ),
    RichItem(
        "04",
        TaskItemStatus.WAITING_CONFIRM,
        "waiting_confirm",
        1,
        "Movies/Harness/Failed/Heat 1995/Heat.1995.1080p.mkv",
        None,
        "harness-plan-04",
    ),
    RichItem(
        "05",
        TaskItemStatus.SKIPPED,
        "completed",
        1,
        "Movies/Harness/Failed/Sample 2020/Sample.2020.WEB-DL.mkv",
        None,
        None,
    ),
    RichItem(
        "06",
        TaskItemStatus.PENDING,
        "pipeline",
        0,
        "Movies/Harness/Failed/Pending 2021/Pending.2021.1080p.mkv",
        None,
        None,
    ),
)


def seed_run_detail_population(
    repository: SQLiteTaskRepository,
    task: PersistentTask,
    base: datetime,
) -> None:
    """Attach one rich, fully durable detail population to a real Task.

    Every row goes through the write path its real producer uses —
    ``upsert_item``, ``append_result``, ``append_operational_log`` and
    ``append_evidence`` — so the selected-run detail reads (the progress
    partition, the server-filtered item pages, the exactly-linked operation
    records, one item's evidence and the result package export) can only ever
    serve durable SQLite rows.  The timestamps are one deterministic window
    so the record stream keeps one stable newest-first order.
    """

    storage_id = "harness-storage"
    verified = f"{task.task_id}-01"
    uncertain = f"{task.task_id}-02"
    verified_source = "Movies/Harness/Failed/Arrival 2016/Arrival.2016.2160p.mkv"
    verified_target = "Movies/Arrival 2016/Arrival 2016.mkv"

    for index, spec in enumerate(RICH_ITEMS):
        occurred = base + timedelta(seconds=10 + index)
        repository.upsert_item(
            PersistentTaskItem(
                item_id=f"{task.task_id}-{spec.suffix}",
                task_id=task.task_id,
                storage_id=storage_id,
                resource_library_id="movies",
                source_path=spec.source_path,
                source_display=spec.source_path,
                status=spec.status,
                stage=spec.stage,
                attempts=spec.attempts,
                created_at=occurred,
                updated_at=occurred,
                plan_id=spec.plan_id,
                destination_storage_id=(storage_id if spec.destination_path is not None else None),
                destination_path=spec.destination_path,
                execution_status=spec.execution_status,
                error=spec.error,
            )
        )

    # Two Results: one whose move the executor verified end to end, one whose
    # effect stayed unverified — the progress split publishes them as one
    # confirmed success and one uncertain success that is never counted twice.
    repository.append_result(
        PersistentResultRecord(
            result_id=f"{task.task_id}-result-01",
            task_id=task.task_id,
            item_id=verified,
            source_storage_id=storage_id,
            source_path=verified_source,
            destination_storage_id=storage_id,
            destination_path=verified_target,
            recognition_type="C",
            provider="tmdb",
            provider_id="101",
            metadata_policy_id="C",
            naming_policy_id="A",
            classification_policy_id="A",
            organize_policy_id="A",
            operation="MOVE",
            status="SUCCESS",
            created_at=base + timedelta(seconds=20),
            title="Arrival",
            completed_operations=("MOVE",),
            effect_certainty="verified_complete",
        )
    )
    repository.append_result(
        PersistentResultRecord(
            result_id=f"{task.task_id}-result-02",
            task_id=task.task_id,
            item_id=uncertain,
            source_storage_id=storage_id,
            source_path=RICH_ITEMS[1].source_path,
            destination_storage_id=storage_id,
            destination_path=RICH_ITEMS[1].destination_path,
            recognition_type="C",
            provider="tmdb",
            provider_id="101",
            metadata_policy_id="C",
            naming_policy_id="A",
            classification_policy_id="A",
            organize_policy_id="A",
            operation="MOVE",
            status="SUCCESS",
            created_at=base + timedelta(seconds=21),
            title="Blade Runner",
            completed_operations=("MOVE",),
            effect_certainty="attempted_unverified",
            uncertain_effects=("mutation_outcome",),
        )
    )

    # One captured pipeline-evidence row (kind=evidence in 操作记录), plus the
    # plan-linked operational log the item-evidence read joins through its
    # persisted plan ID and a task-linked failure log (kind=log).
    repository.append_evidence(
        PipelineEvidence(
            evidence_id=f"{task.task_id}-evidence-01",
            task_id=task.task_id,
            item_id=verified,
            attempts=1,
            source_storage_id=storage_id,
            source_path=verified_source,
            captured_at=base + timedelta(seconds=22),
            configuration_snapshot_id=None,
            configuration_snapshot_digest=None,
            outcome="planned",
            sections={
                "parse": EvidenceSection(True, value={"titleCandidate": "Arrival", "year": 2016}),
                "recognition": EvidenceSection(True, value={"recognitionType": "C"}),
                "plan": EvidenceSection(True, value={"operation": "MOVE"}),
            },
        )
    )
    repository.append_operational_log(
        OperationalLogRecord(
            log_id=f"{task.task_id}-log-01",
            occurred_at=base + timedelta(seconds=23),
            level=LogLevel.INFO,
            component="organizer",
            event="organizer.execution_result",
            task_id=task.task_id,
            plan_id="harness-plan-01",
            status="SUCCESS",
        )
    )
    repository.append_operational_log(
        OperationalLogRecord(
            log_id=f"{task.task_id}-log-02",
            occurred_at=base + timedelta(seconds=24),
            level=LogLevel.ERROR,
            component="workflow",
            event="workflow.failed",
            task_id=task.task_id,
            status="failed",
        )
    )


def run_worker_once(state: AppState) -> dict:
    """One real Worker claim + Task linkage over the durable pending Job."""

    def handler(job, cancelled):
        coordinator = PersistentTaskCoordinator(state.repository, state.repository)
        task = coordinator.create(
            job.command.value,
            execute_authorized=False,
            scope_path="Movies/Harness/Linked",
            configuration_snapshot_id=job.configuration_snapshot_id,
            configuration_snapshot_digest=job.configuration_snapshot_digest,
            require_configuration_snapshot=job.configuration_snapshot_id is not None,
        )
        if cancelled():
            return None
        return task.task_id

    worker = AutomationWorker(
        state.repository,
        handler,
        worker_id=WORKER_ID,
        label="harness-inventory-worker",
        configuration_snapshot_id=state.managed.active.revision_id,
        configuration_snapshot_digest=state.managed.active.digest,
        runtime_schema_version=SCHEMA_VERSION,
    )
    claimed = worker.run_next()
    if claimed is None:
        return {"linked": False, "reason": "no claimable Job"}
    return {
        "linked": claimed.task_id is not None,
        "jobId": claimed.job_id,
        "taskId": claimed.task_id,
        "jobStatus": claimed.status.value,
    }


def run_manual_organize_once(state: AppState) -> dict[str, str]:
    """Admit and execute one exact Preview through the production Worker path."""

    with state._manual_lock:
        if state.manual_run is not None:
            return dict(state.manual_run)
        active = state.managed.active
        state.api._worker_service.register_worker(
            "harness-manual-worker",
            "Harness Manual Organize Worker",
            10.0,
            ("scan", "preview", "organize"),
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
            runtime_schema_version=SCHEMA_VERSION,
        )
        status, intent = wsgi_request(
            state.api,
            "POST",
            "/api/v1/resource-libraries/source/files/organize",
            body={"paths": ["One.2001.mkv"]},
            token=HARNESS_ADMIN_TOKEN,
        )
        if status != 201:
            raise RuntimeError(f"Manual Organize intent admission failed: {status}")
        item = intent["items"][0]
        status, intent = wsgi_request(
            state.api,
            "POST",
            f"/api/v1/operations/organize/intents/{intent['intentId']}"
            f"/items/{item['itemId']}/choice",
            body={
                "expectedVersion": intent["version"],
                "expectedItemVersion": item["version"],
                "recognitionTypeId": "C",
                "namingPolicyId": "A",
                "classificationPolicyId": "A",
                "organizePolicyId": "A",
            },
            token=HARNESS_ADMIN_TOKEN,
        )
        if status != 200:
            raise RuntimeError(f"Manual Organize policy selection failed: {status}")
        status, preview = wsgi_request(
            state.api,
            "POST",
            f"/api/v1/operations/organize/intents/{intent['intentId']}/previews",
            body={"expectedVersion": intent["version"]},
            token=HARNESS_ADMIN_TOKEN,
        )
        if status != 201:
            raise RuntimeError(f"Manual Organize Preview failed: {status}")
        status, execution = wsgi_request(
            state.api,
            "POST",
            f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
            body={
                "confirmation": True,
                "itemIds": [value["itemId"] for value in preview["items"]],
                "expectedIntentVersion": intent["version"],
            },
            token=HARNESS_ADMIN_TOKEN,
        )
        if status != 202:
            raise RuntimeError(f"Manual Organize execution admission failed: {status}")
        if not execution.get("taskId") or not execution.get("executionId"):
            raise RuntimeError("Manual Organize admission returned no durable execution link")

        completed = ManualOrganizeExecutionWorker(
            state.api._manual_execution,
            worker_id="harness-manual-worker",
            notice=lambda _line: None,
        ).run_next()
        if completed is None or completed.status.value != "completed":
            raise RuntimeError("Manual Organize Worker did not complete the admitted execution")
        durable = state.repository.get_manual_execution(execution["executionId"])
        if durable is None or durable.task_id != execution["taskId"] or len(durable.items) != 1:
            raise RuntimeError("Manual Organize Worker lost its durable TaskItem linkage")
        state.manual_run = {
            "runId": durable.task_id,
            "taskId": durable.task_id,
            "itemId": durable.items[0].task_item_id,
            "executionId": durable.execution_id,
            "previewId": durable.preview_id,
            "status": completed.status.value,
        }
        return dict(state.manual_run)


def register_manual_worker(state: AppState) -> dict[str, object]:
    """Register the real Worker before the browser's explicit Execute action."""

    active = state.managed.active
    state.api._worker_service.register_worker(
        "harness-manual-worker",
        "Harness Manual Organize Worker",
        10.0,
        ("scan", "preview", "organize"),
        configuration_snapshot_id=active.revision_id,
        configuration_snapshot_digest=active.digest,
        runtime_schema_version=SCHEMA_VERSION,
    )
    return {"registered": True}


def run_manual_worker_once(state: AppState) -> dict[str, object]:
    """Claim one UI-admitted execution and complete it with the real Worker."""

    with state._manual_lock:
        completed = ManualOrganizeExecutionWorker(
            state.api._manual_execution,
            worker_id="harness-manual-worker",
            notice=lambda _line: None,
        ).run_next()
        if completed is None:
            return {"completed": False, "reason": "no admitted manual execution"}
        durable = state.repository.get_manual_execution(completed.execution_id)
        if durable is None or durable.task_id != completed.task_id:
            raise RuntimeError("Manual Organize Worker lost its durable Task linkage")
        return {
            "completed": completed.status.value == "completed",
            "executionId": durable.execution_id,
            "taskId": durable.task_id,
            "status": completed.status.value,
            "itemCount": len(durable.items),
        }


class _PreMutationFailureExecutor:
    """A local test seam that records one known-zero-effect execution failure."""

    def execute(self, plan, _storages, **_kwargs):
        return ExecutionResult(
            ExecutionStatus.FAILED,
            plan.operation,
            plan.source,
            plan.target,
            plan_id=plan.plan_id,
            resolved_destination=plan.target,
            errors=("harness injected a failure before Storage mutation",),
            effect_certainty=ExecutionEffectCertainty.NONE,
        )


def seed_task_item_recovery_journey(state: AppState) -> dict[str, str]:
    """Create a real linked Manual TaskItem at a pending Recognition decision.

    The Manual intent, exact Preview, execution admission, Worker claim and
    failure Result all use the product services. The failure executor is a
    deterministic test seam that fails before Storage is touched; a subsequent
    real RecognitionReviewService row provides the legal waiting state the
    browser resolves through the product API.
    """

    with state._manual_lock:
        if state.recovery_run is not None:
            return dict(state.recovery_run)
        active = state.managed.active
        filename = "Recovery.2005.mkv"
        source_file = state.managed.root / "source" / filename
        source_file.write_bytes(b"synthetic recovery media; no real codec parsing")
        scan = StorageScanner(
            state.managed.runtime.create_storages(),
            state.file_index,
            clock=lambda: datetime.now(UTC) + timedelta(hours=2),
        ).scan(state.managed.runtime.resource_libraries[0])
        if scan.status.value != "completed":
            raise RuntimeError("recovery fixture ResourceLibrary scan did not complete")

        provider = state.managed.metadata_registry.resolve("tmdb")
        existing_candidates = tuple(getattr(provider, "_candidates", ()))
        if not any(value.provider_id == "205" for value in existing_candidates):
            provider._candidates = existing_candidates + (
                MediaCandidate(
                    "tmdb",
                    "205",
                    MediaType.MOVIE,
                    "Recovery",
                    year=2005,
                    genres=("Animation",),
                    countries=("JP",),
                ),
            )

        state.api._worker_service.register_worker(
            "harness-recovery-manual-worker",
            "Harness Recovery Manual Worker",
            10.0,
            ("scan", "preview", "organize"),
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
            runtime_schema_version=SCHEMA_VERSION,
        )
        status, intent = wsgi_request(
            state.api,
            "POST",
            "/api/v1/resource-libraries/source/files/organize",
            body={"paths": [filename]},
            token=HARNESS_ADMIN_TOKEN,
        )
        if status != 201:
            raise RuntimeError(f"recovery Manual Organize intent failed: {status}")
        item = intent["items"][0]
        status, intent = wsgi_request(
            state.api,
            "POST",
            f"/api/v1/operations/organize/intents/{intent['intentId']}"
            f"/items/{item['itemId']}/choice",
            body={
                "expectedVersion": intent["version"],
                "expectedItemVersion": item["version"],
                "recognitionTypeId": "C",
                "namingPolicyId": "A",
                "classificationPolicyId": "A",
                "organizePolicyId": "A",
            },
            token=HARNESS_ADMIN_TOKEN,
        )
        if status != 200:
            raise RuntimeError(f"recovery Manual Organize choice failed: {status}")
        status, preview = wsgi_request(
            state.api,
            "POST",
            f"/api/v1/operations/organize/intents/{intent['intentId']}/previews",
            body={"expectedVersion": intent["version"]},
            token=HARNESS_ADMIN_TOKEN,
        )
        if status != 201:
            raise RuntimeError(f"recovery Manual Organize Preview failed: {status}")
        status, execution = wsgi_request(
            state.api,
            "POST",
            f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
            body={
                "confirmation": True,
                "itemIds": [value["itemId"] for value in preview["items"]],
                "expectedIntentVersion": intent["version"],
            },
            token=HARNESS_ADMIN_TOKEN,
        )
        if status != 202:
            raise RuntimeError(f"recovery Manual Organize admission failed: {status}")

        manual_execution = state.api._manual_execution
        actual_executor = manual_execution._executor
        manual_execution._executor = _PreMutationFailureExecutor()
        try:
            completed = ManualOrganizeExecutionWorker(
                manual_execution,
                worker_id="harness-recovery-manual-worker",
                notice=lambda _line: None,
            ).run_next()
        finally:
            manual_execution._executor = actual_executor
        if completed is None or completed.status.value != "failed":
            raise RuntimeError("recovery fixture did not produce the expected safe failure")

        durable = state.repository.get_manual_execution(execution["executionId"])
        if durable is None or len(durable.items) != 1:
            raise RuntimeError("recovery fixture lost the exact manual execution item")
        manual_item = durable.items[0]
        current = state.repository.get_item(manual_item.task_item_id)
        if current is None or current.status is not TaskItemStatus.FAILED:
            raise RuntimeError("recovery fixture item did not persist its failed outcome")
        processing = dataclasses.replace(
            current,
            status=TaskItemStatus.PROCESSING,
            stage="recognizing",
        )
        state.repository.upsert_item(processing)
        review = RecognitionReviewService(
            state.repository,
            state.managed.runtime.strategy.recognition_types,
        ).create(
            processing,
            RecognitionResult(status=RecognitionStatus.UNRECOGNIZED),
        )
        state.recovery_run = {
            "runId": durable.task_id,
            "taskId": durable.task_id,
            "itemId": manual_item.task_item_id,
            "previewId": preview["previewId"],
            "executionId": durable.execution_id,
            "reviewId": review.review_id,
            "sourcePath": filename,
        }
        if source_file.read_bytes() != b"synthetic recovery media; no real codec parsing":
            raise RuntimeError("zero-mutation recovery fixture changed the source")
        return dict(state.recovery_run)


def run_task_item_recovery_worker_once(state: AppState) -> dict[str, object]:
    """Run the real resident queued-workflow handler for the recovery Job."""

    recovery_item_ids = [
        str(value)
        for value in (
            state.recovery_run.get("itemId") if state.recovery_run else None,
            state.recovery_batch_run.get("singleItemId") if state.recovery_batch_run else None,
            state.recovery_batch_run.get("batchEligibleItemId")
            if state.recovery_batch_run
            else None,
        )
        if value is not None
    ]
    if not recovery_item_ids:
        raise RuntimeError("task-item recovery fixture has not been seeded")
    from mediaflow.final_cli import _run_queued_workflow

    queued = next(
        (
            value
            for item_id in recovery_item_ids
            for value in state.repository.list_recovery_continuations(item_id, limit=10)
            if value.status.value == "queued" and value.new_task_id is None
        ),
        None,
    )
    if queued is None:
        return {"ran": False, "reason": "no queued recovery continuation"}
    job = state.repository.get_job(queued.job_id)
    if job is None:
        raise RuntimeError("queued recovery continuation lost its Job")
    if state.managed.config_path is None:
        raise RuntimeError("resident recovery Worker has no managed config path")
    active = state.managed.active
    state.repository.register_worker(
        WORKER_ID,
        "harness-inventory-worker",
        30.0,
        ("scan", "preview", "organize", "recovery-continuation"),
        configuration_snapshot_id=active.revision_id,
        configuration_snapshot_digest=active.digest,
        runtime_schema_version=SCHEMA_VERSION,
        now=datetime.now(UTC),
    )
    # Older unclaimed seed Jobs are harness fixtures. Close them with an
    # unregistered claim before the exact recovery Job; a snapshot-bound
    # Worker may claim only this continuation and must never mistake it for a
    # fixture. The actual recovery Job is claimed below by AutomationWorker.
    while True:
        pending = tuple(
            sorted(
                (
                    value
                    for value in state.repository.list_jobs(limit=100)
                    if value.status is AutomationJobStatus.PENDING
                ),
                key=lambda value: (value.created_at, value.job_id),
            )
        )
        if not pending or pending[0].job_id == job.job_id:
            break
        claimed_fixture = state.repository.claim_next_job(datetime.now(UTC))
        if claimed_fixture is None:
            break
        state.repository.complete_claimed_job(
            dataclasses.replace(
                claimed_fixture,
                status=AutomationJobStatus.COMPLETED,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error=None,
            )
        )
    worker = AutomationWorker(
        state.repository,
        lambda value, cancelled: _run_queued_workflow(
            value,
            str(state.managed.config_path),
            cancelled,
            repository=state.repository,
        ),
        worker_id=WORKER_ID,
        label="harness-inventory-worker",
        configuration_snapshot_id=active.revision_id,
        configuration_snapshot_digest=active.digest,
        runtime_schema_version=SCHEMA_VERSION,
    )
    with patch(
        "mediaflow.final_cli.metadata_provider_registry_from_environment",
        lambda _provider_ids: state.managed.metadata_registry,
    ):
        completed_job = worker.run_next()
    if completed_job is None or completed_job.job_id != job.job_id:
        return {"ran": False, "reason": "queued recovery Job was not claimable"}
    continuation = state.repository.get_recovery_continuation_for_job(job.job_id)
    return {
        "ran": True,
        "jobId": job.job_id,
        "taskId": completed_job.task_id,
        "continuationStatus": continuation.status.value if continuation else None,
        "newTaskId": continuation.new_task_id if continuation else None,
        "newResultId": continuation.new_result_id if continuation else None,
    }


def seed_task_item_recovery_batch(state: AppState) -> dict[str, object]:
    """Create exact pinned TaskItems for single and mixed browser recovery."""

    if state.recovery_batch_run is not None:
        return dict(state.recovery_batch_run)

    source_root = state.managed.root / "source"
    files = {
        "Batch/C/BatchSingle.2006.mkv": b"synthetic single recovery source",
        "Batch/C/BatchEligible.2007.mkv": b"synthetic accepted batch source",
        "Batch/C/BatchStale.2008.mkv": b"synthetic stale batch source",
        "Batch/C/BatchUnknown.2009.mkv": b"synthetic unknown effect sibling",
        "Batch/C/BatchSuccess.2010.mkv": b"synthetic successful sibling",
        "Batch/C/BatchIgnored.2011.mkv": b"synthetic ignored sibling",
    }
    for relative_path, content in files.items():
        source = source_root / relative_path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(content)

    scan = StorageScanner(
        state.managed.runtime.create_storages(),
        state.file_index,
        clock=lambda: datetime.now(UTC) + timedelta(hours=2),
    ).scan(state.managed.runtime.resource_libraries[0])
    if scan.status.value != "completed":
        raise RuntimeError("recovery batch fixture ResourceLibrary scan did not complete")

    provider = state.managed.metadata_registry.resolve("tmdb")
    existing_candidates = tuple(getattr(provider, "_candidates", ()))
    added_candidates = tuple(
        MediaCandidate(
            "tmdb",
            provider_id,
            MediaType.MOVIE,
            title,
            year=year,
            genres=("Animation",),
            countries=("JP",),
        )
        for provider_id, title, year in (
            ("206", "BatchSingle", 2006),
            ("207", "BatchEligible", 2007),
        )
        if not any(value.provider_id == provider_id for value in existing_candidates)
    )
    provider._candidates = existing_candidates + added_candidates

    active = state.managed.active
    task = PersistentTaskCoordinator(state.repository, state.repository).create(
        "organize",
        execute_authorized=False,
        scope_path="Batch",
        configuration_snapshot_id=active.revision_id,
        configuration_snapshot_digest=active.digest,
        require_configuration_snapshot=True,
        status=PersistentTaskStatus.PARTIAL_SUCCESS,
    )
    now = datetime.now(UTC)
    identifiers = {
        "single": f"{task.task_id}-single",
        "eligible": f"{task.task_id}-eligible",
        "stale": f"{task.task_id}-stale",
        "success": f"{task.task_id}-success",
        "unknown": f"{task.task_id}-unknown",
        "ignored": f"{task.task_id}-ignored",
    }
    eligible_failure = FailureExplanation(
        category="analysis_interrupted",
        message="the last analysis stopped before any Storage mutation",
        durable_state="failed",
        side_effects="none",
        retry_safe=True,
        next_action="continue this failed item through a fresh pinned DryRun",
    ).encode()
    unknown_failure = FailureExplanation(
        category="execution_outcome_unknown",
        message="the previous operation outcome could not be verified",
        durable_state="investigation_required",
        side_effects="unknown",
        retry_safe=False,
        next_action="inspect the recorded effect evidence before taking another action",
    ).encode()

    def make_item(item_id: str, path: str, status: TaskItemStatus, stage: str, error=None):
        record = state.file_index.find_by_path("source-storage", "source", path)
        if record is None or record.occurrence_id is None or record.fingerprint is None:
            raise RuntimeError(f"recovery batch fixture has no verified source identity for {path}")
        return PersistentTaskItem(
            item_id=item_id,
            task_id=task.task_id,
            storage_id="source-storage",
            resource_library_id="source",
            source_path=path,
            source_display=path,
            status=status,
            stage=stage,
            attempts=1,
            created_at=now,
            updated_at=now,
            error=error,
            source_occurrence_id=record.occurrence_id,
            source_fingerprint=record.fingerprint,
            source_fingerprint_state="verified",
        )

    item_specs = (
        (
            identifiers["single"],
            "Batch/C/BatchSingle.2006.mkv",
            TaskItemStatus.FAILED,
            "failed",
            eligible_failure,
        ),
        (
            identifiers["eligible"],
            "Batch/C/BatchEligible.2007.mkv",
            TaskItemStatus.FAILED,
            "failed",
            eligible_failure,
        ),
        (
            identifiers["stale"],
            "Batch/C/BatchStale.2008.mkv",
            TaskItemStatus.FAILED,
            "failed",
            eligible_failure,
        ),
        (
            identifiers["success"],
            "Batch/C/BatchSuccess.2010.mkv",
            TaskItemStatus.SUCCESS,
            "completed",
            None,
        ),
        (
            identifiers["unknown"],
            "Batch/C/BatchUnknown.2009.mkv",
            TaskItemStatus.FAILED,
            "failed",
            unknown_failure,
        ),
        (
            identifiers["ignored"],
            "Batch/C/BatchIgnored.2011.mkv",
            TaskItemStatus.IGNORED,
            "ignored_by_operator",
            None,
        ),
    )
    for item_id, path, status, stage, error in item_specs:
        state.repository.upsert_item(make_item(item_id, path, status, stage, error))

    result_values = (
        PersistentResultRecord(
            result_id=f"{task.task_id}-result-success",
            task_id=task.task_id,
            item_id=identifiers["success"],
            source_storage_id="source-storage",
            source_path="Batch/C/BatchSuccess.2010.mkv",
            destination_storage_id="media-target",
            destination_path="Movies/BatchSingle (2006)/BatchSingle (2006).mkv",
            recognition_type="C",
            provider="tmdb",
            provider_id="206",
            metadata_policy_id="C",
            naming_policy_id="A",
            classification_policy_id="A",
            organize_policy_id="A",
            operation="MOVE",
            status="SUCCESS",
            created_at=now,
            title="BatchSingle",
            completed_operations=("MOVE",),
            effect_certainty="verified_complete",
        ),
        PersistentResultRecord(
            result_id=f"{task.task_id}-result-unknown",
            task_id=task.task_id,
            item_id=identifiers["unknown"],
            source_storage_id="source-storage",
            source_path="Batch/C/BatchUnknown.2009.mkv",
            destination_storage_id="media-target",
            destination_path="Movies/BatchUnknown (2009)/BatchUnknown (2009).mkv",
            recognition_type="C",
            provider="tmdb",
            provider_id="209",
            metadata_policy_id="C",
            naming_policy_id="A",
            classification_policy_id="A",
            organize_policy_id="A",
            operation="MOVE",
            status="FAILED",
            created_at=now,
            title="BatchUnknown",
            completed_operations=("MOVE",),
            effect_certainty="attempted_unverified",
            uncertain_effects=("mutation_outcome",),
            error=unknown_failure,
        ),
    )
    for result in result_values:
        state.repository.append_result(result)

    state.repository.update_task(
        dataclasses.replace(
            task,
            total_items=len(item_specs),
            completed_items=2,
            failed_items=4,
            updated_at=now,
            completed_at=now,
        )
    )
    state.recovery_batch_run = {
        "runId": task.task_id,
        "taskId": task.task_id,
        "singleItemId": identifiers["single"],
        "batchEligibleItemId": identifiers["eligible"],
        "staleItemId": identifiers["stale"],
        "successItemId": identifiers["success"],
        "unknownItemId": identifiers["unknown"],
        "ignoredItemId": identifiers["ignored"],
        "singleSourcePath": "Batch/C/BatchSingle.2006.mkv",
    }
    return dict(state.recovery_batch_run)


def stale_task_item_batch_selection(state: AppState) -> dict[str, object]:
    """Change one selected checkpoint after the browser captured its version."""

    if state.recovery_batch_run is None:
        raise RuntimeError("recovery batch fixture has not been seeded")
    item_id = str(state.recovery_batch_run["staleItemId"])
    item = state.repository.get_item(item_id)
    if item is None:
        raise RuntimeError("selected stale batch fixture item disappeared")
    state.repository.upsert_item(
        dataclasses.replace(item, stage="failed_after_selection", updated_at=datetime.now(UTC))
    )
    return {"changed": True, "itemId": item_id}


def task_item_recovery_batch_state(state: AppState) -> dict[str, object]:
    """Return relative, read-only state for the single and batch browser journey."""

    if state.recovery_batch_run is None:
        return {"available": False}
    run = state.recovery_batch_run
    item_ids = {
        key: str(run[run_key])
        for key, run_key in (
            ("single", "singleItemId"),
            ("eligible", "batchEligibleItemId"),
            ("stale", "staleItemId"),
            ("success", "successItemId"),
            ("unknown", "unknownItemId"),
            ("ignored", "ignoredItemId"),
        )
    }
    items = {key: state.repository.get_item(item_id) for key, item_id in item_ids.items()}
    continuations = {
        key: state.repository.list_recovery_continuations(item_id, limit=10)
        for key, item_id in item_ids.items()
    }
    return {
        "available": True,
        "taskId": run["taskId"],
        "itemIds": item_ids,
        "itemStatuses": {
            key: value.status.value if value is not None else None for key, value in items.items()
        },
        "itemStages": {
            key: value.stage if value is not None else None for key, value in items.items()
        },
        "continuations": {
            key: [
                {
                    "status": value.status.value,
                    "newTaskId": value.new_task_id,
                    "newResultId": value.new_result_id,
                }
                for value in rows
            ]
            for key, rows in continuations.items()
        },
        "sourceExists": {
            path: (state.managed.root / "source" / path).is_file()
            for path in (
                "Batch/C/BatchSingle.2006.mkv",
                "Batch/C/BatchEligible.2007.mkv",
            )
        },
        "targetFiles": [
            value.relative_to(state.managed.root / "destination").as_posix()
            for value in (state.managed.root / "destination").rglob("*")
            if value.is_file()
        ],
    }


def task_item_recovery_state(state: AppState) -> dict[str, object]:
    """Return bounded test-only state for independent source/result assertions."""

    if state.recovery_run is None:
        return {"available": False}
    run = state.recovery_run
    task = state.repository.get_task(run["taskId"])
    source = state.repository.get_item(run["itemId"])
    continuations = state.repository.list_recovery_continuations(run["itemId"], limit=10)
    continuation = continuations[0] if continuations else None
    analysis_task = (
        state.repository.get_task(continuation.new_task_id)
        if continuation is not None and continuation.new_task_id
        else None
    )
    analysis_items = (
        state.repository.list_items(continuation.new_task_id)
        if continuation is not None and continuation.new_task_id
        else ()
    )
    linked_results = (
        state.repository.list_results(continuation.new_task_id)
        if continuation and continuation.new_task_id
        else ()
    )
    return {
        "available": True,
        "taskId": run["taskId"],
        "itemId": run["itemId"],
        "taskStatus": task.status.value if task else None,
        "itemStatus": source.status.value if source else None,
        "itemStage": source.stage if source else None,
        "continuationStatus": continuation.status.value if continuation else None,
        "analysisTaskId": continuation.new_task_id if continuation else None,
        "analysisTaskStatus": analysis_task.status.value if analysis_task else None,
        "analysisItems": [
            {
                "status": value.status.value,
                "stage": value.stage,
                "error": value.error,
                "sourcePath": value.source_path,
            }
            for value in analysis_items
        ],
        "analysisResultId": continuation.new_result_id if continuation else None,
        "resultIds": [value.result_id for value in linked_results],
        "sourceExists": (state.managed.root / "source" / run["sourcePath"]).is_file(),
        "targetFiles": [
            value.relative_to(state.managed.root / "destination").as_posix()
            for value in (state.managed.root / "destination").rglob("*")
            if value.is_file()
        ],
    }


def manual_file_state(state: AppState, filename: str = "Three.2003.mkv") -> dict[str, object]:
    """Return relative-only state for one new-task synthetic source file.

    The file identity comes from the harness query string (`file=`); the
    default keeps the original new-task journey file. The name is validated
    against the synthetic fixture set so the read stays bounded to files the
    harness itself created.
    """

    allowed = ("One.2001.mkv", "Two.2002.mkv", "Three.2003.mkv", "Four.2004.mkv")
    if filename not in allowed:
        raise RuntimeError(f"harness: unknown manual-file-state file {filename!r}")
    stem = filename.split(".")[0]
    source = state.managed.root / "source" / filename
    destination = state.managed.root / "destination"
    targets = sorted(
        path.relative_to(destination).as_posix()
        for path in destination.rglob(f"{stem}*.mkv")
        if path.is_file()
    )
    return {
        "sourceExists": source.is_file(),
        "destinationTargets": targets,
    }


#: The unique Task command of the real standalone processing-chain proof.  It
#: is neither the Manual command nor a seeded command, so the browser spec can
#: isolate its run with the existing server-side command filter without
#: touching the seeded population's counts.
PIPELINE_TASK_COMMAND = "harness-standalone-organize"

#: The managed source file the standalone chain organizes.  Its path contains
#: the `/电影/` directory the checked Active recognition rules match to
#: RecognitionType A, and its identity ("Two", 2002, Animation/JP) is distinct
#: from the Manual journey's "One" so no destination conflict can mask the
#: executor's durable MOVE steps.
PIPELINE_SOURCE_FILE = "电影/Two.2002.mkv"


#: The synthetic sources reserved for the paused-scope continuation journey.
#: The recorded one is already owned by the paused Task (so the continuation
#: must never repeat it) and the remaining one is the only work left.  Both are
#: dedicated names, so the remaining-scope proof can never be confused with
#: another journey's media.
# The authority-refusal fixture's own ResourceLibrary-relative scope and its
# two eligible remaining sources.
AUTHORITY_SCOPE = "Authority"
AUTHORITY_FIRST_FILE = "Seven.2007.mkv"
AUTHORITY_SECOND_FILE = "Eight.2008.mkv"

CONTINUATION_RECORDED_FILE = "Six.2006.mkv"
CONTINUATION_SOURCE_FILE = "Five.2005.mkv"


def seed_continuation_journey(state: AppState) -> dict[str, object]:
    """Create one real paused scan Task with one already-recorded source.

    This is a genuine durable state produced by the real production
    coordinator: a scan Task that discovered exactly one source and was then
    durably paused at a supported item boundary.  Its item budget is two, so
    exactly one unit of remaining work exists — the continuation must process
    that one and nothing else.
    """

    active = state.managed.active
    source_root = state.managed.root / "source"
    (source_root / CONTINUATION_SOURCE_FILE).write_bytes(b"continuation synthetic media")
    coordinator = PersistentTaskCoordinator(state.repository, state.repository)
    task = coordinator.create(
        "scan",
        execute_authorized=False,
        scope_path=None,
        item_limit=2,
        configuration_snapshot_id=active.revision_id,
        configuration_snapshot_digest=active.digest,
        require_configuration_snapshot=True,
    )
    # One source is already recorded, so the continuation must never repeat it.
    coordinator.record_discovered(
        task.task_id,
        "source-storage",
        "source",
        CONTINUATION_RECORDED_FILE,
        f"source-storage:{CONTINUATION_RECORDED_FILE}",
    )
    state.repository.request_task_pause(task.task_id, datetime.now(UTC))
    paused = coordinator.acknowledge_pause(task.task_id)
    if paused.status is not PersistentTaskStatus.PAUSED:
        raise RuntimeError("continuation fixture Task did not pause")
    state.continuation_task_id = task.task_id
    return {
        "taskId": task.task_id,
        "status": paused.status.value,
        "itemLimit": paused.item_limit,
        "recordedSource": CONTINUATION_RECORDED_FILE,
        "remainingSource": CONTINUATION_SOURCE_FILE,
    }


def run_continuation_worker_once(state: AppState) -> dict[str, object]:
    """Claim and run the queued continuation through the REAL Worker handler.

    The Job is claimed by its exact identity through the production
    ``AutomationWorker`` (registered with the managed Active pin, as a resident
    Worker is), and the handler is the production ``_run_queued_workflow`` — the
    same entry point the resident Worker uses.  Nothing here re-implements,
    stubs or bypasses the continuation boundary.
    """

    from mediaflow.final_cli import _run_queued_workflow

    active = state.managed.active
    state.repository.register_worker(
        WORKER_ID,
        "harness-inventory-worker",
        30.0,
        ("scan", "preview", "organize", "scope-continuation"),
        configuration_snapshot_id=active.revision_id,
        configuration_snapshot_digest=active.digest,
        runtime_schema_version=SCHEMA_VERSION,
        now=datetime.now(UTC),
    )
    continuation_job = None
    for candidate in state.repository.list_jobs(limit=100):
        if candidate.command.value == "scope-continuation" and candidate.status.value == "pending":
            continuation_job = candidate
            break
    if continuation_job is None:
        return {"ran": False, "reason": "no queued scope continuation"}

    # The production claim has no command filter and orders by admission time,
    # so the harness's own older seed Jobs are claimed first.  They are harness
    # fixtures, not product work: each is closed through the production
    # ``complete_claimed_job`` write path without running a workflow, and the
    # loop continues until the real continuation Job owns the claim.  The
    # continuation itself always goes through the production claim fence and the
    # production Worker handler.
    config_path = state.managed.config_path
    claimed = state.repository.claim_next_job(datetime.now(UTC), worker_id=WORKER_ID)
    skipped: list[str] = []
    while claimed is not None and claimed.job_id != continuation_job.job_id:
        skipped.append(claimed.job_id)
        state.repository.complete_claimed_job(
            dataclasses.replace(
                claimed,
                status=AutomationJobStatus.COMPLETED,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error=None,
            )
        )
        claimed = state.repository.claim_next_job(datetime.now(UTC), worker_id=WORKER_ID)
    if claimed is None:
        return {"ran": False, "reason": "the continuation Job was not claimable"}
    task_id = _run_queued_workflow(
        claimed,
        str(config_path) if config_path is not None else None,
        lambda: False,
        repository=state.repository,
    )
    state.repository.complete_claimed_job(
        dataclasses.replace(
            claimed,
            status=AutomationJobStatus.COMPLETED,
            updated_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            task_id=task_id,
        )
    )
    continuation = state.repository.get_scope_continuation_for_job(claimed.job_id)
    return {
        "ran": True,
        "jobId": claimed.job_id,
        "taskId": task_id,
        "continuationStatus": continuation.status.value if continuation else None,
        "newTaskId": continuation.new_task_id if continuation else None,
        "skippedSeedJobs": skipped,
    }


def seed_authority_refusal(state: AppState) -> dict[str, object]:
    """Create one real paused Task that was admitted as a mutation.

    Its ``execute_authorized`` boolean records the original admission, but no
    live reusable execution authority exists for it: it has no definition-linked
    occurrence Job and therefore no unattended grant.  The backend must refuse a
    native Continue and name the exact-Preview/explicit-intent journey instead of
    continuing under the stored boolean.
    """

    active = state.managed.active
    # A dedicated, ResourceLibrary-relative scope holding exactly two eligible
    # sources, so the native exact Preview really has a remaining scope to
    # review under the run's own pin.
    source_root = state.managed.root / "source"
    authority_root = source_root / AUTHORITY_SCOPE
    authority_root.mkdir(parents=True, exist_ok=True)
    (authority_root / AUTHORITY_FIRST_FILE).write_bytes(b"authority synthetic media")
    (authority_root / AUTHORITY_SECOND_FILE).write_bytes(b"authority synthetic media two")
    coordinator = PersistentTaskCoordinator(state.repository, state.repository)
    task = coordinator.create(
        "preview",
        execute_authorized=True,
        scope_path=AUTHORITY_SCOPE,
        item_limit=2,
        configuration_snapshot_id=active.revision_id,
        configuration_snapshot_digest=active.digest,
        require_configuration_snapshot=True,
    )
    state.repository.request_task_pause(task.task_id, datetime.now(UTC))
    paused = coordinator.acknowledge_pause(task.task_id)
    if paused.status is not PersistentTaskStatus.PAUSED:
        raise RuntimeError("authority-refusal fixture Task did not pause")
    return {
        "taskId": task.task_id,
        "status": paused.status.value,
        "scope": AUTHORITY_SCOPE,
        "remainingSources": [AUTHORITY_FIRST_FILE, AUTHORITY_SECOND_FILE],
    }


def continuation_journey_state(state: AppState) -> dict[str, object]:
    """Report the durable state of the continuation journey (bounded reads only)."""

    source_task_id = state.continuation_task_id
    if source_task_id is None:
        return {"seeded": False}
    source = state.repository.get_task(source_task_id)
    continuations = state.repository.list_scope_continuations(source_task_id)
    linked = [
        task for task in state.repository.list_tasks(limit=100) if task.task_id != source_task_id
    ]
    return {
        "seeded": True,
        "sourceTaskId": source_task_id,
        "sourceStatus": source.status.value if source else None,
        "sourceItemPaths": sorted(
            item.source_path for item in state.repository.list_items(source_task_id)
        ),
        "continuations": [item.document() for item in continuations],
        "linkedTasks": [
            {
                "taskId": task.task_id,
                "status": task.status.value,
                "itemPaths": sorted(
                    item.source_path for item in state.repository.list_items(task.task_id)
                ),
            }
            for task in linked
        ],
    }


def run_standalone_pipeline_once(state: AppState) -> dict[str, str]:
    """Execute one real standalone `organize --execute`-shape run.

    This is the assembly the CLI wires for `organize --execute` on one file
    path — and the one the reviewer's P1 names: ``PersistentTaskCoordinator``
    → ``MediaOrganizerService`` → ``OrganizerExecutor`` over the managed
    fixture's temporary Active configuration, Local Storage and a local
    synthetic MetadataProvider.  No Manual intent/preview/execution is created,
    so the TaskItem has no ``manual_execution_items`` linkage and
    ``planEvidence`` correctly reports unavailable: the only durable proof of
    its completed steps is the checkpoint/Result step lists the executor
    itself persisted.  Every mutation stays inside the harness's temporary
    roots; the run is idempotent for one harness lifetime.
    """

    with state._pipeline_lock:
        if state.pipeline_run is not None:
            return dict(state.pipeline_run)
        managed = state.managed
        source_root = managed.root / "source"
        target_root = managed.root / "destination"
        pipeline_file = source_root / PIPELINE_SOURCE_FILE
        pipeline_file.parent.mkdir(parents=True, exist_ok=True)
        pipeline_file.write_bytes(b"synthetic standalone media")

        # The standalone chain opens its own Storage adapters over the same
        # temporary roots, exactly as a second process would; the physical
        # tree stays shared with the managed fixture.
        storages = {
            "source-storage": LocalStorage("source-storage", str(source_root)),
            "media-target": LocalStorage("media-target", str(target_root)),
        }
        runtime = managed.runtime
        resource_library = next(
            item for item in runtime.resource_libraries if item.library_id == "source"
        )
        media_libraries = {item.library_id: item for item in runtime.media_libraries}
        providers = MetadataProviderRegistry(
            (
                SyntheticMetadataProvider(
                    (
                        MediaCandidate(
                            "tmdb",
                            "102",
                            MediaType.MOVIE,
                            "Two",
                            year=2002,
                            genres=("Animation",),
                            countries=("JP",),
                        ),
                    )
                ),
            )
        )
        strategy = strategy_runner_from_configuration(
            runtime.strategy, providers, storages=storages
        )
        coordinator = PersistentTaskCoordinator(state.repository, state.repository)
        # Managed authority: like the CLI, the Task pins the Active snapshot.
        task = coordinator.create(
            PIPELINE_TASK_COMMAND,
            execute_authorized=True,
            scope_path=PIPELINE_SOURCE_FILE,
            configuration_snapshot_id=runtime.configuration_snapshot_id,
            configuration_snapshot_digest=runtime.configuration_snapshot_digest,
            require_configuration_snapshot=runtime.configuration_authority == "MANAGED",
        )
        service = MediaOrganizerService(
            strategy,
            StorageScanner(storages, InMemoryFileIndexRepository()),
            storages,
            media_libraries,
            runtime.strategy.recognition_type_policies,
            JsonLinesOperationHistoryRepository(managed.root / "pipeline-history.jsonl"),
            executor=OrganizerExecutor(),
            source_display_roots=dict(runtime.resource_display_roots),
            task_coordinator=coordinator,
            task_id=task.task_id,
        )
        # The supported single-file branch of `organize --execute`: a bounded
        # ResourceLibrary-relative display path plus its storage path.
        item_result = service.process_file(
            PIPELINE_SOURCE_FILE,
            resource_library=resource_library,
            storage_path=PIPELINE_SOURCE_FILE,
            execute=True,
        )
        finished = coordinator.finish(task.task_id, MediaOrganizerBatchResult((item_result,)))

        items = state.repository.list_items(task.task_id)
        if len(items) != 1:
            raise RuntimeError(
                f"standalone pipeline run expected one durable item, got {len(items)}"
            )
        item = items[0]
        if item.status is not TaskItemStatus.SUCCESS:
            raise RuntimeError(f"standalone pipeline run did not succeed: {item.status.value}")
        results = state.repository.list_results(task.task_id)
        if not results or not results[0].completed_operations:
            raise RuntimeError("standalone pipeline run persisted no completed steps")
        state.pipeline_run = {
            "runId": finished.task_id,
            "taskId": finished.task_id,
            "itemId": item.item_id,
            "status": finished.status.value,
            "sourcePath": PIPELINE_SOURCE_FILE,
        }
        return dict(state.pipeline_run)


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - wsgiref API
        return


class ThreadingWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
    daemon_threads = True


def application(environ, start_response):
    path = str(environ.get("PATH_INFO", ""))
    if path.startswith("/__harness__/") and STATE is not None:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        if path == "/__harness__/run-worker" and method == "POST":
            document = run_worker_once(STATE)
        elif path == "/__harness__/run-manual-organize" and method == "POST":
            document = run_manual_organize_once(STATE)
        elif path == "/__harness__/register-manual-worker" and method == "POST":
            document = register_manual_worker(STATE)
        elif path == "/__harness__/run-manual-worker" and method == "POST":
            document = run_manual_worker_once(STATE)
        elif path == "/__harness__/seed-task-item-recovery" and method == "POST":
            document = seed_task_item_recovery_journey(STATE)
        elif path == "/__harness__/run-task-item-recovery-worker" and method == "POST":
            document = run_task_item_recovery_worker_once(STATE)
        elif path == "/__harness__/task-item-recovery-state" and method == "GET":
            document = task_item_recovery_state(STATE)
        elif path == "/__harness__/seed-task-item-recovery-batch" and method == "POST":
            document = seed_task_item_recovery_batch(STATE)
        elif path == "/__harness__/stale-task-item-batch-selection" and method == "POST":
            document = stale_task_item_batch_selection(STATE)
        elif path == "/__harness__/task-item-recovery-batch-state" and method == "GET":
            document = task_item_recovery_batch_state(STATE)
        elif path == "/__harness__/manual-file-state" and method == "GET":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            requested_file = (query.get("file") or ["Three.2003.mkv"])[0]
            document = manual_file_state(STATE, filename=requested_file)
        elif path == "/__harness__/run-standalone-pipeline" and method == "POST":
            document = run_standalone_pipeline_once(STATE)
        elif path == "/__harness__/seed-continuation" and method == "POST":
            document = seed_continuation_journey(STATE)
        elif path == "/__harness__/run-continuation-worker" and method == "POST":
            document = run_continuation_worker_once(STATE)
        elif path == "/__harness__/seed-authority-refusal" and method == "POST":
            document = seed_authority_refusal(STATE)
        elif path == "/__harness__/continuation-state" and method == "GET":
            document = continuation_journey_state(STATE)
        elif path == "/__harness__/restart" and method == "POST":
            STATE.restart()
            document = {"restarted": True}
        elif path == "/__harness__/health" and method == "GET":
            document = {"status": "ok"}
        else:
            document = {"error": "harness route not found"}
        body = json.dumps(document).encode("utf-8")
        start_response(
            "200 OK" if "error" not in document else "404 Not Found",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [body]
    return STATE.api(environ, start_response)


def main(argv: list[str] | None = None) -> int:
    global ADMIN_PRINCIPAL

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4183)
    parser.add_argument("--database", type=Path, default=None)
    parser.add_argument(
        "--admin-principal-id",
        default=None,
        help="test-only principal ID resolved through the example runtime config",
    )
    args = parser.parse_args(argv)

    if args.admin_principal_id is not None:
        ADMIN_PRINCIPAL = configured_harness_admin(args.admin_principal_id)

    if not (asset_root() / "index.html").is_file():
        print(
            "harness: built V2 artifact is missing; run `npm --prefix web run build` first",
            file=sys.stderr,
        )
        return 2

    database = args.database or Path(tempfile_dir()) / "operations-inventory.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    managed_root = database.parent / f"{database.stem}-manual-organize"
    repository, file_index, managed, api = build_managed_fixture(database, managed_root)
    seed(repository, api)
    global STATE
    STATE = AppState(
        database,
        repository=repository,
        api=api,
        managed=managed,
        file_index=file_index,
    )
    # The AC-T7 continuation fixture is deliberately NOT seeded here: the
    # existing inventory assertions depend on the exact four-run population.
    # The browser seeds it explicitly through ``POST /__harness__/seed-continuation``
    # when the continuation journey starts, and that seed still goes through the
    # real production coordinator.

    with make_server(
        args.host,
        args.port,
        application,
        server_class=ThreadingWSGIServer,
        handler_class=QuietHandler,
    ) as server:
        print(
            f"operations inventory harness: http://{args.host}:{args.port}/ui-v2/ "
            f"(database {database})",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def tempfile_dir() -> str:
    import tempfile

    return tempfile.mkdtemp(prefix="mediaflow-inventory-harness-")


if __name__ == "__main__":
    raise SystemExit(main())
