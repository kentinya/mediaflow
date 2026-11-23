from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
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
    CandidateMatchResult,
    CandidateMatchStatus,
    MediaCandidate,
    MediaType,
    MetadataIdentificationResult,
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
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from tests.managed_config_fixture import publish_managed_document
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
                coordinator, task, item = create_processing_item(repository)
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
                    [
                        value.item_id
                        for value in coordinator.retryable_items(task.task_id, failed_only=False)
                    ],
                    [item.item_id],
                )
                self.assertEqual(
                    repository.list_metadata_correction_audit(review.review_id)[0].note, "fix query"
                )
                with self.assertRaises(ValueError):
                    service.resolve(review.review_id, query="Again", year=2024, media_type="movie")
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)

    def test_correction_rejects_identity_type_outside_policy_query_type(self) -> None:
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
                with self.assertRaisesRegex(ValueError, "not permitted"):
                    service.resolve(
                        review.review_id,
                        query="Correct Title",
                        year=2024,
                        media_type="tv",
                        actor="operator",
                    )
                self.assertEqual(
                    repository.get_metadata_correction(review.review_id).status,
                    MetadataCorrectionStatus.PENDING,
                )
                self.assertEqual(
                    repository.get_item(item.item_id).status,
                    TaskItemStatus.WAITING_METADATA_CORRECTION,
                )

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
                task = coordinator.create("organize", execute_authorized=False)
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
        correction = MetadataCorrectionSelection("B", "B", "tmdb", "Correct Title", 2024, "tv")
        result = runner.run_path(
            "/tv/Wrong.2025.mkv",
            live_metadata=True,
            resource_library_id="tv",
            metadata_correction=correction,
        )
        self.assertEqual(provider.tv_queries, [("Correct Title", 2024)])
        self.assertEqual(result.metadata.identity.provider_id, "129")
        self.assertEqual(result.recognition.recognition_type_id, "B")
        self.assertEqual(result.policy.naming_policy_id, "B")
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

    def test_retired_correction_cli_is_an_ordinary_parser_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(database)
            config_path = Path(directory, "strategy.json")
            config_path.write_text(json.dumps(document), encoding="utf-8")
            publish_managed_document(document)
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
            # The retired CLI correction entrance is gone with the CLI; the
            # durable pending correction is untouched by any other surface.
            with self.assertRaises(ModuleNotFoundError):
                __import__("mediaflow.final_cli")
            with SQLiteTaskRepository(database) as repository:
                stored = repository.get_metadata_correction(review.review_id)
                self.assertEqual(stored.status.value, "pending")


def mismatch_identification(reason: str = "Season 4 is not available for 'Show' (2024)"):
    return MetadataIdentificationResult(
        MetadataIdentificationStatus.METADATA_MISMATCH,
        identification().recognition_type,
        match=CandidateMatchResult(CandidateMatchStatus.NOT_FOUND, reasons=(reason,)),
        query="Show",
    )


class MetadataCorrectionReopenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.configuration = development_strategy_configuration()
        self.policy = next(
            item for item in self.configuration.metadata_policies if item.policy_id == "B"
        )

    def _resolved_review(self, repository):
        _, _, item = create_processing_item(repository)
        service = MetadataCorrectionService(repository, self.configuration.metadata_policies)
        review = service.create(
            item,
            identification(MetadataIdentificationStatus.NOT_FOUND, count=0),
            self.policy,
            ParseResult("Show", year=2024, season=4, episode=1, episodes=(1,)),
        )
        service.resolve(
            review.review_id,
            query="Show",
            year=2024,
            media_type="tv",
            provider_id="2024",
            actor="operator",
            note="first decision",
        )
        item = replace(
            repository.get_item(item.item_id),
            status=TaskItemStatus.PROCESSING,
            stage="analysis",
        )
        repository.upsert_item(item)
        return service, item, review

    def test_mismatch_reopens_the_same_item_review_and_preserves_its_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service, item, review = self._resolved_review(repository)
                reopened = service.create(
                    item,
                    mismatch_identification(),
                    self.policy,
                    ParseResult("Show", year=2024, season=4, episode=1, episodes=(1,)),
                )
                self.assertEqual(reopened.review_id, review.review_id)
                self.assertEqual(reopened.status, MetadataCorrectionStatus.PENDING)
                self.assertIn("metadata_mismatch | Season 4 is not available", reopened.outcome)
                self.assertEqual(
                    repository.get_item(item.item_id).status,
                    TaskItemStatus.WAITING_METADATA_CORRECTION,
                )
                audit = repository.list_metadata_correction_audit(review.review_id)
                self.assertEqual(len(audit), 1)
                self.assertEqual(audit[0].note, "first decision")

                service.resolve(
                    reopened.review_id,
                    query="Show",
                    year=2019,
                    media_type="tv",
                    actor="operator",
                    note="second decision",
                )
                self.assertEqual(
                    len(repository.list_metadata_correction_audit(review.review_id)), 2
                )

    def test_reopen_failure_rolls_back_review_and_item_together(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                service, item, review = self._resolved_review(repository)
            connection = sqlite3.connect(database)
            connection.execute(
                """CREATE TRIGGER reject_correction_reopen BEFORE UPDATE ON task_items
                WHEN NEW.status='waiting_metadata_correction'
                BEGIN SELECT RAISE(ABORT, 'injected'); END"""
            )
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                service = MetadataCorrectionService(
                    repository, self.configuration.metadata_policies
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    service.create(
                        item,
                        mismatch_identification(),
                        self.policy,
                        ParseResult("Show", year=2024, season=4, episode=1, episodes=(1,)),
                    )
                self.assertEqual(
                    repository.get_metadata_correction(review.review_id).status,
                    MetadataCorrectionStatus.RESOLVED,
                )
                self.assertEqual(
                    repository.get_item(item.item_id).status,
                    TaskItemStatus.PROCESSING,
                )
                self.assertEqual(
                    len(repository.list_metadata_correction_audit(review.review_id)), 1
                )
