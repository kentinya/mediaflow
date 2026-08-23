from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import replace

from mediaflow.domain.duplicates import (
    DuplicateComparisonResult,
    DuplicateStatus,
    FileHashEvidence,
    HashMode,
    HashPolicy,
    HashResult,
    HashStatus,
)
from mediaflow.domain.organizer import Conflict, ConflictType, OrganizePlan, PlanStatus
from mediaflow.domain.storage import Storage, StorageEntry, StorageEntryType, StorageError

CancellationCheck = Callable[[], bool]


class StorageHasher:
    """Calculates versioned Hash evidence through the read-only Storage port."""

    def calculate(
        self,
        storage: Storage,
        path: str,
        policy: HashPolicy,
        *,
        cancellation_check: CancellationCheck | None = None,
        entry: StorageEntry | None = None,
    ) -> HashResult:
        if policy.mode is HashMode.NONE:
            return HashResult(HashStatus.SKIPPED, reason="Hash policy is NONE")
        try:
            observed = entry or storage.stat(path)
        except StorageError as error:
            return HashResult(HashStatus.INDETERMINATE, reason=f"stat failed: {error.code.value}")
        if observed.entry_type is not StorageEntryType.FILE or observed.size < 0:
            return HashResult(HashStatus.INDETERMINATE, reason="Hash source is not a regular file")
        if policy.mode is HashMode.FULL and observed.size > policy.full_max_file_size:
            return HashResult(HashStatus.INDETERMINATE, reason="file exceeds full Hash size limit")
        if cancellation_check and cancellation_check():
            return HashResult(HashStatus.CANCELLED, reason="Hash calculation cancelled")
        wanted = (
            min(observed.size, policy.fast_sample_bytes)
            if policy.mode is HashMode.FAST
            else observed.size
        )
        algorithm = "sha256-size-prefix-v1" if policy.mode is HashMode.FAST else "sha256-full-v1"
        digest = hashlib.sha256()
        digest.update(algorithm.encode("ascii"))
        digest.update(b"\0")
        digest.update(str(observed.size).encode("ascii"))
        digest.update(b"\0")
        consumed = 0
        try:
            with storage.read(path) as stream:
                while consumed < wanted:
                    if cancellation_check and cancellation_check():
                        return HashResult(HashStatus.CANCELLED, reason="Hash calculation cancelled")
                    chunk = stream.read(min(policy.chunk_size, wanted - consumed))
                    if not chunk:
                        return HashResult(
                            HashStatus.INDETERMINATE,
                            reason="file ended before its reported size/sample",
                        )
                    if len(chunk) > wanted - consumed:
                        return HashResult(
                            HashStatus.INDETERMINATE,
                            reason="Storage read exceeded the requested Hash bound",
                        )
                    digest.update(chunk)
                    consumed += len(chunk)
                if policy.mode is HashMode.FULL and stream.read(1):
                    return HashResult(
                        HashStatus.INDETERMINATE,
                        reason="file contains data beyond its reported size",
                    )
        except (StorageError, OSError) as error:
            code = error.code.value if isinstance(error, StorageError) else "io_error"
            return HashResult(HashStatus.INDETERMINATE, reason=f"read failed: {code}")
        try:
            after = storage.stat(path)
        except StorageError as error:
            return HashResult(
                HashStatus.INDETERMINATE,
                reason=f"post-Hash stat failed: {error.code.value}",
            )
        if (
            after.entry_type is not StorageEntryType.FILE
            or after.size != observed.size
            or after.modified_at != observed.modified_at
        ):
            return HashResult(
                HashStatus.INDETERMINATE, reason="file changed during Hash calculation"
            )
        return HashResult(
            HashStatus.COMPLETE,
            FileHashEvidence(
                policy.mode,
                algorithm,
                digest.hexdigest(),
                observed.size,
                consumed,
                policy.mode is HashMode.FULL,
            ),
        )


