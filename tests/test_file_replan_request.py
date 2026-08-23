from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.file_replan_request import FileReplanRequestService
from mediaflow.application.task_retry import TaskRetryRequestService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.task_persistence import PersistentResultRecord, TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from tests.test_file_catalog import file_record

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


class FileReplanRequestTests(unittest.TestCase):
    def _prepare(self, database):
        with SQLiteFileIndexRepository(database) as file_index:
            file_index.batch_upsert((file_record("one", "source-storage", "source", "Bad.mkv"),))
        with SQLiteTaskRepository(database) as repository:
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("preview", execute_authorized=False)
            item = coordinator.begin_item(
                task.task_id, "source-storage", "source", "Bad.mkv", "Bad.mkv"
            )
            failed = replace(item, status=TaskItemStatus.FAILED, error="failed")
            repository.upsert_item(failed)
            repository.append_result(
                PersistentResultRecord(
                    "result-1",
                    task.task_id,
                    item.item_id,
                    "source-storage",
                    "Bad.mkv",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    TaskItemStatus.FAILED.value,
                    NOW,
                )
            )

    def test_replan_requests_latest_failed_result_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            self._prepare(database)
            with (
                SQLiteFileIndexRepository(database) as file_index,
                SQLiteTaskRepository(database) as repository,
            ):
                catalog = FileCatalogService(
                    file_index,
                    ("source",),
                    ("source-storage",),
                    task_repository=repository,
                )
                decision = FileReplanRequestService(
                    catalog,
                    TaskRetryRequestService(repository),
                ).request("one", actor="operator")
                self.assertEqual(
                    repository.get_item(decision.item_id).status, TaskItemStatus.PENDING
                )

    def test_missing_latest_result_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteFileIndexRepository(database) as file_index:
                file_index.batch_upsert(
                    (file_record("one", "source-storage", "source", "Bad.mkv"),)
                )
            with (
                SQLiteFileIndexRepository(database) as file_index,
                SQLiteTaskRepository(database) as repository,
            ):
                catalog = FileCatalogService(
                    file_index,
                    ("source",),
                    ("source-storage",),
                    task_repository=repository,
                )
                with self.assertRaisesRegex(ValueError, "latest TaskResult"):
                    FileReplanRequestService(
                        catalog,
                        TaskRetryRequestService(repository),
                    ).request("one", actor="operator")

    def test_cli_replan_constructs_no_storage_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            self._prepare(database)
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(database)
            config_path = root / "strategy.json"
            config_path.write_text(json.dumps(document), encoding="utf-8")
            output, error = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("file re-plan constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "files",
                        "re-plan",
                        "one",
                        "--actor",
                        "operator",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("FILE RE-PLAN REQUEST", output.getvalue())
            self.assertIn("Media mutation: 0", output.getvalue())


if __name__ == "__main__":
    unittest.main()
