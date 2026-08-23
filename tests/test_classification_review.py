from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.classification_review import ClassificationReviewService
from mediaflow.application.dashboard import DashboardService
from mediaflow.application.media_organizer import MediaOrganizerBatchResult, MediaOrganizerService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.strategy_test import (
    StrategyTestResult,
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.classification import (
    ClassificationPolicy,
    ClassificationResult,
    ClassificationRule,
    ClassificationStatus,
)
from mediaflow.domain.classification_review import (
    ClassificationReviewStatus,
    ClassificationSelection,
)
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.metadata import (
    MediaCandidate,
    MediaIdentity,
    MediaType,
    MetadataIdentificationResult,
    MetadataIdentificationStatus,
)
from mediaflow.domain.naming import NamingResult
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
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_metadata_review import create_processing_item


def policy() -> ClassificationPolicy:
    return ClassificationPolicy(
        "A",
        "Movies",
        (
            ClassificationRule(
                "low",
                "Low",
                "movies",
                "Movies",
                "Other",
                priority=10,
            ),
            ClassificationRule(
                "high",
                "High",
                "movies",
                "Movies",
                "精选",
                priority=100,
            ),
            ClassificationRule(
                "disabled",
                "Disabled",
                "movies",
                "Movies",
                "Disabled",
                priority=1000,
                enabled=False,
            ),
        ),
    )


def identity() -> MediaIdentity:
    return MediaIdentity("tmdb", "129", MediaType.MOVIE, "千与千寻", year=2001)


def unclassified(recognition_type="C") -> ClassificationResult:
    return ClassificationResult(
        policy_id="A",
        recognition_type_id=recognition_type,
        status=ClassificationStatus.UNCLASSIFIED,
        warnings=("no classification rule matched",),
    )


def api_request(api, path, *, method="GET", token="operator", document=None, query=""):
    statuses = []
    raw = json.dumps(document or {}).encode()
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(raw)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(raw),
    }
    body = b"".join(api(environ, lambda value, headers: statuses.append(value)))
    return int(statuses[0].split()[0]), json.loads(body)


class FakeStrategy:
    def __init__(self, result, classification_policy):
        self.result = result
        self._policy = classification_policy

    def run_path(self, *args, **kwargs):
        return self.result

    def classification_policy(self, policy_id):
        if policy_id != self._policy.policy_id:
            raise LookupError(policy_id)
        return self._policy


