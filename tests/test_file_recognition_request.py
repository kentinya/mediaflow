from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.file_recognition_request import FileRecognitionRequestService
from mediaflow.application.recognition_retry import RecognitionRetryService
from mediaflow.application.recognition_review import RecognitionReviewService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.recognition import RecognitionResult, RecognitionStatus
from mediaflow.domain.recognition_review import RecognitionReviewStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from tests.test_file_catalog import file_record


class FileRecognitionRequestTests(unittest.TestCase):
    def _prepare(self, database):
        with SQLiteFileIndexRepository(database) as file_index:
            file_index.batch_upsert(
                (file_record("one", "source-storage", "source", "Unknown.mkv"),)
            )
        with SQLiteTaskRepository(database) as repository:
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("preview", execute_authorized=False)
            item = coordinator.begin_item(
                task.task_id, "source-storage", "source", "Unknown.mkv", "Unknown.mkv"
            )
            RecognitionReviewService(
                repository, development_strategy_configuration().recognition_types
            ).create(item, RecognitionResult(status=RecognitionStatus.UNRECOGNIZED))

    def test_request_uses_pending_recognition_review(self) -> None:
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
                decision = FileRecognitionRequestService(
                    catalog,
                    RecognitionRetryService(repository),
                ).request("one", actor="operator")
                self.assertEqual(decision.actor, "operator")
                detail = catalog.detail("one")
                review = next(item for item in detail.related_reviews if item.kind == "recognition")
                self.assertEqual(
                    repository.get_recognition_review(review.review_id).status,
                    RecognitionReviewStatus.RETRY_REQUESTED,
                )

    def test_missing_pending_review_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteFileIndexRepository(database) as file_index:
                file_index.batch_upsert(
                    (file_record("one", "source-storage", "source", "Unknown.mkv"),)
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
                with self.assertRaisesRegex(ValueError, "pending RecognitionReview"):
                    FileRecognitionRequestService(
                        catalog,
                        RecognitionRetryService(repository),
                    ).request("one", actor="operator")

    def test_cli_request_constructs_no_storage_or_provider(self) -> None:
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
                side_effect=AssertionError("file re-recognition constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "files",
                        "re-recognize",
                        "one",
                        "--actor",
                        "operator",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("FILE RE-RECOGNITION REQUEST", output.getvalue())
            self.assertIn("Media mutation: 0", output.getvalue())


if __name__ == "__main__":
    unittest.main()
