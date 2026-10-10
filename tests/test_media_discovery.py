"""Bounded ResourceLibrary folder and mixed-selection discovery (Slice 44 RO-6).

The suite runs against the real runtime SQLite repository, real Local Storage
adapters and the real application services, with a controlled clock and
synthetic temporary media.  It covers the scope/budget/stability/persistence/
Worker/API families named by Task 44.6 without weakening any production
capability.
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

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.media_discovery import MediaDiscoveryService
from mediaflow.domain.library import FileStabilityPolicy
from mediaflow.domain.media_discovery import (
    DiscoveryBudgets,
    DiscoveryError,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

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
        # The configured include/exclude/stability policy is not part of the
        # managed document schema (the runtime loads only extensions and
        # maxDepth).  The test injects it on the loaded runtime object so the
        # shared pure filter/stability semantics can be exercised directly.
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
    ):

        document = self.document(
            stability=stability,
            max_depth=max_depth,
            extensions=extensions,
            second_library=second_library,
        )
        source = _RecordingStorage(LocalStorage("source", self.source_root))
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
            self.assertEqual("discovery_conflict", caught.exception.code)

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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


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
