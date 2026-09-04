from __future__ import annotations

import os
import re
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.scanner import (
    ResourceLibraryService,
    ScanAlreadyRunningError,
    StorageScanner,
)
from mediaflow.domain.library import (
    FileStabilityPolicy,
    ResourceLibrary,
    ScanMode,
    ScanRule,
    ScanRuleKind,
)
from mediaflow.domain.scanner import CancellationToken, FileChange, FileScanStatus
from mediaflow.domain.storage import (
    StorageCapabilities,
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
)
from mediaflow.domain.tasks import ScanTask, TaskStatus
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository

NOW = datetime(2026, 8, 19, 12, tzinfo=UTC)


class MutableClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class FakeStorage:
    def __init__(self, storage_id: str = "fake", *, read_only: bool = True) -> None:
        self._storage_id = storage_id
        self._read_only = read_only
        self.directories: set[str] = {""}
        self.files: dict[str, tuple[int, datetime]] = {}
        self.list_errors: dict[str, StorageErrorCode] = {}
        self.mutations = {
            "write": 0,
            "create_directory": 0,
            "move": 0,
            "copy": 0,
            "delete": 0,
            "hard_link": 0,
            "soft_link": 0,
        }
        self.list_calls: list[str] = []
        self.active_lists = 0
        self.max_active_lists = 0
        self.list_delay = 0.0
        self.block_list: threading.Event | None = None
        self.entered_list = threading.Event()
        self._lock = threading.Lock()

    @property
    def storage_id(self) -> str:
        return self._storage_id

    @property
    def name(self) -> str:
        return self._storage_id

    @property
    def read_only(self) -> bool:
        return self._read_only

    @property
    def capabilities(self) -> StorageCapabilities:
        return StorageCapabilities()

    def add_directory(self, path: str) -> None:
        current = path.strip("/")
        while current:
            self.directories.add(current)
            current = current.rpartition("/")[0]

    def add_file(
        self, path: str, size: int = 1, modified_at: datetime = NOW - timedelta(hours=1)
    ) -> None:
        key = path.strip("/")
        self.add_directory(key.rpartition("/")[0])
        self.files[key] = (size, modified_at)

    def list(self, path: str):
        key = path.strip("/")
        with self._lock:
            self.list_calls.append(key)
            self.active_lists += 1
            self.max_active_lists = max(self.max_active_lists, self.active_lists)
        self.entered_list.set()
        try:
            if self.block_list:
                self.block_list.wait(2)
            if self.list_delay:
                time.sleep(self.list_delay)
            if key in self.list_errors:
                raise StorageError(self.list_errors[key], "list", key, "fake list failure")
            if key not in self.directories:
                raise StorageError(StorageErrorCode.NOT_FOUND, "list", key, "missing")
            prefix = f"{key}/" if key else ""
            entries = []
            for directory in sorted(self.directories):
                if (
                    directory
                    and directory.startswith(prefix)
                    and "/" not in directory[len(prefix) :]
                ):
                    entries.append(self._entry(directory, True))
            for file_path in sorted(self.files):
                if file_path.startswith(prefix) and "/" not in file_path[len(prefix) :]:
                    entries.append(self._entry(file_path, False))
            return tuple(entries)
        finally:
            with self._lock:
                self.active_lists -= 1

    def _entry(self, path: str, directory: bool) -> StorageEntry:
        size, modified = (0, NOW) if directory else self.files[path]
        return StorageEntry(
            path.rpartition("/")[-1],
            path,
            StorageEntryType.DIRECTORY if directory else StorageEntryType.FILE,
            size,
            modified,
        )

    def stat(self, path: str) -> StorageEntry:
        key = path.strip("/")
        if key in self.directories:
            return self._entry(key, True)
        if key in self.files:
            return self._entry(key, False)
        raise StorageError(StorageErrorCode.NOT_FOUND, "stat", key, "missing")

    def exists(self, path: str) -> bool:
        return path.strip("/") in self.directories | self.files.keys()

    def read(self, path: str):
        raise AssertionError("scanner must not read file contents")

    def _mutation(self, operation: str) -> None:
        self.mutations[operation] += 1
        raise AssertionError(f"scanner called mutation {operation}")

    def write(self, path, data, *, overwrite=False) -> None:
        self._mutation("write")

    def create_directory(self, path) -> None:
        self._mutation("create_directory")

    def move(self, source, target, *, overwrite=False) -> None:
        self._mutation("move")

    def copy(self, source, target, *, overwrite=False) -> None:
        self._mutation("copy")

    def delete(self, path) -> None:
        self._mutation("delete")

    def hard_link(self, source, target) -> None:
        self._mutation("hard_link")

    def soft_link(self, source, target) -> None:
        self._mutation("soft_link")


class ScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = FakeStorage()
        self.index = InMemoryFileIndexRepository()
        self.clock = MutableClock()
        self.scanner = StorageScanner({"fake": self.storage}, self.index, clock=self.clock)

    def library(self, **changes) -> ResourceLibrary:
        base = ResourceLibrary("library", "Library", "fake", "", exclude_rules=())
        return replace(base, **changes)

    def records(self, library_id: str = "library"):
        return {record.path: record for record in self.index.list_by_resource_library(library_id)}

    def test_complete_scan_has_zero_mutation_calls(self) -> None:
        self.storage.add_file("Movies/A.mkv")
        result = self.scanner.scan(self.library())
        self.assertEqual(TaskStatus.COMPLETED, result.status)
        self.assertEqual(
            {
                "write": 0,
                "create_directory": 0,
                "move": 0,
                "copy": 0,
                "delete": 0,
                "hard_link": 0,
                "soft_link": 0,
            },
            self.storage.mutations,
        )

    def test_scan_task_receives_status_progress_and_errors(self) -> None:
        self.storage.add_file("A.mkv")
        task, result = self.scanner.run_task(
            ScanTask("task-1", "library", ScanMode.FULL.value), self.library()
        )
        self.assertEqual(TaskStatus.COMPLETED, task.status)
        self.assertEqual(result.started_at, task.started_at)
        self.assertEqual(1, task.progress["candidates_found"])
        self.assertEqual((), task.errors)

    def test_extensions_are_configurable_and_case_insensitive(self) -> None:
        for name in ("movie.mkv", "upper.MKV", "mixed.MkV", "note.txt"):
            self.storage.add_file(name)
        result = self.scanner.scan(self.library(file_extensions=(".MKV",)))
        self.assertEqual(3, result.statistics.media_candidates)
        self.assertEqual(FileScanStatus.IGNORED, self.records()["note.txt"].scan_status)

    def test_include_rules_limit_results_and_prune_directories(self) -> None:
        self.storage.add_file("Movies/A.mkv")
        self.storage.add_file("TV/B.mkv")
        library = self.library(include_rules=("Movies/**",))
        result = self.scanner.scan(library)
        self.assertEqual(1, result.statistics.media_candidates)
        self.assertNotIn("TV", self.storage.list_calls)

    def test_exclude_priority_prunes_directories_and_temporary_files(self) -> None:
        self.storage.add_file("Movies/A.mkv")
        self.storage.add_file("sample/B.mkv")
        self.storage.add_file("download.mkv.part")
        library = self.library(exclude_rules=("**/sample/**", "*.part"))
        result = self.scanner.scan(library)
        self.assertEqual(1, result.statistics.media_candidates)
        self.assertNotIn("sample", self.storage.list_calls)

    def test_rule_kinds_path_filename_extension_directory_glob_regex(self) -> None:
        self.storage.add_file("Keep/A.mkv")
        self.storage.add_file("Keep/B.mp4")
        cases = (
            ScanRule(ScanRuleKind.PATH, "Keep/A.mkv"),
            ScanRule(ScanRuleKind.FILENAME, "A.mkv"),
            ScanRule(ScanRuleKind.EXTENSION, "mkv"),
            ScanRule(ScanRuleKind.GLOB, "Keep/*.mkv"),
            ScanRule(ScanRuleKind.REGEX, r"A\.mkv$"),
        )
        for index, rule in enumerate(cases):
            library = replace(self.library(), library_id=f"rules-{index}", include_rules=(rule,))
            result = self.scanner.scan(library)
            self.assertEqual(1, result.statistics.media_candidates)
        excluded = replace(
            self.library(),
            library_id="directory-rule",
            exclude_rules=(ScanRule(ScanRuleKind.DIRECTORY, "Keep"),),
        )
        self.assertEqual(0, self.scanner.scan(excluded).statistics.files_visited)

    def test_max_depth_zero_one_two_and_unlimited(self) -> None:
        self.storage.add_file("a.mkv")
        self.storage.add_file("one/b.mkv")
        self.storage.add_file("one/two/c.mkv")
        expected = {0: 1, 1: 2, 2: 3, None: 3}
        for depth, count in expected.items():
            library = replace(self.library(), library_id=f"depth-{depth}", max_depth=depth)
            self.assertEqual(count, self.scanner.scan(library).statistics.media_candidates)

    def test_symlinks_are_ignored_and_never_followed(self) -> None:
        original = self.storage.list

        def list_with_symlink(path: str):
            entries = list(original(path))
            if path == "":
                entries.append(StorageEntry("loop", "loop", StorageEntryType.SYMLINK, 0, NOW))
            return tuple(entries)

        self.storage.list = list_with_symlink
        result = self.scanner.scan(self.library())
        self.assertEqual(1, result.statistics.ignored)
        self.assertEqual([""], self.storage.list_calls)

    def test_stability_minimum_age(self) -> None:
        self.storage.add_file("recent.mkv", modified_at=NOW - timedelta(seconds=30))
        self.storage.add_file("old.mkv", modified_at=NOW - timedelta(seconds=120))
        library = self.library(stability_policy=FileStabilityPolicy(minimum_age_seconds=60))
        result = self.scanner.scan(library)
        self.assertEqual(1, result.statistics.unstable)
        self.assertEqual(FileScanStatus.READY, self.records()["old.mkv"].scan_status)

    def test_stable_size_progresses_across_scans_and_reaches_ready(self) -> None:
        self.storage.add_file("movie.mkv", size=10)
        policy = FileStabilityPolicy(stable_size_duration_seconds=60)
        library = self.library(stability_policy=policy)
        first = self.scanner.scan(library)
        self.assertEqual(1, first.statistics.unstable)
        self.clock.advance(30)
        second = self.scanner.scan(library)
        self.assertEqual(1, second.statistics.unstable)
        self.assertEqual(NOW, self.records()["movie.mkv"].stable_since)
        self.clock.advance(31)
        third = self.scanner.scan(library)
        self.assertEqual(1, third.statistics.media_candidates)

    def test_size_or_modified_change_resets_stability(self) -> None:
        self.storage.add_file("movie.mkv", size=10)
        library = self.library(
            stability_policy=FileStabilityPolicy(stable_size_duration_seconds=60)
        )
        self.scanner.scan(library)
        self.clock.advance(30)
        self.scanner.scan(library)
        self.storage.files["movie.mkv"] = (11, self.storage.files["movie.mkv"][1])
        self.clock.advance(40)
        self.scanner.scan(library)
        record = self.records()["movie.mkv"]
        self.assertEqual(FileChange.MODIFIED, record.change)
        self.assertIsNone(record.stable_since)
        self.storage.files["movie.mkv"] = (11, NOW)
        self.clock.advance(60)
        self.scanner.scan(library)
        self.assertIsNone(self.records()["movie.mkv"].stable_since)

    def test_incremental_new_unchanged_modified(self) -> None:
        self.storage.add_file("A.mkv", 1)
        self.storage.add_file("B.mkv", 1)
        library = self.library(scan_mode=ScanMode.INCREMENTAL)
        self.scanner.scan(library)
        self.assertEqual(FileChange.NEW, self.records()["A.mkv"].change)
        self.clock.advance(1)
        self.scanner.scan(library)
        self.assertEqual(FileChange.UNCHANGED, self.records()["A.mkv"].change)
        self.storage.files["A.mkv"] = (2, NOW)
        self.clock.advance(1)
        self.scanner.scan(library)
        records = self.records()
        self.assertEqual(FileChange.MODIFIED, records["A.mkv"].change)
        self.assertEqual(FileChange.UNCHANGED, records["B.mkv"].change)

    def test_full_scan_marks_missing_but_incremental_does_not(self) -> None:
        self.storage.add_file("A.mkv")
        self.storage.add_file("B.mkv")
        library = self.library()
        self.scanner.scan(library)
        del self.storage.files["B.mkv"]
        self.clock.advance(1)
        self.scanner.scan(library, mode=ScanMode.INCREMENTAL)
        self.assertNotEqual(FileScanStatus.MISSING, self.records()["B.mkv"].scan_status)
        self.scanner.scan(library, mode=ScanMode.FULL)
        missing = self.records()["B.mkv"]
        self.assertEqual(FileScanStatus.MISSING, missing.scan_status)
        self.assertIsNotNone(missing.missing_since)

    def test_partial_directory_failure_protects_old_index(self) -> None:
        self.storage.add_file("good/A.mkv")
        self.storage.add_file("blocked/B.mkv")
        library = self.library()
        self.scanner.scan(library)
        del self.storage.files["good/A.mkv"]
        self.storage.list_errors["blocked"] = StorageErrorCode.PERMISSION_DENIED
        result = self.scanner.scan(library)
        self.assertEqual(TaskStatus.PARTIAL_SUCCESS, result.status)
        records = self.records()
        # An incomplete full scan cannot prove that an unvisited source is missing.
        self.assertEqual(FileScanStatus.READY, records["good/A.mkv"].scan_status)
        self.assertNotEqual(FileScanStatus.MISSING, records["blocked/B.mkv"].scan_status)

    def test_pruned_directory_is_not_reconciled_as_missing(self) -> None:
        self.storage.add_file("Keep/A.mkv")
        self.storage.add_file("Excluded/B.mkv")
        library = self.library()
        self.scanner.scan(library)
        restricted = replace(library, exclude_rules=("Excluded/**",))
        self.scanner.scan(restricted)
        self.assertNotEqual(FileScanStatus.MISSING, self.records()["Excluded/B.mkv"].scan_status)

    def test_failed_root_scan_does_not_reconcile_missing(self) -> None:
        self.storage.add_file("A.mkv")
        library = self.library()
        self.scanner.scan(library)
        del self.storage.files["A.mkv"]
        self.storage.list_errors[""] = StorageErrorCode.AUTHENTICATION_FAILED
        result = self.scanner.scan(library)
        self.assertEqual(TaskStatus.FAILED, result.status)
        self.assertNotEqual(FileScanStatus.MISSING, self.records()["A.mkv"].scan_status)

    def test_cancelled_scan_stops_new_lists_and_never_marks_missing(self) -> None:
        self.storage.add_file("old.mkv")
        library = self.library()
        self.scanner.scan(library)
        del self.storage.files["old.mkv"]
        self.storage.add_file("one/A.mkv")
        token = CancellationToken()
        result = self.scanner.scan(
            library, cancellation=token, on_progress=lambda _: token.cancel()
        )
        self.assertEqual(TaskStatus.CANCELLED, result.status)
        self.assertNotEqual(FileScanStatus.MISSING, self.records()["old.mkv"].scan_status)
        self.assertNotIn("one", self.storage.list_calls[-1:])

    def test_concurrency_is_bounded(self) -> None:
        for index in range(8):
            self.storage.add_file(f"dir-{index}/A.mkv")
        self.storage.list_delay = 0.01
        library = self.library(max_scan_concurrency=3)
        self.scanner.scan(library)
        self.assertGreater(self.storage.max_active_lists, 1)
        self.assertLessEqual(self.storage.max_active_lists, 3)

    def test_batch_persistence_limits_batch_size(self) -> None:
        for index in range(7):
            self.storage.add_file(f"file-{index}.mkv")
        self.scanner.scan(self.library(persistence_batch_size=3))
        self.assertEqual([3, 3, 1], self.index.batch_sizes)

    def test_duplicate_scan_lock(self) -> None:
        self.storage.block_list = threading.Event()
        result: list[object] = []

        def scan() -> None:
            result.append(self.scanner.scan(self.library()))

        thread = threading.Thread(target=scan)
        thread.start()
        self.storage.entered_list.wait(1)
        with self.assertRaises(ScanAlreadyRunningError):
            self.scanner.scan(self.library())
        self.storage.block_list.set()
        thread.join(2)
        self.assertEqual(1, len(result))

    def test_multiple_and_overlapping_libraries_have_distinct_identity(self) -> None:
        self.storage.add_file("Downloads/Movies/A.mkv")
        first = ResourceLibrary("all", "All", "fake", "Downloads", exclude_rules=())
        second = ResourceLibrary("movies", "Movies", "fake", "Downloads/Movies", exclude_rules=())
        self.assertEqual(
            ("all", "movies"), ResourceLibraryService.overlapping_pairs((first, second))[0]
        )
        self.scanner.scan(first)
        self.scanner.scan(second)
        records = self.index.snapshot()
        self.assertEqual(2, len(records))
        self.assertNotEqual(records[0].identity, records[1].identity)

    def test_resource_library_validation(self) -> None:
        self.storage.add_directory("Downloads")
        service = ResourceLibraryService({"fake": self.storage})
        self.assertEqual((), service.validate(ResourceLibrary("id", "name", "fake", "/Downloads")))
        self.assertTrue(service.validate(ResourceLibrary("bad", "bad", "fake", "/missing")))
        self.assertTrue(ResourceLibraryService({}).validate(self.library()))
        with self.assertRaises(ValueError):
            self.library(max_depth=-1)
        with self.assertRaises(re.error):
            ScanRule(ScanRuleKind.REGEX, "[")


