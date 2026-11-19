"""Bounded ResourceLibrary folder and mixed-selection discovery (Slice 44 RO-6).

The suite runs against the real runtime SQLite repository, real Local Storage
adapters and the real application services, with a controlled clock and
synthetic temporary media.  It covers the scope/budget/stability/persistence/
Worker/API families named by Task 44.6 without weakening any production
capability.
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
from unittest import mock

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.media_discovery import MediaDiscoveryService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.library import FileStabilityPolicy
from mediaflow.domain.media_discovery import (
    DiscoveryBudgets,
)
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import (
    StorageError,
    StorageErrorCode,
)
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.task_engine_test_helpers import (
    ManualOrganizeExecutionWorker,
    claim_and_run,
)

SNAPSHOT_ID = "active-1"
SNAPSHOT_DIGEST = "a" * 64
OPERATOR_TOKEN = "operator-token"
#: A second published operator sharing the same ResourceLibrary.  The tokens are
#: environment-owned exactly like production, so a two-principal journey resolves
#: them through the real configuration loader.
SECOND_OPERATOR_TOKEN = "second-operator-token"
SECOND_OPERATOR_FIRST_ENV = "MEDIAFLOW_TEST_FIRST_OPERATOR_TOKEN"
SECOND_OPERATOR_SECOND_ENV = "MEDIAFLOW_TEST_SECOND_OPERATOR_TOKEN"


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


class _RecordingStorage:
    """Delegate Storage that records every call and performs real effects.

    Reads and effects are delegated to the wrapped real provider, so a confirmed
    execution journey exercises the production effect path; the recorded call
    list is what proves a zero-mutation stage performed no mutation.
    """

    def __init__(self, storage) -> None:
        self._storage = storage
        self.reads: list[tuple[str, str]] = []
        self.mutations: list[tuple[str, str]] = []
        self._unreadable: set[str] = set()

    def fail_listing(self, prefix: str) -> None:
        """Make one subtree unreadable after admission."""

        self._unreadable.add(prefix.strip("/"))

    def __getattr__(self, name):
        return getattr(self._storage, name)

    @property
    def storage_id(self) -> str:
        return self._storage.storage_id

    def list(self, path: str):
        self.reads.append(("list", path))
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
        self.mutations.append(("read", path))
        return self._storage.read(path)

    def write(self, path: str, data, *, overwrite: bool = False) -> None:
        self.mutations.append(("write", path))
        self._storage.write(path, data, overwrite=overwrite)

    def create_directory(self, path: str) -> None:
        self.mutations.append(("create_directory", path))
        self._storage.create_directory(path)

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutations.append(("move", source))
        self._storage.move(source, target, overwrite=overwrite)

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutations.append(("copy", source))
        self._storage.copy(source, target, overwrite=overwrite)

    def delete(self, path: str) -> None:
        self.mutations.append(("delete", path))
        self._storage.delete(path)

    def hard_link(self, source: str, target: str) -> None:
        self.mutations.append(("hard_link", source))
        self._storage.hard_link(source, target)

    def soft_link(self, source: str, target: str) -> None:
        self.mutations.append(("soft_link", source))
        self._storage.soft_link(source, target)


class _DiscoveryFixture(unittest.TestCase):
    """A real managed runtime: pinned Active revision, real Local Storage, real SQLite."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.source_root = self.root / "source"
        self.source_root.mkdir()
        self.second_root = self.root / "second-root"
        self.second_root.mkdir()
        self.target_root = self.root / "target"
        self.target_root.mkdir()
        self.database = self.root / "runtime.sqlite3"
        self.clock = _Clock()

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def _require_long_path_fixture_support(self, relative: str) -> None:
        """Skip a real-filesystem long-path case only on a proved path limit.

        The temporary filesystem is probed with the exact fixture the test
        needs (the parent directories *and* a regular file).  A genuine
        ``ENAMETOOLONG`` produces a precise reported skip; every other error
        (permission, I/O, application) is re-raised so it still fails.
        """

        probe = self.source_root / relative
        try:
            probe.parent.mkdir(parents=True, exist_ok=True)
            probe.write_bytes(b"probe")
        except OSError as error:
            if error.errno == errno.ENAMETOOLONG:
                self.skipTest(
                    f"temporary filesystem cannot create a >1024-byte path fixture "
                    f"(errno {error.errno}: {error.strerror}); in-memory coverage runs instead"
                )
            raise

    def media(
        self,
        relative: str,
        *,
        size: int = 512,
        modified_at: datetime | None = None,
        second: bool = False,
    ):
        path = (self.second_root if second else self.source_root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"m" * size)
        if modified_at is not None:
            stamp = modified_at.timestamp()
            os.utime(path, (stamp, stamp))
        return path

    def publish_policy(self, value, *, document: dict) -> None:
        """Load one real published policy revision into a running journey.

        The revision goes through the production managed authority and loader,
        exactly like the Web/API Save surface, so every policy assertion below
        reads a genuinely published and loaded configuration rather than an
        injected object.
        """

        from mediaflow.infrastructure.runtime_configuration import (
            load_managed_runtime_configuration,
            with_managed_snapshot,
        )

        revision = _activate(
            ManagedConfigurationService(
                SQLiteConfigurationRepository(self.database),
                bootstrap_database_path=str(self.database),
            ),
            document,
        )
        runtime = with_managed_snapshot(
            load_managed_runtime_configuration(
                revision.document, bootstrap_database_path=str(self.database)
            ),
            snapshot_id=revision.revision_id,
            digest=revision.digest,
        )
        value.configuration = runtime
        value.discovery._runtime_resolver = lambda sid, digest: runtime
        value.previews._runtime_resolver = lambda sid, digest: runtime
        value.intents._runtime_resolver = lambda sid, digest: runtime
        return revision, runtime

    def document(
        self,
        *,
        stability: FileStabilityPolicy | None = None,
        max_depth: int | None = None,
        extensions: tuple[str, ...] = ("mkv", "mp4"),
        exclude_rules: tuple[str, ...] = (),
        second_library: bool = False,
        attachments: bool = False,
        second_operator: bool = False,
    ) -> dict:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        if second_operator:
            # Two enabled operator principals share one published configuration.
            # Their tokens are environment-owned exactly like production, so the
            # journey resolves them through the real loader instead of injecting
            # synthetic permission sets.
            document["api"]["principals"] = [
                {
                    "id": "operator",
                    "tokenEnv": SECOND_OPERATOR_FIRST_ENV,
                    "roles": ["operator"],
                    "enabled": True,
                },
                {
                    "id": "second-operator",
                    "tokenEnv": SECOND_OPERATOR_SECOND_ENV,
                    "roles": ["operator"],
                    "enabled": True,
                },
            ]
            document["api"].pop("tokenEnv", None)
        document["persistence"]["databasePath"] = str(self.database)
        document["historyPath"] = str(self.root / "history.jsonl")
        document["storages"] = [
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
        library = {
            "id": "library",
            "name": "Library",
            "storageId": "source",
            "storagePath": "",
            "enabled": True,
            "extensions": list(extensions),
            "maxDepth": max_depth,
        }
        document["resourceLibraries"] = [library]
        if second_library:
            # A second enabled ResourceLibrary with a *different* Storage and
            # root but the same legal relative folder names — the exact
            # cross-library reconciliation hazard B's P1 describes.
            document["storages"].append(
                {
                    "id": "source2",
                    "name": "Source2",
                    "type": "local",
                    "rootPath": str(self.second_root),
                    "enabled": True,
                }
            )
            document["resourceLibraries"].append(
                {
                    "id": "library2",
                    "name": "Library2",
                    "storageId": "source2",
                    "storagePath": "",
                    "enabled": True,
                    "extensions": list(extensions),
                    "maxDepth": max_depth,
                }
            )
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
        if attachments:
            # The real managed attachment policy, published and production-
            # loaded exactly like the Web/API Save surface would. Movie test
            # paths are pinned to RecognitionType A so discovery must use the
            # same owner policy as the later manual Preview.
            for policy in document.get("organizePolicies", []):
                policy["attachments"]["enabled"] = True
            # RO-2/AC-16: the Files journey resolves each source's type through the
            # pinned RecognitionRule, and only that resolved type's policy can
            # associate a sidecar.  The fixture therefore publishes the ordinary
            # video rule (every configured video suffix) so an attachment journey
            # starts from a real decided type instead of an invented default.
            document["recognitionRules"].append(
                {
                    "id": "discovery-video-fixture",
                    "name": "Discovery video fixture",
                    "priority": 200,
                    "score": 100,
                    "stopOnMatch": True,
                    "condition": {
                        "field": "extension",
                        "operator": "in",
                        "value": ["mkv", "mp4", "wmv", "avi"],
                    },
                    "outputRecognitionType": "A",
                }
            )
        return document

    @contextmanager
    def journey(
        self,
        *,
        stability: FileStabilityPolicy | None = None,
        max_depth: int | None = None,
        extensions: tuple[str, ...] = ("mkv", "mp4"),
        exclude_rules: tuple[str, ...] = (),
        budgets: DiscoveryBudgets | None = None,
        second_library: bool = False,
        attachments: bool = False,
        metadata_query_type: str | None = None,
        max_provider_requests: int | None = None,
        source_storage=None,
        provider=None,
        second_operator: bool = False,
        task_scheduling: bool = False,
        worker_lease: float | None = None,
    ):

        document = self.document(
            stability=stability,
            max_depth=max_depth,
            extensions=extensions,
            second_library=second_library,
            attachments=attachments,
            second_operator=second_operator,
        )
        if metadata_query_type is not None:
            for policy in document.get("metadataPolicies", []):
                policy["mediaQueryType"] = metadata_query_type
        if max_provider_requests is not None:
            for policy in document.get("metadataPolicies", []):
                policy["maxProviderRequests"] = max_provider_requests
        source = _RecordingStorage(
            source_storage
            if source_storage is not None
            else LocalStorage("source", self.source_root)
        )
        target = _RecordingStorage(LocalStorage("target", self.target_root))
        storages = {"source": source, "target": target}
        if second_library:
            storages["source2"] = _RecordingStorage(LocalStorage("source2", self.second_root))
        with (
            SQLiteConfigurationRepository(self.database) as configuration_repository,
            SQLiteTaskRepository(self.database) as repository,
        ):
            managed = ManagedConfigurationService(
                configuration_repository,
                bootstrap_database_path=str(self.database),
            )
            revision = _activate(managed, document)
            runtime = _runtime_for(
                managed, revision, stability=stability, exclude_rules=exclude_rules
            )
            intents = ManualOrganizeIntentService(
                repository,
                managed,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storage_factory=lambda value, ids: dict(storages),
            )
            providers = MetadataProviderRegistry((provider,)) if provider is not None else None
            previews = ManualOrganizePreviewService(
                repository,
                intents,
                configuration=runtime,
                providers=providers,
                storages=dict(storages),
                clock=self.clock,
            )
            executions = ManualOrganizeExecutionService(
                repository,
                previews,
                intents,
                checkpoint_service=ProcessingCheckpointService(repository),
                storages=dict(storages),
                clock=self.clock,
            )
            execution_worker = ManualOrganizeExecutionWorker(
                executions, worker_id="execution-worker", notice=lambda line: None
            )
            discovery = MediaDiscoveryService(
                repository,
                intents,
                configuration=runtime,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                preview_service=previews,
                storages=dict(storages),
                clock=self.clock,
                budgets=budgets or DiscoveryBudgets(),
                **({"lease_seconds": worker_lease} if worker_lease is not None else {}),
            )
            task_engine = None
            if task_scheduling:
                from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
                from mediaflow.application.task_scheduling import TaskSchedulingService
                from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

                repository.register_worker(
                    "task-engine-worker",
                    "task engine",
                    5.0,
                    ("manual_organize",),
                    None,
                    None,
                    SCHEMA_VERSION,
                    self.clock(),
                )
                task_engine = ManualTaskEngineWorker(
                    repository,
                    TaskSchedulingService(
                        repository,
                        capacity=getattr(runtime, "automation_maximum_active_jobs", 100),
                        locks=repository,
                    ),
                    discovery,
                    executions,
                    clock=self.clock,
                    worker_id="task-engine-worker",
                    notice=lambda line: None,
                    **({"lease_seconds": worker_lease} if worker_lease is not None else {}),
                )
            if second_operator:
                with mock.patch.dict(
                    os.environ,
                    {
                        SECOND_OPERATOR_FIRST_ENV: OPERATOR_TOKEN,
                        SECOND_OPERATOR_SECOND_ENV: SECOND_OPERATOR_TOKEN,
                    },
                ):
                    principals = runtime.resolve_api_principals()
            else:
                principals = (
                    ResolvedApiPrincipal(
                        "operator",
                        OPERATOR_TOKEN,
                        frozenset(
                            {
                                ApiPermission.READ,
                                ApiPermission.MANAGE_MANUAL_ORGANIZE,
                                ApiPermission.EXECUTE_MANUAL_ORGANIZE,
                                # The production OPERATOR role also carries the
                                # Task Center control permission; the fixture
                                # mirrors it so the real pause/cancel route is
                                # exercised through its authenticated entry.
                                ApiPermission.CANCEL_JOB,
                                # RO-2/AC-15: the native four-type recovery this
                                # journey exercises is the operator's own decision
                                # surface, so the fixture principal carries exactly
                                # the documented operator permissions.
                                ApiPermission.RESOLVE_RECOGNITION_REVIEW,
                                ApiPermission.RESOLVE_METADATA_REVIEW,
                                ApiPermission.RESOLVE_CLASSIFICATION_REVIEW,
                                ApiPermission.RESOLVE_CONFIRMATION,
                            }
                        ),
                    ),
                )
            api = MediaFlowApi(
                repository,
                principals=(
                    *principals,
                    ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
                ),
                configuration_service=managed,
                bootstrap_document=document,
                manual_intent_service=intents,
                manual_preview_service=previews,
                manual_execution_service=executions,
                media_discovery_service=discovery,
                storage_adapters=dict(storages),
            )
            try:
                yield SimpleNamespace(
                    api=api,
                    repository=repository,
                    intents=intents,
                    previews=previews,
                    executions=executions,
                    execution_worker=execution_worker,
                    discovery=discovery,
                    task_engine=task_engine,
                    configuration=runtime,
                    clock=self.clock,
                    source=source,
                    target=target,
                    storages=storages,
                    revision=revision,
                )
            finally:
                pass

    def assert_zero_mutation_with_admitted_work(self, value) -> None:
        """Discovery is metadata-only even though its organizing Task is real.

        RO-2/Task46.3: the durable Task admitted with the selection is *not* a
        media effect.  This proves both facts the older ``list_tasks() == ()``
        assertion conflated: no Storage mutation happened, and every admitted Task
        of this journey is still an unexecuted, non-terminal organizing Task whose
        bounded walk has not produced a TaskItem yet.
        """

        self.assertEqual([], value.source.mutations)
        self.assertEqual([], value.target.mutations)
        tasks = tuple(value.repository.list_tasks(limit=50))
        self.assertTrue(tasks)
        for task in tasks:
            self.assertEqual("manual_organize", task.command)
            self.assertNotIn(task.status.value, {"completed", "partial_success", "failed"})
            self.assertEqual((), value.repository.list_items(task.task_id))

    def assert_organizing_task_admitted(self, value, document) -> None:
        """The admitted Files selection already owns one durable organizing Task."""

        task_id = document.get("organizeTaskId")
        self.assertIsInstance(task_id, str, document)
        task = value.repository.get_task(task_id)
        self.assertIsNotNone(task, document)
        self.assertEqual("manual_organize", task.command)
        self.assertEqual("pending", task.status.value)
        self.assertTrue(task.execute_authorized)
        self.assertEqual(document["configurationSnapshotId"], task.configuration_snapshot_id)

    @staticmethod
    def request(value, path: str, method: str = "GET", body=None, *, token=OPERATOR_TOKEN):
        statuses: list[str] = []
        raw = json.dumps(body).encode() if body is not None else b""
        path_info, _, query_string = path.partition("?")
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path_info,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(raw)),
            "REMOTE_ADDR": "127.0.0.1",
            "wsgi.input": io.BytesIO(raw),
            "CONTENT_TYPE": "application/json",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        response = b"".join(value.api(environ, lambda status, headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(response)

    def advance_once(self, value, *, step: int = 0) -> dict:
        """Advance one bounded Worker step and return the operator projection."""

        result = claim_and_run(
            value.discovery, worker_id=f"worker-{step}", claim_token=f"token-{step}"
        )
        if result is None:
            raise AssertionError("discovery was not claimable")
        status, document = self.request(
            value, f"/api/operations/organize/discoveries/{result.discovery_id}"
        )
        if status != 200:
            raise AssertionError(document)
        return document

    def run_discovery(self, value, *, steps: int = 5) -> dict:
        """Drive the resident-Worker path until the discovery settles.

        Returns the *operator projection* of the settled discovery, exactly as
        the authenticated readback publishes it.
        """

        result = None
        for index in range(steps):
            result = claim_and_run(
                value.discovery, worker_id=f"worker-{index}", claim_token=f"token-{index}"
            )
            if result is None:
                raise AssertionError("discovery was not claimable")
            if result.terminal:
                break
        else:
            raise AssertionError("discovery did not settle within the bounded step budget")
        status, document = self.request(
            value, f"/api/operations/organize/discoveries/{result.discovery_id}"
        )
        if status != 200:
            raise AssertionError(document)
        return document


def _activate(service, document):
    draft = service.import_draft(document, actor="tester")
    validated = service.validate(draft.revision_id, actor="tester")
    if validated.status.value != "validated":
        raise AssertionError(validated.validation_errors)
    return service.activate(
        validated.revision_id, expected_version=validated.version, actor="tester"
    )


def _runtime_for(managed, revision, *, stability, exclude_rules):
    """Load the pinned revision and inject the library-level policy under test."""

    from dataclasses import replace as _replace

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
    )
    libraries = tuple(
        _replace(
            library,
            exclude_rules=tuple(exclude_rules),
            stability_policy=stability or library.stability_policy,
        )
        for library in runtime.resource_libraries
    )
    return _replace(runtime, resource_libraries=libraries)


class RetainedTaskKernelFilesJourneyTests(_DiscoveryFixture):
    """The Files journeys this Task retained, driven only by the Task kernel.

    The retired standalone discovery/execution Worker modules are gone; every
    admission here goes through the real authenticated Files API and is
    advanced exclusively by ``ManualTaskEngineWorker`` under its scheduling
    claim, exactly like the resident Worker.
    """

    def _admit(self, value, paths, *, request_id=None):
        body = {"paths": list(paths), "autoPrepare": True}
        if request_id is not None:
            body["requestId"] = request_id
        return self.request(
            value,
            "/api/resource-libraries/library/files/discoveries",
            "POST",
            body,
        )

    def _drive(self, value, task_id, *, steps=12):
        from mediaflow.domain.task_scheduling import TaskQueueState

        for _ in range(steps):
            value.repository.heartbeat_worker("task-engine-worker", self.clock())
            value.task_engine.run_next()
            discovery = value.repository.get_media_discovery_for_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            if discovery is None or state is None:
                continue
            if state.queue_state in {
                TaskQueueState.WAITING_HUMAN,
                TaskQueueState.SETTLED,
            }:
                return discovery
        return value.repository.get_media_discovery_for_task(task_id)

    def _projection(self, value, discovery_id):
        status, document = self.request(
            value, f"/api/operations/organize/discoveries/{discovery_id}"
        )
        self.assertEqual(200, status, document)
        return document

    def test_real_stability_requires_an_elapsed_unchanged_observation(self) -> None:
        """A file is admitted only after its real stable interval elapsed."""

        self.media("Movies/One.2001.mkv", modified_at=datetime(2025, 12, 31, tzinfo=UTC))
        with self.journey(
            task_scheduling=True,
            stability=FileStabilityPolicy(
                minimum_age_seconds=0,
                modified_threshold_seconds=0,
                stable_size_duration_seconds=60,
            ),
        ) as value:
            status, admitted = self._admit(value, ["Movies"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]

            # First observation: the interval is not fabricated, so the source
            # is honestly not yet proven stable and the Task waits.
            value.task_engine.run_next()
            discovery = value.repository.get_media_discovery_for_task(task_id)
            self.assertIsNotNone(discovery)
            first = self._projection(value, discovery.discovery_id)
            self.assertEqual(0, first["progress"]["primarySources"], first)
            self.assertEqual(1, first["progress"]["unstableEntries"], first)
            self.assertEqual("waiting_stability", first["status"], first)
            self.assertFalse(first["progress"]["incomplete"])

            # A later observation of the same unchanged source proves the
            # elapsed interval and admits it exactly once, still under the
            # same Task claim.
            value.clock.advance(120)
            discovery = self._drive(value, task_id)
            self.assertIsNotNone(discovery)
            settled = self._projection(value, discovery.discovery_id)
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual(1, len(settled["sources"]), settled)
            self.assertEqual(0, settled["progress"]["unstableEntries"], settled)
            self.assertEqual(1, settled["primarySourceCount"], settled)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_one_hundred_and_one_primary_items_cannot_yield_a_prefix(self) -> None:
        """101 eligible files refuse a truncated executable prefix."""

        for index in range(101):
            self.media(f"Movies/Bulk.{index:03d}.mkv")
        with self.journey(task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            self.assertIsNotNone(discovery)
            settled = self._projection(value, discovery.discovery_id)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertEqual("primary_limit", settled["progress"]["incompleteReason"])
            self.assertEqual(100, settled["progress"]["primarySources"])
            self.assertTrue(settled["progress"]["incomplete"])
            self.assertFalse(settled["actions"]["finalize"]["available"])
            self.assertEqual("discovery_budget_limited", settled["actions"]["finalize"]["refusal"])
            self.assertIn("narrow", settled["nextAction"])

            status, refused = self.request(
                value,
                f"/api/operations/organize/discoveries/{discovery.discovery_id}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("discovery_budget_limited", refused["error"]["code"])
            self.assertIsNone(refused.get("intentId"))
            # No items were frozen and no Storage effect happened.
            self.assertEqual((), value.repository.list_items(task_id))
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_colon_named_directory_and_file_mixed_selections_admit_exact_plans(self) -> None:
        """Directory and mixed scopes keep literal colon names exact."""

        from mediaflow.domain.manual_organize_preview import ManualPreviewItemStatus

        directory = "电影/Directory: Set"
        mixed_folder = "电影/Mixed: Folder"
        mixed_file = "电影/Mixed: Other/Mixed Two.2026.mkv"
        sources = {
            f"{directory}/Directory One.2026.mkv": "Directory One",
            f"{directory}/Directory Two.2026.mkv": "Directory Two",
            f"{mixed_folder}/Mixed One.2026.mkv": "Mixed One",
            mixed_file: "Mixed Two",
        }
        for path in sources:
            self.media(path, size=256)
        provider = SyntheticMetadataProvider(
            tuple(
                MediaCandidate(
                    "tmdb",
                    str(300 + index),
                    MediaType.MOVIE,
                    title,
                    year=2026,
                    genres=("Animation",),
                    countries=("CN",),
                )
                for index, title in enumerate(sources.values())
            )
        )
        document = self.document()
        document["recognitionRules"][0]["condition"]["children"][0]["value"] = "library"
        with self.journey(task_scheduling=True, provider=provider) as value:
            self.publish_policy(value, document=document)

            status, admitted = self._admit(value, [directory])
            self.assertEqual(202, status, admitted)
            discovery = self._drive(value, admitted["organizeTaskId"])
            self.assertIsNotNone(discovery)
            settled = self._projection(value, discovery.discovery_id)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(
                sorted(list(sources)[:2]), sorted(item["path"] for item in settled["sources"])
            )
            preview = value.repository.get_manual_preview(settled["previewId"])
            self.assertIsNotNone(preview)
            self.assertEqual(
                sorted(list(sources)[:2]),
                sorted(item.source.path for item in preview.items),
            )
            self.assertEqual(
                [ManualPreviewItemStatus.PREVIEWED] * 2,
                [item.status for item in preview.items],
            )

            status, admitted = self._admit(value, [mixed_folder, mixed_file])
            self.assertEqual(202, status, admitted)
            discovery = self._drive(value, admitted["organizeTaskId"])
            self.assertIsNotNone(discovery)
            mixed = self._projection(value, discovery.discovery_id)
            self.assertEqual("completed", mixed["status"], mixed)
            expected = sorted((f"{mixed_folder}/Mixed One.2026.mkv", mixed_file))
            self.assertEqual(expected, sorted(item["path"] for item in mixed["sources"]))
            mixed_preview = value.repository.get_manual_preview(mixed["previewId"])
            self.assertIsNotNone(mixed_preview)
            self.assertEqual(expected, sorted(item.source.path for item in mixed_preview.items))
            self.assertEqual(
                [ManualPreviewItemStatus.PREVIEWED] * 2,
                [item.status for item in mixed_preview.items],
            )
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_a_colon_named_scope_reaches_one_real_confirmed_move(self) -> None:
        """Punctuation colons stay one exact source through confirmation."""

        from mediaflow.domain.task_persistence import PersistentTaskStatus

        source_path = (
            "电影/Perfect World Movie: Nine Tribulations Incinerate the Heavens "
            "(2026) [tmdbid=1598732]/Perfect World Movie: Nine Tribulations "
            "Incinerate the Heavens.2026.2160p.WEB-DL.SDR.42.0Mbps.H.265."
            "Dolby Digital Plus.mkv"
        )
        title = "Perfect World Movie: Nine Tribulations Incinerate the Heavens"
        self.media(source_path, size=512)
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "1598732",
                    MediaType.MOVIE,
                    title,
                    year=2026,
                    genres=("Animation",),
                    countries=("CN",),
                ),
            )
        )
        document = self.document()
        document["recognitionRules"][0]["condition"]["children"][0]["value"] = "library"
        with self.journey(task_scheduling=True, provider=provider) as value:
            self.publish_policy(value, document=document)
            status, admitted = self._admit(value, [source_path])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            self.assertIsNotNone(discovery)
            settled = self._projection(value, discovery.discovery_id)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual([source_path], [item["path"] for item in settled["sources"]])

            preview = value.repository.get_manual_preview(settled["previewId"])
            self.assertIsNotNone(preview)
            self.assertEqual([source_path], [item.source.path for item in preview.items])
            status, preview_document = self.request(
                value,
                f"/api/operations/organize/previews/{settled['previewId']}",
            )
            self.assertEqual(200, status, preview_document)
            ready = [
                item["itemId"]
                for item in preview_document["items"]
                if item["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview_document)
            status, admitted_execution = self.request(
                value,
                f"/api/operations/organize/previews/{settled['previewId']}/execute",
                "POST",
                {
                    "confirmation": True,
                    "itemIds": ready,
                    "expectedIntentVersion": preview_document["intentVersion"],
                    "allowOverwrite": False,
                    "allowSourceCleanup": False,
                },
            )
            self.assertIn(status, (200, 202), admitted_execution)
            for _ in range(8):
                value.task_engine.run_next()
                if value.repository.get_task(task_id).status is PersistentTaskStatus.COMPLETED:
                    break
            self.assertIs(
                PersistentTaskStatus.COMPLETED,
                value.repository.get_task(task_id).status,
            )
            self.assertFalse((self.source_root / source_path).exists())
            moved = list(Path(self.target_root).rglob("*.mkv"))
            self.assertEqual(1, len(moved))
            self.assertEqual(b"m" * 512, moved[0].read_bytes())
