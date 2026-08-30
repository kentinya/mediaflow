from __future__ import annotations

import io
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.automation import AutomationJobService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.recovery_admission import RecoveryAdmissionService
from mediaflow.application.recovery_batch import RecoveryBatchContinuationService
from mediaflow.application.recovery_continuation import RecoveryContinuationService
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.recovery_batch import RecoveryBatchItemStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import PersistentResultRecord, TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import ASSETS
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
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation_service = RecoveryContinuationService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                )
                checkpoint = continuation_service.checkpoint_service.get(source_item.item_id)
                service = RecoveryBatchContinuationService(
                    repository,
                    continuation_service=continuation_service,
                    admission_service=RecoveryAdmissionService(
                        repository,
                        snapshot_validator=lambda _id, _digest: None,
                        checkpoint_service=continuation_service.checkpoint_service,
                    ),
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
            self.assertIsNotNone(batch.items[0].request_id)

    def test_api_batch_submission_and_task_reload_expose_parent_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _RecoveryContinuationTests()
            environment = helper._environment(directory)
            source_task, source_item = helper._seed_failed_item(environment)
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

    def test_two_accepted_children_complete_independently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _RecoveryContinuationTests()
            environment = helper._environment(directory)
            source_task, source_item = helper._seed_failed_item(environment)
            sibling_path = Path(environment["source_file"]).with_name("Sibling.mkv")
            sibling_path.write_bytes(b"unchanged-sibling")
            with SQLiteTaskRepository(environment["database"]) as repository:
                sibling = repository.list_items(source_task.task_id)[1]
                sibling = replace(
                    sibling,
                    status=TaskItemStatus.FAILED,
                    stage="failed",
                    error="sibling failure",
                )
                repository.upsert_item(sibling)
                repository.append_result(
                    PersistentResultRecord(
                        "result-second-failure",
                        source_task.task_id,
                        sibling.item_id,
                        "source-storage",
                        sibling.source_path,
                        "target-storage",
                        "Movies/Sibling.mkv",
                        "C",
                        "tmdb",
                        "124",
                        "C",
                        "A",
                        "A",
                        "A",
                        "MOVE",
                        TaskItemStatus.FAILED.value,
                        datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
                        title="Sibling",
                        error="sibling failure",
                        effect_certainty="none",
                        uncertain_effects=(),
                    )
                )
                continuation_service = RecoveryContinuationService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                )
                admission_service = RecoveryAdmissionService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                    checkpoint_service=continuation_service.checkpoint_service,
                )
                selections = [
                    {
                        "itemId": item.item_id,
                        "expectedCheckpointVersion": continuation_service.checkpoint_service.get(
                            item.item_id
                        ).checkpoint_version,
                    }
                    for item in repository.list_items(source_task.task_id)
                    if item.status is TaskItemStatus.FAILED
                ]
                batch = RecoveryBatchContinuationService(
                    repository,
                    continuation_service=continuation_service,
                    admission_service=admission_service,
                ).submit(
                    source_task.task_id,
                    selections,
                    actor="operator",
                    maximum_active_jobs=100,
                )
                self.assertEqual(len(batch.items), 2)
                self.assertEqual(
                    {item.status for item in batch.items},
                    {RecoveryBatchItemStatus.QUEUED},
                )
                self.assertEqual(len({item.continuation_id for item in batch.items}), 2)
            provider = DetailCountingProvider(
                candidates=(
                    MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),
                    MediaCandidate("tmdb", "43", MediaType.MOVIE, "Sibling", year=2024),
                )
            )
            source_before = (source_task.task_id, source_item.item_id, source_item.error)
            target_before = tuple(
                sorted(
                    (
                        str(path.relative_to(environment["target_root"])),
                        path.stat().st_size,
                    )
                    for path in Path(environment["target_root"]).rglob("*")
                    if path.is_file()
                )
            )

            def run_worker_without_assertion() -> int:
                output, errors = io.StringIO(), io.StringIO()
                original_create_storages = RuntimeConfiguration.create_storages

                def create_storages(configuration, external=None, storage_ids=None):
                    return original_create_storages(configuration, external, storage_ids)

                with (
                    patch.object(RuntimeConfiguration, "create_storages", create_storages),
                    patch(
                        "mediaflow.final_cli.metadata_provider_registry_from_environment",
                        lambda _ids: MetadataProviderRegistry((provider,)),
                    ),
                ):
                    return final_main(
                        ["--config", str(environment["config"]), "worker", "run-next"],
                        stdout=output,
                        stderr=errors,
                    )

            worker_codes = (run_worker_without_assertion(), run_worker_without_assertion())
            self.assertEqual(set(worker_codes), {0, 1})
            with SQLiteTaskRepository(environment["database"]) as repository:
                reloaded = repository.get_recovery_batch(batch.batch_id)
                self.assertEqual(reloaded.status.value, "partial")
                self.assertEqual(
                    {item.status for item in reloaded.items},
                    {RecoveryBatchItemStatus.COMPLETED, RecoveryBatchItemStatus.FAILED},
                )
                self.assertEqual(
                    repository.get_item(source_item.item_id).error,
                    "original failure",
                )
                self.assertEqual(repository.get_item(sibling.item_id).error, "sibling failure")
                self.assertEqual(len(repository.list_results(source_task.task_id)), 3)
            self.assertEqual(
                (source_task.task_id, source_item.item_id, source_item.error),
                source_before,
            )
            self.assertEqual(
                tuple(
                    sorted(
                        (
                            str(path.relative_to(environment["target_root"])),
                            path.stat().st_size,
                        )
                        for path in Path(environment["target_root"]).rglob("*")
                        if path.is_file()
                    )
                ),
                target_before,
            )

    def test_failed_item_batch_admits_request_and_links_child_in_one_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _RecoveryContinuationTests()
            environment = helper._environment(directory)
            source_task, source_item = helper._seed_failed_item(environment)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation_service = RecoveryContinuationService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                )
                admission_service = RecoveryAdmissionService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                    checkpoint_service=continuation_service.checkpoint_service,
                )
                checkpoint = continuation_service.checkpoint_service.get(source_item.item_id)
                service = RecoveryBatchContinuationService(
                    repository,
                    continuation_service=continuation_service,
                    admission_service=admission_service,
                )
                with patch.object(
                    repository,
                    "update_recovery_batch_item",
                    side_effect=AssertionError("accepted child used a second linkage write"),
                ):
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
                self.assertIsNotNone(batch.items[0].continuation_id)
                self.assertIsNotNone(batch.items[0].job_id)
                self.assertEqual(
                    len(repository.list_recovery_continuations(source_item.item_id)),
                    1,
                )

    def test_duplicate_batch_submission_keeps_one_active_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _RecoveryContinuationTests()
            environment = helper._environment(directory)
            source_task, source_item = helper._seed_failed_item(environment)
            with SQLiteTaskRepository(environment["database"]) as repository:
                service = RecoveryBatchContinuationService(
                    repository,
                    continuation_service=RecoveryContinuationService(
                        repository,
                        snapshot_validator=lambda _id, _digest: None,
                    ),
                    admission_service=RecoveryAdmissionService(
                        repository,
                        snapshot_validator=lambda _id, _digest: None,
                    ),
                )
                checkpoint = service._continuation_service.checkpoint_service.get(
                    source_item.item_id
                )
                first = service.submit(
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
                second = service.submit(
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
                self.assertNotEqual(first.batch_id, second.batch_id)
                self.assertEqual(
                    len(repository.list_recovery_continuations(source_item.item_id)), 1
                )
                self.assertEqual(second.items[0].status, RecoveryBatchItemStatus.REFUSED)

    def test_batch_api_rejects_bad_input_and_enforces_read_permission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            helper = _RecoveryContinuationTests()
            environment = helper._environment(directory)
            source_task, _source_item = helper._seed_failed_item(environment)
            api = helper._api(environment)
            status, document = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/recovery/continue-batch",
                method="POST",
                body={"items": "not-a-list"},
            )
            self.assertEqual(status, 400)
            self.assertEqual(document["error"]["code"], "invalid_request")
            status, document = api_request(api, "/api/v1/recovery-batches/unknown")
            self.assertEqual(status, 404)
            self.assertEqual(document["error"]["code"], "not_found")
            status, document = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/recovery/continue-batch",
                method="POST",
                body={"items": [{}] * 101},
            )
            self.assertEqual(status, 400)
            self.assertEqual(document["error"]["code"], "invalid_request")
            status, document = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/recovery/continue-batch",
                method="POST",
                body={"items": [{"itemId": "foreign-item", "expectedCheckpointVersion": "0" * 64}]},
            )
            self.assertEqual(status, 202)
            self.assertEqual(document["counts"]["refused"], 1)
            api._principals = (
                ResolvedApiPrincipal("reader", "reader-token", frozenset({ApiPermission.READ})),
            )
            status, document = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/recovery/continue-batch",
                method="POST",
                body={"items": []},
                token="reader-token",
            )
            self.assertEqual(status, 403)
            self.assertEqual(document["error"]["code"], "forbidden")
            script = ASSETS["/ui/app.js"][1].decode("utf-8")
            self.assertIn("confirmBatchRecovery", script)
            self.assertIn("showRecoveryBatch", script)
            self.assertIn("continue-batch", script)


if __name__ == "__main__":
    unittest.main()
