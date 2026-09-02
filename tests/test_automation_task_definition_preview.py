from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.automation_task_definition_preview import (
    AutomationTaskDefinitionPreviewService,
)
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize_preview import PreviewReadOnlyStorage
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.read_only_storage import ReadOnlyStorageMutationError
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.automation import AutomationTaskDefinition
from mediaflow.domain.automation_task_definition_preview import (
    AutomationTaskDefinitionPreviewError,
    AutomationTaskDefinitionPreviewItemStatus,
    AutomationTaskDefinitionPreviewStatus,
)
from mediaflow.domain.library import FileStabilityPolicy, MediaLibrary, ResourceLibrary
from mediaflow.domain.metadata import (
    MediaCandidate,
    MediaType,
    MetadataError,
    MetadataErrorCode,
)
from mediaflow.domain.organizer import ConflictStrategy, OrganizeOperationType, OrganizePolicy
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageCapabilities
from mediaflow.domain.task_persistence import PersistentTask, PersistentTaskStatus
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.runtime_configuration import (
    RuntimeConfiguration,
    StorageDefinition,
    with_managed_snapshot,
)
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import smoke_strategy_configuration
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi

SNAPSHOT_ID = "active-1"
SNAPSHOT_DIGEST = "a" * 64


def _api_request(api, path: str, *, query: str = ""):
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": "Bearer viewer-token",
    }
    result = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


def _runtime(
    source_root: Path,
    target_root: Path,
    database: Path,
    *,
    definitions: tuple[AutomationTaskDefinition, ...],
    resource_library: ResourceLibrary | None = None,
    strategy=None,
) -> RuntimeConfiguration:
    return with_managed_snapshot(
        RuntimeConfiguration(
            strategy or smoke_strategy_configuration(),
            (
                StorageDefinition("source", "local", str(source_root), "Source"),
                StorageDefinition("target", "local", str(target_root), "Target"),
            ),
            (
                resource_library
                or ResourceLibrary(
                    "special",
                    "Special",
                    "source",
                    "Media",
                ),
            ),
            (),
            (
                MediaLibrary("movies", "Movies", "target", "Movies"),
                MediaLibrary("tv", "TV", "target", "TV"),
            ),
            str(source_root / "history.jsonl"),
            str(database),
            automation_task_definitions=definitions,
        ),
        snapshot_id=SNAPSHOT_ID,
        digest=SNAPSHOT_DIGEST,
    )


def _definition(
    definition_id: str = "def-1",
    *,
    scope: str | None = "",
    limit: int = 10,
    library_id: str = "special",
) -> AutomationTaskDefinition:
    return AutomationTaskDefinition(
        definition_id,
        "Definition",
        library_id,
        scope,
        "scan-and-plan",
        interval_seconds=60,
        item_limit=limit,
    )


def _provider(
    *,
    title: str = "One",
    provider_id: str = "129",
    year: int = 2001,
    genres: tuple[str, ...] = ("Animation",),
    countries: tuple[str, ...] = ("JP",),
) -> SyntheticMetadataProvider:
    return SyntheticMetadataProvider(
        (
            MediaCandidate(
                "tmdb",
                provider_id,
                MediaType.MOVIE,
                title,
                year=year,
                genres=genres,
                countries=countries,
            ),
        )
    )


class _NoCapabilityStorage:
    """Storage double with read-only access and no mutating capabilities."""

    def __init__(self, storage, capabilities: StorageCapabilities) -> None:
        self._storage = storage
        self._capabilities = capabilities

    @property
    def storage_id(self):
        return self._storage.storage_id

    @property
    def name(self):
        return self._storage.name

    @property
    def read_only(self):
        return self._storage.read_only

    @property
    def capabilities(self):
        return self._capabilities

    def list(self, path):
        return self._storage.list(path)

    def stat(self, path):
        return self._storage.stat(path)

    def exists(self, path):
        return self._storage.exists(path)

    def read(self, path):
        return self._storage.read(path)

    def _reject(self, operation):
        raise AssertionError(f"Preview attempted mutation: {operation}")

    write = create_directory = move = copy = delete = hard_link = soft_link = _reject


class _StorageCallCounter:
    def __init__(self, storage) -> None:
        self._storage = storage
        self.calls: list[str] = []

    def __getattr__(self, name):
        value = getattr(self._storage, name)
        if name not in {
            "list",
            "stat",
            "exists",
            "read",
            "write",
            "create_directory",
            "move",
            "copy",
            "delete",
            "hard_link",
            "soft_link",
        } or not callable(value):
            return value

        def counted(*args, **kwargs):
            self.calls.append(name)
            return value(*args, **kwargs)

        return counted


class FailingMetadataProvider(SyntheticMetadataProvider):
    def __init__(self, code: MetadataErrorCode) -> None:
        super().__init__(())
        self._code = code

    def search_movie(self, query, policy=None, **kwargs):
        raise MetadataError(
            self._code,
            "apiKey=preview-secret provider request failed",
        )