class LocalStorageScannerIntegrationTests(unittest.TestCase):
    def test_expected_tree_filtering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                "Movies/A.mkv": b"a",
                "Movies/B.mp4": b"b",
                "Movies/downloading.mkv.part": b"partial",
                "TV/Show.S01E01.mkv": b"show",
                "Ignore/C.mkv": b"ignored",
                "readme.txt": b"text",
            }
            for name, content in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                old = time.time() - 3600
                os.utime(target, (old, old))
            storage = LocalStorage("local", root, read_only=True)
            repository = InMemoryFileIndexRepository()
            scanner = StorageScanner({"local": storage}, repository)
            library = ResourceLibrary(
                "downloads",
                "Downloads",
                "local",
                "",
                exclude_rules=("Ignore/**", "*.part"),
                file_extensions=("mkv", "mp4"),
            )
            result = scanner.scan(library)
            ready = {
                record.path
                for record in repository.list_by_resource_library("downloads")
                if record.scan_status is FileScanStatus.READY
            }
            self.assertEqual({"Movies/A.mkv", "Movies/B.mp4", "TV/Show.S01E01.mkv"}, ready)
            self.assertEqual(3, result.statistics.media_candidates)

    def test_sqlite_file_index_persists_across_repository_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "file-index.sqlite3"
            storage = FakeStorage("durable")
            storage.add_file("A.mkv")
            library = ResourceLibrary("durable-library", "Durable", "durable", "")
            with SQLiteFileIndexRepository(database) as repository:
                result = StorageScanner({"durable": storage}, repository).scan(library)
                self.assertEqual(TaskStatus.COMPLETED, result.status)
                del storage.files["A.mkv"]
                StorageScanner({"durable": storage}, repository).scan(library)
            with SQLiteFileIndexRepository(database) as reopened:
                records = reopened.list_by_resource_library("durable-library")
                self.assertEqual(1, len(records))
                self.assertEqual("A.mkv", records[0].path)
                self.assertEqual(FileScanStatus.MISSING, records[0].scan_status)
