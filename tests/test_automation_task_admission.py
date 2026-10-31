"""Task47.3: automatic Scheduler due and Run once admit one kernel Task.

The Scheduler admits the Task *before* business readiness and commits the
occurrence/due/schedule advance with it inside one transaction, so no
``automation_jobs`` row is written and a full or concurrent tick leaves the due
state unchanged.  The resident Task engine then advances that same Task through
the shared definition pipeline under its live claim fence.
"""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.automation import IntervalScheduler
from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
from mediaflow.domain.automation import (
    AutomationTaskDefinition,
    AutomationTaskRunMode,
    SchedulerConfigurationSnapshot,
)
from mediaflow.domain.task_persistence import PersistentTaskStatus, TaskItemStatus
from mediaflow.domain.task_scheduling import TaskQueueState, TaskTrigger
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository

NOW = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
DIGEST = "a" * 64


def _definition(definition_id: str = "definition", *, enabled: bool = True):
    return AutomationTaskDefinition(
        definition_id=definition_id,
        name=definition_id,
        resource_library_id="resource",
        source_scope="incoming",
        mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
        interval_seconds=60,
        item_limit=7,
        enabled=enabled,
    )


def _snapshot(definitions, *, maximum_active_jobs: int = 10, version: int = 3):
    return SchedulerConfigurationSnapshot(
        "revision-1",
        DIGEST,
        (),
        maximum_active_jobs,
        tuple(definitions),
        version,
        ("resource",),
        ("resource",),
    )


def _rows(repository: SQLiteTaskRepository, table: str) -> int:
    return int(repository._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class SchedulerTaskAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.database = Path(self._directory.name, "runtime.sqlite3")
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.repository.close)

    def _scheduler(self, active, *, capacity=10):
        from mediaflow.application.task_scheduling import TaskSchedulingService

        return IntervalScheduler(
            self.repository,
            (),
            configuration_snapshot_resolver=lambda: active,
            scheduling_service=TaskSchedulingService(self.repository, capacity=capacity),
        )

    def test_due_definition_admits_one_task_with_no_job(self) -> None:
        active = _snapshot((_definition(),))
        emitted = self._scheduler(active).tick(NOW)

        self.assertEqual(len(emitted), 1)
        task_id = emitted[0].task_id
        self.assertEqual(emitted[0].job_id, task_id)
        self.assertEqual(_rows(self.repository, "automation_jobs"), 0)
        task = self.repository.get_task(task_id)
        self.assertIsNotNone(task)
        state = self.repository.get_task_scheduling(task_id)
        self.assertIs(state.admission_trigger, TaskTrigger.SCHEDULE)
        self.assertIs(state.queue_state, TaskQueueState.QUEUED)
        occurrence = self.repository.get_latest_automation_definition_occurrence("definition")
        # The occurrence keeps its durable link through the existing ``job_id``
        # column, which now carries the substantive Task identity (no Job row).
        self.assertEqual(occurrence.job_id, task_id)
        # the due state advanced once
        due = self.repository.get_automation_definition_due_state("definition")
        self.assertEqual(due.last_occurrence_at, NOW)

    def test_concurrent_ticks_admit_the_same_occurrence_once(self) -> None:
        active = _snapshot((_definition(),))
        first = self._scheduler(active).tick(NOW)
        second = self._scheduler(active).tick(NOW)
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 0)
        self.assertEqual(_rows(self.repository, "automation_jobs"), 0)
        states = [
            self.repository.get_task_scheduling(row["task_id"])
            for row in self.repository._connection.execute(
                "SELECT task_id FROM task_scheduling"
            ).fetchall()
        ]
        self.assertEqual(len(states), 1)

    def test_full_capacity_leaves_the_occurrence_due_without_a_task(self) -> None:
        active = _snapshot((_definition(),), maximum_active_jobs=1)
        from mediaflow.application.task_scheduling import TaskSchedulingService

        # Occupy the one shared slot with a different admitted Task.
        occupied = TaskSchedulingService(self.repository, capacity=1).admit(
            "organize",
            execute_authorized=True,
            trigger=TaskTrigger.MANUAL,
            principal="operator",
            request_id="occupied",
            configuration_snapshot_id="snapshot",
            configuration_snapshot_digest="digest",
        )
        emitted = self._scheduler(active, capacity=1).tick(NOW)

        self.assertEqual(emitted, ())
        self.assertEqual(_rows(self.repository, "automation_jobs"), 0)
        self.assertEqual(_rows(self.repository, "task_scheduling"), 1)
        due = self.repository.get_automation_definition_due_state("definition")
        self.assertIsNone(due.last_occurrence_at)
        self.assertEqual(
            self.repository.get_task_scheduling(occupied.task.task_id).queue_state,
            TaskQueueState.QUEUED,
        )

    def test_disabled_definition_is_not_admitted(self) -> None:
        active = _snapshot((_definition(enabled=False),))
        self.assertEqual(self._scheduler(active).tick(NOW), ())
        self.assertEqual(_rows(self.repository, "task_scheduling"), 0)


class AutomaticEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.database = Path(self._directory.name, "runtime.sqlite3")
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.repository.close)
        self.repository.register_worker(
            "worker-1", "worker one", 5.0, ("organize",), None, None, SCHEMA_VERSION, NOW
        )

    def _admit(self, scheduling, *, trigger=TaskTrigger.SCHEDULE):
        return scheduling.admit(
            "organize",
            execute_authorized=True,
            trigger=trigger,
            principal="automation-scheduler",
            request_id=f"request-{trigger.value}",
            scope_path="incoming",
            item_limit=7,
            configuration_snapshot_id="snapshot-1",
            configuration_snapshot_digest="digest-1",
        )

    def _worker(self, scheduling, runner):
        return ManualTaskEngineWorker(
            self.repository,
            scheduling,
            None,
            None,
            worker_id="worker-1",
            clock=lambda: NOW,
            automatic_runner=runner,
        )

    def test_automatic_task_runs_its_runner_and_settles_completed(self) -> None:
        from mediaflow.application.task_scheduling import TaskSchedulingService

        scheduling = TaskSchedulingService(self.repository, capacity=5)
        admission = self._admit(scheduling)
        seen: list[str] = []

        def runner(task, claim, clock=None, heartbeat=None):
            seen.append(task.task_id)

        worker = self._worker(scheduling, runner)
        worker.run_next()

        self.assertEqual(seen, [admission.task.task_id])
        task = self.repository.get_task(admission.task.task_id)
        self.assertIs(task.status, PersistentTaskStatus.COMPLETED)
        self.assertIs(
            self.repository.get_task_scheduling(task.task_id).queue_state,
            TaskQueueState.SETTLED,
        )

    def test_automatic_failure_settles_failed_without_replay(self) -> None:
        from mediaflow.application.task_scheduling import TaskSchedulingService

        scheduling = TaskSchedulingService(self.repository, capacity=5)
        admission = self._admit(scheduling)

        def runner(task, claim, clock=None, heartbeat=None):
            raise RuntimeError("provider unavailable")

        worker = self._worker(scheduling, runner)
        worker.run_next()

        task = self.repository.get_task(admission.task.task_id)
        self.assertIs(task.status, PersistentTaskStatus.FAILED)

    def test_automatic_waiting_item_returns_the_slot_to_human(self) -> None:
        from mediaflow.application.task_scheduling import TaskSchedulingService

        scheduling = TaskSchedulingService(self.repository, capacity=5)
        admission = self._admit(scheduling)

        def runner(task, claim, clock=None, heartbeat=None):
            item = scheduling.begin_item(
                claim,
                storage_id="local",
                resource_library_id="library",
                source_path="incoming/A.mkv",
                source_display="incoming/A.mkv",
                source_storage_path="incoming/A.mkv",
                now=NOW + timedelta(seconds=1),
            )
            scheduling.record_item(
                claim,
                replace(
                    item,
                    status=TaskItemStatus.WAITING_METADATA,
                    stage="waiting_metadata",
                    updated_at=NOW + timedelta(seconds=2),
                ),
                now=NOW + timedelta(seconds=2),
            )

        worker = self._worker(scheduling, runner)
        worker.run_next()

        state = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertIs(state.queue_state, TaskQueueState.WAITING_HUMAN)
        self.assertFalse(state.holds_capacity)
        self.assertEqual(self.repository.count_scheduled_capacity_use(), 0)


class KernelTaskCoordinatorTests(unittest.TestCase):
    """The definition pipeline publishes under the live Task claim fence."""

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.database = Path(self._directory.name, "runtime.sqlite3")
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.repository.close)
        self.repository.register_worker(
            "worker-1", "worker one", 5.0, ("organize",), None, None, SCHEMA_VERSION, NOW
        )

    def test_item_and_result_commit_under_the_claim_fence(self) -> None:
        from mediaflow.application.media_organizer import MediaOrganizerItemResult
        from mediaflow.application.task_runtime import KernelTaskCoordinator
        from mediaflow.application.task_scheduling import TaskSchedulingService

        real_now = datetime.now(UTC)
        self.repository.register_worker(
            "worker-1", "worker one", 5.0, ("organize",), None, None, SCHEMA_VERSION, real_now
        )
        scheduling = TaskSchedulingService(self.repository, capacity=5)
        admission = scheduling.admit(
            "organize",
            execute_authorized=True,
            trigger=TaskTrigger.SCHEDULE,
            principal="automation-scheduler",
            scope_path="incoming",
            item_limit=7,
            configuration_snapshot_id="snapshot-1",
            configuration_snapshot_digest="digest-1",
            now=real_now,
        )
        claim = scheduling.claim_next(worker_id="worker-1", now=real_now)
        claim = scheduling.begin_work(claim, now=real_now + timedelta(seconds=1))
        coordinator = KernelTaskCoordinator(self.repository, self.repository, scheduling, claim)
        item = coordinator.begin_item(
            admission.task.task_id,
            "local",
            "library",
            "incoming/A.mkv",
            "incoming/A.mkv",
            source_storage_path="incoming/A.mkv",
        )
        coordinator.complete_item(item, MediaOrganizerItemResult("incoming/A.mkv"))

        stored = self.repository.get_item(item.item_id)
        self.assertIsNotNone(stored)
        self.assertIs(stored.status, TaskItemStatus.SKIPPED)
        results = self.repository.list_results(admission.task.task_id)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].result_id, f"{item.item_id}:{item.attempts}")


if __name__ == "__main__":
    unittest.main()
