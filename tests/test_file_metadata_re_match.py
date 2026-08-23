from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.file_metadata_correction import FileMetadataCorrectionService
from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.metadata import MetadataIdentificationStatus
from mediaflow.domain.metadata_correction import MetadataCorrectionStatus
from mediaflow.domain.parser import ParseResult
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from tests.test_file_catalog import file_record
from tests.test_metadata_review import identification


class FileMetadataReMatchTests(unittest.TestCase):
    def _prepare(self, database):
        strategy = development_strategy_configuration()
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
            policy = next(value for value in strategy.metadata_policies if value.policy_id == "A")
            MetadataCorrectionService(repository, strategy.metadata_policies).create(
                item,
                identification(MetadataIdentificationStatus.NOT_FOUND, count=0),
                policy,
                ParseResult("Unknown", year=2025),
            )

    def test_re_match_resolves_pending_metadata_correction(self) -> None:
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
                review = FileMetadataCorrectionService(
                    catalog,
                    MetadataCorrectionService(
                        repository,
                        development_strategy_configuration().metadata_policies,
                    ),
                ).resolve(
                    "one",
                    query="Correct Title",
                    year=2024,
                    media_type="movie",
                    actor="operator",
                )
                self.assertEqual(review.corrected_query, "Correct Title")
                self.assertEqual(review.status, MetadataCorrectionStatus.RESOLVED)
                detail = catalog.detail("one")
                link = next(
                    item for item in detail.related_reviews if item.kind == "metadata_correction"
                )
                self.assertEqual(
                    repository.get_metadata_correction(link.review_id).status,
                    MetadataCorrectionStatus.RESOLVED,
                )

    def test_missing_review_fails_closed(self) -> None:
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
                with self.assertRaisesRegex(ValueError, "pending MetadataCorrectionReview"):
                    FileMetadataCorrectionService(
                        catalog,
                        MetadataCorrectionService(
                            repository,
                            development_strategy_configuration().metadata_policies,
                        ),
                    ).resolve(
                        "one",
                        query="Correct Title",
                        media_type="movie",
                        actor="operator",
                    )

    def test_cli_re_match_constructs_no_storage_or_provider(self) -> None:
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
                side_effect=AssertionError("file metadata re-match constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "files",
                        "re-match",
                        "one",
                        "--query",
                        "Correct Title",
                        "--media-type",
                        "movie",
                        "--actor",
                        "operator",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("FILE METADATA RE-MATCH", output.getvalue())
            self.assertIn("Media mutation: 0", output.getvalue())


if __name__ == "__main__":
    unittest.main()
