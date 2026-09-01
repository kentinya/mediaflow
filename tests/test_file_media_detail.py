from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.evidence_capture import build_pipeline_evidence
from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.media_organizer import MediaOrganizerService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.application.recognition_review import RecognitionReviewService
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
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.media_evidence import EvidenceSection
from mediaflow.domain.metadata import (
    CandidateMatchResult,
    CandidateMatchStatus,
    CandidateScore,
    MediaCandidate,
    MediaIdentity,
    MediaType,
    MetadataIdentificationResult,
    MetadataIdentificationStatus,
    ScoreComponent,
)
from mediaflow.domain.naming import NamingResult
from mediaflow.domain.organizer import (
    Conflict,
    ConflictStrategy,
    ConflictType,
    ExecutionResult,
    ExecutionStatus,
    OrganizeOperationType,
    OrganizePlan,
    OrganizePolicy,
    PlanOperation,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.recognition import (
    RecognitionResult,
    RecognitionStatus,
    RecognitionType,
    ResolvedRecognitionPolicy,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTaskItem,
    TaskItemStatus,
)
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_file_catalog import file_record

NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)


def api_request(api, path: str, *, token="viewer-token", method="GET", body=None, query=""):
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }
    if body is not None:
        raw = json.dumps(body).encode("utf-8")
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    body = b"".join(api(environ, lambda value, headers: statuses.append(value)))
    return int(statuses[0].split()[0]), json.loads(body)


def _metadata_waiting_result() -> MetadataIdentificationResult:
    candidate = MediaCandidate("tmdb", "129", MediaType.MOVIE, "Movie", year=2024)
    score = CandidateScore(
        candidate,
        88.5,
        (ScoreComponent("title", 65, "title similarity"),),
        matched_local_title="Movie",
        matched_provider_title="Movie",
        matched_title_source="title",
    )
    return MetadataIdentificationResult(
        MetadataIdentificationStatus.NEED_CONFIRM,
        RecognitionType("C", "Special"),
        match=CandidateMatchResult(
            CandidateMatchStatus.NEED_CONFIRM,
            candidate,
            score.total_score,
            (score,),
        ),
        query="Movie",
    )


def _metadata_correction_result() -> MetadataIdentificationResult:
    return MetadataIdentificationResult(
        MetadataIdentificationStatus.NOT_FOUND,
        RecognitionType("C", "Special"),
        query="Missing Movie",
    )


def _classification_waiting_result() -> tuple[
    ClassificationResult, ClassificationPolicy, MediaIdentity
]:
    policy = ClassificationPolicy(
        "A",
        "Movies",
        (
            ClassificationRule(
                "rule-a",
                "Movies",
                "movies",
                "Movies",
                "Other",
                priority=10,
            ),
        ),
    )
    return (
        ClassificationResult(
            policy_id="A",
            recognition_type_id="C",
            status=ClassificationStatus.UNCLASSIFIED,
            warnings=("no match",),
        ),
        policy,
        MediaIdentity("tmdb", "129", MediaType.MOVIE, "Movie", year=2024),
    )


def _conflicted_plan() -> OrganizePlan:
    source = "Incoming/Movie.mkv"
    target = "Movies/Movie/Movie.mkv"
    return OrganizePlan(
        "source",
        "target",
        source,
        target,
        "C",
        "A",
        "A",
        "A",
        operation=PlanOperation.MOVE,
        conflicts=(Conflict(ConflictType.DESTINATION_EXISTS, source, target, "exists"),),
        status=PlanStatus.CONFLICT,
        plan_id="plan-conflict",
        media_library_root="Movies",
        relative_destination="Movie/Movie.mkv",
        source_location=StorageLocation("source", source),
        destination_location=StorageLocation("target", target),
    )


class _StaticStrategy:
    """Small production-pipeline seam for exercising each waiting boundary."""

    def __init__(self, result, classification_policy=None) -> None:
        self.result = result
        self._classification_policy = classification_policy

    def run_path(self, *args, **kwargs):
        return self.result

    def classification_policy(self, policy_id):
        if (
            self._classification_policy is None
            or policy_id != self._classification_policy.policy_id
        ):
            raise LookupError(policy_id)
        return self._classification_policy


