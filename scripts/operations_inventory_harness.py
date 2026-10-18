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
- ``POST /__harness__/seed-inventory-poll-population`` creates one active
  mixed-progress Task and three terminal failures through real Task
  coordinator/repository paths;
- ``POST /__harness__/append-inventory-poll-failure`` appends a terminal Task
  so the browser can prove that a visible terminal-only inventory refreshes;
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
import copy
import dataclasses
import io
import json
import os
import socketserver
import sys
import threading
import time
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mediaflow.application.automation import AutomationWorker  # noqa: E402
from mediaflow.application.classification_review import ClassificationReviewService  # noqa: E402
from mediaflow.application.configuration_objects import ConfigurationObjectService  # noqa: E402
from mediaflow.application.configuration_snapshot import ManagedConfigurationService  # noqa: E402
from mediaflow.application.conflict_resolution import ConfirmationService  # noqa: E402
from mediaflow.application.file_catalog import FileCatalogService  # noqa: E402
from mediaflow.application.manual_organize_worker import (  # noqa: E402
    ManualOrganizeExecutionWorker,
)
from mediaflow.application.media_organizer import (  # noqa: E402
    MediaOrganizerBatchResult,
    MediaOrganizerService,
)
from mediaflow.application.metadata import MetadataProviderRegistry  # noqa: E402
from mediaflow.application.metadata_correction import MetadataCorrectionService  # noqa: E402
from mediaflow.application.metadata_review import MetadataReviewService  # noqa: E402
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
from mediaflow.domain.classification import (  # noqa: E402
    ClassificationPolicy,
    ClassificationResult,
    ClassificationRule,
    ClassificationStatus,
)
from mediaflow.domain.configuration_management import (  # noqa: E402
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
)
from mediaflow.domain.failure import FailureExplanation  # noqa: E402
from mediaflow.domain.logging import LogLevel, OperationalLogRecord  # noqa: E402
from mediaflow.domain.media_evidence import EvidenceSection, PipelineEvidence  # noqa: E402
from mediaflow.domain.metadata import (  # noqa: E402
    CandidateMatchResult,
    CandidateMatchStatus,
    CandidateScore,
    MediaCandidate,
    MediaIdentity,
    MediaType,
    MetadataIdentificationResult,
    MetadataIdentificationStatus,
    ScoreComponent,
)
from mediaflow.domain.organizer import (  # noqa: E402
    AttachmentPolicy,
    Conflict,
    ConflictStrategy,
    ConflictType,
    ExecutionEffectCertainty,
    ExecutionResult,
    ExecutionStatus,
    OrganizeOperationType,
    OrganizePlan,
    OrganizePolicy,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.parser import ParseResult  # noqa: E402
from mediaflow.domain.recognition import (  # noqa: E402
    RecognitionResult,
    RecognitionStatus,
    RecognitionType,
)
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
    storage_adapters: dict[str, object] | None = None,
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
            "storage_adapters": storage_adapters,
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


class _QueryScopedMetadataProvider(SyntheticMetadataProvider):
    """Keep unrelated browser fixtures outside each search's candidate budget."""

    def search_movie(self, query, policy=None, **kwargs):
        candidates = super().search_movie(query, policy, **kwargs)
        title = getattr(query, "title_candidate", getattr(query, "title", query))
        normalized = "".join(
            character.casefold() for character in str(title) if character.isalnum()
        )
        return tuple(
            value
            for value in candidates
            if normalized
            in "".join(character.casefold() for character in value.title if character.isalnum())
        )


def build_managed_fixture(
    database: Path,
    root: Path,
    *,
    include_cross_storage_destinations: bool = False,
    storage_adapters: dict[str, object] | None = None,
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
    # Dedicated sibling sources for the RO-2 independence proof, so a real
    # MOVE of one can never consume the other journey's fixtures.
    (source_root / "Ninth.2009.mkv").write_bytes(b"sibling independence synthetic media")
    (source_root / "Tenth.2010.mkv").write_bytes(b"sibling independence synthetic media")
    # The RO-2 new-source ambiguity proof's own source.  It has no prior
    # Result/choice/review and exactly two tied provider candidates, so the
    # preparation must withhold automatic selection and ground both candidates
    # for a same-page choice.
    (source_root / "Eleventh.2011.mkv").write_bytes(b"ambiguous identity synthetic media")

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
    document["resourceLibraries"][0]["displayRootPath"] = str(source_root)
    document["mediaLibraries"][0]["rootPath"] = "Movies"
    document["api"]["principals"] = [
        {
            "id": ADMIN_PRINCIPAL.principal_id,
            "tokenEnv": "MEDIAFLOW_HARNESS_ADMIN_TOKEN",
            "roles": ["admin"],
            "enabled": True,
        }
    ]
    if include_cross_storage_destinations:
        document["resourceLibraries"].append(
            {
                "id": "destination",
                "name": "Destination",
                "storageId": "media-target",
                "storagePath": "",
                "enabled": True,
                "extensions": ["mkv", "txt"],
            }
        )
        document["mediaLibraries"].append(
            {
                "id": "archive",
                "name": "Archive",
                "storageId": "source-storage",
                "rootPath": "Archive",
            }
        )
        (source_root / "Archive").mkdir(parents=True, exist_ok=True)

    document["resourceLibraries"].append(
        {
            "id": "retirement",
            "name": "Retirement stability",
            "storageId": "source-storage",
            "storagePath": "Retirement",
            "enabled": True,
            "extensions": ["mkv"],
            "stability": {
                "minimumAgeSeconds": 0,
                "modifiedThresholdSeconds": 0,
                "stableSizeDurationSeconds": 3,
            },
        }
    )
    document["organizePolicies"][0]["attachments"] = {"enabled": True}
    overwrite_policy = dict(document["organizePolicies"][0])
    overwrite_policy.update(
        {"id": "overwrite-fixture", "conflictStrategy": "overwrite", "overwrite": True}
    )
    document["organizePolicies"].append(overwrite_policy)
    document["recognitionTypes"].append({"id": "overwrite-fixture", "name": "Overwrite fixture"})
    document["recognitionTypePolicies"].append(
        {
            "id": "type-overwrite-fixture",
            "recognitionType": "overwrite-fixture",
            "metadataPolicy": "C",
            "namingPolicy": "A",
            "classificationPolicy": "A",
            "organizePolicy": "overwrite-fixture",
        }
    )

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
    # Fresh sources are created after compatibility fixture indexing.
    retirement_root = source_root / "Retirement"
    retirement_root.mkdir(exist_ok=True)
    for name in ("Thirteenth.2013.mkv", "Fourteenth.2014.mkv"):
        fresh = retirement_root / name
        fresh.write_bytes(b"fresh retirement source")
        old = time.time() - 86400
        os.utime(fresh, (old, old))
    (retirement_root / "Downloading.mkv.part").write_bytes(b"temporary")
    registry = MetadataProviderRegistry(
        (
            _QueryScopedMetadataProvider(
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
                    MediaCandidate(
                        "tmdb",
                        "113",
                        MediaType.MOVIE,
                        "Thirteenth",
                        year=2013,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                    MediaCandidate(
                        "tmdb",
                        "114",
                        MediaType.MOVIE,
                        "Fourteenth",
                        year=2014,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                    MediaCandidate(
                        "tmdb",
                        "105",
                        MediaType.MOVIE,
                        "Five",
                        year=2005,
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
                    # The RO-2 sibling-independence proof's own sources, so a
                    # real MOVE of one never consumes another journey's media.
                    MediaCandidate(
                        "tmdb",
                        "109",
                        MediaType.MOVIE,
                        "Ninth",
                        year=2009,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                    MediaCandidate(
                        "tmdb",
                        "110",
                        MediaType.MOVIE,
                        "Tenth",
                        year=2010,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                    # The RO-2 new-source ambiguity proof's own tied candidates:
                    # two equally-ranked identities for one brand-new source, so
                    # the preparation must ground both and require an explicit
                    # same-page choice before anything can execute.
                    MediaCandidate(
                        "tmdb",
                        "111",
                        MediaType.MOVIE,
                        "Eleventh",
                        year=2011,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                    MediaCandidate(
                        "tmdb",
                        "911",
                        MediaType.MOVIE,
                        "Eleventh",
                        year=2011,
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
    api = build_api(
        repository,
        managed=managed,
        file_index=file_index,
        storage_adapters=storage_adapters,
    )
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
        self._inventory_poll_lock = threading.Lock()
        self.repository = repository
        self.api = api
        self.managed = managed
        self.file_index = file_index
        self.manual_run: dict[str, str] | None = None
        self.pipeline_run: dict[str, str] | None = None
        #: The paused scan Task of the AC-T7 continuation journey.
        self.continuation_task_id: str | None = None
        self.recovery_run: dict[str, str] | None = None
        self.recovery_runs: dict[str, dict[str, str]] = {}
        self.recovery_batch_run: dict[str, object] | None = None
        self.recovery_batch_summary_run: dict[str, object] | None = None
        self.task_center_problems: dict[str, object] | None = None
        self.task_center_problem_page: dict[str, object] | None = None
        self.inventory_poll_population: dict[str, object] | None = None

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


#: The definition identity the real-Python Automation lifecycle proof drives.
AUTOMATION_LIFECYCLE_DEFINITION_ID = "harness-automation"
#: The unpublished name a harness successor Draft carries for the corrupt
#: retained-history proof. It must never appear as the removed definition's
#: published history.
AUTOMATION_LIFECYCLE_DRAFT_NAME = "NEVER PUBLISHED browser draft"

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
        AutomationCommand.PREVIEW,
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
        "preview",
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


def seed_inventory_poll_population(state: AppState) -> dict[str, object]:
    """Create durable progress and terminal rows for the live inventory proof."""

    with state._inventory_poll_lock:
        if state.inventory_poll_population is not None:
            return dict(state.inventory_poll_population)
        coordinator = PersistentTaskCoordinator(state.repository, state.repository)
        now = datetime.now(UTC)
        running = coordinator.create(
            "scan",
            execute_authorized=False,
            scope_path="Movies/Inventory Live Running",
        )
        state.repository.update_task(
            dataclasses.replace(
                running,
                status=PersistentTaskStatus.RUNNING,
                started_at=now,
                updated_at=now,
                total_items=2,
                completed_items=1,
                failed_items=0,
            )
        )
        for item_id, status, stage, filename in (
            (
                "inventory-live-processed",
                TaskItemStatus.DRY_RUN,
                "completed",
                "Processed.mkv",
            ),
            (
                "inventory-live-current",
                TaskItemStatus.PROCESSING,
                "organizing",
                "Current.mkv",
            ),
        ):
            state.repository.upsert_item(
                PersistentTaskItem(
                    item_id=item_id,
                    task_id=running.task_id,
                    storage_id="harness-inventory-storage",
                    resource_library_id="harness-inventory-library",
                    source_path=f"Inventory Live/{filename}",
                    source_display=filename,
                    status=status,
                    stage=stage,
                    attempts=1,
                    created_at=now,
                    updated_at=now,
                )
            )

        terminal: list[dict[str, str]] = []
        for index in range(1, 4):
            task = coordinator.create(
                "scan",
                execute_authorized=False,
                scope_path=f"Movies/Inventory Poll {index:02}",
            )
            failed_at = now + timedelta(milliseconds=index)
            state.repository.update_task(
                dataclasses.replace(
                    task,
                    status=PersistentTaskStatus.FAILED,
                    updated_at=failed_at,
                    completed_at=failed_at,
                    total_items=1,
                    completed_items=0,
                    failed_items=1,
                    error="synthetic inventory polling fixture",
                )
            )
            state.repository.upsert_item(
                PersistentTaskItem(
                    item_id=f"inventory-poll-failure-{index:02}",
                    task_id=task.task_id,
                    storage_id="harness-inventory-storage",
                    resource_library_id="harness-inventory-library",
                    source_path=f"Inventory Poll/{index:02}.mkv",
                    source_display=f"{index:02}.mkv",
                    status=TaskItemStatus.FAILED,
                    stage="failed",
                    attempts=1,
                    created_at=failed_at,
                    updated_at=failed_at,
                    error="synthetic inventory polling fixture",
                )
            )
            terminal.append({"taskId": task.task_id, "scope": task.scope_path or ""})
        state.inventory_poll_population = {
            "runningTaskId": running.task_id,
            "terminalFailures": terminal,
            "appendedFailure": None,
        }
        return dict(state.inventory_poll_population)


def append_inventory_poll_failure(state: AppState) -> dict[str, object]:
    """Append one terminal failure through the supported Task producer."""

    with state._inventory_poll_lock:
        population = state.inventory_poll_population
        if population is None:
            raise RuntimeError("inventory poll population has not been seeded")
        existing = population.get("appendedFailure")
        if isinstance(existing, dict):
            return dict(existing)
        task = PersistentTaskCoordinator(state.repository, state.repository).create(
            "scan",
            execute_authorized=False,
            scope_path="Movies/Inventory Poll 04",
        )
        failed_at = datetime.now(UTC)
        state.repository.update_task(
            dataclasses.replace(
                task,
                status=PersistentTaskStatus.FAILED,
                updated_at=failed_at,
                completed_at=failed_at,
                total_items=1,
                completed_items=0,
                failed_items=1,
                error="synthetic inventory polling fixture",
            )
        )
        state.repository.upsert_item(
            PersistentTaskItem(
                item_id="inventory-poll-failure-04",
                task_id=task.task_id,
                storage_id="harness-inventory-storage",
                resource_library_id="harness-inventory-library",
                source_path="Inventory Poll/04.mkv",
                source_display="04.mkv",
                status=TaskItemStatus.FAILED,
                stage="failed",
                attempts=1,
                created_at=failed_at,
                updated_at=failed_at,
                error="synthetic inventory polling fixture",
            )
        )
        result = {"taskId": task.task_id, "scope": task.scope_path or ""}
        population["appendedFailure"] = result
        return dict(result)


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
        ("scan", "preview", "organize", "media_discovery"),
        configuration_snapshot_id=active.revision_id,
        configuration_snapshot_digest=active.digest,
        runtime_schema_version=SCHEMA_VERSION,
    )
    return {"registered": True}


def run_discovery_worker_once(state: AppState) -> dict[str, object]:
    """Advance one admitted preparation through the real bounded-discovery Worker.

    A full preparation first completes its zero-mutation walk, then internally
    freezes the reviewed sources and runs the complete production analysis to
    link the exact Preview.  Each call advances one bounded pass, so the browser
    journey can observe the real durable stages.
    """

    from mediaflow.application.media_discovery_worker import MediaDiscoveryWorker

    service = getattr(state.api, "_media_discovery", None)
    if service is None:
        return {"advanced": False, "reason": "no media discovery service"}
    with state._manual_lock:
        worker = MediaDiscoveryWorker(
            service, worker_id="harness-discovery-worker", notice=lambda _line: None
        )
        advanced = worker.run_next()
        if advanced is None:
            return {"advanced": False, "reason": "no admitted discovery"}
        durable = state.repository.get_media_discovery(advanced.discovery_id)
        if durable is None:
            raise RuntimeError("discovery Worker lost its durable record")
        return {
            "advanced": True,
            "discoveryId": durable.discovery_id,
            "status": durable.status.value,
            "previewId": durable.preview_id,
            "intentId": durable.intent_id,
            "frozen": durable.frozen,
        }


def run_manual_worker_once(state: AppState) -> dict[str, object]:
    """Claim one UI-admitted execution and complete it with the real Worker."""

    with state._manual_lock:
        manual_execution = state.api._manual_execution
        actual_executor = manual_execution._executor
        fail_before_mutation = getattr(state, "fail_next_manual_execution", False)
        if fail_before_mutation:
            manual_execution._executor = _PreMutationFailureExecutor()
            state.fail_next_manual_execution = False
        try:
            completed = ManualOrganizeExecutionWorker(
                manual_execution,
                worker_id="harness-manual-worker",
                notice=lambda _line: None,
            ).run_next()
        finally:
            manual_execution._executor = actual_executor
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


def operations_origin_state(state: AppState, *, task_id: str) -> dict[str, object]:
    """Report the durable definition origin of one executed Operations run.

    Reads the real unified Operations projection the operator's own list uses,
    so the browser journey can prove that Automation history and Operations
    reach the *same* durable run with the frozen definition origin, rather than
    a dummy Job or a read-time guess from today's Active configuration.
    """

    if not task_id:
        return {"found": False}
    try:
        overviews = state.repository.list_operations_runs(limit=50)
    except Exception:
        return {"found": False}
    for overview in overviews:
        if overview.task_id != task_id:
            continue
        return {
            "found": True,
            "taskId": overview.task_id,
            "originKind": overview.origin_kind,
            "originDefinitionId": overview.origin_definition_id,
            "originDefinitionName": overview.origin_definition_name,
        }
    return {"found": False}


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


def seed_batch_summary_recovery(state: AppState) -> dict[str, object]:
    """Create a real two-item Manual batch recovery for the R3 browser proof.

    Two sources are admitted through the production Manual Organize services,
    executed by a failure seam that stops before any Storage mutation, then run
    through the real batch continuation and the real resident Worker so each
    child has its own completed linked re-analysis.  The operator then prepares
    each child's independent summary and confirms only the ready subset in the
    task's own interface.
    """

    with state._manual_lock:
        if state.recovery_batch_summary_run is not None:
            return dict(state.recovery_batch_summary_run)
        active = state.managed.active
        names = (
            "Batch/C/BatchSummaryA.2012.mkv",
            "Batch/C/BatchSummaryB.2013.mkv",
        )
        source_files = {}
        for name in names:
            source = state.managed.root / "source" / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"synthetic batch summary media")
            source_files[name] = source
        scan = StorageScanner(
            state.managed.runtime.create_storages(),
            state.file_index,
            clock=lambda: datetime.now(UTC) + timedelta(hours=2),
        ).scan(state.managed.runtime.resource_libraries[0])
        if scan.status.value != "completed":
            raise RuntimeError("batch summary fixture ResourceLibrary scan did not complete")

        provider = state.managed.metadata_registry.resolve("tmdb")
        existing_candidates = tuple(getattr(provider, "_candidates", ()))
        provider._candidates = existing_candidates + tuple(
            MediaCandidate(
                "tmdb",
                provider_id,
                MediaType.MOVIE,
                title,
                year=2012,
                genres=("Animation",),
                countries=("JP",),
            )
            for provider_id, title in (("212", "BatchSummaryA"), ("213", "BatchSummaryB"))
            if not any(value.provider_id == provider_id for value in existing_candidates)
        )
        state.api._worker_service.register_worker(
            "harness-batch-summary-worker",
            "Harness Batch Summary Worker",
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
            body={"paths": list(names)},
            token=HARNESS_ADMIN_TOKEN,
        )
        if status != 201:
            raise RuntimeError(f"batch summary intent failed: {status}")
        for item in intent["items"]:
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
                raise RuntimeError(f"batch summary choice failed: {status}")
        status, preview = wsgi_request(
            state.api,
            "POST",
            f"/api/v1/operations/organize/intents/{intent['intentId']}/previews",
            body={"expectedVersion": intent["version"]},
            token=HARNESS_ADMIN_TOKEN,
        )
        if status != 201:
            raise RuntimeError(f"batch summary Preview failed: {status}")
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
            raise RuntimeError(f"batch summary admission failed: {status}")
        manual_execution = state.api._manual_execution
        actual_executor = manual_execution._executor
        manual_execution._executor = _PreMutationFailureExecutor()
        try:
            completed = ManualOrganizeExecutionWorker(
                manual_execution,
                worker_id="harness-batch-summary-worker",
                notice=lambda _line: None,
            ).run_next()
        finally:
            manual_execution._executor = actual_executor
        if completed is None or completed.status.value != "failed":
            raise RuntimeError("batch summary fixture did not produce a safe failure")
        durable = state.repository.get_manual_execution(execution["executionId"])
        if durable is None or len(durable.items) != 2:
            raise RuntimeError("batch summary fixture lost its manual execution items")
        item_ids = tuple(value.task_item_id for value in durable.items)
        state.recovery_batch_summary_run = {
            "runId": durable.task_id,
            "taskId": durable.task_id,
            "itemIds": list(item_ids),
            "executionId": durable.execution_id,
            "sourceNames": list(names),
        }
        return dict(state.recovery_batch_summary_run)


def seed_task_item_recovery_journey(state: AppState, kind: str = "recognition") -> dict[str, str]:
    """Create a real linked Manual TaskItem at a native recovery decision.

    The Manual intent, exact Preview, execution admission, Worker claim and
    failure Result all use the product services. The failure executor is a
    deterministic test seam that fails before Storage is touched; a subsequent
    real RecognitionReviewService row provides the legal waiting state the
    browser resolves through the product API.
    """

    supported = {
        "recognition",
        "metadata",
        "metadata_correction",
        "classification",
        "conflict",
        "conflict_overwrite",
        "technical",
        "technical_success",
        "attachment",
    }
    if kind not in supported:
        raise ValueError("unsupported recovery fixture kind")
    with state._manual_lock:
        if kind in state.recovery_runs:
            return dict(state.recovery_runs[kind])
        if kind == "attachment":
            # Earlier sequential browser cases intentionally leave admitted work.
            # Settle only never-started fixture executions without running media effects.
            for task in state.repository.list_tasks(limit=1000, command="manual_organize"):
                for pending in state.repository.list_manual_executions_for_task(task.task_id):
                    if pending.status.value == "admitted":
                        state.api._manual_execution.fail_unstarted_execution(
                            pending.execution_id,
                            RuntimeError("prior browser fixture settled before next case"),
                        )
        active = state.managed.active
        titles = {
            "recognition": "Recovery",
            "metadata": "MetadataChoice",
            "metadata_correction": "MetadataCorrection",
            "classification": "ClassificationRecovery",
            "conflict": "ConflictRecovery",
            "conflict_overwrite": "ConflictOverwriteRecovery",
            "technical": "TechnicalRecovery",
            "technical_success": "TechnicalRecoveryChain",
            "attachment": "AttachmentRecovery",
        }
        years = {
            "recognition": 2005,
            "metadata": 2015,
            "metadata_correction": 2016,
            "classification": 2017,
            "conflict": 2018,
            "conflict_overwrite": 2020,
            "technical": 2019,
            "technical_success": 2021,
            "attachment": 2022,
        }
        organize_policy_id = "overwrite-fixture" if kind == "conflict_overwrite" else "A"
        recognition_type_id = "overwrite-fixture" if kind == "conflict_overwrite" else "C"
        title = titles[kind]
        year = years[kind]
        filename = f"{title}.{year}.mkv"
        provider_id = {
            "recognition": "205",
            "metadata": "215",
            "metadata_correction": "216",
            "classification": "217",
            "conflict": "218",
            "conflict_overwrite": "220",
            "technical": "219",
            "technical_success": "221",
            "attachment": "222",
        }[kind]
        source_file = state.managed.root / "source" / filename
        source_file.write_bytes(b"synthetic recovery media; no real codec parsing")
        if kind == "attachment":
            source_file.with_suffix(".en.srt").write_bytes(b"subtitle")
        scan = StorageScanner(
            state.managed.runtime.create_storages(),
            state.file_index,
            clock=lambda: datetime.now(UTC) + timedelta(hours=2),
        ).scan(state.managed.runtime.resource_libraries[0])
        if scan.status.value != "completed":
            raise RuntimeError("recovery fixture ResourceLibrary scan did not complete")

        provider = state.managed.metadata_registry.resolve("tmdb")
        existing_candidates = tuple(getattr(provider, "_candidates", ()))
        if not any(value.provider_id == provider_id for value in existing_candidates):
            provider._candidates = existing_candidates + (
                MediaCandidate(
                    "tmdb",
                    provider_id,
                    MediaType.MOVIE,
                    title,
                    year=year,
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
                "recognitionTypeId": recognition_type_id,
                "namingPolicyId": "A",
                "classificationPolicyId": "A",
                "organizePolicyId": organize_policy_id,
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
        if kind == "attachment":
            attachment_target = (
                state.managed.root
                / "destination"
                / manual_item.plan["executionPlan"]["attachments"][0]["destination"]["path"]
            )
            attachment_target.parent.mkdir(parents=True, exist_ok=True)
            attachment_target.write_bytes(b"preserve existing subtitle")
        current = state.repository.get_item(manual_item.task_item_id)
        if current is None or current.status is not TaskItemStatus.FAILED:
            raise RuntimeError("recovery fixture item did not persist its failed outcome")
        processing = dataclasses.replace(
            current, status=TaskItemStatus.PROCESSING, stage="metadata"
        )
        state.repository.upsert_item(processing)
        if kind != "recognition":
            prior_recognition = RecognitionReviewService(
                state.repository,
                state.managed.runtime.strategy.recognition_types,
            ).create(
                processing,
                RecognitionResult(status=RecognitionStatus.UNRECOGNIZED),
            )
            RecognitionReviewService(
                state.repository,
                state.managed.runtime.strategy.recognition_types,
            ).resolve(prior_recognition.review_id, recognition_type_id, actor="harness")
            processing = state.repository.get_item(manual_item.task_item_id)
            if processing is None:
                raise RuntimeError("recovery fixture lost its resolved Recognition TaskItem")
            processing = dataclasses.replace(
                processing, status=TaskItemStatus.PROCESSING, stage="metadata"
            )
        state.repository.upsert_item(processing)
        review_id = None
        if kind == "recognition":
            review = RecognitionReviewService(
                state.repository,
                state.managed.runtime.strategy.recognition_types,
            ).create(
                processing,
                RecognitionResult(status=RecognitionStatus.UNRECOGNIZED),
            )
            review_id = review.review_id
        elif kind in {"metadata", "attachment"}:
            candidate = MediaCandidate(
                "tmdb",
                provider_id,
                MediaType.MOVIE,
                title,
                year=year,
                genres=("Animation",),
                countries=("JP",),
            )
            identification = MetadataIdentificationResult(
                MetadataIdentificationStatus.NEED_CONFIRM,
                RecognitionType("C", "Special"),
                match=CandidateMatchResult(
                    CandidateMatchStatus.NEED_CONFIRM,
                    candidate,
                    72,
                    (CandidateScore(candidate, 72, (ScoreComponent("title", 72, "title match"),)),),
                ),
                query=title,
            )
            policy = next(
                value
                for value in state.managed.runtime.strategy.metadata_policies
                if value.policy_id == "C" and value.enabled
            )
            review = MetadataReviewService(state.repository).create(
                processing, identification, policy.policy_id
            )
            review_id = review.review_id
        elif kind == "metadata_correction":
            policy = next(
                value
                for value in state.managed.runtime.strategy.metadata_policies
                if value.policy_id == "C" and value.enabled
            )
            review = MetadataCorrectionService(state.repository, (policy,)).create(
                processing,
                MetadataIdentificationResult(
                    MetadataIdentificationStatus.NOT_FOUND,
                    RecognitionType("C", "Special"),
                    query=title,
                ),
                policy,
                ParseResult(title, year=year, original_filename=filename),
            )
            review_id = review.review_id
        elif kind == "classification":
            policy = next(
                value
                for value in state.managed.runtime.strategy.classification_policies
                if value.policy_id == "A" and value.enabled
            )
            review = ClassificationReviewService(state.repository).create(
                processing,
                ClassificationResult(
                    policy_id=policy.policy_id,
                    recognition_type_id="C",
                    status=ClassificationStatus.UNCLASSIFIED,
                ),
                policy,
                MediaIdentity(
                    "tmdb",
                    provider_id,
                    MediaType.MOVIE,
                    title,
                    year=year,
                    genres=("Animation",),
                    countries=("JP",),
                    recognition_type_id="C",
                ),
            )
            review_id = review.review_id
        elif kind in {"conflict", "conflict_overwrite"}:
            target_path = str(manual_item.plan["executionPlan"]["targetPath"])
            destination = state.managed.root / "destination" / target_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"existing destination must be preserved")
            policy = next(
                value
                for value in state.managed.runtime.strategy.organize_policies
                if value.policy_id == organize_policy_id
            )
            plan = OrganizePlan(
                source_storage_id="source-storage",
                target_storage_id="media-target",
                source=filename,
                target=target_path,
                recognition_type_id="C",
                naming_policy_id="A",
                classification_policy_id="A",
                organize_policy_id=policy.policy_id,
                conflicts=(
                    Conflict(
                        ConflictType.DESTINATION_EXISTS,
                        filename,
                        target_path,
                        "destination already exists",
                    ),
                ),
                status=PlanStatus.CONFLICT,
                plan_id=str(manual_item.plan["planId"]),
                source_location=StorageLocation("source-storage", filename),
                destination_location=StorageLocation("media-target", target_path),
            )
            waiting = dataclasses.replace(
                processing,
                status=TaskItemStatus.WAITING_CONFIRM,
                stage="waiting_confirm",
            )
            confirmation = ConfirmationService(state.repository).create(
                task_id=durable.task_id,
                item_id=manual_item.task_item_id,
                plan=plan,
                policy=policy,
                item=waiting,
            )
            review_id = confirmation.confirmation_id
        else:
            failure = FailureExplanation(
                category="technical_dependency_unavailable",
                message=(
                    "a temporary dependency stopped the previous attempt before Storage mutation"
                ),
                durable_state="failed",
                side_effects="none",
                retry_safe=True,
                next_action=(
                    "repair the dependency, then continue this item through a fresh pinned DryRun"
                ),
            )
            failed = dataclasses.replace(
                current,
                status=TaskItemStatus.FAILED,
                stage="failed",
                error=failure.encode(),
            )
            state.repository.upsert_item(failed)
            # Preserve a successful and effect-unknown sibling in the same
            # mixed task while the operator repairs only this item.
            coordinator = PersistentTaskCoordinator(state.repository, state.repository)
            latest_task = state.repository.get_task(durable.task_id)
            if latest_task is None:
                raise RuntimeError("technical recovery fixture lost its Task")
            state.repository.update_task(
                dataclasses.replace(
                    latest_task,
                    status=PersistentTaskStatus.RUNNING,
                    completed_at=None,
                    updated_at=datetime.now(UTC),
                )
            )
            success = coordinator.begin_item(
                durable.task_id,
                "source-storage",
                "source",
                "TechnicalRecoverySuccess.2019.mkv",
                "TechnicalRecoverySuccess.2019.mkv",
            )
            success = dataclasses.replace(success, status=TaskItemStatus.SUCCESS, stage="completed")
            state.repository.upsert_item(success)
            state.repository.release(success.storage_id, success.source_path, success.task_id)
            unknown = coordinator.begin_item(
                durable.task_id,
                "source-storage",
                "source",
                "TechnicalRecoveryUnknown.2019.mkv",
                "TechnicalRecoveryUnknown.2019.mkv",
            )
            unknown_failure = FailureExplanation(
                category="execution_outcome_unknown",
                message="the sibling's prior effect could not be verified",
                durable_state="inspection_required",
                side_effects="unknown",
                retry_safe=False,
                next_action="inspect this sibling's effect evidence before taking another action",
            )
            unknown = dataclasses.replace(
                unknown,
                status=TaskItemStatus.FAILED,
                stage="execution_outcome_unknown",
                error=unknown_failure.encode(),
            )
            state.repository.upsert_item(unknown)
            state.repository.release(unknown.storage_id, unknown.source_path, unknown.task_id)
            now = datetime.now(UTC)
            state.repository.append_result(
                PersistentResultRecord(
                    result_id=f"{unknown.item_id}-unknown-result",
                    task_id=durable.task_id,
                    item_id=unknown.item_id,
                    source_storage_id=unknown.storage_id,
                    source_path=unknown.source_path,
                    destination_storage_id="media-target",
                    destination_path="Movies/TechnicalRecoveryUnknown.mkv",
                    recognition_type="C",
                    provider="tmdb",
                    provider_id="9001",
                    metadata_policy_id="C",
                    naming_policy_id="A",
                    classification_policy_id="A",
                    organize_policy_id="A",
                    operation="MOVE",
                    status="FAILED",
                    created_at=now,
                    title="Technical recovery unknown sibling",
                    completed_operations=("MOVE",),
                    effect_certainty="attempted_unverified",
                    uncertain_effects=("mutation_outcome",),
                    error=unknown_failure.encode(),
                )
            )
            state.repository.update_task(
                dataclasses.replace(
                    state.repository.get_task(durable.task_id),
                    status=PersistentTaskStatus.PARTIAL_SUCCESS,
                    total_items=3,
                    completed_items=1,
                    failed_items=2,
                    updated_at=now,
                    completed_at=now,
                )
            )
            # Introduce an ambiguous new Metadata blocker only after the
            # original manual plan has safely failed and the recovery Worker
            # is later admitted, so setup cannot consume or bias its intent.
            alternate = MediaCandidate(
                "tmdb",
                "930" if kind == "technical_success" else "929",
                MediaType.MOVIE,
                title,
                year=year,
                genres=("Animation",),
                countries=("JP",),
            )
            provider._candidates = tuple(provider._candidates) + (alternate,)
        run = {
            "runId": durable.task_id,
            "taskId": durable.task_id,
            "itemId": manual_item.task_item_id,
            "previewId": preview["previewId"],
            "executionId": durable.execution_id,
            "reviewId": review_id or "",
            "sourcePath": filename,
            "kind": kind,
            "providerId": provider_id,
            "targetPath": (
                str(manual_item.plan["executionPlan"]["targetPath"])
                if kind in {"conflict", "conflict_overwrite"}
                else ""
            ),
        }
        if source_file.read_bytes() != b"synthetic recovery media; no real codec parsing":
            raise RuntimeError("zero-mutation recovery fixture changed the source")
        state.recovery_runs[kind] = run
        state.recovery_run = state.recovery_run or run
        return dict(run)


def run_task_item_recovery_worker_once(
    state: AppState, *, item_id: str | None = None
) -> dict[str, object]:
    """Run the real resident queued-workflow handler for the recovery Job."""

    recovery_item_ids = [
        str(value)
        for value in (
            *(run.get("itemId") for run in state.recovery_runs.values()),
            state.recovery_run.get("itemId") if state.recovery_run else None,
            state.recovery_batch_run.get("singleItemId") if state.recovery_batch_run else None,
            state.recovery_batch_run.get("batchEligibleItemId")
            if state.recovery_batch_run
            else None,
        )
        if value is not None and (item_id is None or str(value) == item_id)
    ]
    if item_id is not None and not recovery_item_ids:
        # Linked blocker TaskItems are native recovery subjects too; the
        # explicit ID is read from the product's recovery detail response.
        recovery_item_ids = [item_id]
    if item_id is None and state.recovery_batch_summary_run is not None:
        recovery_item_ids.extend(
            str(value) for value in state.recovery_batch_summary_run["itemIds"]
        )
    if not recovery_item_ids:
        raise RuntimeError("task-item recovery fixture has not been seeded")
    from mediaflow.final_cli import _run_queued_workflow

    queued = min(
        (
            value
            for item_id in recovery_item_ids
            for value in state.repository.list_recovery_continuations(item_id, limit=10)
            if value.status.value == "queued" and value.new_task_id is None
        ),
        key=lambda value: value.created_at,
        default=None,
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
    # fixture. Jobs that belong to *any* recovery continuation (for example the
    # sibling child of a two-item batch) are never closed: each child owns its
    # own durable Job and must reach its own outcome.
    recovery_job_ids = {
        value.job_id
        for item_id in recovery_item_ids
        for value in state.repository.list_recovery_continuations(item_id, limit=10)
        if value.job_id is not None
    }
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
        if pending[0].job_id in recovery_job_ids:
            # Another recovery child owns this Job; leave it for its own call.
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
        "continuationError": continuation.error if continuation else None,
        "continuationRecovery": continuation.recovery if continuation else None,
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


def batch_summary_recovery_state(state: AppState) -> dict[str, object]:
    """Return read-only state for the two-item real Manual batch summary proof."""

    if state.recovery_batch_summary_run is None:
        return {"available": False}
    run = state.recovery_batch_summary_run
    item_ids = [str(value) for value in run["itemIds"]]
    items = {item_id: state.repository.get_item(item_id) for item_id in item_ids}
    continuations = {
        item_id: state.repository.list_recovery_continuations(item_id, limit=10)
        for item_id in item_ids
    }
    return {
        "available": True,
        "taskId": run["taskId"],
        "itemIds": item_ids,
        "itemStatuses": {
            item_id: value.status.value if value is not None else None
            for item_id, value in items.items()
        },
        "continuations": {
            item_id: [
                {
                    "status": value.status.value,
                    "newTaskId": value.new_task_id,
                    "newResultId": value.new_result_id,
                }
                for value in rows
            ]
            for item_id, rows in continuations.items()
        },
        "sourceExists": {
            name: (state.managed.root / "source" / name).is_file() for name in run["sourceNames"]
        },
        "targetFiles": [
            value.relative_to(state.managed.root / "destination").as_posix()
            for value in (state.managed.root / "destination").rglob("*")
            if value.is_file()
        ],
    }


def task_item_recovery_state(state: AppState, *, item_id: str | None = None) -> dict[str, object]:
    """Return bounded test-only state for independent source/result assertions."""

    run = next(
        (
            value
            for value in state.recovery_runs.values()
            if item_id is not None and value.get("itemId") == item_id
        ),
        state.recovery_run if item_id is None else None,
    )
    if run is None:
        return {"available": False}
    task = state.repository.get_task(run["taskId"])
    source = state.repository.get_item(run["itemId"])
    success_item = (
        state.repository.get_item(run["successItemId"]) if run.get("successItemId") else None
    )
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
    provider = state.managed.metadata_registry.resolve("tmdb")
    return {
        "available": True,
        "taskId": run["taskId"],
        "itemId": run["itemId"],
        "successItemId": run.get("successItemId"),
        "taskStatus": task.status.value if task else None,
        "itemStatus": source.status.value if source else None,
        "itemStage": source.stage if source else None,
        "continuationStatus": continuation.status.value if continuation else None,
        "analysisTaskId": continuation.new_task_id if continuation else None,
        "analysisTaskStatus": analysis_task.status.value if analysis_task else None,
        "analysisItemId": analysis_items[0].item_id if analysis_items else None,
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
        "sourceResultHistory": [
            {
                "resultId": value.result_id,
                "status": value.status,
                "effectCertainty": value.effect_certainty,
            }
            for value in state.repository.list_results(run["taskId"], limit=100)
            if value.item_id == run["itemId"]
        ],
        "siblingStatuses": {
            value.source_path: value.status.value
            for value in state.repository.list_items(run["taskId"])
            if value.item_id != run["itemId"]
        },
        "providerCalls": getattr(provider, "calls", None),
        "conflictTargetPreserved": (
            (state.managed.root / "destination" / run["targetPath"]).read_bytes()
            == b"existing destination must be preserved"
            if run.get("kind") in {"conflict", "conflict_overwrite"}
            and (state.managed.root / "destination" / run["targetPath"]).is_file()
            else None
        ),
        "sourceExists": (state.managed.root / "source" / run["sourcePath"]).is_file(),
        "successItemStatus": (success_item.status.value if success_item is not None else None),
        "successSourceExists": (
            (state.managed.root / "source" / str(run["successSourcePath"])).is_file()
            if run.get("successSourcePath")
            else None
        ),
        "successResultId": run.get("successResultId"),
        "targetFiles": [
            value.relative_to(state.managed.root / "destination").as_posix()
            for value in (state.managed.root / "destination").rglob("*")
            if value.is_file()
        ],
    }


def task_result_state(state: AppState, *, task_id: str | None = None) -> dict[str, object]:
    """Return bounded durable item/result evidence for one harness Task."""

    if not isinstance(task_id, str) or not task_id.strip():
        return {"available": False}
    task = state.repository.get_task(task_id)
    if task is None:
        return {"available": False}
    return {
        "available": True,
        "taskId": task.task_id,
        "taskStatus": task.status.value,
        "items": [
            {
                "itemId": item.item_id,
                "sourcePath": item.source_path,
                "status": item.status.value,
            }
            for item in state.repository.list_items(task_id, limit=100)
        ],
        "results": [
            {
                "resultId": result.result_id,
                "itemId": result.item_id,
                "sourcePath": result.source_path,
                "status": result.status,
                "effectCertainty": result.effect_certainty,
                "completedOperations": list(result.completed_operations),
            }
            for result in state.repository.list_results(task_id, limit=100)
        ],
    }


def manual_file_state(state: AppState, filename: str = "Three.2003.mkv") -> dict[str, object]:
    """Return relative-only state for one new-task synthetic source file.

    The file identity comes from the harness query string (`file=`); the
    default keeps the original new-task journey file. The name is validated
    against the synthetic fixture set so the read stays bounded to files the
    harness itself created.
    """

    allowed = (
        "One.2001.mkv",
        "Two.2002.mkv",
        "Three.2003.mkv",
        "Four.2004.mkv",
        "Ninth.2009.mkv",
        "Tenth.2010.mkv",
        "Eleventh.2011.mkv",
    )
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
AUTHORITY_MISSING_PIN_SCOPE = "AuthorityMissingPin"
AUTHORITY_MISSING_PIN_FILES = ("BrokenPinA.2017.mkv", "BrokenPinB.2018.mkv")
AUTHORITY_TARGETS = (
    "Movies/Movies/Anime/Seven (2007) [tmdbid-107]/Seven (2007).mkv",
    "Movies/Movies/Anime/Eight (2008) [tmdbid-108]/Eight (2008).mkv",
)

CONTINUATION_RECORDED_FILE = "C/Continuation/Six.2006.mkv"
CONTINUATION_SOURCE_FILE = "C/Continuation/Five.2005.mkv"


def seed_continuation_journey(state: AppState) -> dict[str, object]:
    """Create one real paused Preview Task with one already-recorded source.

    This is a genuine durable state produced by the real production
    coordinator: a Preview Task that discovered exactly one source and was then
    durably paused at a supported item boundary.  Its item budget is two, so
    exactly one unit of remaining work exists — the continuation must process
    that one and nothing else.
    """

    active = state.managed.active
    source_root = state.managed.root / "source"
    (source_root / "C" / "Continuation").mkdir(parents=True, exist_ok=True)
    (source_root / CONTINUATION_SOURCE_FILE).write_bytes(b"continuation synthetic media")
    coordinator = PersistentTaskCoordinator(state.repository, state.repository)
    task = coordinator.create(
        "preview",
        execute_authorized=False,
        scope_path=str(source_root / "C" / "Continuation"),
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
    with patch(
        "mediaflow.final_cli.metadata_provider_registry_from_environment",
        lambda _provider_ids: state.managed.metadata_registry,
    ):
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


def publish_configuration_successor(state: AppState):
    """Publish a checked, operationally identical B successor for pin tests."""

    service = state.managed.configuration_service
    active = service.active()
    if active is None:
        raise RuntimeError("temporary managed configuration has no Active revision")
    draft = service.import_draft(active.document, actor="harness-authority-successor")
    validated = service.validate(draft.revision_id, actor="harness-authority-successor")
    objects = state.api._configuration_objects
    if objects is None:
        raise RuntimeError("temporary managed configuration object service is unavailable")
    for storage_id in ("source-storage", "media-target"):
        checked = objects.storage_check(
            validated.revision_id,
            storage_id=storage_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="harness-authority-successor",
        )
        if checked.status is not ConfigurationStorageCheckStatus.PASSED:
            raise RuntimeError(f"successor Storage check failed for {storage_id}")
    strategy = objects.recognition_strategy_test(
        validated.revision_id,
        expected_version=validated.version,
        expected_digest=validated.digest,
        actor="harness-authority-successor",
        resource_library_id="source",
        synthetic_path="Example.Movie.2024.1080p.mkv",
    )
    if strategy.status is not ConfigurationStrategyTestStatus.COMPLETED:
        raise RuntimeError("successor recognition strategy test did not complete")
    destination = objects.destination_precheck(
        validated.revision_id,
        expected_version=validated.version,
        expected_digest=validated.digest,
        actor="harness-authority-successor",
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
        raise RuntimeError("successor destination precheck did not complete")
    return objects.activate_checked(
        validated.revision_id,
        expected_version=validated.version,
        actor="harness-authority-successor",
    )


def authority_execution_state(
    state: AppState, *, source_task_id: str | None = None
) -> dict[str, object]:
    """Expose only the authority-pin and fixture-file evidence for the browser proof."""

    task = state.repository.get_task(source_task_id) if source_task_id else None
    active = state.managed.configuration_service.active()
    scope = task.scope_path if task is not None and task.scope_path else AUTHORITY_SCOPE
    filenames = (
        AUTHORITY_MISSING_PIN_FILES
        if scope == AUTHORITY_MISSING_PIN_SCOPE
        else (AUTHORITY_FIRST_FILE, AUTHORITY_SECOND_FILE)
    )
    source_root = state.managed.root / "source" / scope
    destination_root = state.managed.root / "destination"
    destination_paths = AUTHORITY_TARGETS if scope == AUTHORITY_SCOPE else ()
    return {
        "available": task is not None,
        "sourceTaskId": task.task_id if task else None,
        "scope": scope,
        "sourceTaskStatus": task.status.value if task else None,
        "taskSnapshotId": task.configuration_snapshot_id if task else None,
        "taskSnapshotDigest": task.configuration_snapshot_digest if task else None,
        "activeSnapshotId": active.revision_id if active else None,
        "activeSnapshotDigest": active.digest if active else None,
        "sourceFiles": {filename: (source_root / filename).is_file() for filename in filenames},
        "destinationFiles": sorted(
            relative_path
            for relative_path in destination_paths
            if (destination_root / relative_path).is_file()
        ),
    }


def seed_authority_refusal(state: AppState, *, missing_snapshot: bool = False) -> dict[str, object]:
    """Create one real paused Task that was admitted as a mutation.

    Its ``execute_authorized`` boolean records the original admission, but no
    live reusable execution authority exists for it: it has no definition-linked
    occurrence Job and therefore no unattended grant.  The backend must refuse a
    native Continue and name the exact-Preview/explicit-intent journey instead of
    continuing under the stored boolean.
    """

    active = state.managed.active
    current_active = state.managed.configuration_service.active() or active
    # A dedicated, ResourceLibrary-relative scope holding exactly two eligible
    # sources, so the native exact Preview really has a remaining scope to
    # review under the run's own pin.
    source_root = state.managed.root / "source"
    fixture_scope = AUTHORITY_MISSING_PIN_SCOPE if missing_snapshot else AUTHORITY_SCOPE
    fixture_files = (
        AUTHORITY_MISSING_PIN_FILES
        if missing_snapshot
        else (AUTHORITY_FIRST_FILE, AUTHORITY_SECOND_FILE)
    )
    authority_root = source_root / fixture_scope
    authority_root.mkdir(parents=True, exist_ok=True)
    (authority_root / fixture_files[0]).write_bytes(b"authority synthetic media")
    (authority_root / fixture_files[1]).write_bytes(b"authority synthetic media two")
    coordinator = PersistentTaskCoordinator(state.repository, state.repository)
    task_snapshot_id = (
        "harness-missing-configuration-revision" if missing_snapshot else active.revision_id
    )
    task = coordinator.create(
        "preview",
        execute_authorized=True,
        scope_path=fixture_scope,
        item_limit=2,
        configuration_snapshot_id=task_snapshot_id,
        configuration_snapshot_digest=current_active.digest if missing_snapshot else active.digest,
        require_configuration_snapshot=True,
    )
    state.repository.request_task_pause(task.task_id, datetime.now(UTC))
    paused = coordinator.acknowledge_pause(task.task_id)
    if paused.status is not PersistentTaskStatus.PAUSED:
        raise RuntimeError("authority-refusal fixture Task did not pause")
    successor = None if missing_snapshot else publish_configuration_successor(state)
    return {
        "taskId": task.task_id,
        "status": paused.status.value,
        "scope": fixture_scope,
        "taskSnapshotId": task_snapshot_id,
        "activeSnapshotId": (successor.revision_id if successor else current_active.revision_id),
        "remainingSources": list(fixture_files),
    }


def run_automation_run_once_worker(state: AppState, *, discovery_id: str) -> dict[str, object]:
    """Advance the admitted definition-bound Run once with the real Worker.

    The API only *admits* the discovery; this route is the resident
    Processing-Worker boundary that turns it into bounded, metadata-only
    Storage observations and freezes the manifest.  It never mutates Storage.
    """

    from mediaflow.application.media_discovery_worker import MediaDiscoveryWorker

    service = getattr(state.api, "_media_discovery", None)
    if service is None:
        return {"advanced": False, "reason": "media discovery service is unavailable"}
    worker = MediaDiscoveryWorker(service, worker_id="harness-discovery-worker")
    try:
        service.get(discovery_id)
    except Exception:
        return {"advanced": False, "reason": "the requested Run-once discovery is unavailable"}
    latest = None
    for _ in range(12):
        result = worker.run_next()
        if result is None:
            break
        latest = result
        if result.discovery_id == discovery_id:
            return {
                "advanced": True,
                "discoveryId": result.discovery_id,
                "status": result.status.value,
                "primarySourceCount": len(result.sources),
            }
    current = service.get(discovery_id)
    if latest is None:
        return {
            "advanced": False,
            "reason": "the requested Run-once discovery was not claimable",
            "discoveryId": discovery_id,
            "status": current.status.value,
        }
    # A freshly written source may legitimately still be inside the configured
    # stability interval, so the honest durable outcome is reported rather than
    # forced to a fabricated "completed".
    return {
        "advanced": False,
        "reason": "the Worker advanced earlier queued discoveries before the requested one",
        "discoveryId": discovery_id,
        "status": current.status.value,
        "primarySourceCount": len(current.sources),
        "lastAdvancedDiscoveryId": latest.discovery_id,
    }


def run_preview_analysis_worker(state: AppState, *, analysis_id: str) -> dict[str, object]:
    """Advance one admitted durable exact analysis with the real Worker.

    The API only *admits* the analysis; this route is the resident
    Processing-Worker boundary that runs the existing exact-Preview service and
    links the resulting Preview.  It is metadata-only and never mutates Storage.
    """

    from mediaflow.application.preview_analysis import PreviewAnalysisWorker

    service = getattr(state.api, "_preview_analyses", None)
    if service is None:
        return {"advanced": False, "reason": "preview analysis service is unavailable"}
    worker = PreviewAnalysisWorker(service, worker_id="harness-analysis-worker")
    try:
        service.get(analysis_id)
    except Exception:
        return {"advanced": False, "reason": "the requested Preview analysis is unavailable"}
    latest = None
    for _ in range(12):
        result = worker.run_next()
        if result is None:
            break
        latest = result
        if result.analysis_id == analysis_id:
            return {
                "advanced": True,
                "analysisId": result.analysis_id,
                "status": result.status.value,
                "previewId": result.preview_id,
            }
    current = service.get(analysis_id)
    if latest is None:
        return {
            "advanced": False,
            "reason": "the requested Preview analysis was not claimable",
            "analysisId": analysis_id,
            "status": current.status.value,
        }
    return {
        "advanced": False,
        "reason": "the Worker advanced earlier queued analyses before the requested one",
        "analysisId": analysis_id,
        "status": current.status.value,
        "previewId": current.preview_id,
        "lastAdvancedAnalysisId": latest.analysis_id,
    }


def preview_analysis_state(state: AppState, *, analysis_id: str) -> dict[str, object]:
    """Report one durable exact analysis for the browser proof (reads only)."""

    service = getattr(state.api, "_preview_analyses", None)
    if service is None or not analysis_id:
        return {"found": False}
    try:
        analysis = service.get(analysis_id)
    except Exception:
        return {"found": False}
    return {
        "found": True,
        "analysisId": analysis.analysis_id,
        "kind": analysis.kind.value,
        "status": analysis.status.value,
        "version": analysis.version,
        "previewId": analysis.preview_id,
        "definitionId": analysis.definition_id,
        "intentId": analysis.intent_id,
    }


def automation_run_once_state(state: AppState, *, discovery_id: str) -> dict[str, object]:
    """Report the durable Run-once manifest for the browser proof.

    Bounded reads only: the exact frozen source paths and the durable origin.
    No Storage, Provider or work is touched.
    """

    service = getattr(state.api, "_media_discovery", None)
    if service is None or not discovery_id:
        return {"found": False}
    try:
        discovery = service.get(discovery_id)
    except Exception:
        return {"found": False}
    origin = discovery.definition_origin
    return {
        "found": True,
        "discoveryId": discovery.discovery_id,
        "status": discovery.status.value,
        "primarySourceCount": len(discovery.sources),
        "sources": [item.get("path") for item in discovery.sources],
        "intentId": discovery.intent_id,
        "frozen": discovery.frozen_at is not None,
        "definitionId": origin.definition_id if origin is not None else None,
        "sourceScope": origin.source_scope if origin is not None else None,
        "effectivePrimaryLimit": (origin.effective_primary_limit if origin is not None else None),
    }


def automation_lifecycle_state(state: AppState) -> dict[str, object]:
    """Report the durable definition/authority state for the lifecycle proof.

    Bounded reads only: the Active definitions, the definition's live
    unattended-grant state and the linked occurrence count. No Storage,
    Provider or work is touched.
    """

    configuration_service = state.managed.configuration_service
    active = configuration_service.active()
    definitions = (
        [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "enabled": item.get("enabled"),
                "mode": item.get("mode"),
                "resourceLibraryId": item.get("resourceLibraryId"),
                "itemLimit": item.get("itemLimit"),
            }
            for item in active.document.get("automationTaskDefinitions", [])
        ]
        if active is not None
        else []
    )
    grants = getattr(state.api, "_unattended_grants", None)
    occurrences = getattr(state.api, "_automation_occurrences", None)
    grant_state = None
    if grants is not None:
        try:
            grant = grants.get_for_definition(AUTOMATION_LIFECYCLE_DEFINITION_ID)
        except Exception:
            grant = None
        if grant is not None:
            grant_state = {
                "status": grant.status.value,
                "grantId": grant.grant_id,
                "definitionId": grant.definition_id,
            }
    occurrence_total = 0
    if occurrences is not None:
        try:
            occurrence_total = len(occurrences.list(AUTOMATION_LIFECYCLE_DEFINITION_ID, limit=20))
        except Exception:
            occurrence_total = 0
    return {
        "activeRevisionId": active.revision_id if active is not None else None,
        "definitions": definitions,
        "grant": grant_state,
        "occurrenceTotal": occurrence_total,
    }


def seed_automation_definition_grant(state: AppState) -> dict[str, object]:
    """Persist one real active unattended grant for the removal proof.

    The grant admission journey requires a persisted exact Preview; this
    isolated harness writes the durable grant row directly through the runtime
    repository, exactly as the grant service would, so the browser can then
    prove that a real removal revokes live authority and keeps its audit.
    """

    from mediaflow.domain.automation import AutomationTaskDefinition
    from mediaflow.domain.unattended_execution import (
        UnattendedExecutionGrant,
        UnattendedExecutionGrantAudit,
        UnattendedExecutionGrantStatus,
    )

    active = state.managed.configuration_service.active()
    if active is None:
        return {"error": "no Active configuration"}
    stored = next(
        (
            item
            for item in active.document.get("automationTaskDefinitions", [])
            if item.get("id") == AUTOMATION_LIFECYCLE_DEFINITION_ID
        ),
        None,
    )
    if stored is None:
        return {"error": "definition not found"}
    domain = AutomationTaskDefinition.from_document(stored)
    now = datetime.now(UTC)
    grant = UnattendedExecutionGrant(
        "harness-grant-1",
        domain.definition_id,
        domain.resource_library_id,
        domain.source_scope,
        domain.run_mode,
        domain.item_limit,
        UnattendedExecutionGrantStatus.ACTIVE,
        "harness-admin",
        now,
        domain.definition_fingerprint,
        active.revision_id,
        active.digest,
        active.version,
    )
    state.repository.create_unattended_execution_grant(
        grant,
        UnattendedExecutionGrantAudit(
            "harness-grant-audit-1",
            grant.grant_id,
            "granted",
            now,
            "harness-admin",
            {"definitionId": domain.definition_id},
        ),
    )
    return {"grantId": grant.grant_id, "status": grant.status.value}


def open_automation_definition_draft(state: AppState) -> dict[str, object]:
    """Open one real successor Draft with an unpublished definition candidate.

    The corrupt-history browser proof needs a same-ID Draft candidate that was
    never published, created through the real managed Draft authority (not a
    database edit). It returns the Draft revision identity so the caller can
    assert the candidate stayed stored yet was never presented as the removed
    definition's published history.
    """

    configuration_service = state.managed.configuration_service
    active = configuration_service.active()
    if active is None:
        return {"error": "no Active configuration"}
    try:
        draft = configuration_service.create_successor_draft(
            actor="harness",
            expected_active_revision_id=active.revision_id,
            expected_active_version=active.revision_sequence or active.version,
            expected_active_digest=active.digest,
            verified_active=active,
        )
        document = copy.deepcopy(draft.document)
        definitions = document.get("automationTaskDefinitions")
        if not isinstance(definitions, list):
            return {"error": "Active carries no Automation definition section"}
        candidate = next(
            (
                item
                for item in definitions
                if isinstance(item, dict) and item.get("id") == AUTOMATION_LIFECYCLE_DEFINITION_ID
            ),
            None,
        )
        if candidate is None:
            return {"error": "the lifecycle definition is not present in the Active"}
        candidate["name"] = AUTOMATION_LIFECYCLE_DRAFT_NAME
        edited = configuration_service.edit_draft(
            draft.revision_id,
            document,
            expected_version=draft.version,
            actor="harness",
        )
    except Exception as error:
        return {"error": f"draft open failed: {type(error).__name__}"}
    return {
        "draftRevisionId": edited.revision_id,
        "draftName": AUTOMATION_LIFECYCLE_DRAFT_NAME,
    }


def restore_source_media(state: AppState) -> dict[str, object]:
    """Recreate the deterministic source media the browser journeys organize.

    A real Move execution genuinely relocates the source file, so a later
    sequential test would find an empty scope.  This restores the exact original
    synthetic bytes under the same ResourceLibrary-relative paths so every test
    starts from the same known population.  It is a test-fixture control only:
    it writes the temporary harness source root, never a product code path.
    """

    source_root = state.managed.root / "source"
    scoped_fixtures = (
        source_root / "电影" / "One.2001.mkv",
        source_root / "电影" / "Two.2002.mkv",
    )
    for scoped_fixture in scoped_fixtures:
        scoped_fixture.unlink(missing_ok=True)
    try:
        scoped_fixtures[0].parent.rmdir()
    except OSError:
        pass
    # The Run-once restart journey executes these same deterministic fixtures
    # through OrganizerExecutor. Restore their source files before the next
    # browser test and clear only their known outputs from this temporary
    # harness destination, so an earlier successful Move cannot turn a later
    # preview into an unrelated destination conflict.
    destination_root = state.managed.root / "destination"
    fixture_outputs = (
        ("One", 2001, "101"),
        ("Two", 2002, "102"),
        ("Three", 2003, "103"),
        ("Four", 2004, "104"),
    )
    for title, year, provider_id in fixture_outputs:
        directory_name = f"{title} ({year}) [tmdbid-{provider_id}]"
        filename = f"{title} ({year}).mkv"
        output = destination_root / "Movies" / "Movies" / "Anime" / directory_name / filename
        output.unlink(missing_ok=True)
        parent = output.parent
        while parent != destination_root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    files = {
        "One.2001.mkv": b"synthetic browser media",
        "Two.2002.mkv": b"second synthetic browser media",
        "Three.2003.mkv": b"new-task synthetic browser media",
        "Four.2004.mkv": b"default-origin synthetic browser media",
    }
    for relative_path, content in files.items():
        target = source_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    scan = StorageScanner(
        state.managed.runtime.create_storages(),
        state.file_index,
        clock=lambda: datetime.now(UTC) + timedelta(hours=2),
    ).scan(state.managed.runtime.resource_libraries[0])
    if scan.status.value != "completed":
        raise RuntimeError("restored harness media could not be reindexed")
    return {"restored": sorted(files), "indexStatus": scan.status.value}


def seed_scheduled_worker_scope(state: AppState) -> dict[str, object]:
    """Create and index one recognized source under an exact scoped definition."""

    relative_path = "电影/One.2001.mkv"
    target = state.managed.root / "source" / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"scheduled Worker exact Preview fixture")
    scan = StorageScanner(
        state.managed.runtime.create_storages(),
        state.file_index,
        clock=lambda: datetime.now(UTC) + timedelta(hours=2),
    ).scan(state.managed.runtime.resource_libraries[0])
    if scan.status.value != "completed":
        raise RuntimeError("scheduled Worker fixture could not be indexed")
    return {
        "sourcePath": relative_path,
        "scanStatus": scan.status.value,
        "indexed": state.file_index.find_by_path("source-storage", "source", relative_path)
        is not None,
    }


def seed_run_once_mixed_scope(state: AppState) -> dict[str, object]:
    """Create and index two recognized sources for the native mixed-recovery run."""

    files = {
        "电影/One.2001.mkv": b"synthetic browser media",
        "电影/Two.2002.mkv": b"second synthetic browser media",
    }
    for relative_path, content in files.items():
        target = state.managed.root / "source" / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    scan = StorageScanner(
        state.managed.runtime.create_storages(),
        state.file_index,
        clock=lambda: datetime.now(UTC) + timedelta(hours=2),
    ).scan(state.managed.runtime.resource_libraries[0])
    if scan.status.value != "completed":
        raise RuntimeError("mixed Run-once fixture could not be indexed")
    return {"sourcePaths": sorted(files), "scanStatus": scan.status.value}


def reset_automation_definitions(state: AppState) -> dict[str, object]:
    """Publish an empty Automation section through the real managed authority.

    The isolated browser journey runs several sequential tests against one
    temporary configuration store. Each test must start from a known definition
    population, so this control route performs a real focused successor
    publication that removes every definition and revokes their unattended
    authority — the same production boundary the browser exercises, not a
    database edit. The removed definitions' Scheduler due-state rows are
    cleared through the runtime repository, so a later journey recreating the
    same definition ID starts with a fresh due state exactly as a genuinely
    new definition would.
    """

    configuration_service = state.managed.configuration_service
    active = configuration_service.active()
    if active is None:
        return {"error": "no Active configuration"}
    grants = getattr(state.api, "_unattended_grants", None)
    definition_ids = [
        str(item.get("id"))
        for item in active.document.get("automationTaskDefinitions", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    if grants is not None:
        for definition_id in definition_ids:
            try:
                if grants.get_for_definition(definition_id) is not None:
                    grants.revoke(
                        definition_id=definition_id,
                        actor="harness-admin",
                        reason="harness reset",
                    )
            except Exception:
                pass
    draft = configuration_service.create_successor_draft(
        actor="harness",
        expected_active_revision_id=active.revision_id,
        expected_active_version=active.revision_sequence or active.version,
        expected_active_digest=active.digest,
        verified_active=active,
    )
    document = copy.deepcopy(draft.document)
    document["automationTaskDefinitions"] = []
    edited = configuration_service.edit_draft(
        draft.revision_id,
        document,
        expected_version=draft.version,
        actor="harness",
        audit_context={
            "kind": "schedule",
            "objectId": "",
            "action": "harness_reset",
            "before": None,
            "after": None,
        },
    )
    validated = configuration_service.validate(edited.revision_id, actor="harness")
    if validated.status.value != "validated":
        return {"error": "reset validation failed", "errors": list(validated.validation_errors)}
    activated = configuration_service.activate(
        validated.revision_id,
        expected_version=validated.version,
        actor="harness",
    )
    state.repository.clear_automation_definition_schedule_states(tuple(definition_ids))
    return {
        "removed": definition_ids,
        "activeRevisionId": activated.revision_id,
    }


def crowd_automation_command_trail(state: AppState, *, edits: int) -> dict[str, object]:
    """Publish ordinary focused Automation edits to crowd the command trail.

    The Copy-reconciliation proof must cross the production paging boundary the
    real browser journey cannot reach economically by clicking: after a real
    Copy commits, this control publishes ordinary focused successor revisions
    (the same ``AutomationWorkspaceCommandService`` commands the browser issues,
    not database writes) so the committed Copy's command row is only reachable
    by a reader that pages the durable ledger with a real cursor. The edit
    target is deliberately a definition other than the copy's source, matching
    the shape B reproduced.
    """

    workspace = getattr(state.api, "_automation_workspace", None)
    configuration_service = state.managed.configuration_service
    active = configuration_service.active()
    if workspace is None or active is None:
        return {"error": "no Active Automation workspace"}
    definition_ids = [
        str(item.get("id"))
        for item in active.document.get("automationTaskDefinitions", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    if not definition_ids:
        return {"error": "no definition to crowd the trail with"}
    target = definition_ids[-1]
    published = 0
    for index in range(max(0, int(edits))):
        try:
            current = configuration_service.active()
            if current is None:
                break
            workspace.save_object(
                {"id": target, "name": f"Harness crowd {index}"},
                actor="harness",
                object_id=target,
                expected_revision_id=current.revision_id,
                expected_version=current.revision_sequence or current.version,
                expected_digest=current.digest,
            )
        except Exception as error:
            return {
                "error": f"crowd publication failed: {type(error).__name__}",
                "published": published,
            }
        published += 1
    return {"published": published, "target": target}


def run_automation_scheduler_tick(state: AppState) -> dict[str, object]:
    """Invoke the real managed-definition Scheduler once against the Active.

    The retained-history proof needs a real due occurrence emitted by the
    production Scheduler — not a database edit — so this control constructs
    the exact resident Scheduler assembly (one repository, the managed
    snapshot resolver, the Active definitions) and calls ``tick`` once. The
    emitted occurrence, Job and due-state advance are the same durable rows
    the resident service writes.
    """

    from mediaflow.application.automation import IntervalScheduler
    from mediaflow.domain.automation import SchedulerConfigurationSnapshot

    configuration_service = state.managed.configuration_service
    active = configuration_service.active()
    if active is None:
        return {"error": "no Active configuration"}
    try:
        runtime = with_managed_snapshot(
            load_managed_runtime_configuration(
                active.document,
                bootstrap_database_path=str(state.database),
            ),
            snapshot_id=active.revision_id,
            digest=active.digest,
            version=active.version,
        )
    except Exception as error:
        return {"error": f"runtime configuration did not load: {type(error).__name__}"}
    scheduler = IntervalScheduler(
        state.repository,
        (),
        configuration_snapshot_resolver=lambda: SchedulerConfigurationSnapshot(
            active.revision_id,
            active.digest,
            (),
            runtime.automation_maximum_active_jobs,
            tuple(runtime.automation_task_definitions),
            active.version,
            tuple(item.library_id for item in runtime.resource_libraries),
            tuple(item.library_id for item in runtime.resource_libraries if item.enabled),
        ),
    )
    emitted = scheduler.tick()
    occurrences = state.repository.list_automation_definition_occurrences(
        AUTOMATION_LIFECYCLE_DEFINITION_ID, limit=20
    )
    return {
        "emitted": [job.definition_id for job in emitted],
        "occurrenceTotal": len(occurrences),
    }


def run_automation_definition_worker_once(state: AppState) -> dict[str, object]:
    """Run one emitted definition occurrence through the production Worker."""

    from mediaflow.final_cli import _run_queued_workflow

    occurrence = state.repository.get_latest_automation_definition_occurrence(
        AUTOMATION_LIFECYCLE_DEFINITION_ID
    )
    if occurrence is None:
        return {"ran": False, "reason": "no emitted definition occurrence"}
    if state.managed.config_path is None:
        return {"ran": False, "reason": "the resident Worker has no managed config path"}
    active = state.managed.configuration_service.active()
    if active is None:
        return {"ran": False, "reason": "no Active configuration"}

    worker = AutomationWorker(
        state.repository,
        lambda job, cancelled: _run_queued_workflow(
            job,
            str(state.managed.config_path),
            cancelled,
            repository=state.repository,
        ),
        worker_id="harness-automation-definition-worker",
        label="harness-automation-definition-worker",
        supported_commands=("organize",),
        configuration_snapshot_id=active.revision_id,
        configuration_snapshot_digest=active.digest,
        runtime_schema_version=SCHEMA_VERSION,
    )
    with patch(
        "mediaflow.final_cli.metadata_provider_registry_from_environment",
        lambda _provider_ids: state.managed.metadata_registry,
    ):
        completed = worker.run_next()
    if completed is None:
        return {"ran": False, "reason": "no claimable scheduled definition Job"}
    if completed.job_id != occurrence.job_id:
        return {
            "ran": False,
            "reason": "the Worker claimed a different queued Job",
            "jobId": completed.job_id,
        }
    persisted_occurrence = state.repository.get_latest_automation_definition_occurrence(
        AUTOMATION_LIFECYCLE_DEFINITION_ID
    )
    return {
        "ran": True,
        "jobId": completed.job_id,
        "jobStatus": completed.status.value,
        "taskId": completed.task_id,
        "occurrenceId": occurrence.occurrence_id,
        "occurrenceTaskId": (
            persisted_occurrence.task_id if persisted_occurrence is not None else None
        ),
    }


def corrupt_automation_published_history(state: AppState) -> dict[str, object]:
    """Corrupt the retained published revisions that carry the definition.

    The real browser journey must prove the actionable unavailable state for
    structurally corrupt published evidence — the shape B reproduced — without
    the browser editing SQLite. This control corrupts the
    ``automationTaskDefinitions`` section of every superseded published revision
    that carries the definition, keeping each revision ID, its stored digest and
    its positive activation audit exactly as durable authority recorded them.
    Every retained candidate is corrupted deliberately: a still-intact revision
    would otherwise resolve the history legitimately (for example through a
    retained occurrence pin), which is correct product behavior but not the
    corrupt-evidence scenario under test. It is harness infrastructure, not a
    product endpoint, and it never touches production configuration.
    """

    import sqlite3

    repository = state.managed.configuration_repository
    targets = []
    for revision in repository.list_revisions(limit=500):
        if revision.status.value != "superseded":
            continue
        definitions = revision.document.get("automationTaskDefinitions")
        if isinstance(definitions, list) and any(
            isinstance(item, dict) and item.get("id") == AUTOMATION_LIFECYCLE_DEFINITION_ID
            for item in definitions
        ):
            targets.append(revision)
    if not targets:
        return {"error": "no superseded published revision carries the definition"}
    connection = sqlite3.connect(str(state.database))
    try:
        for target in targets:
            payload = copy.deepcopy(target.document)
            payload["automationTaskDefinitions"] = "corrupt section"
            connection.execute(
                "UPDATE managed_configuration_revisions SET payload=? WHERE revision_id=?",
                (json.dumps(payload), target.revision_id),
            )
        connection.commit()
    finally:
        connection.close()
    return {
        "corruptedRevisionIds": [target.revision_id for target in targets],
        "definitionId": AUTOMATION_LIFECYCLE_DEFINITION_ID,
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


def seed_task_center_problem_journey(state: AppState) -> dict[str, object]:
    """Create the mixed cross-Task problem population for the nine views.

    Every problem is written through the production service its real producer
    uses (``RecognitionReviewService``, ``ClassificationReviewService``, the
    conflict confirmation write path), and every unresolved failure item is a
    real ``task_items`` row.  No fixture flag fakes a current problem, so the
    nine views, their counts and their per-type file lists can only be derived
    from durable evidence.  One Task deliberately carries several problem
    types at once so the overlapping-list semantics are provable.

    Nothing here mutates Storage or calls a Provider; the temporary root and
    the synthetic MetadataProvider are the same isolated fixture the other
    journeys use.
    """

    if state.task_center_problems is not None:
        return dict(state.task_center_problems)
    managed = state.managed
    coordinator = PersistentTaskCoordinator(state.repository, state.repository)
    now = datetime.now(UTC)
    snapshot = managed.active

    def begin(task_id: str, item_id: str, filename: str) -> PersistentTaskItem:
        item = PersistentTaskItem(
            item_id=item_id,
            task_id=task_id,
            storage_id="source-storage",
            resource_library_id="source",
            source_path=filename,
            source_display=filename,
            status=TaskItemStatus.PROCESSING,
            stage="recognizing",
            attempts=1,
            created_at=now,
            updated_at=now,
        )
        state.repository.upsert_item(item)
        return item

    # Task 1: two recognition files and one unresolved technical failure.  The
    # task therefore belongs to both the recognition and failure lists.
    mixed = coordinator.create(
        "organize",
        execute_authorized=False,
        scope_path="TaskCenter/Mixed",
        configuration_snapshot_id=snapshot.revision_id,
        configuration_snapshot_digest=snapshot.digest,
        require_configuration_snapshot=True,
    )
    recognition_types = (RecognitionType("A", "Movie"), RecognitionType("B", "TV"))
    recognition_service = RecognitionReviewService(state.repository, recognition_types)
    for index in range(2):
        item_id = f"{mixed.task_id}-recog-{index}"
        recognition_service.create(
            begin(mixed.task_id, item_id, f"TaskCenter/Mixed/Recog{index}.mkv"),
            RecognitionResult(status=RecognitionStatus.UNRECOGNIZED),
        )
    failure_item_id = f"{mixed.task_id}-failure"
    failure_item = begin(
        mixed.task_id,
        failure_item_id,
        "TaskCenter/Mixed/Broken.mkv",
    )
    state.repository.upsert_item(
        dataclasses.replace(
            failure_item,
            status=TaskItemStatus.FAILED,
            stage="failed",
            error=FailureExplanation(
                category="storage_permission_denied",
                message="the destination Storage rejected the write",
                durable_state="no_media_moved",
                side_effects="none",
                retry_safe=True,
                next_action="repair the destination Storage permission, then re-check this item",
            ).encode(),
        )
    )

    # One successful sibling with a durable Result and one unknown-effect
    # failure keep terminal success and uncertain mutation evidence visible
    # beside the zero-effect technical failure. The unknown checkpoint is
    # deliberately inspect-only.
    success_item_id = f"{mixed.task_id}-success"
    success_path = "TaskCenter/Mixed/Completed.mkv"
    success_item = dataclasses.replace(
        begin(mixed.task_id, success_item_id, success_path),
        status=TaskItemStatus.SUCCESS,
        stage="completed",
        plan_id=f"{mixed.task_id}-success-plan",
        destination_storage_id="target-storage",
        destination_path="Movies/Completed/Completed.mkv",
        execution_status="SUCCESS",
    )
    state.repository.upsert_item(success_item)
    state.repository.append_result(
        PersistentResultRecord(
            result_id=f"{mixed.task_id}-success-result",
            task_id=mixed.task_id,
            item_id=success_item_id,
            source_storage_id="source-storage",
            source_path=success_path,
            destination_storage_id="target-storage",
            destination_path="Movies/Completed/Completed.mkv",
            recognition_type="A",
            provider="tmdb",
            provider_id="451",
            metadata_policy_id="A",
            naming_policy_id="A",
            classification_policy_id="A",
            organize_policy_id="A",
            operation="MOVE",
            status="SUCCESS",
            created_at=now,
            title="Completed sibling",
            completed_operations=("MOVE", "ATTACHMENT_MOVE"),
            attachment_count=1,
            effect_certainty="verified_complete",
        )
    )

    unknown_item_id = f"{mixed.task_id}-unknown-effect"
    unknown_path = "TaskCenter/Mixed/UnknownEffect.mkv"
    unknown_failure = FailureExplanation(
        category="execution_outcome_unknown",
        message="the destination effect could not be verified",
        durable_state="inspection_required",
        side_effects="unknown",
        retry_safe=False,
        next_action="inspect the recorded effect evidence before deciding what to do next",
    )
    unknown_item = dataclasses.replace(
        begin(mixed.task_id, unknown_item_id, unknown_path),
        status=TaskItemStatus.FAILED,
        stage="execution_outcome_unknown",
        plan_id=f"{mixed.task_id}-unknown-plan",
        execution_status="FAILED",
        error=unknown_failure.encode(),
    )
    state.repository.upsert_item(unknown_item)
    state.repository.append_result(
        PersistentResultRecord(
            result_id=f"{mixed.task_id}-unknown-result",
            task_id=mixed.task_id,
            item_id=unknown_item_id,
            source_storage_id="source-storage",
            source_path=unknown_path,
            destination_storage_id="target-storage",
            destination_path="Movies/UnknownEffect/UnknownEffect.mkv",
            recognition_type="A",
            provider="tmdb",
            provider_id="452",
            metadata_policy_id="A",
            naming_policy_id="A",
            classification_policy_id="A",
            organize_policy_id="A",
            operation="MOVE",
            status="FAILED",
            created_at=now,
            title="Unknown effect sibling",
            completed_operations=("MOVE",),
            effect_certainty="unknown",
            uncertain_effects=("mutation_outcome",),
            error=unknown_failure.encode(),
        )
    )

    # The same primary file has both a primary destination conflict and an
    # attached subtitle conflict. Both durable confirmations point back to
    # one TaskItem, so recovery counts one affected primary file rather than
    # two attachment steps.
    conflict_item_id = f"{mixed.task_id}-conflict"
    conflict_source = "TaskCenter/Mixed/ConflictMovie.mkv"
    conflict_item = dataclasses.replace(
        begin(mixed.task_id, conflict_item_id, conflict_source),
        status=TaskItemStatus.WAITING_CONFIRM,
        stage="waiting_confirm",
        plan_id=f"{mixed.task_id}-conflict-plan",
    )
    confirmation_service = ConfirmationService(state.repository)
    conflict_policy = OrganizePolicy(
        f"{mixed.task_id}-conflict-policy",
        OrganizeOperationType.MOVE,
        ConflictStrategy.MANUAL,
        attachments=AttachmentPolicy(enabled=True),
    )

    def create_pending_conflict(
        source_path: str,
        target_path: str,
        plan_id: str,
        *,
        publish_item: bool = True,
    ) -> None:
        plan = OrganizePlan(
            source_storage_id="source-storage",
            target_storage_id="target-storage",
            source=source_path,
            target=target_path,
            recognition_type_id="A",
            naming_policy_id="A",
            classification_policy_id="A",
            organize_policy_id=conflict_policy.policy_id,
            conflicts=(
                Conflict(
                    ConflictType.DESTINATION_EXISTS,
                    source_path,
                    target_path,
                    "destination already exists",
                ),
            ),
            status=PlanStatus.CONFLICT,
            plan_id=plan_id,
            source_location=StorageLocation("source-storage", source_path),
            destination_location=StorageLocation("target-storage", target_path),
        )
        confirmation_service.create(
            task_id=mixed.task_id,
            item_id=conflict_item_id,
            plan=plan,
            policy=conflict_policy,
            item=conflict_item if publish_item else None,
        )

    create_pending_conflict(
        conflict_source,
        "Movies/ConflictMovie.mkv",
        f"{mixed.task_id}-primary-conflict-plan",
    )
    create_pending_conflict(
        "TaskCenter/Mixed/ConflictMovie.en.srt",
        "Movies/ConflictMovie.en.srt",
        f"{mixed.task_id}-attachment-conflict-plan",
        publish_item=False,
    )

    state.repository.update_task(
        dataclasses.replace(
            mixed,
            status=PersistentTaskStatus.PARTIAL_SUCCESS,
            updated_at=now,
            completed_at=now,
            total_items=6,
            completed_items=1,
            failed_items=2,
        )
    )

    # Task 2: one classification file, proving the classification list.
    classified = coordinator.create(
        "organize",
        execute_authorized=False,
        scope_path="TaskCenter/Classified",
    )
    classification_policy = ClassificationPolicy(
        "classification-a",
        "Classification A",
        rules=(
            ClassificationRule(
                "rule-1",
                "Rule 1",
                "media-target",
                "Movies",
                priority=10,
            ),
        ),
    )
    ClassificationReviewService(state.repository).create(
        begin(
            classified.task_id,
            f"{classified.task_id}-class",
            "TaskCenter/Classified/Unclassified.mkv",
        ),
        ClassificationResult(
            policy_id=classification_policy.policy_id,
            recognition_type_id="A",
            status=ClassificationStatus.UNCLASSIFIED,
        ),
        classification_policy,
        MediaIdentity(
            "tmdb",
            "101",
            MediaType.MOVIE,
            "Unclassified",
            year=2001,
        ),
    )

    # Task 3: one pending Metadata correction candidate.
    metadata = coordinator.create(
        "organize",
        execute_authorized=False,
        scope_path="TaskCenter/Metadata",
    )
    from mediaflow.application.metadata_correction import MetadataCorrectionService
    from mediaflow.domain.parser import ParseResult

    metadata_policy = next(
        value
        for value in managed.runtime.strategy.metadata_policies
        if value.policy_id == "C" and value.enabled
    )
    MetadataCorrectionService(state.repository, (metadata_policy,)).create(
        begin(
            metadata.task_id,
            f"{metadata.task_id}-metadata",
            "TaskCenter/Metadata/Unknown.mkv",
        ),
        MetadataIdentificationResult(
            status=MetadataIdentificationStatus.NOT_FOUND,
            recognition_type=RecognitionType("C", "Special"),
            query="Unknown",
        ),
        metadata_policy,
        ParseResult(
            title_candidate="Unknown",
            year=1999,
            original_filename="Unknown.mkv",
        ),
    )

    # A Job that failed before any Task existed, carrying durable structured
    # repair evidence and no linked Task. It is the run-level attention case
    # with no file members: the 需要处理 view must locate it and its action must
    # reach the existing Job detail, not a fabricated file list.
    run_repair_now = datetime.now(UTC)
    run_repair_job = AutomationJob(
        "harness-run-repair",
        AutomationCommand.PREVIEW,
        AutomationJobStatus.FAILED,
        run_repair_now,
        run_repair_now,
        completed_at=run_repair_now,
        failure_category="snapshot_digest_mismatch",
        failure_durable_state="the saved published revision digest no longer matches",
        failure_side_effects="none",
        failure_retry_safe=False,
        failure_next_action=(
            "restore the exact saved published revision, then emit a new occurrence"
        ),
    )
    state.repository.create_job(run_repair_job)

    state.task_center_problems = {
        "mixedTaskId": mixed.task_id,
        "mixedRecognitionItemIds": [
            f"{mixed.task_id}-recog-0",
            f"{mixed.task_id}-recog-1",
        ],
        "mixedFailureItemId": failure_item_id,
        "mixedSuccessItemId": success_item_id,
        "mixedUnknownItemId": unknown_item_id,
        "mixedConflictItemId": conflict_item_id,
        "classificationTaskId": classified.task_id,
        "classificationItemId": f"{classified.task_id}-class",
        "metadataTaskId": metadata.task_id,
        "metadataItemId": f"{metadata.task_id}-metadata",
        "runRepairJobId": run_repair_job.job_id,
    }
    return dict(state.task_center_problems)


def seed_task_center_problem_page(state: AppState) -> dict[str, object]:
    """Create 21 real zero-effect failures for the server-paged file journey."""

    if state.task_center_problem_page is not None:
        return dict(state.task_center_problem_page)
    now = datetime.now(UTC)
    snapshot = state.managed.active
    coordinator = PersistentTaskCoordinator(state.repository, state.repository)
    task = coordinator.create(
        "organize",
        execute_authorized=False,
        scope_path="TaskCenter/PagedFailures",
        configuration_snapshot_id=snapshot.revision_id,
        configuration_snapshot_digest=snapshot.digest,
        require_configuration_snapshot=True,
        status=PersistentTaskStatus.FAILED,
    )
    explanation = FailureExplanation(
        category="analysis_interrupted",
        message="the analysis worker stopped before a Storage mutation",
        durable_state="failure is recorded",
        side_effects="none",
        retry_safe=True,
        next_action="repair the analysis dependency, then explicitly re-check this item",
    ).encode()
    item_ids: list[str] = []
    for index in range(21):
        item_id = f"{task.task_id}-failure-{index:02d}"
        source_path = f"TaskCenter/PagedFailures/Failure{index:02d}.mkv"
        item_ids.append(item_id)
        state.repository.upsert_item(
            PersistentTaskItem(
                item_id=item_id,
                task_id=task.task_id,
                storage_id="source-storage",
                resource_library_id="source",
                source_path=source_path,
                source_display=source_path,
                status=TaskItemStatus.FAILED,
                stage="failed",
                attempts=1,
                created_at=now + timedelta(microseconds=index),
                updated_at=now + timedelta(microseconds=index),
                error=explanation,
            )
        )
    state.repository.update_task(
        dataclasses.replace(
            task,
            updated_at=now,
            completed_at=now,
            total_items=len(item_ids),
            failed_items=len(item_ids),
        )
    )
    state.task_center_problem_page = {
        "taskId": task.task_id,
        "itemCount": len(item_ids),
        "firstItemId": item_ids[0],
        "lastItemId": item_ids[-1],
    }
    return dict(state.task_center_problem_page)


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


def retirement_stability_state(state: AppState, *, change: bool = False):
    root = state.managed.root / "source" / "Retirement"
    source = root / "Thirteenth.2013.mkv"
    if change:
        source.write_bytes(source.read_bytes() + b"changed")
    records = state.repository.list_media_discoveries(limit=500)
    matching = [item for item in records if item.resource_library_id == "retirement"]
    observations = []
    for item in matching:
        observations.extend(
            value.document()
            for value in state.repository.list_media_discovery_observations(
                item.discovery_id, limit=100
            )
        )
    counts = {
        table: state.repository._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("tasks", "automation_jobs", "manual_execution_authorizations")
    }
    return {
        "counts": counts,
        "observations": observations,
        "sources": sorted(path.name for path in root.iterdir()),
        "targets": sorted(
            path.name
            for path in (state.managed.root / "destination").rglob("*")
            if path.is_file() and path.name.startswith(("Thirteenth", "Fourteenth"))
        ),
    }


def application(environ, start_response):
    path = str(environ.get("PATH_INFO", ""))
    if path.startswith("/__harness__/") and STATE is not None:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        if path == "/__harness__/retirement-state" and method == "GET":
            document = retirement_stability_state(STATE)
        elif path == "/__harness__/retirement-change" and method == "POST":
            document = retirement_stability_state(STATE, change=True)
        elif path == "/__harness__/run-worker" and method == "POST":
            document = run_worker_once(STATE)
        elif path == "/__harness__/run-manual-organize" and method == "POST":
            document = run_manual_organize_once(STATE)
        elif path == "/__harness__/register-manual-worker" and method == "POST":
            document = register_manual_worker(STATE)
        elif path == "/__harness__/run-manual-worker" and method == "POST":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            STATE.fail_next_manual_execution = (query.get("failBeforeMutation") or ["0"])[0] == "1"
            document = run_manual_worker_once(STATE)
        elif path == "/__harness__/run-discovery-worker" and method == "POST":
            document = run_discovery_worker_once(STATE)
        elif path == "/__harness__/seed-task-center-problems" and method == "POST":
            document = seed_task_center_problem_journey(STATE)
        elif path == "/__harness__/seed-task-center-problem-page" and method == "POST":
            document = seed_task_center_problem_page(STATE)
        elif path == "/__harness__/seed-task-item-recovery" and method == "POST":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            kind = (query.get("kind") or ["recognition"])[0]
            document = seed_task_item_recovery_journey(STATE, kind)
        elif path == "/__harness__/run-task-item-recovery-worker" and method == "POST":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            item_id = (query.get("itemId") or [None])[0]
            document = run_task_item_recovery_worker_once(STATE, item_id=item_id)
        elif path == "/__harness__/task-item-recovery-state" and method == "GET":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            item_id = (query.get("itemId") or [None])[0]
            document = task_item_recovery_state(STATE, item_id=item_id)
        elif path == "/__harness__/task-result-state" and method == "GET":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            task_id = (query.get("taskId") or [None])[0]
            document = task_result_state(STATE, task_id=task_id)
        elif path == "/__harness__/seed-task-item-recovery-batch" and method == "POST":
            document = seed_task_item_recovery_batch(STATE)
        elif path == "/__harness__/seed-batch-summary-recovery" and method == "POST":
            document = seed_batch_summary_recovery(STATE)
        elif path == "/__harness__/batch-summary-recovery-state" and method == "GET":
            document = batch_summary_recovery_state(STATE)
        elif path == "/__harness__/stale-task-item-batch-selection" and method == "POST":
            document = stale_task_item_batch_selection(STATE)
        elif path == "/__harness__/task-item-recovery-batch-state" and method == "GET":
            document = task_item_recovery_batch_state(STATE)
        elif path == "/__harness__/operations-origin-state" and method == "GET":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            task_id = (query.get("taskId") or [""])[0]
            document = operations_origin_state(STATE, task_id=task_id)
        elif path == "/__harness__/manual-file-state" and method == "GET":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            requested_file = (query.get("file") or ["Three.2003.mkv"])[0]
            document = manual_file_state(STATE, filename=requested_file)
        elif path == "/__harness__/run-standalone-pipeline" and method == "POST":
            document = run_standalone_pipeline_once(STATE)
        elif path == "/__harness__/seed-inventory-poll-population" and method == "POST":
            document = seed_inventory_poll_population(STATE)
        elif path == "/__harness__/append-inventory-poll-failure" and method == "POST":
            document = append_inventory_poll_failure(STATE)
        elif path == "/__harness__/seed-continuation" and method == "POST":
            document = seed_continuation_journey(STATE)
        elif path == "/__harness__/run-continuation-worker" and method == "POST":
            document = run_continuation_worker_once(STATE)
        elif path == "/__harness__/seed-authority-refusal" and method == "POST":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            missing_snapshot = (query.get("missingPin") or ["0"])[0] == "1"
            document = seed_authority_refusal(STATE, missing_snapshot=missing_snapshot)
        elif path == "/__harness__/authority-state" and method == "GET":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            task_id = (query.get("taskId") or [None])[0]
            document = authority_execution_state(STATE, source_task_id=task_id)
        elif path == "/__harness__/continuation-state" and method == "GET":
            document = continuation_journey_state(STATE)
        elif path == "/__harness__/automation-lifecycle-state" and method == "GET":
            document = automation_lifecycle_state(STATE)
        elif path == "/__harness__/run-automation-run-once-worker" and method == "POST":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            discovery_id = (query.get("discoveryId") or [""])[0]
            document = run_automation_run_once_worker(STATE, discovery_id=discovery_id)
        elif path == "/__harness__/automation-run-once-state" and method == "GET":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            discovery_id = (query.get("discoveryId") or [""])[0]
            document = automation_run_once_state(STATE, discovery_id=discovery_id)
        elif path == "/__harness__/run-preview-analysis-worker" and method == "POST":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            analysis_id = (query.get("analysisId") or [""])[0]
            document = run_preview_analysis_worker(STATE, analysis_id=analysis_id)
        elif path == "/__harness__/preview-analysis-state" and method == "GET":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            analysis_id = (query.get("analysisId") or [""])[0]
            document = preview_analysis_state(STATE, analysis_id=analysis_id)
        elif path == "/__harness__/seed-automation-definition-grant" and method == "POST":
            document = seed_automation_definition_grant(STATE)
        elif path == "/__harness__/reset-automation-definitions" and method == "POST":
            document = reset_automation_definitions(STATE)
        elif path == "/__harness__/restore-source-media" and method == "POST":
            document = restore_source_media(STATE)
        elif path == "/__harness__/seed-scheduled-worker-scope" and method == "POST":
            document = seed_scheduled_worker_scope(STATE)
        elif path == "/__harness__/seed-run-once-mixed-scope" and method == "POST":
            document = seed_run_once_mixed_scope(STATE)
        elif path == "/__harness__/open-automation-definition-draft" and method == "POST":
            document = open_automation_definition_draft(STATE)
        elif path == "/__harness__/run-automation-scheduler-tick" and method == "POST":
            document = run_automation_scheduler_tick(STATE)
        elif path == "/__harness__/run-automation-definition-worker" and method == "POST":
            document = run_automation_definition_worker_once(STATE)
        elif path == "/__harness__/corrupt-automation-published-history" and method == "POST":
            document = corrupt_automation_published_history(STATE)
        elif path == "/__harness__/crowd-automation-command-trail" and method == "POST":
            query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))
            raw_edits = (query.get("edits") or ["0"])[0]
            try:
                requested_edits = max(0, min(1000, int(raw_edits)))
            except ValueError:
                requested_edits = 0
            document = crowd_automation_command_trail(STATE, edits=requested_edits)
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
