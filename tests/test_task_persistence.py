from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.task_runtime import PersistentTaskCoordinator, TaskLockError
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository


class PersistentTaskTests(unittest.TestCase):
    def test_schema_task_item_and_unicode_result_survive_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("organize", execute_authorized=False)
                item = coordinator.record_discovered(
                    task.task_id, "源存储", "电影", "电影/千与千寻.mkv", "千与千寻.mkv"
                )
                repository.append_result(
                    PersistentResultRecord(
                        "result-1",
                        task.task_id,
                        item.item_id,
                        "源存储",
                        item.source_path,
                        "目标存储",
                        "动漫/千与千寻.mkv",
                        "C",
                        "tmdb",
                        "129",
                        "C",
                        "A",
                        "A",
                        "A",
                        "MOVE",
                        "dry_run",
                        datetime.now(UTC),
                        "千与千寻",
                    )
                )
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.get_task(task.task_id), task)
                self.assertEqual(reopened.list_items(task.task_id)[0].source_path, item.source_path)
                result = reopened.list_results(task.task_id)[0]
                self.assertEqual(result.title, "千与千寻")
                self.assertEqual(result.recognition_type, "C")

    def test_lock_is_storage_aware_and_explicitly_reclaimable(self) -> None:
        now = datetime.now(UTC)
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            self.assertTrue(repository.acquire("a", "folder//movie.mkv", "task-a", now))
            self.assertFalse(repository.acquire("a", "folder/movie.mkv", "task-b", now))
            self.assertTrue(repository.acquire("b", "folder/movie.mkv", "task-b", now))
            self.assertTrue(repository.acquire("a", "other/movie.mkv", "task-b", now))
            self.assertEqual(repository.reclaim_task_locks("task-a"), 1)
            self.assertTrue(repository.acquire("a", "folder/movie.mkv", "task-b", now))
            repository.release("a", "folder/movie.mkv", "task-b")
            self.assertTrue(repository.acquire("a", "folder/movie.mkv", "task-c", now))
            with self.assertRaises(ValueError):
                repository.acquire("a", "../movie.mkv", "task", now)

    def test_lock_conflict_is_persisted_without_storage_access(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            first = coordinator.create("organize", execute_authorized=True)
            second = coordinator.create("organize", execute_authorized=True)
            coordinator.begin_item(first.task_id, "s", "r", "movie.mkv", "movie.mkv")
            with self.assertRaises(TaskLockError):
                coordinator.begin_item(second.task_id, "s", "r", "movie.mkv", "movie.mkv")
            item = repository.list_items(second.task_id)[0]
            self.assertEqual(item.status, TaskItemStatus.FAILED)
            self.assertEqual(item.stage, "lock")

    def test_retry_selection_and_execute_authority(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("organize", execute_authorized=False)
            now = datetime.now(UTC)
            base = PersistentTaskItem(
                "failed",
                task.task_id,
                "s",
                "r",
                "failed.mkv",
                "failed.mkv",
                TaskItemStatus.FAILED,
                "failed",
                1,
                now,
                now,
            )
            repository.upsert_item(base)
            repository.upsert_item(
                replace(
                    base,
                    item_id="partial",
                    source_path="partial.mkv",
                    status=TaskItemStatus.PARTIAL,
                )
            )
            repository.upsert_item(
                replace(
                    base,
                    item_id="success",
                    source_path="success.mkv",
                    status=TaskItemStatus.SUCCESS,
                )
            )
            repository.upsert_item(
                replace(
                    base,
                    item_id="crash-after-success",
                    source_path="completed-before-crash.mkv",
                    status=TaskItemStatus.PROCESSING,
                )
            )
            repository.append_result(
                PersistentResultRecord(
                    "completed-result",
                    task.task_id,
                    "crash-after-success",
                    "s",
                    "completed-before-crash.mkv",
                    "target",
                    "Movies/completed.mkv",
                    "A",
                    "tmdb",
                    "1",
                    "A",
                    "A",
                    "A",
                    "A",
                    "MOVE",
                    "success",
                    now,
                )
            )
            self.assertEqual(
                {
                    item.item_id
                    for item in coordinator.retryable_items(task.task_id, failed_only=True)
                },
                {"failed", "partial"},
            )
            with self.assertRaisesRegex(ValueError, "not execute-authorized"):
                coordinator.reopen(task.task_id, execute=True)

    def test_persistence_config_validation_creates_no_database(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "nested", "runtime.sqlite3")
            document["persistence"] = {"databasePath": str(database)}
            load_runtime_configuration(copy.deepcopy(document))
            self.assertFalse(database.exists())
            config = Path(directory, "config.json")
            config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            output, errors = io.StringIO(), io.StringIO()
            code = final_main(
                ["--config", str(config), "config", "validate"],
                stdout=output,
                stderr=errors,
            )
            self.assertEqual(code, 0, errors.getvalue())
            self.assertFalse(database.exists())

    def test_active_task_is_discoverable_after_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                task = PersistentTaskCoordinator(repository, repository).create(
                    "organize", execute_authorized=True
                )
                stale = replace(task, updated_at=datetime.now(UTC) - timedelta(hours=1))
                repository.update_task(stale)
            with SQLiteTaskRepository(database) as reopened:
                loaded = reopened.get_task(task.task_id)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertEqual(loaded.status, PersistentTaskStatus.RUNNING)

    def test_cancel_persists_items_releases_locks_and_stops_new_items(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository,
        ):
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("organize", execute_authorized=True)
            item = coordinator.begin_item(task.task_id, "s", "r", "movie.mkv", "movie.mkv")
            cancelled = coordinator.cancel(task.task_id)
            self.assertEqual(cancelled.status, PersistentTaskStatus.CANCELLED)
            self.assertEqual(
                repository.get_item(item.item_id).status,
                TaskItemStatus.CANCELLED,
            )
            self.assertTrue(repository.acquire("s", "movie.mkv", "another-task", datetime.now(UTC)))
            with self.assertRaisesRegex(RuntimeError, "not running"):
                coordinator.begin_item(task.task_id, "s", "r", "later.mkv", "later.mkv")

    def test_unknown_scan_command_creates_no_persistent_task_or_file_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "absent.json"
            errors = io.StringIO()
            with redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
                final_main(
                    ["--config", str(config), "scan"],
                    stdout=io.StringIO(),
                    stderr=errors,
                )
            self.assertEqual(2, raised.exception.code)
            self.assertIn("invalid choice", errors.getvalue())
            self.assertEqual([], list(root.iterdir()))


class DiscoveryAdmissionIdentityTests(unittest.TestCase):
    """The durable identity that separates every admission kind (B45.5 P1-2).

    The storage writer and both open-work finders must agree on one identity, so
    an ordinary Files preparation, two paused runs' recoveries and one repeated
    recovery request can never alias each other.  These cases exercise the real
    SQLite writer and both finders, including a reopen across connections.
    """

    @staticmethod
    def _discovery(
        discovery_id: str,
        *,
        status=None,
        auto_prepare: bool = False,
        recovery_task: str | None = None,
        excluded: tuple[str, ...] = (),
        budget: int = 100,
        definition: tuple[str, str] | None = None,
    ):
        from mediaflow.domain.media_discovery import (
            DefinitionRunOnceOrigin,
            DiscoveryBudgets,
            DiscoveryCounters,
            DiscoveryEntryKind,
            DiscoveryIncompleteReason,
            DiscoveryProgress,
            DiscoveryScopeEntry,
            DiscoveryStatus,
            MediaDiscovery,
        )

        now = datetime(2026, 10, 19, tzinfo=UTC)
        origin = None
        if definition is not None:
            origin = DefinitionRunOnceOrigin(
                definition[0],
                "Nightly",
                definition[1],
                "snap",
                1,
                "digest",
                "library",
                "Sub",
                4,
                4,
            )
        return MediaDiscovery(
            discovery_id,
            "operator",
            "library",
            "storage",
            "snap",
            "digest",
            status or DiscoveryStatus.QUEUED,
            1,
            replace(DiscoveryBudgets(), max_primary_sources=budget),
            DiscoveryProgress(
                "queued",
                (DiscoveryScopeEntry("Sub", DiscoveryEntryKind.DIRECTORY),),
                DiscoveryCounters(),
                DiscoveryIncompleteReason.NONE,
                (),
                (),
            ),
            now,
            now,
            auto_prepare=auto_prepare,
            definition_origin=origin,
            recovery_source_task_id=recovery_task,
            recovery_excluded_paths=excluded,
        )

    def test_ordinary_definition_and_recovery_admissions_never_alias(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "identity.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                ordinary = self._discovery("discovery-ordinary", auto_prepare=True)
                repository.create_media_discovery(ordinary)
                # The same scope/pin/actor admitted as a recovery preparation of
                # task one is a genuinely different intent and must not be
                # refused as a duplicate of the ordinary preparation.
                recovery = self._discovery(
                    "discovery-recovery",
                    auto_prepare=True,
                    recovery_task="task-one",
                    excluded=("Sub/Done.2001.mkv",),
                    budget=2,
                )
                repository.create_media_discovery(recovery)
                # A second paused run over the identical scope is its own work.
                other = self._discovery(
                    "discovery-other",
                    auto_prepare=True,
                    recovery_task="task-two",
                    budget=2,
                )
                repository.create_media_discovery(other)
                # Two definitions over the same scope are two intents.
                for discovery_id, fingerprint in (
                    ("discovery-definition-a", "a" * 64),
                    ("discovery-definition-b", "b" * 64),
                ):
                    repository.create_media_discovery(
                        self._discovery(
                            discovery_id,
                            auto_prepare=True,
                            definition=("nightly", fingerprint),
                        )
                    )

                # Each finder resolves exactly its own admission kind.
                found = repository.find_open_media_discovery(
                    actor="operator",
                    resource_library_id="library",
                    storage_id="storage",
                    snapshot_id="snap",
                    snapshot_digest="digest",
                    scope_signature='[["Sub","directory"]]',
                    auto_prepare=True,
                )
                assert found is not None and found.discovery_id == "discovery-ordinary"
                for task_id, expected in (
                    ("task-one", "discovery-recovery"),
                    ("task-two", "discovery-other"),
                ):
                    recovered = repository.find_open_recovery_discovery(
                        actor="operator",
                        recovery_source_task_id=task_id,
                        resource_library_id="library",
                        storage_id="storage",
                        snapshot_id="snap",
                        snapshot_digest="digest",
                        scope_signature='[["Sub","directory"]]',
                        recovery_excluded_paths=(
                            ("Sub/Done.2001.mkv",) if task_id == "task-one" else ()
                        ),
                        max_primary_sources=2,
                    )
                    assert recovered is not None, task_id
                    assert recovered.discovery_id == expected, (task_id, recovered.discovery_id)
                # A *changed* recovery context is a new admission, not a silent
                # reuse of the record that was admitted under different
                # exclusions/budget.
                assert (
                    repository.find_open_recovery_discovery(
                        actor="operator",
                        recovery_source_task_id="task-one",
                        resource_library_id="library",
                        storage_id="storage",
                        snapshot_id="snap",
                        snapshot_digest="digest",
                        scope_signature='[["Sub","directory"]]',
                        recovery_excluded_paths=(),
                        max_primary_sources=2,
                    )
                    is None
                )
                assert (
                    repository.find_open_media_discovery(
                        actor="operator",
                        resource_library_id="library",
                        storage_id="storage",
                        snapshot_id="snap",
                        snapshot_digest="digest",
                        scope_signature='[["Sub","directory"]]',
                        auto_prepare=True,
                        definition_id="nightly",
                        definition_fingerprint="a" * 64,
                    ).discovery_id
                    == "discovery-definition-a"
                )
                assert (
                    repository.find_open_media_discovery(
                        actor="operator",
                        resource_library_id="library",
                        storage_id="storage",
                        snapshot_id="snap",
                        snapshot_digest="digest",
                        scope_signature='[["Sub","directory"]]',
                        auto_prepare=True,
                        definition_id="nightly",
                        definition_fingerprint="b" * 64,
                    ).discovery_id
                    == "discovery-definition-b"
                )
            # The identity is durable: a second connection reads the same
            # partitions without recomputing anything from the current Active.
            with SQLiteTaskRepository(database) as reopened:
                recovered = reopened.find_open_recovery_discovery(
                    actor="operator",
                    recovery_source_task_id="task-one",
                    resource_library_id="library",
                    storage_id="storage",
                    snapshot_id="snap",
                    snapshot_digest="digest",
                    scope_signature='[["Sub","directory"]]',
                    recovery_excluded_paths=("Sub/Done.2001.mkv",),
                    max_primary_sources=2,
                )
                assert recovered is not None
                assert recovered.discovery_id == "discovery-recovery"
                assert recovered.recovery_excluded_paths == ("Sub/Done.2001.mkv",)
                assert recovered.recovery_source_task_id == "task-one"

    def test_an_ordinary_admission_keeps_its_previous_durable_identity(self) -> None:
        """An already open ordinary admission still reconciles byte-identically.

        The origin keys are only added for a definition/recovery admission, so a
        discovery written before this correction keeps the same stored
        signature and the same reconciliation outcome.  Nothing is cleared,
        backfilled or rewritten.
        """

        from mediaflow.domain.media_discovery import (
            DiscoveryBudgets,
            DiscoveryCounters,
            DiscoveryEntryKind,
            DiscoveryIncompleteReason,
            DiscoveryProgress,
            DiscoveryScopeEntry,
            DiscoveryStatus,
            MediaDiscovery,
            discovery_admission_identity,
        )

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "compat.sqlite3")
            now = datetime(2026, 10, 19, tzinfo=UTC)
            # The exact identity the previous implementation persisted.
            legacy_signature = json.dumps(
                {
                    "actor": "operator",
                    "resourceLibraryId": "library",
                    "storageId": "storage",
                    "scope": '[["Sub","directory"]]',
                    "snapshotId": "snap",
                    "snapshotDigest": "digest",
                    "autoPrepare": True,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            assert (
                discovery_admission_identity(
                    actor="operator",
                    resource_library_id="library",
                    storage_id="storage",
                    snapshot_id="snap",
                    snapshot_digest="digest",
                    scope_signature='[["Sub","directory"]]',
                    auto_prepare=True,
                )
                == legacy_signature
            )
            discovery = MediaDiscovery(
                "discovery-legacy",
                "operator",
                "library",
                "storage",
                "snap",
                "digest",
                DiscoveryStatus.QUEUED,
                1,
                DiscoveryBudgets(),
                DiscoveryProgress(
                    "queued",
                    (DiscoveryScopeEntry("Sub", DiscoveryEntryKind.DIRECTORY),),
                    DiscoveryCounters(),
                    DiscoveryIncompleteReason.NONE,
                    (),
                    (),
                ),
                now,
                now,
                auto_prepare=True,
            )
            with SQLiteTaskRepository(database) as repository:
                # Seed the row exactly as the prior implementation stored it,
                # which is also what this build would store for the same input.
                stored = replace(discovery, recovery_source_task_id=None)
                repository.create_media_discovery(stored)
                self.assertEqual(
                    repository._connection.execute(
                        "SELECT admission_signature FROM media_discoveries WHERE discovery_id=?",
                        ("discovery-legacy",),
                    ).fetchone()["admission_signature"],
                    legacy_signature,
                )
                found = repository.find_open_media_discovery(
                    actor="operator",
                    resource_library_id="library",
                    storage_id="storage",
                    snapshot_id="snap",
                    snapshot_digest="digest",
                    scope_signature='[["Sub","directory"]]',
                    auto_prepare=True,
                )
                assert found is not None
                assert found.discovery_id == "discovery-legacy"


class SourceOwnershipEvidenceTests(unittest.TestCase):
    """One physical source keeps one owner, judged only by comparable evidence.

    B46.3-04 required the comparison itself to separate the *physical source and
    its comparable content version* from the library/principal/pin/plan context.
    These are the two ownership paths that exist in the repository — a TaskItem and
    a Files discovery admission — asserted over one durable database.
    """

    @staticmethod
    def _entry(path: str, size: int, modified: datetime):
        from mediaflow.domain.storage import StorageEntry, StorageEntryType

        return StorageEntry(path.rsplit("/", 1)[-1], path, StorageEntryType.FILE, size, modified)

    def _version(self, path: str, size: int, modified: datetime):
        from mediaflow.domain.source_evidence import source_version_evidence

        return source_version_evidence(self._entry(path, size, modified))

    def test_two_library_bindings_of_one_entry_share_one_content_version(self) -> None:
        """The binding enters the digest but never the comparable version."""

        from mediaflow.domain.source_evidence import (
            source_fingerprint,
            stored_source_version_evidence,
        )

        modified = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
        entry = self._entry("Movies/One.2001.mkv", 64, modified)
        whole = source_fingerprint("source", "whole", entry)
        nested = source_fingerprint("source", "nested", entry)
        # The reviewed-occurrence digests really differ by binding...
        self.assertNotEqual(whole.value, nested.value)
        # ...while the comparable content version agrees, and it round-trips
        # through the durable evidence document of *either* binding.
        self.assertEqual(source_version_evidence_from(whole), source_version_evidence_from(nested))
        self.assertEqual(
            source_version_evidence_from(whole), stored_source_version_evidence(whole.evidence)
        )

    def test_a_task_item_owner_holds_across_bindings_and_releases_on_replacement(
        self,
    ) -> None:
        from mediaflow.domain.source_evidence import (
            source_version_is_known_different,
            stored_source_version_evidence,
        )

        modified = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "ownership.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("manual_organize", execute_authorized=True)
                entry = self._entry("Movies/One.2001.mkv", 64, modified)
                from mediaflow.domain.source_evidence import source_fingerprint

                fingerprint = source_fingerprint("source", "nested", entry)
                item = coordinator.begin_item(
                    task.task_id,
                    "source",
                    "nested",
                    "One.2001.mkv",
                    "One.2001.mkv",
                    source_occurrence_id="occ-1",
                    source_fingerprint=fingerprint.value,
                    source_fingerprint_state="verified",
                )
                repository.upsert_item(
                    replace(
                        item,
                        source_storage_path="Movies/One.2001.mkv",
                        status=TaskItemStatus.PENDING,
                        stage="waiting_metadata",
                    )
                )

                # The same physical source under another binding is the same owner:
                # the two fingerprints are incomparable, not different content.
                owned = repository.find_owned_source_work(
                    storage_id="source",
                    source_path="Movies/One.2001.mkv",
                    storage_path="Movies/One.2001.mkv",
                    resource_library_id="whole",
                    source_version=self._version("Movies/One.2001.mkv", 64, modified),
                )
                self.assertIsNotNone(owned, "an unchanged source under another binding")
                self.assertEqual(task.task_id, owned["taskId"])
                # The same binding's digest is directly comparable, so an unchanged
                # source is owned there too.
                self.assertIsNotNone(
                    repository.find_owned_source_work(
                        storage_id="source",
                        source_path="One.2001.mkv",
                        storage_path="Movies/One.2001.mkv",
                        resource_library_id="nested",
                        source_fingerprint=fingerprint.value,
                        source_version=self._version("Movies/One.2001.mkv", 64, modified),
                    )
                )
                # A really replaced file is different content.  Inside the binding
                # that observed it the stored digest is directly comparable, so the
                # claim is released for the new version instead of blocking it.
                replaced = self._version("Movies/One.2001.mkv", 512, modified)
                self.assertTrue(
                    source_version_is_known_different(
                        replaced,
                        stored_source_version_evidence(fingerprint.evidence),
                    )
                )
                from mediaflow.domain.source_evidence import source_fingerprint

                self.assertIsNone(
                    repository.find_owned_source_work(
                        storage_id="source",
                        source_path="One.2001.mkv",
                        storage_path="Movies/One.2001.mkv",
                        resource_library_id="nested",
                        source_fingerprint=source_fingerprint(
                            "source",
                            "nested",
                            self._entry("Movies/One.2001.mkv", 512, modified),
                        ).value,
                        source_version=replaced,
                    )
                )
                # No comparable version is ever "different": instead of releasing a
                # live claim on incomparable evidence, the claim is kept.
                self.assertFalse(source_version_is_known_different(None, None))
                self.assertFalse(source_version_is_known_different(replaced, None))
                self.assertIsNotNone(
                    repository.find_owned_source_work(
                        storage_id="source",
                        source_path="Movies/One.2001.mkv",
                        storage_path="Movies/One.2001.mkv",
                        resource_library_id="whole",
                        source_version=replaced,
                    )
                )
                # A settled item no longer owns the source.
                repository.upsert_item(
                    replace(
                        item,
                        source_storage_path="Movies/One.2001.mkv",
                        status=TaskItemStatus.SUCCESS,
                        stage="success",
                    )
                )
                self.assertIsNone(
                    repository.find_owned_source_work(
                        storage_id="source",
                        source_path="Movies/One.2001.mkv",
                        storage_path="Movies/One.2001.mkv",
                        resource_library_id="whole",
                        source_version=self._version("Movies/One.2001.mkv", 64, modified),
                    )
                )

    def test_the_ownership_decision_and_the_item_admission_are_one_transaction(
        self,
    ) -> None:
        """B46.3-05: the deciding check is the one that also writes the item.

        A read-only check made before the admission can pass and then lose the
        source to a concurrent owner between the check and the item write.  The
        production boundary therefore asks and writes inside one
        ``BEGIN IMMEDIATE``: a second connection that committed the source in
        between makes the write refuse instead of committing a competing item,
        and the item table stays untouched for the loser.
        """

        from mediaflow.domain.source_evidence import source_fingerprint

        modified = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "ownership.sqlite3")
            with (
                SQLiteTaskRepository(database) as first,
                SQLiteTaskRepository(database) as second,
            ):
                entry = self._entry("Movies/One.2001.mkv", 64, modified)
                version = self._version("Movies/One.2001.mkv", 64, modified)
                owner_task = PersistentTaskCoordinator(first, first).create(
                    "manual_organize", execute_authorized=True
                )
                owner_item = PersistentTaskCoordinator(first, first).begin_item(
                    owner_task.task_id,
                    "source",
                    "library",
                    "Movies/One.2001.mkv",
                    "Movies/One.2001.mkv",
                    source_fingerprint=source_fingerprint("source", "library", entry).value,
                    source_fingerprint_state="verified",
                    source_storage_path="Movies/One.2001.mkv",
                )
                first.upsert_item(
                    replace(
                        owner_item,
                        status=TaskItemStatus.PENDING,
                        stage="waiting_metadata",
                    )
                )

                contender = PersistentTaskCoordinator(second, second).create(
                    "organize", execute_authorized=True
                )
                candidate = replace(
                    owner_item,
                    item_id="contender-item",
                    task_id=contender.task_id,
                    attempts=1,
                )
                # The item is never written for a source another unfinished work
                # owns, and the exact owner is reported instead.
                refused = second.claim_task_item_with_ownership(candidate, source_version=version)
                self.assertIsNotNone(refused)
                self.assertEqual(owner_task.task_id, refused["taskId"])
                self.assertIsNone(second.get_item("contender-item"))
                self.assertEqual(
                    ("pending", "waiting_metadata"),
                    (
                        second.get_item(owner_item.item_id).status.value,
                        second.get_item(owner_item.item_id).stage,
                    ),
                )

                # The owner's own row is never its own competitor, so a retry of
                # the same Task still admits (at no point does the boundary make a
                # legal owner refuse its own remaining work).
                self.assertIsNone(
                    second.claim_task_item_with_ownership(owner_item, source_version=version)
                )
                self.assertEqual(owner_task.task_id, second.get_item(owner_item.item_id).task_id)

    def test_a_legal_continuation_lineage_is_not_its_own_owner(self) -> None:
        """A continuation's ancestors are its source, never a competing owner."""

        from mediaflow.domain.source_evidence import source_fingerprint

        modified = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "lineage.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                entry = self._entry("Movies/One.2001.mkv", 64, modified)
                version = self._version("Movies/One.2001.mkv", 64, modified)
                ancestor = coordinator.create("manual_organize", execute_authorized=True)
                ancestor_item = coordinator.begin_item(
                    ancestor.task_id,
                    "source",
                    "library",
                    "Movies/One.2001.mkv",
                    "Movies/One.2001.mkv",
                    source_fingerprint=source_fingerprint("source", "library", entry).value,
                    source_fingerprint_state="verified",
                    source_storage_path="Movies/One.2001.mkv",
                )
                repository.upsert_item(
                    replace(ancestor_item, status=TaskItemStatus.PAUSED, stage="paused")
                )
                continuation = coordinator.create(
                    "organize", execute_authorized=False, item_limit=1
                )
                # Without the lineage the ancestor really owns the source...
                self.assertIsNotNone(
                    repository.claim_task_item_with_ownership(
                        replace(
                            ancestor_item,
                            item_id="lineage-item",
                            task_id=continuation.task_id,
                            attempts=1,
                        ),
                        source_version=version,
                    )
                )
                # ...and with it the continuation admits its own remaining scope.
                self.assertIsNone(
                    repository.claim_task_item_with_ownership(
                        replace(
                            ancestor_item,
                            item_id="lineage-item",
                            task_id=continuation.task_id,
                            attempts=1,
                        ),
                        source_version=version,
                        exclude_lineage_task_id=ancestor.task_id,
                    )
                )
                self.assertEqual(continuation.task_id, repository.get_item("lineage-item").task_id)

    def test_a_pre_change_admission_row_is_still_read_as_an_owner(self) -> None:
        """B46.3-05: narrowing the read must never skip a legacy identity.

        A durable Files admission written before the canonical Storage-relative
        scope existed records its identity only in its progress document.  The
        corrected ownership read decides the source *inside* the SQL predicate, so
        that legacy shape is the one place where a too-narrow predicate would
        silently answer "free".  The row here is a real admitted discovery written
        through the production repository with an empty recorded scope, exactly
        what a pre-change row round-trips as, and it must still be found — both as
        the source owner and through the atomic per-source admission boundary.
        """

        from mediaflow.domain.media_discovery import (
            DiscoveryBudgets,
            DiscoveryCounters,
            DiscoveryEntryKind,
            DiscoveryIncompleteReason,
            DiscoveryProgress,
            DiscoveryScopeEntry,
            DiscoveryStatus,
            MediaDiscovery,
        )

        now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "legacy-owner.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                legacy = MediaDiscovery(
                    "legacy-admission",
                    "operator",
                    "library",
                    "source",
                    "snap",
                    "d" * 64,
                    DiscoveryStatus.QUEUED,
                    1,
                    DiscoveryBudgets(),
                    DiscoveryProgress(
                        "queued",
                        (DiscoveryScopeEntry("Movies/One.2001.mkv", DiscoveryEntryKind.FILE),),
                        DiscoveryCounters(),
                        DiscoveryIncompleteReason.NONE,
                        message="queued",
                        manual_selection=True,
                    ),
                    now,
                    now,
                    # Deliberately the pre-change evidence shape: no recorded
                    # canonical scope at all.
                    storage_scope=(),
                )
                repository.create_media_discovery(legacy)
                owner = repository.find_owned_source_work(
                    storage_id="source",
                    source_path="Movies/One.2001.mkv",
                    storage_path="Movies/One.2001.mkv",
                    resource_library_id="library",
                )
                self.assertIsNotNone(owner, "the legacy admission lost its source")
                self.assertEqual("legacy-admission", owner["discoveryId"])
                self.assertEqual("discovery", owner["kind"])
                # A genuinely different source is still free.
                self.assertIsNone(
                    repository.find_owned_source_work(
                        storage_id="source",
                        source_path="Movies/Two.2002.mkv",
                        storage_path="Movies/Two.2002.mkv",
                        resource_library_id="library",
                    )
                )
                # Its own re-read never refuses itself.
                self.assertIsNone(
                    repository.find_owned_source_work(
                        storage_id="source",
                        source_path="Movies/One.2001.mkv",
                        storage_path="Movies/One.2001.mkv",
                        resource_library_id="library",
                        exclude_discovery_id="legacy-admission",
                    )
                )

    def test_a_legacy_task_item_without_evidence_keeps_its_claim(self) -> None:
        """A pre-change row proves no version, so it never reads as replaced."""
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "legacy.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("manual_organize", execute_authorized=True)
                item = coordinator.begin_item(
                    task.task_id, "source", "library", "Movies/One.2001.mkv", "One.2001.mkv"
                )
                repository.upsert_item(
                    replace(item, status=TaskItemStatus.PENDING, stage="waiting_metadata")
                )
                # An observed version with nothing comparable on the stored side is
                # unknown, not "different".
                self.assertIsNotNone(
                    repository.find_owned_source_work(
                        storage_id="source",
                        source_path="Movies/One.2001.mkv",
                        resource_library_id="library",
                        source_version=self._version(
                            "Movies/One.2001.mkv", 512, datetime(2026, 10, 21, tzinfo=UTC)
                        ),
                    )
                )

    def test_a_recorded_canonical_path_is_never_re_read_as_its_relative_name(self) -> None:
        """B46.3-06: a proven different path is a different file, not the same one.

        Two admissions of one Storage under two library roots record their own
        canonical Storage paths.  A lookup for the second must not reach the first
        through the library-relative name -- but a record that recorded *no*
        canonical path for that entry is still the conservative legacy owner inside
        its own binding.  Both facts are asserted on rows written through the
        production repository, so the distinction cannot drift back into an
        unconditional fallback.
        """

        from mediaflow.domain.media_discovery import (
            DiscoveryBudgets,
            DiscoveryCounters,
            DiscoveryEntryKind,
            DiscoveryIncompleteReason,
            DiscoveryProgress,
            DiscoveryScopeEntry,
            DiscoveryStatus,
            MediaDiscovery,
        )

        now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

        def admission(discovery_id: str, library: str, storage_scope) -> MediaDiscovery:
            return MediaDiscovery(
                discovery_id,
                "operator",
                library,
                "source",
                "snap",
                "d" * 64,
                DiscoveryStatus.QUEUED,
                1,
                DiscoveryBudgets(),
                DiscoveryProgress(
                    "queued",
                    (DiscoveryScopeEntry("One.2001.mkv", DiscoveryEntryKind.FILE),),
                    DiscoveryCounters(),
                    DiscoveryIncompleteReason.NONE,
                    message="queued",
                    manual_selection=True,
                ),
                now,
                now,
                storage_scope=storage_scope,
            )

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "distinct-sources.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                repository.create_media_discovery(
                    admission("admission-a", "one", (("One.2001.mkv", "A/One.2001.mkv"),))
                )
                repository.create_media_discovery(
                    admission("admission-b", "two", (("One.2001.mkv", "B/One.2001.mkv"),))
                )
                # Each canonical path resolves to its own owner, and neither one
                # answers for the other.
                first = repository.find_owned_source_work(
                    storage_id="source",
                    source_path="One.2001.mkv",
                    storage_path="A/One.2001.mkv",
                    resource_library_id="one",
                )
                self.assertIsNotNone(first)
                self.assertEqual("admission-a", first["discoveryId"])
                second = repository.find_owned_source_work(
                    storage_id="source",
                    source_path="One.2001.mkv",
                    storage_path="B/One.2001.mkv",
                    resource_library_id="two",
                )
                self.assertIsNotNone(second)
                self.assertEqual("admission-b", second["discoveryId"])
                # The same physical source through a third binding of the same
                # Storage is still one owner, not a third admission.
                alias = repository.find_owned_source_work(
                    storage_id="source",
                    source_path="A/One.2001.mkv",
                    storage_path="A/One.2001.mkv",
                    resource_library_id="whole",
                )
                self.assertIsNotNone(alias)
                self.assertEqual("admission-a", alias["discoveryId"])
                # A different canonical path in the *same* binding is free, even
                # though it carries the identical library-relative name: the
                # recorded canonical identity decides, not the name.
                self.assertIsNone(
                    repository.find_owned_source_work(
                        storage_id="source",
                        source_path="One.2001.mkv",
                        storage_path="C/One.2001.mkv",
                        resource_library_id="one",
                    )
                )
                # A caller that cannot supply a canonical path at all stays on the
                # conservative identity instead of being answered "free": the
                # record's own library-relative path still names unfinished work.
                conservative = repository.find_owned_source_work(
                    storage_id="source",
                    source_path="One.2001.mkv",
                    resource_library_id="one",
                )
                self.assertIsNotNone(conservative)
                # ...and that conservative answer never leaves the record's own
                # binding: the same relative name in the other binding names the
                # other root's own work, never this one's.
                other = repository.find_owned_source_work(
                    storage_id="source",
                    source_path="One.2001.mkv",
                    resource_library_id="two",
                )
                self.assertIsNotNone(other)
                self.assertEqual("admission-b", other["discoveryId"])


def source_version_evidence_from(fingerprint):
    from mediaflow.domain.source_evidence import stored_source_version_evidence

    return stored_source_version_evidence(fingerprint.evidence)


class ManualRecoveryPreparationPersistenceTests(unittest.TestCase):
    def test_preparation_round_trips_and_supersedes_without_authority(self) -> None:
        """A prepared summary persists, supersedes and never invents authority."""

        from mediaflow.domain.manual_recovery import (
            ManualRecoveryPreparation,
            ManualRecoveryPreparationStatus,
        )

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "preparations.sqlite3")
            now = datetime(2026, 10, 17, tzinfo=UTC)
            with SQLiteTaskRepository(database) as repository:
                repository.create_manual_intent_with_audit(
                    _manual_intent("intent-1"),
                    _manual_items("intent-1"),
                    _manual_audit("intent-1"),
                )
                task_id, item_id = self._source_task_and_item(repository)
                preparation = ManualRecoveryPreparation(
                    "prep-1",
                    task_id,
                    item_id,
                    "continuation-1",
                    "analysis-task-1",
                    "analysis-result-1",
                    "intent-1",
                    "preview-1",
                    1,
                    "b" * 64,
                    "c" * 64,
                    "snap-1",
                    "digest-1",
                    "operator",
                    ManualRecoveryPreparationStatus.PREPARED,
                    now,
                    now,
                )
                repository.create_manual_recovery_preparation(preparation)
                stored = repository.get_manual_recovery_preparation("prep-1")
                assert stored is not None
                assert stored.authorization_id is None
                assert stored.execution_id is None
                assert stored.intent_version == 1
                assert stored.status is ManualRecoveryPreparationStatus.PREPARED
                assert repository.get_current_manual_recovery_preparation(task_id, item_id)
                assert repository.list_manual_recovery_preparations(task_id, item_id)

                # A prepared summary must not claim execution authority.
                with self.assertRaises(ValueError):
                    repository.create_manual_recovery_preparation(
                        replace(preparation, preparation_id="prep-bad", authorization_id="a")
                    )

                superseded = repository.supersede_manual_recovery_preparation("prep-1", now=now)
                assert superseded.status is ManualRecoveryPreparationStatus.SUPERSEDED
                assert repository.get_current_manual_recovery_preparation(task_id, item_id) is None

            # Reopening preserves the exact record; the historical row is intact.
            with SQLiteTaskRepository(database) as reopened:
                stored = reopened.get_manual_recovery_preparation("prep-1")
                assert stored is not None
                assert stored.status is ManualRecoveryPreparationStatus.SUPERSEDED
                assert stored.authorization_id is None

    def _source_task_and_item(self, repository):
        from mediaflow.application.task_runtime import PersistentTaskCoordinator
        from mediaflow.domain.task_persistence import TaskItemStatus

        coordinator = PersistentTaskCoordinator(repository, repository)
        task = coordinator.create(
            "manual_organize",
            execute_authorized=False,
            item_limit=1,
            configuration_snapshot_id="snap-1",
            configuration_snapshot_digest="digest-1",
            require_configuration_snapshot=True,
        )
        item = coordinator.begin_item(
            task.task_id, "source", "source", "Media/One.2001.mkv", "Media/One.2001.mkv"
        )
        repository.upsert_item(replace(item, status=TaskItemStatus.FAILED, stage="failed"))
        repository.release(item.storage_id, item.source_path, item.task_id)
        return task.task_id, item.item_id


