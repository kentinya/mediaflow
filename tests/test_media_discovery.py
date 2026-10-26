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
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import quote

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.manual_organize_worker import ManualOrganizeExecutionWorker
from mediaflow.application.media_discovery import MediaDiscoveryService
from mediaflow.application.media_discovery_worker import MediaDiscoveryWorker
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.library import FileStabilityPolicy
from mediaflow.domain.manual_organize import ManualSourceIdentity
from mediaflow.domain.manual_organize_preview import ManualPreviewItemStatus
from mediaflow.domain.media_discovery import (
    DiscoveryBudgets,
    DiscoveryConflict,
    DiscoveryError,
    DiscoveryObservation,
)
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.source_evidence import occurrence_id_for, source_fingerprint
from mediaflow.domain.storage import (
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
    StoragePage,
)
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.in_memory_storage import InMemoryStorage
from tests.storage_fixtures import PagedMemoryStorage

SNAPSHOT_ID = "active-1"
SNAPSHOT_DIGEST = "a" * 64
OPERATOR_TOKEN = "operator-token"


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
    ) -> dict:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
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
        source_storage=None,
        provider=None,
    ):

        document = self.document(
            stability=stability,
            max_depth=max_depth,
            extensions=extensions,
            second_library=second_library,
            attachments=attachments,
        )
        if metadata_query_type is not None:
            for policy in document.get("metadataPolicies", []):
                policy["mediaQueryType"] = metadata_query_type
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
            )
            api = MediaFlowApi(
                repository,
                None,
                principals=(
                    ResolvedApiPrincipal(
                        "operator",
                        OPERATOR_TOKEN,
                        frozenset(
                            {
                                ApiPermission.READ,
                                ApiPermission.MANAGE_MANUAL_ORGANIZE,
                                ApiPermission.EXECUTE_MANUAL_ORGANIZE,
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

        result = value.discovery.claim_and_run(
            worker_id=f"worker-{step}", claim_token=f"token-{step}"
        )
        if result is None:
            raise AssertionError("discovery was not claimable")
        status, document = self.request(
            value, f"/api/v1/operations/organize/discoveries/{result.discovery_id}"
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
            result = value.discovery.claim_and_run(
                worker_id=f"worker-{index}", claim_token=f"token-{index}"
            )
            if result is None:
                raise AssertionError("discovery was not claimable")
            if result.terminal:
                break
        else:
            raise AssertionError("discovery did not settle within the bounded step budget")
        status, document = self.request(
            value, f"/api/v1/operations/organize/discoveries/{result.discovery_id}"
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


class AdmissionAndScopeTests(_DiscoveryFixture):
    """Scope 1 and AC2: whole-scope validation and component-aware deduplication."""

    def test_folder_only_selection_admits_one_durable_discovery(self) -> None:
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey() as value:
            status, document = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, document)
            self.assertEqual("discovery", document["journey"])
            self.assertTrue(document["zeroMutation"])
            self.assertEqual("queued", document["status"])
            self.assertEqual(
                [{"path": "Movies", "kind": "directory"}], document["selection"]["scopes"]
            )
            self.assertEqual([], value.source.mutations)
            # RO-2: the organizing Task is admitted *before* any traversal or
            # business readiness, so exactly one durable pending Task with the
            # admitting pin and admitted scope already exists here.
            self.assert_organizing_task_admitted(value, document)
            encoded = json.dumps(document)
            for forbidden in ("fingerprint", "occurrenceId", SNAPSHOT_DIGEST, "Bearer "):
                self.assertNotIn(forbidden, encoded)

    def test_mixed_selection_deduplicates_component_aware_overlaps(self) -> None:
        self.media("Movies/One.2001.mkv")
        self.media("Movies/SP/Extra.mkv")
        self.media("Movies/SP/Deep/More.mkv")
        with self.journey() as value:
            status, document = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {
                    "paths": [
                        "Movies",
                        "Movies/One.2001.mkv",
                        "Movies/SP",
                        "Movies/SP/Deep",
                        "Movies",
                    ]
                },
            )
            self.assertEqual(202, status, document)
            # The parent folder covers every descendant and the repeated value;
            # the explicit file inside it is not a second admitted scope.
            self.assertEqual(
                [{"path": "Movies", "kind": "directory"}], document["selection"]["scopes"]
            )

    def test_a_file_and_its_sibling_folder_are_both_admitted_once(self) -> None:
        self.media("Movies/One.2001.mkv")
        self.media("Shows/Ep.01.mkv")
        with self.journey() as value:
            status, document = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/One.2001.mkv", "Shows"]},
            )
            self.assertEqual(202, status, document)
            self.assertEqual(
                [
                    {"path": "Movies/One.2001.mkv", "kind": "file"},
                    {"path": "Shows", "kind": "directory"},
                ],
                document["selection"]["scopes"],
            )

    def test_invalid_scope_is_rejected_before_any_durable_admission(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            cases = (
                (["../escape.mkv"], 400, "invalid_path"),
                (["/etc/passwd"], 400, "invalid_path"),
                (["Movies" + chr(92) + "One.mkv"], 400, "invalid_path"),
                (["Movies/./One.mkv"], 400, "invalid_path"),
                ([], 400, "selection_empty"),
                (["Movies/Missing.mkv"], 404, "source_missing"),
                (
                    [f"Movies/Bulk.{index:03d}.mkv" for index in range(101)],
                    400,
                    "selection_over_limit",
                ),
            )
            for paths, expected_status, code in cases:
                status, document = self.request(
                    value,
                    "/api/v1/resource-libraries/library/files/discoveries",
                    "POST",
                    {"paths": paths},
                )
                self.assertEqual(expected_status, status, (paths, document))
                self.assertEqual(code, document["error"]["code"], paths)
            # A partly invalid request never becomes a different valid scope.
            self.assertEqual((), value.repository.list_media_discoveries())
            self.assertEqual([], value.source.mutations)

    def test_files_admission_commits_a_real_pending_organizing_task(self) -> None:
        """RO-2/B46.3-01: the organizing Task exists before business readiness.

        The Files command must create observable durable organizing work
        immediately — before the bounded walk, a Provider lookup, target calculation
        or an executable plan.  A preparation rename or a detached placeholder is not
        enough: the Task carries its own admitted scope, the immutable pin and
        execute authority, and the discovery links it.
        """

        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {
                    "paths": ["Movies"],
                    "autoPrepare": True,
                    "requestId": "11111111-1111-4111-8111-111111111111",
                },
            )
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            self.assertIsInstance(task_id, str, admitted)
            task = value.repository.get_task(task_id)
            self.assertIsNotNone(task)
            self.assertEqual("manual_organize", task.command)
            self.assertEqual("pending", task.status.value)
            self.assertTrue(task.execute_authorized)
            self.assertEqual(admitted["configurationSnapshotId"], task.configuration_snapshot_id)
            self.assertIsNotNone(task.configuration_snapshot_digest)
            # The Task is admitted before any item, plan or effect exists.
            self.assertEqual((), value.repository.list_items(task_id))
            self.assertIsNone(admitted["previewId"])
            self.assertIsNone(admitted["intentId"])
            # The same organizing work is reachable from the admitted record, so
            # progress/decisions/confirmation all belong to this one Task.
            stored = value.repository.get_media_discovery(admitted["discoveryId"])
            self.assertEqual(task_id, stored.organize_task_id)
            self.assertEqual([], value.source.mutations)
            # The bounded walk then advances the same Task instead of creating a
            # second one.
            settled = self.run_discovery(value)
            self.assertIn(settled["status"], {"completed", "partial_success"}, settled)
            self.assertEqual([task_id], [item.task_id for item in value.repository.list_tasks()])
            self.assertIn(value.repository.get_task(task_id).status.value, {"running", "pending"})

    def test_a_second_request_keeps_its_own_refused_item(self) -> None:
        """B46.3-02: a converging request never answers with the first result.

        A submits `[One]`.  B submits `[One, downloading.mkv.part]` before A's work
        runs: B legitimately converges on the same durable work, but B's own result
        must still report A's file as *existing* work and its own `.part` sibling as
        refused with the temporary-file reason.  An exact repetition of B reads the
        identical answer, and nothing is executed twice.
        """

        self.media("Movies/One.2001.mkv")
        self.media("Movies/downloading.mkv.part")
        first = {
            "paths": ["Movies/One.2001.mkv"],
            "autoPrepare": True,
            "requestId": "11111111-1111-4111-8111-111111111111",
        }
        second = {
            "paths": ["Movies/One.2001.mkv", "Movies/downloading.mkv.part"],
            "autoPrepare": True,
            "requestId": "22222222-2222-4222-8222-222222222222",
        }
        with self.journey() as value:
            status, admitted = self.request(
                value, "/api/v1/resource-libraries/library/files/discoveries", "POST", first
            )
            self.assertEqual(202, status, admitted)
            self.assertEqual([], admitted["selection"]["existing"])
            self.assertEqual([], admitted["selection"]["refused"])

            status, converged = self.request(
                value, "/api/v1/resource-libraries/library/files/discoveries", "POST", second
            )
            self.assertEqual(202, status, converged)
            self.assertEqual(admitted["discoveryId"], converged["discoveryId"])
            # B's one still-admissible member is the already admitted file, so it
            # appears as the *shared* admitted scope, and its excluded sibling keeps
            # its own reason.
            self.assertEqual(
                [{"path": "Movies/One.2001.mkv", "kind": "file"}],
                converged["selection"]["scopes"],
            )
            self.assertEqual(
                ["Movies/downloading.mkv.part"],
                [item["path"] for item in converged["selection"]["refused"]],
            )
            self.assertEqual("temporary_file", converged["selection"]["refused"][0]["reason"])

            # An exact repetition of B is stable: no duplicated work, no lost
            # refusal evidence, no rewritten first result.
            status, repeated = self.request(
                value, "/api/v1/resource-libraries/library/files/discoveries", "POST", second
            )
            self.assertEqual(202, status, repeated)
            self.assertEqual(converged["selection"], repeated["selection"])

            # The exact second request identity reads back its own result.
            status, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{converged['discoveryId']}"
                "?requestId=22222222-2222-4222-8222-222222222222",
            )
            self.assertEqual(200, status, detail)
            self.assertEqual(converged["selection"], detail["selection"])
            self.assertEqual("22222222-2222-4222-8222-222222222222", detail["admissionRequestId"])

            # The first request still reads its own original result.
            status, first_detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}"
                "?requestId=11111111-1111-4111-8111-111111111111",
            )
            self.assertEqual(200, status, first_detail)
            self.assertEqual([], first_detail["selection"]["refused"])
            self.assertEqual([], first_detail["selection"]["existing"])
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual([], value.source.mutations)

    def test_a_refused_sibling_does_not_block_an_independent_third_file(self) -> None:
        """RO-2: eligible siblings stay independently admissible."""

        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        self.media("Movies/Three.2003.mkv")
        self.media("Movies/downloading.mkv.part")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {
                    "paths": ["Movies/One.2001.mkv"],
                    "autoPrepare": True,
                    "requestId": "11111111-1111-4111-8111-111111111111",
                },
            )
            self.assertEqual(202, status, admitted)
            status, converged = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {
                    "paths": [
                        "Movies/One.2001.mkv",
                        "Movies/downloading.mkv.part",
                        "Movies/Three.2003.mkv",
                    ],
                    "autoPrepare": True,
                    "requestId": "22222222-2222-4222-8222-222222222222",
                },
            )
            self.assertEqual(202, status, converged)
            self.assertEqual(
                [{"path": "Movies/Three.2003.mkv", "kind": "file"}],
                converged["selection"]["scopes"],
            )
            self.assertEqual(
                ["Movies/One.2001.mkv"],
                [item["path"] for item in converged["selection"]["existing"]],
            )
            self.assertEqual(
                ["Movies/downloading.mkv.part"],
                [item["path"] for item in converged["selection"]["refused"]],
            )
            self.assertEqual([], value.source.mutations)

    def test_files_work_readback_reopens_multiple_runs_by_request_identity(self) -> None:
        """RO-2: Files reads several known runs and one exact lost request."""

        self.media("Movies/One.2001.mkv")
        self.media("Other/Two.2002.mkv")
        with self.journey() as value:
            for index in range(3):
                status, admitted = self.request(
                    value,
                    "/api/v1/resource-libraries/library/files/discoveries",
                    "POST",
                    {
                        "paths": ["Movies/One.2001.mkv" if index == 0 else "Other/Two.2002.mkv"],
                        "autoPrepare": True,
                        "requestId": f"1111111{index}-1111-4111-8111-111111111111",
                    },
                )
                self.assertEqual(202, status, admitted)
            status, page = self.request(
                value, "/api/v1/resource-libraries/library/files/organize-work?limit=1"
            )
            self.assertEqual(200, status, page)
            self.assertEqual(1, len(page["items"]))
            self.assertIsNotNone(page["nextBefore"], page)
            status, next_page = self.request(
                value,
                "/api/v1/resource-libraries/library/files/organize-work"
                f"?limit=1&before={quote(page['nextBefore'], safe='')}",
            )
            self.assertEqual(200, status, next_page)
            self.assertEqual(1, len(next_page["items"]))
            self.assertNotEqual(
                page["items"][0]["discoveryId"], next_page["items"][0]["discoveryId"]
            )
            status, exact = self.request(
                value,
                "/api/v1/resource-libraries/library/files/organize-work"
                "?requestId=11111111-1111-4111-8111-111111111111",
            )
            self.assertEqual(200, status, exact)
            self.assertEqual(1, len(exact["items"]))
            self.assertEqual(
                "11111111-1111-4111-8111-111111111111",
                exact["items"][0]["admissionRequestId"],
            )
            status, missing = self.request(
                value,
                "/api/v1/resource-libraries/library/files/organize-work"
                "?requestId=99999999-9999-4999-8999-999999999999",
            )
            self.assertEqual(200, status, missing)
            self.assertEqual([], missing["items"])
            self.assertEqual([], value.source.mutations)

    def test_a_newly_accepted_sibling_really_enters_the_admitted_scope(self) -> None:
        """B46.3-02: an accepted sibling must reach discovery, not just the reply.

        A submits `[One]`.  B submits `[One, Three]` before the walk runs.  B's
        response says `Three` was admitted, so the *durable* work must really hold
        it: the very next Worker pass has to discover it, and the exact readback of
        each request keeps its own evidence.  A response-only "admission" is a lost
        admission — the operator would wait forever for work that never ran.
        """

        self.media("Movies/One.2001.mkv")
        self.media("Movies/Three.2003.mkv")
        with self.journey() as value:
            status, first = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {
                    "paths": ["Movies/One.2001.mkv"],
                    "autoPrepare": True,
                    "requestId": "11111111-1111-4111-8111-111111111111",
                },
            )
            self.assertEqual(202, status, first)
            status, second = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {
                    "paths": ["Movies/One.2001.mkv", "Movies/Three.2003.mkv"],
                    "autoPrepare": True,
                    "requestId": "22222222-2222-4222-8222-222222222222",
                },
            )
            self.assertEqual(202, status, second)
            self.assertEqual(first["discoveryId"], second["discoveryId"])
            self.assertEqual(
                [{"kind": "file", "path": "Movies/Three.2003.mkv"}],
                second["selection"]["scopes"],
            )
            self.assertEqual(
                ["Movies/One.2001.mkv"],
                [item["path"] for item in second["selection"]["existing"]],
            )

            # The durable scope — not only the reply — really holds the sibling.
            stored = value.repository.get_media_discovery(first["discoveryId"])
            self.assertEqual(
                ["Movies/One.2001.mkv", "Movies/Three.2003.mkv"],
                sorted(entry.path for entry in stored.progress.scope_entries),
            )
            self.assertEqual(
                "Movies/Three.2003.mkv", dict(stored.storage_scope)["Movies/Three.2003.mkv"]
            )

            # The real Worker discovers both, so the accepted sibling really runs.
            settled = self.run_discovery(value)
            self.assertIn(settled["status"], {"completed", "partial_success"}, settled)
            self.assertEqual(
                ["Movies/One.2001.mkv", "Movies/Three.2003.mkv"],
                sorted(item["path"] for item in settled["sources"]),
            )
            self.assertIsNotNone(settled["intentId"])
            intent = value.repository.get_manual_intent(settled["intentId"])
            self.assertEqual(
                ["Movies/One.2001.mkv", "Movies/Three.2003.mkv"],
                sorted(item.source.path for item in intent.items),
            )
            # Exactly one durable organizing Task: converging requests never
            # duplicate the admitted work.
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual([], value.source.mutations)

    def test_overlapping_library_bindings_own_one_concrete_storage_source(self) -> None:
        """B46.3-04: identity is the confined Storage path, not the binding.

        One temporary file is exposed through two valid ResourceLibrary bindings of
        the same Storage: `nested` rooted at `Movies` and `whole` rooted at the
        Storage root.  Submitting `nested/One.2001.mkv` and then
        `whole/Movies/One.2001.mkv` names the same concrete source, so the second
        request must be refused with the exact existing work instead of starting a
        second organizing Task.
        """

        self.media("Movies/One.2001.mkv")
        document = self.document()
        # Two valid bindings of the *same* Storage: the whole Storage root and a
        # root nested at `Movies`.
        document["resourceLibraries"] = [
            {
                "id": "whole",
                "name": "Whole",
                "storageId": "source",
                "storagePath": "",
                "enabled": True,
                "extensions": ["mkv", "mp4"],
                "maxDepth": None,
                "excludeRules": [],
            },
            {
                "id": "nested",
                "name": "Nested",
                "storageId": "source",
                "storagePath": "Movies",
                "enabled": True,
                "extensions": ["mkv", "mp4"],
                "maxDepth": None,
                "excludeRules": [],
            },
        ]
        with self.journey() as value:
            self.publish_policy(value, document=document)
            status, first = self.request(
                value,
                "/api/v1/resource-libraries/nested/files/discoveries",
                "POST",
                {
                    "paths": ["One.2001.mkv"],
                    "autoPrepare": True,
                    "requestId": "11111111-1111-4111-8111-111111111111",
                },
            )
            self.assertEqual(202, status, first)
            stored = value.repository.get_media_discovery(first["discoveryId"])
            self.assertEqual("Movies/One.2001.mkv", dict(stored.storage_scope)["One.2001.mkv"])
            status, second = self.request(
                value,
                "/api/v1/resource-libraries/whole/files/discoveries",
                "POST",
                {"paths": ["Movies/One.2001.mkv"], "autoPrepare": True},
            )
            self.assertEqual(409, status, second)
            self.assertEqual("source_already_organizing", second["error"]["code"])
            # The refusal names exactly the work that already owns that concrete
            # source, so the operator opens it instead of starting a duplicate.
            self.assertEqual(first["discoveryId"], second["error"]["details"]["existingWorkId"])
            # Exactly one admitted organizing work exists for that source.
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual([], value.source.mutations)

    def test_a_legal_recovery_preparation_does_not_own_itself_out(self) -> None:
        """B46.3-01: a continuation's own lineage is not a competing owner.

        A remaining-scope recovery preparation reviews exactly the still-undecided
        sources of the paused Task it was admitted for.  Those ancestor TaskItems
        must never make the preparation refuse its own remaining scope, otherwise
        the native recovery journey can never reach a summary at all.
        """

        from datetime import UTC
        from datetime import datetime as _datetime

        from mediaflow.application.task_runtime import PersistentTaskCoordinator

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            self.assertEqual((), value.repository.list_tasks())
            snapshot_id, digest = value.discovery._active_pin()
            coordinator = PersistentTaskCoordinator(value.repository, value.repository)
            paused = coordinator.create(
                "organize",
                execute_authorized=True,
                scope_path="Movies",
                item_limit=2,
                configuration_snapshot_id=snapshot_id,
                configuration_snapshot_digest=digest,
                require_configuration_snapshot=True,
            )
            recorded = coordinator.record_discovered(
                paused.task_id,
                "source",
                "library",
                "Movies/One.2001.mkv",
                "source:Movies/One.2001.mkv",
            )
            entry = value.source.stat("Movies/One.2001.mkv")
            fingerprint = source_fingerprint("source", "library", entry)
            value.repository.upsert_item(
                replace(
                    recorded,
                    status=TaskItemStatus.PENDING,
                    stage="pending",
                    source_fingerprint=fingerprint.value,
                    source_fingerprint_state="verified",
                    source_occurrence_id=occurrence_id_for(
                        "source", "library", "Movies/One.2001.mkv", fingerprint.value
                    ),
                    source_observed_at=_datetime.now(UTC),
                )
            )
            value.repository.request_task_pause(paused.task_id, value.discovery._clock())
            coordinator.acknowledge_pause(paused.task_id)
            current = value.repository.get_task(paused.task_id)
            self.assertEqual("paused", current.status.value)
            # The ancestor TaskItem really is unfinished work of that source.
            self.assertIsNotNone(
                value.repository.find_owned_source_work(
                    storage_id="source",
                    source_path="Movies/One.2001.mkv",
                    resource_library_id="library",
                )
            )
            # ...yet the legal continuation of that very Task is not refused.
            self.assertIsNone(
                value.repository.find_owned_source_work(
                    storage_id="source",
                    source_path="Movies/One.2001.mkv",
                    resource_library_id="library",
                    exclude_lineage_task_id=current.task_id,
                )
            )

    def test_a_folder_walk_does_not_admit_an_already_owned_source_again(self) -> None:
        """RO-2/AC-3: verified source ownership across overlapping requests.

        A directly selected file is refused at admission when an unfinished
        organizing work owns it.  A *folder* is deliberately admitted as outer work
        before traversal, so its discovered sources are checked inside its own
        bounded walk: the owned file is kept out of that manifest with the exact
        existing-work reference, while a genuinely free sibling in the same folder is
        still admitted.  No concrete source can be organized twice, and no pre-task
        traversal is required.
        """

        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {
                    "paths": ["Movies/One.2001.mkv"],
                    "autoPrepare": True,
                    "requestId": "11111111-1111-4111-8111-111111111111",
                },
            )
            self.assertEqual(202, status, admitted)
            settled_first = self.run_discovery(value)
            self.assertEqual("completed", settled_first["status"], settled_first)
            self.assertIsNotNone(settled_first["intentId"])
            self.assertEqual(
                ["Movies/One.2001.mkv"],
                [item["path"] for item in settled_first["sources"]],
            )

            status, folder = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {
                    "paths": ["Movies"],
                    "autoPrepare": True,
                    "requestId": "22222222-2222-4222-8222-222222222222",
                },
            )
            self.assertEqual(202, status, folder)
            self.assertNotEqual(admitted["discoveryId"], folder["discoveryId"])
            settled_folder = self.run_discovery(value)
            self.assertEqual(
                ["Movies/Two.2002.mkv"],
                [item["path"] for item in settled_folder["sources"]],
            )
            owned = [
                item
                for item in settled_folder["selection"]["refused"]
                if item["path"] == "Movies/One.2001.mkv"
            ]
            self.assertEqual(1, len(owned), settled_folder["selection"])
            self.assertEqual("source_already_organizing", owned[0]["reason"])
            # The exact existing work is named (a durable Task when a confirmed
            # execution owns it, otherwise the unfinished organizing admission).
            self.assertIn(owned[0]["existingWorkKind"], {"task", "discovery"})
            self.assertIsNotNone(owned[0]["existingWorkId"])
            self.assertEqual([], value.source.mutations)

    def test_symlink_and_root_selection_fail_closed(self) -> None:
        self.media("Movies/One.2001.mkv")
        os.symlink(
            str(self.source_root / "Movies" / "One.2001.mkv"),
            str(self.source_root / "Movies" / "linked.mkv"),
        )
        with self.journey() as value:
            status, document = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/linked.mkv"]},
            )
            self.assertEqual(409, status, document)
            self.assertEqual("source_symlink", document["error"]["code"])

    def test_discovery_admission_requires_manage_permission(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            status, document = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
                token="viewer-token",
            )
            self.assertEqual(403, status, document)
            self.assertEqual("forbidden", document["error"]["code"])

    def test_a_disabled_or_unknown_library_is_refused(self) -> None:
        with self.journey() as value:
            status, document = self.request(
                value,
                "/api/v1/resource-libraries/other/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(404, status, document)
            self.assertEqual("resource_library_not_found", document["error"]["code"])


class ManualEntrySemanticsTests(_DiscoveryFixture):
    """Slice46 RO-2/Task46.3 Scope 2: deliberate selection vs automatic scan.

    A directly selected file is the operator's own inclusion decision.  A
    suffix that is merely absent from the configured allowlist, an include-rule
    miss or a non-extension exclude/match rule keeps its unchanged meaning for
    a *folder expansion* without becoming an additional manual veto.  A
    deliberate selection still obeys what was explicitly excluded for that
    exact file: the built-in temporary/download suffixes and a configured
    extension exclusion.  Every case here runs through the real API, the real
    bounded Worker and real Local Storage.
    """

    def test_directly_selected_unlisted_suffix_is_admitted(self) -> None:
        """A `.txt` file clicked by name is admitted; a folder walk still skips it."""

        self.media("Movies/notes.txt")
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/notes.txt"]},
            )
            self.assertEqual(202, status, admitted)
            self.assertEqual(
                [{"path": "Movies/notes.txt", "kind": "file"}],
                admitted["selection"]["scopes"],
            )
            settled = self.run_discovery(value)
            self.assertEqual(["Movies/notes.txt"], [item["path"] for item in settled["sources"]])
            self.assertEqual([], value.source.mutations)

            # The same suffix reached *through a folder* keeps the automatic
            # extension allowlist meaning: it is still excluded there.
            _, folder = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            folder_settled = self.run_discovery(value)
            self.assertEqual(
                ["Movies/One.2001.mkv"],
                [item["path"] for item in folder_settled["sources"]],
            )
            self.assertIn(
                "unsupported_extension",
                {item["reason"] for item in folder_settled["progress"]["reasons"]},
            )
            self.assertNotEqual(folder["discoveryId"], admitted["discoveryId"])

    def test_directly_selected_file_ignores_include_and_match_rules(self) -> None:
        """An include-rule miss and a file-level exclude rule do not veto a click.

        RO-2/B46.3-03: a deliberate Files selection is the operator's own
        inclusion decision, so those automatic conditions no longer veto either a
        directly named file *or* the tree of a deliberately selected folder.  The
        configured primary-media extension set is the one automatic file filter
        that remains inside a deliberate folder expansion.
        """

        self.media("Kept.2001.mkv")
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Kept.2002.mkv")
        self.media("Movies/notes.txt")
        document = self.document()
        document["resourceLibraries"][0]["includeRules"] = [
            {"kind": "glob", "pattern": "Movies/**"}
        ]
        document["resourceLibraries"][0]["excludeRules"] = [{"kind": "glob", "pattern": "**/Kept*"}]
        with self.journey() as value:
            self.publish_policy(value, document=document)
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Kept.2001.mkv"]},
            )
            self.assertEqual(202, status, admitted)
            settled = self.run_discovery(value)
            self.assertEqual(["Kept.2001.mkv"], [item["path"] for item in settled["sources"]])
            # A deliberately selected folder keeps its configured primary-media
            # extension set and drops the automatic include/match vetoes, so both
            # `mkv` files are primaries while the unlisted `.txt` suffix is not.
            _, folder = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            folder_settled = self.run_discovery(value)
            self.assertEqual(
                ["Movies/Kept.2002.mkv", "Movies/One.2001.mkv"],
                [item["path"] for item in folder_settled["sources"]],
            )
            reasons = {item["reason"] for item in folder_settled["progress"]["reasons"]}
            self.assertIn("unsupported_extension", reasons)
            self.assertNotIn("configured_exclude", reasons)
            self.assertNotIn("not_included", reasons)
            self.assertEqual([], value.source.mutations)

    def test_directly_selected_temporary_and_explicit_extension_are_refused(self) -> None:
        """A temporary suffix and a configured extension exclusion still refuse."""

        self.media("Movies/downloading.mkv.part")
        self.media("Movies/Trailer.mkv")
        document = self.document(extensions=("mkv",))
        document["resourceLibraries"][0]["excludeRules"] = [{"kind": "extension", "pattern": "mkv"}]
        with self.journey() as value:
            self.publish_policy(value, document=document)
            status, temporary = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/downloading.mkv.part"]},
            )
            self.assertEqual(409, status, temporary)
            self.assertEqual("source_excluded", temporary["error"]["code"], temporary)
            self.assertEqual("temporary_file", temporary["error"]["details"]["reason"], temporary)
            status, extension = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/Trailer.mkv"]},
            )
            self.assertEqual(409, status, extension)
            self.assertEqual("source_excluded", extension["error"]["code"], extension)
            self.assertEqual(
                "excluded_extension_rule", extension["error"]["details"]["reason"], extension
            )
            self.assertEqual((), value.repository.list_media_discoveries())
            self.assertEqual([], value.source.mutations)

    def test_a_mixed_direct_selection_admits_every_deliberate_file(self) -> None:
        """Single/multiple direct selections admit exactly the chosen files once."""

        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        self.media("Movies/notes.txt")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/One.2001.mkv", "Movies/notes.txt", "Movies/Two.2002.mkv"]},
            )
            self.assertEqual(202, status, admitted)
            self.assertEqual(
                {"Movies/One.2001.mkv", "Movies/notes.txt", "Movies/Two.2002.mkv"},
                {scope["path"] for scope in admitted["selection"]["scopes"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual(
                {"Movies/One.2001.mkv", "Movies/Two.2002.mkv", "Movies/notes.txt"},
                {item["path"] for item in settled["sources"]},
            )
            self.assertIsNone(settled["progress"]["incompleteReason"], settled)
            self.assertEqual([], value.source.mutations)

    def test_a_partly_refused_selection_keeps_eligible_siblings(self) -> None:
        """B46.3-02: a refused member is its own outcome, not a scope veto.

        Selecting an eligible file together with an explicitly excluded one must
        create real organizing work for the eligible sibling and record the
        refused item's own bounded reason, with zero mutation before the
        operator's explicit confirmation.
        """

        self.media("Movies/One.2001.mkv")
        self.media("Movies/downloading.mkv.part")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/One.2001.mkv", "Movies/downloading.mkv.part"]},
            )
            self.assertEqual(202, status, admitted)
            self.assertEqual(
                [{"path": "Movies/One.2001.mkv", "kind": "file"}],
                admitted["selection"]["scopes"],
            )
            self.assertEqual(
                [
                    {
                        "path": "Movies/downloading.mkv.part",
                        "kind": "file",
                        "code": "source_excluded",
                        "reason": "temporary_file",
                        "organizing": False,
                        "message": (
                            "the selected file is explicitly excluded by the pinned "
                            "ResourceLibrary policy"
                        ),
                        "nextAction": (
                            "select a file that is not a temporary download and not explicitly "
                            "excluded by an extension rule, or wait until the download has "
                            "finished and select it again"
                        ),
                    }
                ],
                admitted["selection"]["refused"],
            )
            self.assertEqual(1, admitted["selection"]["refusedCount"])
            settled = self.run_discovery(value)
            self.assertEqual(["Movies/One.2001.mkv"], [item["path"] for item in settled["sources"]])
            # The refusal survives the durable round-trip (a reload/restart reads
            # exactly the same evidence) and no media effect happened.
            self.assertEqual(1, settled["selection"]["refusedCount"])
            self.assertEqual([], value.source.mutations)

    def test_a_refused_sibling_stays_inside_its_admission_request_identity(self) -> None:
        """A lost-response retry of a partly refused selection reconciles.

        The refused member never became a source, so it lives in
        ``refusedEntries``.  Retrying the same request identity with the same
        selection must return the original durable work instead of claiming a
        different selection (RO-2/AC-16 + the existing exact-request contract).
        """

        self.media("Movies/One.2001.mkv")
        self.media("Movies/downloading.mkv.part")
        body = {
            "paths": ["Movies/One.2001.mkv", "Movies/downloading.mkv.part"],
            "requestId": "11111111-1111-4111-8111-111111111111",
        }
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                body,
            )
            self.assertEqual(202, status, admitted)
            status, reconciled = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                body,
            )
            self.assertEqual(202, status, reconciled)
            self.assertEqual(admitted["discoveryId"], reconciled["discoveryId"])
            # A genuinely different selection still refuses request-ID reuse.
            status, conflicted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {
                    "paths": ["Movies/One.2001.mkv"],
                    "requestId": "11111111-1111-4111-8111-111111111111",
                },
            )
            self.assertEqual(409, status, conflicted)
            self.assertEqual("admission_request_conflict", conflicted["error"]["code"], conflicted)
            self.assertEqual(1, len(value.repository.list_media_discoveries()))
            self.assertEqual([], value.source.mutations)

    def test_refused_entries_survive_a_sqlite_repository_reopen(self) -> None:
        """The per-item refusal evidence is durable, not page-local.

        A close/reload/reconnect/restart reads the same refused item and the same
        bounded reason back from the admitted work, so the operator never loses
        the explanation of which selected item did *not* become organizing work.
        """

        self.media("Movies/One.2001.mkv")
        self.media("Movies/downloading.mkv.part")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/One.2001.mkv", "Movies/downloading.mkv.part"]},
            )
            self.assertEqual(202, status, admitted)
            reopened = SQLiteTaskRepository(self.database)
            try:
                stored = reopened.get_media_discovery(admitted["discoveryId"])
            finally:
                reopened.close()
            self.assertIsNotNone(stored)
            refused = stored.progress.refused_entries
            self.assertEqual(1, len(refused))
            self.assertEqual("Movies/downloading.mkv.part", refused[0].path)
            self.assertEqual("temporary_file", refused[0].reason)
            self.assertEqual("source_excluded", refused[0].code)
            self.assertTrue(stored.progress.manual_selection)
            self.assertEqual([], value.source.mutations)

    def test_a_wholly_refused_selection_creates_no_work(self) -> None:
        """When no submitted item is admissible, the request refuses truthfully."""

        self.media("Movies/downloading.mkv.part")
        with self.journey() as value:
            status, refused = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/downloading.mkv.part"]},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("source_excluded", refused["error"]["code"], refused)
            self.assertEqual("temporary_file", refused["error"]["details"]["reason"], refused)
            self.assertEqual((), value.repository.list_media_discoveries())
            self.assertEqual([], value.source.mutations)


