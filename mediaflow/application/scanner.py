from __future__ import annotations

import fnmatch
import re
import threading
import uuid
from collections import deque
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import PurePosixPath
from urllib.parse import urlparse

from mediaflow.domain.file_index import FileIndexRecord, FileIndexRepository
from mediaflow.domain.library import ResourceLibrary, ScanMode, ScanRule, ScanRuleKind
from mediaflow.domain.logging import Logger, LogLevel
from mediaflow.domain.scanner import (
    CancellationToken,
    DiscoveredFile,
    DiscoveryCallback,
    FileChange,
    FileScanStatus,
    ProgressCallback,
    ScanError,
    ScanResult,
    ScanStatistics,
)
from mediaflow.domain.storage import (
    Storage,
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
)
from mediaflow.domain.tasks import ScanTask, TaskStatus


class ScanAlreadyRunningError(RuntimeError):
    pass


@dataclass
class _Counters:
    directories_visited: int = 0
    files_visited: int = 0
    media_candidates: int = 0
    ignored: int = 0
    unstable: int = 0
    errors: int = 0

    def snapshot(self) -> ScanStatistics:
        return ScanStatistics(
            self.directories_visited,
            self.files_visited,
            self.media_candidates,
            self.ignored,
            self.unstable,
            self.errors,
        )


class ResourceLibraryService:
    def __init__(self, storages: dict[str, Storage]) -> None:
        self._storages = storages

    def validate(self, library: ResourceLibrary) -> tuple[str, ...]:
        errors: list[str] = []
        storage = self._storages.get(library.storage_id)
        if storage is None:
            errors.append("storage does not exist or is disabled")
            return tuple(errors)
        try:
            root = normalize_resource_root(library.root_path)
            entry = storage.stat(root)
            if not entry.is_directory:
                errors.append("root path is not a directory")
        except (ValueError, StorageError):
            errors.append("root path does not exist or is inaccessible")
        return tuple(errors)

    @staticmethod
    def overlapping_pairs(libraries: tuple[ResourceLibrary, ...]) -> tuple[tuple[str, str], ...]:
        pairs: list[tuple[str, str]] = []
        for index, left in enumerate(libraries):
            left_root = normalize_resource_root(left.root_path)
            for right in libraries[index + 1 :]:
                if left.storage_id != right.storage_id:
                    continue
                right_root = normalize_resource_root(right.root_path)
                if _contains(left_root, right_root) or _contains(right_root, left_root):
                    pairs.append((left.library_id, right.library_id))
        return tuple(pairs)


