from __future__ import annotations

import io
import unittest
from datetime import UTC, datetime

from mediaflow.application.duplicates import (
    HashDuplicateDetector,
    StorageHasher,
    apply_hash_duplicate_detection,
)
from mediaflow.domain.duplicates import DuplicateStatus, HashMode, HashPolicy, HashStatus
from mediaflow.domain.organizer import (
    ConflictType,
    OrganizePlan,
    PlanOperation,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.storage import (
    StorageCapabilities,
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
)


class HashStorage:
    storage_id = "memory"
    name = "memory"
    read_only = True
    capabilities = StorageCapabilities()

    def __init__(self, files: dict[str, bytes], sizes: dict[str, int] | None = None) -> None:
        self.files = files
        self.sizes = sizes or {}
        self.stat_calls = 0
        self.read_calls = 0
        self.read_sizes: list[int] = []
        self.mutations = 0
        self.modified_at = datetime(2026, 1, 1, tzinfo=UTC)

    def stat(self, path):
        self.stat_calls += 1
        if path not in self.files:
            raise StorageError(StorageErrorCode.NOT_FOUND, "stat", path, "missing")
        return StorageEntry(
            path.rsplit("/", 1)[-1],
            path,
            StorageEntryType.FILE,
            self.sizes.get(path, len(self.files[path])),
            self.modified_at,
        )

    def read(self, path):
        self.read_calls += 1
        owner = self

        class Tracked(io.BytesIO):
            def read(self, size=-1):
                owner.read_sizes.append(size)
                return super().read(size)

        return Tracked(self.files[path])

    def list(self, path):
        return ()

    def exists(self, path):
        return path in self.files

    def _mutate(self):
        self.mutations += 1
        raise AssertionError("mutation")

    def write(self, *args, **kwargs):
        self._mutate()

    def create_directory(self, *args, **kwargs):
        self._mutate()

    def move(self, *args, **kwargs):
        self._mutate()

    def copy(self, *args, **kwargs):
        self._mutate()

    def delete(self, *args, **kwargs):
        self._mutate()

    def hard_link(self, *args, **kwargs):
        self._mutate()

    def soft_link(self, *args, **kwargs):
        self._mutate()


class DuplicateHashTests(unittest.TestCase):
    @staticmethod
    def plan() -> OrganizePlan:
        return OrganizePlan(
            "source",
            "target",
            "/display/source.mkv",
            "Movies/source.mkv",
            "C",
            "A",
            "A",
            "A",
            operation=PlanOperation.COPY,
            source_location=StorageLocation("source", "source.mkv"),
            destination_location=StorageLocation("target", "Movies/source.mkv"),
        )

    def test_none_performs_zero_stat_read_or_mutation(self) -> None:
        storage = HashStorage({"a": b"data", "b": b"data"})
        result = HashDuplicateDetector().compare(storage, "a", storage, "b", HashPolicy())
        self.assertEqual(result.status, DuplicateStatus.NOT_CHECKED)
        self.assertEqual((storage.stat_calls, storage.read_calls, storage.mutations), (0, 0, 0))

    def test_fast_is_bounded_versioned_and_deterministic(self) -> None:
        storage = HashStorage({"a": b"abcdefghij"})
        policy = HashPolicy(HashMode.FAST, fast_sample_bytes=4, chunk_size=3)
        first = StorageHasher().calculate(storage, "a", policy)
        second = StorageHasher().calculate(storage, "a", policy)
        self.assertEqual(first, second)
        self.assertEqual(first.status, HashStatus.COMPLETE)
        self.assertEqual(first.evidence.algorithm, "sha256-size-prefix-v1")
        self.assertEqual(first.evidence.bytes_hashed, 4)
        self.assertFalse(first.evidence.complete_content)
        self.assertEqual(storage.read_sizes, [3, 1, 3, 1])

    def test_full_streams_empty_small_and_chunked_files(self) -> None:
        policy = HashPolicy(HashMode.FULL, chunk_size=3)
        storage = HashStorage({"empty": b"", "small": b"ab", "large": b"abcdefgh"})
        results = tuple(StorageHasher().calculate(storage, path, policy) for path in storage.files)
        self.assertTrue(all(item.status is HashStatus.COMPLETE for item in results))
        self.assertEqual([item.evidence.bytes_hashed for item in results], [0, 2, 8])
        self.assertTrue(all(item.evidence.complete_content for item in results))
        self.assertIn(1, storage.read_sizes)  # explicit excess-data check

    def test_compare_same_different_and_size_mismatch(self) -> None:
        policy = HashPolicy(HashMode.FULL, chunk_size=2)
        detector = HashDuplicateDetector()
        same = HashStorage({"a": b"same", "b": b"same"})
        self.assertEqual(
            detector.compare(same, "a", same, "b", policy).status, DuplicateStatus.DUPLICATE
        )
        different = HashStorage({"a": b"abcd", "b": b"abce"})
        self.assertEqual(
            detector.compare(different, "a", different, "b", policy).status, DuplicateStatus.UNIQUE
        )
        sized = HashStorage({"a": b"a", "b": b"bb"})
        self.assertEqual(
            detector.compare(sized, "a", sized, "b", policy).status, DuplicateStatus.UNIQUE
        )
        self.assertEqual(sized.read_calls, 0)

    def test_fast_same_prefix_is_explicitly_only_fast_evidence(self) -> None:
        storage = HashStorage({"a": b"same-A", "b": b"same-B"})
        result = HashDuplicateDetector().compare(
            storage, "a", storage, "b", HashPolicy(HashMode.FAST, fast_sample_bytes=4)
        )
        self.assertEqual(result.status, DuplicateStatus.DUPLICATE)
        self.assertFalse(result.source_hash.evidence.complete_content)

    def test_cross_storage_comparison(self) -> None:
        source = HashStorage({"a": b"content"})
        target = HashStorage({"b": b"content"})
        result = HashDuplicateDetector().compare(
            source, "a", target, "b", HashPolicy(HashMode.FULL, chunk_size=2)
        )
        self.assertEqual(result.status, DuplicateStatus.DUPLICATE)
        self.assertEqual((source.mutations, target.mutations), (0, 0))

    def test_missing_destination_is_unique_without_source_read(self) -> None:
        source = HashStorage({"a": b"content"})
        target = HashStorage({})
        result = HashDuplicateDetector().compare(
            source, "a", target, "missing", HashPolicy(HashMode.FULL)
        )
        self.assertEqual(result.status, DuplicateStatus.UNIQUE)
        self.assertEqual((source.stat_calls, source.read_calls), (0, 0))

    def test_premature_eof_excess_size_limit_and_cancellation_are_indeterminate(self) -> None:
        hasher = StorageHasher()
        short = HashStorage({"a": b"abc"}, {"a": 5})
        self.assertEqual(
            hasher.calculate(short, "a", HashPolicy(HashMode.FULL)).status, HashStatus.INDETERMINATE
        )
        excess = HashStorage({"a": b"abcde"}, {"a": 3})
        self.assertEqual(
            hasher.calculate(excess, "a", HashPolicy(HashMode.FULL)).status,
            HashStatus.INDETERMINATE,
        )
        large = HashStorage({"a": b"abcd"})
        self.assertIn(
            "size limit",
            hasher.calculate(large, "a", HashPolicy(HashMode.FULL, full_max_file_size=3)).reason,
        )
        cancelled = hasher.calculate(
            large, "a", HashPolicy(HashMode.FULL), cancellation_check=lambda: True
        )
        self.assertEqual(cancelled.status, HashStatus.CANCELLED)

    def test_storage_failure_is_indeterminate(self) -> None:
        class ReadFailure(HashStorage):
            def read(self, path):
                raise StorageError(StorageErrorCode.CONNECTION_LOST, "read", path, "lost")

        result = StorageHasher().calculate(
            ReadFailure({"a": b"abc"}), "a", HashPolicy(HashMode.FULL)
        )
        self.assertEqual(result.status, HashStatus.INDETERMINATE)
        self.assertIn("connection_lost", result.reason)

    def test_same_size_modification_during_hash_is_indeterminate(self) -> None:
        class Changing(HashStorage):
            def stat(self, path):
                entry = super().stat(path)
                if self.stat_calls > 1:
                    return StorageEntry(
                        entry.name,
                        entry.path,
                        entry.entry_type,
                        entry.size,
                        datetime(2026, 1, 2, tzinfo=UTC),
                    )
                return entry

        result = StorageHasher().calculate(Changing({"a": b"abc"}), "a", HashPolicy(HashMode.FULL))
        self.assertEqual(result.status, HashStatus.INDETERMINATE)
        self.assertIn("changed", result.reason)

    def test_plan_integration_adds_fail_closed_unknown_and_keeps_operation(self) -> None:
        source = HashStorage({"source.mkv": b"abc"}, {"source.mkv": 5})
        target = HashStorage({"Movies/source.mkv": b"abcde"})
        plan = apply_hash_duplicate_detection(
            self.plan(), source, target, HashPolicy(HashMode.FULL, chunk_size=2)
        )
        self.assertEqual(plan.status, PlanStatus.CONFLICT)
        self.assertEqual(plan.operation, PlanOperation.COPY)
        self.assertEqual(plan.recognition_type_id, "C")
        self.assertEqual(plan.duplicate_comparison.status, DuplicateStatus.INDETERMINATE)
        self.assertIn(ConflictType.UNKNOWN, {item.type for item in plan.conflicts})
        self.assertEqual((source.mutations, target.mutations), (0, 0))

    def test_plan_integration_none_returns_same_plan_with_zero_io(self) -> None:
        source, target, plan = HashStorage({}), HashStorage({}), self.plan()
        result = apply_hash_duplicate_detection(plan, source, target, HashPolicy())
        self.assertIs(result, plan)
        self.assertEqual((source.stat_calls, target.stat_calls), (0, 0))

    def test_policy_limits_reject_bools_and_out_of_range_values(self) -> None:
        for kwargs in (
            {"mode": "fast"},
            {"fast_sample_bytes": True},
            {"fast_sample_bytes": 0},
            {"chunk_size": 0},
            {"full_max_file_size": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                HashPolicy(**kwargs)


if __name__ == "__main__":
    unittest.main()
