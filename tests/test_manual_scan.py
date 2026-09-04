from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.manual_scan import ManualScanError, ManualScanService
from mediaflow.application.scanner import StorageScanner
from mediaflow.domain.file_lifecycle import OccurrenceState
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.scanner import FileScanStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import PersistentTaskStatus
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_scanner import FakeStorage

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


def request(api, path: str, *, token: str, method: str = "GET", body=None):
    raw = json.dumps(body).encode("utf-8") if body is not None else b""
    statuses: list[str] = []
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


class ManualScanTests(unittest.TestCase):
    def library(self, library_id: str = "library") -> ResourceLibrary:
        return ResourceLibrary(
            library_id,
            library_id.title(),
            "source",
            "",
            exclude_rules=(),
        )

    def setUp(self) -> None:
        self.storage = FakeStorage("source")
        self.storage.add_file("current.mkv", 10, NOW - timedelta(hours=2))
        self.storage.add_file("sibling.mkv", 11, NOW - timedelta(hours=2))
        self.index = InMemoryFileIndexRepository()
        self.library_value = self.library()
        self.scanner = StorageScanner({"source": self.storage}, self.index, clock=lambda: NOW)
        self.scanner.scan(self.library_value)

    def service(self, repository, *, start_async: bool = False) -> ManualScanService:
        return ManualScanService(
            repository,
            self.index,
            resource_libraries=(self.library_value,),
            storages={"source": self.storage},
            configuration_snapshot_id="active-revision",
            configuration_snapshot_digest="active-digest",
            clock=lambda: NOW,
            start_async=start_async,
        )

    def file_request(self, path: str = "current.mkv") -> dict[str, str]:
        record = self.index.find_by_path("source", "library", path)
        return {
            "scopeKind": "file",
            "resourceLibraryId": "library",
            "fileId": record.file_id,
            "occurrenceId": record.occurrence_id,
            "fingerprint": record.fingerprint,
            "mode": "incremental",
        }

    def test_file_scope_is_durable_and_does_not_reconcile_siblings(self) -> None:
        del self.storage.files["sibling.mkv"]
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                service = self.service(repository)
                admitted = service.admit_document(self.file_request())
                completed = service.run(admitted.task_id)
                self.assertEqual(PersistentTaskStatus.COMPLETED, completed.status)
                self.assertFalse(completed.reconciliation_complete)
                self.assertEqual(0, self.storage.mutations["move"])
                self.assertEqual(
                    FileScanStatus.READY,
                    self.index.find_by_path("source", "library", "sibling.mkv").scan_status,
                )
                self.assertEqual(1, len(repository.list_manual_scan_items(admitted.task_id)))
            with SQLiteTaskRepository(database) as reopened:
                reloaded = self.service(reopened).detail(admitted.task_id)
                self.assertEqual(PersistentTaskStatus.COMPLETED, reloaded.status)
                self.assertEqual(admitted.task_id, reloaded.task_id)
                self.assertEqual("library", reloaded.resource_library_id)

    def test_stale_current_occurrence_is_rejected_without_a_task(self) -> None:
        payload = self.file_request()
        payload["fingerprint"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self.service(repository)
                with self.assertRaises(ManualScanError) as context:
                    service.admit_document(payload)
                self.assertEqual("source_stale", context.exception.code)
                self.assertEqual("no_task_created", context.exception.durable_state)
                self.assertEqual(0, len(repository.list_tasks()))

    def test_source_replacement_after_admission_records_a_failure_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self.service(repository)
                admitted = service.admit_document(self.file_request())
                self.storage.files["current.mkv"] = (99, NOW - timedelta(hours=2))
                failed = service.run(admitted.task_id)
                self.assertEqual(PersistentTaskStatus.FAILED, failed.status)
                self.assertFalse(failed.reconciliation_complete)
                items = repository.list_manual_scan_items(admitted.task_id)
                self.assertEqual(1, len(items))
                self.assertEqual(FileScanStatus.ERROR, items[0].status)
                self.assertFalse(
                    self.index.find_by_path("source", "library", "sibling.mkv").scan_status
                    is FileScanStatus.MISSING
                )

    def test_concurrent_same_library_scans_keep_one_scope_independent(self) -> None:
        self.storage.entered_list.clear()
        self.storage.block_list = threading.Event()
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self.service(repository)
                first = service.admit_document(
                    {
                        "scopeKind": "resource_library",
                        "resourceLibraryId": "library",
                        "mode": "full",
                    }
                )
                second = service.admit_document(
                    {
                        "scopeKind": "resource_library",
                        "resourceLibraryId": "library",
                        "mode": "incremental",
                    }
                )
                outcomes = {}
                first_thread = threading.Thread(
                    target=lambda: outcomes.setdefault("first", service.run(first.task_id))
                )
                second_thread = threading.Thread(
                    target=lambda: outcomes.setdefault("second", service.run(second.task_id))
                )
                first_thread.start()
                self.assertTrue(self.storage.entered_list.wait(2))
                second_thread.start()
                second_thread.join(2)
                self.assertFalse(second_thread.is_alive())
                self.storage.block_list.set()
                first_thread.join(2)
                self.assertFalse(first_thread.is_alive())
                self.assertEqual(PersistentTaskStatus.COMPLETED, outcomes["first"].status)
                self.assertEqual(PersistentTaskStatus.FAILED, outcomes["second"].status)
                self.assertFalse(outcomes["second"].reconciliation_complete)

    def test_full_resource_scan_is_the_only_manual_reconciliation_boundary(self) -> None:
        del self.storage.files["sibling.mkv"]
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self.service(repository)
                admitted = service.admit_document(
                    {
                        "scopeKind": "resource_library",
                        "resourceLibraryId": "library",
                        "mode": "full",
                    }
                )
                completed = service.run(admitted.task_id)
                self.assertEqual(PersistentTaskStatus.COMPLETED, completed.status)
                self.assertTrue(completed.reconciliation_complete)
                self.assertEqual(
                    FileScanStatus.MISSING,
                    self.index.find_by_path("source", "library", "sibling.mkv").scan_status,
                )

    def test_cancelled_task_is_persisted_and_never_claims_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                service = self.service(repository)
                admitted = service.admit_document(
                    {
                        "scopeKind": "resource_library",
                        "resourceLibraryId": "library",
                        "mode": "full",
                    }
                )
                cancelled = service.cancel(admitted.task_id)
                self.assertEqual(PersistentTaskStatus.CANCELLED, cancelled.status)
                self.assertTrue(cancelled.cancellation_requested)
                self.assertFalse(cancelled.reconciliation_complete)
                self.assertTrue(cancelled.retry_safe)
            with SQLiteTaskRepository(database) as reopened:
                reloaded = self.service(reopened).detail(admitted.task_id)
                self.assertEqual(PersistentTaskStatus.CANCELLED, reloaded.status)

    def test_reloaded_task_cannot_run_against_a_different_active_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                admitted = self.service(repository).admit_document(
                    {
                        "scopeKind": "resource_library",
                        "resourceLibraryId": "library",
                        "mode": "full",
                    }
                )
                replacement = ManualScanService(
                    repository,
                    self.index,
                    resource_libraries=(self.library_value,),
                    storages={"source": self.storage},
                    configuration_snapshot_id="replacement-active",
                    configuration_snapshot_digest="replacement-digest",
                    clock=lambda: NOW,
                    start_async=False,
                )
                failed = replacement.run(admitted.task_id)
                self.assertEqual(PersistentTaskStatus.FAILED, failed.status)
                self.assertEqual("configuration", failed.failure_stage)
                self.assertFalse(failed.reconciliation_complete)
                self.assertEqual(0, self.storage.mutations["move"])

    def test_api_rbac_and_web_use_the_same_bounded_scan_contract(self) -> None:
        operator = ResolvedApiPrincipal(
            "operator",
            "operator-token",
            frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN, ApiPermission.CANCEL_JOB}),
        )
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self.service(repository)
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(operator, viewer),
                    manual_scan_service=service,
                )
                payload = self.file_request()
                status, denied = request(
                    api, "/api/v1/scans", token="viewer-token", method="POST", body=payload
                )
                self.assertEqual(403, status)
                self.assertEqual("forbidden", denied["error"]["code"])
                status, admitted = request(
                    api, "/api/v1/scans", token="operator-token", method="POST", body=payload
                )
                self.assertEqual(202, status)
                task_id = admitted["taskId"]
                service.run(task_id)
                status, detail = request(api, f"/api/v1/scans/{task_id}", token="viewer-token")
                self.assertEqual(200, status)
                self.assertEqual("completed", detail["status"])
                self.assertEqual("incremental", detail["mode"])
                self.assertEqual("none", detail["sideEffects"])
                status, _ = request(
                    api,
                    f"/api/v1/scans/{task_id}/cancel",
                    token="viewer-token",
                    method="POST",
                )
                self.assertEqual(403, status)
        script = APP_JS.decode("utf-8")
        self.assertIn("/api/v1/scans", script)
        self.assertIn("Scan current FileIndex item", script)
        self.assertIn("Scan ResourceLibrary", script)
        self.assertIn("Request Scan cancellation", script)

    def test_scan_keeps_occurrence_state_and_never_reads_or_mutates_storage(self) -> None:
        record = self.index.find_by_path("source", "library", "current.mkv")
        self.assertEqual(OccurrenceState.VERIFIED, record.occurrence_state)
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self.service(repository)
                admitted = service.admit_document(self.file_request())
                done = service.run(admitted.task_id)
                self.assertEqual(PersistentTaskStatus.COMPLETED, done.status)
                self.assertEqual(0, sum(self.storage.mutations.values()))


if __name__ == "__main__":
    unittest.main()
