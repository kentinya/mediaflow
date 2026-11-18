from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_ignore import ManualIgnoreService
from mediaflow.application.media_organizer import MediaOrganizerBatchResult
from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.application.metadata_review import MetadataReviewService
from mediaflow.application.recognition_review import RecognitionReviewService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.metadata import MetadataIdentificationStatus
from mediaflow.domain.metadata_correction import MetadataCorrectionStatus
from mediaflow.domain.metadata_review import MetadataReviewStatus
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.recognition import RecognitionResult, RecognitionStatus
from mediaflow.domain.recognition_review import RecognitionReviewStatus
from mediaflow.domain.recovery import RecoveryAdmissionError, RecoveryAdmissionReason
from mediaflow.domain.task_persistence import PersistentTaskStatus, TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from tests.test_metadata_review import identification

SNAPSHOT_ID = "test-recovery-revision"
SNAPSHOT_DIGEST = "a" * 64


class ManualIgnoreBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = development_strategy_configuration()

    @staticmethod
    def _snapshot_validator(snapshot_id: str, digest: str) -> None:
        if snapshot_id != SNAPSHOT_ID or digest != SNAPSHOT_DIGEST:
            raise ValueError("snapshot unavailable")

    def _service(self, repository):
        return ManualIgnoreService(repository, snapshot_validator=self._snapshot_validator)

    def _create_waiting(
        self,
        repository,
        kind,
        number=1,
        task=None,
        *,
        snapshot_id: str = SNAPSHOT_ID,
        snapshot_digest: str = SNAPSHOT_DIGEST,
    ):
        coordinator = PersistentTaskCoordinator(repository, repository)
        if task is None:
            task = coordinator.create(
                "organize",
                execute_authorized=False,
                configuration_snapshot_id=snapshot_id,
                configuration_snapshot_digest=snapshot_digest,
            )
        item = coordinator.begin_item(
            task.task_id, "source", "movies", f"Movie-{number}.mkv", f"Movie-{number}.mkv"
        )
        if kind == "recognition":
            review = RecognitionReviewService(repository, self.strategy.recognition_types).create(
                item, RecognitionResult(status=RecognitionStatus.UNRECOGNIZED)
            )
        elif kind == "metadata":
            review = MetadataReviewService(repository).create(item, identification(), "C")
        else:
            policy = next(
                value for value in self.strategy.metadata_policies if value.policy_id == "A"
            )
            review = MetadataCorrectionService(repository, self.strategy.metadata_policies).create(
                item,
                identification(MetadataIdentificationStatus.NOT_FOUND, count=0),
                policy,
                ParseResult("Unknown", year=2025),
            )
        return coordinator, task, item, review

    @staticmethod
    def _activate_document(database: Path, document: dict) -> object:
        with SQLiteConfigurationRepository(database) as repository:
            service = ManagedConfigurationService(repository)
            draft = service.import_draft(document, actor="tester")
            validated = service.validate(draft.revision_id, actor="tester")
            return service.activate(
                validated.revision_id,
                expected_version=validated.version,
                actor="tester",
            )

    def test_pending_ignore_admits_each_supported_kind_and_settles_the_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create(
                    "organize",
                    execute_authorized=False,
                    configuration_snapshot_id=SNAPSHOT_ID,
                    configuration_snapshot_digest=SNAPSHOT_DIGEST,
                )
                recognition = self._create_waiting(repository, "recognition", number=1, task=task)
                metadata = self._create_waiting(repository, "metadata", number=2, task=task)
                correction = self._create_waiting(
                    repository, "metadata_correction", number=3, task=task
                )
                decisions = self._service(repository).ignore_pending(
                    actor=" operator ",
                    note=" intentionally ignored ",
                    limit=3,
                )
                self.assertEqual(
                    [decision.review_kind.value for decision in decisions],
                    ["recognition", "metadata", "metadata_correction"],
                )
                self.assertEqual(decisions[0].actor, "operator")
                for kind, value in (
                    ("recognition", recognition),
                    ("metadata", metadata),
                    ("metadata_correction", correction),
                ):
                    _, _, item, review = value
                    self.assertEqual(
                        repository.get_item(item.item_id).status, TaskItemStatus.IGNORED
                    )
                    self.assertEqual(
                        repository.list_manual_ignore_audit(item.item_id)[0].note,
                        "intentionally ignored",
                    )
                    self.assertEqual(
                        len(repository.list_recovery_requests(item.item_id)),
                        1,
                    )
                    if kind == "recognition":
                        self.assertEqual(
                            repository.get_recognition_review(review.review_id).status,
                            RecognitionReviewStatus.IGNORED,
                        )
                    elif kind == "metadata":
                        self.assertEqual(
                            repository.get_metadata_review(review.review_id).status,
                            MetadataReviewStatus.IGNORED,
                        )
                    else:
                        self.assertEqual(
                            repository.get_metadata_correction(review.review_id).status,
                            MetadataCorrectionStatus.IGNORED,
                        )
                self.assertEqual(coordinator.retryable_items(task.task_id, failed_only=False), ())
                summary = coordinator.finish(task.task_id, MediaOrganizerBatchResult(()))
                self.assertEqual(summary.status, PersistentTaskStatus.COMPLETED)
                # Slice 48 RO-3: every ignored item is ended progress.
                self.assertEqual(summary.completed_items, 3)
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)

    def test_limit_and_task_filter_select_only_selected_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                first_task = coordinator.create(
                    "organize",
                    execute_authorized=False,
                    configuration_snapshot_id=SNAPSHOT_ID,
                    configuration_snapshot_digest=SNAPSHOT_DIGEST,
                )
                second_task = coordinator.create(
                    "organize",
                    execute_authorized=False,
                    configuration_snapshot_id=SNAPSHOT_ID,
                    configuration_snapshot_digest=SNAPSHOT_DIGEST,
                )
                first_recognition = self._create_waiting(
                    repository, "recognition", number=1, task=first_task
                )
                first_metadata = self._create_waiting(
                    repository, "metadata", number=2, task=first_task
                )
                second_recognition = self._create_waiting(
                    repository, "recognition", number=3, task=second_task
                )
                decisions = self._service(repository).ignore_pending(
                    actor="operator",
                    limit=2,
                    task_id=first_task.task_id,
                )
                self.assertEqual(
                    {decision.review_id for decision in decisions},
                    {first_recognition[3].review_id, first_metadata[3].review_id},
                )
                self.assertEqual(
                    repository.get_item(first_recognition[2].item_id).status,
                    TaskItemStatus.IGNORED,
                )
                self.assertEqual(
                    repository.get_item(first_metadata[2].item_id).status,
                    TaskItemStatus.IGNORED,
                )
                self.assertEqual(
                    repository.get_item(second_recognition[2].item_id).status,
                    TaskItemStatus.WAITING_RECOGNITION,
                )

    def test_invalid_actor_limits_empty_selection_and_missing_task_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                self._create_waiting(repository, "recognition")
                service = self._service(repository)
                with self.assertRaisesRegex(ValueError, "actor"):
                    service.ignore_pending(actor="   ")
                for limit in (0, -1, 101, True):
                    with self.subTest(limit=limit):
                        with self.assertRaisesRegex(ValueError, "limit"):
                            service.ignore_pending(actor="operator", limit=limit)
                with self.assertRaisesRegex(ValueError, "no pending"):
                    service.ignore_pending(actor="operator", task_id="missing")

    def test_each_item_is_atomic_and_later_failure_preserves_earlier_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create(
                    "organize",
                    execute_authorized=False,
                    configuration_snapshot_id=SNAPSHOT_ID,
                    configuration_snapshot_digest=SNAPSHOT_DIGEST,
                )
                first = self._create_waiting(repository, "recognition", number=1, task=task)
                second = self._create_waiting(repository, "metadata", number=2, task=task)
                third = self._create_waiting(repository, "metadata_correction", number=3, task=task)
            second_item = second[2]
            connection = sqlite3.connect(database)
            connection.execute(
                f"""CREATE TRIGGER reject_second_ignore BEFORE INSERT ON manual_ignore_audit
                WHEN NEW.item_id = '{second_item.item_id}'
                BEGIN SELECT RAISE(ABORT, 'injected'); END"""
            )
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                with self.assertRaises(sqlite3.IntegrityError):
                    self._service(repository).ignore_pending(actor="operator", limit=3)
                self.assertEqual(
                    repository.get_item(first[2].item_id).status, TaskItemStatus.IGNORED
                )
                self.assertEqual(
                    repository.get_item(second_item.item_id).status,
                    TaskItemStatus.WAITING_METADATA,
                )
                self.assertEqual(
                    repository.get_item(third[2].item_id).status,
                    TaskItemStatus.WAITING_METADATA_CORRECTION,
                )
                self.assertEqual(
                    repository.get_metadata_review(second[3].review_id).status,
                    MetadataReviewStatus.PENDING,
                )
                self.assertEqual(
                    repository.list_manual_ignore_audit(first[2].item_id)[0].actor, "operator"
                )
                self.assertEqual(repository.list_manual_ignore_audit(second_item.item_id), ())

    def test_without_admission_service_no_direct_ignore_write_occurs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                _, _, item, review = self._create_waiting(repository, "recognition")
                with self.assertRaises(RecoveryAdmissionError) as raised:
                    ManualIgnoreService(repository).ignore_pending(actor="operator", limit=1)
                self.assertEqual(
                    raised.exception.reason, RecoveryAdmissionReason.SNAPSHOT_UNAVAILABLE
                )
                self.assertEqual(
                    repository.get_item(item.item_id).status, TaskItemStatus.WAITING_RECOGNITION
                )
                self.assertEqual(
                    repository.get_recognition_review(review.review_id).status,
                    RecognitionReviewStatus.PENDING,
                )
                self.assertEqual(repository.list_manual_ignore_audit(item.item_id), ())

    def test_retired_direct_ignore_transports_are_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self._service(repository)
                self.assertFalse(hasattr(service, "_legacy_ignore"))
                self.assertFalse(hasattr(service, "_pending_review"))
                self.assertFalse(hasattr(repository, "ignore_waiting_item"))
                self.assertFalse(hasattr(repository, "ignore_waiting_items"))
        from mediaflow.domain import manual_ignore

        self.assertFalse(hasattr(manual_ignore, "ManualIgnoreBatchRequest"))
        self.assertTrue(hasattr(manual_ignore, "ManualIgnoreCandidate"))

    def test_cli_batch_ignore_uses_persistent_admission_without_storage_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(database)
            config_path = root / "strategy.json"
            config_path.write_text(json.dumps(document), encoding="utf-8")
            active = self._activate_document(database, document)
            with SQLiteTaskRepository(database) as repository:
                _, task, item, review = self._create_waiting(
                    repository,
                    "recognition",
                    snapshot_id=active.revision_id,
                    snapshot_digest=active.digest,
                )
            output, error = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("batch ignore constructed Storage"),
            ):
                code = final_main(
                    [
                        "--config",
                        str(config_path),
                        "tasks",
                        "ignore-pending",
                        "--actor",
                        "operator",
                        "--limit",
                        "1",
                    ],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("BATCH MANUAL IGNORE", output.getvalue())
            self.assertIn("Ignored: 1", output.getvalue())
            self.assertIn("Media mutation: 0", output.getvalue())
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(
                    repository.get_recognition_review(review.review_id).status,
                    RecognitionReviewStatus.IGNORED,
                )
                self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.IGNORED)
                self.assertEqual(len(repository.list_recovery_requests(item.item_id)), 1)


if __name__ == "__main__":
    unittest.main()