class ClassificationReviewTests(unittest.TestCase):
    def test_create_bounded_ordered_review_waits_releases_lock_and_preserves_c(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator, task, item = create_processing_item(repository)
                review = ClassificationReviewService(repository).create(
                    item, unclassified(), policy(), identity()
                )
                self.assertEqual(review.recognition_type, "C")
                self.assertEqual(review.status, ClassificationReviewStatus.PENDING)
                choices = repository.list_classification_review_choices(review.review_id)
                self.assertEqual([value.rule_id for value in choices], ["high", "low"])
                self.assertEqual([value.relative_path for value in choices], ["精选", "Other"])
                self.assertEqual(
                    repository.get_item(item.item_id).status,
                    TaskItemStatus.WAITING_CLASSIFICATION,
                )
                self.assertEqual(coordinator.retryable_items(task.task_id, failed_only=False), ())
                coordinator.locks.release(item.storage_id, item.source_path, item.task_id)
                final = coordinator.finish(task.task_id, MediaOrganizerBatchResult(()))
                self.assertEqual(final.status, PersistentTaskStatus.PARTIAL_SUCCESS)
                dashboard = DashboardService(
                    repository, resource_library_count=1, media_library_count=1
                ).snapshot()
                self.assertEqual(dashboard.pending_classification_reviews, 1)
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(len(reopened.list_classification_reviews()), 1)

    def test_create_rejects_classified_empty_and_atomic_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, _, item = create_processing_item(repository)
                with self.assertRaises(ValueError):
                    ClassificationReviewService(repository).create(
                        item,
                        ClassificationResult("movies", "Other", "A", "A"),
                        policy(),
                        identity(),
                    )
                with self.assertRaises(ValueError):
                    ClassificationReviewService(repository).create(
                        item, unclassified(), ClassificationPolicy("A", "Empty"), identity()
                    )
            with SQLiteTaskRepository(database) as repository:
                repository._connection.execute(
                    """CREATE TRIGGER reject_classification_choice BEFORE INSERT
                    ON classification_review_choices BEGIN SELECT RAISE(ABORT, 'injected'); END"""
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    ClassificationReviewService(repository).create(
                        item, unclassified(), policy(), identity()
                    )
                self.assertEqual(repository.list_classification_reviews(), ())
                self.assertEqual(
                    repository.get_item(item.item_id).status, TaskItemStatus.PROCESSING
                )

    def test_choice_snapshot_is_bounded_to_one_hundred(self) -> None:
        rules = tuple(
            ClassificationRule(
                f"rule-{number:03}",
                f"Rule {number}",
                "movies",
                "Movies",
                f"Category-{number}",
                priority=number,
            )
            for number in range(105)
        )
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, _, item = create_processing_item(repository)
                review = ClassificationReviewService(repository).create(
                    item,
                    unclassified(),
                    ClassificationPolicy("A", "Many", rules),
                    identity(),
                )
                choices = repository.list_classification_review_choices(review.review_id)
                self.assertEqual(len(choices), 100)
                self.assertEqual(choices[0].rule_id, "rule-104")
                self.assertEqual(choices[-1].rule_id, "rule-005")

    def test_resolve_valid_invalid_atomic_and_concurrent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator, task, item = create_processing_item(repository)
                review = ClassificationReviewService(repository).create(
                    item, unclassified(), policy(), identity()
                )
                with self.assertRaises(ValueError):
                    ClassificationReviewService(repository).resolve(review.review_id, 9)
                resolved = ClassificationReviewService(repository).resolve(
                    review.review_id, 1, actor="operator", note=" deliberate "
                )
                self.assertEqual(resolved.selected_rule_id, "high")
                self.assertEqual(resolved.selected_relative_path, "精选")
                self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.PENDING)
                self.assertEqual(
                    tuple(
                        value.item_id
                        for value in coordinator.retryable_items(task.task_id, failed_only=False)
                    ),
                    (item.item_id,),
                )
                self.assertEqual(
                    repository.list_classification_review_audit(review.review_id)[0].note,
                    "deliberate",
                )
                with self.assertRaises(ValueError):
                    ClassificationReviewService(repository).resolve(review.review_id, 2)

                _, _, waiting_item = create_processing_item(repository, 3)
                waiting_review = ClassificationReviewService(repository).create(
                    waiting_item, unclassified(), policy(), identity()
                )
                stored = repository.get_item(waiting_item.item_id)
                repository.upsert_item(
                    stored.__class__(**{**stored.__dict__, "status": TaskItemStatus.FAILED})
                )
                with self.assertRaises(ValueError):
                    ClassificationReviewService(repository).resolve(waiting_review.review_id, 1)

            second_database = Path(directory, "concurrent.sqlite3")
            with SQLiteTaskRepository(second_database) as repository:
                _, _, item = create_processing_item(repository)
                review = ClassificationReviewService(repository).create(
                    item, unclassified(), policy(), identity()
                )
            barrier = threading.Barrier(2)
            outcomes = []

            def choose(rank):
                try:
                    with SQLiteTaskRepository(second_database) as repository:
                        barrier.wait()
                        ClassificationReviewService(repository).resolve(review.review_id, rank)
                    outcomes.append("ok")
                except (ValueError, sqlite3.OperationalError):
                    outcomes.append("rejected")

            threads = [threading.Thread(target=choose, args=(rank,)) for rank in (1, 2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sorted(outcomes), ["ok", "rejected"])

    def test_resolution_audit_failure_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, _, item = create_processing_item(repository)
                review = ClassificationReviewService(repository).create(
                    item, unclassified(), policy(), identity()
                )
                repository._connection.execute(
                    """CREATE TRIGGER reject_classification_audit BEFORE INSERT
                    ON classification_review_decision_audit
                    BEGIN SELECT RAISE(ABORT, 'injected'); END"""
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    ClassificationReviewService(repository).resolve(review.review_id, 1)
                self.assertEqual(
                    repository.get_classification_review(review.review_id).status,
                    ClassificationReviewStatus.PENDING,
                )
                self.assertEqual(
                    repository.get_item(item.item_id).status,
                    TaskItemStatus.WAITING_CLASSIFICATION,
                )

    def test_manual_configured_rule_selection_preserves_c_and_rejects_stale(self) -> None:
        configuration = development_strategy_configuration()
        provider = SyntheticMetadataProvider(
            (MediaCandidate("tmdb", "129", MediaType.MOVIE, "Unknown", year=2001),)
        )
        runner = strategy_runner_from_configuration(
            configuration, MetadataProviderRegistry((provider,))
        )
        selection = ClassificationSelection("C", "A", "animation-movie", "movies", "Animation")
        result = runner.run_path(
            "/special/Unknown (2001).mkv",
            live_metadata=True,
            show_naming=True,
            show_classification=True,
            resource_library_id="special",
            metadata_selection=None,
            classification_selection=selection,
        )
        self.assertEqual(result.recognition.recognition_type_id, "C")
        self.assertEqual(result.classification.status, ClassificationStatus.CLASSIFIED)
        self.assertEqual(result.classification.matched_rule_id, "animation-movie")
        self.assertEqual(result.classification.relative_path, "Animation")
        for stale in (
            ClassificationSelection("A", "A", "animation-movie", "movies", "Animation"),
            ClassificationSelection("C", "B", "animation-movie", "movies", "Animation"),
            ClassificationSelection("C", "A", "missing", "movies", "Animation"),
            ClassificationSelection("C", "A", "animation-movie", "movies", "Changed"),
        ):
            with self.subTest(stale=stale), self.assertRaisesRegex(Exception, "no longer matches"):
                runner.run_path(
                    "/special/Unknown (2001).mkv",
                    live_metadata=True,
                    show_classification=True,
                    resource_library_id="special",
                    classification_selection=stale,
                )

    def test_production_workflow_waits_without_planning_or_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recognition = RecognitionType("C", "C")
            classification = unclassified()
            strategy = StrategyTestResult(
                "Movie.mkv",
                ParseResult("Movie"),
                RecognitionResult(recognition),
                ResolvedRecognitionPolicy(recognition, "C", "A", "A", "A", "C"),
                metadata=MetadataIdentificationResult(
                    MetadataIdentificationStatus.MATCHED,
                    recognition,
                    identity=identity(),
                ),
                naming=NamingResult(("Movie",), "Movie.mkv"),
                classification=classification,
            )
            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                service = MediaOrganizerService(
                    FakeStrategy(strategy, policy()),
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
                    resource_library=ResourceLibrary("special", "Special", "source", ""),
                    storage_path="Movie.mkv",
                )
                self.assertIsNone(result.error)
                self.assertIsNone(result.plan)
                self.assertIsNone(result.execution)
                self.assertEqual(
                    repository.list_items(task.task_id)[0].status,
                    TaskItemStatus.WAITING_CLASSIFICATION,
                )
                self.assertEqual(len(repository.list_classification_reviews()), 1)
                self.assertEqual(repository.list_jobs(), ())

    def test_cli_api_rbac_injection_redaction_and_zero_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            document = json.loads(Path("config/strategy.example.json").read_text())
            document["persistence"] = {"databasePath": str(database)}
            config_path = root / "config.json"
            config_path.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                _, _, item = create_processing_item(repository)
                review = ClassificationReviewService(repository).create(
                    item, unclassified(), policy(), identity()
                )
            output = io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("classification review constructed Storage"),
            ):
                self.assertEqual(
                    final_main(
                        [
                            "--config",
                            str(config_path),
                            "classification-reviews",
                            "resolve",
                            review.review_id,
                            "--choice-rank",
                            "1",
                            "--actor",
                            "local",
                        ],
                        stdout=output,
                        stderr=io.StringIO(),
                    ),
                    0,
                )
            self.assertIn("Selected rule: high", output.getvalue())
            with SQLiteTaskRepository(database) as repository:
                _, _, item = create_processing_item(repository, 2)
                review = ClassificationReviewService(repository).create(
                    item, unclassified("A"), policy(), identity()
                )
                principals = (
                    ResolvedApiPrincipal("viewer", "viewer", frozenset({ApiPermission.READ})),
                    ResolvedApiPrincipal(
                        "operator",
                        "operator",
                        frozenset(
                            {ApiPermission.READ, ApiPermission.RESOLVE_CLASSIFICATION_REVIEW}
                        ),
                    ),
                )
                api = MediaFlowApi(repository, None, principals=principals)
                status, listed = api_request(
                    api, "/api/v1/classification-reviews", query="limit=10"
                )
                self.assertEqual(status, 200)
                self.assertTrue(listed["items"])
                status, detail = api_request(
                    api, f"/api/v1/classification-reviews/{review.review_id}"
                )
                self.assertEqual(status, 200)
                self.assertEqual([value["rank"] for value in detail["choices"]], [1, 2])
                status, _ = api_request(api, "/api/v1/classification-reviews", query="limit=0")
                self.assertEqual(status, 400)
                status, _ = api_request(
                    api,
                    f"/api/v1/classification-reviews/{review.review_id}/resolve",
                    method="POST",
                    token="viewer",
                    document={"choiceRank": 1},
                )
                self.assertEqual(status, 403)
                status, _ = api_request(
                    api,
                    f"/api/v1/classification-reviews/{review.review_id}/resolve",
                    method="POST",
                    document={"choiceRank": 2},
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    repository.get_classification_review(review.review_id).actor, "operator"
                )
                self.assertEqual(repository.list_jobs(), ())
                status, detail = api_request(
                    api, f"/api/v1/classification-reviews/{review.review_id}"
                )
                self.assertEqual(status, 200)
                self.assertEqual(len(detail["audit"]), 1)
                self.assertNotIn("note", detail["audit"][0])
                status, _ = api_request(
                    api,
                    "/api/v1/classification-reviews/missing/resolve",
                    method="POST",
                    document={"choiceRank": 1, "path": "Injected", "execute": True},
                )
                self.assertEqual(status, 400)
                self.assertIn(
                    "/api/v1/classification-reviews/{id}/resolve",
                    [entry.route for entry in repository.list_security_audit()],
                )

    def test_schema_eleven_migrates_classification_review_tables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                repository._connection.execute(
                    "UPDATE schema_version SET version=11 WHERE component='runtime'"
                )
                repository._connection.commit()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, 20)
                tables = {
                    row["name"]
                    for row in repository._connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                self.assertIn("classification_reviews", tables)
                self.assertIn("classification_review_decision_audit", tables)