class FileMediaDetailTests(unittest.TestCase):
    def _database(self, directory: str) -> Path:
        return Path(directory, "runtime.sqlite3")

    def test_pipeline_evidence_recursively_redacts_complete_credentials(self) -> None:
        secret = "closure-review-secret"
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(self._database(directory)) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                execution = ExecutionResult(
                    ExecutionStatus.FAILED,
                    PlanOperation.MOVE,
                    "Movies/A.mkv",
                    "Library/A.mkv",
                    warnings=(
                        f"Authorization: Basic {secret}",
                        f"api_key={secret}",
                        f"password: {secret}",
                    ),
                    errors=(
                        f"Authorization: Bearer {secret}",
                        f"token={secret}",
                        f"Cookie: session={secret}",
                    ),
                )
                evidence = build_pipeline_evidence(
                    task,
                    item,
                    execution=execution,
                    error=f"Authorization: Bearer {secret}",
                )

        document = evidence.document()
        serialized = json.dumps(document, ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertIn("[redacted]", serialized)
        self.assertEqual(document["sections"]["operation"]["value"]["status"], "FAILED")
        self.assertEqual(
            document["sections"]["operation"]["value"]["errors"][0],
            "Authorization: [redacted]",
        )
        self.assertTrue(document["sections"]["operation"]["available"])

    def test_pipeline_evidence_write_boundaries_redact_before_sqlite(self) -> None:
        secret = "closure-review-secret"
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                unsafe = replace(
                    build_pipeline_evidence(task, item, outcome="failed"),
                    evidence_id="unsafe-append",
                    error=f"Authorization: Bearer {secret}",
                    warnings=(f"token={secret}",),
                    sections={
                        "operation": EvidenceSection(
                            True,
                            {"errors": [f"Authorization: Basic {secret}"], "status": "FAILED"},
                            ({"reason": f"password={secret}"},),
                            (f"Cookie: session={secret}",),
                            unavailable_reason=f"secret={secret}",
                        )
                    },
                )
                repository.append_evidence(unsafe)
                completed = replace(
                    item, status=TaskItemStatus.FAILED, stage="failed", error="safe"
                )
                result = PersistentResultRecord(
                    "result-secret-test",
                    task.task_id,
                    item.item_id,
                    "source",
                    "Movies/A.mkv",
                    None,
                    None,
                    "C",
                    None,
                    None,
                    "C",
                    "A",
                    "A",
                    "A",
                    "move",
                    "failed",
                    NOW,
                    error="safe",
                )
                repository.complete_item_with_evidence(
                    completed,
                    result,
                    replace(unsafe, evidence_id="unsafe-completion"),
                )
            self.assertNotIn(secret.encode(), database.read_bytes())
            with SQLiteTaskRepository(database) as reopened:
                stored = reopened.list_evidence_for_item(item.item_id)
                self.assertEqual(len(stored), 2)
                serialized = json.dumps([value.document() for value in stored], ensure_ascii=False)
                self.assertNotIn(secret, serialized)
                self.assertIn("[redacted]", serialized)

    def test_historical_unsafe_evidence_is_redacted_on_read_without_rewrite(self) -> None:
        secret = "closure-review-secret"
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert((file_record("one", "source", "movies", "Movies/A.mkv"),))
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                raw_document = build_pipeline_evidence(task, item, outcome="failed").document()
                raw_document["error"] = f"Authorization: Bearer {secret}"
                raw_document["warnings"] = [f"token={secret}"]
                raw_document["sections"]["operation"] = {
                    "available": True,
                    "value": {
                        "status": "FAILED",
                        "errors": [f"Authorization: Basic {secret}"],
                    },
                    "items": [{"reason": f"password={secret}"}],
                    "warnings": [f"Cookie: session={secret}"],
                    "truncated": False,
                    "unavailableReason": f"secret={secret}",
                }
                raw_json = json.dumps(raw_document, ensure_ascii=False, sort_keys=True)
                repository._connection.execute(
                    """INSERT INTO pipeline_evidence (
                        evidence_id, task_id, item_id, attempts, source_storage_id, source_path,
                        captured_at, configuration_snapshot_id, configuration_snapshot_digest,
                        outcome, document
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        "historical-unsafe",
                        task.task_id,
                        item.item_id,
                        item.attempts,
                        "source",
                        "Movies/A.mkv",
                        NOW.isoformat(),
                        None,
                        None,
                        "failed",
                        raw_json,
                    ),
                )
                repository._connection.commit()
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as repository,
            ):
                before = repository._connection.execute(
                    "SELECT document FROM pipeline_evidence WHERE evidence_id=?",
                    ("historical-unsafe",),
                ).fetchone()["document"]
                service = FileCatalogService(
                    index, ("movies",), ("source",), task_repository=repository
                )
                detail = service.detail("one")
                application_document = json.dumps(detail.evidence[0].document(), ensure_ascii=False)
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                    file_catalog=service,
                )
                status, response = api_request(api, "/api/v1/files/one")
                after = repository._connection.execute(
                    "SELECT document FROM pipeline_evidence WHERE evidence_id=?",
                    ("historical-unsafe",),
                ).fetchone()["document"]
            response_text = json.dumps(response, ensure_ascii=False)
            self.assertEqual(status, 200)
            self.assertNotIn(secret, application_document)
            self.assertNotIn(secret, response_text)
            self.assertIn("[redacted]", response_text)
            self.assertEqual(before, raw_json)
            self.assertEqual(after, raw_json)
            self.assertIn("JSON.stringify(item)", APP_JS.decode())

    def test_waiting_boundaries_publish_evidence_and_state_atomically(self) -> None:
        """Each production waiting boundary must roll back all rows on evidence failure."""

        families = ("recognition", "metadata", "metadata_correction", "classification", "conflict")
        blocker_tables = {
            "recognition": "recognition_reviews",
            "metadata": "metadata_reviews",
            "metadata_correction": "metadata_corrections",
            "classification": "classification_reviews",
            "conflict": "conflict_confirmations",
        }
        for family in families:
            with self.subTest(family=family), tempfile.TemporaryDirectory() as directory:
                database = self._database(directory)
                with SQLiteTaskRepository(database) as repository:
                    coordinator = PersistentTaskCoordinator(repository, repository)
                    task = coordinator.create("preview", execute_authorized=False)
                    item = coordinator.begin_item(
                        task.task_id,
                        "source",
                        "movies",
                        "Movie.mkv",
                        "Movie.mkv",
                    )
                    evidence = build_pipeline_evidence(task, item, outcome=f"waiting_{family}")
                    table_name = blocker_tables[family]
                    repository._connection.execute(
                        f"""CREATE TEMP TRIGGER fail_{family}
                        BEFORE INSERT ON {table_name}
                        BEGIN SELECT RAISE(ABORT, 'waiting transaction failed'); END"""
                    )
                    with self.assertRaisesRegex(
                        sqlite3.IntegrityError, "waiting transaction failed"
                    ):
                        if family == "recognition":
                            coordinator.wait_for_recognition(
                                item,
                                RecognitionResult(status=RecognitionStatus.UNRECOGNIZED),
                                (RecognitionType("C", "Special"),),
                                evidence=evidence,
                            )
                        elif family == "metadata":
                            coordinator.wait_for_metadata(
                                item,
                                _metadata_waiting_result(),
                                "C",
                                evidence=evidence,
                            )
                        elif family == "metadata_correction":
                            policy = next(
                                value
                                for value in development_strategy_configuration().metadata_policies
                                if value.policy_id == "C"
                            )
                            coordinator.wait_for_metadata_correction(
                                item,
                                _metadata_correction_result(),
                                policy,
                                ParseResult("Missing Movie"),
                                evidence=evidence,
                            )
                        elif family == "classification":
                            result, policy, identity = _classification_waiting_result()
                            coordinator.wait_for_classification(
                                item,
                                result,
                                policy,
                                identity,
                                evidence=evidence,
                            )
                        else:
                            coordinator.wait_for_confirmation(
                                item,
                                _conflicted_plan(),
                                OrganizePolicy(
                                    "A",
                                    OrganizeOperationType.MOVE,
                                    ConflictStrategy.MANUAL,
                                ),
                                evidence=evidence,
                            )
                    self.assertEqual(
                        repository.get_item(item.item_id).status, TaskItemStatus.PROCESSING
                    )
                    self.assertEqual(repository.list_evidence_for_item(item.item_id), ())
                    self.assertEqual(repository.list_recognition_reviews(), ())
                    self.assertEqual(repository.list_metadata_reviews(), ())
                    self.assertEqual(repository.list_metadata_corrections(), ())
                    self.assertEqual(repository.list_classification_reviews(), ())
                    self.assertEqual(repository.list_confirmations(), ())

    def test_waiting_boundaries_reload_full_checkpoint_and_metadata_match_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movie.mkv", "Movie.mkv"
                )
                evidence = build_pipeline_evidence(
                    task,
                    item,
                    strategy=None,
                    outcome="waiting_metadata",
                )
                coordinator.wait_for_metadata(
                    item,
                    _metadata_waiting_result(),
                    "C",
                    evidence=evidence,
                )
                self.assertEqual(
                    repository.get_item(item.item_id).status, TaskItemStatus.WAITING_METADATA
                )
                stored = repository.list_evidence_for_item(item.item_id)
                self.assertEqual(len(stored), 1)
                self.assertEqual(stored[0].outcome, "waiting_metadata")
                checkpoint = coordinator.repository.get_processing_checkpoint_context(item.item_id)
                self.assertIsNotNone(checkpoint)
                self.assertEqual(checkpoint.item.status, TaskItemStatus.WAITING_METADATA)

    def test_production_waiting_paths_capture_evidence_for_each_blocker_family(self) -> None:
        """The MediaOrganizerService must hand captured evidence to every wait coordinator."""

        configuration = development_strategy_configuration()
        recognition = RecognitionType("C", "Special")
        resolved_policy = ResolvedRecognitionPolicy(recognition, "C", "A", "A", "A", "type-C")
        metadata_policy = next(
            value for value in configuration.metadata_policies if value.policy_id == "C"
        )
        classification_result, classification_policy, identity = _classification_waiting_result()
        matched_metadata = MetadataIdentificationResult(
            MetadataIdentificationStatus.MATCHED,
            recognition,
            identity=identity,
        )
        cases = (
            (
                "recognition",
                StrategyTestResult(
                    "Unknown.mkv",
                    ParseResult("Unknown"),
                    RecognitionResult(status=RecognitionStatus.UNRECOGNIZED),
                    None,
                ),
                TaskItemStatus.WAITING_RECOGNITION,
            ),
            (
                "metadata",
                StrategyTestResult(
                    "Movie.mkv",
                    ParseResult("Movie"),
                    RecognitionResult(recognition),
                    resolved_policy,
                    metadata=_metadata_waiting_result(),
                ),
                TaskItemStatus.WAITING_METADATA,
            ),
            (
                "metadata_correction",
                StrategyTestResult(
                    "Missing.mkv",
                    ParseResult("Missing"),
                    RecognitionResult(recognition),
                    resolved_policy,
                    metadata_policy=metadata_policy,
                    metadata=_metadata_correction_result(),
                ),
                TaskItemStatus.WAITING_METADATA_CORRECTION,
            ),
            (
                "classification",
                StrategyTestResult(
                    "Unclassified.mkv",
                    ParseResult("Unclassified"),
                    RecognitionResult(recognition),
                    resolved_policy,
                    metadata=matched_metadata,
                    naming=NamingResult("Unclassified", "Unclassified.mkv"),
                    classification=classification_result,
                ),
                TaskItemStatus.WAITING_CLASSIFICATION,
            ),
        )
        for family, strategy, expected_status in cases:
            with self.subTest(family=family), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                    coordinator = PersistentTaskCoordinator(repository, repository)
                    task = coordinator.create("preview", execute_authorized=False)
                    service = MediaOrganizerService(
                        _StaticStrategy(strategy, classification_policy),
                        None,
                        {},
                        {},
                        configuration.recognition_type_policies,
                        JsonLinesOperationHistoryRepository(root / "history.jsonl"),
                        task_coordinator=coordinator,
                        task_id=task.task_id,
                    )
                    result = service.process_file(
                        strategy.path,
                        resource_library=ResourceLibrary("movies", "Movies", "source", ""),
                        storage_path=strategy.path,
                    )
                    self.assertIsNone(result.error)
                    self.assertIsNotNone(result.evidence)
                    self.assertEqual(result.evidence.outcome, f"waiting_{family}")
                    item = repository.list_items(task.task_id)[0]
                    self.assertEqual(item.status, expected_status)
                    self.assertEqual(len(repository.list_evidence_for_item(item.item_id)), 1)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            source_root.mkdir()
            target_root.mkdir()
            source_storage = LocalStorage("source", source_root)
            target_storage = LocalStorage("target", target_root)
            strategy = StrategyTestResult(
                "Movie.mkv",
                ParseResult("Movie"),
                RecognitionResult(recognition),
                resolved_policy,
                metadata=matched_metadata,
                naming=NamingResult("Movie", "Movie.mkv", policy_id="A", recognition_type_id="C"),
                classification=ClassificationResult(
                    "movies", "Movies", "A", "C", status=ClassificationStatus.CLASSIFIED
                ),
            )
            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                service = MediaOrganizerService(
                    _StaticStrategy(strategy, classification_policy),
                    None,
                    {"source": source_storage, "target": target_storage},
                    {"movies": MediaLibrary("movies", "Movies", "target", "Movies")},
                    configuration.recognition_type_policies,
                    JsonLinesOperationHistoryRepository(root / "history.jsonl"),
                    task_coordinator=coordinator,
                    task_id=task.task_id,
                )
                with (
                    patch(
                        "mediaflow.application.media_organizer.OrganizePlanner.plan",
                        return_value=_conflicted_plan(),
                    ),
                    patch(
                        "mediaflow.application.media_organizer.apply_hash_duplicate_detection",
                        side_effect=lambda plan, *args, **kwargs: plan,
                    ),
                ):
                    result = service.process_file(
                        strategy.path,
                        resource_library=ResourceLibrary("movies", "Movies", "source", ""),
                        storage_path=strategy.path,
                    )
                self.assertIsNone(result.error)
                self.assertIsNotNone(result.evidence)
                self.assertEqual(result.evidence.outcome, "waiting_confirm")
                item = repository.list_items(task.task_id)[0]
                self.assertEqual(item.status, TaskItemStatus.WAITING_CONFIRM)
                self.assertEqual(len(repository.list_confirmations()), 1)
                self.assertEqual(len(repository.list_evidence_for_item(item.item_id)), 1)

    def test_metadata_evidence_persists_bounded_matcher_explanation(self) -> None:
        recognition = RecognitionType("C", "Special")
        metadata = _metadata_waiting_result()
        strategy = type(
            "Strategy",
            (),
            {
                "parsed": ParseResult("Movie", year=2024),
                "recognition": RecognitionResult(
                    recognition,
                    status=RecognitionStatus.MATCHED,
                ),
                "metadata": metadata,
                "policy": ResolvedRecognitionPolicy(recognition, "C", "A", "A", "A", "C"),
                "naming": None,
                "naming_error": None,
                "classification": None,
                "classification_error": None,
            },
        )()
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(self._database(directory)) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movie.mkv", "Movie.mkv"
                )
                evidence = build_pipeline_evidence(task, item, strategy=strategy)
                document = evidence.section("metadata").document()
                candidate = document["items"][0]
                self.assertEqual(candidate["matchedLocalTitle"], "Movie")
                self.assertEqual(candidate["matchedProviderTitle"], "Movie")
                self.assertEqual(candidate["matchedTitleSource"], "title")
                self.assertEqual(candidate["scoreComponents"][0]["name"], "title")
                self.assertEqual(candidate["scoreComponents"][0]["score"], 65)
                self.assertNotIn("overview", json.dumps(evidence.document()))
                self.assertNotIn("secret", json.dumps(evidence.document()).lower())

    def test_file_detail_bounds_history_and_projects_effects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert((file_record("one", "source", "movies", "Movie.mkv"),))
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movie.mkv", "Movie.mkv"
                )
                for attempt in range(33):
                    repository.append_evidence(
                        build_pipeline_evidence(
                            task,
                            replace(item, attempts=attempt),
                            outcome="partial" if attempt == 0 else "success",
                            error="api_key=do-not-persist" if attempt == 0 else None,
                            captured_at=NOW.replace(minute=attempt % 60),
                        )
                    )
                repository.append_result(
                    PersistentResultRecord(
                        "result-effects",
                        task.task_id,
                        item.item_id,
                        "source",
                        "Movie.mkv",
                        "target",
                        "Movies/Movie.mkv",
                        "C",
                        "tmdb",
                        "129",
                        "C",
                        "A",
                        "A",
                        "A",
                        "move",
                        "partial",
                        NOW,
                        title="Movie",
                        completed_operations=("create_directory", "move"),
                        effect_certainty="attempted_unverified",
                        uncertain_effects=("target effect",),
                        error="partial transfer",
                    )
                )
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as repository,
            ):
                detail = FileCatalogService(
                    index,
                    ("movies",),
                    ("source",),
                    task_repository=repository,
                ).detail("one")
                self.assertEqual(len(detail.evidence), 32)
                self.assertTrue(detail.truncated["evidence"])
                self.assertEqual(
                    detail.results[0].completed_operations, ("create_directory", "move")
                )
                self.assertEqual(detail.results[0].effect_certainty, "attempted_unverified")
                self.assertEqual(detail.results[0].uncertain_effects, ("target effect",))
                rendered = json.dumps(detail.evidence[0].document())
                self.assertNotIn("do-not-persist", rendered)

    def test_legacy_detail_marks_unavailable_and_never_reconstructs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert((file_record("one", "source", "movies", "Movies/A.mkv"),))
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                repository.upsert_item(
                    PersistentTaskItem(
                        item.item_id,
                        task.task_id,
                        "source",
                        "movies",
                        "Movies/A.mkv",
                        "Movies/A.mkv",
                        TaskItemStatus.DRY_RUN,
                        "completed",
                        item.attempts,
                        item.created_at,
                        NOW,
                        plan_id="plan-1",
                    )
                )
                repository.append_result(
                    PersistentResultRecord(
                        "result-1",
                        task.task_id,
                        item.item_id,
                        "source",
                        "Movies/A.mkv",
                        "target",
                        "Movies/A.mkv",
                        "C",
                        "tmdb",
                        "129",
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
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as repository,
            ):
                service = FileCatalogService(
                    index,
                    ("movies",),
                    ("source",),
                    task_repository=repository,
                )
                detail = service.detail("one")
                self.assertEqual(detail.evidence, ())
                self.assertEqual(detail.truncated["evidence"], False)
                self.assertEqual(len(detail.items), 1)
                self.assertEqual(detail.items[0].status, "dry_run")
                self.assertEqual(len(detail.results), 1)
                self.assertEqual(detail.actions, ())

    def test_real_dryrun_capture_persists_type_c_and_downstream_policy_a(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
            tempfile.TemporaryDirectory() as state_root,
        ):
            source_path = Path(source_root, "Movie.2024.mkv")
            source_path.write_bytes(b"movie")
            source_storage = LocalStorage("source", source_root)
            target_storage = LocalStorage("target", target_root)
            storages = {"source": source_storage, "target": target_storage}
            configuration = development_strategy_configuration()
            provider = SyntheticMetadataProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "129",
                        MediaType.MOVIE,
                        "Movie",
                        year=2024,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )
            )
            database = Path(state_root, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create(
                    "preview",
                    execute_authorized=False,
                    configuration_snapshot_id="revision-1",
                    configuration_snapshot_digest="digest-1",
                )
                service = MediaOrganizerService(
                    strategy_runner_from_configuration(
                        configuration, MetadataProviderRegistry((provider,))
                    ),
                    None,
                    storages,
                    {"movies": MediaLibrary("movies", "Movies", "target", "Movies")},
                    configuration.recognition_type_policies,
                    JsonLinesOperationHistoryRepository(Path(state_root, "history.jsonl")),
                    source_display_roots={"movies": source_root},
                    task_coordinator=coordinator,
                    task_id=task.task_id,
                )
                library = ResourceLibrary("special", "Special", "source", "")
                processed = service.process_file(
                    source_path.as_posix(),
                    resource_library=library,
                    storage_path=source_path.name,
                )
                self.assertIsNotNone(processed.evidence)
                self.assertEqual(processed.execution.status.value, "DRY_RUN")
                evidence = repository.list_evidence_for_item(processed.evidence.item_id)
                self.assertEqual(len(evidence), 1)
                record = evidence[0]
                self.assertEqual(record.outcome, "dry_run")
                self.assertEqual(record.section("policies").value["recognitionTypeId"], "C")
                self.assertEqual(record.section("policies").value["namingPolicyId"], "A")
                self.assertEqual(record.section("policies").value["classificationPolicyId"], "A")
                self.assertEqual(record.section("policies").value["organizePolicyId"], "A")
                self.assertEqual(record.section("recognition").value["recognitionTypeId"], "C")
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert((file_record("one", "source", "special", source_path.name),))
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as repository,
            ):
                service = FileCatalogService(
                    index,
                    ("special",),
                    ("source",),
                    task_repository=repository,
                )
                detail = service.detail("one")
                self.assertEqual(len(detail.evidence), 1)
                policies = detail.evidence[0].section("policies").value
                self.assertEqual(policies["recognitionTypeId"], "C")
                self.assertEqual(policies["namingPolicyId"], "A")
                self.assertEqual(policies["classificationPolicyId"], "A")
                self.assertEqual(policies["organizePolicyId"], "A")

    def test_waiting_evidence_and_reload_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                evidence = build_pipeline_evidence(task, item, outcome="waiting_recognition")
                repository.append_evidence(evidence)
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert((file_record("one", "source", "movies", "Movies/A.mkv"),))
            with SQLiteTaskRepository(database) as reopened:
                values = reopened.list_evidence_for_item(item.item_id)
                self.assertEqual(len(values), 1)
                self.assertEqual(values[0].outcome, "waiting_recognition")
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as reopened,
            ):
                service = FileCatalogService(
                    index,
                    ("movies",),
                    ("source",),
                    task_repository=reopened,
                )
                detail = service.detail("one")
                self.assertEqual(detail.evidence[0].outcome, "waiting_recognition")
                self.assertEqual(detail.evidence[0].document(), values[0].document())

    def test_detail_reads_create_no_provider_storage_queue_or_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert((file_record("one", "source", "movies", "Movies/A.mkv"),))
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                repository.append_evidence(
                    build_pipeline_evidence(task, item, outcome="processing")
                )
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as repository,
            ):
                service = FileCatalogService(
                    index,
                    ("movies",),
                    ("source",),
                    task_repository=repository,
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                    file_catalog=service,
                )
                with (
                    patch(
                        "mediaflow.application.metadata.MetadataIdentificationService",
                        side_effect=AssertionError("detail must not construct providers"),
                    ),
                    patch.object(
                        LocalStorage,
                        "list",
                        side_effect=AssertionError("detail must not list Storage"),
                    ),
                    patch.object(
                        LocalStorage,
                        "stat",
                        side_effect=AssertionError("detail must not stat Storage"),
                    ),
                    patch.object(
                        LocalStorage,
                        "exists",
                        side_effect=AssertionError("detail must not probe Storage"),
                    ),
                    patch.object(
                        LocalStorage,
                        "read",
                        side_effect=AssertionError("detail must not read Storage"),
                    ),
                    patch.object(
                        LocalStorage,
                        "write",
                        side_effect=AssertionError("detail must not write Storage"),
                    ),
                    patch.object(
                        LocalStorage,
                        "move",
                        side_effect=AssertionError("detail must not move Storage"),
                    ),
                    patch.object(
                        LocalStorage,
                        "copy",
                        side_effect=AssertionError("detail must not copy Storage"),
                    ),
                    patch.object(
                        LocalStorage,
                        "delete",
                        side_effect=AssertionError("detail must not delete Storage"),
                    ),
                    patch.object(
                        LocalStorage,
                        "create_directory",
                        side_effect=AssertionError("detail must not create Storage directories"),
                    ),
                    patch.object(
                        LocalStorage,
                        "hard_link",
                        side_effect=AssertionError("detail must not hard-link Storage"),
                    ),
                    patch.object(
                        LocalStorage,
                        "soft_link",
                        side_effect=AssertionError("detail must not soft-link Storage"),
                    ),
                    patch.object(
                        SQLiteTaskRepository,
                        "append_security_audit",
                        side_effect=AssertionError("detail must not audit"),
                    ),
                    patch.object(
                        SQLiteTaskRepository,
                        "create_task",
                        side_effect=AssertionError("detail must not create a Task"),
                    ),
                    patch.object(
                        SQLiteTaskRepository,
                        "create_job",
                        side_effect=AssertionError("detail must not create a Job"),
                    ),
                    patch.object(
                        SQLiteTaskRepository,
                        "create_execution_authorization",
                        side_effect=AssertionError("detail must not create authorization"),
                    ),
                ):
                    status, document = api_request(api, "/api/v1/files/one")
                self.assertEqual(status, 200)
                self.assertEqual(document["evidence"][0]["outcome"], "processing")
                self.assertEqual(repository.list_security_audit(), ())
                self.assertIn("Captured pipeline evidence", APP_JS.decode())
                self.assertIn("/api/v1/files/by-source", APP_JS.decode())
                self.assertIn("renderFileMediaSections", APP_JS.decode())
                self.assertIn("showTaskItem(item.taskId, item.itemId)", APP_JS.decode())
                self.assertIn("checkpoint.audits", APP_JS.decode())
                self.assertIn("completedOperations", APP_JS.decode())
                self.assertIn("recognition-reviews", APP_JS.decode())
                self.assertIn("metadata-corrections", APP_JS.decode())

    def test_rbac_denies_read_and_read_only_cannot_invoke_write_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert((file_record("one", "source", "movies", "Movies/A.mkv"),))
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                repository.append_evidence(
                    build_pipeline_evidence(task, item, outcome="failed", error="failed")
                )
                repository.upsert_item(
                    PersistentTaskItem(
                        item.item_id,
                        task.task_id,
                        "source",
                        "movies",
                        "Movies/A.mkv",
                        "Movies/A.mkv",
                        TaskItemStatus.FAILED,
                        "failed",
                        item.attempts,
                        item.created_at,
                        NOW,
                        error="failed",
                    )
                )
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as repository,
            ):
                service = FileCatalogService(
                    index,
                    ("movies",),
                    ("source",),
                    task_repository=repository,
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                    file_catalog=service,
                )
                status, _ = api_request(api, "/api/v1/files/one", token=None)
                self.assertEqual(status, 401)
                status, document = api_request(api, "/api/v1/files/one/re-plan", method="POST")
                self.assertEqual(status, 403)
                self.assertEqual(document["error"]["code"], "forbidden")

    def test_by_source_resolves_unique_and_explains_missing_or_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteFileIndexRepository(database) as index:
                index.batch_upsert(
                    (
                        file_record("one", "source", "movies", "Movies/A.mkv"),
                        file_record("two", "source", "archive", "Movies/A.mkv"),
                    )
                )
            with (
                SQLiteFileIndexRepository(database) as index,
                SQLiteTaskRepository(database) as repository,
            ):
                service = FileCatalogService(
                    index,
                    ("movies", "archive"),
                    ("source",),
                    task_repository=repository,
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                    file_catalog=service,
                )
                status, document = api_request(api, "/api/v1/files/by-source", query="")
                self.assertEqual(status, 400)
                status, document = api_request(
                    api,
                    "/api/v1/files/by-source",
                    query="storageId=source&path=Movies%2FA.mkv",
                )
                self.assertEqual(status, 200)
                self.assertFalse(document["available"])
                self.assertIn("ambiguous", document["unavailableReason"])
                status, document = api_request(
                    api,
                    "/api/v1/files/by-source",
                    query="storageId=source&path=Movies%2FA.mkv&resourceLibrary=movies",
                )
                self.assertEqual(status, 200)
                self.assertTrue(document["available"])
                self.assertEqual(document["fileId"], "one")
                status, document = api_request(
                    api,
                    "/api/v1/files/by-source",
                    query="storageId=source&path=Missing.mkv&resourceLibrary=movies",
                )
                self.assertEqual(status, 200)
                self.assertFalse(document["available"])
                self.assertIn("no current indexed", document["unavailableReason"])

    def test_review_queues_expose_source_links_for_all_blocker_families(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                recognition_item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Recognition.mkv", "Recognition.mkv"
                )
                RecognitionReviewService(repository, (RecognitionType("C", "Special"),)).create(
                    recognition_item,
                    RecognitionResult(status=RecognitionStatus.UNRECOGNIZED),
                )
                correction_item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Correction.mkv", "Correction.mkv"
                )
                policy = next(
                    value
                    for value in development_strategy_configuration().metadata_policies
                    if value.policy_id == "C"
                )
                MetadataCorrectionService(repository, (policy,)).create(
                    correction_item,
                    _metadata_correction_result(),
                    policy,
                    ParseResult("Correction"),
                )
            with SQLiteTaskRepository(database) as repository:
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                )
                status, recognition = api_request(api, "/api/v1/recognition-reviews")
                self.assertEqual(status, 200)
                self.assertEqual(recognition["items"][0]["source_path"], "Recognition.mkv")
                status, correction = api_request(api, "/api/v1/metadata-corrections")
                self.assertEqual(status, 200)
                self.assertEqual(correction["items"][0]["source_path"], "Correction.mkv")

    def test_complete_item_evidence_write_rolls_back_result_and_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                completed = PersistentTaskItem(
                    item.item_id,
                    task.task_id,
                    "source",
                    "movies",
                    "Movies/A.mkv",
                    "Movies/A.mkv",
                    TaskItemStatus.SUCCESS,
                    "completed",
                    item.attempts,
                    item.created_at,
                    NOW,
                )
                result = PersistentResultRecord(
                    "result-1",
                    task.task_id,
                    item.item_id,
                    "source",
                    "Movies/A.mkv",
                    "target",
                    "Movies/A.mkv",
                    "C",
                    "tmdb",
                    "129",
                    "C",
                    "A",
                    "A",
                    "A",
                    "move",
                    "success",
                    NOW,
                )
                evidence = build_pipeline_evidence(task, item, outcome="success")
                with patch.object(
                    SQLiteTaskRepository,
                    "_evidence_values",
                    side_effect=RuntimeError("evidence persistence failed"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "evidence persistence failed"):
                        repository.complete_item_with_evidence(completed, result, evidence)
                persisted = repository.get_item(item.item_id)
                self.assertIsNotNone(persisted)
                self.assertEqual(persisted.status, TaskItemStatus.PROCESSING)
                self.assertEqual(repository.list_results_for_item(item.item_id), ())
                self.assertEqual(repository.list_evidence_for_item(item.item_id), ())

    def test_old_schema_26_migrates_without_losing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = self._database(directory)
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.record_discovered(
                    task.task_id, "source", "movies", "Movies/A.mkv", "Movies/A.mkv"
                )
                repository.append_result(
                    PersistentResultRecord(
                        "legacy-result",
                        task.task_id,
                        item.item_id,
                        "source",
                        "Movies/A.mkv",
                        None,
                        None,
                        "C",
                        "tmdb",
                        "129",
                        "C",
                        "A",
                        "A",
                        "A",
                        "move",
                        "dry_run",
                        NOW,
                    )
                )
            connection = sqlite3.connect(database)
            connection.execute("UPDATE schema_version SET version=26 WHERE component='runtime'")
            connection.execute("DROP TABLE pipeline_evidence")
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.schema_version, SCHEMA_VERSION)
                self.assertEqual(reopened.list_items(task.task_id)[0].item_id, item.item_id)
                self.assertEqual(reopened.list_results(task.task_id)[0].result_id, "legacy-result")
                self.assertEqual(reopened.list_evidence_for_item(item.item_id), ())


if __name__ == "__main__":
    unittest.main()
