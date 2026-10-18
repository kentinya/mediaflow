"""Bounded, read-only discovery of one ResourceLibrary scope.

Discovery answers exactly one question: *which current sources inside this
configured scope satisfy the configured include/exclude/extension/depth and
stability rules right now?*  It is an ordinary in-workflow stage, not a product:

* every fact comes from one bounded ``list_page``/``stat`` observation through
  the Storage port;
* nothing is persisted here.  There is no global file catalog, no
  New/Modified/Unchanged/Missing reconciliation and no long-lived per-file
  record, so a newly appearing file at a previously seen path is simply a
  current candidate;
* stability is proven from the caller's own durable observation of the same
  scope (see :mod:`mediaflow.application.scan_filters`), which is what keeps
  ``stableSizeDurationSeconds`` a real elapsed interval instead of a first-stat
  shortcut;
* no content read, no hash, no Provider call, no mutation.

The filter/stability predicates live in one shared pure module so this walk and
the bounded Files discovery stage cannot drift apart.
"""

from __future__ import annotations

import fnmatch as _fnmatch
import re as _re
import threading
import uuid
from collections import deque
from collections.abc import Callable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from urllib.parse import urlparse

# The ResourceLibrary include/exclude/extension/depth and stability semantics
# live in one shared pure module so the bounded Files discovery stage and this
# walker cannot drift apart.  These names are re-exported for the existing
# private helpers below and for any adapter that imports them.
from mediaflow.application.scan_filters import (  # noqa: F401
    ObservedSource,
    StabilityVerdict,
    classify_entry,
    directory_may_match,
    entry_extension,
    excluded,
    included,
    stability_decision,
    stability_verdict,
)
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
from mediaflow.domain.source_evidence import (
    OccurrenceState,
    occurrence_id_for,
    source_fingerprint,
)
from mediaflow.domain.storage import (
    Storage,
    StorageEntry,
    StorageEntryType,
    StorageError,
)

__all__ = [
    "DiscoveryObservation",
    "ResourceLibraryService",
    "ScanAlreadyRunningError",
    "StorageScanner",
    "normalize_resource_root",
    "normalize_source_path",
    "root_entry_error_code",
]


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


