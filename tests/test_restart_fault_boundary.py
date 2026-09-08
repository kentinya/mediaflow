from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread

from mediaflow.application.automation import (
    AutomationWorker,
    IntervalScheduler,
)
from mediaflow.application.notification import NotificationWorker
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.domain.automation import (
    AutomationClaimLost,
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
    AutomationTaskDefinition,
    AutomationTaskRunMode,
    SchedulerConfigurationSnapshot,
)
from mediaflow.domain.notification import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEventType,
    WebhookDefinition,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64


def _definition(definition_id: str = "fault-definition") -> AutomationTaskDefinition:
    return AutomationTaskDefinition(
        definition_id=definition_id,
        name="Restart fault matrix scan",
        resource_library_id="source",
        mode=AutomationTaskRunMode.SCAN_ONLY,
        interval_seconds=3600,
        item_limit=10,
        enabled=True,
    )


def _snapshot(
    definition: AutomationTaskDefinition,
    *,
    revision_id: str = "revision-1",
    digest: str = DIGEST,
    version: int = 1,
) -> SchedulerConfigurationSnapshot:
    return SchedulerConfigurationSnapshot(
        revision_id,
        digest,
        (),
        10,
        (definition,),
        version,
        ("source",),
        ("source",),
    )


def _request(api, path: str, *, token: str = "viewer-token"):
    statuses: list[str] = []
    path_info, separator, query = path.partition("?")
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path_info,
        "QUERY_STRING": query if separator else "",
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(body)


class _SuccessfulTransport:
    def send(self, request) -> int:
        return 204


