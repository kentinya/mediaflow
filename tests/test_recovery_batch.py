from __future__ import annotations

import tempfile
import unittest

from mediaflow.application.automation import AutomationJobService
from mediaflow.application.recovery_batch import RecoveryBatchContinuationService
from mediaflow.application.recovery_continuation import RecoveryContinuationService
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.recovery_batch import RecoveryBatchItemStatus
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from tests.test_recovery_continuation import (
    DetailCountingProvider,
    api_request,
)
from tests.test_recovery_continuation import (
    RecoveryContinuationTests as _RecoveryContinuationTests,
)


class RecoveryBatchTests(unittest.TestCase):
    def test_mixed_selection_preserves_refusal_and_admits_valid_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _RecoveryContinuationTests()
            environment = helper._environment(directory)
            source_task, source_item = helper._seed_failed_item(environment)
            admitted, _ = helper._admit(environment, source_task, source_item)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation_service = RecoveryContinuationService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                )
                checkpoint = continuation_service.checkpoint_service.get(source_item.item_id)
                service = RecoveryBatchContinuationService(
                    repository,
                    continuation_service=continuation_service,
                )
                batch = service.submit(
                    source_task.task_id,
                    [
                        {
                            "itemId": source_item.item_id,
                            "expectedCheckpointVersion": checkpoint.checkpoint_version,
                        },
                        {
                            "itemId": "missing-item",
                            "expectedCheckpointVersion": checkpoint.checkpoint_version,
                        },
                    ],
                    actor="operator",
                    maximum_active_jobs=100,
                )
            self.assertEqual(batch.selected_count, 2)
            statuses = {item.source_item_id: item.status for item in batch.items}
            self.assertEqual(statuses[source_item.item_id], RecoveryBatchItemStatus.QUEUED)
            self.assertEqual(statuses["missing-item"], RecoveryBatchItemStatus.REFUSED)
            self.assertEqual(batch.unchanged_count, 1)
            self.assertEqual(admitted.item_id, source_item.item_id)

    def test_api_batch_submission_and_task_reload_expose_parent_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _RecoveryContinuationTests()
            environment = helper._environment(directory)
            source_task, source_item = helper._seed_failed_item(environment)
            helper._admit(environment, source_task, source_item)
            api = helper._api(environment)
            status, checkpoint = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}",
            )
            self.assertEqual(status, 200)
            status, document = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/recovery/continue-batch",
                method="POST",
                body={
                    "items": [
                        {
                            "itemId": source_item.item_id,
                            "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                        }
                    ]
                },
            )
            self.assertEqual(status, 202)
            self.assertEqual(document["selected_count"], 1)
            self.assertEqual(document["counts"]["queued"], 1)
            status, detail = api_request(api, f"/api/v1/tasks/{source_task.task_id}")
            self.assertEqual(status, 200)
            self.assertEqual(len(detail["recovery_batches"]), 1)
            self.assertEqual(detail["recovery_batches"][0]["batch_id"], document["batch_id"])

    def test_batch_bound_and_duplicate_selection_fail_closed_without_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _RecoveryContinuationTests()
            environment = helper._environment(directory)
            source_task, source_item = helper._seed_failed_item(environment)
            helper._admit(environment, source_task, source_item)
            with SQLiteTaskRepository(environment["database"]) as repository:
                service = RecoveryBatchContinuationService(repository)
                checkpoint = RecoveryContinuationService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                ).checkpoint_service.get(source_item.item_id)
                with self.assertRaises(ValueError):
                    service.submit(
                        source_task.task_id,
                        [
                            {
                                "itemId": source_item.item_id,
                                "expectedCheckpointVersion": checkpoint.checkpoint_version,
                            }
                        ]
                        * 101,
                        actor="operator",
                        maximum_active_jobs=100,
                    )
                with self.assertRaises(ValueError):
                    service.submit(
                        source_task.task_id,
                        [
                            {
                                "itemId": source_item.item_id,
                                "expectedCheckpointVersion": checkpoint.checkpoint_version,
                            }
                        ]
                        * 2,
                        actor="operator",
                        maximum_active_jobs=100,
                    )
                self.assertEqual(repository.list_recovery_batches(source_task.task_id), ())

    def test_child_terminal_status_is_reflected_after_reload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _RecoveryContinuationTests()
            environment = helper._environment(directory)
            source_task, source_item = helper._seed_failed_item(environment)
            helper._admit(environment, source_task, source_item)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation_service = RecoveryContinuationService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                )
                service = RecoveryBatchContinuationService(
                    repository,
                    continuation_service=continuation_service,
                )
                checkpoint = continuation_service.checkpoint_service.get(source_item.item_id)
                batch = service.submit(
                    source_task.task_id,
                    [
                        {
                            "itemId": source_item.item_id,
                            "expectedCheckpointVersion": checkpoint.checkpoint_version,
                        }
                    ],
                    actor="operator",
                    maximum_active_jobs=100,
                )
                self.assertEqual(batch.items[0].status, RecoveryBatchItemStatus.QUEUED)
                job_id = batch.items[0].job_id
                AutomationJobService(repository).cancel(job_id)
                reloaded = repository.get_recovery_batch(batch.batch_id)
                self.assertEqual(reloaded.items[0].status, RecoveryBatchItemStatus.CANCELLED)
                self.assertEqual(reloaded.status.value, "cancelled")

    def test_uncertain_item_is_refused_and_does_not_create_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _RecoveryContinuationTests()
            environment = helper._environment(directory)
            source_task, source_item = helper._seed_failed_item(
                environment,
                source_path="Media/C/Partial.mkv",
                certainty="attempted_unverified",
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                checkpoint = RecoveryContinuationService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                ).checkpoint_service.get(source_item.item_id)
                batch = RecoveryBatchContinuationService(
                    repository,
                    continuation_service=RecoveryContinuationService(
                        repository,
                        snapshot_validator=lambda _id, _digest: None,
                    ),
                ).submit(
                    source_task.task_id,
                    [
                        {
                            "itemId": source_item.item_id,
                            "expectedCheckpointVersion": checkpoint.checkpoint_version,
                        }
                    ],
                    actor="operator",
                    maximum_active_jobs=100,
                )
                self.assertEqual(batch.items[0].status, RecoveryBatchItemStatus.REFUSED)
                self.assertEqual(batch.items[0].reason, "uncertain_effects")
                self.assertEqual(
                    repository.list_recovery_continuations(source_item.item_id),
                    (),
                )

    def test_queue_capacity_is_recorded_per_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _RecoveryContinuationTests()
            environment = helper._environment(directory)
            source_task, source_item = helper._seed_failed_item(environment)
            helper._admit(environment, source_task, source_item)
            with SQLiteTaskRepository(environment["database"]) as repository:
                checkpoint = RecoveryContinuationService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                ).checkpoint_service.get(source_item.item_id)
                filler = AutomationJobService(
                    repository,
                    maximum_active_jobs=1,
                    configuration_snapshot_id=environment["snapshot"][0],
                    configuration_snapshot_digest=environment["snapshot"][1],
                ).submit("preview", limit=1)
                batch = RecoveryBatchContinuationService(
                    repository,
                    continuation_service=RecoveryContinuationService(
                        repository,
                        snapshot_validator=lambda _id, _digest: None,
                    ),
                ).submit(
                    source_task.task_id,
                    [
                        {
                            "itemId": source_item.item_id,
                            "expectedCheckpointVersion": checkpoint.checkpoint_version,
                        }
                    ],
                    actor="operator",
                    maximum_active_jobs=1,
                )
                self.assertEqual(batch.items[0].status, RecoveryBatchItemStatus.WAITING)
                self.assertEqual(batch.items[0].reason, "queue_full")
                self.assertIsNone(batch.items[0].continuation_id)
                AutomationJobService(repository).cancel(filler.job_id)

    def test_worker_completes_child_and_parent_summary_after_reload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _RecoveryContinuationTests()
            environment = helper._environment(directory)
            source_task, source_item = helper._seed_failed_item(environment)
            helper._admit(environment, source_task, source_item)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation_service = RecoveryContinuationService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                )
                checkpoint = continuation_service.checkpoint_service.get(source_item.item_id)
                batch = RecoveryBatchContinuationService(
                    repository,
                    continuation_service=continuation_service,
                ).submit(
                    source_task.task_id,
                    [
                        {
                            "itemId": source_item.item_id,
                            "expectedCheckpointVersion": checkpoint.checkpoint_version,
                        }
                    ],
                    actor="operator",
                    maximum_active_jobs=100,
                )
            helper._run_worker(
                environment,
                DetailCountingProvider(
                    candidates=(
                        MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),
                    )
                ),
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                reloaded = repository.get_recovery_batch(batch.batch_id)
                self.assertEqual(reloaded.items[0].status, RecoveryBatchItemStatus.COMPLETED)
                self.assertEqual(reloaded.status.value, "completed")
                self.assertEqual(repository.get_item(source_item.item_id).error, "original failure")


if __name__ == "__main__":
    unittest.main()