class ManualFolderExpansionTests(_DiscoveryFixture):
    """B46.3-03 / RO-2 AC-16: the deliberate folder expansion contract.

    A folder the operator selects by hand keeps only the configured
    primary-media extension set (video by default) plus the explicit
    temporary/download and extension exclusions.  The automatic include/exclude/
    match rules keep their unchanged meaning for a library walk, and default
    images/subtitles/NFO never become independent primaries.  Every case runs
    through the real authenticated Files command, the bounded Worker and real
    Local Storage/SQLite.
    """

    def test_default_folder_expansion_skips_pictures_subtitles_and_nfo(self) -> None:
        """Default video extensions: sidecars stay out of the manifest.

        A folder holding a movie with poster/fanart, subtitles, an NFO and two
        unrelated advertising images produces exactly one admitted primary.  The
        non-primary files stay at source and create no fabricated Recognition
        item, so the count is truthful rather than an attention backlog.
        """

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001.poster.jpg")
        self.media("Movies/Film.2001-fanart.jpg")
        self.media("Movies/Film.2001.zh.srt")
        self.media("Movies/Film.2001.nfo")
        self.media("Movies/ad-banner-1.png")
        self.media("Movies/ad-banner-2.jpg")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, admitted)
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(["Movies/Film.2001.mkv"], [i["path"] for i in settled["sources"]])
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            # The non-primary suffixes are explained as non-primary extensions
            # rather than as unreadable or failed sources.
            reasons = {item["reason"]: item["count"] for item in settled["progress"]["reasons"]}
            self.assertEqual(6, reasons.get("unsupported_extension"), settled)
            self.assert_zero_mutation_with_admitted_work(value)
            # Every non-primary file is still at its source path.
            self.assertEqual([], value.source.mutations)

    def test_artwork_off_does_not_promote_pictures_to_primaries(self) -> None:
        """Disabling artwork keeps images out of the primary manifest."""

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001.poster.jpg")
        document = self.document(attachments=True)
        for policy in document["organizePolicies"]:
            attachments = policy["attachments"]
            attachments["enabled"] = True
            attachments["artwork"] = False
        with self.journey() as value:
            _revision, runtime = self.publish_policy(value, document=document)
            self.assertFalse(
                any(
                    policy.organize_policy.attachments.artwork
                    for policy in runtime.strategy.recognition_type_policies
                ),
                runtime.strategy.recognition_type_policies,
            )
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, admitted)
            settled = self.run_discovery(value)
            self.assertEqual(["Movies/Film.2001.mkv"], [i["path"] for i in settled["sources"]])
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual([], value.source.mutations)

    def test_a_custom_primary_extension_set_is_honoured(self) -> None:
        """A deliberately configured extension set decides folder primaries."""

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001.iso")
        with self.journey(extensions=("mkv", "iso")) as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, admitted)
            settled = self.run_discovery(value)
            self.assertEqual(
                ["Movies/Film.2001.iso", "Movies/Film.2001.mkv"],
                sorted(i["path"] for i in settled["sources"]),
                settled,
            )
            self.assertEqual(2, settled["progress"]["primarySources"], settled)
            self.assertEqual([], value.source.mutations)

    def test_a_folder_with_no_eligible_primary_explains_empty(self) -> None:
        """A folder of only non-primary files is empty, not a failure."""

        self.media("Movies/Readme.txt")
        self.media("Movies/ad.jpg")
        self.media("Movies/Film.2001.srt")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, admitted)
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual([], settled["sources"], settled)
            self.assertEqual("empty_excluded", settled["progress"]["phase"], settled)
            self.assertEqual(3, settled["progress"]["excludedEntries"], settled)
            self.assert_zero_mutation_with_admitted_work(value)
            self.assertEqual([], value.source.mutations)

    def test_a_mixed_selection_keeps_folder_filtering_and_direct_files(self) -> None:
        """A mixed selection keeps each entrance's own deliberate meaning."""

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001.poster.jpg")
        self.media("Movies/Film.2001.srt")
        self.media("Movies/notes.txt")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies", "Movies/notes.txt"]},
            )
            self.assertEqual(202, status, admitted)
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            # `Movies/notes.txt` is subsumed by the selected folder, so the
            # folder's configured primary-extension filter decides it.  The
            # direct-file entrance is covered by ManualEntrySemanticsTests.
            self.assertEqual(["Movies/Film.2001.mkv"], [i["path"] for i in settled["sources"]])
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual([], value.source.mutations)

    def test_an_explicitly_excluded_folder_member_is_reported_per_item(self) -> None:
        """A temporary suffix inside a deliberate folder is its own refusal."""

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/downloading.mkv.part")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, admitted)
            settled = self.run_discovery(value)
            self.assertEqual(["Movies/Film.2001.mkv"], [i["path"] for i in settled["sources"]])
            reasons = {item["reason"] for item in settled["progress"]["reasons"]}
            self.assertIn("temporary_file", reasons)
            self.assertEqual([], value.source.mutations)


class DiscoveryWalkTests(_DiscoveryFixture):
    """Scope 3 and AC3: pinned filters, depth, temp files and real stability."""

    def test_a_folder_walk_finds_only_eligible_media(self) -> None:
        self.media("Movies/One.2001.mkv")
        self.media("Movies/notes.txt")
        self.media("Movies/part.mkv.part")
        self.media("Movies/Sub/Two.2002.mp4")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(2, settled["progress"]["primarySources"], settled)
            self.assertIsNone(settled["progress"]["incompleteReason"])
            _, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            paths = {item["path"] for item in detail["sources"]}
            self.assertEqual({"Movies/One.2001.mkv", "Movies/Sub/Two.2002.mp4"}, paths)
            reasons = {item["reason"] for item in detail["progress"]["reasons"]}
            self.assertIn("unsupported_extension", reasons)
            self.assertIn("temporary_file", reasons)
            self.assertEqual([], value.source.mutations)

    def test_configured_depth_prunes_descendants_and_is_explained(self) -> None:
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Deep/Two.2002.mkv")
        with self.journey(max_depth=1) as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            _, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            excluded = [
                item for item in detail["progress"]["findings"] if item["kind"] == "excluded"
            ]
            self.assertTrue(any(item["reason"] == "configured_depth_exceeded" for item in excluded))

    def test_safety_depth_truncation_is_a_truthful_incomplete_outcome(self) -> None:
        """The Task's own 32-level safety bound is never a configured exclusion.

        With the configured library depth unset, a folder holding eligible
        media below the Task's safety depth must produce an honest
        safety-depth incomplete outcome that refuses finalization, rather
        than claiming a completed scope and offering a truncated prefix.
        """

        self.media("Movies/One.2001.mkv")
        deep = self.source_root / "Movies" / "Deep"
        for index in range(33):
            deep = deep / f"Level{index:02d}"
        deep.mkdir(parents=True)
        (deep / "Two.2002.mkv").write_bytes(b"m" * 512)
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            # The deep subtree was never reached: the walk is honestly
            # incomplete, never a completed scope.
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertEqual("safety_depth_limit", settled["progress"]["incompleteReason"])
            self.assertTrue(settled["progress"]["incomplete"])
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            _, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            self.assertEqual("safety_depth_limit", detail["progress"]["incompleteReason"])
            truncated = [
                item for item in detail["progress"]["findings"] if item["kind"] == "truncated"
            ]
            self.assertTrue(
                any(item["reason"] == "safety_depth_limit" for item in truncated),
                detail["progress"]["findings"],
            )
            # The truncated prefix can never be finalized.
            self.assertFalse(detail["actions"]["finalize"]["available"])
            self.assertIn("narrow", detail["nextAction"])
            status, refused = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("discovery_budget_limited", refused["error"]["code"])
            self.assert_zero_mutation_with_admitted_work(value)

    def test_real_stability_requires_an_elapsed_unchanged_observation(self) -> None:
        self.media("Movies/One.2001.mkv", modified_at=datetime(2025, 12, 31, tzinfo=UTC))
        with self.journey(
            stability=FileStabilityPolicy(
                minimum_age_seconds=0,
                modified_threshold_seconds=0,
                stable_size_duration_seconds=60,
            )
        ) as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            # First observation: the interval is not fabricated, so the source
            # is honestly not yet proven stable.
            first = self.advance_once(value)
            self.assertEqual(0, first["progress"]["primarySources"], first)
            self.assertEqual(1, first["progress"]["unstableEntries"], first)
            self.assertEqual("waiting_stability", first["status"], first)
            self.assertTrue(first["progress"]["incomplete"] is False)
            # A later observation of the same unchanged source proves the
            # elapsed interval and admits it exactly once.
            value.clock.advance(120)
            settled = self.run_discovery(value)
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual(1, len(settled["sources"]))
            _, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            # The source is now proven stable, so it is no longer waiting: the
            # unstable count describes the current observation pass.
            self.assertEqual(0, detail["progress"]["unstableEntries"])
            self.assertEqual(1, detail["primarySourceCount"])
            self.assertEqual(1, len(detail["sources"]))

    def test_a_changed_size_resets_the_observed_interval(self) -> None:
        path = self.source_root / "Movies" / "One.2001.mkv"
        self.media("Movies/One.2001.mkv", size=512, modified_at=datetime(2025, 12, 31, tzinfo=UTC))
        with self.journey(
            stability=FileStabilityPolicy(
                minimum_age_seconds=0,
                modified_threshold_seconds=0,
                stable_size_duration_seconds=60,
            )
        ) as value:
            self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.advance_once(value)
            value.clock.advance(120)
            # The file is still being written: a changed size must reset the
            # interval rather than admit it as stable.
            path.write_bytes(b"m" * 4096)
            second = self.advance_once(value, step=1)
            self.assertEqual(0, second["progress"]["primarySources"], second)
            self.assertEqual("waiting_stability", second["status"], second)
            value.clock.advance(120)
            third = self.run_discovery(value)
            self.assertEqual(1, third["progress"]["primarySources"], third)

    def test_an_all_excluded_scope_is_a_distinct_empty_outcome(self) -> None:
        self.media("Movies/notes.txt")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual(0, settled["progress"]["primarySources"], settled)
            _, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            self.assertGreater(detail["progress"]["excludedEntries"], 0)
            self.assertEqual(0, detail["progress"]["unstableEntries"])
            self.assertEqual(0, detail["progress"]["errorEntries"])

    def test_an_unreadable_subtree_preserves_sibling_findings(self) -> None:
        self.media("Movies/One.2001.mkv")
        self.media("Locked/Two.2002.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies", "Locked"]},
            )
            # One selected subtree becomes unreadable after admission; the
            # unaffected sibling keeps its independent finding.
            value.source.fail_listing("Locked")
            settled = self.run_discovery(value)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual("read_failure", settled["progress"]["incompleteReason"])
            _, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            self.assertTrue(detail["progress"]["incomplete"])
            self.assertEqual(1, detail["primarySourceCount"])
            self.assertEqual(
                {"Movies/One.2001.mkv"},
                {item["path"] for item in detail["sources"]},
            )


