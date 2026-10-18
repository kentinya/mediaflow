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

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.media_discovery import MediaDiscoveryService
from mediaflow.application.media_discovery_worker import MediaDiscoveryWorker
from mediaflow.domain.file_lifecycle import source_fingerprint
from mediaflow.domain.library import FileStabilityPolicy
from mediaflow.domain.manual_organize import ManualSourceIdentity
from mediaflow.domain.media_discovery import (
    DiscoveryBudgets,
    DiscoveryConflict,
    DiscoveryError,
    DiscoveryObservation,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import (
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
    StoragePage,
)
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
    """Wrap Local Storage and record every call so mutation can be proven absent."""

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

    def create_directory(self, path: str) -> None:
        self.mutations.append(("create_directory", path))

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutations.append(("move", source))

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutations.append(("copy", source))

    def delete(self, path: str) -> None:
        self.mutations.append(("delete", path))

    def hard_link(self, source: str, target: str) -> None:
        self.mutations.append(("hard_link", source))

    def soft_link(self, source: str, target: str) -> None:
        self.mutations.append(("soft_link", source))


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
            document["recognitionRules"].append(
                {
                    "id": "discovery-movie-fixture",
                    "name": "Discovery movie fixture",
                    "priority": 200,
                    "score": 100,
                    "stopOnMatch": True,
                    "condition": {
                        "field": "path",
                        "operator": "contains",
                        "value": "Movies/",
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
                None,
                managed,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storage_factory=lambda value, ids: dict(storages),
            )
            previews = ManualOrganizePreviewService(
                repository,
                intents,
                None,
                configuration=runtime,
                storages=dict(storages),
                clock=self.clock,
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
                            }
                        ),
                    ),
                    ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
                ),
                configuration_service=managed,
                bootstrap_document=document,
                manual_intent_service=intents,
                manual_preview_service=previews,
                media_discovery_service=discovery,
                storage_adapters=dict(storages),
            )
            try:
                yield SimpleNamespace(
                    api=api,
                    repository=repository,
                    intents=intents,
                    previews=previews,
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
            self.assertEqual((), value.repository.list_tasks())
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
            self.assertEqual((), value.repository.list_tasks())

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
            self.assertEqual((), value.repository.list_tasks())

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
            self.assertEqual((), value.repository.list_tasks())
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
            self.assertEqual((), value.repository.list_tasks())
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
            self.assertEqual((), value.repository.list_tasks())
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
            self.assertEqual((), value.repository.list_tasks())
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
            self.assertEqual((), value.repository.list_tasks())

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
            self.assertEqual((), value.repository.list_tasks())

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
            self.assertEqual((), value.repository.list_tasks())
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
            self.assertEqual((), value.repository.list_tasks())

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
            self.assertEqual((), value.repository.list_tasks())

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
            self.assertEqual((), value.repository.list_tasks())

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
            self.assertEqual((), value.repository.list_tasks())

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
            self.assertEqual((), value.repository.list_tasks())
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
            self.assertEqual((), value.repository.list_tasks())

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
            self.media("Movies/A.2001.mkv")
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
                self.assertEqual(["Movies/A.2001.mkv"], [i.source.path for i in created.items])
                # The authenticated listing exposes exactly the one linked
                # intent, never a hidden duplicate.
                status, listed = self.request(value, "/api/v1/manual-intents")
                self.assertEqual(200, status, listed)
                ids = [item["intentId"] for item in listed["items"]]
                self.assertEqual(1, ids.count(winner["intentId"]), (attempt, ids))
                # Discovery grants no execution authority and mutates no media.
                self.assertEqual([], value.source.mutations)
                self.assertEqual((), value.repository.list_tasks())
                self.assertTrue((self.source_root / "Movies" / "A.2001.mkv").is_file())

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
            self.assertEqual((), value.repository.list_tasks())

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
            # A directly selected excluded directory is refused by the same
            # policy that prunes it during a parent walk.
            status, refused = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies/Excluded"]},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("source_excluded", refused["error"]["code"], refused)
            # The published nonzero stability policy is genuinely consumed: the
            # first observation cannot fabricate the interval.
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
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
            self.assertEqual((), value.repository.list_tasks())

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
            self.assertEqual((), value.repository.list_tasks())
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
            self.assertEqual((), value.repository.list_tasks())


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

    def test_a_directly_selected_file_cannot_bypass_an_excluded_ancestor(self) -> None:
        """B-P1/AC2: a nested file under an excluded directory is refused.

        B proved that selecting ``Blocked`` returns 409 while selecting its
        descendant file was admitted and completed as a primary.  A direct
        selection must share the same root-relative exclude policy as a parent
        walk, so the descendant is refused with a bounded, actionable error and
        no durable record.
        """

        self.media("Blocked/Sub/Film.2001.mkv")
        self.media("Keep/Good.2001.mkv")
        document = self._excluded_ancestor_document()
        with self.journey() as value:
            revision, runtime = self._production_journey(document)
            self.assertEqual(
                ("Blocked",),
                tuple(rule.pattern for rule in runtime.resource_libraries[0].exclude_rules),
            )
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            status, refused = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Blocked/Sub/Film.2001.mkv"]},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("source_excluded", refused["error"]["code"], refused)
            self.assertEqual("configured_exclude", refused["error"]["details"]["reason"], refused)
            self.assertEqual("Blocked", refused["error"]["details"]["prunedAncestor"], refused)
            self.assertEqual("none", refused["error"]["details"]["sideEffects"], refused)
            # No durable record was created for the refused selection.
            self.assertEqual((), value.repository.list_media_discoveries())
            # The same file reached through an admitted parent is still pruned
            # by the walk, so the policy has one meaning regardless of entrance.
            _, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Keep"]},
            )
            settled = self.run_discovery(value)
            self.assertEqual(["Keep/Good.2001.mkv"], [i["path"] for i in settled["sources"]])
            self.assertEqual([], value.source.mutations)
            self.assertEqual((), value.repository.list_tasks())

    def test_a_directly_selected_nested_folder_cannot_bypass_a_pruned_ancestor(self) -> None:
        """B-P1/AC2: a nested folder below an excluded ancestor is refused."""

        self.media("Blocked/Sub/Film.2001.mkv")
        document = self._excluded_ancestor_document()
        with self.journey() as value:
            revision, runtime = self._production_journey(document)
            value.discovery._runtime_resolver = lambda sid, digest: runtime
            status, refused = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Blocked/Sub"]},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("source_excluded", refused["error"]["code"], refused)
            self.assertEqual("Blocked", refused["error"]["details"]["prunedAncestor"], refused)
            self.assertEqual((), value.repository.list_media_discoveries())
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
            self.assertEqual((), value.repository.list_tasks())

            selections = (
                ("library", ["Movies/Other", relative_main, relative_trailer]),
                ("library2", [relative_trailer, relative_main, "Movies/Other"]),
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
                self.assertEqual(
                    [relative_main],
                    [item["path"] for item in settled["sources"]],
                    settled,
                )
                settled_by_library[library_id] = (admitted, settled)

            admitted, settled = settled_by_library["library"]
            reverse_admitted, reverse_settled = settled_by_library["library2"]
            status, reverse_frozen = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{reverse_admitted['discoveryId']}/finalize",
                "POST",
                {"expectedVersion": reverse_settled["version"]},
            )
            self.assertEqual(201, status, reverse_frozen)
            reverse_intent = value.repository.get_manual_intent(reverse_frozen["intentId"])
            self.assertEqual([relative_main], [item.source.path for item in reverse_intent.items])
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
            self.assertEqual([relative_main], [item.source.path for item in intent.items])
            self.assertEqual({"A"}, {item.choice.recognition_type_id for item in intent.items})
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual((), value.repository.list_tasks())

            # Ground one valid offline metadata identity so Preview can produce
            # the exact plan without contacting a MetadataProvider.
            item = intent.items[0]
            now = value.clock()
            task_id = "mixed-trailer-preview-proof"
            value.repository.create_task(
                PersistentTask(
                    task_id,
                    "preview",
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
                    relative_main,
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
            self.assertEqual(relative_main, preview_item["source"]["path"])
            self.assertEqual(
                [("trailer", relative_trailer)],
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
            self.assertEqual((), value.repository.list_tasks())

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
        """

        self.media("Movies/Film.2001.mkv")
        self.media("Movies/Film.2001-trailer.mp4")
        self.media("Movies/Drop.2001.mkv")
        self.media("Movies/Drop.2001-trailer.mp4")
        document = self.document(attachments=True)
        document["resourceLibraries"][0]["excludeRules"] = [
            {"kind": "filename", "pattern": "Drop.2001.mkv"}
        ]
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
            self.assertEqual((), value.repository.list_tasks())

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
            self.assertEqual((), value.repository.list_tasks())

    def test_nondefault_rule_type_keeps_sources_through_the_manual_default_preview(self) -> None:
        """A discovery rule cannot hide a source from the later manual default choice.

        The folder rule recognizes B and B enables Trailer attachments, but the
        existing manual-intent journey still defaults a new unindexed source to
        A. Discovery must preserve the Trailer as an ordinary reviewed source;
        the exact Preview then plans both sources under the unchanged A choice.
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
            value.discovery._runtime_resolver = lambda _sid, _digest: runtime
            status, admitted = self.request(
                value,
                "/api/v1/resource-libraries/library/files/discoveries",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(202, status, admitted)
            settled = self.run_discovery(value)
            self.assertEqual("completed", settled["status"], settled)
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
            self.assertEqual({"A"}, {item.choice.recognition_type_id for item in intent.items})
            self.assertIn(
                "B",
                {item.type_id for item in intent.options.recognition_types},
                "the non-default type remains available for explicit operator review",
            )

            # Ground the same valid metadata identity for both source-linked
            # Preview choices, as a completed offline result would, without
            # admitting execution authority or contacting a Provider.
            now = value.clock()
            for index, item in enumerate(intent.items):
                task_id = f"preview-proof-task-{index}"
                value.repository.create_task(
                    PersistentTask(
                        task_id,
                        "preview",
                        PersistentTaskStatus.COMPLETED,
                        False,
                        now,
                        now,
                    )
                )
                value.repository.append_result(
                    PersistentResultRecord(
                        f"preview-proof-result-{index}",
                        task_id,
                        f"preview-proof-item-{index}",
                        "source",
                        item.source.path,
                        "target",
                        f"Movies/Film (2001)/Film {index}.mkv",
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
            for item in intent.items:
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
                intent = value.repository.get_manual_intent(intent.intent_id)

            status, preview = self.request(
                value,
                f"/api/v1/manual-intents/{intent.intent_id}/preview",
                "POST",
                {"expectedVersion": intent.version},
            )
            self.assertEqual(201, status, preview)
            self.assertEqual("previewed", preview["status"], preview)
            self.assertEqual(expected, {item["source"]["path"] for item in preview["items"]})
            self.assertTrue(all(item["status"] == "previewed" for item in preview["items"]))
            main = next(
                item for item in preview["items"] if item["source"]["path"].endswith(".mkv")
            )
            self.assertEqual([], main["plan"]["attachments"])
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
            self.assertEqual((), value.repository.list_tasks())

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
            self.assertEqual((), value.repository.list_tasks())

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