@dataclass(frozen=True)
class DiscoveryObservation:
    """One bounded, in-workflow observation of a real Storage source.

    It is the *only* thing this module produces for a file: the current entry
    facts plus the deterministic source evidence an execution admission needs.
    It is never persisted here and never becomes a catalog row.
    """

    storage_id: str
    resource_library_id: str
    path: str
    filename: str
    extension: str
    size: int
    modified_at: datetime
    status: FileScanStatus
    change: FileChange
    occurrence_id: str | None
    fingerprint: str | None
    fingerprint_algorithm: str | None
    fingerprint_evidence: dict[str, object] | None
    occurrence_state: OccurrenceState
    stable_since: datetime | None

    def discovered_file(self, observed_at: datetime) -> DiscoveredFile:
        return DiscoveredFile(
            self.storage_id,
            self.resource_library_id,
            self.path,
            self.filename,
            self.extension,
            self.size,
            self.modified_at,
            observed_at,
            self.status,
            self.change,
            self.occurrence_id,
            self.fingerprint,
            self.occurrence_state.value,
            self.stable_since,
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
    """Storage-port-only, metadata-only, mutation-free discovery walker.

    Despite the historical name it persists nothing.  It exists so that exactly
    one implementation decides what the configured scope currently contains, and
    every consumer (the organizer pipeline, bounded Files discovery, recovery)
    agrees on include/exclude/depth/stability and on the source evidence that an
    execution admission re-validates later.
    """

    def __init__(
        self,
        storages: Mapping[str, Storage] | dict[str, Storage],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        logger: Logger | None = None,
    ) -> None:
        self._storages = dict(storages)
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
        previous: Mapping[str, ObservedSource] | None = None,
    ) -> ScanResult:
        """Walk one library and report its current candidates.

        ``previous`` is the caller's own durable observation of this exact
        scope, used only to prove a stable-size interval.  Passing nothing is
        legal and honest: a fresh scope then simply stays ``unstable`` until a
        later observation proves the configured interval.
        """

        self._acquire(resource_library.library_id)
        try:
            return self._scan(
                resource_library,
                mode or resource_library.scan_mode,
                cancellation or CancellationToken(),
                on_progress,
                on_discovered,
                dict(previous or {}),
            )
        finally:
            self._release(resource_library.library_id)

    def observe_file(
        self,
        resource_library: ResourceLibrary,
        path: str,
        *,
        mode: ScanMode | None = None,
        expected_occurrence_id: str | None = None,
        expected_fingerprint: str | None = None,
        cancellation: CancellationToken | None = None,
        on_progress: ProgressCallback | None = None,
        on_discovered: DiscoveryCallback | None = None,
    ) -> ScanResult:
        """Observe exactly one Storage source without traversing its library."""

        if (expected_occurrence_id is None) != (expected_fingerprint is None):
            raise ValueError("expected source occurrence and fingerprint must be provided together")
        self._acquire(resource_library.library_id)
        try:
            scan_id = uuid.uuid4().hex
            started = self._clock()
            counters = _Counters()
            errors: list[ScanError] = []
            token = cancellation or CancellationToken()
            selected_mode = mode or resource_library.scan_mode
            if token.is_cancelled:
                return ScanResult(
                    scan_id,
                    resource_library.library_id,
                    selected_mode,
                    "cancelled",
                    started,
                    self._clock(),
                    counters.snapshot(),
                    (),
                )
            if not resource_library.enabled:
                raise ValueError("resource library is disabled")
            storage = self._storages.get(resource_library.storage_id)
            if storage is None:
                raise ValueError("resource library storage does not exist")
            root = normalize_resource_root(resource_library.root_path)
            source_path = normalize_source_path(path)
            if not source_path or not _contains(root, source_path) or source_path == root:
                error = StorageError(
                    "invalid_path",
                    "stat",
                    source_path,
                    "source is outside the configured ResourceLibrary",
                )
                return self._observation_failure(
                    scan_id, resource_library, selected_mode, started, source_path, error
                )
            try:
                entry = storage.stat(source_path)
                if entry.entry_type is not StorageEntryType.FILE:
                    raise StorageError(
                        "invalid_path",
                        "stat",
                        source_path,
                        "manual Scan source is not a file",
                    )
                observed = source_fingerprint(
                    storage.storage_id, resource_library.library_id, entry
                )
                observed_occurrence_id = occurrence_id_for(
                    storage.storage_id,
                    resource_library.library_id,
                    entry.path,
                    observed.value,
                )
                if expected_fingerprint is not None and (
                    observed.value != expected_fingerprint
                    or observed_occurrence_id != expected_occurrence_id
                ):
                    raise StorageError(
                        "invalid_path",
                        "stat",
                        source_path,
                        "current source occurrence changed",
                    )
            except StorageError as error:
                return self._observation_failure(
                    scan_id, resource_library, selected_mode, started, source_path, error
                )
            relative = self._relative(entry.path, root)
            discovered = self._observe(
                resource_library, storage, entry, relative, now=self._clock()
            )
            counters.files_visited = 1
            if discovered.status is FileScanStatus.READY:
                counters.media_candidates = 1
            elif discovered.status is FileScanStatus.UNSTABLE:
                counters.unstable = 1
            elif discovered.status is FileScanStatus.IGNORED:
                counters.ignored = 1
            if on_discovered:
                on_discovered(discovered)
            if on_progress:
                on_progress(counters.snapshot())
            return ScanResult(
                scan_id,
                resource_library.library_id,
                selected_mode,
                "cancelled" if token.is_cancelled else "completed",
                started,
                self._clock(),
                counters.snapshot(),
                tuple(errors),
            )
        finally:
            self._release(resource_library.library_id)

    def _observation_failure(
        self,
        scan_id: str,
        library: ResourceLibrary,
        mode: ScanMode,
        started: datetime,
        path: str,
        error: StorageError,
    ) -> ScanResult:
        scan_error = self._scan_error(path, error)
        return ScanResult(
            scan_id,
            library.library_id,
            mode,
            "failed",
            started,
            self._clock(),
            ScanStatistics(files_visited=1, errors=1),
            (scan_error,),
        )

    def _scan(
        self,
        library: ResourceLibrary,
        mode: ScanMode,
        cancellation: CancellationToken,
        on_progress: ProgressCallback | None,
        on_discovered: DiscoveryCallback | None,
        observations: dict[str, ObservedSource],
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
            "discovery started",
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
            result = ScanResult(
                scan_id,
                library.library_id,
                mode,
                "failed",
                started,
                self._clock(),
                ScanStatistics(errors=1),
                (scan_error,),
            )
            self._log(LogLevel.ERROR, "discovery failed", library=library.library_id, errors=1)
            return result

        pending: deque[tuple[str, int]] = deque([(root, 0)])
        status = "completed"
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
                            status = "failed"
                            root_failed = True
                            pending.clear()
                        else:
                            status = "partial_success"
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
                                continue
                            if not self._directory_may_match(library.include_rules, relative):
                                continue
                            if library.max_depth is None or depth < library.max_depth:
                                pending.append((entry.path, depth + 1))
                            continue
                        if entry.entry_type is not StorageEntryType.FILE:
                            counters.ignored += 1
                            continue
                        counters.files_visited += 1
                        discovered = self._observe(
                            library,
                            storage,
                            entry,
                            relative,
                            now=self._clock(),
                            previous=observations.get(entry.path),
                        )
                        if discovered.status is FileScanStatus.READY:
                            counters.media_candidates += 1
                        elif discovered.status is FileScanStatus.UNSTABLE:
                            counters.unstable += 1
                        elif discovered.status is FileScanStatus.IGNORED:
                            counters.ignored += 1
                        if on_discovered:
                            on_discovered(discovered)
                    if on_progress:
                        on_progress(counters.snapshot())
                if root_failed:
                    for future in futures:
                        future.cancel()
                    futures.clear()
                    break
            if cancellation.is_cancelled:
                status = "cancelled"

        result = ScanResult(
            scan_id,
            library.library_id,
            mode,
            status,
            started,
            self._clock(),
            counters.snapshot(),
            tuple(errors),
        )
        self._log(
            LogLevel.INFO,
            "discovery completed",
            library=library.library_id,
            status=status,
            directories=counters.directories_visited,
            files=counters.files_visited,
            candidates=counters.media_candidates,
            ignored=counters.ignored,
            unstable=counters.unstable,
            errors=counters.errors,
        )
        return result

    def _observe(
        self,
        library: ResourceLibrary,
        storage: Storage,
        entry: StorageEntry,
        relative: str,
        *,
        now: datetime,
        previous: ObservedSource | None = None,
    ) -> DiscoveredFile:
        extension = PurePosixPath(entry.name).suffix.lower().lstrip(".")
        observed_fingerprint = source_fingerprint(storage.storage_id, library.library_id, entry)
        unchanged = bool(
            previous is not None and previous.matches(entry, observed_fingerprint.value)
        )
        change = (
            FileChange.NEW
            if previous is None
            else FileChange.UNCHANGED
            if unchanged
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
        if unchanged and previous is not None and not ignored:
            stable_since = previous.stable_since or previous.observed_at
        if ignored:
            status = FileScanStatus.IGNORED
        else:
            verdict = stability_decision(
                library.stability_policy,
                entry,
                now=now,
                unchanged_previous=unchanged,
                observed_since=stable_since,
            )
            if verdict is StabilityVerdict.STABLE:
                status = FileScanStatus.READY
            else:
                status = FileScanStatus.UNSTABLE
        occurrence_id = (
            occurrence_id_for(
                storage.storage_id,
                library.library_id,
                entry.path,
                observed_fingerprint.value,
            )
            if observed_fingerprint.state is OccurrenceState.VERIFIED
            else None
        )
        observation = DiscoveryObservation(
            storage.storage_id,
            library.library_id,
            entry.path,
            entry.name,
            extension,
            entry.size,
            entry.modified_at,
            status,
            change,
            occurrence_id,
            observed_fingerprint.value,
            observed_fingerprint.algorithm,
            observed_fingerprint.evidence,
            observed_fingerprint.state,
            stable_since,
        )
        return observation.discovered_file(now)

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
        return directory_may_match(rules, path)

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
                    f"discovery already running for resource library {library_id}"
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


def normalize_source_path(path: str) -> str:
    """Normalize one Storage-relative source path without permitting traversal."""

    if (
        not isinstance(path, str)
        or "\x00" in path
        or urlparse(path).scheme
        or path.startswith(("/", "\\"))
        or (len(path) > 1 and path[1] == ":")
    ):
        raise ValueError("invalid source path")
    parts: list[str] = []
    for part in path.replace("\\", "/").split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError("source path traversal")
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
        return _re.search(pattern, path) is not None
    normalized = path.strip("/")
    candidates = (normalized, filename, "/" + normalized)
    patterns = (pattern, pattern.removeprefix("**/"))
    if directory:
        for candidate_pattern in patterns:
            base = candidate_pattern.removesuffix("/**").rstrip("/")
            if base != candidate_pattern and normalized == base:
                return True
    return any(
        _fnmatch.fnmatchcase(candidate, candidate_pattern)
        for candidate in candidates
        for candidate_pattern in patterns
    )


def _contains(parent: str, child: str) -> bool:
    return not parent or child == parent or child.startswith(parent.rstrip("/") + "/")


def root_entry_error_code() -> str:
    return "invalid_path"
