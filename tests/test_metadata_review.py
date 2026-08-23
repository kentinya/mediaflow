from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.dashboard import DashboardService
from mediaflow.application.media_organizer import MediaOrganizerBatchResult, MediaOrganizerService
from mediaflow.application.metadata_review import MetadataReviewService
from mediaflow.application.strategy_test import StrategyTestResult
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.metadata import (
    CandidateMatchResult,
    CandidateMatchStatus,
    CandidateScore,
    MediaCandidate,
    MediaType,
    MetadataIdentificationResult,
    MetadataIdentificationStatus,
    ScoreComponent,
)
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.recognition import (
    RecognitionResult,
    RecognitionType,
    ResolvedRecognitionPolicy,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import PersistentTaskStatus, TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def identification(
    status: MetadataIdentificationStatus = MetadataIdentificationStatus.NEED_CONFIRM,
    *,
    count: int = 2,
    recognition_type: str = "C",
) -> MetadataIdentificationResult:
    scores = []
    for rank in range(1, count + 1):
        candidate = MediaCandidate(
            "tmdb",
            str(100 + rank),
            MediaType.MOVIE,
            f"候选 {rank}",
            original_title=f"Candidate {rank}",
            year=2025,
            regional_release_date="2026-01-01",
            overview="must-not-persist super-secret",
            alternative_titles=("large-provider-payload",),
        )
        scores.append(
            CandidateScore(
                candidate,
                80 - rank,
                (ScoreComponent("title", 65, f"matched 候选 {rank}"),),
                matched_provider_title=f"候选 {rank}",
                matched_title_source="translation",
            )
        )
    match_status = {
        MetadataIdentificationStatus.NEED_CONFIRM: CandidateMatchStatus.NEED_CONFIRM,
        MetadataIdentificationStatus.AMBIGUOUS: CandidateMatchStatus.AMBIGUOUS,
        MetadataIdentificationStatus.NOT_FOUND: CandidateMatchStatus.NOT_FOUND,
    }.get(status, CandidateMatchStatus.MATCHED)
    match = CandidateMatchResult(
        match_status,
        scores[0].candidate if scores else None,
        scores[0].total_score if scores else 0,
        tuple(scores),
    )
    return MetadataIdentificationResult(
        status,
        RecognitionType(recognition_type, recognition_type),
        match=match,
        query="测试电影",
    )


def create_processing_item(repository: SQLiteTaskRepository, number: int = 1):
    coordinator = PersistentTaskCoordinator(repository, repository)
    task = coordinator.create("preview", execute_authorized=False)
    item = coordinator.begin_item(
        task.task_id, "source", "movies", f"Movie-{number}.mkv", f"Movie-{number}.mkv"
    )
    return coordinator, task, item


def api_request(api, path: str, *, token="viewer-token", query=""):
    statuses = []
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    body = b"".join(api(environ, lambda value, headers: statuses.append(value)))
    return int(statuses[0].split()[0]), json.loads(body)


class FakeStrategy:
    def __init__(self, result):
        self.result = result

    def run_path(self, *args, **kwargs):
        return self.result


class MetadataReviewTests(unittest.TestCase):
    def test_need_confirm_ambiguous_bounded_snapshot_and_c_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, _, item = create_processing_item(repository)
                review = MetadataReviewService(repository).create(
                    item, identification(count=25), "C"
                )
                self.assertEqual(review.recognition_type, "C")
                self.assertEqual(review.outcome, "need_confirm")
                self.assertEqual(
                    repository.get_item(item.item_id).status, TaskItemStatus.WAITING_METADATA
                )
                candidates = repository.list_metadata_review_candidates(review.review_id)
                self.assertEqual(len(candidates), 20)
                self.assertEqual([value.rank for value in candidates], list(range(1, 21)))
                serialized = repr(candidates)
                self.assertNotIn("must-not-persist", serialized)
                self.assertNotIn("large-provider-payload", serialized)
                self.assertEqual(candidates[0].matched_title_source, "translation")

                _, _, second_item = create_processing_item(repository, 2)
                second = MetadataReviewService(repository).create(
                    second_item,
                    identification(MetadataIdentificationStatus.AMBIGUOUS),
                    "A",
                )
                self.assertEqual(second.outcome, "ambiguous")
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(len(reopened.list_metadata_reviews()), 2)

    def test_non_review_outcomes_create_nothing_and_one_review_per_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, _, item = create_processing_item(repository)
                for status in (
                    MetadataIdentificationStatus.MATCHED,
                    MetadataIdentificationStatus.NOT_FOUND,
                    MetadataIdentificationStatus.PROVIDER_ERROR,
                ):
                    with self.subTest(status=status), self.assertRaises(ValueError):
                        MetadataReviewService(repository).create(item, identification(status), "A")
                self.assertEqual(repository.list_metadata_reviews(), ())
                MetadataReviewService(repository).create(item, identification(), "A")
                with self.assertRaises((sqlite3.IntegrityError, ValueError)):
                    MetadataReviewService(repository).create(item, identification(), "A")
                self.assertEqual(len(repository.list_metadata_reviews()), 1)

    def test_atomic_failure_rolls_back_review_candidates_and_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, _, item = create_processing_item(repository)
            connection = sqlite3.connect(database)
            connection.execute(
                """CREATE TRIGGER reject_review_candidate BEFORE INSERT
                ON metadata_review_candidates BEGIN SELECT RAISE(ABORT, 'injected'); END"""
            )
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                with self.assertRaises(sqlite3.IntegrityError):
                    MetadataReviewService(repository).create(item, identification(), "A")
                self.assertEqual(repository.list_metadata_reviews(), ())
                self.assertEqual(
                    repository.get_item(item.item_id).status, TaskItemStatus.PROCESSING
                )

    def test_workflow_waits_releases_lock_and_excludes_blind_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                recognition = RecognitionType("C", "C")
                result = StrategyTestResult(
                    "Movie.mkv",
                    ParseResult("Movie"),
                    RecognitionResult(recognition),
                    ResolvedRecognitionPolicy(recognition, "C", "A", "A", "A", "C"),
                    metadata=identification(),
                )
                service = MediaOrganizerService(
                    FakeStrategy(result),
                    None,
                    {},
                    {},
                    (),
                    JsonLinesOperationHistoryRepository(root / "history.jsonl"),
                    task_coordinator=coordinator,
                    task_id=task.task_id,
                )
                item_result = service.process_file(
                    "Movie.mkv",
                    resource_library=ResourceLibrary("movies", "Movies", "source", ""),
                    storage_path="Movie.mkv",
                )
                self.assertIsNone(item_result.error)
                stored = repository.list_items(task.task_id)[0]
                self.assertEqual(stored.status, TaskItemStatus.WAITING_METADATA)
                self.assertEqual(coordinator.retryable_items(task.task_id, failed_only=False), ())
                final = coordinator.finish(task.task_id, MediaOrganizerBatchResult(()))
                self.assertEqual(final.status, PersistentTaskStatus.PARTIAL_SUCCESS)
                self.assertTrue(repository.acquire("source", "Movie.mkv", "other-task", NOW))
                self.assertEqual(len(repository.list_metadata_reviews()), 1)
                self.assertEqual(repository.list_jobs(), ())
            history = (root / "history.jsonl").read_text(encoding="utf-8")
            self.assertIn("WAITING_METADATA", history)

    def test_cli_api_dashboard_rbac_limits_redaction_and_zero_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            configuration = json.loads(Path("config/strategy.example.json").read_text())
            configuration["persistence"] = {"databasePath": str(database)}
            config_path = root / "config.json"
            config_path.write_text(json.dumps(configuration), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                _, _, item = create_processing_item(repository)
                review = MetadataReviewService(repository).create(item, identification(), "C")
                dashboard = DashboardService(
                    repository, resource_library_count=1, media_library_count=1
                ).snapshot()
                self.assertEqual(dashboard.pending_metadata_reviews, 1)
            output = io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("metadata review CLI constructed Storage"),
            ):
                self.assertEqual(
                    final_main(
                        [
                            "--config",
                            str(config_path),
                            "metadata-reviews",
                            "show",
                            review.review_id,
                        ],
                        stdout=output,
                        stderr=io.StringIO(),
                    ),
                    0,
                )
            self.assertIn("METADATA REVIEW", output.getvalue())
            with SQLiteTaskRepository(database) as repository:
                principals = tuple(
                    ResolvedApiPrincipal(role, f"{role}-token", frozenset({ApiPermission.READ}))
                    for role in ("viewer", "operator", "executor", "auditor", "admin")
                )
                api = MediaFlowApi(repository, None, principals=principals)
                self.assertEqual(api_request(api, "/api/v1/metadata-reviews", token=None)[0], 401)
                for role in ("viewer", "operator", "executor", "auditor", "admin"):
                    self.assertEqual(
                        api_request(
                            api,
                            "/api/v1/metadata-reviews",
                            token=f"{role}-token",
                            query="limit=1",
                        )[0],
                        200,
                    )
                status, shown = api_request(
                    api,
                    f"/api/v1/metadata-reviews/{review.review_id}",
                    token="viewer-token",
                )
                self.assertEqual(status, 200)
                self.assertEqual(shown["recognition_type"], "C")
                self.assertNotIn("overview", repr(shown))
                for query in ("limit=0", "limit=101", "secret=token-value"):
                    self.assertEqual(
                        api_request(
                            api,
                            "/api/v1/metadata-reviews",
                            token="viewer-token",
                            query=query,
                        )[0],
                        400,
                    )
                self.assertEqual(
                    api_request(api, "/api/v1/metadata-reviews/unknown", token="viewer-token")[0],
                    404,
                )
                audit = repository.list_security_audit(limit=50)
                self.assertTrue(
                    any(value.route == "/api/v1/metadata-reviews/{id}" for value in audit)
                )
                self.assertNotIn("token-value", repr(audit))

    def test_schema_nine_migrates_to_ten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            connection.execute("INSERT INTO schema_version VALUES ('runtime', 9)")
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, 21)
                self.assertEqual(repository.list_metadata_reviews(), ())
