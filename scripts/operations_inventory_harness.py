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
import socketserver
import sys
import threading
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
    document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
    document["storages"][0]["rootPath"] = str(source_root)
    document["storages"][1]["rootPath"] = str(destination_root)
    document["resourceLibraries"][0]["storagePath"] = ""
    document["mediaLibraries"][0]["rootPath"] = "Movies"

    configuration_repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
    configuration_service = ManagedConfigurationService(
        configuration_repository,
        bootstrap_database_path=str(root / "configuration.sqlite3"),
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
            bootstrap_database_path=str(root / "configuration.sqlite3"),
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
                )
            ),
        )
    )
    managed = ManagedHarnessContext(
        root=root,
        configuration_repository=configuration_repository,
        configuration_service=configuration_service,
        bootstrap_document=document,
        active=active,
        runtime=runtime,
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
        elif path == "/__harness__/manual-file-state" and method == "GET":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            requested_file = (query.get("file") or ["Three.2003.mkv"])[0]
            document = manual_file_state(STATE, filename=requested_file)
        elif path == "/__harness__/run-standalone-pipeline" and method == "POST":
            document = run_standalone_pipeline_once(STATE)
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4183)
    parser.add_argument("--database", type=Path, default=None)
    args = parser.parse_args(argv)

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