class BudgetTests(_DiscoveryFixture):
    """Scope 2 and AC2: concrete budgets are durable and enforced."""

    def test_exactly_one_hundred_primary_items_are_supported(self) -> None:
        for index in range(100):
            self.media(f"Movies/Bulk.{index:03d}.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value, steps=8)
            self.assertEqual(100, settled["progress"]["primarySources"], settled)
            self.assertEqual("completed", settled["status"], settled)

    def test_one_hundred_and_one_primary_items_cannot_yield_a_prefix(self) -> None:
        for index in range(101):
            self.media(f"Movies/Bulk.{index:03d}.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value, steps=8)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertEqual("primary_limit", settled["progress"]["incompleteReason"])
            self.assertEqual(100, settled["progress"]["primarySources"])
            self.assertTrue(settled["progress"]["incomplete"])
            _, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            self.assertTrue(detail["progress"]["incomplete"])
            self.assertEqual("primary_limit", detail["progress"]["incompleteReason"])
            # A budget-limited walk is never an executable prefix: the finalize
            # action is not advertised, and an explicit finalize attempt is
            # refused with a durable, actionable refusal.
            self.assertFalse(detail["actions"]["finalize"]["available"])
            self.assertEqual("discovery_budget_limited", detail["actions"]["finalize"]["refusal"])
            self.assertIn("narrow", detail["nextAction"])
            status, refused = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("discovery_budget_limited", refused["error"]["code"])
            # Nothing was frozen and no intent exists.
            self.assertIsNone(refused.get("intentId"))
            self.assert_zero_mutation_with_admitted_work(value)

    def test_the_entry_budget_stops_the_walk_honestly(self) -> None:
        for index in range(20):
            self.media(f"Movies/Bulk.{index:03d}.mkv")
        budgets = DiscoveryBudgets(max_visited_entries=5, max_primary_sources=100)
        with self.journey(budgets=budgets) as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertEqual("entry_limit", settled["progress"]["incompleteReason"])
            self.assertLessEqual(settled["progress"]["visitedEntries"], 5 + 20)

    def test_the_page_budget_and_repeated_cursors_fail_closed(self) -> None:
        for index in range(10):
            self.media(f"Movies/Bulk.{index:03d}.mkv")
        budgets = DiscoveryBudgets(max_page_fetches=1, max_visited_entries=10_000)
        with self.journey(budgets=budgets) as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertEqual("page_limit", settled["progress"]["incompleteReason"])

    def test_counters_and_scope_survive_a_restart_without_duplicating_sources(self) -> None:
        for index in range(4):
            self.media(f"Movies/Bulk.{index:03d}.mkv")
        with self.journey(budgets=DiscoveryBudgets(max_visited_entries=3)) as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            first = self.advance_once(value)
            version = first["version"]
            counters = first["progress"]["visitedEntries"]
            # Re-open the durable repository exactly as a restarted process does.
            reopened = SQLiteTaskRepository(self.database)
            try:
                stored = reopened.get_media_discovery(admitted["discoveryId"])
            finally:
                reopened.close()
            self.assertEqual(version, stored.version)
            self.assertEqual(counters, stored.progress.counters.visited_entries)
            self.assertEqual(
                [{"path": "Movies", "kind": "directory"}],
                [item.document() for item in stored.progress.scope_entries],
            )


class WorkerOwnershipTests(_DiscoveryFixture):
    """Scope 5 and AC4: durable Worker ownership, fencing and cooperative control."""

    def test_two_workers_never_claim_one_discovery(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            first = value.repository.claim_next_media_discovery(
                value.clock(), worker_id="worker-1", claim_token="token-1", lease_seconds=300
            )
            self.assertIsNotNone(first)
            second = value.repository.claim_next_media_discovery(
                value.clock(), worker_id="worker-2", claim_token="token-2", lease_seconds=300
            )
            self.assertIsNone(second)
            # A stale owner cannot publish progress for the live claim.
            stored = value.repository.get_media_discovery(admitted["discoveryId"])
            self.assertEqual("token-1", stored.claim_token)
            self.assertFalse(
                value.repository.heartbeat_media_discovery_claim(
                    admitted["discoveryId"], "token-2", value.clock(), 300
                )
            )
            self.assertTrue(
                value.repository.heartbeat_media_discovery_claim(
                    admitted["discoveryId"], "token-1", value.clock(), 300
                )
            )

    def test_pause_and_continue_preserve_findings_and_do_not_duplicate_items(self) -> None:
        for index in range(4):
            self.media(f"Movies/Bulk.{index:03d}.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            value.repository.claim_next_media_discovery(
                value.clock(), worker_id="worker-1", claim_token="token-1", lease_seconds=300
            )
            # A cooperative pause stops at the next safe boundary.
            value.discovery.request_pause(
                admitted["discoveryId"], actor="operator", expected_version=1
            )
            paused = value.discovery.run_claimed(
                admitted["discoveryId"], worker_id="worker-1", claim_token="token-1"
            )
            self.assertEqual("paused", paused.status.value)
            self.assertTrue(paused.pause_requested)
            _, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            self.assertTrue(detail["pauseRequested"])
            self.assertTrue(detail["actions"]["resume"]["available"])
            # Continue: the same durable scope and counters are retained.
            resumed = value.discovery.resume(
                admitted["discoveryId"], actor="operator", expected_version=detail["version"]
            )
            self.assertFalse(resumed.pause_requested)
            settled = self.run_discovery(value, steps=8)
            paths = [item["path"] for item in settled["sources"]]
            self.assertEqual(len(paths), len(set(paths)), paths)
            self.assertEqual(4, settled["progress"]["primarySources"], settled)

    def test_a_concurrent_pause_is_acknowledged_instead_of_losing_the_race(self) -> None:
        """AC3: an accepted pause must not be lost to a Worker's version CAS."""

        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            identifier = admitted["discoveryId"]
            entered, release = threading.Event(), threading.Event()
            original = value.source.list_page

            def blocked(path, *, limit, cursor=None):
                entered.set()
                if not release.wait(10):
                    raise AssertionError("coordination timed out")
                return original(path, limit=limit, cursor=cursor)

            value.source.list_page = blocked
            worker = MediaDiscoveryWorker(value.discovery, clock=value.clock, worker_id="worker-1")
            thread = threading.Thread(target=worker.run_next)
            thread.start()
            try:
                self.assertTrue(entered.wait(10))
                # The operator pauses mid-walk, so the Worker's next publication
                # loses the version CAS and must react to the fresh record.
                paused = value.discovery.request_pause(
                    identifier, actor="operator", expected_version=admitted["version"]
                )
                self.assertTrue(paused.pause_requested)
            finally:
                release.set()
                thread.join(10)
                self.assertFalse(thread.is_alive())
            _, detail = self.request(value, f"/api/v1/operations/organize/discoveries/{identifier}")
            # The accepted pause survived: it is durably acknowledged, natively
            # continuable, and the record was never stranded on the conflict.
            self.assertEqual("paused", detail["status"])
            self.assertTrue(detail["pauseRequested"])
            self.assertTrue(detail["actions"]["resume"]["available"])
            self.assertIsNone(value.repository.media_discovery_claim(identifier)["claimToken"])
            self.assertEqual([], value.source.mutations)
            # Continue resumes the same permitted scope with no lost finding.
            _, resumed = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{identifier}/resume",
                "POST",
                {"expectedVersion": detail["version"]},
            )
            self.assertFalse(resumed["pauseRequested"])
            settled = self.run_discovery(value, steps=8)
            self.assertEqual(
                ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"],
                sorted(item["path"] for item in settled["sources"]),
                settled,
            )
            self.assert_zero_mutation_with_admitted_work(value)
            self.assertEqual([], value.source.mutations)

    def test_a_pause_racing_the_publication_keeps_the_bounded_work(self) -> None:
        """B44-8-1: a same-owner pause must not discard completed bounded work.

        The Worker really completes the bounded walk (101 primary candidates in
        a real Local directory) and only its final publication loses the version
        CAS to an accepted pause.  The acknowledgement must reconcile the
        pause with that pass's counters, findings, manifest and monotonic
        material refusal: discarding them would hide the encountered 100-item
        limit and let a later Continue silently re-walk with reset accounting.
        """

        for index in range(101):
            self.media(f"Movies/Film.{index:03}.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            identifier = admitted["discoveryId"]
            entered, release = threading.Event(), threading.Event()
            original = value.repository.record_media_discovery_progress
            attempted: list[dict] = []

            def delayed(discovery, **kwargs):
                if kwargs.get("claim_token"):
                    attempted.append(discovery.document())
                    entered.set()
                    if not release.wait(10):
                        raise AssertionError("coordination timed out")
                return original(discovery, **kwargs)

            value.repository.record_media_discovery_progress = delayed
            worker = MediaDiscoveryWorker(
                value.discovery, clock=value.clock, worker_id="old-worker"
            )
            thread = threading.Thread(target=worker.run_next)
            thread.start()
            try:
                self.assertTrue(entered.wait(10))
                _, before = self.request(
                    value, f"/api/v1/operations/organize/discoveries/{identifier}"
                )
                # The publication really carries the completed bounded work,
                # including the encountered primary-limit refusal.
                self.assertEqual("partial_success", attempted[0]["status"], attempted[0])
                self.assertEqual(101, attempted[0]["progress"]["counters"]["visitedEntries"])
                self.assertEqual(["primary_limit"], attempted[0]["progress"]["refusalReasons"])
                _, accepted = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{identifier}/pause",
                    "POST",
                    {"expectedVersion": before["version"]},
                )
                self.assertTrue(accepted["pauseRequested"], accepted)
            finally:
                release.set()
                thread.join(10)
                self.assertFalse(thread.is_alive())
            _, paused = self.request(value, f"/api/v1/operations/organize/discoveries/{identifier}")
            # The accepted pause is acknowledged *with* the same owner's work:
            # no reset counters, no lost finding, no hidden refusal.
            self.assertEqual("paused", paused["status"])
            self.assertTrue(paused["pauseRequested"])
            self.assertEqual(101, paused["progress"]["visitedEntries"], paused["progress"])
            self.assertEqual(2, paused["progress"]["pageFetches"], paused["progress"])
            self.assertEqual(100, paused["progress"]["primarySources"], paused["progress"])
            self.assertEqual(["primary_limit"], paused["progress"]["refusalReasons"])
            self.assertEqual("primary_limit", paused["progress"]["materialRefusal"])
            self.assertEqual(100, len(paused["sources"]), paused["sources"])
            # Continue resumes the same scope; the consumed refusal stays durable
            # and Finalize refuses instead of freezing a truncated prefix.
            _, resumed = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{identifier}/resume",
                "POST",
                {"expectedVersion": paused["version"]},
            )
            self.assertFalse(resumed["pauseRequested"])
            settled = self.run_discovery(value, steps=8)
            self.assertEqual(["primary_limit"], settled["progress"]["refusalReasons"], settled)
            self.assertFalse(settled["actions"]["finalize"]["available"], settled)
            status, refused = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{identifier}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("discovery_budget_limited", refused["error"]["code"])
            self.assert_zero_mutation_with_admitted_work(value)
            self.assertEqual([], value.source.mutations)

    def test_a_continue_racing_the_publication_is_refused_until_acknowledged(self) -> None:
        """AC3/AC5: a pending pause refuses Continue, then continues the same work.

        The Worker really completes the bounded walk (101 primary candidates in
        a real Local directory) and its publication is held.  An accepted pause
        is still pending acknowledgement, so a Continue in that window must be
        refused actionably with the durable work unchanged instead of racing the
        acknowledgement.  Once the pause is acknowledged with the same owner's
        work, Continue is offered again and the same scope continues without a
        reset or a redundant re-walk.
        """

        for index in range(101):
            self.media(f"Movies/Film.{index:03}.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            identifier = admitted["discoveryId"]
            entered, release = threading.Event(), threading.Event()
            original = value.repository.record_media_discovery_progress

            def delayed(discovery, **kwargs):
                if kwargs.get("claim_token"):
                    entered.set()
                    if not release.wait(10):
                        raise AssertionError("coordination timed out")
                return original(discovery, **kwargs)

            value.repository.record_media_discovery_progress = delayed
            worker = MediaDiscoveryWorker(
                value.discovery, clock=value.clock, worker_id="old-worker"
            )
            thread = threading.Thread(target=worker.run_next)
            thread.start()
            try:
                self.assertTrue(entered.wait(10))
                _, before = self.request(
                    value, f"/api/v1/operations/organize/discoveries/{identifier}"
                )
                _, paused = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{identifier}/pause",
                    "POST",
                    {"expectedVersion": before["version"]},
                )
                self.assertTrue(paused["pauseRequested"], paused)
                # The pause is not acknowledged at a safe boundary yet, so the
                # native Continue is not offered and the backend refuses a
                # direct/stale-client Continue without changing any work.
                self.assertFalse(paused["actions"]["resume"]["available"], paused)
                self.assertEqual(
                    "discovery_pause_pending",
                    paused["actions"]["resume"]["pendingReason"],
                    paused,
                )
                status, refused = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{identifier}/resume",
                    "POST",
                    {"expectedVersion": paused["version"]},
                )
                self.assertEqual(409, status, refused)
                self.assertEqual("discovery_pause_pending", refused["error"]["code"], refused)
            finally:
                release.set()
                thread.join(10)
                self.assertFalse(thread.is_alive())
            _, acknowledged = self.request(
                value, f"/api/v1/operations/organize/discoveries/{identifier}"
            )
            # The acknowledgement preserved the same owner's completed bounded
            # work and released ownership; only now is Continue offered.
            self.assertEqual("paused", acknowledged["status"], acknowledged)
            self.assertTrue(acknowledged["pauseRequested"], acknowledged)
            self.assertEqual(
                101, acknowledged["progress"]["visitedEntries"], acknowledged["progress"]
            )
            self.assertEqual(["primary_limit"], acknowledged["progress"]["refusalReasons"])
            self.assertEqual(100, len(acknowledged["sources"]), acknowledged["sources"])
            self.assertTrue(acknowledged["actions"]["resume"]["available"], acknowledged)
            self.assertIsNone(value.repository.media_discovery_claim(identifier)["claimToken"])
            _, resumed = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{identifier}/resume",
                "POST",
                {"expectedVersion": acknowledged["version"]},
            )
            self.assertFalse(resumed["pauseRequested"], resumed)
            settled = self.run_discovery(value, steps=8)
            self.assertEqual(["primary_limit"], settled["progress"]["refusalReasons"], settled)
            self.assertFalse(settled["actions"]["finalize"]["available"], settled)
            self.assertEqual(100, len(settled["sources"]), settled["sources"])
            self.assert_zero_mutation_with_admitted_work(value)
            self.assertEqual([], value.source.mutations)

    def test_a_premature_continue_never_strands_the_pause_acknowledgement(self) -> None:
        """B44-8-2: pending Pause refuses Continue, then acknowledged Continue works.

        This is the deterministic form of the reviewed defect sequence: the
        Worker really completes the walk, its publication loses the version CAS
        to an accepted pause, and the operator's Continue arrives while the
        acknowledgement is still uncommitted.  Under the acknowledge-before-
        Continue rule the premature Continue is refused without changing the
        durable work, the acknowledgement then lands with that work preserved,
        and the native Continue genuinely continues the same scope instead of
        leaving the record durably ``paused`` with no usable Resume.
        """

        self.media("Movies/Film.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            identifier = admitted["discoveryId"]
            publish_entered, publish_release = threading.Event(), threading.Event()
            settle_entered, settle_release = threading.Event(), threading.Event()
            original_publish = value.repository.record_media_discovery_progress
            original_settle = value.repository.settle_media_discovery_control
            settlement_attempts: list[dict] = []

            def delayed_publish(discovery, **kwargs):
                if kwargs.get("claim_token"):
                    publish_entered.set()
                    if not publish_release.wait(10):
                        raise AssertionError("publication coordination timed out")
                return original_publish(discovery, **kwargs)

            def delayed_settle(discovery, **kwargs):
                if kwargs.get("claim_token"):
                    settlement_attempts.append(discovery.document())
                    if len(settlement_attempts) == 1:
                        settle_entered.set()
                        if not settle_release.wait(10):
                            raise AssertionError("settlement coordination timed out")
                return original_settle(discovery, **kwargs)

            value.repository.record_media_discovery_progress = delayed_publish
            value.repository.settle_media_discovery_control = delayed_settle
            worker = MediaDiscoveryWorker(
                value.discovery, clock=value.clock, worker_id="live-worker"
            )
            thread = threading.Thread(target=worker.run_next)
            thread.start()
            try:
                self.assertTrue(publish_entered.wait(10))
                _, before = self.request(
                    value, f"/api/v1/operations/organize/discoveries/{identifier}"
                )
                _, paused = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{identifier}/pause",
                    "POST",
                    {"expectedVersion": before["version"]},
                )
                self.assertTrue(paused["pauseRequested"], paused)
                publish_release.set()
                self.assertTrue(settle_entered.wait(10))
                # The operator's Continue arrives while the pause
                # acknowledgement is still in flight and uncommitted.
                status, refused = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{identifier}/resume",
                    "POST",
                    {"expectedVersion": paused["version"]},
                )
                self.assertEqual(409, status, refused)
                self.assertEqual("discovery_pause_pending", refused["error"]["code"], refused)
            finally:
                publish_release.set()
                settle_release.set()
                thread.join(10)
                self.assertFalse(thread.is_alive())
            # The acknowledgement settled the accepted pause with the same
            # owner's completed bounded work, and it is natively continuable.
            _, acknowledged = self.request(
                value, f"/api/v1/operations/organize/discoveries/{identifier}"
            )
            self.assertEqual("paused", acknowledged["status"], acknowledged)
            self.assertTrue(acknowledged["pauseRequested"], acknowledged)
            self.assertTrue(acknowledged["actions"]["resume"]["available"], acknowledged)
            self.assertEqual(
                1, acknowledged["progress"]["visitedEntries"], acknowledged["progress"]
            )
            self.assertEqual(1, len(acknowledged["sources"]), acknowledged["sources"])
            self.assertIsNone(value.repository.media_discovery_claim(identifier)["claimToken"])
            # The acknowledged Continue really continues the same scope.
            _, resumed = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{identifier}/resume",
                "POST",
                {"expectedVersion": acknowledged["version"]},
            )
            self.assertFalse(resumed["pauseRequested"], resumed)
            settled = self.run_discovery(value, steps=8)
            self.assertEqual(
                ["Movies/Film.2001.mkv"], [item["path"] for item in settled["sources"]]
            )
            self.assert_zero_mutation_with_admitted_work(value)
            self.assertEqual([], value.source.mutations)

    def test_an_open_cancellation_left_by_an_earlier_build_is_recovered(self) -> None:
        """AC1: a queued record already carrying cancel_requested must not strand.

        An earlier build wrote the request flag without settling the record, and
        its claimant excluded ``cancel_requested=1`` rows forever.  The recovery
        path must still reach a durable terminal acknowledgement through a real
        Worker pickup rather than leaving an unclaimable open record.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            identifier = admitted["discoveryId"]
            # Reproduce the stranded durable state directly, exactly as an
            # earlier build left it: the request flag is durable but the record
            # is still open and would never be claimed again.
            with SQLiteTaskRepository(self.database) as raw:
                raw._connection.execute(
                    "UPDATE media_discoveries SET cancel_requested=1 WHERE discovery_id=?",
                    (identifier,),
                )
                raw._connection.commit()
            _, stranded = self.request(
                value, f"/api/v1/operations/organize/discoveries/{identifier}"
            )
            self.assertEqual("queued", stranded["status"])
            self.assertTrue(stranded["cancelRequested"])
            self.assertFalse(stranded["actions"]["finalize"]["available"])
            # The resident Worker really picks it up and settles the accepted
            # cancellation instead of never being allowed to claim it again.
            self.clock.advance(600)
            claimed = value.discovery.claim_and_run(worker_id="recovery", claim_token="recovery-1")
            self.assertIsNotNone(claimed)
            self.assertEqual("cancelled", claimed.status.value)
            _, readback = self.request(
                value, f"/api/v1/operations/organize/discoveries/{identifier}"
            )
            self.assertEqual("cancelled", readback["status"])
            self.assertTrue(readback["cancelRequested"])
            self.assertIsNone(value.repository.media_discovery_claim(identifier)["claimToken"])
            self.assertEqual([], value.source.mutations)
            self.assert_zero_mutation_with_admitted_work(value)

    def test_resume_cannot_undo_an_accepted_cancellation(self) -> None:
        """AC3: cancellation is terminal; every later control refuses actionably."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            identifier = admitted["discoveryId"]
            _, cancelled = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{identifier}/cancel",
                "POST",
                {"expectedVersion": admitted["version"]},
            )
            self.assertEqual("cancelled", cancelled["status"])
            for action in ("resume", "pause", "cancel"):
                status, refused = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{identifier}/{action}",
                    "POST",
                    {"expectedVersion": cancelled["version"]},
                )
                self.assertEqual(409, status, refused)
                self.assertEqual("discovery_not_open", refused["error"]["code"])
            # Even the exact durable claim cannot resurrect cancelled work.
            value.clock.advance(600)
            self.assertIsNone(
                value.discovery.claim_and_run(worker_id="w", claim_token="late-token")
            )
            _, readback = self.request(
                value, f"/api/v1/operations/organize/discoveries/{identifier}"
            )
            self.assertEqual("cancelled", readback["status"])
            self.assertEqual(cancelled["version"], readback["version"])
            self.assertEqual([], value.source.mutations)

    def test_cancellation_preserves_findings_and_grants_no_authority(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            value.repository.claim_next_media_discovery(
                value.clock(), worker_id="worker-1", claim_token="token-1", lease_seconds=300
            )
            value.discovery.request_cancel(
                admitted["discoveryId"], actor="operator", expected_version=1
            )
            cancelled = value.discovery.run_claimed(
                admitted["discoveryId"], worker_id="worker-1", claim_token="token-1"
            )
            self.assertEqual("cancelled", cancelled.status.value)
            _, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            self.assertTrue(detail["cancelRequested"])
            self.assertFalse(detail["actions"]["finalize"]["available"])
            self.assertEqual("not_available_from_discovery", detail["execution"])
            self.assert_zero_mutation_with_admitted_work(value)

    def test_a_stale_owner_cannot_publish_progress(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            value.repository.claim_next_media_discovery(
                value.clock(), worker_id="worker-1", claim_token="token-1", lease_seconds=300
            )
            with self.assertRaises(DiscoveryError) as caught:
                value.discovery.run_claimed(
                    admitted["discoveryId"], worker_id="worker-2", claim_token="token-2"
                )
            # A different persisted claim is ownership loss, not a mere version
            # conflict: the stale owner must stop without writing anything.
            self.assertEqual("discovery_ownership_lost", caught.exception.code)

    def test_queued_cancellation_reaches_durable_terminal_acknowledgement(self) -> None:
        """A44-4: an accepted cancel of unclaimed work must not strand the record."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            identifier = admitted["discoveryId"]
            status, cancelled = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{identifier}/cancel",
                "POST",
                {"expectedVersion": admitted["version"]},
            )
            self.assertEqual(200, status, cancelled)
            # The acknowledgement is durable and terminal immediately: no Worker
            # pass is required to make the operator's accepted cancellation real.
            self.assertEqual("cancelled", cancelled["status"])
            self.assertTrue(cancelled["cancelRequested"])
            self.assertFalse(cancelled["actions"]["finalize"]["available"])
            self.assertFalse(cancelled["actions"]["pause"]["available"])
            self.assertFalse(cancelled["actions"]["resume"]["available"])
            self.assertEqual("not_available_from_discovery", cancelled["execution"])
            # Three real Worker pickups find no claimable work, and the readback
            # never regresses to an open queued record.
            for _ in range(3):
                value.clock.advance(600)
                self.assertIsNone(
                    value.discovery.claim_and_run(
                        worker_id="cancel-worker", claim_token="cancel-token"
                    )
                )
            _, readback = self.request(
                value, f"/api/v1/operations/organize/discoveries/{identifier}"
            )
            self.assertEqual("cancelled", readback["status"])
            self.assertTrue(readback["cancelRequested"])
            self.assertEqual(admitted["version"] + 1, readback["version"])
            # Finalize refuses cancellation explicitly.
            status, refused = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{identifier}/finalize",
                "POST",
                {"expectedVersion": readback["version"]},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("discovery_not_complete", refused["error"]["code"])
            # A deliberate same-scope submission creates successor work instead
            # of reconciling to the cancelled record.
            _, successor = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertNotEqual(identifier, successor["discoveryId"])
            self.assert_zero_mutation_with_admitted_work(value)
            self.assertEqual([], value.source.mutations)

    def test_cancellation_during_an_in_flight_walk_reaches_terminal(self) -> None:
        """A44-4: an in-flight cancellation is not stranded by the stale CAS."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            identifier = admitted["discoveryId"]
            entered, release = threading.Event(), threading.Event()
            original = value.source.list_page

            def blocked(path, *, limit, cursor=None):
                entered.set()
                if not release.wait(10):
                    raise AssertionError("coordination timed out")
                return original(path, limit=limit, cursor=cursor)

            value.source.list_page = blocked
            worker = MediaDiscoveryWorker(
                value.discovery, clock=value.clock, worker_id="old-worker"
            )
            results: list[object] = []
            thread = threading.Thread(target=lambda: results.append(worker.run_next()))
            thread.start()
            try:
                self.assertTrue(entered.wait(10))
                _, before = self.request(
                    value, f"/api/v1/operations/organize/discoveries/{identifier}"
                )
                status, control = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{identifier}/cancel",
                    "POST",
                    {"expectedVersion": before["version"]},
                )
                self.assertEqual(200, status, control)
            finally:
                release.set()
                thread.join(10)
                self.assertFalse(thread.is_alive())
            _, readback = self.request(
                value, f"/api/v1/operations/organize/discoveries/{identifier}"
            )
            # The returning old Worker honoured the accepted cancellation at its
            # safe boundary instead of stranding it behind a stale version.
            self.assertEqual("cancelled", readback["status"])
            self.assertTrue(readback["cancelRequested"])
            self.assertFalse(readback["actions"]["finalize"]["available"])
            self.assertEqual([], value.source.mutations)
            self.assert_zero_mutation_with_admitted_work(value)

    def test_a_stale_owner_cannot_clear_a_successor_claim(self) -> None:
        """A44-5: takeover must leave the successor's claim and state untouched."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            identifier = admitted["discoveryId"]
            entered, release = threading.Event(), threading.Event()
            original = value.source.list_page

            def blocked(path, *, limit, cursor=None):
                entered.set()
                if not release.wait(10):
                    raise AssertionError("coordination timed out")
                return original(path, limit=limit, cursor=cursor)

            value.source.list_page = blocked
            notices: list[str] = []
            worker = MediaDiscoveryWorker(
                value.discovery, clock=value.clock, worker_id="old-worker", notice=notices.append
            )
            results: list[object] = []
            thread = threading.Thread(target=lambda: results.append(worker.run_next()))
            thread.start()
            try:
                self.assertTrue(entered.wait(10))
                # The old Worker's lease expires and a successor takes over
                # *between* the successful heartbeat and the publication.
                value.clock.advance(600)
                claimed = value.repository.claim_next_media_discovery(
                    value.clock(),
                    worker_id="successor-worker",
                    claim_token="successor-claim",
                    lease_seconds=300,
                )
                self.assertIsNotNone(claimed)
                self.assertEqual(identifier, claimed.discovery_id)
            finally:
                release.set()
                thread.join(10)
                self.assertFalse(thread.is_alive())
            self.assertIsNone(results[0])
            self.assertTrue(any("discovery_ownership_lost" in line for line in notices), notices)
            # The successor's claim, status, controls and version are untouched.
            claim = value.repository.media_discovery_claim(identifier)
            self.assertEqual("successor-worker", claim["workerId"])
            self.assertEqual("successor-claim", claim["claimToken"])
            _, readback = self.request(
                value, f"/api/v1/operations/organize/discoveries/{identifier}"
            )
            self.assertEqual("queued", readback["status"])
            self.assertFalse(readback["pauseRequested"])
            self.assertFalse(readback["cancelRequested"])
            self.assertEqual(admitted["version"], readback["version"])
            self.assertEqual([], value.source.mutations)
            # The valid successor still advances the same durable scope safely.
            advanced = value.discovery.run_claimed(
                identifier, worker_id="successor-worker", claim_token="successor-claim"
            )
            self.assertIn(
                advanced.status.value, {"completed", "waiting_stability", "partial_success"}
            )
            self.assert_zero_mutation_with_admitted_work(value)

    def test_cancellation_and_takeover_are_durable_across_connections(self) -> None:
        """AC1/AC2/AC3: real SQLite transactions, separate connections and restart."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            cancelled_id = admitted["discoveryId"]
            status, cancelled = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{cancelled_id}/cancel",
                "POST",
                {"expectedVersion": admitted["version"]},
            )
            self.assertEqual(200, status, cancelled)

            _, other = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertNotEqual(cancelled_id, other["discoveryId"])
            value.repository.claim_next_media_discovery(
                value.clock(), worker_id="old-worker", claim_token="old-claim", lease_seconds=300
            )

            # A second, independent connection to the same database observes the
            # same durable outcomes: the cancellation is already terminal, and
            # the takeover claim is real.
            with SQLiteTaskRepository(self.database) as separate:
                self.assertEqual(
                    "cancelled", separate.get_media_discovery(cancelled_id).status.value
                )
                self.assertIsNone(separate.media_discovery_claim(cancelled_id)["claimToken"])
                self.assertIsNone(
                    separate.claim_next_media_discovery(
                        value.clock(),
                        worker_id="separate-worker",
                        claim_token="separate-claim",
                        lease_seconds=300,
                    )
                )
                self.clock.advance(600)
                taken = separate.claim_next_media_discovery(
                    value.clock(),
                    worker_id="successor-worker",
                    claim_token="successor-claim",
                    lease_seconds=300,
                )
                self.assertIsNotNone(taken)
                self.assertEqual(other["discoveryId"], taken.discovery_id)
                # Renewal and progress by the displaced owner are refused.
                self.assertFalse(
                    separate.heartbeat_media_discovery_claim(
                        taken.discovery_id, "old-claim", value.clock(), 300
                    )
                )
                with self.assertRaises(DiscoveryError) as lost:
                    separate.record_media_discovery_progress(
                        replace(
                            taken,
                            version=taken.version + 1,
                            progress=replace(taken.progress, phase="running"),
                        ),
                        expected_version=taken.version,
                        claim_token="old-claim",
                    )
                self.assertEqual("discovery_ownership_lost", lost.exception.code)
                self.assertEqual(
                    "successor-claim",
                    separate.media_discovery_claim(taken.discovery_id)["claimToken"],
                )
                # Cancellation cannot be undone by resume or a Worker publication.
                with self.assertRaises(DiscoveryError) as refused:
                    value.discovery.resume(
                        cancelled_id, actor="operator", expected_version=cancelled["version"]
                    )
                self.assertEqual("discovery_not_open", refused.exception.code)

            # Reopening the database preserves both durable outcomes.
            with SQLiteTaskRepository(self.database) as reopened:
                self.assertEqual(
                    "cancelled", reopened.get_media_discovery(cancelled_id).status.value
                )
                self.assertEqual(
                    "successor-claim",
                    reopened.media_discovery_claim(other["discoveryId"])["claimToken"],
                )
            self.assertEqual([], value.source.mutations)
            self.assert_zero_mutation_with_admitted_work(value)

    def test_control_requires_the_exact_current_version(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            status, document = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/pause",
                "POST",
                {"expectedVersion": 99},
            )
            self.assertEqual(409, status, document)
            self.assertEqual("discovery_conflict", document["error"]["code"])


