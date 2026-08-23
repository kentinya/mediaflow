from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.metadata_review import MetadataReviewService
from mediaflow.application.strategy_test import (
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.domain.metadata import (
    MediaCandidate,
    MediaType,
    MetadataError,
    MetadataErrorCode,
    MetadataIdentificationStatus,
)
from mediaflow.domain.metadata_review import MetadataReviewStatus, MetadataSelection
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_metadata_review import create_processing_item, identification


def api_request(api, path, *, method="GET", token="operator", document=None):
    statuses = []
    raw = json.dumps(document or {}).encode()
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(raw)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(raw),
    }
    body = b"".join(api(environ, lambda value, headers: statuses.append(value)))
    return int(statuses[0].split()[0]), json.loads(body)


class MetadataResolutionTests(unittest.TestCase):
    def test_resolve_persisted_rank_preserves_c_and_transitions_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator, task, item = create_processing_item(repository)
                review = MetadataReviewService(repository).create(item, identification(), "C")
                resolved = MetadataReviewService(repository).resolve(
                    review.review_id, 2, actor="operator", note=" selected deliberately "
                )
                self.assertEqual(resolved.status, MetadataReviewStatus.RESOLVED)
                self.assertEqual(resolved.recognition_type, "C")
                self.assertEqual(resolved.selected_rank, 2)
                self.assertEqual(resolved.selected_provider_id, "102")
                self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.PENDING)
                self.assertEqual(
                    tuple(
                        value.item_id
                        for value in coordinator.retryable_items(task.task_id, failed_only=False)
                    ),
                    (item.item_id,),
                )
                audit = repository.list_metadata_review_audit(review.review_id)
                self.assertEqual(len(audit), 1)
                self.assertEqual(audit[0].provider_id, "102")
                self.assertEqual(audit[0].note, "selected deliberately")
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(
                    reopened.get_metadata_review(review.review_id).selected_provider_id, "102"
                )
                self.assertEqual(len(reopened.list_metadata_review_audit(review.review_id)), 1)

    def test_invalid_repeat_and_nonwaiting_resolution_fail_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, _, item = create_processing_item(repository)
                review = MetadataReviewService(repository).create(item, identification(), "A")
                for rank in (0, 3, 999):
                    with self.subTest(rank=rank), self.assertRaises(ValueError):
                        MetadataReviewService(repository).resolve(review.review_id, rank)
                repository.upsert_item(
                    repository.get_item(item.item_id).__class__(
                        **{
                            **repository.get_item(item.item_id).__dict__,
                            "status": TaskItemStatus.FAILED,
                        }
                    )
                )
                with self.assertRaises(ValueError):
                    MetadataReviewService(repository).resolve(review.review_id, 1)
                self.assertEqual(repository.list_metadata_review_audit(review.review_id), ())
                self.assertEqual(
                    repository.get_metadata_review(review.review_id).status,
                    MetadataReviewStatus.PENDING,
                )
                with self.assertRaises(LookupError):
                    MetadataReviewService(repository).resolve("missing", 1)

    def test_audit_failure_rolls_back_review_and_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, _, item = create_processing_item(repository)
                review = MetadataReviewService(repository).create(item, identification(), "A")
            connection = sqlite3.connect(database)
            connection.execute(
                """CREATE TRIGGER reject_metadata_decision BEFORE INSERT
                ON metadata_review_decision_audit BEGIN SELECT RAISE(ABORT, 'injected'); END"""
            )
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                with self.assertRaises(sqlite3.IntegrityError):
                    MetadataReviewService(repository).resolve(review.review_id, 1)
                self.assertEqual(
                    repository.get_metadata_review(review.review_id).status,
                    MetadataReviewStatus.PENDING,
                )
                self.assertEqual(
                    repository.get_item(item.item_id).status, TaskItemStatus.WAITING_METADATA
                )
                self.assertEqual(repository.list_metadata_review_audit(review.review_id), ())

    def test_concurrent_resolution_commits_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                _, _, item = create_processing_item(repository)
                review = MetadataReviewService(repository).create(item, identification(), "A")
            barrier = threading.Barrier(2)
            outcomes = []

            def resolve(rank):
                try:
                    with SQLiteTaskRepository(database) as repository:
                        barrier.wait()
                        MetadataReviewService(repository).resolve(review.review_id, rank)
                    outcomes.append("ok")
                except (ValueError, sqlite3.OperationalError):
                    outcomes.append("rejected")

            threads = [threading.Thread(target=resolve, args=(rank,)) for rank in (1, 2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sorted(outcomes), ["ok", "rejected"])
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(len(repository.list_metadata_review_audit(review.review_id)), 1)

    def test_selection_uses_provider_detail_not_search_and_preserves_c(self) -> None:
        configuration = development_strategy_configuration()
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "858024",
                    MediaType.MOVIE,
                    "Hamnet",
                    year=2025,
                    genres=("Animation",),
                ),
            )
        )
        runner = strategy_runner_from_configuration(
            configuration, MetadataProviderRegistry((provider,))
        )
        selection = MetadataSelection("C", "C", "tmdb", "858024", "movie")
        result = runner.run_path(
            "/special/哈姆奈特 (2025).mkv",
            live_metadata=True,
            show_naming=True,
            show_classification=True,
            resource_library_id="special",
            metadata_selection=selection,
        )
        self.assertEqual(provider.calls, 1)
        self.assertEqual(result.metadata.identity.provider_id, "858024")
        self.assertEqual(result.metadata.identity.matched_by, "manual_provider_id")
        self.assertEqual(result.recognition.recognition_type_id, "C")
        self.assertTrue(result.recognition_type_preserved)
        self.assertIsNotNone(result.naming)
        self.assertIsNotNone(result.classification)
        for stale in (
            MetadataSelection("A", "C", "tmdb", "858024", "movie"),
            MetadataSelection("C", "A", "tmdb", "858024", "movie"),
            MetadataSelection("C", "C", "other", "858024", "movie"),
            MetadataSelection("C", "C", "tmdb", "858024", "tv"),
        ):
            with self.subTest(stale=stale), self.assertRaisesRegex(Exception, "no longer matches"):
                runner.run_path(
                    "/special/哈姆奈特 (2025).mkv",
                    live_metadata=True,
                    resource_library_id="special",
                    metadata_selection=stale,
                )

    def test_provider_failure_during_selected_retry_is_a_metadata_failure(self) -> None:
        class FailingProvider(SyntheticMetadataProvider):
            def get_movie(self, provider_id, policy=None, **kwargs):
                self.calls += 1
                raise MetadataError(MetadataErrorCode.TIMEOUT, "provider unavailable")

        provider = FailingProvider(
            (MediaCandidate("tmdb", "858024", MediaType.MOVIE, "Hamnet", year=2025),)
        )
        runner = strategy_runner_from_configuration(
            development_strategy_configuration(), MetadataProviderRegistry((provider,))
        )
        result = runner.run_path(
            "/movies/Hamnet (2025).mkv",
            live_metadata=True,
            resource_library_id="movies",
            metadata_selection=MetadataSelection("A", "A", "tmdb", "858024", "movie"),
        )
        self.assertEqual(provider.calls, 1)
        self.assertEqual(result.metadata.status, MetadataIdentificationStatus.PROVIDER_ERROR)
        self.assertIsNone(result.metadata.identity)

    def test_cli_and_api_resolution_permissions_fields_and_zero_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            document = json.loads(Path("config/strategy.example.json").read_text())
            document["persistence"] = {"databasePath": str(database)}
            config_path = root / "config.json"
            config_path.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                _, _, item = create_processing_item(repository)
                review = MetadataReviewService(repository).create(item, identification(), "C")
            output = io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("resolution constructed Storage"),
            ):
                self.assertEqual(
                    final_main(
                        [
                            "--config",
                            str(config_path),
                            "metadata-reviews",
                            "resolve",
                            review.review_id,
                            "--candidate-rank",
                            "1",
                            "--actor",
                            "local-operator",
                        ],
                        stdout=output,
                        stderr=io.StringIO(),
                    ),
                    0,
                )
            self.assertIn("Selected candidate: tmdb:101", output.getvalue())
            with SQLiteTaskRepository(database) as repository:
                _, _, second_item = create_processing_item(repository, 2)
                second = MetadataReviewService(repository).create(
                    second_item, identification(), "A"
                )
                principals = (
                    ResolvedApiPrincipal("viewer", "viewer", frozenset({ApiPermission.READ})),
                    ResolvedApiPrincipal(
                        "operator",
                        "operator",
                        frozenset({ApiPermission.READ, ApiPermission.RESOLVE_METADATA_REVIEW}),
                    ),
                )
                api = MediaFlowApi(repository, None, principals=principals)
                status, _ = api_request(
                    api,
                    f"/api/v1/metadata-reviews/{second.review_id}/resolve",
                    method="POST",
                    token="viewer",
                    document={"candidateRank": 1},
                )
                self.assertEqual(status, 403)
                status, _ = api_request(
                    api,
                    f"/api/v1/metadata-reviews/{second.review_id}/resolve",
                    method="POST",
                    document={"candidateRank": 2},
                )
                self.assertEqual(status, 200)
                resolved = repository.get_metadata_review(second.review_id)
                self.assertEqual(resolved.actor, "operator")
                self.assertEqual(repository.list_jobs(), ())
                status, _ = api_request(
                    api,
                    "/api/v1/metadata-reviews/missing/resolve",
                    method="POST",
                    document={"candidateRank": 1, "providerId": "injected", "execute": True},
                )
                self.assertEqual(status, 400)
                routes = [entry.route for entry in repository.list_security_audit()]
                self.assertIn("/api/v1/metadata-reviews/{id}/resolve", routes)

    def test_schema_ten_migrates_resolution_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                repository._connection.execute(
                    "UPDATE schema_version SET version=10 WHERE component='runtime'"
                )
                repository._connection.commit()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, 20)
                columns = {
                    row["name"]
                    for row in repository._connection.execute("PRAGMA table_info(metadata_reviews)")
                }
                self.assertIn("selected_provider_id", columns)
                self.assertIsNotNone(
                    repository._connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name='metadata_review_decision_audit'"
                    ).fetchone()
                )