class HashDuplicateDetector:
    def __init__(self, hasher: StorageHasher | None = None) -> None:
        self._hasher = hasher or StorageHasher()

    def compare(
        self,
        source_storage: Storage,
        source_path: str,
        destination_storage: Storage,
        destination_path: str,
        policy: HashPolicy,
        *,
        cancellation_check: CancellationCheck | None = None,
    ) -> DuplicateComparisonResult:
        if policy.mode is HashMode.NONE:
            return DuplicateComparisonResult(
                DuplicateStatus.NOT_CHECKED, policy.mode, reason="Hash policy is NONE"
            )
        try:
            destination = destination_storage.stat(destination_path)
        except StorageError as error:
            if error.code.value == "not_found":
                return DuplicateComparisonResult(
                    DuplicateStatus.UNIQUE, policy.mode, reason="destination does not exist"
                )
            return DuplicateComparisonResult(
                DuplicateStatus.INDETERMINATE,
                policy.mode,
                reason=f"destination stat failed: {error.code.value}",
            )
        try:
            source = source_storage.stat(source_path)
        except StorageError as error:
            return DuplicateComparisonResult(
                DuplicateStatus.INDETERMINATE,
                policy.mode,
                reason=f"source stat failed: {error.code.value}",
            )
        if (
            source.entry_type is not StorageEntryType.FILE
            or destination.entry_type is not StorageEntryType.FILE
        ):
            return DuplicateComparisonResult(
                DuplicateStatus.INDETERMINATE,
                policy.mode,
                reason="duplicate comparison requires two regular files",
            )
        if source.size != destination.size:
            return DuplicateComparisonResult(
                DuplicateStatus.UNIQUE, policy.mode, reason="file sizes differ"
            )
        source_hash = self._hasher.calculate(
            source_storage,
            source_path,
            policy,
            cancellation_check=cancellation_check,
            entry=source,
        )
        if source_hash.status is not HashStatus.COMPLETE:
            return DuplicateComparisonResult(
                DuplicateStatus.INDETERMINATE,
                policy.mode,
                source_hash=source_hash,
                reason=source_hash.reason,
            )
        destination_hash = self._hasher.calculate(
            destination_storage,
            destination_path,
            policy,
            cancellation_check=cancellation_check,
            entry=destination,
        )
        if destination_hash.status is not HashStatus.COMPLETE:
            return DuplicateComparisonResult(
                DuplicateStatus.INDETERMINATE,
                policy.mode,
                source_hash,
                destination_hash,
                destination_hash.reason,
            )
        duplicate = source_hash.evidence.digest == destination_hash.evidence.digest
        return DuplicateComparisonResult(
            DuplicateStatus.DUPLICATE if duplicate else DuplicateStatus.UNIQUE,
            policy.mode,
            source_hash,
            destination_hash,
            "matching size and Hash" if duplicate else "Hash values differ",
        )


def apply_hash_duplicate_detection(
    plan: OrganizePlan,
    source_storage: Storage,
    destination_storage: Storage,
    policy: HashPolicy,
    *,
    detector: HashDuplicateDetector | None = None,
    cancellation_check: CancellationCheck | None = None,
) -> OrganizePlan:
    """Attach read-only Hash evidence and fail-closed conflicts to a portable plan."""
    if policy.mode is HashMode.NONE or plan.status is PlanStatus.INVALID:
        return plan
    if plan.source_location is None or plan.destination_location is None:
        comparison = DuplicateComparisonResult(
            DuplicateStatus.INDETERMINATE,
            policy.mode,
            reason="portable source/destination locations are unavailable",
        )
    else:
        comparison = (detector or HashDuplicateDetector()).compare(
            source_storage,
            plan.source_location.path,
            destination_storage,
            plan.destination_location.path,
            policy,
            cancellation_check=cancellation_check,
        )
    conflicts = list(plan.conflicts)
    if comparison.status is DuplicateStatus.DUPLICATE and not any(
        item.type is ConflictType.DUPLICATE_MEDIA for item in conflicts
    ):
        conflicts.append(
            Conflict(
                ConflictType.DUPLICATE_MEDIA,
                plan.source,
                plan.target,
                f"matching {policy.mode.value} Hash evidence",
            )
        )
    elif comparison.status is DuplicateStatus.INDETERMINATE:
        conflicts.append(
            Conflict(
                ConflictType.UNKNOWN,
                plan.source,
                plan.target,
                f"Hash duplicate detection is indeterminate: {comparison.reason}",
            )
        )
    return replace(
        plan,
        duplicate_comparison=comparison,
        conflicts=tuple(conflicts),
        status=PlanStatus.CONFLICT if conflicts else plan.status,
    )