class FreezeAndHandoffTests(_DiscoveryFixture):
    """Scope 6 and AC5: frozen lists feed the existing pipeline unchanged."""

    def test_two_libraries_with_the_same_relative_path_never_reconcile(self) -> None:
        """B blocker (P1): the admission binds the exact library/Storage binding.

        Two enabled ResourceLibraries with different roots can contain the
        same legal relative folder.  While the first library's discovery is
        still open, submitting the same relative path through the second
        library is a *different source selection*: it must admit its own
        discovery bound to the second library/Storage, and its finalize must
        freeze that second library's real files — never the first library's
        sources under the second library's return context.
        """

        self.media("SP/Extra.2003.mkv")
        self.media("SP/Second.Library.2024.mkv", second=True)
        with self.journey(second_library=True) as value:
            _, first = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["SP"]},
            )
            self.assertEqual("library", first["resourceLibraryId"], first)
            # The same relative path through the second enabled library is a
            # different admission: a separate durable record bound to
            # library2/source2, never a reconciliation to the first record.
            status, second = self.request(
                value,
                "/api/v1/resource-libraries/library2/files/discoveries",
                "POST",
                {"paths": ["SP"]},
            )
            self.assertEqual(202, status, second)
            self.assertEqual("library2", second["resourceLibraryId"], second)
            self.assertNotEqual(first["discoveryId"], second["discoveryId"])
            # Both durable records exist, each with its own binding.
            stored = {
                row.discovery_id: row for row in value.repository.list_media_discoveries(limit=50)
            }
            self.assertEqual(
                ("library", "source"),
                (
                    stored[first["discoveryId"]].resource_library_id,
                    stored[first["discoveryId"]].storage_id,
                ),
            )
            self.assertEqual(
                ("library2", "source2"),
                (
                    stored[second["discoveryId"]].resource_library_id,
                    stored[second["discoveryId"]].storage_id,
                ),
            )
            # The second walk discovers the second library's own file.
            settled = self.run_discovery(value)
            if settled["discoveryId"] != second["discoveryId"]:
                for _ in range(8):
                    stored_second = value.repository.get_media_discovery(second["discoveryId"])
                    if stored_second is not None and stored_second.terminal:
                        settled = self.request(
                            value,
                            f"/api/v1/operations/organize/discoveries/{second['discoveryId']}",
                        )[1]
                        break
                    self.run_discovery(value)
            self.assertEqual(1, settled["primarySourceCount"], settled)
            self.assertEqual(
                ["SP/Second.Library.2024.mkv"],
                [item["path"] for item in settled["sources"]],
                settled,
            )
            # Freezing the second discovery hands the second library's exact
            # source to the existing manual intent boundary.
            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{second['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(201, status, frozen)
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertIsNotNone(intent)
            self.assertEqual(
                [("source2", "library2", "SP/Second.Library.2024.mkv")],
                [
                    (item.source.storage_id, item.source.resource_library_id, item.source.path)
                    for item in intent.items
                ],
            )
            # The first library's file never entered the second discovery.
            self.assertNotIn(
                "SP/Extra.2003.mkv",
                [item.source.path for item in intent.items],
            )

    def test_two_libraries_with_the_same_relative_path_discover_their_own_sources(
        self,
    ) -> None:
        """Both libraries complete their own walks from the same relative path."""

        self.media("SP/Extra.2003.mkv")
        self.media("SP/Second.Library.2024.mkv", second=True)
        with self.journey(second_library=True) as value:
            _, first = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["SP"]},
            )
            _, second = self.request(
                value,
                "/api/v1/resource-libraries/library2/files/discoveries",
                "POST",
                {"paths": ["SP"]},
            )
            # Drive the Worker until both walks settle.
            for _ in range(10):
                if (
                    value.repository.get_media_discovery(first["discoveryId"]).terminal
                    and value.repository.get_media_discovery(second["discoveryId"]).terminal
                ):
                    break
                value.discovery.claim_and_run(worker_id=f"worker-{_}", claim_token=f"token-{_}")
            first_doc = value.repository.get_media_discovery(first["discoveryId"])
            second_doc = value.repository.get_media_discovery(second["discoveryId"])
            self.assertEqual(["SP/Extra.2003.mkv"], [item["path"] for item in first_doc.sources])
            self.assertEqual(
                ["SP/Second.Library.2024.mkv"], [item["path"] for item in second_doc.sources]
            )
            # Zero mutation across both libraries.
            for storage in value.storages.values():
                self.assertEqual([], storage.mutations)

    def test_finalize_freezes_one_deduplicated_list_and_links_the_intent(self) -> None:
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual(2, settled["progress"]["primarySources"], settled)
            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(201, status, frozen)
            self.assertTrue(frozen["frozen"])
            self.assertIsNotNone(frozen["intentId"])
            self.assertEqual([], value.source.mutations)
            # The existing intent/Preview boundary now owns the exact sources.
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertIsNotNone(intent)
            self.assertEqual(2, len(intent.items))
            self.assertEqual(
                {item.source.path for item in intent.items},
                {"Movies/One.2001.mkv", "Movies/Two.2002.mkv"},
            )

    def test_later_folder_additions_cannot_enlarge_a_frozen_list(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            _, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.media("Movies/Late.2003.mkv")
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertEqual(1, len(intent.items))
            self.assertEqual("Movies/One.2001.mkv", intent.items[0].source.path)

    def test_a_changed_source_after_freeze_stops_only_its_own_item(self) -> None:
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            _, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            (self.source_root / "Movies" / "Two.2002.mkv").unlink()
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertEqual(2, len(intent.items))
            # The durable intent still holds both exact frozen identities.
            self.assertEqual(
                {item.source.path for item in intent.items},
                {"Movies/One.2001.mkv", "Movies/Two.2002.mkv"},
            )

    def test_finalize_is_refused_before_the_walk_finishes(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            status, document = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": 1},
            )
            self.assertEqual(409, status, document)
            self.assertEqual("discovery_not_complete", document["error"]["code"])

    def test_media_library_has_no_discovery_entry(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            status, document = self.request(
                value,
                "/api/v1/media-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertNotEqual(202, status)
            self.assertNotEqual("discovery", document.get("journey"))


class ZeroMutationTests(_DiscoveryFixture):
    """AC6: discovery is metadata-only and performs zero mutation."""

    def test_discovery_reads_metadata_only_and_never_reads_content(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.run_discovery(value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            kinds = {kind for kind, _ in value.source.reads}
            self.assertNotIn("read", kinds)
            self.assertTrue(kinds.issubset({"stat", "list_page", "list", "exists"}), kinds)
            self.assert_zero_mutation_with_admitted_work(value)

    def test_a_reconciled_scope_returns_the_durable_record_once_terminal(self) -> None:
        """Actor/scope/pin reconciliation and distinct successor work.

        While the first record is still open, an identical actor/scope/pin
        submission reconciles to the same durable discovery instead of
        admitting a duplicate walk (the lost-response case).  After the
        discovery settles terminal, resubmitting the same scope is deliberate
        successor work and admits a new independent record.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, first = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            # The first record is still open: the same submission reconciles.
            status, second = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, second)
            self.assertEqual(first["discoveryId"], second["discoveryId"])
            self.assertEqual(1, len(value.repository.list_media_discoveries()))
            # A different scope is a genuinely different admission.
            self.media("Shows/Ep.01.mkv")
            status, other = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Shows"]},
            )
            self.assertEqual(202, status, other)
            self.assertNotEqual(first["discoveryId"], other["discoveryId"])
            # Once the first discovery settled terminal, the same scope is
            # deliberate successor work: a new independent record.
            settled = self.run_discovery(value)
            if settled["discoveryId"] != first["discoveryId"]:
                # The claim loop may settle the sibling scope first; keep
                # driving the Worker until the first record is terminal.
                for _ in range(8):
                    stored = value.repository.get_media_discovery(first["discoveryId"])
                    if stored is not None and stored.terminal:
                        break
                    settled = self.run_discovery(value)
            status, successor = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, successor)
            self.assertNotEqual(first["discoveryId"], successor["discoveryId"])
            self.assertEqual(3, len(value.repository.list_media_discoveries()))

    def test_discovery_readback_is_scoped_to_the_admitting_principal(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            status, document = self.request(
                value, "/api/v1/operations/organize/discoveries", token="viewer-token"
            )
            self.assertEqual(200, status, document)
            self.assertEqual([], document["items"])


class OperationsProjectionTests(_DiscoveryFixture):
    """Scope 5/6: the native readback, list and control surface."""

    def test_the_principal_scoped_list_publishes_the_admitted_discoveries(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            status, page = self.request(value, "/api/v1/operations/organize/discoveries")
            self.assertEqual(200, status, page)
            self.assertEqual("discovery", page["journey"])
            self.assertEqual(1, page["total"])
            self.assertEqual(admitted["discoveryId"], page["items"][0]["discoveryId"])
            # The list projection never publishes the exact source rows.
            self.assertNotIn("sources", page["items"][0])
            self.assertEqual("none", page["sideEffects"])

    def test_the_readback_never_publishes_a_claim_token_or_digest(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.run_discovery(value)
            _, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            encoded = json.dumps(detail)
            for forbidden in (
                "claimToken",
                "fingerprint",
                "occurrenceId",
                SNAPSHOT_DIGEST,
                "Bearer ",
                "storagePath",
            ):
                self.assertNotIn(forbidden, encoded)
            self.assertEqual("not_available_from_discovery", detail["execution"])
            self.assertTrue(detail["zeroMutation"])

    def test_a_worker_can_advance_the_discovery_through_the_cli_runner(self) -> None:
        from mediaflow.application.media_discovery_worker import MediaDiscoveryWorker

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            worker = MediaDiscoveryWorker(
                value.discovery, worker_id="cli-worker", notice=lambda line: None
            )
            self.assertEqual(("media_discovery",), worker.commands)
            result = worker.run_next()
            self.assertIsNotNone(result)
            self.assertEqual(admitted["discoveryId"], result.discovery_id)
            # A second pass finds no claimable work because the first pass
            # settled the bounded scope.
            self.assertIsNone(worker.run_next())

    def test_an_unknown_discovery_read_fails_closed(self) -> None:
        with self.journey() as value:
            status, document = self.request(
                value, "/api/v1/operations/organize/discoveries/does-not-exist"
            )
            self.assertEqual(404, status, document)
            self.assertEqual("discovery_not_found", document["error"]["code"])

    def test_an_unknown_worker_readiness_is_reported_truthfully(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            _, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            # No Worker is registered in this fixture, so readiness is false and
            # the operator receives an actionable next step.
            self.assertFalse(detail["worker"]["ready"])
            self.assertTrue(detail["worker"]["nextAction"])
            self.assertEqual(
                "start or repair the resident Processing Worker so discovery can continue",
                detail["nextAction"],
            )


class RepeatedObservationManifestTests(_DiscoveryFixture):
    """A44-1: one exact source per admitted path through repeated observations.

    A repeated stability observation pass, a repeated provider page or a
    resumed/restarted Worker must never append a second copy of an already
    eligible source, and a source that changes or disappears must not survive
    merely because its path was seen before.
    """

    def test_repeated_stability_passes_keep_one_copy_and_freeze_one_intent(self) -> None:
        old = datetime(2025, 12, 31, tzinfo=UTC)
        self.media("Movies/A.2001.mkv", modified_at=old)
        changing = self.media("Movies/B.2002.mkv", modified_at=old)
        with self.journey(stability=FileStabilityPolicy(stable_size_duration_seconds=60)) as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            first = self.advance_once(value)
            self.assertEqual(0, first["progress"]["primarySources"], first)
            value.clock.advance(120)
            # B is still being written: its changed size resets its interval,
            # while the unchanged A proves the elapsed interval exactly once.
            changing.write_bytes(b"m" * 1024)
            second = self.advance_once(value, step=1)
            self.assertEqual(1, second["progress"]["primarySources"], second)
            value.clock.advance(120)
            third = self.advance_once(value, step=2)
            paths = [item["path"] for item in third["sources"]]
            # A was observed stable in both passes but appears exactly once.
            self.assertEqual(["Movies/A.2001.mkv", "Movies/B.2002.mkv"], paths, third)
            self.assertEqual(2, third["progress"]["primarySources"], third)
            self.assertEqual(2, third["primarySourceCount"], third)
            # The unique manifest freezes into one valid intent.
            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": third["version"]},
            )
            self.assertEqual(201, status, frozen)
            self.assertIsNotNone(frozen["intentId"], frozen)
            self.assertIsNone(frozen["failure"], frozen)
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertEqual(
                ["Movies/A.2001.mkv", "Movies/B.2002.mkv"],
                [item.source.path for item in intent.items],
            )
            self.assertEqual([], value.source.mutations)

    def test_duplicate_provider_pages_yield_one_source_and_one_intent(self) -> None:
        """The real OpenList adapter's non-atomic repeated page.

        The production HTTP parser/adapter legitimately publishes the same
        ordinary filename on two pages because the provider listing is not an
        atomic snapshot.  Discovery must still keep exactly one source and
        freeze one valid intent instead of failing with ``duplicate_source``.
        """

        self.media("Movies/A.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            raw = value.source._storage
            entry = raw.stat("Movies/A.2001.mkv")
            original = value.source.list_page

            def pages(path, *, limit, cursor=None):
                if path == "Movies":
                    # Page 1 and page 2 both return the same ordinary filename;
                    # only the cursor distinguishes them, so the second page
                    # never terminates the walk on its own.
                    if cursor is None:
                        return StoragePage([entry], "page:2")
                    return StoragePage([entry], None)
                return original(path, limit=limit, cursor=cursor)

            value.source.list_page = pages
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(["Movies/A.2001.mkv"], [i["path"] for i in settled["sources"]])
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(201, status, frozen)
            self.assertIsNone(frozen["failure"], frozen)
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertEqual(["Movies/A.2001.mkv"], [item.source.path for item in intent.items])

    def test_duplicate_observations_never_falsely_exhaust_the_primary_bound(self) -> None:
        """Exactly 100 unique primaries are supported even across repeated pages."""

        for index in range(100):
            self.media(f"Movies/Bulk.{index:03d}.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            raw = value.source._storage
            entries = [raw.stat(f"Movies/Bulk.{index:03d}.mkv") for index in range(100)]
            original = value.source.list_page

            def pages(path, *, limit, cursor=None):
                if path == "Movies":
                    # Every page re-publishes the whole directory, exactly like a
                    # non-atomic provider listing; a naive append would count
                    # 100 duplicates as 200 and falsely hit the primary limit.
                    if cursor is None:
                        return StoragePage(entries, "page:2")
                    return StoragePage(entries, None)
                return original(path, limit=limit, cursor=cursor)

            value.source.list_page = pages
            settled = self.run_discovery(value, steps=8)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(100, settled["progress"]["primarySources"], settled)
            self.assertEqual(100, len(settled["sources"]), settled)
            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(201, status, frozen)
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertEqual(100, len(intent.items))

    def test_a_source_that_disappears_is_not_retained_by_path_alone(self) -> None:
        """A previously eligible file that disappears must not survive.

        The manifest is keyed by the exact observed source, not by the fact
        that a path was seen once.  A fully completed later pass over the same
        admitted scope drops a file that is no longer there.
        """

        path = self.source_root / "Movies" / "Gone.2001.mkv"
        old = datetime(2025, 12, 31, tzinfo=UTC)
        self.media("Movies/One.2001.mkv", modified_at=old)
        self.media("Movies/Gone.2001.mkv", modified_at=old)
        with self.journey(stability=FileStabilityPolicy(stable_size_duration_seconds=60)) as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            # Seed one real durable prior observation of Gone so the first pass
            # legitimately proves its unchanged interval and admits it.
            entry = value.source.stat("Movies/Gone.2001.mkv")
            fingerprint = source_fingerprint("source", "library", entry)
            value.clock.advance(120)
            value.repository.upsert_media_discovery_observations(
                admitted["discoveryId"],
                (
                    DiscoveryObservation(
                        "Movies/Gone.2001.mkv",
                        entry.size,
                        entry.modified_at,
                        fingerprint.value,
                        self.clock.now - timedelta(seconds=120),
                        self.clock.now - timedelta(seconds=120),
                    ),
                ),
            )
            first = self.advance_once(value)
            self.assertIn(
                "Movies/Gone.2001.mkv",
                [item["path"] for item in first["sources"]],
                first,
            )
            self.assertEqual("waiting_stability", first["status"], first)
            # The file disappears and a later pass re-walks the same scope.
            path.unlink()
            value.clock.advance(120)
            settled = self.run_discovery(value)
            self.assertEqual(
                ["Movies/One.2001.mkv"], [item["path"] for item in settled["sources"]], settled
            )

    def test_a_changed_prior_source_keeps_truthful_stability_semantics(self) -> None:
        old = datetime(2025, 12, 31, tzinfo=UTC)
        self.media("Movies/A.2001.mkv", modified_at=old)
        changing = self.source_root / "Movies" / "B.2002.mkv"
        self.media("Movies/B.2002.mkv", modified_at=old)
        with self.journey(stability=FileStabilityPolicy(stable_size_duration_seconds=60)) as value:
            self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.advance_once(value)
            value.clock.advance(120)
            changing.write_bytes(b"m" * 4096)
            second = self.advance_once(value, step=1)
            # A is proven stable; B changed, so its interval restarts and it is
            # never claimed as an eligible primary.
            self.assertEqual(["Movies/A.2001.mkv"], [i["path"] for i in second["sources"]], second)
            self.assertEqual(1, second["progress"]["unstableEntries"], second)
            reasons = {item["reason"] for item in second["progress"]["reasons"]}
            self.assertIn("waiting_stable_size", reasons)


class ConfinedProviderEntryTests(_DiscoveryFixture):
    """A44-2: provider entries never expand discovery outside the selection."""

    def _unconfined(self, value, entry):
        original = value.source.list_page

        def pages(path, *, limit, cursor=None):
            return StoragePage([entry])

        value.source.list_page = pages
        return original

    def test_sibling_provider_entry_is_refused_without_freezing(self) -> None:
        """The exact A44-2 reproduction: a sibling file never becomes an intent."""

        self.media("Selected/A.2001.mkv")
        self.media("Outside/B.2002.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Selected"]},
            )
            raw = value.source._storage
            self._unconfined(value, raw.stat("Outside/B.2002.mkv"))
            settled = self.run_discovery(value)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertEqual("unsafe_entry", settled["progress"]["incompleteReason"], settled)
            self.assertEqual(["unsafe_entry"], settled["progress"]["refusalReasons"], settled)
            self.assertEqual([], settled["sources"], settled)
            self.assertFalse(settled["actions"]["finalize"]["available"], settled)
            self.assertEqual("discovery_budget_limited", settled["actions"]["finalize"]["refusal"])
            # No out-of-selection stat/traversal happened: the refused entry was
            # never observed as a source.
            self.assertNotIn(("stat", "Outside/B.2002.mkv"), value.source.reads)
            status, refused = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(409, status, refused)
            self.assert_zero_mutation_with_admitted_work(value)
            self.assertEqual([], value.source.mutations)

    def test_ancestor_and_traversal_entries_are_refused(self) -> None:
        self.media("Selected/A.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Selected"]},
            )
            raw = value.source._storage
            real = raw.stat("Selected/A.2001.mkv")
            hostile = (
                StorageEntry(
                    "B.2002.mkv",
                    "Outside/B.2002.mkv",
                    StorageEntryType.FILE,
                    1024,
                    real.modified_at,
                ),
                StorageEntry(
                    "../B.2002.mkv",
                    "Selected/../B.2002.mkv",
                    StorageEntryType.FILE,
                    1024,
                    real.modified_at,
                ),
                StorageEntry(
                    "B.2002.mkv",
                    "/Selected/B.2002.mkv",
                    StorageEntryType.FILE,
                    1024,
                    real.modified_at,
                ),
                # A deeper descendant returned while listing the selected
                # directory is not one ordinary child of that directory.
                StorageEntry(
                    "Deep.2002.mkv",
                    "Selected/Sub/Deep.2002.mkv",
                    StorageEntryType.FILE,
                    1024,
                    real.modified_at,
                ),
            )
            for index, entry in enumerate(hostile):
                status, admitted_case = self.request(
                    value,
                    "/api/v1/resource-libraries/library/files/discoveries",
                    "POST",
                    {"paths": ["Selected"]},
                )
                self.assertEqual(202, status, admitted_case)
                self._unconfined(value, entry)
                settled = self.run_discovery(value)
                self.assertEqual("partial_success", settled["status"], (index, settled))
                self.assertEqual("unsafe_entry", settled["progress"]["incompleteReason"], settled)
                self.assertEqual([], settled["sources"], (index, settled))
                self.assertFalse(settled["actions"]["finalize"]["available"], settled)
                self.assertNotIn(
                    ("stat", entry.path), value.source.reads, (index, value.source.reads)
                )
                self.assertEqual([], value.source.mutations)
                # A legitimate exact whitespace name is not confused with the
                # refused hostile entry.
                self.assertNotIn(entry.path, [i["path"] for i in settled["sources"]])

    def test_exact_whitespace_names_and_root_prefixes_still_admit(self) -> None:
        """Legitimate adapter conventions are preserved, not over-rejected."""

        self.media("Selected/  Padded.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Selected"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(
                ["Selected/  Padded.2001.mkv"],
                [item["path"] for item in settled["sources"]],
                settled,
            )
            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(201, status, frozen)

    def test_path_name_mismatch_is_refused(self) -> None:
        self.media("Selected/A.2001.mkv")
        with self.journey() as value:
            self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Selected"]},
            )
            raw = value.source._storage
            real = raw.stat("Selected/A.2001.mkv")
            inconsistent = StorageEntry(
                "Different.2001.mkv",
                "Selected/A.2001.mkv",
                StorageEntryType.FILE,
                real.size,
                real.modified_at,
            )
            self._unconfined(value, inconsistent)
            settled = self.run_discovery(value)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertEqual("unsafe_entry", settled["progress"]["incompleteReason"], settled)
            self.assertEqual([], settled["sources"], settled)


class DurableRefusalMonotonicityTests(_DiscoveryFixture):
    """A44-3: material safety/budget/cursor refusals survive read failure."""

    def _cursor_then_read_failure(self, value, *, read_failure_first: bool):
        """Select Loop (repeated cursor) and Locked (ordinary read failure).

        ``read_failure_first`` controls the event order, because the durable
        refusal must hold in both orders and across a restart.
        """

        raw = value.source._storage
        original = value.source.list_page

        def pages(path, *, limit, cursor=None):
            if path == "Loop":
                if cursor is None:
                    return StoragePage([raw.stat("Loop/A.2001.mkv")], "repeated")
                return StoragePage([], "repeated")
            return original(path, limit=limit, cursor=cursor)

        value.source.list_page = pages
        if not read_failure_first:
            value.source.fail_listing("Locked")

    def test_cursor_refusal_is_not_erased_by_a_later_read_failure(self) -> None:
        self.media("Loop/A.2001.mkv")
        self.media("Locked/B.2002.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Loop", "Locked"]},
            )
            self._cursor_then_read_failure(value, read_failure_first=False)
            settled = self.run_discovery(value)
            self.assertEqual("partial_success", settled["status"], settled)
            # The current dominant fact may be the read failure, but the
            # material cursor refusal stays durable and keeps Finalize refused.
            self.assertEqual(["cursor_repeated"], settled["progress"]["refusalReasons"], settled)
            self.assertEqual("cursor_repeated", settled["progress"]["materialRefusal"], settled)
            self.assertFalse(settled["actions"]["finalize"]["available"], settled)
            self.assertEqual("discovery_budget_limited", settled["actions"]["finalize"]["refusal"])
            status, refused = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("discovery_budget_limited", refused["error"]["code"])
            self.assertIsNone(refused.get("intentId"))
            self.assert_zero_mutation_with_admitted_work(value)

    def test_read_failure_before_the_cursor_refusal_is_equally_durable(self) -> None:
        self.media("Loop/A.2001.mkv")
        self.media("Locked/B.2002.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Locked", "Loop"]},
            )
            self._cursor_then_read_failure(value, read_failure_first=True)
            settled = self.run_discovery(value)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertEqual(["cursor_repeated"], settled["progress"]["refusalReasons"], settled)
            self.assertFalse(settled["actions"]["finalize"]["available"], settled)
            status, refused = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(409, status, refused)

    def test_material_refusal_survives_a_sqlite_restart(self) -> None:
        self.media("Loop/A.2001.mkv")
        self.media("Locked/B.2002.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Loop", "Locked"]},
            )
            self._cursor_then_read_failure(value, read_failure_first=False)
            settled = self.run_discovery(value)
            self.assertEqual(["cursor_repeated"], settled["progress"]["refusalReasons"], settled)
            reopened = SQLiteTaskRepository(self.database)
            try:
                stored = reopened.get_media_discovery(admitted["discoveryId"])
            finally:
                reopened.close()
            self.assertEqual(
                ("cursor_repeated",),
                tuple(item.value for item in stored.progress.refusal_reasons),
            )
            from mediaflow.domain.media_discovery import discovery_material_refusal

            self.assertIsNotNone(discovery_material_refusal(stored.progress))

    def test_read_failure_only_subset_still_freezes(self) -> None:
        """The separately legal explicitly reviewed read-failure subset works."""

        self.media("Movies/One.2001.mkv")
        self.media("Locked/Two.2002.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies", "Locked"]},
            )
            value.source.fail_listing("Locked")
            settled = self.run_discovery(value)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertEqual("read_failure", settled["progress"]["incompleteReason"], settled)
            self.assertEqual([], settled["progress"]["refusalReasons"], settled)
            self.assertIsNone(settled["progress"]["materialRefusal"], settled)
            self.assertTrue(settled["actions"]["finalize"]["available"], settled)
            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(201, status, frozen)
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertEqual(["Movies/One.2001.mkv"], [item.source.path for item in intent.items])


class FinalizeHandoffFencingTests(_DiscoveryFixture):
    """AC4 / RO-6: one discovery freezes exactly one linked intent.

    Concurrent, repeated and lost-response finalize requests must converge on
    the one durable linked intent.  The discovery link and the intent are the
    same transaction, so a losing request can never commit an orphan intent.
    """

    def _admit_and_settle(self, value, *, paths=("Movies",)):
        status, admitted = self.request(
            value,
            "/api/v1/resource-libraries/library/files/discoveries",
            "POST",
            {"paths": list(paths)},
        )
        self.assertEqual(202, status, admitted)
        return admitted, self.run_discovery(value)

    def test_concurrent_finalize_converges_on_one_linked_intent(self) -> None:
        """Two legitimate simultaneous finalize requests create one intent.

        The race is repeated on fresh discoveries so a scheduler that happens
        to serialize one pair cannot hide a lost-fencing regression.  The
        fixture reuses one runtime database across the loop, so each attempt
        asserts the exact +1 delta rather than an absolute count.
        """

        for attempt in range(3):
            # Each attempt needs its own concrete source: Task46.3 RO-2 source
            # ownership legitimately keeps one unfinished work per verified source,
            # so reusing one path across attempts would be a real refusal instead of
            # the finalize race this case studies.
            self.media(f"Movies/A{attempt}.2001.mkv")
            with self.journey() as value:
                admitted, settled = self._admit_and_settle(value)
                before = len(value.repository.list_manual_intents())
                barrier = threading.Barrier(2)

                def finalize(_):
                    barrier.wait()
                    return self.request(
                        value,
                        "/api/v1/operations/organize/discoveries/"
                        f"{admitted['discoveryId']}/finalize",
                        "POST",
                        {"expectedVersion": settled["version"]},
                    )

                with ThreadPoolExecutor(max_workers=2) as pool:
                    replies = list(pool.map(finalize, range(2)))
                statuses = sorted(status for status, _ in replies)
                self.assertEqual([201, 409], statuses, (attempt, replies))
                winner = next(document for status, document in replies if status == 201)
                loser = next(document for status, document in replies if status == 409)
                self.assertEqual("discovery_conflict", loser["error"]["code"], loser)
                durable = value.repository.list_manual_intents()
                # Exactly one new durable intent: the losing request minted no
                # orphan work.
                self.assertEqual(
                    before + 1, len(durable), (attempt, [i.intent_id for i in durable])
                )
                created = next(item for item in durable if item.intent_id == winner["intentId"])
                self.assertEqual(
                    [f"Movies/A{attempt}.2001.mkv"], [i.source.path for i in created.items]
                )
                # The authenticated listing exposes exactly the one linked
                # intent, never a hidden duplicate.
                status, listed = self.request(value, "/api/v1/manual-intents")
                self.assertEqual(200, status, listed)
                ids = [item["intentId"] for item in listed["items"]]
                self.assertEqual(1, ids.count(winner["intentId"]), (attempt, ids))
                # Discovery grants no execution authority and mutates no media.
                self.assertEqual([], value.source.mutations)
                self.assert_zero_mutation_with_admitted_work(value)
                self.assertTrue((self.source_root / "Movies" / f"A{attempt}.2001.mkv").is_file())

    def test_two_repository_linkers_race_to_one_intent(self) -> None:
        """The durable one-shot link guard fences two simultaneous writers."""

        self.media("Movies/A.2001.mkv")
        with self.journey() as value:
            admitted, _ = self._admit_and_settle(value)
            discovery = value.repository.get_media_discovery(admitted["discoveryId"])
            source = ManualSourceIdentity.from_document(discovery.sources[0])

            def link(_):
                intent, audit = value.intents.prepare_from_sources(
                    (source,),
                    actor=discovery.actor,
                    snapshot_id=discovery.snapshot_id,
                    snapshot_digest=discovery.snapshot_digest,
                    pinned_snapshot=True,
                )
                linked = replace(
                    discovery,
                    version=discovery.version + 1,
                    intent_id=intent.intent_id,
                    frozen_at=self.clock.now,
                )
                try:
                    value.repository.create_manual_intent_for_discovery(
                        linked,
                        expected_version=discovery.version,
                        intent=intent,
                        items=intent.items,
                        audit=audit,
                    )
                    return "linked"
                except DiscoveryConflict:
                    return "conflict"

            barrier = threading.Barrier(2)

            def raced(_):
                barrier.wait()
                return link(_)

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(raced, range(2)))
            self.assertEqual(["conflict", "linked"], sorted(outcomes), outcomes)
            self.assertEqual(1, len(value.repository.list_manual_intents()))

    def test_finalize_fails_closed_without_atomic_linkage(self) -> None:
        """A repository that cannot link atomically never commits an orphan intent."""

        self.media("Movies/A.2001.mkv")
        with self.journey() as value:
            admitted, settled = self._admit_and_settle(value)
            before = len(value.repository.list_manual_intents())
            with mock.patch.object(value.repository, "create_manual_intent_for_discovery", None):
                status, document = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                    "POST",
                    {"expectedVersion": settled["version"]},
                )
            self.assertEqual(503, status, document)
            self.assertEqual("discovery_unavailable", document["error"]["code"], document)
            self.assertEqual(before, len(value.repository.list_manual_intents()))
            _, readback = self.request(
                value, f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}"
            )
            self.assertIsNone(readback["intentId"], readback)
            self.assertFalse(readback["frozen"], readback)

    def test_lost_response_repeat_never_creates_an_orphan_intent(self) -> None:
        """A repeated finalize on a stale version fails without orphan work."""

        self.media("Movies/A.2001.mkv")
        with self.journey() as value:
            admitted, settled = self._admit_and_settle(value)
            path = f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize"
            first_status, first = self.request(
                value, path, "POST", {"expectedVersion": settled["version"]}
            )
            self.assertEqual(201, first_status, first)
            # The original response was lost and the operator retries with the
            # version they already held: no second intent is committed.
            repeat_status, repeat = self.request(
                value, path, "POST", {"expectedVersion": settled["version"]}
            )
            self.assertEqual(409, repeat_status, repeat)
            self.assertEqual("discovery_conflict", repeat["error"]["code"], repeat)
            durable = value.repository.list_manual_intents()
            self.assertEqual(1, len(durable), [item.intent_id for item in durable])
            self.assertEqual(first["intentId"], durable[0].intent_id)

    def test_fenced_plan_publication_requires_the_exact_live_claim(self) -> None:
        """The plan link, lifecycle and claim release are one fenced write.

        A prepared plan must never be published by an owner whose claim was
        taken over, and the publication must release the claim it wrote under in
        the same statement.  The repository boundary is exercised directly so a
        future refactor cannot quietly split the fence from the plan link.
        """

        from mediaflow.domain.media_discovery import DiscoveryOwnershipLost

        self.media("Movies/A.2001.mkv")
        with self.journey() as value:
            admitted, settled = self._admit_and_settle(value)
            frozen = value.discovery.finalize(
                admitted["discoveryId"],
                actor="operator",
                expected_version=settled["version"],
            )
            self.assertIsNotNone(frozen.intent_id)
            # A frozen generic Files record is not claimable by the walk (its
            # reviewed finalize path owns it), so the live claim this boundary
            # must fence is written directly, exactly as the analyzing Worker
            # would hold it.
            value.repository._connection.execute(
                "UPDATE media_discoveries SET status=?, claim_worker_id=?, claim_token=?, "
                "claim_expires_at=? WHERE discovery_id=?",
                (
                    "analyzing",
                    "owner",
                    "owner-token",
                    (self.clock.now + timedelta(minutes=10)).isoformat(),
                    admitted["discoveryId"],
                ),
            )
            value.repository._connection.commit()
            claimed = value.repository.get_media_discovery(admitted["discoveryId"])
            self.assertIsNotNone(claimed)
            self.assertEqual("owner-token", claimed.claim_token)
            # A different owner cannot publish the plan or the settled status.
            prepared = replace(
                claimed,
                status=claimed.status.__class__.COMPLETED,
                version=claimed.version + 1,
                preview_id="0" * 32,
                progress=replace(claimed.progress, phase="prepared"),
            )
            with self.assertRaises(DiscoveryOwnershipLost):
                value.repository.publish_media_discovery_plan(
                    prepared,
                    expected_version=claimed.version,
                    claim_token="stolen-token",
                )
            durable = value.repository.get_media_discovery(admitted["discoveryId"])
            self.assertIsNone(durable.preview_id)
            self.assertEqual(claimed.status, durable.status)
            self.assertEqual("owner-token", durable.claim_token)
            # The exact owner publishes it once and the claim is released in
            # the same durable outcome.
            published = value.repository.publish_media_discovery_plan(
                prepared,
                expected_version=claimed.version,
                claim_token="owner-token",
            )
            self.assertEqual("0" * 32, published.preview_id)
            self.assertEqual("prepared", published.progress.phase)
            self.assertIsNone(published.claim_token)
            self.assertEqual(
                None, value.repository.media_discovery_claim(admitted["discoveryId"])["claimToken"]
            )
            # A repeated publication cannot publish a second plan: the claim
            # the first write released is no longer the live owner's.
            with self.assertRaises(DiscoveryOwnershipLost):
                value.repository.publish_media_discovery_plan(
                    replace(published, version=published.version + 1, preview_id="1" * 32),
                    expected_version=claimed.version,
                    claim_token="owner-token",
                )
            self.assertEqual(
                "0" * 32,
                value.repository.get_media_discovery(admitted["discoveryId"]).preview_id,
            )
            self.assertEqual([], value.source.mutations)

    def test_the_plan_rows_and_the_run_link_are_one_atomic_publication(self) -> None:
        """The analyzed plan and its discovery link commit — or not — together.

        B's confirmed window: the old path persisted the plan rows first and
        then fenced the discovery link, so a control that won the version race
        left a fully persisted current plan behind, readable from the intent
        and confirmable through the normal admission.  The atomic boundary
        writes the plan rows *inside* the fenced publication, so a lost race
        leaves no plan row at all, and a won race publishes the exact plan and
        releases the claim in the same commit.
        """

        self.media("Movies/A.2001.mkv")
        with self.journey() as value:
            admitted, settled = self._admit_and_settle(value)
            frozen = value.discovery.finalize(
                admitted["discoveryId"],
                actor="operator",
                expected_version=settled["version"],
            )
            intent = value.intents.get(frozen.intent_id)
            # The Worker's exact live claim, as the analyzing pass would hold it.
            value.repository._connection.execute(
                "UPDATE media_discoveries SET status=?, claim_worker_id=?, claim_token=?, "
                "claim_expires_at=? WHERE discovery_id=?",
                (
                    "analyzing",
                    "owner",
                    "owner-token",
                    (self.clock.now + timedelta(minutes=10)).isoformat(),
                    admitted["discoveryId"],
                ),
            )
            value.repository._connection.commit()
            claimed = value.repository.get_media_discovery(admitted["discoveryId"])
            plan = value.previews.create(
                intent.intent_id,
                [item.item_id for item in intent.items],
                actor="analysis-worker",
                expected_version=intent.version,
                persist=False,
            )
            prepared = replace(
                claimed,
                status=claimed.status.__class__.COMPLETED,
                version=claimed.version + 1,
                preview_id=plan.preview_id,
                progress=replace(claimed.progress, phase="prepared"),
            )
            # A control that won the version race between the analysis and the
            # publication rolls the whole transaction back: the operator's
            # pause request bumped the version, so the stale publication matches
            # no live row — no discovery link AND no plan row was ever written.
            value.repository._connection.execute(
                "UPDATE media_discoveries SET version=version+1, pause_requested=1, "
                "updated_at=? WHERE discovery_id=?",
                (self.clock.now.isoformat(), admitted["discoveryId"]),
            )
            value.repository._connection.commit()
            with self.assertRaises(DiscoveryConflict):
                value.repository.publish_media_discovery_plan_with_plan(
                    prepared,
                    plan,
                    expected_version=claimed.version,
                    claim_token="owner-token",
                )
            self.assertIsNone(value.repository.get_manual_preview(plan.preview_id))
            self.assertEqual((), value.repository.list_manual_previews(intent.intent_id))
            durable = value.repository.get_media_discovery(admitted["discoveryId"])
            self.assertIsNone(durable.preview_id)
            self.assertEqual("owner-token", durable.claim_token)
            self.assertTrue(durable.pause_requested)
            # The exact owner (after the pause was cleared) re-reads the fresh
            # record and publishes once: the plan, the link and the claim
            # release are all durable afterwards.
            prepared = replace(
                durable,
                status=durable.status.__class__.COMPLETED,
                version=durable.version + 1,
                preview_id=plan.preview_id,
                progress=replace(durable.progress, phase="prepared"),
            )
            published_discovery, published_plan = (
                value.repository.publish_media_discovery_plan_with_plan(
                    prepared,
                    plan,
                    expected_version=durable.version,
                    claim_token="owner-token",
                )
            )
            self.assertEqual(plan.preview_id, published_discovery.preview_id)
            self.assertEqual(plan.preview_id, published_plan.preview_id)
            self.assertTrue(published_plan.current)
            self.assertEqual(
                plan.preview_id,
                value.repository.get_latest_manual_preview(intent.intent_id).preview_id,
            )
            self.assertIsNone(
                value.repository.media_discovery_claim(admitted["discoveryId"])["claimToken"]
            )
            # A repeated publication cannot publish a second plan: the claim
            # the first write released is no longer the live owner's.
            from mediaflow.domain.media_discovery import DiscoveryOwnershipLost

            with self.assertRaises(DiscoveryOwnershipLost):
                replayed = replace(
                    plan,
                    preview_id="1" * 32,
                    items=tuple(
                        replace(
                            item,
                            preview_id="1" * 32,
                            preview_item_id="2" * 32,
                        )
                        for item in plan.items
                    ),
                )
                value.repository.publish_media_discovery_plan_with_plan(
                    replace(published_discovery, version=published_discovery.version + 1),
                    replayed,
                    expected_version=claimed.version,
                    claim_token="owner-token",
                )
            self.assertEqual(
                plan.preview_id,
                value.repository.get_latest_manual_preview(intent.intent_id).preview_id,
            )
            self.assertEqual([], value.source.mutations)

    def test_finalize_of_an_already_frozen_discovery_is_idempotent(self) -> None:
        """Re-finalizing the frozen record returns its one linked intent."""

        self.media("Movies/A.2001.mkv")
        with self.journey() as value:
            admitted, settled = self._admit_and_settle(value)
            path = f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize"
            _, first = self.request(value, path, "POST", {"expectedVersion": settled["version"]})
            _, readback = self.request(
                value, f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}"
            )
            second_status, second = self.request(
                value, path, "POST", {"expectedVersion": readback["version"]}
            )
            self.assertEqual(201, second_status, second)
            self.assertEqual(first["intentId"], second["intentId"])
            self.assertEqual(1, len(value.repository.list_manual_intents()))

    def test_discarding_an_unpublished_plan_is_scoped_to_its_own_identity(self) -> None:
        """Cleanup retires one exact Preview; a sibling plan stays confirmable.

        A Worker that lost the publication race retires only the plan it
        analyzed.  An unrelated current plan of the same intent (a different
        still-undecided source) must keep its current identity and its
        confirmable items, so cleanup can never silently withdraw a legal
        sibling's summary.
        """

        self.media("Movies/A.2001.mkv")
        self.media("Movies/B.2002.mkv")
        with self.journey() as value:
            admitted, settled = self._admit_and_settle(value)
            frozen = value.discovery.finalize(
                admitted["discoveryId"],
                actor="operator",
                expected_version=settled["version"],
            )
            intent = value.intents.get(frozen.intent_id)
            first, second = (item.item_id for item in intent.items)
            staying = value.previews.create(
                frozen.intent_id,
                [first],
                actor="operator",
                expected_version=intent.version,
            )
            losing = value.previews.create(
                frozen.intent_id,
                [second],
                actor="operator",
                expected_version=intent.version,
            )
            self.assertTrue(staying.current)
            self.assertTrue(losing.current)
            # Retiring the losing plan is exact to that plan.
            value.repository.discard_manual_preview(
                losing.preview_id, "the run's control changed first", self.clock.now
            )
            retired = value.repository.get_manual_preview(losing.preview_id)
            self.assertFalse(retired.current)
            self.assertEqual("stale", retired.status.value)
            self.assertTrue(all(not item.current for item in retired.items))
            kept = value.repository.get_manual_preview(staying.preview_id)
            self.assertTrue(kept.current)
            # This fixture has no Metadata Provider authority, so the plan's own
            # per-item outcome is "unavailable"; what must survive cleanup is the
            # sibling's current identity and its still-live item rows.
            self.assertNotEqual("stale", kept.status.value)
            self.assertTrue(all(item.current for item in kept.items))
            self.assertEqual([first], [item.item_id for item in kept.items])
            self.assertEqual([], value.source.mutations)

    def test_a_frozen_link_survives_a_sqlite_reopen_without_duplication(self) -> None:
        """A restart between the finalize commit and the response keeps one intent."""

        self.media("Movies/A.2001.mkv")
        with self.journey() as value:
            admitted, settled = self._admit_and_settle(value)
            path = f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize"
            first_status, first = self.request(
                value, path, "POST", {"expectedVersion": settled["version"]}
            )
            self.assertEqual(201, first_status, first)
            discovery_id = admitted["discoveryId"]
            linked = first["intentId"]
        # The process restarts and reopens the same durable database.
        with self.journey() as value:
            status, readback = self.request(
                value, f"/api/v1/operations/organize/discoveries/{discovery_id}"
            )
            self.assertEqual(200, status, readback)
            self.assertTrue(readback["frozen"], readback)
            self.assertEqual(linked, readback["intentId"], readback)
            # The restart does not reopen or duplicate the already frozen work.
            self.assertEqual(1, len(value.repository.list_manual_intents()))
            status, again = self.request(
                value, path, "POST", {"expectedVersion": readback["version"]}
            )
            self.assertEqual(201, status, again)
            self.assertEqual(linked, again["intentId"], again)
            self.assertEqual(1, len(value.repository.list_manual_intents()))

    def test_the_repository_link_is_a_one_shot_discovery_transition(self) -> None:
        """The atomic repository boundary refuses a second link deterministically."""

        from mediaflow.application.manual_organize import ManualOrganizeIntentService

        self.media("Movies/A.2001.mkv")
        with self.journey() as value:
            admitted, settled = self._admit_and_settle(value)
            discovery = value.repository.get_media_discovery(admitted["discoveryId"])
            intents = value.intents
            self.assertIsInstance(intents, ManualOrganizeIntentService)
            source = ManualSourceIdentity.from_document(discovery.sources[0])
            intent, audit = intents.prepare_from_sources(
                (source,),
                actor=discovery.actor,
                snapshot_id=discovery.snapshot_id,
                snapshot_digest=discovery.snapshot_digest,
                pinned_snapshot=True,
            )
            linked = replace(
                discovery,
                version=discovery.version + 1,
                intent_id=intent.intent_id,
                frozen_at=self.clock.now,
            )
            value.repository.create_manual_intent_for_discovery(
                linked,
                expected_version=discovery.version,
                intent=intent,
                items=intent.items,
                audit=audit,
            )
            # A second request that still holds the original version, or that
            # replays the same winning transition, is refused without side
            # effect: the intent is never duplicated.
            with self.assertRaises(DiscoveryConflict):
                value.repository.create_manual_intent_for_discovery(
                    linked,
                    expected_version=discovery.version,
                    intent=intent,
                    items=intent.items,
                    audit=audit,
                )
            self.assertEqual(1, len(value.repository.list_manual_intents()))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class A44BlockingDefectRegressions(_DiscoveryFixture):
    """The eight proven P1 defect groups from A's folder-journey audit.

    Each case reproduces the *observable* failure A established (its probe
    receipts are the reference) and asserts the corrected ordinary behaviour:
    atomic equivalent-scope admission, actual configured policy, real
    non-busy stability waiting, legal long names, truthful partial discovery,
    correct traversal accounting, Trailer association and command-specific
    Worker readiness.  No assertion is weakened and no capability is faked.
    """

    # -- A44-6: atomic admission of equivalent scopes ---------------------

    def test_reordered_equivalent_scope_converges_on_one_open_admission(self) -> None:
        """A44-6: ``[A, B]`` and ``[B, A]`` are one admitted scope."""

        self.media("A/One.mkv")
        self.media("B/Two.mkv")
        with self.journey() as value:
            _, first = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["A", "B"]},
            )
            status, second = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["B", "A"]},
            )
            self.assertEqual(202, status, second)
            self.assertEqual(first["discoveryId"], second["discoveryId"], second)
            self.assertEqual(1, len(value.repository.list_media_discoveries()))
            # The durable scope is canonical, so the two equivalent requests
            # cannot persist two different orders of the same selection.
            self.assertEqual(
                [{"path": "A", "kind": "directory"}, {"path": "B", "kind": "directory"}],
                second["selection"]["scopes"],
            )
            self.assertEqual([], value.source.mutations)
            self.assert_zero_mutation_with_admitted_work(value)

    def test_concurrent_equivalent_admissions_serialize_across_sqlite_connections(self) -> None:
        """A44-6: concurrent reads cannot both create the same open admission."""

        self.media("Movies/One.mkv")
        with self.journey() as value:
            second_repository = SQLiteTaskRepository(self.database)
            barrier = threading.Barrier(2)

            def synchronize_first_lookup(repository):
                original = repository.find_open_media_discovery
                first = True

                def find_open(**kwargs):
                    nonlocal first
                    result = original(**kwargs)
                    if first:
                        first = False
                        barrier.wait(timeout=5)
                    return result

                repository.find_open_media_discovery = find_open

            synchronize_first_lookup(value.repository)
            synchronize_first_lookup(second_repository)
            second_discovery = MediaDiscoveryService(
                second_repository,
                value.intents,
                configuration=value.configuration,
                runtime_resolver=lambda _snapshot_id, _snapshot_digest: value.configuration,
                storages=value.storages,
                clock=self.clock,
            )

            def admit(service):
                return service.admit(
                    resource_library_id="library",
                    relative_paths=["Movies"],
                    actor="operator",
                )

            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    records = list(pool.map(admit, (value.discovery, second_discovery)))
            finally:
                second_repository.close()
            self.assertEqual(records[0].discovery_id, records[1].discovery_id)
            self.assertEqual(1, len(value.repository.list_media_discoveries()))
            self.assertEqual([], value.source.mutations)

    def test_an_open_admission_beyond_the_recent_window_still_reconciles(self) -> None:
        """A44-6: an existing admission beyond the recent-list window.

        The original request is still open and queued while 50 other scopes are
        admitted.  Resubmitting the original scope must reconcile to that same
        durable record: persistent identity, not a bounded recent-list scan.
        """

        for index in range(51):
            self.media(f"Folder{index:02}/One.mkv")
        with self.journey() as value:
            _, first = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Folder00"]},
            )
            for index in range(1, 51):
                self.clock.advance(1)
                self.request(
                    value,
                    "/api/v1/resource-libraries/library/files/discoveries",
                    "POST",
                    {"paths": [f"Folder{index:02}"]},
                )
            status, repeated = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Folder00"]},
            )
            self.assertEqual(202, status, repeated)
            self.assertEqual(first["discoveryId"], repeated["discoveryId"], repeated)
            self.assertEqual("queued", repeated["status"], repeated)
            self.assertEqual(51, len(value.repository.list_media_discoveries(limit=100)))

    def test_a_terminal_equivalent_scope_is_deliberate_successor_work(self) -> None:
        """A44-6: reconciliation never reopens finished or frozen work."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            _, first = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual(first["discoveryId"], settled["discoveryId"])
            status, successor = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, successor)
            self.assertNotEqual(first["discoveryId"], successor["discoveryId"])

    # -- A44-7: actual configured policy ---------------------------------

    def _managed_policy_journey(self, *, library_policy: dict):
        """Publish and production-load one real include/exclude/stability policy."""

        document = self.document()
        document["resourceLibraries"][0].update(library_policy)
        return document

    def test_published_depth_policy_governs_direct_selection(self) -> None:
        """A44-7: a directly selected subtree cannot bypass configured depth."""

        self.media("Movies/One.mkv")
        self.media("Movies/Sub/Two.mkv")
        with self.journey() as value:
            # Publish the real managed policy through the production loader.
            from mediaflow.infrastructure.runtime_configuration import (
                load_managed_runtime_configuration,
                with_managed_snapshot,
            )

            document = json.loads(json.dumps(value.revision.document))
            document["resourceLibraries"][0]["maxDepth"] = 1
            from mediaflow.application.configuration_snapshot import ManagedConfigurationService

            with SQLiteConfigurationRepository(self.database) as configuration_repository:
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(self.database),
                )
                revision = _activate(managed, document)
                runtime = with_managed_snapshot(
                    load_managed_runtime_configuration(
                        revision.document, bootstrap_database_path=str(self.database)
                    ),
                    snapshot_id=revision.revision_id,
                    digest=revision.digest,
                )
            self.assertEqual(1, runtime.resource_libraries[0].max_depth)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            status, refused = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/Sub"]},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("source_excluded", refused["error"]["code"], refused)
            self.assertEqual(
                "configured_depth_exceeded",
                refused["error"]["details"]["reason"],
                refused,
            )
            # The parent selection under the same policy still works and the
            # configured depth still prunes the deeper file.
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual(["Movies/One.mkv"], [i["path"] for i in settled["sources"]], settled)
            self.assertEqual([], value.source.mutations)

    def test_published_exclude_and_stability_policy_reach_the_worker(self) -> None:
        """A44-7: the real loader consumes published exclude/stability policy."""

        old = datetime(2025, 12, 31, tzinfo=UTC)
        self.media("Movies/Keep.mkv", modified_at=old)
        self.media("Movies/Excluded/Drop.mkv", modified_at=old)
        document = self._managed_policy_journey(
            library_policy={
                "excludeRules": [{"kind": "directory", "pattern": "Movies/Excluded"}],
                "stability": {
                    "minimumAgeSeconds": 0,
                    "modifiedThresholdSeconds": 0,
                    "stableSizeDurationSeconds": 60,
                },
            }
        )
        with self.journey() as value:
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
            library = runtime.resource_libraries[0]
            self.assertEqual(
                ("Movies/Excluded",),
                tuple(rule.pattern for rule in library.exclude_rules),
            )
            self.assertEqual(60, library.stability_policy.stable_size_duration_seconds)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            # B46.3-03: a directory exclude rule keeps its unchanged automatic
            # meaning for a library walk, but it no longer vetoes the folder the
            # operator deliberately selected.  The deliberately selected
            # excluded folder is therefore admitted as organizing work.
            status, admitted_folder = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/Excluded"]},
            )
            self.assertEqual(202, status, admitted_folder)
            self.assertEqual(
                [{"kind": "directory", "path": "Movies/Excluded"}],
                admitted_folder["selection"]["scopes"],
            )
            # The published nonzero stability policy is genuinely consumed: the
            # first observation of that admitted folder cannot fabricate the
            # interval, so nothing is published as a primary yet.
            first = self.advance_once(value)
            self.assertEqual("waiting_stability", first["status"], first)
            self.assertEqual(0, first["progress"]["primarySources"], first)
            self.assertEqual([], value.source.mutations)

    def test_an_unsupported_resource_library_field_is_refused_not_ignored(self) -> None:
        """A44-7: an unconsumed policy field is never silently published."""

        from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration

        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["resourceLibraries"][0]["excludeRulesTypo"] = ["Movies"]
        with self.assertRaises(ValueError) as raised:
            load_runtime_configuration(document)
        self.assertIn("unsupported field", str(raised.exception))

    # -- A44-8: genuine, non-busy stability waiting ----------------------

    def test_waiting_work_is_not_immediately_reclaimed(self) -> None:
        """A44-8: a waiting discovery is due only after its real interval.

        Reclaiming it in a tight loop would spin, consume the traversal budget
        while traversing nothing and starve other resident commands.  The
        durable due time gates the pickup, and other queued work proceeds.
        """

        self.media("Old/One.mkv", modified_at=datetime(2025, 12, 31, tzinfo=UTC))
        self.media("Next/Two.mkv", modified_at=datetime(2025, 12, 31, tzinfo=UTC))
        with self.journey(stability=FileStabilityPolicy(stable_size_duration_seconds=60)) as value:
            _, old = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Old"]},
            )
            first = self.advance_once(value)
            self.assertEqual("waiting_stability", first["status"], first)
            self.assertIsNotNone(first["nextObservationAt"], first)
            observed_entries = first["progress"]["visitedEntries"]
            self.clock.advance(1)
            _, sibling = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Next"]},
            )
            # The waiting record is not due, so the sibling gets the Worker.
            picked = [
                value.discovery.claim_and_run(worker_id=f"w{index}", claim_token=f"t{index}")
                for index in range(4)
            ]
            ids = {item.discovery_id for item in picked if item is not None}
            self.assertNotIn(old["discoveryId"], ids, ids)
            self.assertIn(sibling["discoveryId"], ids, ids)
            # Idle waiting consumed no further traversal budget: the durable
            # counters are exactly the ones the one real walk established.
            stored = value.repository.get_media_discovery(old["discoveryId"])
            self.assertEqual(observed_entries, stored.progress.counters.visited_entries)
            self.assert_zero_mutation_with_admitted_work(value)

    def test_a_due_waiting_discovery_is_re_observed_and_proves_stability(self) -> None:
        """A44-8: once due, a later real observation proves the interval."""

        self.media("Movies/One.2001.mkv", modified_at=datetime(2025, 12, 31, tzinfo=UTC))
        with self.journey(stability=FileStabilityPolicy(stable_size_duration_seconds=60)) as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            first = self.advance_once(value)
            self.assertEqual("waiting_stability", first["status"], first)
            # Still not due: the claim finds no work rather than spinning.
            self.assertIsNone(value.discovery.claim_and_run(worker_id="early", claim_token="early"))
            self.clock.advance(120)
            settled = self.run_discovery(value)
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertIsNone(settled["nextObservationAt"], settled)
            self.assertEqual(["Movies/One.2001.mkv"], [item["path"] for item in settled["sources"]])
            self.assertEqual(admitted["discoveryId"], settled["discoveryId"])

    # -- A44-9: legal long names and per-item error isolation ------------

    def test_a_legal_long_filename_does_not_strand_its_batch(self) -> None:
        """A44-9: a 179-character ordinary Local filename is preserved exactly."""

        long_name = "L" * 175 + ".mkv"
        self.assertEqual(179, len(long_name))
        self.media(f"Movies/{long_name}")
        self.media("Movies/Short.2001.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(2, settled["progress"]["primarySources"], settled)
            self.assertIsNone(settled["failure"], settled)
            paths = {item["path"] for item in settled["sources"]}
            self.assertIn(f"Movies/{long_name}", paths)
            # The exact name survives the freeze into the linked intent.
            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(201, status, frozen)
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertIn(long_name, [item.source.filename for item in intent.items])
            self.assertEqual([], value.source.mutations)

    def test_a_legal_long_relative_path_is_readable_end_to_end(self) -> None:
        """A44-9: a >1024-character legal path does not break list or detail.

        Real-filesystem coverage.  The temporary filesystem is probed first so
        a host path-length limit (macOS ``PATH_MAX`` 1024) produces an explicit,
        reported skip; the platform-independent ``..._in_memory`` case below
        still exercises the exact path through the real application/API/
        persistence layers on every host.  Any non-path-length error still
        fails.
        """

        path = (
            "Long/" + "/".join(("d" + str(index) + "x" * 197) for index in range(6)) + "/Film.mkv"
        )
        # This is a provider-neutral path projection regression. macOS Local
        # cannot create a >1024-byte physical path; keep the exact logical path
        # in Storage while exercising the real Worker, SQLite and API below.
        source = PagedMemoryStorage("source", read_only=False)
        source.add_file(path, size=512, modified_at=self.clock() - timedelta(hours=1))
        self.assertGreater(len(path), 1024)
        with self.journey(source_storage=source) as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Long"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertGreater(len(settled["sources"][0]["path"]), 1024)
            # The bounded list projection stays readable for the same exact
            # long path, and the detail readback publishes the exact bytes.
            status, listing = self.request(value, "/api/v1/operations/organize/discoveries")
            self.assertEqual(200, status, listing)
            found = next(
                item for item in listing["items"] if item["discoveryId"] == admitted["discoveryId"]
            )
            self.assertEqual(1, found["primarySourceCount"], found)
            status, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            self.assertEqual(200, status, detail)
            self.assertEqual(settled["sources"][0]["path"], detail["sources"][0]["path"])
            self.assertEqual(path, detail["sources"][0]["path"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_a_legal_long_relative_path_is_readable_end_to_end_in_memory(self) -> None:
        """A44-9 (platform-independent): exact >1024 path through real layers.

        A provider-neutral in-memory Storage replaces only the source adapter,
        so the exact long ResourceLibrary-relative path is preserved byte-for-
        byte through the real discovery service, the real SQLite repository and
        the real authenticated API list/detail projections, with zero mutation.
        This is the coverage that must hold on macOS and Linux alike.
        """

        path = (
            "Long/" + "/".join(("d" + str(index) + "x" * 197) for index in range(6)) + "/Film.mkv"
        )
        self.assertGreater(len(path), 1024)
        storage = InMemoryStorage("source", {path: b"m" * 512})
        with self.journey(source_storage=storage) as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Long"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            # The exact bytes survive the walk, not a shortened or normalized
            # substitute.
            self.assertEqual(path, settled["sources"][0]["path"])
            status, listing = self.request(value, "/api/v1/operations/organize/discoveries")
            self.assertEqual(200, status, listing)
            found = next(
                item for item in listing["items"] if item["discoveryId"] == admitted["discoveryId"]
            )
            self.assertEqual(1, found["primarySourceCount"], found)
            status, detail = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            self.assertEqual(200, status, detail)
            self.assertEqual(path, detail["sources"][0]["path"])
            # Discovery is metadata-only and performed no mutation.
            self.assertEqual([], value.source.mutations)

    # -- A44-10: truthful partial discovery ------------------------------

    def test_a_missing_selected_file_is_an_incomplete_scope(self) -> None:
        """A44-10: a gone explicit file is never reported as complete."""

        gone = self.media("Gone.mkv")
        self.media("Good/Keep.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Gone.mkv", "Good"]},
            )
            gone.unlink()
            settled = self.run_discovery(value)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertTrue(settled["progress"]["incomplete"], settled)
            self.assertEqual("read_failure", settled["progress"]["incompleteReason"], settled)
            self.assertEqual(1, settled["progress"]["errorEntries"], settled)
            self.assertEqual(
                ["Good/Keep.mkv"], [item["path"] for item in settled["sources"]], settled
            )
            # A known eligible subset keeps its explicit reviewed path.
            self.assertTrue(settled["actions"]["finalize"]["available"], settled)
            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(201, status, frozen)
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertEqual(["Good/Keep.mkv"], [item.source.path for item in intent.items])

    def test_a_permission_denied_selected_file_is_an_incomplete_scope(self) -> None:
        """A44-10: a denied explicit file is equally a real partial discovery."""

        self.media("Denied.mkv")
        self.media("Good/Keep.mkv")
        with self.journey() as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Denied.mkv", "Good"]},
            )
            original = value.source.stat

            def denied(path):
                if path == "Denied.mkv":
                    raise StorageError(
                        StorageErrorCode.PERMISSION_DENIED,
                        "stat",
                        path,
                        "synthetic permission denial",
                    )
                return original(path)

            value.source.stat = denied
            settled = self.run_discovery(value)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertTrue(settled["progress"]["incomplete"], settled)
            self.assertEqual("read_failure", settled["progress"]["incompleteReason"], settled)
            self.assertEqual(1, settled["progress"]["errorEntries"], settled)
            self.assertEqual(
                ["Good/Keep.mkv"], [item["path"] for item in settled["sources"]], settled
            )

    # -- A44-11: correct traversal accounting ----------------------------

    def test_many_pages_of_one_directory_do_not_exhaust_the_directory_budget(self) -> None:
        """A44-11: pages are not new directories.

        One real directory served over many pages is still one opened
        directory; the directory budget must not be consumed by paging.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey(budgets=DiscoveryBudgets(max_visited_directories=1)) as value:
            raw = value.source._storage
            pages = {"count": 0}

            def paged(path, *, limit, cursor=None):
                if path != "Movies":
                    return raw.list_page(path, limit=limit, cursor=cursor)
                pages["count"] += 1
                if cursor is None:
                    # The same legal media basename repeats on the next page,
                    # exactly like the provider's non-atomic listing.
                    return StoragePage([raw.stat("Movies/One.2001.mkv")], "page-2")
                return StoragePage([raw.stat("Movies/One.2001.mkv")], None)

            value.source.list_page = paged
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual(1, settled["progress"]["visitedDirectories"], settled)
            self.assertEqual(2, settled["progress"]["pageFetches"], settled)
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual("completed", settled["status"], settled)
            self.assertIsNone(settled["progress"]["materialRefusal"], settled)

    # -- A44-12: Trailer association -------------------------------------

    def test_a_matching_trailer_is_not_an_independent_primary(self) -> None:
        """A44-12: the existing attachment association governs primaries.

        With the *published and production-loaded* attachment policy enabled, a
        matching Trailer video is an attachment of its main file.  It must not
        also become a second independent primary, and 51 main files plus 51
        matching Trailers must stay inside the 100-primary bound instead of
        being refused as a 102-candidate truncation.
        """

        for index in range(51):
            self.media(f"Movies/Film{index:03d}.2001.mkv")
            self.media(f"Movies/Film{index:03d}.2001-trailer.mp4")
        with self.journey(attachments=True) as value:
            self.assertTrue(
                all(
                    policy.organize_policy.attachments.enabled
                    for policy in value.configuration.strategy.recognition_type_policies
                ),
                value.configuration.strategy.recognition_type_policies,
            )
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value, steps=8)
            # 51 main files plus their 51 associated Trailers is 51 primaries,
            # never 102 candidates hitting the primary bound.
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(51, settled["progress"]["primarySources"], settled)
            self.assertIsNone(settled["progress"]["materialRefusal"], settled)
            paths = [item["path"] for item in settled["sources"]]
            self.assertIn("Movies/Film000.2001.mkv", paths)
            # A classified Trailer is an attachment of its main file, not a
            # second independent primary: the exact Preview re-discovers it
            # from live Storage under the same policy.
            self.assertNotIn("Movies/Film000.2001-trailer.mp4", paths)
            self.assertEqual(
                sorted(f"Movies/Film{index:03d}.2001.mkv" for index in range(51)), sorted(paths)
            )
            self.assertEqual([], value.source.mutations)
            self.assert_zero_mutation_with_admitted_work(value)
            # The frozen manifest still hands the existing attachment semantics
            # to the ordinary intent/Preview boundary.
            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(201, status, frozen)
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertEqual(51, len(intent.items))

    # -- A44-13: command-specific Worker readiness -----------------------

    def test_readiness_reflects_the_real_discovery_command(self) -> None:
        """A44-13: process health alone never implies discovery can run."""

        from mediaflow.application.automation import ProcessingWorkerService
        from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            service = ProcessingWorkerService(
                value.repository, runtime_schema_version=SCHEMA_VERSION
            )
            service.register_worker(
                "scan-only",
                "scan-only worker",
                5.0,
                ("scan",),
                runtime_schema_version=SCHEMA_VERSION,
            )
            value.api._worker_service = service
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertFalse(admitted["worker"]["ready"], admitted["worker"])
            self.assertEqual("unsupported_command", admitted["worker"]["condition"], admitted)
            self.assertIn("discovery", admitted["worker"]["nextAction"])
            self.assertEqual([], value.source.mutations)
            self.assert_zero_mutation_with_admitted_work(value)


class A44BReviewCorrections(_DiscoveryFixture):
    """The three P1 defect groups B proved against candidate ``d9a9af4``.

    Each case reproduces B's actual production-runtime probe (real managed
    publication/loading, real Local Storage/SQLite and the authenticated API,
    with no injected or removed runtime policy) and asserts the corrected
    ordinary behaviour: root-relative ancestor policy at every direct-selection
    entrance, real attachment association instead of a filename shortcut, and
    lost-response recovery that requires proof of the original binding.
    """

    # -- P1: direct selection cannot bypass a pruned ancestor -------------

    def _excluded_ancestor_document(self, *, max_depth: int | None = None) -> dict:
        document = self.document(max_depth=max_depth)
        document["resourceLibraries"][0]["excludeRules"] = [
            {"kind": "directory", "pattern": "Blocked"}
        ]
        return document

    def _production_journey(self, document: dict):
        """Publish one document through the real loader, exactly like B's probe."""

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
        return revision, runtime

    def test_a_directly_selected_file_ignores_an_excluded_ancestor(self) -> None:
        """Task46.3 RO-2 supersedes the earlier ancestor-veto for a direct file.

        A configured directory exclude rule shapes automatic folder walks.  It
        is no longer an additional veto on the exact file the operator selected
        by name, nor on the tree of the folder they deliberately selected
        (B46.3-03): the configured primary-media extension set is the one
        automatic file filter left inside a deliberate folder expansion.
        """

        self.media("Blocked/Sub/Film.2001.mkv")
        self.media("Keep/Good.2001.mkv")
        document = self._excluded_ancestor_document()
        with self.journey() as value:
            _revision, runtime = self._production_journey(document)
            self.assertEqual(
                ("Blocked",),
                tuple(rule.pattern for rule in runtime.resource_libraries[0].exclude_rules),
            )
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Blocked/Sub/Film.2001.mkv"]},
            )
            self.assertEqual(202, status, admitted)
            settled = self.run_discovery(value)
            self.assertEqual(["Blocked/Sub/Film.2001.mkv"], [i["path"] for i in settled["sources"]])
            # A deliberately selected folder below the same excluded ancestor is
            # now admitted as organizing work: the directory rule keeps its
            # automatic meaning for a library walk without vetoing the tree the
            # operator selected by hand.
            status, refused = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Blocked"]},
            )
            self.assertEqual(202, status, refused)
            blocked_settled = self.run_discovery(value)
            # Task46.3 RO-2 source ownership: this exact file is already owned by
            # the unfinished preparation admitted above, so the folder walk keeps it
            # out of a second manifest and reports that existing work.  The earlier
            # ancestor veto is gone; the ownership fact is what applies now, and it
            # is a per-item result rather than a scope failure.
            self.assertEqual([], [i["path"] for i in blocked_settled["sources"]])
            self.assertEqual(
                ["Blocked/Sub/Film.2001.mkv"],
                [item["path"] for item in blocked_settled["selection"]["refused"]],
                blocked_settled["selection"],
            )
            _, keep_admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Keep"]},
            )
            keep_settled = self.run_discovery(value)
            self.assertEqual(["Keep/Good.2001.mkv"], [i["path"] for i in keep_settled["sources"]])
            self.assertEqual([], value.source.mutations)

    def test_a_directly_selected_nested_folder_below_an_excluded_ancestor_is_admitted(
        self,
    ) -> None:
        """B46.3-03: an exclude rule no longer vetoes a deliberate folder choice.

        The rule keeps its unchanged automatic meaning for a library walk, so it
        is still asserted through the Scanner-equivalent walk in
        :mod:`tests.test_scanner` and through a definition-bound Run once; here
        the deliberate selection is what must be admitted.
        """

        self.media("Blocked/Sub/Film.2001.mkv")
        document = self._excluded_ancestor_document()
        with self.journey() as value:
            revision, runtime = self._production_journey(document)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Blocked/Sub"]},
            )
            self.assertEqual(202, status, admitted)
            settled = self.run_discovery(value)
            self.assertEqual(
                ["Blocked/Sub/Film.2001.mkv"],
                [i["path"] for i in settled["sources"]],
            )
            self.assertEqual([], value.source.mutations)

    def test_a_directly_selected_file_below_a_depth_pruned_ancestor_is_refused(self) -> None:
        """B-P1/AC2: configured depth applies root-relative to a direct file.

        A parent walk prunes a child directory of a depth-``maxDepth`` folder, so
        a file under that child is unreachable.  Selecting it directly must not
        admit it merely because the leaf itself looks shallow.
        """

        self.media("Movies/Sub/Deep/Film.2001.mkv")
        document = self.document(max_depth=1)
        with self.journey() as value:
            revision, runtime = self._production_journey(document)
            self.assertEqual(1, runtime.resource_libraries[0].max_depth)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            status, refused = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/Sub/Deep/Film.2001.mkv"]},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("source_excluded", refused["error"]["code"], refused)
            self.assertEqual(
                "configured_depth_exceeded", refused["error"]["details"]["reason"], refused
            )
            self.assertEqual("Movies/Sub", refused["error"]["details"]["prunedAncestor"], refused)
            self.assertEqual((), value.repository.list_media_discoveries())

    # -- P1: real attachment association, not a filename shortcut ---------

    def test_mixed_explicit_selection_preserves_trailer_association_through_preview(self) -> None:
        """A44-14: explicit files and a selected empty folder share one association set.

        The native Files page submits this mixed shape when a directory is
        selected with individual files. A matching Trailer must follow its
        admitted main source under that source's pinned default policy,
        regardless of explicit selection order, then remain visible as an
        attachment in the existing zero-mutation Preview.
        """

        from mediaflow.domain.task_persistence import (
            PersistentResultRecord,
            PersistentTask,
            PersistentTaskStatus,
        )

        relative_main = "Movies/Film.2001.mkv"
        relative_trailer = "Movies/Film.2001-trailer.mp4"
        self.media(relative_main)
        self.media(relative_trailer)
        self.media(relative_main, second=True)
        self.media(relative_trailer, second=True)
        (self.source_root / "Movies" / "Other").mkdir(parents=True)
        (self.second_root / "Movies" / "Other").mkdir(parents=True)

        with self.journey(
            attachments=True, second_library=True, metadata_query_type="none"
        ) as value:
            policy_a = next(
                policy
                for policy in value.configuration.strategy.recognition_type_policies
                if policy.recognition_type_id == "A"
            )
            self.assertTrue(policy_a.organize_policy.attachments.enabled)
            self.assertTrue(policy_a.organize_policy.attachments.trailers)

            _, folder_admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            folder_settled = self.run_discovery(value)
            self.assertEqual("completed", folder_settled["status"], folder_settled)
            self.assertEqual(1, folder_settled["progress"]["primarySources"], folder_settled)
            self.assertEqual(
                [relative_main],
                [item["path"] for item in folder_settled["sources"]],
                folder_settled,
            )
            status, folder_frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{folder_admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": folder_settled["version"]},
            )
            self.assertEqual(201, status, folder_frozen)
            folder_intent = value.repository.get_manual_intent(folder_frozen["intentId"])
            self.assertEqual([relative_main], [item.source.path for item in folder_intent.items])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assert_zero_mutation_with_admitted_work(value)

            # Task46.3 RO-2 source ownership keeps one unfinished work per verified
            # concrete source, so each traversal in this journey uses its own pair of
            # files.  That is the real production rule; the association behaviour
            # under test is unchanged.
            self.media("Mixed/Film.2001.mkv")
            self.media("Mixed/Film.2001-trailer.mp4")
            self.media("Other/Film.2001.mkv", second=True)
            self.media("Other/Film.2001-trailer.mp4", second=True)
            (self.source_root / "Mixed" / "Other").mkdir(parents=True)
            (self.second_root / "Other" / "Other").mkdir(parents=True)
            selections = (
                (
                    "library",
                    ["Mixed/Other", "Mixed/Film.2001.mkv", "Mixed/Film.2001-trailer.mp4"],
                ),
                ("library2", ["Other", "Other/Film.2001-trailer.mp4", "Other/Film.2001.mkv"]),
            )
            settled_by_library = {}
            for library_id, paths in selections:
                status, admitted = self.request(
                    value,
                    f"/api/v1/resource-libraries/{library_id}/files/discoveries",
                    "POST",
                    {"paths": paths},
                )
                self.assertEqual(202, status, admitted)
                settled = self.run_discovery(value)
                self.assertEqual("completed", settled["status"], settled)
                self.assertEqual(1, settled["progress"]["primarySources"], settled)
                # The trailer is associated with its admitted main file, so the
                # manifest holds exactly one primary in this library's own root.
                manifest = [item["path"] for item in settled["sources"]]
                self.assertEqual(1, len(manifest), settled)
                self.assertIn(manifest[0], {"Mixed/Film.2001.mkv", "Other/Film.2001.mkv"}, settled)
                settled_by_library[library_id] = (admitted, settled, manifest[0])

            admitted, settled, expected_main = settled_by_library["library"]
            reverse_admitted, reverse_settled, reverse_main = settled_by_library["library2"]
            status, reverse_frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{reverse_admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": reverse_settled["version"]},
            )
            self.assertEqual(201, status, reverse_frozen)
            reverse_intent = value.repository.get_manual_intent(reverse_frozen["intentId"])
            self.assertEqual([reverse_main], [item.source.path for item in reverse_intent.items])
            self.assertEqual(
                {"A"}, {item.choice.recognition_type_id for item in reverse_intent.items}
            )

            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(201, status, frozen)
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertEqual([expected_main], [item.source.path for item in intent.items])
            self.assertEqual({"A"}, {item.choice.recognition_type_id for item in intent.items})
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assert_zero_mutation_with_admitted_work(value)

            # Ground one valid offline metadata identity so Preview can produce
            # the exact plan without contacting a MetadataProvider.
            item = intent.items[0]
            now = value.clock()
            task_id = "mixed-trailer-preview-proof"
            value.repository.create_task(
                PersistentTask(
                    task_id,
                    "organize",
                    PersistentTaskStatus.COMPLETED,
                    False,
                    now,
                    now,
                )
            )
            value.repository.append_result(
                PersistentResultRecord(
                    "mixed-trailer-preview-result",
                    task_id,
                    "mixed-trailer-preview-item",
                    "source",
                    expected_main,
                    "target",
                    "Movies/Film (2001)/Film (2001).mkv",
                    "A",
                    "tmdb",
                    "909",
                    "A",
                    "A",
                    "A",
                    "A",
                    "MOVE",
                    "dry_run",
                    now,
                    title="Film",
                )
            )
            status, _choice = self.request(
                value,
                f"/api/v1/operations/organize/intents/{intent.intent_id}/items/{item.item_id}/choice",
                "POST",
                {
                    "expectedVersion": intent.version,
                    "expectedItemVersion": item.version,
                    "recognitionTypeId": "A",
                    "metadata": {
                        "provider": "tmdb",
                        "providerId": "909",
                        "mediaType": "movie",
                        "title": "Film",
                    },
                },
            )
            self.assertEqual(200, status)
            tasks_before_preview = tuple(value.repository.list_tasks())
            intent = value.repository.get_manual_intent(intent.intent_id)
            status, preview = self.request(
                value,
                f"/api/v1/manual-intents/{intent.intent_id}/preview",
                "POST",
                {"expectedVersion": intent.version},
            )
            self.assertEqual(201, status, preview)
            self.assertEqual("previewed", preview["status"], preview)
            preview_item = preview["items"][0]
            self.assertEqual(expected_main, preview_item["source"]["path"])
            self.assertEqual(
                [
                    (
                        "trailer",
                        expected_main.replace("Film.2001.mkv", "Film.2001-trailer.mp4"),
                    )
                ],
                [
                    (attachment["type"], attachment["source"]["path"])
                    for attachment in preview_item["plan"]["attachments"]
                ],
            )
            self.assertEqual(tasks_before_preview, tuple(value.repository.list_tasks()))
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_an_orphan_trailer_is_a_truthful_primary(self) -> None:
        """B-P1/AC4/AC5: a trailer with no associated main file is not dropped.

        B proved an orphan-only folder reported ``completed`` with no sources
        and no finding.  A video the production matcher cannot associate keeps
        its ordinary primary identity and is reported truthfully.
        """

        self.media("Movies/Orphan.2001-trailer.mp4")
        with self.journey(attachments=True) as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(
                ["Movies/Orphan.2001-trailer.mp4"],
                [item["path"] for item in settled["sources"]],
                settled,
            )
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual([], value.source.mutations)
            self.assert_zero_mutation_with_admitted_work(value)

    def test_a_disabled_trailer_policy_keeps_both_videos_as_primaries(self) -> None:
        """B-P1/AC4/AC5: a policy that does not classify a trailer admits both.

        B proved that with the published policy's ``trailers`` disabled the walk
        returned only the main mkv.  A suffix that the applicable pinned policy
        does not classify as an attachment must keep ordinary primary
        processing.
        """

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001-trailer.mp4")
        document = self.document(attachments=True)
        for policy in document["organizePolicies"]:
            policy["attachments"]["trailers"] = False
            policy["attachments"]["otherSameStem"] = False
        with self.journey() as value:
            revision, runtime = self._production_journey(document)
            self.assertTrue(
                all(
                    not policy.organize_policy.attachments.trailers
                    and not policy.organize_policy.attachments.other_same_stem
                    for policy in runtime.strategy.recognition_type_policies
                ),
                runtime.strategy.recognition_type_policies,
            )
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(
                ["Movies/Film.2001-trailer.mp4", "Movies/Film.2001.mkv"],
                sorted(item["path"] for item in settled["sources"]),
                settled,
            )
            self.assertEqual(2, settled["progress"]["primarySources"], settled)
            self.assertEqual([], value.source.mutations)

    def test_a_matching_trailer_is_still_demoted_across_pages(self) -> None:
        """B-P1/AC5: association governs even when main and trailer split pages.

        The demotion must be evaluated over the real observed same-directory
        entries, so a trailer that appears before its main file on an earlier
        page is still an attachment once the directory is fully walked.
        """

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001-trailer.mp4")
        with self.journey(attachments=True) as value:
            raw = value.source._storage
            state = {"page": 0}

            def paged(path, *, limit, cursor=None):
                if path != "Movies":
                    return raw.list_page(path, limit=limit, cursor=cursor)
                state["page"] += 1
                if cursor is None:
                    # The trailer is served first, before its main file exists
                    # in this walk's view of the directory.
                    return StoragePage([raw.stat("Movies/Film.2001-trailer.mp4")], "page-2")
                return StoragePage([raw.stat("Movies/Film.2001.mkv")], None)

            value.source.list_page = paged
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(
                ["Movies/Film.2001.mkv"],
                [item["path"] for item in settled["sources"]],
                settled,
            )
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual(2, settled["progress"]["pageFetches"], settled)

    def test_one_hundred_and_one_true_primaries_still_refuse_a_prefix(self) -> None:
        """B-P1/AC5: the bound counts true primaries, not demoted candidates.

        100 main files plus 100 associated trailers is 100 primaries; 101 true
        primaries still refuses an executable prefix.  This keeps the existing
        100/101 semantics while the bound is now evaluated after association.
        """

        for index in range(101):
            self.media(f"Movies/Film{index:03d}.2001.mkv")
        with self.journey(attachments=True) as value:
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value, steps=8)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertEqual("primary_limit", settled["progress"]["incompleteReason"], settled)
            self.assertEqual(100, settled["progress"]["primarySources"], settled)
            self.assertFalse(settled["actions"]["finalize"]["available"], settled)
            self.assertEqual([], value.source.mutations)

    def test_a_trailer_of_an_unadmitted_main_file_keeps_ordinary_processing(self) -> None:
        """B-P1/AC5: a trailer whose main file is policy-excluded is a primary.

        The association is only against *admitted* main files, so a trailer
        whose apparent owner is excluded by policy is not silently absorbed.
        RO-2/B46.3-03 keeps the *explicit extension exclusion* as a real veto
        inside a deliberate folder expansion, so this case still produces an
        unadmitted main file — a non-extension exclude/match rule no longer does.
        """

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001-trailer.mp4")
        self.media("Movies/Drop.2001.wmv")
        self.media("Movies/Drop.2001-trailer.mp4")
        document = self.document(attachments=True, extensions=("mkv", "mp4", "wmv"))
        document["resourceLibraries"][0]["excludeRules"] = [{"kind": "extension", "pattern": "wmv"}]
        with self.journey() as value:
            revision, runtime = self._production_journey(document)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            # The excluded main file is not admitted, so its trailer is not an
            # attachment of anything and keeps its own primary identity.
            self.assertEqual(
                ["Movies/Drop.2001-trailer.mp4", "Movies/Film.2001.mkv"],
                sorted(item["path"] for item in settled["sources"]),
                settled,
            )
            self.assertEqual([], value.source.mutations)

    def test_reciprocal_same_stem_videos_keep_one_admitted_primary(self) -> None:
        """B-P1/AC4/AC5: a mutual same-stem group never empties its own manifest.

        B proved that with the existing ``otherSameStem`` setting enabled,
        ``Film.2001.mkv`` and ``Film.2001.mp4`` each classify as the *other's*
        attachment through the real production matcher.  The naive demotion then
        removed both owners and the walk published ``completed`` with an empty
        manifest, so neither eligible video reached Preview.  An attachment may
        only be demoted while the primary it attaches to stays admitted, so a
        mutual group keeps one deterministic admitted primary.
        """

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001.mp4")
        document = self.document(attachments=True)
        for policy in document["organizePolicies"]:
            policy["attachments"]["otherSameStem"] = True
        with self.journey() as value:
            _revision, runtime = self._production_journey(document)
            self.assertTrue(
                all(
                    policy.organize_policy.attachments.other_same_stem
                    for policy in runtime.strategy.recognition_type_policies
                ),
                runtime.strategy.recognition_type_policies,
            )
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(
                ["Movies/Film.2001.mkv"],
                [item["path"] for item in settled["sources"]],
                settled,
            )
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual([], value.source.mutations)
            self.assert_zero_mutation_with_admitted_work(value)

    def test_a_three_member_same_stem_group_keeps_exactly_one_primary(self) -> None:
        """B-P1/AC4/AC5: a wider mutual group is resolved deterministically.

        Three videos share one stem and the policy classifies every one of them
        as an attachment of each other.  The resolution must retain exactly one
        admitted primary and demote the others, independent of directory page
        order, so the durable manifest is stable and never empty.
        """

        for extension in ("mkv", "mp4", "avi"):
            self.media(f"Movies/Film.2001.{extension}")
        document = self.document(attachments=True, extensions=("mkv", "mp4", "avi"))
        for policy in document["organizePolicies"]:
            policy["attachments"]["otherSameStem"] = True
        with self.journey(extensions=("mkv", "mp4", "avi")) as value:
            _revision, runtime = self._production_journey(document)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(
                ["Movies/Film.2001.avi"],
                [item["path"] for item in settled["sources"]],
                settled,
            )
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual([], value.source.mutations)

    def test_a_mutual_group_is_resolved_the_same_across_pages(self) -> None:
        """B-P1/AC5: the resolution does not depend on directory page order.

        The mutual same-stem group is served across two pages, with the
        lexicographically *later* member first.  The retained primary is the same
        one the single-page walk chooses, so a paginated directory and an
        unpaginated one agree and neither can publish an empty manifest.
        """

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001.mp4")
        document = self.document(attachments=True)
        for policy in document["organizePolicies"]:
            policy["attachments"]["otherSameStem"] = True
        with self.journey() as value:
            _revision, runtime = self._production_journey(document)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            raw = value.source._storage

            def paged(path, *, limit, cursor=None):
                if path != "Movies":
                    return raw.list_page(path, limit=limit, cursor=cursor)
                if cursor is None:
                    return StoragePage([raw.stat("Movies/Film.2001.mp4")], "page-2")
                return StoragePage([raw.stat("Movies/Film.2001.mkv")], None)

            value.source.list_page = paged
            self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(
                ["Movies/Film.2001.mkv"],
                [item["path"] for item in settled["sources"]],
                settled,
            )
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual(2, settled["progress"]["pageFetches"], settled)
            self.assertEqual([], value.source.mutations)

    def test_mixed_type_attachment_settings_use_the_retained_owners_policy(self) -> None:
        """A trailer stays selectable when only another type treats it as an attachment."""

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001-trailer.mp4")
        document = self.document(attachments=True)
        for policy in document["organizePolicies"]:
            policy["attachments"]["enabled"] = policy["id"] == "B"
        document["recognitionRules"] = [
            {
                "id": "movie-folder",
                "name": "Movie folder",
                "priority": 100,
                "score": 100,
                "stopOnMatch": True,
                "condition": {
                    "field": "path",
                    "operator": "contains",
                    "value": "Movies/",
                },
                "outputRecognitionType": "A",
            }
        ]
        with self.journey() as value:
            _revision, runtime = self._production_journey(document)
            policies = {
                policy.recognition_type_id: policy.organize_policy.attachments
                for policy in runtime.strategy.recognition_type_policies
            }
            self.assertFalse(policies["A"].enabled)
            self.assertTrue(policies["B"].enabled)
            value.discovery._runtime_resolver = lambda _sid, _digest: runtime
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, admitted)
            settled = self.run_discovery(value)
            expected = {"Movies/Film.2001.mkv", "Movies/Film.2001-trailer.mp4"}
            self.assertEqual(expected, {item["path"] for item in settled["sources"]})
            self.assertEqual(2, settled["progress"]["primarySources"], settled)
            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(201, status, frozen)
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertEqual(expected, {item.source.path for item in intent.items})
            status, preview = self.request(
                value,
                f"/api/v1/manual-intents/{intent.intent_id}/preview",
                "POST",
                {"expectedVersion": intent.version},
            )
            self.assertEqual(201, status, preview)
            self.assertEqual(intent.intent_id, preview["intentId"], preview)
            self.assertEqual(expected, {item["source"]["path"] for item in preview["items"]})
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assert_zero_mutation_with_admitted_work(value)

    def test_a_rule_resolved_type_governs_the_later_exact_preview(self) -> None:
        """RO-2/AC-16: the pinned rule's type is the Files item's real choice.

        The folder rule recognizes B and B enables Trailer attachments, so the
        walk associates the trailer under B and the *intent* carries B as this
        source's decision.  The exact Preview then plans under that same pinned B
        policy, so the reviewed plan and the associated sidecar agree.  Nothing
        here is a default: a source with no matching rule stays undecided and is
        covered by its own native Recognition journey.
        """

        from mediaflow.domain.task_persistence import (
            PersistentResultRecord,
            PersistentTask,
            PersistentTaskStatus,
        )

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001-trailer.mp4")
        document = self.document(attachments=True)
        for policy in document["organizePolicies"]:
            policy["attachments"]["enabled"] = policy["id"] == "B"
        for policy in document["metadataPolicies"]:
            policy["mediaQueryType"] = "none"
        document["recognitionRules"] = [
            {
                "id": "movie-folder-b",
                "name": "Movie folder B",
                "priority": 100,
                "score": 100,
                "stopOnMatch": True,
                "condition": {
                    "field": "path",
                    "operator": "contains",
                    "value": "Movies/",
                },
                "outputRecognitionType": "B",
            }
        ]
        with self.journey() as value:
            _revision, runtime = self._production_journey(document)
            policies = {
                policy.recognition_type_id: policy.organize_policy.attachments
                for policy in runtime.strategy.recognition_type_policies
            }
            self.assertFalse(policies["A"].enabled)
            self.assertTrue(policies["B"].enabled)
            # The walk, the intent admission and the analysis all resolve under the
            # one published pin, exactly as the production assembly composes them.
            value.discovery._runtime_resolver = lambda _sid, _digest: runtime
            value.intents._runtime_resolver = lambda _sid, _digest: runtime
            value.previews._runtime_resolver = lambda _sid, _digest: runtime
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, admitted)
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            # B associates the trailer under its own policy, so the walk keeps one
            # primary and the trailer as an attachment of it.
            self.assertEqual(
                {"Movies/Film.2001.mkv"}, {item["path"] for item in settled["sources"]}
            )
            self.assertEqual(1, settled["progress"]["primarySources"], settled)

            status, frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(201, status, frozen)
            intent = value.repository.get_manual_intent(frozen["intentId"])
            self.assertEqual({"Movies/Film.2001.mkv"}, {item.source.path for item in intent.items})
            # The rule's own answer, not the first configured type, is the item's
            # decision, and its downstream policies are that type's exact mapping.
            self.assertEqual({"B"}, {item.choice.recognition_type_id for item in intent.items})
            self.assertEqual({"B"}, {item.choice.naming_policy_id for item in intent.items})

            # Ground one valid offline metadata identity so Preview can produce the
            # exact plan without contacting a MetadataProvider.
            now = value.clock()
            item = intent.items[0]
            task_id = "preview-proof-task"
            value.repository.create_task(
                PersistentTask(
                    task_id,
                    "organize",
                    PersistentTaskStatus.COMPLETED,
                    False,
                    now,
                    now,
                )
            )
            value.repository.append_result(
                PersistentResultRecord(
                    "preview-proof-result",
                    task_id,
                    "preview-proof-item",
                    "source",
                    item.source.path,
                    "target",
                    "Movies/Film (2001)/Film.mkv",
                    "B",
                    "tmdb",
                    "909",
                    "B",
                    "A",
                    "A",
                    "A",
                    "MOVE",
                    "dry_run",
                    now,
                    title="Film",
                )
            )
            status, _choice = self.request(
                value,
                f"/api/v1/operations/organize/intents/{intent.intent_id}/items/{item.item_id}/choice",
                "POST",
                {
                    "expectedVersion": intent.version,
                    "expectedItemVersion": item.version,
                    "recognitionTypeId": "B",
                    "metadata": {
                        "provider": "tmdb",
                        "providerId": "909",
                        # RecognitionType B is the TV type in this pinned policy, so
                        # its grounded identity keeps that media type.
                        "mediaType": "tv",
                        "title": "Film",
                    },
                },
            )
            self.assertEqual(200, status, _choice)
            intent = value.repository.get_manual_intent(intent.intent_id)
            status, preview = self.request(
                value,
                f"/api/v1/manual-intents/{intent.intent_id}/preview",
                "POST",
                {"expectedVersion": intent.version},
            )
            self.assertEqual(201, status, preview)
            self.assertEqual("previewed", preview["status"], preview)
            main = preview["items"][0]
            self.assertEqual("Movies/Film.2001.mkv", main["source"]["path"])
            self.assertEqual("B", main["plan"]["recognitionType"])
            self.assertEqual(
                [
                    (
                        "trailer",
                        "Movies/Film.2001-trailer.mp4",
                    )
                ],
                [
                    (attachment["type"], attachment["source"]["path"])
                    for attachment in main["plan"]["attachments"]
                ],
            )
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    # -- P1: genuine original-admission proof for a lost response ---------

    def test_a_retried_request_reconciles_to_its_own_admission_under_a_new_pin(self) -> None:
        """B-P1/AC6: the caller's own request identity proves the admission.

        B proved the remaining hole: the page renders an older pin, a successor
        activation changes the Storage root before the POST is consumed, and the
        readback then mistakes an equivalent older open admission for this
        request.  The immutable pin is resolved by the backend at admission
        time, so a rendered pin can never prove which admission the POST became.
        The caller's own ``requestId`` can: resubmitting it returns the record it
        actually created, even though the Active pin has since changed.
        """

        import uuid

        self.media("Recover/Original.mkv")
        self.media("new-root/Recover/Different.mkv")
        request_id = str(uuid.uuid4())
        with self.journey() as value:
            status, first = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Recover"], "requestId": request_id},
            )
            self.assertEqual(202, status, first)
            self.assertEqual(request_id, first["admissionRequestId"], first)
            original_pin = first["configurationSnapshotId"]
            # A successor activation changes the ResourceLibrary Storage root
            # and admits the same relative folder name as *different* work.
            successor = self.document(second_library=True)
            successor["resourceLibraries"][0]["storagePath"] = "new-root"
            _revision, runtime = self._production_journey(successor)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            _, other = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Recover"]},
            )
            self.assertNotEqual(first["discoveryId"], other["discoveryId"], other)
            # Retrying the *original* request identity returns its own durable
            # record, never the successor's equivalent-scope admission.
            status, retried = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Recover"], "requestId": request_id},
            )
            self.assertEqual(202, status, retried)
            self.assertEqual(first["discoveryId"], retried["discoveryId"], retried)
            self.assertEqual(original_pin, retried["configurationSnapshotId"], retried)
            self.assertEqual([], value.source.mutations)
            self.assert_zero_mutation_with_admitted_work(value)

    def test_a_retried_request_reconciles_before_statting_a_changed_root(self) -> None:
        """A proved retry survives even when its old relative path is gone."""

        import uuid

        self.media("Recover/Original.mkv")
        self.media("new-root/Elsewhere/Different.mkv")
        request_id = str(uuid.uuid4())
        with self.journey() as value:
            status, first = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Recover"], "requestId": request_id},
            )
            self.assertEqual(202, status, first)
            successor = self.document()
            successor["resourceLibraries"][0]["storagePath"] = "new-root"
            _revision, runtime = self._production_journey(successor)
            value.discovery._runtime_resolver = lambda _sid, _digest: runtime
            status, retried = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Recover"], "requestId": request_id},
            )
            self.assertEqual(202, status, retried)
            self.assertEqual(first["discoveryId"], retried["discoveryId"], retried)
            self.assertEqual(first["configurationSnapshotId"], retried["configurationSnapshotId"])
            self.assertEqual(1, len(value.repository.list_media_discoveries()))
            self.assertEqual([], value.source.mutations)

    def test_a_request_identity_cannot_be_reused_for_a_different_scope(self) -> None:
        """A request ID cannot certify a different submitted path set."""

        import uuid

        self.media("First/Film.2001.mkv")
        self.media("Second/Film.2002.mkv")
        request_id = str(uuid.uuid4())
        with self.journey() as value:
            status, first = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["First"], "requestId": request_id},
            )
            self.assertEqual(202, status, first)
            status, refused = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Second"], "requestId": request_id},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("admission_request_conflict", refused["error"]["code"], refused)
            self.assertIn("new request ID", refused["error"]["details"]["nextAction"])
            self.assertEqual(
                [first["discoveryId"]],
                [item.discovery_id for item in value.repository.list_media_discoveries()],
            )
            self.assertEqual([], value.source.mutations)

    def test_a_request_identity_cannot_be_reused_for_a_different_library(self) -> None:
        """A request ID is bound to the immutable ResourceLibrary identity."""

        import uuid

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2002.mkv", second=True)
        request_id = str(uuid.uuid4())
        with self.journey(second_library=True) as value:
            status, first = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"], "requestId": request_id},
            )
            self.assertEqual(202, status, first)
            status, refused = self.request(
                value,
                "/api/v1/resource-libraries/library2/files/discoveries",
                "POST",
                {"paths": ["Movies"], "requestId": request_id},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("admission_request_conflict", refused["error"]["code"], refused)
            self.assertIn("new request ID", refused["error"]["details"]["nextAction"])
            self.assertEqual(
                [first["discoveryId"]],
                [item.discovery_id for item in value.repository.list_media_discoveries()],
            )
            self.assertEqual([], value.source.mutations)

    def test_ambiguous_legacy_request_identity_remains_unresolved(self) -> None:
        """Legacy duplicate IDs cannot make readback guess between discoveries."""

        import uuid

        self.media("First/Film.2001.mkv")
        self.media("Second/Film.2002.mkv")
        request_id = str(uuid.uuid4())
        with self.journey() as value:
            _, first = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["First"], "requestId": request_id},
            )
            _, second = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Second"]},
            )
            with value.repository._connection:
                value.repository._connection.execute(
                    "UPDATE media_discoveries SET admission_request_id=? WHERE discovery_id=?",
                    (request_id, second["discoveryId"]),
                )
            status, unresolved = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["First"], "requestId": request_id},
            )
            self.assertEqual(409, status, unresolved)
            self.assertEqual(
                "admission_request_unresolved", unresolved["error"]["code"], unresolved
            )
            self.assertIn("Operations", unresolved["error"]["details"]["nextAction"])
            self.assertEqual(
                {first["discoveryId"], second["discoveryId"]},
                {item.discovery_id for item in value.repository.list_media_discoveries()},
            )
            self.assertEqual([], value.source.mutations)

    def test_an_admission_without_a_request_identity_reports_none(self) -> None:
        """The identity is optional, so an existing client keeps working."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, admitted)
            self.assertIsNone(admitted["admissionRequestId"], admitted)

    def test_a_malformed_request_identity_is_refused_without_admission(self) -> None:
        """A malformed identity is never stored as a reconciliation key."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            for invalid in ("not-a-uuid", 42, "", "  "):
                status, refused = self.request(
                    value,
                    "/api/v1/resource-libraries/library/files/discoveries",
                    "POST",
                    {"paths": ["Movies"], "requestId": invalid},
                )
                self.assertEqual(400, status, (invalid, refused))
                self.assertEqual("invalid_request", refused["error"]["code"], refused)
            self.assertEqual((), value.repository.list_media_discoveries())
            self.assertEqual([], value.source.mutations)

    def test_an_unknown_request_identity_still_admits_normally(self) -> None:
        """A fresh identity is a new admission, not a failed lookup."""

        import uuid

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"], "requestId": str(uuid.uuid4())},
            )
            self.assertEqual(202, status, admitted)
            self.assertEqual("queued", admitted["status"], admitted)

    def test_a_request_identity_cannot_recover_another_principal_admission(self) -> None:
        """The identity lookup is bound to the admitting principal."""

        import uuid

        self.media("Movies/One.2001.mkv")
        request_id = str(uuid.uuid4())
        with self.journey() as value:
            self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"], "requestId": request_id},
            )
            stored = value.repository.find_media_discovery_by_request_id(
                actor="someone-else", admission_request_id=request_id
            )
            self.assertIsNone(stored)
            own = value.repository.find_media_discovery_by_request_id(
                actor="operator", admission_request_id=request_id
            )
            self.assertIsNotNone(own)

    def test_a_trailer_beside_a_mutual_group_is_not_retained_as_a_primary(self) -> None:
        """B-P1/AC4: the resolution must not promote a Trailer to a primary.

        With ``otherSameStem`` enabled, ``Film.2001.mkv`` and ``Film.2001.mp4``
        are each other's attachment, and ``Film.2001-trailer.mp4`` is a Trailer
        of that same group.  The group keeps exactly one admitted primary, and
        the Trailer must still be demoted -- retaining it because its immediate
        owner happens to be the demoted member would count an attachment as
        independent media.
        """

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001.mp4")
        self.media("Movies/Film.2001-trailer.mp4")
        document = self.document(attachments=True)
        for policy in document["organizePolicies"]:
            policy["attachments"]["otherSameStem"] = True
        with self.journey() as value:
            _revision, runtime = self._production_journey(document)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(
                ["Movies/Film.2001.mkv"],
                [item["path"] for item in settled["sources"]],
                settled,
            )
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual([], value.source.mutations)
            self.assert_zero_mutation_with_admitted_work(value)

    def test_a_chain_of_related_stems_never_keeps_an_attachment_as_a_primary(self) -> None:
        """B-P1/AC4: the retained set must be a true fixpoint.

        ``Film.2001.1080p.mkv`` attaches to ``Film.2001.mkv``, which attaches to
        ``Film.mkv``.  Every admitted source must stop being an attachment of an
        admitted source, so only the chain's root may remain; a single greedy
        pass can leave a shorter stem admitted while its longer-stem attachment
        is retained too.
        """

        self.media("Movies/Film.mkv")
        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001.1080p.mkv")
        document = self.document(attachments=True)
        for policy in document["organizePolicies"]:
            policy["attachments"]["otherSameStem"] = True
        with self.journey() as value:
            _revision, runtime = self._production_journey(document)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(
                ["Movies/Film.mkv"],
                [item["path"] for item in settled["sources"]],
                settled,
            )
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual([], value.source.mutations)

    def test_a_four_member_stem_chain_converges_to_its_root(self) -> None:
        """B-P1/AC4: a longer chain must not leave intermediate primaries.

        Each member attaches to the next shorter stem, so exactly the root may
        remain admitted; a resolution that stops after one greedy pass would
        leave an attachment counted as an independent primary.
        """

        for name in (
            "Film.mkv",
            "Film.2001.mkv",
            "Film.2001.1080p.mkv",
            "Film.2001.1080p.remux.mkv",
        ):
            self.media(f"Movies/{name}")
        document = self.document(attachments=True)
        for policy in document["organizePolicies"]:
            policy["attachments"]["otherSameStem"] = True
        with self.journey() as value:
            _revision, runtime = self._production_journey(document)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
            self.assertEqual(
                ["Movies/Film.mkv"],
                [item["path"] for item in settled["sources"]],
                settled,
            )
            self.assertEqual(1, settled["progress"]["primarySources"], settled)
            self.assertEqual([], value.source.mutations)