class StorageScanner:
    """Storage-port-only scanner with bounded directory concurrency and batched persistence."""

    def __init__(
        self,
        storages: dict[str, Storage],
        file_index: FileIndexRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        logger: Logger | None = None,
    ) -> None:
        self._storages = storages
        self._file_index = file_index
        self._clock = clock
        self._logger = logger
        self._active_libraries: set[str] = set()
        self._active_lock = threading.Lock()

    def scan(
        self,
        resource_library: ResourceLibrary,
        *,
        mode: ScanMode | None = None,
        cancellation: CancellationToken | None = None,
        on_progress: ProgressCallback | None = None,
        on_discovered: DiscoveryCallback | None = None,
    ) -> ScanResult:
        self._acquire(resource_library.library_id)
        try:
            return self._scan(
                resource_library,
                mode or resource_library.scan_mode,
                cancellation or CancellationToken(),
                on_progress,
                on_discovered,
            )
        finally:
            self._release(resource_library.library_id)

    def run_task(
        self,
        task: ScanTask,
        resource_library: ResourceLibrary,
        *,
        cancellation: CancellationToken | None = None,
        on_progress: ProgressCallback | None = None,
        on_discovered: DiscoveryCallback | None = None,
    ) -> tuple[ScanTask, ScanResult]:
        if task.resource_library_id != resource_library.library_id:
            raise ValueError("scan task and resource library do not match")
        mode = ScanMode(task.mode)
        result = self.scan(
            resource_library,
            mode=mode,
            cancellation=cancellation,
            on_progress=on_progress,
            on_discovered=on_discovered,
        )
        statistics = result.statistics
        completed_task = replace(
            task,
            status=result.status,
            started_at=result.started_at,
            completed_at=result.completed_at,
            progress={
                "directories_visited": statistics.directories_visited,
                "files_visited": statistics.files_visited,
                "candidates_found": statistics.media_candidates,
                "ignored": statistics.ignored,
                "unstable": statistics.unstable,
                "errors": statistics.errors,
            },
            errors=result.errors,
        )
        return completed_task, result

    def _scan(
        self,
        library: ResourceLibrary,
        mode: ScanMode,
        cancellation: CancellationToken,
        on_progress: ProgressCallback | None,
        on_discovered: DiscoveryCallback | None,
    ) -> ScanResult:
        scan_id = uuid.uuid4().hex
        started = self._clock()
        counters = _Counters()
        errors: list[ScanError] = []
        if not library.enabled:
            raise ValueError("resource library is disabled")
        storage = self._storages.get(library.storage_id)
        if storage is None:
            raise ValueError("resource library storage does not exist")
        root = normalize_resource_root(library.root_path)
        self._log(
            LogLevel.INFO,
            "scan started",
            library=library.library_id,
            storage=storage.storage_id,
            root=root,
        )

        try:
            root_entry = storage.stat(root)
            if not root_entry.is_directory:
                raise StorageError(
                    code=root_entry_error_code(),
                    operation="stat",
                    path=root,
                    message="scan root is not a directory",
                )
        except StorageError as error:
            scan_error = self._scan_error(root, error)
            completed = self._clock()
            result = ScanResult(
                scan_id,
                library.library_id,
                mode,
                TaskStatus.FAILED,
                started,
                completed,
                ScanStatistics(errors=1),
                (scan_error,),
            )
            self._log(LogLevel.ERROR, "scan failed", library=library.library_id, errors=1)
            return result

        pending: deque[tuple[str, int]] = deque([(root, 0)])
        protected: list[str] = []
        batch: list[FileIndexRecord] = []
        status = TaskStatus.COMPLETED
        root_failed = False
        with ThreadPoolExecutor(
            max_workers=library.max_scan_concurrency, thread_name_prefix="mediaflow-scan"
        ) as executor:
            futures: dict[Future[tuple[StorageEntry, ...]], tuple[str, int]] = {}
            while pending or futures:
                while (
                    pending
                    and len(futures) < library.max_scan_concurrency
                    and not cancellation.is_cancelled
                ):
                    directory, depth = pending.popleft()
                    futures[executor.submit(lambda path=directory: tuple(storage.list(path)))] = (
                        directory,
                        depth,
                    )
                if not futures:
                    break
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    directory, depth = futures.pop(future)
                    if cancellation.is_cancelled:
                        continue
                    try:
                        entries = future.result()
                    except StorageError as error:
                        errors.append(self._scan_error(directory, error))
                        counters.errors += 1
                        if depth == 0 and directory == root:
                            status = TaskStatus.FAILED
                            root_failed = True
                            pending.clear()
                        else:
                            protected.append(directory)
                            status = TaskStatus.PARTIAL_SUCCESS
                        continue
                    counters.directories_visited += 1
                    for entry in entries:
                        if cancellation.is_cancelled:
                            break
                        relative = self._relative(entry.path, root)
                        if entry.entry_type is StorageEntryType.DIRECTORY:
                            if self._excluded(
                                library.exclude_rules, relative, entry.name, "", True
                            ):
                                protected.append(entry.path)
                                continue
                            if not self._directory_may_match(library.include_rules, relative):
                                protected.append(entry.path)
                                continue
                            if library.max_depth is None or depth < library.max_depth:
                                pending.append((entry.path, depth + 1))
                            else:
                                protected.append(entry.path)
                            continue
                        if entry.entry_type is not StorageEntryType.FILE:
                            counters.ignored += 1
                            continue
                        counters.files_visited += 1
                        record, discovered = self._process_file(
                            library, storage, entry, relative, scan_id, self._clock()
                        )
                        batch.append(record)
                        if discovered.status is FileScanStatus.READY:
                            counters.media_candidates += 1
                        elif discovered.status is FileScanStatus.UNSTABLE:
                            counters.unstable += 1
                        elif discovered.status is FileScanStatus.IGNORED:
                            counters.ignored += 1
                        if on_discovered:
                            on_discovered(discovered)
                        if len(batch) >= library.persistence_batch_size:
                            self._file_index.batch_upsert(tuple(batch))
                            batch.clear()
                    if on_progress:
                        on_progress(counters.snapshot())
                if root_failed:
                    for future in futures:
                        future.cancel()
                    futures.clear()
                    break
            if cancellation.is_cancelled:
                status = TaskStatus.CANCELLED

        if batch:
            self._file_index.batch_upsert(tuple(batch))
        completed = self._clock()
        if mode is ScanMode.FULL and status in {TaskStatus.COMPLETED, TaskStatus.PARTIAL_SUCCESS}:
            self._file_index.reconcile_missing(
                library.library_id,
                scan_id,
                completed,
                protected_prefixes=tuple(protected),
            )
        result = ScanResult(
            scan_id,
            library.library_id,
            mode,
            status,
            started,
            completed,
            counters.snapshot(),
            tuple(errors),
        )
        self._log(
            LogLevel.INFO,
            "scan completed",
            library=library.library_id,
            status=status.value,
            directories=counters.directories_visited,
            files=counters.files_visited,
            candidates=counters.media_candidates,
            ignored=counters.ignored,
            unstable=counters.unstable,
            errors=counters.errors,
        )
        return result

    def _process_file(
        self,
        library: ResourceLibrary,
        storage: Storage,
        entry: StorageEntry,
        relative: str,
        scan_id: str,
        now: datetime,
    ) -> tuple[FileIndexRecord, DiscoveredFile]:
        extension = PurePosixPath(entry.name).suffix.lower().lstrip(".")
        previous = self._file_index.find_by_path(storage.storage_id, library.library_id, entry.path)
        change = (
            FileChange.NEW
            if previous is None
            else FileChange.UNCHANGED
            if previous.size == entry.size and previous.modified_at == entry.modified_at
            else FileChange.MODIFIED
        )
        ignored = extension not in library.file_extensions
        ignored = ignored or self._excluded(
            library.exclude_rules, relative, entry.name, extension, False
        )
        ignored = ignored or not self._included(
            library.include_rules, relative, entry.name, extension
        )
        stable_since = None
        if previous and change is FileChange.UNCHANGED:
            stable_since = previous.stable_since or previous.last_seen_at
        if ignored:
            status = FileScanStatus.IGNORED
        else:
            age = max(0.0, (now - entry.modified_at).total_seconds())
            stable_duration = (
                (now - stable_since).total_seconds() if stable_since is not None else 0.0
            )
            required_age = max(
                library.stability_policy.minimum_age_seconds,
                library.stability_policy.modified_threshold_seconds,
            )
            stable = age >= required_age and (
                library.stability_policy.stable_size_duration_seconds == 0
                or stable_since is not None
                and stable_duration >= library.stability_policy.stable_size_duration_seconds
            )
            status = FileScanStatus.READY if stable else FileScanStatus.UNSTABLE
        first_seen = previous.first_seen_at if previous else now
        created = previous.created_at if previous else now
        record = FileIndexRecord(
            file_id=(
                previous.file_id
                if previous
                else uuid.uuid5(
                    uuid.NAMESPACE_URL, f"{storage.storage_id}:{library.library_id}:{entry.path}"
                ).hex
            ),
            storage_id=storage.storage_id,
            resource_library_id=library.library_id,
            path=entry.path,
            filename=entry.name,
            extension=extension,
            size=entry.size,
            modified_at=entry.modified_at,
            first_seen_at=first_seen,
            last_seen_at=now,
            stable_since=stable_since,
            scan_status=status,
            change=change,
            created_at=created,
            updated_at=now,
            missing_since=None,
            last_scan_id=scan_id,
        )
        discovered = DiscoveredFile(
            storage.storage_id,
            library.library_id,
            entry.path,
            entry.name,
            extension,
            entry.size,
            entry.modified_at,
            now,
            status,
            change,
        )
        return record, discovered

    @staticmethod
    def _included(
        rules: tuple[ScanRule | str, ...], path: str, filename: str, extension: str
    ) -> bool:
        return not rules or any(_matches(rule, path, filename, extension, False) for rule in rules)

    @staticmethod
    def _excluded(
        rules: tuple[ScanRule | str, ...],
        path: str,
        filename: str,
        extension: str,
        directory: bool,
    ) -> bool:
        return any(_matches(rule, path, filename, extension, directory) for rule in rules)

    @staticmethod
    def _directory_may_match(rules: tuple[ScanRule | str, ...], path: str) -> bool:
        if not rules:
            return True
        for raw_rule in rules:
            rule = (
                raw_rule
                if isinstance(raw_rule, ScanRule)
                else ScanRule(ScanRuleKind.GLOB, raw_rule)
            )
            if rule.kind is ScanRuleKind.REGEX:
                return True
            if rule.kind in {ScanRuleKind.FILENAME, ScanRuleKind.EXTENSION}:
                return True
            pattern = rule.pattern.lstrip("/")
            fixed = re.split(r"[*?[{]", pattern, maxsplit=1)[0].rstrip("/")
            if (
                not fixed
                or fixed == path
                or fixed.startswith(path + "/")
                or path.startswith(fixed + "/")
            ):
                return True
        return False

    @staticmethod
    def _relative(path: str, root: str) -> str:
        if not root:
            return path.strip("/")
        value = path.strip("/")
        root_value = root.strip("/")
        return "" if value == root_value else value.removeprefix(root_value + "/")

    def _scan_error(self, path: str, error: StorageError) -> ScanError:
        return ScanError(path, error.operation, error.code, self._clock())

    def _acquire(self, library_id: str) -> None:
        with self._active_lock:
            if library_id in self._active_libraries:
                raise ScanAlreadyRunningError(
                    f"scan already running for resource library {library_id}"
                )
            self._active_libraries.add(library_id)

    def _release(self, library_id: str) -> None:
        with self._active_lock:
            self._active_libraries.discard(library_id)

    def _log(self, level: LogLevel, message: str, **context: object) -> None:
        if self._logger:
            self._logger.log(level, message, **context)