class RestartFaultBoundaryTests(unittest.TestCase):
    def test_scheduler_concurrent_restart_ticks_emit_one_occurrence_and_job(self) -> None:
        definition = _definition()
        active = _snapshot(definition)
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                repository.initialize_automation_definition_due_state(
                    definition.definition_id,
                    NOW,
                    NOW,
                    definition_fingerprint=definition.definition_fingerprint,
                )

            barrier = Barrier(2)
            results: list[tuple] = []
            errors: list[BaseException] = []

            def tick() -> None:
                try:
                    with SQLiteTaskRepository(database) as repository:
                        scheduler = IntervalScheduler(
                            repository,
                            (),
                            configuration_snapshot_resolver=lambda: active,
                        )
                        barrier.wait(timeout=5)
                        results.append(scheduler.tick(NOW))
                except BaseException as error:  # pragma: no cover - asserted below
                    errors.append(error)

            threads = [Thread(target=tick) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            self.assertEqual(errors, [])
            self.assertEqual(sum(len(value) for value in results), 1)

            with SQLiteTaskRepository(database) as restarted:
                self.assertEqual(len(restarted.list_jobs()), 1)
                occurrences = restarted.list_automation_definition_occurrences(
                    definition.definition_id
                )
                self.assertEqual(len(occurrences), 1)
                self.assertEqual(occurrences[0].job_id, restarted.list_jobs()[0].job_id)
                # A later restart around the same due slot must stay quiet.
                scheduler = IntervalScheduler(
                    restarted,
                    (),
                    configuration_snapshot_resolver=lambda: active,
                )
                self.assertEqual(scheduler.tick(NOW), ())
                self.assertEqual(len(restarted.list_jobs()), 1)

    def test_worker_process_restart_rejects_stale_heartbeat_and_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            job_id = "fault-fenced-job"
            old = NOW - timedelta(hours=3)
            with SQLiteTaskRepository(database) as first_process:
                first_process.create_job(
                    AutomationJob(
                        job_id,
                        AutomationCommand.SCAN,
                        AutomationJobStatus.PENDING,
                        old,
                        old,
                        limit=1,
                        configuration_snapshot_id="revision-1",
                        configuration_snapshot_digest=DIGEST,
                        configuration_snapshot_version=1,
                    )
                )
                first_process.register_worker(
                    worker_id="worker-a",
                    label="worker-a",
                    heartbeat_interval_seconds=5.0,
                    supported_commands=("scan", "preview"),
                    configuration_snapshot_id="revision-1",
                    configuration_snapshot_digest=DIGEST,
                    runtime_schema_version=33,
                    now=old,
                )
                first_process.heartbeat_worker("worker-a", old)
                stale_claim = first_process.claim_next_job(old, worker_id="worker-a")
                self.assertIsNotNone(stale_claim)
                self.assertEqual(stale_claim.worker_id, "worker-a")

            with SQLiteTaskRepository(database) as second_process:
                requeued = second_process.requeue_stale_job(job_id, NOW - timedelta(hours=2), NOW)
                self.assertEqual(requeued.status, AutomationJobStatus.PENDING)
                self.assertIsNone(requeued.claim_token)
                second_process.register_worker(
                    worker_id="worker-b",
                    label="worker-b",
                    heartbeat_interval_seconds=5.0,
                    supported_commands=("scan", "preview"),
                    configuration_snapshot_id="revision-1",
                    configuration_snapshot_digest=DIGEST,
                    runtime_schema_version=33,
                    now=NOW,
                )
                current_claim = second_process.claim_next_job(NOW, worker_id="worker-b")
                self.assertIsNotNone(current_claim)
                self.assertEqual(current_claim.worker_id, "worker-b")
                self.assertTrue(
                    second_process.complete_claimed_job(
                        replace(
                            current_claim,
                            status=AutomationJobStatus.COMPLETED,
                            updated_at=NOW,
                            completed_at=NOW,
                            task_id="task-b",
                        )
                    )
                )

                with self.assertRaises(AutomationClaimLost):
                    second_process.heartbeat_job(job_id, stale_claim.claim_token, NOW)
                self.assertFalse(
                    second_process.complete_claimed_job(
                        replace(
                            stale_claim,
                            status=AutomationJobStatus.COMPLETED,
                            updated_at=NOW,
                            completed_at=NOW,
                            task_id="task-a",
                        )
                    )
                )
                persisted = second_process.get_job(job_id)
                self.assertEqual(persisted.status, AutomationJobStatus.COMPLETED)
                self.assertEqual(persisted.worker_id, "worker-b")
                self.assertEqual(persisted.task_id, "task-b")
                self.assertIsNone(persisted.claim_token)

                viewer = ResolvedApiPrincipal(
                    "viewer", "viewer-token", frozenset({ApiPermission.READ})
                )
                api = MediaFlowApi(second_process, None, principals=(viewer,))
                status, document = _request(api, f"/api/v1/jobs/{job_id}")
                self.assertEqual(status, 200)
                self.assertEqual(document["job_id"], job_id)
                self.assertEqual(document["status"], "completed")
                self.assertNotIn("claim_token", json.dumps(document).lower())

    def test_uncertain_executor_effect_survives_restart_without_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            task_id = "uncertain-task"
            with SQLiteTaskRepository(database) as first_process:
                task = PersistentTask(
                    task_id,
                    "organize",
                    PersistentTaskStatus.PARTIAL_SUCCESS,
                    True,
                    NOW,
                    NOW,
                    NOW,
                    NOW,
                    total_items=2,
                    completed_items=1,
                    failed_items=1,
                )
                first_process.create_task(task)
                first_process.upsert_item(
                    PersistentTaskItem(
                        "item-success",
                        task_id,
                        "source",
                        "library",
                        "Ok.2001.mkv",
                        "Ok.2001.mkv",
                        TaskItemStatus.SUCCESS,
                        "completed",
                        1,
                        NOW,
                        NOW,
                        destination_storage_id="target",
                        destination_path="Movies/Ok (2001)/Ok (2001).mkv",
                    )
                )
                first_process.upsert_item(
                    PersistentTaskItem(
                        "item-uncertain",
                        task_id,
                        "source",
                        "library",
                        "Uncertain.2001.mkv",
                        "Uncertain.2001.mkv",
                        TaskItemStatus.PARTIAL,
                        "failed",
                        1,
                        NOW,
                        NOW,
                        destination_storage_id="target",
                        destination_path="Movies/Uncertain (2001)/Uncertain (2001).mkv",
                        error="uncertain executor response",
                    )
                )
                first_process.append_result(
                    PersistentResultRecord(
                        "result-success",
                        task_id,
                        "item-success",
                        "source",
                        "Ok.2001.mkv",
                        "target",
                        "Movies/Ok (2001)/Ok (2001).mkv",
                        "C",
                        "tmdb",
                        "1",
                        "metadata-c",
                        "naming-a",
                        "classification-a",
                        "organize-move",
                        "MOVE",
                        "success",
                        NOW,
                        title="Ok",
                        completed_operations=("MOVE",),
                        effect_certainty="verified_complete",
                    )
                )
                first_process.append_result(
                    PersistentResultRecord(
                        "result-uncertain",
                        task_id,
                        "item-uncertain",
                        "source",
                        "Uncertain.2001.mkv",
                        "target",
                        "Movies/Uncertain (2001)/Uncertain (2001).mkv",
                        "C",
                        "tmdb",
                        "2",
                        "metadata-c",
                        "naming-a",
                        "classification-a",
                        "organize-move",
                        "MOVE",
                        "partial",
                        NOW,
                        title="Uncertain",
                        error="unknown effect",
                        completed_operations=("MOVE",),
                        effect_certainty="attempted_unverified",
                        uncertain_effects=("mutation_outcome",),
                    )
                )

            with SQLiteTaskRepository(database) as restarted:
                items = {item.item_id: item for item in restarted.list_items(task_id)}
                self.assertEqual(items["item-success"].status, TaskItemStatus.SUCCESS)
                self.assertEqual(items["item-uncertain"].status, TaskItemStatus.PARTIAL)
                self.assertEqual(len(restarted.list_results(task_id)), 2)
                checkpoint = ProcessingCheckpointService(restarted).get(
                    "item-uncertain", task_id=task_id
                )
                self.assertEqual(checkpoint.effect_certainty.value, "attempted_unverified")
                self.assertEqual(checkpoint.completed_operations, ("MOVE",))
                self.assertEqual(checkpoint.uncertain_effects, ("mutation_outcome",))
                self.assertIn("investigate", checkpoint.permitted_action_ids)
                self.assertNotIn("retry", checkpoint.permitted_action_ids)
                self.assertIn("automatic_replay_refused", checkpoint.refusal_reason)

                viewer = ResolvedApiPrincipal(
                    "viewer", "viewer-token", frozenset({ApiPermission.READ})
                )
                api = MediaFlowApi(restarted, None, principals=(viewer,))
                status, detail = _request(api, f"/api/v1/tasks/{task_id}/items/item-uncertain")
                self.assertEqual(status, 200)
                self.assertEqual(detail["permitted_action_ids"], ["investigate"])
                self.assertNotIn("retry", detail["permitted_action_ids"])
                self.assertEqual(detail["effects"]["certainty"], "attempted_unverified")
                self.assertIn("automatic_replay_refused", detail["refusal_reason"])
                status, success = _request(api, f"/api/v1/tasks/{task_id}/items/item-success")
                self.assertEqual(status, 200)
                self.assertEqual(success["status"], "success")

    def test_notification_outbox_survives_restart_and_lease_is_at_least_once(self) -> None:
        definition = WebhookDefinition(
            "hook",
            "https://example.invalid/mediaflow",
            "MEDIAFLOW_WEBHOOK_SECRET",
            (NotificationEventType.JOB_COMPLETED,),
            timeout_seconds=1.0,
            max_attempts=2,
            base_retry_seconds=0.1,
            max_retry_seconds=1.0,
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as first_process:
                for index, status in enumerate(
                    (
                        NotificationDeliveryStatus.PENDING,
                        NotificationDeliveryStatus.RETRY,
                        NotificationDeliveryStatus.DELIVERED,
                        NotificationDeliveryStatus.DEAD_LETTER,
                    )
                ):
                    first_process.create_delivery(
                        NotificationDelivery(
                            f"delivery-{status.value}",
                            definition.webhook_id,
                            f"event-{index}",
                            NotificationEventType.JOB_COMPLETED,
                            "{}",
                            status,
                            1 if status != NotificationDeliveryStatus.PENDING else 0,
                            NOW,
                            NOW,
                            NOW,
                            NOW if status == NotificationDeliveryStatus.DELIVERED else None,
                        )
                    )
                first_process.create_delivery(
                    NotificationDelivery(
                        "delivery-stale-lease",
                        definition.webhook_id,
                        "event-stale",
                        NotificationEventType.JOB_COMPLETED,
                        "{}",
                        NotificationDeliveryStatus.DELIVERING,
                        1,
                        NOW,
                        NOW - timedelta(seconds=301),
                        NOW - timedelta(seconds=301),
                    )
                )

            with SQLiteTaskRepository(database) as restarted:
                persisted = {item.delivery_id: item for item in restarted.list_deliveries()}
                self.assertEqual(len(persisted), 5)
                self.assertEqual(
                    {item.status for item in persisted.values()},
                    {
                        NotificationDeliveryStatus.PENDING,
                        NotificationDeliveryStatus.RETRY,
                        NotificationDeliveryStatus.DELIVERED,
                        NotificationDeliveryStatus.DEAD_LETTER,
                        NotificationDeliveryStatus.DELIVERING,
                    },
                )
                worker = NotificationWorker(
                    restarted,
                    {definition.webhook_id: (definition, "test-secret")},
                    _SuccessfulTransport(),
                    delivery_lease_seconds=300,
                    clock=lambda: NOW + timedelta(seconds=301),
                )
                reclaimed = worker.run_next()
                self.assertEqual(reclaimed.delivery_id, "delivery-stale-lease")
                self.assertEqual(reclaimed.status, NotificationDeliveryStatus.DELIVERED)
                self.assertEqual(reclaimed.attempts, 2)
                self.assertEqual(len(restarted.list_deliveries()), 5)

                viewer = ResolvedApiPrincipal(
                    "viewer", "viewer-token", frozenset({ApiPermission.READ})
                )
                api = MediaFlowApi(restarted, None, principals=(viewer,))
                status, document = _request(api, "/api/v1/notifications?limit=20")
                self.assertEqual(status, 200)
                self.assertEqual(len(document["items"]), 5)
                self.assertNotIn("body", json.dumps(document).lower())
                status, page = _request(api, "/api/v1/jobs?limit=1")
                self.assertEqual(status, 200)
                self.assertIn("items", page)

    def test_api_and_web_read_projection_after_restart_is_zero_mutation(self) -> None:
        definition = _definition()
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: _snapshot(definition),
                ).tick(NOW)
                AutomationWorker(repository, lambda job, cancelled: "task-1").run_next()
                before = {
                    "jobs": len(repository.list_jobs()),
                    "tasks": len(repository.list_tasks()),
                    "notifications": len(repository.list_deliveries()),
                }
            viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
            with SQLiteTaskRepository(database) as restarted:
                api = MediaFlowApi(restarted, None, principals=(viewer,))
                for path in (
                    "/api/v1/jobs?limit=20",
                    "/api/v1/tasks?limit=20",
                    "/api/v1/notifications?limit=20",
                    "/api/v1/logs?limit=20",
                ):
                    status, _ = _request(api, path)
                    self.assertEqual(status, 200, path)
                self.assertIn(b"showTaskItem", APP_JS)
                self.assertIn(b"showTask", APP_JS)
                after = {
                    "jobs": len(restarted.list_jobs()),
                    "tasks": len(restarted.list_tasks()),
                    "notifications": len(restarted.list_deliveries()),
                }
                self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
