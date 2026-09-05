from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.file_index_lifecycle import FileIndexLifecycleService
from mediaflow.application.scanner import StorageScanner
from mediaflow.domain.file_lifecycle import (
    FileIndexLifecycleError,
    OccurrenceState,
    ProcessingDisposition,
)
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.scanner import FileScanStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.domain.tasks import TaskStatus
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import ASSETS
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_scanner import FakeStorage

NOW = datetime(2026, 8, 25, 12, tzinfo=UTC)


def request(api, path: str, *, token: str, method: str = "GET", body=None):
    statuses: list[str] = []
    raw = json.dumps(body).encode("utf-8") if body is not None else b""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(raw)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(raw),
    }
    payload = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload)


class FileIndexLifecycleTests(unittest.TestCase):
    def library(self) -> ResourceLibrary:
        return ResourceLibrary("library", "Library", "source", "")

    def test_same_path_unchanged_retains_occurrence_and_replacement_gets_new_one(self) -> None:
        storage = FakeStorage("source")
        storage.add_file("movie.mkv", 10, NOW - timedelta(hours=2))
        index = InMemoryFileIndexRepository()
        scanner = StorageScanner({"source": storage}, index, clock=lambda: NOW)

        first = scanner.scan(self.library())
        self.assertEqual(TaskStatus.COMPLETED, first.status)
        original = index.find_by_path("source", "library", "movie.mkv")
        self.assertEqual(OccurrenceState.VERIFIED, original.occurrence_state)
        scanner.scan(self.library())
        unchanged = index.find_by_path("source", "library", "movie.mkv")
        self.assertEqual(original.occurrence_id, unchanged.occurrence_id)
        self.assertEqual("unchanged", unchanged.change.value)

        storage.files["movie.mkv"] = (11, NOW - timedelta(hours=2))
        scanner.scan(self.library())
        replacement = index.find_by_path("source", "library", "movie.mkv")
        self.assertNotEqual(original.occurrence_id, replacement.occurrence_id)
        self.assertEqual(ProcessingDisposition.UNKNOWN, replacement.processing_disposition)
        history = index.occurrence_history(replacement.file_id)
        self.assertEqual(
            {original.occurrence_id, replacement.occurrence_id},
            {item.occurrence_id for item in history},
        )
        self.assertFalse(
            next(
                item for item in history if item.occurrence_id == original.occurrence_id
            ).is_current
        )

    def test_partial_scan_does_not_fabricate_missing(self) -> None:
        storage = FakeStorage("source")
        storage.add_file("good/movie.mkv", 10, NOW - timedelta(hours=2))
        storage.add_file("broken/other.mkv", 10, NOW - timedelta(hours=2))
        index = InMemoryFileIndexRepository()
        scanner = StorageScanner({"source": storage}, index, clock=lambda: NOW)
        scanner.scan(self.library())
        del storage.files["good/movie.mkv"]
        from mediaflow.domain.storage import StorageErrorCode

        storage.list_errors["broken"] = StorageErrorCode.IO_ERROR
        result = scanner.scan(self.library())
        self.assertEqual(TaskStatus.PARTIAL_SUCCESS, result.status)
        self.assertEqual(
            FileScanStatus.READY,
            index.find_by_path("source", "library", "good/movie.mkv").scan_status,
        )

    def test_unreadable_source_evidence_is_explicitly_unverified(self) -> None:
        storage = FakeStorage("source")
        storage.add_file("uncertain.mkv", -1, NOW - timedelta(hours=2))
        index = InMemoryFileIndexRepository()
        scanner = StorageScanner({"source": storage}, index, clock=lambda: NOW)

        result = scanner.scan(self.library())

        self.assertEqual(TaskStatus.COMPLETED, result.status)
        record = index.find_by_path("source", "library", "uncertain.mkv")
        self.assertEqual(FileScanStatus.READY, record.scan_status)
        self.assertEqual(OccurrenceState.UNVERIFIED, record.occurrence_state)
        self.assertIsNone(record.fingerprint)
        self.assertEqual(ProcessingDisposition.UNVERIFIED, record.processing_disposition)
        self.assertEqual(
            "refresh the current source occurrence before processing",
            record.processing_next_action,
        )

    def test_stale_reconciliation_preserves_current_and_records_attention(self) -> None:
        storage = FakeStorage("source")
        storage.add_file("movie.mkv", 10, NOW - timedelta(hours=2))
        index = InMemoryFileIndexRepository()
        StorageScanner({"source": storage}, index, clock=lambda: NOW).scan(self.library())
        current = index.find_by_path("source", "library", "movie.mkv")

        index.batch_upsert(
            (
                replace(
                    current,
                    occurrence_id="occ-stale-observation",
                    fingerprint="a" * 64,
                    updated_at=NOW - timedelta(minutes=1),
                    last_seen_at=NOW - timedelta(minutes=1),
                ),
            )
        )

        conflicted = index.find_by_path("source", "library", "movie.mkv")
        self.assertEqual(current.occurrence_id, conflicted.occurrence_id)
        self.assertEqual(ProcessingDisposition.ATTENTION, conflicted.processing_disposition)
        self.assertEqual(FileScanStatus.READY, conflicted.scan_status)
        self.assertEqual(1, len(index.occurrence_history(current.file_id)))

    def test_unverified_result_cannot_become_current_processing_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            storage = FakeStorage("source")
            storage.add_file("movie.mkv", 10, NOW - timedelta(hours=2))
            library = self.library()
            with SQLiteFileIndexRepository(database) as index:
                StorageScanner({"source": storage}, index, clock=lambda: NOW).scan(library)
                record = index.find_by_path("source", "library", "movie.mkv")
                with SQLiteTaskRepository(database) as tasks:
                    tasks.append_result(
                        PersistentResultRecord(
                            "unverified-result",
                            "task-unverified",
                            "item-unverified",
                            "source",
                            "movie.mkv",
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            "copy",
                            "success",
                            NOW,
                            effect_certainty="none",
                            source_occurrence_id=record.occurrence_id,
                            source_fingerprint=record.fingerprint,
                            source_fingerprint_state="unverified",
                        )
                    )
                    catalog = FileCatalogService(
                        index, ("library",), ("source",), task_repository=tasks
                    )
                    projection = FileIndexLifecycleService(catalog, index, tasks).detail(
                        record.file_id
                    )
                self.assertEqual(
                    ProcessingDisposition.UNVERIFIED,
                    index.find_by_file_id(record.file_id).processing_disposition,
                )
                self.assertIsNone(projection.current_result)
                self.assertEqual("unverified_legacy", projection.result_relevance[0][1])

    def test_result_is_bound_to_occurrence_and_old_result_is_not_current_after_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            storage = FakeStorage("source")
            storage.add_file("movie.mkv", 10, NOW - timedelta(hours=2))
            library = self.library()
            with SQLiteFileIndexRepository(database) as index:
                scanner = StorageScanner({"source": storage}, index, clock=lambda: NOW)
                scanner.scan(library)
                original = index.find_by_path("source", "library", "movie.mkv")
                with SQLiteTaskRepository(database) as tasks:
                    tasks.append_result(
                        PersistentResultRecord(
                            "old-result",
                            "task-old",
                            "item-old",
                            "source",
                            "movie.mkv",
                            "media",
                            "Media/movie.mkv",
                            "C",
                            "tmdb",
                            "1",
                            "C",
                            "A",
                            "A",
                            "A",
                            "move",
                            "success",
                            NOW,
                            effect_certainty="verified_complete",
                            source_occurrence_id=original.occurrence_id,
                            source_fingerprint=original.fingerprint,
                            source_fingerprint_state="verified",
                        )
                    )
                self.assertEqual(
                    ProcessingDisposition.ORGANIZED,
                    index.find_by_path("source", "library", "movie.mkv").processing_disposition,
                )
                storage.files["movie.mkv"] = (11, NOW - timedelta(hours=2))
                scanner.scan(library)
                replacement = index.find_by_path("source", "library", "movie.mkv")
                self.assertEqual(ProcessingDisposition.UNKNOWN, replacement.processing_disposition)
                with SQLiteTaskRepository(database) as tasks:
                    catalog = FileCatalogService(
                        index, ("library",), ("source",), task_repository=tasks
                    )
                    projection = FileIndexLifecycleService(catalog, index, tasks).detail(
                        replacement.file_id
                    )
                self.assertIsNone(projection.current_result)
                self.assertEqual(
                    "historical_different_occurrence", projection.result_relevance[0][1]
                )

    def test_copy_skip_move_and_missing_keep_disposition_orthogonal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            storage = FakeStorage("source")
            storage.add_file("movie.mkv", 10, NOW - timedelta(hours=2))
            with SQLiteFileIndexRepository(database) as index:
                scanner = StorageScanner({"source": storage}, index, clock=lambda: NOW)
                scanner.scan(self.library())
                record = index.find_by_path("source", "library", "movie.mkv")
                with SQLiteTaskRepository(database) as tasks:
                    for result_id, operation, status in (
                        ("copy-result", "copy", "success"),
                        ("skip-result", "skip", "skipped"),
                    ):
                        tasks.append_result(
                            PersistentResultRecord(
                                result_id,
                                "task-" + result_id,
                                "item-" + result_id,
                                "source",
                                "movie.mkv",
                                "media",
                                "Media/movie.mkv",
                                None,
                                None,
                                None,
                                None,
                                None,
                                None,
                                None,
                                operation,
                                status,
                                NOW,
                                effect_certainty="none",
                                source_occurrence_id=record.occurrence_id,
                                source_fingerprint=record.fingerprint,
                                source_fingerprint_state="verified",
                            )
                        )
                        record = index.find_by_path("source", "library", "movie.mkv")
                    self.assertEqual(ProcessingDisposition.SKIPPED, record.processing_disposition)
                    self.assertEqual(FileScanStatus.READY, record.scan_status)
                    tasks.append_result(
                        PersistentResultRecord(
                            "move-result",
                            "task-move",
                            "item-move",
                            "source",
                            "movie.mkv",
                            "media",
                            "Media/movie.mkv",
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            "move",
                            "success",
                            NOW,
                            effect_certainty="verified_complete",
                            source_occurrence_id=record.occurrence_id,
                            source_fingerprint=record.fingerprint,
                            source_fingerprint_state="verified",
                        )
                    )
                self.assertEqual(
                    ProcessingDisposition.ORGANIZED,
                    index.find_by_path("source", "library", "movie.mkv").processing_disposition,
                )
                del storage.files["movie.mkv"]
                scanner.scan(self.library())
                missing = index.find_by_path("source", "library", "movie.mkv")
                self.assertEqual(FileScanStatus.MISSING, missing.scan_status)
                self.assertEqual(ProcessingDisposition.ORGANIZED, missing.processing_disposition)

    def test_reprocess_is_exact_audited_admission_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            storage = FakeStorage("source")
            storage.add_file("movie.mkv", 10, NOW - timedelta(hours=2))
            with SQLiteFileIndexRepository(database) as index:
                scanner = StorageScanner({"source": storage}, index, clock=lambda: NOW)
                scanner.scan(self.library())
                record = index.find_by_path("source", "library", "movie.mkv")
                with SQLiteTaskRepository(database) as tasks:
                    tasks.append_result(
                        PersistentResultRecord(
                            "result",
                            "task",
                            "item",
                            "source",
                            "movie.mkv",
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            "copy",
                            "success",
                            NOW,
                            effect_certainty="verified_complete",
                            source_occurrence_id=record.occurrence_id,
                            source_fingerprint=record.fingerprint,
                            source_fingerprint_state="verified",
                        )
                    )
                request_value = index.admit_reprocess(
                    record.file_id,
                    record.occurrence_id,
                    record.fingerprint,
                    actor="operator",
                    requested_at=NOW,
                )
                self.assertEqual("admitted", request_value.status)
                self.assertFalse(
                    any(value for value in storage.mutations.values()),
                    "Reprocess admission must not mutate Storage",
                )
                with self.assertRaises(FileIndexLifecycleError) as duplicate:
                    index.admit_reprocess(
                        record.file_id,
                        record.occurrence_id,
                        record.fingerprint,
                        actor="operator",
                        requested_at=NOW,
                    )
                self.assertEqual("duplicate_reprocess", duplicate.exception.code)
                with SQLiteTaskRepository(database) as tasks:
                    self.assertEqual(0, len(tasks.list_tasks()))
                self.assertEqual(1, len(index.list_reprocess_requests(record.file_id)))

    def test_api_rbac_projection_and_body_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            storage = FakeStorage("source")
            storage.add_file("movie.mkv", 10, NOW - timedelta(hours=2))
            with SQLiteFileIndexRepository(database) as index:
                StorageScanner({"source": storage}, index, clock=lambda: NOW).scan(self.library())
                record = index.find_by_path("source", "library", "movie.mkv")
                with SQLiteTaskRepository(database) as tasks:
                    tasks.append_result(
                        PersistentResultRecord(
                            "result",
                            "task",
                            "item",
                            "source",
                            "movie.mkv",
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            "copy",
                            "success",
                            NOW,
                            effect_certainty="verified_complete",
                            source_occurrence_id=record.occurrence_id,
                            source_fingerprint=record.fingerprint,
                            source_fingerprint_state="verified",
                        )
                    )
                with SQLiteTaskRepository(database) as tasks:
                    catalog = FileCatalogService(
                        index, ("library",), ("source",), task_repository=tasks
                    )
                    api = MediaFlowApi(
                        tasks,
                        None,
                        principals=(
                            ResolvedApiPrincipal(
                                "viewer", "viewer-token", frozenset({ApiPermission.READ})
                            ),
                            ResolvedApiPrincipal(
                                "operator",
                                "operator-token",
                                frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN}),
                            ),
                        ),
                        file_catalog=catalog,
                        file_index=index,
                    )
                    status, detail = request(
                        api, f"/api/v1/file-index/{record.file_id}", token="viewer-token"
                    )
                    self.assertEqual(200, status)
                    self.assertEqual("ready", detail["discovery"]["status"])
                    self.assertEqual("organized", detail["processingDisposition"])
                    self.assertTrue(detail["reprocess"]["eligible"])
                    status, _ = request(
                        api,
                        f"/api/v1/file-index/{record.file_id}/reprocess",
                        token="viewer-token",
                        method="POST",
                        body={
                            "occurrenceId": record.occurrence_id,
                            "fingerprint": record.fingerprint,
                        },
                    )
                    self.assertEqual(403, status)
                    status, admitted = request(
                        api,
                        f"/api/v1/file-index/{record.file_id}/reprocess",
                        token="operator-token",
                        method="POST",
                        body={
                            "occurrenceId": record.occurrence_id,
                            "fingerprint": record.fingerprint,
                        },
                    )
                    self.assertEqual(202, status)
                    self.assertFalse(admitted["taskCreated"])
                    self.assertFalse(admitted["providerRequested"])
                    status, _ = request(
                        api,
                        f"/api/v1/file-index/{record.file_id}/reprocess",
                        token="operator-token",
                        method="POST",
                        body={
                            "occurrenceId": record.occurrence_id,
                            "fingerprint": record.fingerprint,
                            "path": "/tmp",
                        },
                    )
                    self.assertEqual(400, status)
                    script = ASSETS["/ui/app.js"][1].decode("utf-8")
                    self.assertIn("processingDisposition", script)
                    self.assertIn("currentOccurrence", script)
                    self.assertIn("/reprocess", script)
                    self.assertIn("Confirm Reprocess admission", script)

    def test_old_file_index_rows_are_explicitly_legacy_after_migration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "legacy.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute(
                    """CREATE TABLE file_index (
                        file_id TEXT PRIMARY KEY, storage_id TEXT NOT NULL,
                        resource_library_id TEXT NOT NULL, path TEXT NOT NULL,
                        filename TEXT NOT NULL, extension TEXT NOT NULL, size INTEGER NOT NULL,
                        modified_at TEXT NOT NULL, first_seen_at TEXT NOT NULL,
                        last_seen_at TEXT NOT NULL, stable_since TEXT, scan_status TEXT NOT NULL,
                        change_status TEXT NOT NULL, created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL, missing_since TEXT, last_scan_id TEXT,
                        UNIQUE(storage_id, resource_library_id, path)
                    )"""
                )
                values = (
                    "legacy-file",
                    "source",
                    "library",
                    "movie.mkv",
                    "movie.mkv",
                    "mkv",
                    10,
                    NOW.isoformat(),
                    NOW.isoformat(),
                    NOW.isoformat(),
                    None,
                    "ready",
                    "new",
                    NOW.isoformat(),
                    NOW.isoformat(),
                    None,
                    None,
                )
                connection.execute(
                    "INSERT INTO file_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values
                )
                connection.commit()
            with SQLiteFileIndexRepository(database) as index:
                record = index.find_by_file_id("legacy-file")
                self.assertEqual(OccurrenceState.LEGACY, record.occurrence_state)
                self.assertIsNone(record.fingerprint)
                self.assertEqual(1, len(index.occurrence_history("legacy-file")))

    def test_runtime_migration_preserves_tasks_items_results_and_file_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            with SQLiteTaskRepository(database) as repository:
                repository.create_task(
                    PersistentTask(
                        "task-legacy",
                        "scan",
                        PersistentTaskStatus.COMPLETED,
                        False,
                        NOW,
                        NOW,
                    )
                )
                repository.upsert_item(
                    PersistentTaskItem(
                        "item-legacy",
                        "task-legacy",
                        "source",
                        "library",
                        "movie.mkv",
                        "movie.mkv",
                        TaskItemStatus.SUCCESS,
                        "completed",
                        1,
                        NOW,
                        NOW,
                    )
                )
                repository.append_result(
                    PersistentResultRecord(
                        "result-legacy",
                        "task-legacy",
                        "item-legacy",
                        "source",
                        "movie.mkv",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        "scan",
                        "success",
                        NOW,
                    )
                )
            with sqlite3.connect(database) as connection:
                connection.execute(
                    """CREATE TABLE file_index (
                        file_id TEXT PRIMARY KEY, storage_id TEXT NOT NULL,
                        resource_library_id TEXT NOT NULL, path TEXT NOT NULL,
                        filename TEXT NOT NULL, extension TEXT NOT NULL, size INTEGER NOT NULL,
                        modified_at TEXT NOT NULL, first_seen_at TEXT NOT NULL,
                        last_seen_at TEXT NOT NULL, stable_since TEXT, scan_status TEXT NOT NULL,
                        change_status TEXT NOT NULL, created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL, missing_since TEXT, last_scan_id TEXT,
                        UNIQUE(storage_id, resource_library_id, path)
                    )"""
                )
                connection.execute(
                    "INSERT INTO file_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        "legacy-file",
                        "source",
                        "library",
                        "movie.mkv",
                        "movie.mkv",
                        "mkv",
                        10,
                        NOW.isoformat(),
                        NOW.isoformat(),
                        NOW.isoformat(),
                        None,
                        "ready",
                        "new",
                        NOW.isoformat(),
                        NOW.isoformat(),
                        None,
                        None,
                    ),
                )
                connection.execute(
                    "UPDATE schema_version SET version=? WHERE component='runtime'",
                    (31,),
                )
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(SCHEMA_VERSION, repository.schema_version)
                self.assertIsNotNone(repository.get_task("task-legacy"))
                self.assertEqual("movie.mkv", repository.get_item("item-legacy").source_path)
                self.assertEqual(1, len(repository.list_results("task-legacy")))
                with SQLiteFileIndexRepository(database) as index:
                    record = index.find_by_file_id("legacy-file")
                    self.assertEqual(OccurrenceState.LEGACY, record.occurrence_state)
                    self.assertIsNone(record.fingerprint)
                    self.assertEqual(1, len(index.occurrence_history("legacy-file")))