def _manual_intent(intent_id: str):
    from mediaflow.domain.manual_organize import (
        ManualConfigurationSnapshot,
        ManualIntentStatus,
        ManualOrganizeIntent,
    )

    now = datetime(2026, 10, 4, tzinfo=UTC)
    return ManualOrganizeIntent(
        intent_id,
        "operator",
        "snap-base",
        "digest-base",
        ManualIntentStatus.OPEN,
        1,
        now,
        now,
        _manual_items(intent_id),
        ManualConfigurationSnapshot("snap-base", "digest-base", (), (), (), (), ()),
        "continue to an exact zero-mutation Preview",
        None,
        (),
    )


def _manual_items(intent_id: str):
    from mediaflow.domain.manual_organize import (
        ManualChoice,
        ManualIntentItem,
        ManualIntentItemStatus,
        ManualSourceIdentity,
    )

    now = datetime(2026, 10, 4, tzinfo=UTC)
    source = ManualSourceIdentity(
        source_id="occ-base",
        storage_id="storage-base",
        resource_library_id="library-base",
        path="Movies/One.2001.mkv",
        filename="One.2001.mkv",
        extension="mkv",
        size=512,
        modified_at=now,
        observed_at=now,
        stable_since=None,
        occurrence_id="occ-base",
        fingerprint="a" * 64,
        fingerprint_algorithm="storage-entry-sha256",
        fingerprint_evidence={"source": "storage_entry"},
        occurrence_state="verified",
    )
    return (
        ManualIntentItem(
            "item-base",
            intent_id,
            0,
            source,
            ManualChoice("A", None, "A", "A", "A"),
            ManualIntentItemStatus.READY,
            None,
            1,
            now,
            now,
        ),
    )


def _manual_audit(intent_id: str):
    from mediaflow.domain.manual_organize import ManualIntentAudit

    now = datetime(2026, 10, 4, tzinfo=UTC)
    return ManualIntentAudit(
        "audit-base", intent_id, None, "operator", "created_from_storage_source", {}, {}, now
    )


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