class AutomationTaskDefinitionPreviewTests(unittest.TestCase):
    def _fixture(self, files: dict[str, bytes | None]):
        directory = tempfile.TemporaryDirectory()
        target_directory = tempfile.TemporaryDirectory()
        source_root = Path(directory.name)
        target_root = Path(target_directory.name)
        for relative, data in files.items():
            target = source_root / "Media" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if data is not None:
                target.write_bytes(data)
        database = source_root / "runtime.sqlite3"
        return directory, target_directory, source_root, target_root, database

    @staticmethod
    def _services(
        repository,
        configuration,
        provider,
        source_root,
        target_root,
        *,
        file_index=None,
        clock=None,
    ):
        options = {
            "file_index": file_index,
        }
        if clock is not None:
            options["clock"] = clock
        return AutomationTaskDefinitionPreviewService(
            repository,
            configuration=configuration,
            providers=MetadataProviderRegistry((provider,)),
            storages={
                "source": LocalStorage("source", source_root),
                "target": LocalStorage("target", target_root),
            },
            **options,
        )

    def test_scope_limit_reload_and_exact_identity(self):
        fixture = self._fixture(
            {
                "C/one/One.2001.mkv": b"x" * 10,
                "C/two/One.2001.mkv": b"x" * 10,
                "C/three/One.2001.mkv": b"x" * 10,
                "C/ignore.txt": b"x" * 10,
                "outside/Four.2001.mkv": b"x" * 10,
            }
        )
        directory, target_directory, source_root, target_root, database = fixture
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(scope="C", limit=2),),
        )
        provider = _provider()
        try:
            with SQLiteTaskRepository(database) as repository:
                previews = self._services(
                    repository, configuration, provider, source_root, target_root
                )
                preview = previews.create("def-1", actor="tester")
                document = preview.document()
                self.assertEqual(document["status"], "partial")
                self.assertEqual(document["definitionFingerprint"], document["definitionVersion"])
                self.assertEqual(document["configurationRevisionId"], SNAPSHOT_ID)
                self.assertEqual(document["configurationRevisionDigest"], SNAPSHOT_DIGEST)
                self.assertEqual(document["counts"]["discovered"], 4)
                self.assertEqual(document["counts"]["excludedIgnored"], 1)
                self.assertEqual(document["counts"]["selected"], 2)
                self.assertEqual(document["counts"]["permitted"], 2)
                self.assertEqual(document["counts"]["unstable"], 0)
                self.assertEqual(document["counts"]["truncatedByLimit"], 1)
                self.assertEqual(len(document["items"]), 4)
                statuses = {item["status"] for item in document["items"]}
                self.assertEqual(
                    statuses,
                    {"previewed", "truncated", "excluded"},
                )
                out_of_scope = [
                    item for item in document["items"] if "outside" in item["source"]["path"]
                ]
                self.assertEqual(out_of_scope, [])
                items, total, next_after = previews.items(preview.preview_id, limit=2)
                self.assertEqual(total, 4)
                self.assertEqual(len(items), 2)
                self.assertEqual(next_after, 2)
                items2, total2, next_after2 = previews.items(preview.preview_id, limit=2, after=2)
                self.assertEqual(len(items2), 2)
                self.assertIsNone(next_after2)
                self.assertEqual([item.position for item in items2], [2, 3])
            with SQLiteTaskRepository(database) as reopened:
                previews = self._services(
                    reopened, configuration, provider, source_root, target_root
                )
                reloaded = previews.latest_readonly("def-1")
                self.assertEqual(reloaded.document(), document)
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_recognition_type_c_stays_c_with_downstream_a_policies(self):
        fixture = self._fixture({"C/One.2001.mkv": b"x" * 10})
        directory, target_directory, source_root, target_root, database = fixture
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(),),
        )
        try:
            with SQLiteTaskRepository(database) as repository:
                previews = self._services(
                    repository, configuration, _provider(), source_root, target_root
                )
                preview = previews.create("def-1", actor="tester")
                item = preview.items[0]
                self.assertEqual(item.status, AutomationTaskDefinitionPreviewItemStatus.PREVIEWED)
                self.assertEqual(item.recognition_type_id, "C")
                self.assertEqual(item.recognition_type_policy_id, "type-C")
                self.assertEqual(item.metadata_policy_id, "C")
                self.assertEqual(item.naming_policy_id, "A")
                self.assertEqual(item.classification_policy_id, "A")
                self.assertEqual(item.organize_policy_id, "A")
                self.assertEqual(item.destination_storage_id, "target")
                self.assertIn("Movies/Anime/", item.destination_path or "")
                self.assertEqual(item.operation, "MOVE")
                self.assertEqual(item.capability_verdict, "ok")
                self.assertNotIn("secret", json.dumps(item.document()))
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_mixed_outcomes_keep_independent_state(self):
        fixture = self._fixture(
            {
                "A/One.2001.mkv": b"x" * 10,
                "C/1/One.2001.mkv": b"x" * 10,
                "C/2/One.2001.mkv": b"x" * 10,
                "C/3/One.2001.mkv": b"x" * 10,
                "C/Unstable.2001.mkv": b"x" * 10,
                "C/tr1/One.2001.mkv": b"x" * 10,
                "C/tr2/One.2001.mkv": b"x" * 10,
                "C/tr3/One.2001.mkv": b"x" * 10,
                "unknown/mystery.mkv": b"x" * 10,
                "C/ignore.txt": b"x" * 10,
            }
        )
        directory, target_directory, source_root, target_root, database = fixture
        resource_library = ResourceLibrary(
            "special",
            "Special",
            "source",
            "Media",
            stability_policy=FileStabilityPolicy(minimum_age_seconds=3600),
        )
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(scope="", limit=5),),
            resource_library=resource_library,
        )
        old = datetime(2020, 1, 1, tzinfo=UTC).timestamp()
        for relative in (
            "A/One.2001.mkv",
            "C/1/One.2001.mkv",
            "C/2/One.2001.mkv",
            "C/3/One.2001.mkv",
            "C/tr1/One.2001.mkv",
            "C/tr2/One.2001.mkv",
            "C/tr3/One.2001.mkv",
            "unknown/mystery.mkv",
            "C/ignore.txt",
        ):
            os.utime(source_root / "Media" / relative, (old, old))
        try:
            with SQLiteTaskRepository(database) as repository:
                previews = self._services(
                    repository,
                    configuration,
                    _provider(),
                    source_root,
                    target_root,
                )
                preview = previews.create("def-1", actor="tester")
                by_path = {item.source.path: item for item in preview.items}
                self.assertEqual(by_path["Media/A/One.2001.mkv"].status.value, "previewed")
                self.assertEqual(by_path["Media/C/1/One.2001.mkv"].status.value, "previewed")
                self.assertEqual(by_path["Media/C/2/One.2001.mkv"].status.value, "previewed")
                self.assertEqual(by_path["Media/C/3/One.2001.mkv"].status.value, "previewed")
                self.assertEqual(by_path["Media/unknown/mystery.mkv"].status.value, "blocked")
                self.assertEqual(by_path["Media/C/ignore.txt"].status.value, "excluded")
                self.assertEqual(by_path["Media/C/Unstable.2001.mkv"].status.value, "unstable")
                self.assertEqual(
                    {
                        item.status.value
                        for item in preview.items
                        if any(marker in item.source.path for marker in ("tr1", "tr2", "tr3"))
                    },
                    {"truncated"},
                )
                self.assertTrue(
                    all(item.next_action.strip() for item in preview.items),
                )
                self.assertEqual(preview.status, AutomationTaskDefinitionPreviewStatus.PARTIAL)
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_fail_closed_boundaries(self):
        fixture = self._fixture({"C/One.2001.mkv": b"x" * 10})
        directory, target_directory, source_root, target_root, database = fixture
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(),),
        )
        try:
            with SQLiteTaskRepository(database) as repository:
                previews = self._services(
                    repository, configuration, _provider(), source_root, target_root
                )
                with self.assertRaisesRegex(AutomationTaskDefinitionPreviewError, "was not found"):
                    previews.create("missing", actor="tester")
                with self.assertRaisesRegex(AutomationTaskDefinitionPreviewError, "revision"):
                    previews.create("def-1", actor="tester", revision_id="other")
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_disabled_library_and_missing_storage_fail_closed_without_evidence(self):
        fixture = self._fixture({"C/One.2001.mkv": b"x" * 10})
        directory, target_directory, source_root, target_root, database = fixture
        disabled_library = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(),),
            resource_library=ResourceLibrary(
                "special", "Special", "source", "Media", enabled=False
            ),
        )
        try:
            with SQLiteTaskRepository(database) as repository:
                previews = self._services(
                    repository,
                    disabled_library,
                    _provider(),
                    source_root,
                    target_root,
                )
                with self.assertRaisesRegex(
                    AutomationTaskDefinitionPreviewError, "disabled ResourceLibrary"
                ):
                    previews.create("def-1", actor="tester")
                rows = repository._connection.execute(
                    "SELECT COUNT(*) FROM automation_task_definition_previews"
                ).fetchone()[0]
                self.assertEqual(rows, 0)
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_provider_rate_limit_and_unresolved_metadata_classification(self):
        fixture = self._fixture(
            {
                "C/One.2001.mkv": b"x" * 10,
                "C/Two.2001.mkv": b"x" * 10,
                "C/Three.2001.mkv": b"x" * 10,
            }
        )
        directory, target_directory, source_root, target_root, database = fixture
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(),),
        )
        try:
            with SQLiteTaskRepository(database) as repository:
                rate_limited = self._services(
                    repository,
                    configuration,
                    FailingMetadataProvider(MetadataErrorCode.RATE_LIMITED),
                    source_root,
                    target_root,
                )
                preview = rate_limited.create("def-1", actor="tester")
                self.assertTrue(
                    any(
                        item.status is AutomationTaskDefinitionPreviewItemStatus.UNAVAILABLE
                        for item in preview.items
                    )
                )
                self.assertNotIn("preview-secret", json.dumps(preview.document()))
            with SQLiteTaskRepository(database) as repository:
                no_candidates = self._services(
                    repository,
                    configuration,
                    SyntheticMetadataProvider(()),
                    source_root,
                    target_root,
                )
                preview = no_candidates.create("def-1", actor="tester")
                self.assertTrue(
                    all(
                        item.status is AutomationTaskDefinitionPreviewItemStatus.BLOCKED
                        for item in preview.items
                    )
                )
            with SQLiteTaskRepository(database) as repository:
                unclassified = self._services(
                    repository,
                    configuration,
                    _provider(genres=(), countries=()),
                    source_root,
                    target_root,
                )
                preview = unclassified.create("def-1", actor="tester")
                self.assertTrue(
                    all(
                        item.status is AutomationTaskDefinitionPreviewItemStatus.BLOCKED
                        for item in preview.items
                    )
                )
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_conflict_manual_and_overwrite_fail_closed_per_item(self):
        fixture = self._fixture({"C/One.2001.mkv": b"x" * 10})
        directory, target_directory, source_root, target_root, database = fixture
        target = target_root / "Movies" / "Anime" / "One (2001)" / "One (2001).mkv"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"existing")
        base = smoke_strategy_configuration()
        overwrite_policy = OrganizePolicy(
            "overwrite",
            OrganizeOperationType.MOVE,
            conflict_strategy=ConflictStrategy.OVERWRITE,
        )
        custom_policies = tuple(
            replace(
                value,
                organize_policy=overwrite_policy,
            )
            if value.recognition_type_id == "C"
            else value
            for value in base.recognition_type_policies
        )
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(),),
            strategy=replace(base, recognition_type_policies=custom_policies),
        )
        try:
            with SQLiteTaskRepository(database) as repository:
                previews = self._services(
                    repository, configuration, _provider(), source_root, target_root
                )
                preview = previews.create("def-1", actor="tester")
                item = preview.items[0]
                self.assertEqual(item.status, AutomationTaskDefinitionPreviewItemStatus.BLOCKED)
                self.assertIn("conflict", item.blocker or "")
                self.assertNotEqual(json.loads(item.conflicts_json or "[]"), [])
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_unsupported_storage_capability_blocks_item_with_gap_evidence(self):
        fixture = self._fixture({"C/One.2001.mkv": b"x" * 10})
        directory, target_directory, source_root, target_root, database = fixture
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(),),
        )
        try:
            with SQLiteTaskRepository(database) as repository:
                previews = AutomationTaskDefinitionPreviewService(
                    repository,
                    configuration=configuration,
                    providers=MetadataProviderRegistry((_provider(),)),
                    storages={
                        "source": LocalStorage("source", source_root),
                        "target": _NoCapabilityStorage(
                            LocalStorage("target", target_root),
                            StorageCapabilities(),
                        ),
                    },
                )
                preview = previews.create("def-1", actor="tester")
                item = preview.items[0]
                self.assertEqual(item.status, AutomationTaskDefinitionPreviewItemStatus.BLOCKED)
                self.assertEqual(item.capability_verdict, "capability_gap")
                self.assertIn("can_copy", json.loads(item.required_capabilities_json or "[]"))
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_staleness_after_definition_edit_revision_change_and_invalidate(self):
        fixture = self._fixture({"C/One.2001.mkv": b"x" * 10})
        directory, target_directory, source_root, target_root, database = fixture
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(),),
        )
        try:
            with SQLiteTaskRepository(database) as repository:
                previews = self._services(
                    repository, configuration, _provider(), source_root, target_root
                )
                preview = previews.create("def-1", actor="tester")
                self.assertTrue(preview.current)
                previews.invalidate("def-1", "the pinned Automation Task Definition was edited")
                stale = previews.get_readonly(preview.preview_id)
                self.assertEqual(stale.status, AutomationTaskDefinitionPreviewStatus.STALE)
                self.assertFalse(stale.current)
                self.assertIn("edited", stale.stale_reason or "")
                self.assertEqual(stale.preview_id, preview.preview_id)
                fresh = previews.create("def-1", actor="tester")
            edited_configuration = _runtime(
                source_root,
                target_root,
                database,
                definitions=(_definition(limit=1),),
            )
            with SQLiteTaskRepository(database) as repository:
                previews = self._services(
                    repository, edited_configuration, _provider(), source_root, target_root
                )
                stale = previews.get_readonly(fresh.preview_id)
                self.assertEqual(stale.status, AutomationTaskDefinitionPreviewStatus.STALE)
                self.assertIn("changed", stale.stale_reason or "")
                current = previews.create("def-1", actor="tester")
            changed_revision = _runtime(
                source_root,
                target_root,
                database,
                definitions=(_definition(),),
            )
            changed_revision = replace(
                changed_revision,
                configuration_snapshot_id="active-2",
                configuration_snapshot_digest="b" * 64,
            )
            with SQLiteTaskRepository(database) as repository:
                previews = self._services(
                    repository, changed_revision, _provider(), source_root, target_root
                )
                stale = previews.get_readonly(current.preview_id)
                self.assertEqual(stale.status, AutomationTaskDefinitionPreviewStatus.STALE)
                self.assertIn("revision", stale.stale_reason or "")
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_stable_size_preview_reuses_durable_scanner_history(self):
        fixture = self._fixture({"C/One.2001.mkv": b"x" * 10})
        directory, target_directory, source_root, target_root, database = fixture
        current = [datetime(2026, 9, 1, 12, tzinfo=UTC)]
        modified_at = current[0] - timedelta(hours=1)
        source_path = source_root / "Media" / "C" / "One.2001.mkv"
        timestamp = int(modified_at.timestamp() * 1_000_000_000)
        os.utime(source_path, ns=(timestamp, timestamp))
        resource_library = ResourceLibrary(
            "special",
            "Special",
            "source",
            "Media",
            stability_policy=FileStabilityPolicy(stable_size_duration_seconds=60),
        )
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(scope="", limit=5),),
            resource_library=resource_library,
        )
        index = InMemoryFileIndexRepository()
        source = _StorageCallCounter(LocalStorage("source", source_root))
        target = _StorageCallCounter(LocalStorage("target", target_root))

        def clock():
            return current[0]

        scanner = StorageScanner({"source": source}, index, clock=clock)
        try:
            first = scanner.scan(resource_library)
            self.assertEqual(first.statistics.unstable, 1)
            current[0] += timedelta(seconds=61)
            second = scanner.scan(resource_library)
            self.assertEqual(second.statistics.media_candidates, 1)
            record = index.find_by_path("source", "special", "Media/C/One.2001.mkv")
            self.assertIsNotNone(record)
            self.assertIsNotNone(record.stable_since)
            source.calls.clear()
            target.calls.clear()
            with SQLiteTaskRepository(database) as repository:
                previews = AutomationTaskDefinitionPreviewService(
                    repository,
                    configuration=configuration,
                    providers=MetadataProviderRegistry((_provider(),)),
                    storages={"source": source, "target": target},
                    file_index=index,
                    clock=clock,
                )
                preview = previews.create("def-1", actor="tester")
                self.assertEqual(preview.status, AutomationTaskDefinitionPreviewStatus.PREVIEWED)
                self.assertEqual(preview.items[0].source.stability, "stable")
                self.assertEqual(preview.items[0].source.scan_status, "ready")
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_preview_read_paths_and_api_do_not_probe_storage(self):
        fixture = self._fixture({"C/One.2001.mkv": b"x" * 10})
        directory, target_directory, source_root, target_root, database = fixture
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(),),
        )
        index = InMemoryFileIndexRepository()
        source = _StorageCallCounter(LocalStorage("source", source_root))
        target = _StorageCallCounter(LocalStorage("target", target_root))
        try:
            scanner = StorageScanner(
                {"source": source},
                index,
            )
            scanner.scan(configuration.resource_libraries[0])
            with SQLiteTaskRepository(database) as repository:
                previews = AutomationTaskDefinitionPreviewService(
                    repository,
                    configuration=configuration,
                    providers=MetadataProviderRegistry((_provider(),)),
                    storages={"source": source, "target": target},
                    file_index=index,
                )
                preview = previews.create("def-1", actor="tester")
                source.calls.clear()
                target.calls.clear()
                previews.get_readonly(preview.preview_id)
                previews.latest_readonly("def-1")
                previews.list_readonly("def-1")
                previews.get(preview.preview_id)
                previews.latest("def-1")
                previews.list("def-1")
                previews.items(preview.preview_id, limit=1)
                self.assertEqual(source.calls, [])
                self.assertEqual(target.calls, [])

                record = index.find_by_path("source", "special", "Media/C/One.2001.mkv")
                self.assertIsNotNone(record)
                index.batch_upsert((replace(record, size=record.size + 1),))
                stale = previews.get_readonly(preview.preview_id)
                self.assertEqual(stale.status, AutomationTaskDefinitionPreviewStatus.STALE)
                self.assertIn("source fact", stale.stale_reason or "")

                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                    automation_preview_service=previews,
                )
                paths = (
                    "/api/v1/automation/task-definitions/def-1/previews",
                    f"/api/v1/automation/task-definitions/def-1/previews/{preview.preview_id}",
                    f"/api/v1/automation/task-definitions/def-1/previews/{preview.preview_id}/items",
                )
                self.assertIn(
                    "const data = await api(`/api/v1/automation/task-definitions/"
                    "${encodeURIComponent(item.id)}/previews?limit=10`);",
                    APP_JS.decode("utf-8"),
                )
                for path in paths:
                    query = "limit=1" if path.endswith("previews") else ""
                    status, _ = _api_request(api, path, query=query)
                    self.assertEqual(status, 200)
                self.assertEqual(source.calls, [])
                self.assertEqual(target.calls, [])
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_oversized_values_are_bounded_and_redacted_deterministically(self):
        fixture = self._fixture({"C/One.2001.mkv": b"x" * 10})
        directory, target_directory, source_root, target_root, database = fixture
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(),),
        )
        provider = _provider()
        try:
            with SQLiteTaskRepository(database) as repository:
                previews = self._services(
                    repository, configuration, provider, source_root, target_root
                )
                huge = {"value": "x" * (2 * 1024 * 1024)}
                with patch.object(
                    AutomationTaskDefinitionPreviewService,
                    "_plan_document",
                    return_value=huge,
                ):
                    preview = previews.create("def-1", actor="tester")
                document = preview.document()
                encoded = json.dumps(document).encode("utf-8")
                self.assertLess(len(encoded), 128 * 1024)
                self.assertTrue(
                    any(item.get("plan", {}).get("truncated") for item in document["items"])
                )
                self.assertNotIn("secret", json.dumps(document))
                persisted = []
                for table in (
                    "automation_task_definition_previews",
                    "automation_task_definition_preview_items",
                ):
                    persisted.extend(
                        str(tuple(row))
                        for row in repository._connection.execute(
                            f"SELECT * FROM {table}"
                        ).fetchall()
                    )
                self.assertNotIn("secret", "\n".join(persisted))
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_empty_scope_is_bounded_blocked_with_explicit_next_action(self):
        fixture = self._fixture({})
        directory, target_directory, source_root, target_root, database = fixture
        (source_root / "Media" / "C").mkdir(parents=True)
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(),),
        )
        try:
            with SQLiteTaskRepository(database) as repository:
                previews = self._services(
                    repository, configuration, _provider(), source_root, target_root
                )
                preview = previews.create("def-1", actor="tester")
                self.assertEqual(preview.status, AutomationTaskDefinitionPreviewStatus.BLOCKED)
                self.assertEqual(preview.items, ())
                self.assertIn("no media items", preview.next_action)
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_read_only_storage_guard_refuses_mutation_and_trees_are_identical(self):
        fixture = self._fixture({"C/One.2001.mkv": b"x" * 10})
        directory, target_directory, source_root, target_root, database = fixture
        configuration = _runtime(
            source_root,
            target_root,
            database,
            definitions=(_definition(),),
        )

        def manifest(root: Path) -> dict[str, tuple[int, str]]:
            return {
                str(path.relative_to(root)): (
                    path.stat().st_size,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
                for path in sorted(root.rglob("*"))
                if path.is_file()
                and path.name not in {"runtime.sqlite3", "history.jsonl"}
                and not path.name.startswith("runtime.sqlite3.")
            }

        before = (manifest(source_root), manifest(target_root))
        try:
            with SQLiteTaskRepository(database) as repository:
                previews = self._services(
                    repository, configuration, _provider(), source_root, target_root
                )
                preview = previews.create("def-1", actor="tester")
                self.assertEqual(preview.status, AutomationTaskDefinitionPreviewStatus.PREVIEWED)
                guard = PreviewReadOnlyStorage(LocalStorage("source", source_root))
                for operation, call in (
                    ("write", lambda: guard.write("Media/C/One.2001.mkv", b"x")),
                    ("create_directory", lambda: guard.create_directory("new")),
                    ("move", lambda: guard.move("Media/C/One.2001.mkv", "moved")),
                    ("copy", lambda: guard.copy("Media/C/One.2001.mkv", "copy")),
                    ("delete", lambda: guard.delete("Media/C/One.2001.mkv")),
                    ("hard_link", lambda: guard.hard_link("Media/C/One.2001.mkv", "link")),
                    ("soft_link", lambda: guard.soft_link("Media/C/One.2001.mkv", "link")),
                ):
                    with (
                        self.subTest(operation=operation),
                        self.assertRaises(ReadOnlyStorageMutationError),
                    ):
                        call()
                self.assertEqual(
                    {key: value for key, value in guard.mutation_calls.items() if value},
                    {
                        "Write": 1,
                        "CreateDirectory": 1,
                        "Move": 1,
                        "Copy": 1,
                        "Delete": 1,
                        "HardLink": 1,
                        "SoftLink": 1,
                    },
                )
                rows = {
                    table: repository._connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                    for table in (
                        "automation_jobs",
                        "tasks",
                        "task_items",
                        "task_results",
                        "execution_authorizations",
                    )
                }
                self.assertEqual(
                    rows,
                    {
                        "automation_jobs": 0,
                        "tasks": 0,
                        "task_items": 0,
                        "task_results": 0,
                        "execution_authorizations": 0,
                    },
                )
            after = (manifest(source_root), manifest(target_root))
            self.assertEqual(before, after)
        finally:
            directory.cleanup()
            target_directory.cleanup()


class AutomationTaskDefinitionPreviewPersistenceTests(unittest.TestCase):
    def test_migration_from_schema_27_keeps_existing_rows_and_adds_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            with SQLiteTaskRepository(database) as repository:
                legacy = datetime(2026, 1, 1, tzinfo=UTC)
                repository.create_task(
                    PersistentTask(
                        task_id="legacy-task",
                        command="scan",
                        status=PersistentTaskStatus.COMPLETED,
                        execute_authorized=False,
                        created_at=legacy,
                        updated_at=legacy,
                    )
                )
                with repository._connection:
                    repository._connection.execute(
                        "DROP TABLE automation_task_definition_preview_items"
                    )
                    repository._connection.execute("DROP TABLE automation_task_definition_previews")
                    repository._connection.execute(
                        "UPDATE schema_version SET version=27 WHERE component='runtime'"
                    )
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.schema_version, SCHEMA_VERSION)
                columns = {
                    row["name"]
                    for row in reopened._connection.execute(
                        "PRAGMA table_info(automation_task_definition_previews)"
                    )
                }
                self.assertIn("definition_fingerprint", columns)
                task = reopened.get_task("legacy-task")
                self.assertIsNotNone(task)

    def test_bounded_queries_latest_list_and_item_paging(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as target:
            source_root = Path(directory)
            target_root = Path(target)
            (source_root / "Media" / "C").mkdir(parents=True)
            (source_root / "Media" / "C" / "One.2001.mkv").write_bytes(b"x" * 10)
            database = source_root / "runtime.sqlite3"
            configuration = _runtime(
                source_root,
                target_root,
                database,
                definitions=(_definition(),),
            )
            with SQLiteTaskRepository(database) as repository:
                previews = AutomationTaskDefinitionPreviewService(
                    repository,
                    configuration=configuration,
                    providers=MetadataProviderRegistry((_provider(),)),
                    storages={
                        "source": LocalStorage("source", source_root),
                        "target": LocalStorage("target", target_root),
                    },
                )
                first = previews.create("def-1", actor="tester")
                second = previews.create("def-1", actor="tester")
                values = repository.list_automation_task_definition_previews("def-1", limit=1)
                self.assertEqual(len(values), 1)
                self.assertEqual(values[0].preview_id, second.preview_id)
                latest = repository.get_latest_automation_task_definition_preview("def-1")
                self.assertEqual(latest.preview_id, second.preview_id)
                self.assertEqual(latest.status, AutomationTaskDefinitionPreviewStatus.PREVIEWED)
                items, total, next_after = previews.items(second.preview_id, limit=1)
                self.assertEqual(total, 1)
                self.assertEqual(next_after, None)
                self.assertIsNotNone(first)


class AutomationTaskDefinitionPreviewApiTests(unittest.TestCase):
    def _document(self, root: Path) -> dict:
        value = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        value["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
        value["storages"][0]["rootPath"] = str(root / "source")
        value["storages"][1]["rootPath"] = str(root / "target")
        return value

    def _request(
        self,
        api,
        path: str,
        *,
        method: str = "GET",
        body=None,
        token: str = "admin-token",
        query: str = "",
    ):
        payload = b"" if body is None else json.dumps(body).encode("utf-8")
        statuses: list[str] = []
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "CONTENT_LENGTH": str(len(payload)),
            "wsgi.input": io.BytesIO(payload),
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        result = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(result)

    def test_api_run_list_read_rbac_and_read_only_view_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Media" / "C").mkdir(parents=True)
            (root / "source" / "Media" / "C" / "One.2001.mkv").write_bytes(b"x" * 10)
            (root / "target").mkdir()
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as configuration,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
            ):
                managed = ManagedConfigurationService(
                    configuration,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                provider = _provider()
                previews = AutomationTaskDefinitionPreviewService(
                    runtime,
                    managed,
                    providers=MetadataProviderRegistry((provider,)),
                    storages={
                        "source-storage": LocalStorage("source-storage", root / "source"),
                        "media-target": LocalStorage("media-target", root / "target"),
                    },
                )
                api = MediaFlowApi(
                    runtime,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                    configuration_service=managed,
                    bootstrap_document=document,
                    automation_preview_service=previews,
                )
                draft = managed.import_draft(document, actor="tester")
                status, body = self._request(
                    api,
                    "/api/v1/automation/task-definitions",
                    method="POST",
                    body={
                        "revisionId": draft.revision_id,
                        "expectedVersion": draft.version,
                        "definition": {
                            "id": "task",
                            "name": "Task",
                            "resourceLibraryId": "source",
                            "mode": "scan-and-plan",
                            "sourceScope": "C",
                            "intervalSeconds": 60,
                            "itemLimit": 5,
                        },
                    },
                )
                self.assertEqual(status, 200)
                draft = managed.require(draft.revision_id)
                validated = managed.validate(draft.revision_id, actor="tester")
                active = managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                rows_before = runtime._connection.execute(
                    "SELECT COUNT(*) FROM automation_task_definition_previews"
                ).fetchone()[0]
                jobs_before = runtime._connection.execute(
                    "SELECT COUNT(*) FROM automation_jobs"
                ).fetchone()[0]
                status, body = self._request(
                    api,
                    "/api/v1/automation/task-definitions/task/preview",
                    method="POST",
                    body={},
                )
                self.assertEqual(status, 201)
                self.assertEqual(body["status"], "previewed")
                self.assertEqual(body["configurationRevisionId"], active.revision_id)
                self.assertEqual(body["configurationRevisionDigest"], active.digest)
                preview_id = body["previewId"]
                status, listing = self._request(
                    api,
                    "/api/v1/automation/task-definitions/task/previews",
                )
                self.assertEqual(status, 200)
                self.assertEqual(listing["total"], 1)
                status, detail = self._request(
                    api,
                    f"/api/v1/automation/task-definitions/task/previews/{preview_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(detail["itemTotal"], 1)
                status, paged = self._request(
                    api,
                    f"/api/v1/automation/task-definitions/task/previews/{preview_id}/items",
                    query="limit=10",
                )
                self.assertEqual(status, 200)
                self.assertEqual(paged["total"], 1)
                # A read-only principal can inspect but cannot run.
                status, _ = self._request(
                    api,
                    "/api/v1/automation/task-definitions/task/previews",
                    token="viewer-token",
                )
                self.assertEqual(status, 200)
                status, _ = self._request(
                    api,
                    "/api/v1/automation/task-definitions/task/preview",
                    method="POST",
                    body={},
                    token="viewer-token",
                )
                self.assertEqual(status, 403)
                # Read-only view load creates no evidence, Job, Task, or revision.
                rows_after = runtime._connection.execute(
                    "SELECT COUNT(*) FROM automation_task_definition_previews"
                ).fetchone()[0]
                jobs_after = runtime._connection.execute(
                    "SELECT COUNT(*) FROM automation_jobs"
                ).fetchone()[0]
                tasks_after = runtime._connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[
                    0
                ]
                self.assertEqual(rows_after, rows_before + 1)
                self.assertEqual(jobs_after, jobs_before)
                self.assertEqual(tasks_after, 0)
                self.assertEqual(len(configuration.list_revisions()), 1)
                self.assertEqual(managed.active().version, 2)
                # Activating a newer revision makes an existing preview visibly stale.
                draft = managed.import_draft(active.document, actor="tester")
                status, _ = self._request(
                    api,
                    "/api/v1/automation/task-definitions/task",
                    method="PUT",
                    body={
                        "revisionId": draft.revision_id,
                        "expectedVersion": draft.version,
                        "definition": {
                            "id": "task",
                            "name": "Task renamed",
                            "resourceLibraryId": "source",
                            "mode": "scan-and-plan",
                            "sourceScope": "C",
                            "intervalSeconds": 60,
                            "itemLimit": 5,
                        },
                    },
                )
                self.assertEqual(status, 200)
                draft = managed.require(draft.revision_id)
                status, fresh = self._request(
                    api,
                    "/api/v1/automation/task-definitions/task/preview",
                    method="POST",
                    body={},
                )
                self.assertEqual(status, 201)
                validated = managed.validate(draft.revision_id, actor="tester")
                managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                status, stale_detail = self._request(
                    api,
                    f"/api/v1/automation/task-definitions/task/previews/{fresh['previewId']}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(stale_detail["status"], "stale")
                self.assertIn("Active revision", stale_detail["staleReason"])

    def test_api_rejects_scope_injection_and_missing_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Media" / "C").mkdir(parents=True)
            (root / "source" / "Media" / "C" / "One.2001.mkv").write_bytes(b"x" * 10)
            (root / "target").mkdir()
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as configuration,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
            ):
                managed = ManagedConfigurationService(
                    configuration,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                previews = AutomationTaskDefinitionPreviewService(
                    runtime,
                    managed,
                    providers=MetadataProviderRegistry((_provider(),)),
                    storages={
                        "source-storage": LocalStorage("source-storage", root / "source"),
                        "media-target": LocalStorage("media-target", root / "target"),
                    },
                )
                api = MediaFlowApi(
                    runtime,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=managed,
                    bootstrap_document=document,
                    automation_preview_service=previews,
                )
                draft = managed.import_draft(document, actor="tester")
                validated = managed.validate(draft.revision_id, actor="tester")
                managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                status, _ = self._request(
                    api,
                    "/api/v1/automation/task-definitions/missing/preview",
                    method="POST",
                    body={},
                )
                self.assertEqual(status, 404)
                status, body = self._request(
                    api,
                    "/api/v1/automation/task-definitions/missing/preview",
                    method="POST",
                    body={"sourceScope": "/etc"},
                )
                self.assertEqual(status, 400)
                self.assertIn("revisionId", body["error"]["message"])

    def test_definition_actions_mark_previews_stale_with_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Media" / "C").mkdir(parents=True)
            (root / "source" / "Media" / "C" / "One.2001.mkv").write_bytes(b"x" * 10)
            (root / "target").mkdir()
            document = self._document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as configuration,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
            ):
                managed = ManagedConfigurationService(
                    configuration,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                previews = AutomationTaskDefinitionPreviewService(
                    runtime,
                    managed,
                    providers=MetadataProviderRegistry((_provider(),)),
                    storages={
                        "source-storage": LocalStorage("source-storage", root / "source"),
                        "media-target": LocalStorage("media-target", root / "target"),
                    },
                )
                api = MediaFlowApi(
                    runtime,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=managed,
                    bootstrap_document=document,
                    automation_preview_service=previews,
                )
                draft = managed.import_draft(document, actor="tester")
                status, _ = self._request(
                    api,
                    "/api/v1/automation/task-definitions",
                    method="POST",
                    body={
                        "revisionId": draft.revision_id,
                        "expectedVersion": draft.version,
                        "definition": {
                            "id": "task",
                            "name": "Task",
                            "resourceLibraryId": "source",
                            "mode": "scan-and-plan",
                            "sourceScope": "C",
                            "intervalSeconds": 60,
                            "itemLimit": 5,
                        },
                    },
                )
                draft = managed.require(draft.revision_id)
                validated = managed.validate(draft.revision_id, actor="tester")
                active = managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                for action, body_fields in (
                    ("edit", {"name": "Task edited"}),
                    ("copy", {}),
                    ("enable", {"enabled": True}),
                    ("disable", {"enabled": False}),
                ):
                    status, body = self._request(
                        api,
                        "/api/v1/automation/task-definitions/task/preview",
                        method="POST",
                        body={},
                    )
                    self.assertEqual(status, 201)
                    preview_id = body["previewId"]
                    draft = managed.import_draft(active.document, actor="tester")
                    if action == "edit":
                        status, _ = self._request(
                            api,
                            "/api/v1/automation/task-definitions/task",
                            method="PUT",
                            body={
                                "revisionId": draft.revision_id,
                                "expectedVersion": draft.version,
                                "definition": {
                                    "id": "task",
                                    "name": "Task edited",
                                    "resourceLibraryId": "source",
                                    "mode": "scan-and-plan",
                                    "sourceScope": "C",
                                    "intervalSeconds": 60,
                                    "itemLimit": 5,
                                },
                            },
                        )
                    elif action == "copy":
                        status, _ = self._request(
                            api,
                            "/api/v1/automation/task-definitions/task/copy",
                            method="POST",
                            body={
                                "revisionId": draft.revision_id,
                                "expectedVersion": draft.version,
                            },
                        )
                    else:
                        status, _ = self._request(
                            api,
                            f"/api/v1/automation/task-definitions/task/{action}",
                            method="POST",
                            body={
                                "revisionId": draft.revision_id,
                                "expectedVersion": draft.version,
                            },
                        )
                    self.assertEqual(status, 200)
                    status, detail = self._request(
                        api,
                        f"/api/v1/automation/task-definitions/task/previews/{preview_id}",
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(detail["status"], "stale")
                    self.assertIn(action, detail["staleReason"])


if __name__ == "__main__":
    unittest.main()