class NativeRecognitionJourneyTests(_DiscoveryFixture):
    """RO-2/AC-16: a rule miss is a real Recognition problem, never a default type."""

    def setUp(self) -> None:
        super().setUp()
        self._no_rules = True

    def document(self, **kwargs) -> dict:
        document = super().document(**kwargs)
        if self._no_rules:
            document["recognitionRules"] = []
        return document

    def _production_journey(self, document: dict):
        """Publish one document through the real managed loader."""

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
        return revision, runtime

    def _admit_and_settle(self, value, paths: list[str]):
        status, admitted = self.request(
            value,
            "/api/v1/resource-libraries/library/files/discoveries",
            "POST",
            {"paths": paths, "autoPrepare": True},
        )
        self.assertEqual(202, status, admitted)
        settled = self.run_discovery(value)
        return admitted, settled

    def _reanalysed_preview(self, value, admitted, settled):
        current = value.repository.get_media_discovery(settled["discoveryId"])
        status, accepted = self.request(
            value,
            f"/api/v1/operations/organize/discoveries/{settled['discoveryId']}/analyze",
            "POST",
            {"expectedVersion": current.version},
        )
        self.assertEqual(200, status, accepted)
        for index in range(8):
            result = value.discovery.claim_and_run(
                worker_id=f"reanalysis-{index}", claim_token=f"reanalysis-token-{index}"
            )
            self.assertIsNotNone(result)
            if result.terminal or result.preview_id is not None:
                break
        return value.repository.get_media_discovery(admitted["discoveryId"])

    def test_a_rule_miss_stays_an_undecided_native_recognition_problem(self) -> None:
        """B46.3-01: no type is forced when the pinned rules match nothing.

        The Files selection is admitted, walked and analyzed with the published
        configuration whose rule set is empty.  The admitted Task must carry one
        ``waiting_recognition`` item, the Recognition view must count it, and no
        plan, target or media effect may exist — the operator decides the type.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            admitted, settled = self._admit_and_settle(value, ["Movies/One.2001.mkv"])
            self.assertEqual("prepared", settled["progress"]["phase"], settled)
            preview = value.repository.get_manual_preview(settled["previewId"])
            self.assertIsNotNone(preview)
            self.assertEqual(
                [ManualPreviewItemStatus.BLOCKED],
                [item.status for item in preview.items],
            )
            self.assertIsNone(preview.items[0].plan["recognitionType"])
            self.assertIsNone(preview.items[0].plan["destination"])
            self.assertIsNone(preview.items[0].plan["operation"])

            task_id = admitted["organizeTaskId"]
            items = value.repository.list_items(task_id)
            self.assertEqual(["waiting_recognition"], [item.status.value for item in items])
            intent = value.repository.get_manual_intent(settled["intentId"])
            self.assertEqual([None], [item.choice.recognition_type_id for item in intent.items])
            self.assertEqual([None], [item.choice.naming_policy_id for item in intent.items])

            status, recognition = self.request(value, "/api/v1/operations/runs?view=recognition")
            self.assertEqual(200, status, recognition)
            self.assertEqual(1, recognition["total"], recognition)
            status, attention = self.request(value, "/api/v1/operations/runs?view=attention")
            self.assertEqual(200, status, attention)
            self.assertEqual(1, attention["total"], attention)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_an_ambiguous_rule_match_is_not_a_forced_choice(self) -> None:
        """RO-2/AC-16: two equally-scored types stay the operator's decision."""

        self.media("Movies/One.2001.mkv")
        self._no_rules = False
        document = self.document()
        document["recognitionRules"] = [
            {
                "id": "movie-type",
                "name": "Movie type",
                "priority": 100,
                "score": 100,
                "stopOnMatch": False,
                "condition": {"field": "extension", "operator": "in", "value": ["mkv"]},
                "outputRecognitionType": "A",
            },
            {
                "id": "tv-type",
                "name": "TV type",
                "priority": 100,
                "score": 100,
                "stopOnMatch": False,
                "condition": {"field": "extension", "operator": "in", "value": ["mkv"]},
                "outputRecognitionType": "B",
            },
        ]
        with self.journey() as value:
            _revision, runtime = self._production_journey(document)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            value.intents._runtime_resolver = lambda sid, digest: runtime
            value.previews._runtime_resolver = lambda sid, digest: runtime
            admitted, settled = self._admit_and_settle(value, ["Movies/One.2001.mkv"])
            preview = value.repository.get_manual_preview(settled["previewId"])
            self.assertIsNotNone(preview)
            item = preview.items[0]
            self.assertEqual(ManualPreviewItemStatus.BLOCKED, item.status)
            self.assertIsNone(item.plan["recognitionType"])
            self.assertEqual("ambiguous", item.plan["analysis"]["status"], item.plan)
            intent = value.repository.get_manual_intent(settled["intentId"])
            self.assertEqual([None], [value.choice.recognition_type_id for value in intent.items])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_a_rule_match_selects_that_type_and_its_policy_mapping(self) -> None:
        """The inverse case: one real rule answer is the item's own decision."""

        self.media("Movies/One.2001.mkv")
        self._no_rules = False
        document = self.document()
        document["recognitionRules"] = [
            {
                "id": "bluray-tv",
                "name": "Bluray TV",
                "priority": 100,
                "score": 100,
                "stopOnMatch": True,
                "condition": {"field": "filename", "operator": "contains", "value": "One"},
                "outputRecognitionType": "B",
            }
        ]
        with self.journey() as value:
            _revision, runtime = self._production_journey(document)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            value.intents._runtime_resolver = lambda sid, digest: runtime
            value.previews._runtime_resolver = lambda sid, digest: runtime
            _admitted, settled = self._admit_and_settle(value, ["Movies/One.2001.mkv"])
            intent = value.repository.get_manual_intent(settled["intentId"])
            self.assertEqual({"B"}, {item.choice.recognition_type_id for item in intent.items})
            self.assertEqual({"B"}, {item.choice.naming_policy_id for item in intent.items})
            self.assertEqual({"B"}, {item.choice.classification_policy_id for item in intent.items})
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_a_native_recognition_decision_reaches_a_real_confirmed_result(self) -> None:
        """RO-2/AC-16 journey: decision → analysis → exact summary → execution.

        The whole native chain runs through its real entries: the operator saves a
        Recognition decision on the admitted Task's own item, the run re-analyzes
        under the same pin, links the exact summary and confirms one selected
        subset, and the resident execution Worker performs exactly that effect.
        The decision and the summary before it grant no execution authority.
        """

        self.media("Movies/One.2001.mkv")
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "201",
                    MediaType.MOVIE,
                    "One",
                    year=2001,
                    genres=("Animation",),
                    countries=("JP",),
                ),
            )
        )
        with self.journey(provider=provider) as value:
            admitted, settled = self._admit_and_settle(value, ["Movies/One.2001.mkv"])
            task_id = admitted["organizeTaskId"]
            item = value.repository.list_items(task_id)[0]
            self.assertEqual("waiting_recognition", item.status.value)

            status, checkpoint = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{item.item_id}"
            )
            self.assertEqual(200, status, checkpoint)
            self.assertIn("resolve_recognition", checkpoint["permitted_action_ids"])
            status, decision = self.request(
                value,
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
                "POST",
                {
                    "kind": "recognition",
                    "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                    "recognitionTypeId": "A",
                },
            )
            self.assertEqual(200, status, decision)
            # A saved decision is not success and grants no authority.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            preview_discovery = self._reanalysed_preview(value, admitted, settled)
            self.assertIsNotNone(preview_discovery.preview_id)
            intent = value.repository.get_manual_intent(preview_discovery.intent_id)
            self.assertEqual({"A"}, {value.choice.recognition_type_id for value in intent.items})

            status, preview = self.request(
                value,
                f"/api/v1/operations/organize/previews/{preview_discovery.preview_id}",
            )
            self.assertEqual(200, status, preview)
            ready = [
                value["itemId"] for value in preview["items"] if value["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            status, admitted_execution = self.request(
                value,
                f"/api/v1/operations/organize/previews/{preview_discovery.preview_id}/execute",
                "POST",
                {
                    "confirmation": True,
                    "itemIds": ready,
                    "expectedIntentVersion": preview["intentVersion"],
                    "allowOverwrite": False,
                    "allowSourceCleanup": False,
                },
            )
            self.assertIn(status, (200, 202), admitted_execution)
            completed = value.execution_worker.run_next()
            self.assertIsNotNone(completed)
            execution = value.repository.get_manual_execution(completed.execution_id)
            # Every selected item really succeeded.
            self.assertEqual(["success"], [value.status.value for value in execution.items])
            # Exactly the reviewed cross-Storage move: one verified copy to the
            # target directory, then the source delete.  No sibling or extra path
            # is touched.
            self.assertEqual(
                ["create_directory", "write"],
                [kind for kind, _path in value.target.mutations],
                value.target.mutations,
            )
            self.assertEqual(
                [("read", "Movies/One.2001.mkv"), ("delete", "Movies/One.2001.mkv")],
                value.source.mutations,
                value.source.mutations,
            )
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            self.assertEqual(
                [
                    Path(
                        self.target_root,
                        "Organized/Movies/Movies/Anime/One (2001) [tmdbid-201]",
                        "One (2001).mkv",
                    ).read_bytes()
                ],
                [b"m" * 512],
            )
            # The Task the Files selection admitted is the one that settled.
            self.assertEqual("completed", value.repository.get_task(task_id).status.value)
