from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.file_catalog import FileCatalogFilter, FileCatalogService
from mediaflow.application.recognition_review import RecognitionReviewService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.file_index import FileIndexRecord
from mediaflow.domain.recognition import RecognitionResult, RecognitionStatus
from mediaflow.domain.scanner import FileChange, FileScanStatus
from mediaflow.domain.task_persistence import PersistentResultRecord
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


def file_record(
    file_id: str,
    storage_id: str,
    resource_library_id: str,
    path: str,
    *,
    scan_status: FileScanStatus = FileScanStatus.READY,
    change: FileChange = FileChange.UNCHANGED,
    updated_at: datetime | None = None,
) -> FileIndexRecord:
    return FileIndexRecord(
        file_id,
        storage_id,
        resource_library_id,
        path,
        Path(path).name,
        Path(path).suffix.lstrip("."),
        123,
        NOW - timedelta(hours=2),
        NOW - timedelta(days=3),
        NOW - timedelta(hours=1),
        NOW - timedelta(hours=1),
        scan_status,
        change,
        NOW - timedelta(days=3),
        updated_at or NOW,
    )


class FileCatalogTests(unittest.TestCase):
    def _service(self, repository):
        return FileCatalogService(repository, ("movies", "tv"), ("local", "remote"))

    def test_list_orders_and_filters_without_unrelated_records(self) -> None:
        repository = InMemoryFileIndexRepository()
        repository.batch_upsert(
            (
                file_record(
                    "one",
                    "local",
                    "movies",
                    "Movies/A.mkv",
                    updated_at=NOW - timedelta(minutes=3),
                ),
                file_record(
                    "two",
                    "local",
                    "tv",
                    "TV/B.mkv",
                    scan_status=FileScanStatus.UNSTABLE,
                    updated_at=NOW - timedelta(minutes=2),
                ),
                file_record(
                    "three",
                    "remote",
                    "movies",
                    "Movies/C.mkv",
                    updated_at=NOW - timedelta(minutes=1),
                ),
                file_record(
                    "other",
                    "local",
                    "other",
                    "Other/D.mkv",
                    updated_at=NOW,
                ),
            )
        )
        service = self._service(repository)
        values = service.list(FileCatalogFilter(storage_id="local", limit=2))
        self.assertEqual([value.file_id for value in values], ["two", "one"])
        values = service.list(
            FileCatalogFilter(
                resource_library_id="movies",
                scan_status=FileScanStatus.READY,
                query="c.mkv",
                limit=10,
            )
        )
        self.assertEqual([value.file_id for value in values], ["three"])

    def test_unknown_ids_invalid_limit_and_missing_file_fail_closed(self) -> None:
        repository = InMemoryFileIndexRepository()
        service = self._service(repository)
        with self.assertRaisesRegex(ValueError, "ResourceLibrary"):
            service.list(FileCatalogFilter(resource_library_id="missing"))
        with self.assertRaisesRegex(ValueError, "Storage"):
            service.list(FileCatalogFilter(storage_id="missing"))
        for limit in (0, -1, 1001, True):
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(ValueError, "limit"):
                    service.list(FileCatalogFilter(limit=limit))
        with self.assertRaises(LookupError):
            service.show("missing")

    def test_show_returns_in_scope_record_and_rejects_out_of_scope_resource(self) -> None:
        repository = InMemoryFileIndexRepository()
        repository.batch_upsert((file_record("one", "local", "movies", "Movies/A.mkv"),))
        service = self._service(repository)
        self.assertEqual(service.show("one").file_id, "one")
        with self.assertRaisesRegex(ValueError, "ResourceLibrary"):
            service.show("one", resource_library_id="missing")

    def test_cursor_pagination_uses_stable_order_and_cursor_components(self) -> None:
        repository = InMemoryFileIndexRepository()
        repository.batch_upsert(
            (
                file_record(
                    "one",
                    "local",
                    "movies",
                    "Movies/A.mkv",
                    updated_at=NOW - timedelta(minutes=4),
                ),
                file_record(
                    "two",
                    "local",
                    "movies",
                    "Movies/B.mkv",
                    updated_at=NOW - timedelta(minutes=3),
                ),
                file_record(
                    "three",
                    "local",
                    "movies",
                    "Movies/C.mkv",
                    updated_at=NOW - timedelta(minutes=2),
                ),
                file_record(
                    "four",
                    "local",
                    "movies",
                    "Movies/D.mkv",
                    updated_at=NOW - timedelta(minutes=1),
                ),
            )
        )
        service = self._service(repository)
        values = service.list(
            FileCatalogFilter(
                after=(NOW - timedelta(minutes=3), "two"),
                limit=10,
            )
        )
        self.assertEqual([value.file_id for value in values], ["one"])
        values = service.list(
            FileCatalogFilter(
                before=(NOW - timedelta(minutes=3), "two"),
                limit=10,
            )
        )
        self.assertEqual([value.file_id for value in values], ["four", "three"])
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            service.list(
                FileCatalogFilter(
                    after=(NOW, "one"),
                    before=(NOW, "one"),
                )
            )
        with self.assertRaisesRegex(ValueError, "file ID"):
            service.list(FileCatalogFilter(after=(NOW, "")))

    def test_cli_cursor_list_construct_no_storage_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert(
                    (
                        file_record(
                            "one",
                            "source-storage",
                            "source",
                            "Movies/A.mkv",
                            updated_at=NOW - timedelta(minutes=3),
                        ),
                        file_record(
                            "two",
                            "source-storage",
                            "source",
                            "Movies/B.mkv",
                            updated_at=NOW - timedelta(minutes=2),
                        ),
                    )
                )
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(database)
            config_path = root / "strategy.json"
            config_path.write_text(json.dumps(document), encoding="utf-8")
            output, error = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("file catalog cursor constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "files",
                        "list",
                        "--after",
                        (NOW - timedelta(minutes=2)).isoformat(),
                        "--cursor-file-id",
                        "two",
                        "--limit",
                        "10",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("one", output.getvalue())
            self.assertNotIn("two", output.getvalue())

    def test_detail_enriches_latest_result_without_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteFileIndexRepository(database) as file_index:
                file_index.batch_upsert((file_record("one", "local", "movies", "Movies/A.mkv"),))
            with SQLiteTaskRepository(database) as task_repository:
                task_repository.append_result(
                    PersistentResultRecord(
                        "result-1",
                        "task-1",
                        "item-1",
                        "local",
                        "Movies/A.mkv",
                        "target",
                        "Media/Movies/A.mkv",
                        "C",
                        "tmdb",
                        "101",
                        "C",
                        "A",
                        "A",
                        "A",
                        "move",
                        "dry_run",
                        NOW,
                        title="Movie A",
                    )
                )
                coordinator = PersistentTaskCoordinator(task_repository, task_repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "local", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                RecognitionReviewService(
                    task_repository, development_strategy_configuration().recognition_types
                ).create(item, RecognitionResult(status=RecognitionStatus.UNRECOGNIZED))
            with (
                SQLiteFileIndexRepository(database) as file_index,
                SQLiteTaskRepository(database) as task_repository,
            ):
                service = FileCatalogService(
                    file_index,
                    ("movies",),
                    ("local",),
                    task_repository=task_repository,
                )
                detail = service.detail("one")
            self.assertEqual(detail.latest_result.result_id, "result-1")
            self.assertEqual(detail.latest_result.recognition_type, "C")
            self.assertEqual(detail.latest_result.title, "Movie A")
            self.assertEqual(detail.related_reviews[0].kind, "recognition")

    def test_stats_reflects_index_counts_and_scoping(self) -> None:
        repository = InMemoryFileIndexRepository()
        repository.batch_upsert(
            (
                file_record("one", "local", "movies", "Movies/A.mkv"),
                file_record(
                    "two",
                    "local",
                    "movies",
                    "Movies/B.mkv",
                    scan_status=FileScanStatus.UNSTABLE,
                ),
                file_record("three", "remote", "movies", "Movies/C.mkv"),
            )
        )
        service = self._service(repository)
        stats = service.stats(storage_id="local")
        self.assertEqual(stats.total, 2)
        self.assertEqual(stats.by_status.get(FileScanStatus.READY), 1)
        self.assertEqual(stats.by_status.get(FileScanStatus.UNSTABLE), 1)
        stats = service.stats(resource_library_id="movies")
        self.assertEqual(stats.total, 3)
        with self.assertRaisesRegex(ValueError, "Storage"):
            service.stats(storage_id="missing")

    def test_derived_filters_require_task_repository_and_match_latest_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteFileIndexRepository(database) as file_index:
                file_index.batch_upsert(
                    (
                        file_record("one", "local", "movies", "Movies/A (2024).mkv"),
                        file_record("two", "local", "movies", "Movies/B (2025).mkv"),
                    )
                )
            with SQLiteTaskRepository(database) as task_repository:
                task_repository.append_result(
                    PersistentResultRecord(
                        "result-1",
                        "task-1",
                        "item-1",
                        "local",
                        "Movies/A (2024).mkv",
                        "target",
                        "Media/Movies/A.mkv",
                        "C",
                        "tmdb",
                        "101",
                        "C",
                        "A",
                        "A",
                        "A",
                        "move",
                        "dry_run",
                        NOW,
                        title="Movie A (2024)",
                    )
                )
                task_repository.append_result(
                    PersistentResultRecord(
                        "result-2",
                        "task-2",
                        "item-2",
                        "local",
                        "Movies/B (2025).mkv",
                        "target",
                        "Media/Movies/B.mkv",
                        "B",
                        "tvdb",
                        "202",
                        "B",
                        "A",
                        "A",
                        "A",
                        "move",
                        "dry_run",
                        NOW,
                        title="Movie B (2025)",
                    )
                )
            with (
                SQLiteFileIndexRepository(database) as file_index,
                SQLiteTaskRepository(database) as task_repository,
            ):
                service = FileCatalogService(
                    file_index,
                    ("movies",),
                    ("local",),
                    task_repository=task_repository,
                )
                values = service.list(FileCatalogFilter(recognition_type="C", limit=10))
                self.assertEqual([value.file_id for value in values], ["one"])
                values = service.list(FileCatalogFilter(provider_id="202", limit=10))
                self.assertEqual([value.file_id for value in values], ["two"])
                values = service.list(FileCatalogFilter(year=2025, limit=10))
                self.assertEqual([value.file_id for value in values], ["two"])
            with SQLiteFileIndexRepository(database) as file_index:
                no_task_service = FileCatalogService(
                    file_index,
                    ("movies",),
                    ("local",),
                )
                with self.assertRaisesRegex(ValueError, "Task repository"):
                    no_task_service.list(FileCatalogFilter(recognition_type="C", limit=10))

    def test_cli_list_and_show_construct_no_storage_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert(
                    (file_record("one", "source-storage", "source", "Movies/A.mkv"),)
                )
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(database)
            config_path = root / "strategy.json"
            config_path.write_text(json.dumps(document), encoding="utf-8")
            output, error = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("file catalog constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "files",
                        "list",
                        "--limit",
                        "10",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("FILE CATALOG", output.getvalue())
            self.assertIn("Total: 1", output.getvalue())

            output, error = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("file catalog stats constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "files",
                        "stats",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("FILE CATALOG STATS", output.getvalue())
            self.assertIn("Total: 1", output.getvalue())

            output, error = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("file catalog constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "files",
                        "show",
                        "one",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("FILE CATALOG DETAIL", output.getvalue())
            self.assertIn("File ID: one", output.getvalue())


if __name__ == "__main__":
    unittest.main()
