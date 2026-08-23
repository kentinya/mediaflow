from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from mediaflow.application.media_organizer import MediaOrganizerService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.application.strategy_test import (
    StrategyTestResult,
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.metadata import (
    MediaCandidate,
    MediaType,
    MetadataIdentificationStatus,
)
from mediaflow.domain.metadata_correction import (
    MetadataCorrectionSelection,
    MetadataCorrectionStatus,
)
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.recognition import (
    RecognitionResult,
    RecognitionType,
    ResolvedRecognitionPolicy,
)
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from tests.test_metadata_review import create_processing_item, identification


class CapturingProvider(SyntheticMetadataProvider):
    def __init__(self, candidates):
        super().__init__(candidates)
        self.movie_queries = []
        self.tv_queries = []

    def search_movie(self, query, policy=None, **kwargs):
        self.movie_queries.append((query.title_candidate, query.year))
        return super().search_movie(query, policy, **kwargs)

    def search_tv(self, query, policy=None, **kwargs):
        self.tv_queries.append((query.title_candidate, query.year))
        return super().search_tv(query, policy, **kwargs)


class MetadataCorrectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.configuration = development_strategy_configuration()
        self.policy_a = next(
            item for item in self.configuration.metadata_policies if item.policy_id == "A"
        )

    def test_not_found_correction_is_persisted_resolved_and_audited(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, _, item = create_processing_item(repository)
                service = MetadataCorrectionService(
                    repository, self.configuration.metadata_policies
                )
                review = service.create(
                    item,
                    identification(MetadataIdentificationStatus.NOT_FOUND, count=0),
                    self.policy_a,
                    ParseResult("Wrong", year=2025),
                )
                self.assertEqual(review.status, MetadataCorrectionStatus.PENDING)
                self.assertEqual(
                    repository.get_item(item.item_id).status,
                    TaskItemStatus.WAITING_METADATA_CORRECTION,
                )
                resolved = service.resolve(
                    review.review_id,
                    query=" Correct Title ",
                    year=2024,
                    media_type="movie",
                    actor="operator",
                    note="fix query",
                )
                self.assertEqual(resolved.corrected_query, "Correct Title")
                self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.PENDING)
                self.assertEqual(
                    repository.list_metadata_correction_audit(review.review_id)[0].note, "fix query"
                )
                with self.assertRaises(ValueError):
                    service.resolve(review.review_id, query="Again", year=2024, media_type="movie")
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)

    def test_tracked_not_found_waits_releases_lock_and_is_not_blindly_retryable(self) -> None:
        policy = self.policy_a

        class FakeStrategy:
            def run_path(self, *args, **kwargs):
                recognition = RecognitionType("C", "C")
                return StrategyTestResult(
                    "Movie.mkv",
                    ParseResult("Movie", year=2025),
                    RecognitionResult(recognition),
                    ResolvedRecognitionPolicy(recognition, "C", "A", "A", "A", "C"),
                    metadata_policy=policy,
                    metadata=identification(
                        MetadataIdentificationStatus.NOT_FOUND,
                        count=0,
                        recognition_type="C",
                    ),
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                service = MediaOrganizerService(
                    FakeStrategy(),
                    None,
                    {},
                    {},
                    (),
                    JsonLinesOperationHistoryRepository(root / "history.jsonl"),
                    task_coordinator=coordinator,
                    task_id=task.task_id,
                )
                result = service.process_file(
                    "Movie.mkv",
                    resource_library=ResourceLibrary("movies", "Movies", "source", ""),
                    storage_path="Movie.mkv",
                )
                self.assertIsNone(result.error)
                item = repository.list_items(task.task_id)[0]
                self.assertEqual(item.status, TaskItemStatus.WAITING_METADATA_CORRECTION)
                self.assertEqual(coordinator.retryable_items(task.task_id, failed_only=False), ())
                self.assertTrue(repository.acquire("source", "Movie.mkv", "other", item.updated_at))
                self.assertEqual(len(repository.list_metadata_corrections()), 1)

    def test_rejects_non_not_found_invalid_and_stale_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, _, item = create_processing_item(repository)
                service = MetadataCorrectionService(
                    repository, self.configuration.metadata_policies
                )
                with self.assertRaises(ValueError):
                    service.create(
                        item,
                        identification(MetadataIdentificationStatus.NEED_CONFIRM),
                        self.policy_a,
                        ParseResult("Movie"),
                    )
                review = service.create(
                    item,
                    identification(MetadataIdentificationStatus.NOT_FOUND, count=0),
                    self.policy_a,
                    ParseResult("Movie"),
                )
                invalid = (
                    dict(query=None, year=None, media_type="movie"),
                    dict(query="Movie", year=1800, media_type="movie"),
                    dict(query="Movie", year=2025, media_type="album"),
                    dict(query=None, year=2025, media_type="movie", provider_id="bad/id"),
                )
                for values in invalid:
                    with self.subTest(values=values), self.assertRaises(ValueError):
                        service.resolve(review.review_id, **values)
                stale = MetadataCorrectionService(repository, ())
                with self.assertRaisesRegex(ValueError, "no longer"):
                    stale.resolve(review.review_id, query="Movie", year=2025, media_type="movie")
                self.assertEqual(repository.list_metadata_correction_audit(review.review_id), ())

    def test_corrected_query_media_type_and_direct_id_use_real_provider_paths(self) -> None:
        candidates = (MediaCandidate("tmdb", "129", MediaType.TV, "Correct Title", year=2024),)
        provider = CapturingProvider(candidates)
        runner = strategy_runner_from_configuration(
            self.configuration, MetadataProviderRegistry((provider,))
        )
        correction = MetadataCorrectionSelection("C", "C", "tmdb", "Correct Title", 2024, "tv")
        result = runner.run_path(
            "/special/Wrong.2025.mkv",
            live_metadata=True,
            resource_library_id="special",
            metadata_correction=correction,
        )
        self.assertEqual(provider.tv_queries, [("Correct Title", 2024)])
        self.assertEqual(result.metadata.identity.provider_id, "129")
        self.assertEqual(result.recognition.recognition_type_id, "C")
        self.assertEqual(result.policy.naming_policy_id, "A")
        self.assertTrue(result.recognition_type_preserved)

        movie_provider = CapturingProvider(
            (MediaCandidate("tmdb", "858024", MediaType.MOVIE, "Hamnet", year=2025),)
        )
        direct = strategy_runner_from_configuration(
            self.configuration, MetadataProviderRegistry((movie_provider,))
        ).run_path(
            "/movies/Wrong.2025.mkv",
            live_metadata=True,
            resource_library_id="movies",
            metadata_correction=MetadataCorrectionSelection(
                "A", "A", "tmdb", None, 2025, "movie", "858024"
            ),
        )
        self.assertEqual(movie_provider.movie_queries, [])
        self.assertEqual(direct.metadata.identity.matched_by, "manual_provider_id")

    def test_cli_works_without_storage_or_provider_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(database)
            config_path = Path(directory, "strategy.json")
            config_path.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                _, _, item = create_processing_item(repository)
                review = MetadataCorrectionService(
                    repository, self.configuration.metadata_policies
                ).create(
                    item,
                    identification(MetadataIdentificationStatus.NOT_FOUND, count=0),
                    self.policy_a,
                    ParseResult("Wrong", year=2025),
                )
            output, error = io.StringIO(), io.StringIO()
            code = final_main(
                [
                    "--config",
                    str(config_path),
                    "metadata-corrections",
                    "resolve",
                    review.review_id,
                    "--query",
                    "Hamnet",
                    "--year",
                    "2025",
                    "--media-type",
                    "movie",
                    "--actor",
                    "operator",
                ],
                stdout=output,
                stderr=error,
            )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("Corrected query: Hamnet", output.getvalue())
            self.assertNotIn("authorization", output.getvalue().casefold())


if __name__ == "__main__":
    unittest.main()