def normalize_resource_root(path: str) -> str:
    if not isinstance(path, str) or "\x00" in path or urlparse(path).scheme:
        raise ValueError("invalid resource library root")
    parts: list[str] = []
    for part in path.replace("\\", "/").split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError("resource library root traversal")
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def _matches(
    raw_rule: ScanRule | str, path: str, filename: str, extension: str, directory: bool
) -> bool:
    rule = raw_rule if isinstance(raw_rule, ScanRule) else ScanRule(ScanRuleKind.GLOB, raw_rule)
    pattern = rule.pattern
    if rule.kind is ScanRuleKind.PATH:
        return path == pattern.strip("/")
    if rule.kind is ScanRuleKind.FILENAME:
        return filename == pattern
    if rule.kind is ScanRuleKind.EXTENSION:
        return extension.lower() == pattern.lower().lstrip(".")
    if rule.kind is ScanRuleKind.DIRECTORY:
        return directory and (path == pattern.strip("/") or filename == pattern.strip("/"))
    if rule.kind is ScanRuleKind.REGEX:
        return re.search(pattern, path) is not None
    normalized = path.strip("/")
    candidates = (normalized, filename, "/" + normalized)
    patterns = (pattern, pattern.removeprefix("**/"))
    if directory:
        for candidate_pattern in patterns:
            base = candidate_pattern.removesuffix("/**").rstrip("/")
            if base != candidate_pattern and normalized == base:
                return True
    return any(
        fnmatch.fnmatchcase(candidate, candidate_pattern)
        for candidate in candidates
        for candidate_pattern in patterns
    )


def _contains(parent: str, child: str) -> bool:
    return not parent or child == parent or child.startswith(parent.rstrip("/") + "/")


def root_entry_error_code() -> StorageErrorCode:
    return StorageErrorCode.INVALID_PATH
