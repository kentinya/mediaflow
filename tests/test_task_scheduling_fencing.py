"""Ownership fencing, real concurrency and the uncertain-effect boundary.

These tests use separate real connections (and, for admission, separate OS
processes) against one temporary database.  They exist to prove the properties a
single in-process call can never prove: only one effective owner, no capacity
overbooking, no stale publication, and no replay of a mutation whose outcome was
never durably recorded.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.task_scheduling import TaskSchedulingService
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.domain.task_scheduling import (
    TASK_MUTATION_IN_FLIGHT,
    TaskClaimFence,
    TaskClaimFenceLost,
    TaskControl,
    TaskControlRejected,
    TaskMachineStage,
    TaskQueueFull,
    TaskQueueState,
    TaskSchedulingError,
    TaskTrigger,
    TaskWorkerRejected,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

#: The exact source range the candidate review sees; the base-side process below
#: imports the *base* revision only so a race between two real processes is
#: measured on the same durable code under test.
_ADMIT_PROCESS = """
from datetime import UTC, datetime
from pathlib import Path
import sys

from mediaflow.application.task_scheduling import TaskSchedulingService
from mediaflow.domain.task_scheduling import TaskQueueFull, TaskTrigger
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

database, request_id = Path(sys.argv[1]), sys.argv[2]
now = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
try:
    with SQLiteTaskRepository(database) as repository:
        service = TaskSchedulingService(repository, capacity=1)
        admission = service.admit(
            "organize",
            execute_authorized=True,
            trigger=TaskTrigger.SCHEDULE,
            principal="scheduler",
            request_id=request_id,
            scope_path="Media",
        )
except TaskQueueFull:
    print("refused")
else:
    print("admitted", admission.task.task_id)
"""


class FencingTestCase(unittest.TestCase):
    capacity = 2

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.database = Path(self._directory.name, "runtime.sqlite3")
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.repository.close)
        self.repository.register_worker(
            "worker-1",
            "worker one",
            5.0,
            ("organize",),
            None,
            None,
            SCHEMA_VERSION,
            NOW,
        )
        self.repository.register_worker(
            "worker-2",
            "worker two",
            5.0,
            ("organize",),
            None,
            None,
            SCHEMA_VERSION,
            NOW,
        )

    def service(self, *, capacity=None, repository=None):
        return TaskSchedulingService(
            repository or self.repository,
            capacity=self.capacity if capacity is None else capacity,
            locks=repository or self.repository,
        )

    def admit(self, service, *, request_id="request-1", **overrides):
        arguments = {
            "execute_authorized": True,
            "trigger": TaskTrigger.MANUAL,
            "principal": "operator",
            "request_id": request_id,
            "scope_path": "媒体/电影",
            "item_limit": 10,
            "configuration_snapshot_id": "snapshot-1",
            "configuration_snapshot_digest": "digest-1",
        }
        arguments.update(overrides)
        return service.admit("organize", **arguments)

    def connection(self, now: datetime | None = None):
        """A second, independent real connection to the same database."""

        repository = SQLiteTaskRepository(self.database)
        self.addCleanup(repository.close)
        return repository

    def started(self, service, *, worker="worker-1", now=None):
        at = now or NOW
        claim = service.claim_next(worker_id=worker, now=at)
        self.assertIsNotNone(claim)
        assert claim is not None
        return service.begin_work(
            claim, stage=TaskMachineStage.EXECUTION, now=at + timedelta(seconds=1)
        )

    def item(self, service, claim, path="媒体/电影/A.mkv", *, now=None):
        return service.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path=path,
            source_display=path,
            now=now or NOW + timedelta(seconds=2),
        )

    def waiting_human(
        self,
        service,
        *,
        request_id="request-1",
        success_first=False,
        now=None,
    ):
        """One Task that reached the human boundary with a genuine real DB row."""

        at = now or NOW
        admission = self.admit(service, request_id=request_id)
        claim = self.started(service, now=at)
        success_item = None
        offset = 2
        if success_first:
            success_item = self.item(
                service,
                claim,
                path=f"媒体/电影/{request_id}-done.mkv",
                now=at + timedelta(seconds=2),
            )
            service.complete_item(
                claim,
                replace(
                    success_item,
                    status=TaskItemStatus.SUCCESS,
                    stage="completed",
                    updated_at=at + timedelta(seconds=3),
                ),
                result=self.result(success_item),
                now=at + timedelta(seconds=3),
            )
            offset = 3
        item = self.item(
            service,
            claim,
            path=f"媒体/电影/{request_id}-waiting.mkv",
            now=at + timedelta(seconds=offset),
        )
        waiting = replace(
            item,
            status=TaskItemStatus.WAITING_CONFIRM,
            stage="waiting_confirm",
            updated_at=at + timedelta(seconds=offset + 1),
        )
        task = replace(
            self.repository.get_task(claim.task_id),
            status=PersistentTaskStatus.PARTIAL_SUCCESS,
            total_items=2 if success_first else 1,
            completed_items=1 if success_first else 0,
            completed_at=at + timedelta(seconds=offset + 2),
        )
        service.defer_to_human(
            claim,
            task=task,
            items=(waiting,),
            now=at + timedelta(seconds=offset + 2),
        )
        return admission, claim, success_item

    def result(self, item):
        return PersistentResultRecord(
            f"{item.item_id}:{item.attempts}",
            item.task_id,
            item.item_id,
            item.storage_id,
            item.source_path,
            "local",
            "Media/A/A.mkv",
            "C",
            None,
            None,
            None,
            None,
            None,
            None,
            "move",
            "success",
            NOW + timedelta(seconds=3),
            effect_certainty="verified_complete",
        )


class ConcurrencyTests(FencingTestCase):
    def test_two_workers_racing_one_task_produce_exactly_one_owner(self) -> None:
        service = self.service(capacity=1)
        admission = self.admit(service)
        barrier = threading.Barrier(2)
        outcomes: list[object] = []
        lock = threading.Lock()

        def claim(worker: str, token: str) -> None:
            repository = SQLiteTaskRepository(self.database)
            try:
                contender = self.service(capacity=1, repository=repository)
                barrier.wait(timeout=10)
                outcome = contender.claim_next(
                    worker_id=worker, claim_token=token, now=NOW + timedelta(seconds=1)
                )
            finally:
                repository.close()
            with lock:
                outcomes.append(outcome)

        threads = [
            threading.Thread(target=claim, args=("worker-1", "token-one")),
            threading.Thread(target=claim, args=("worker-2", "token-two")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        winners = [outcome for outcome in outcomes if outcome is not None]
        self.assertEqual(len(winners), 1)
        state = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertIsNotNone(state)
        assert state is not None
        self.assertIs(state.queue_state, TaskQueueState.CLAIMED)
        self.assertEqual(state.claim_generation, 1)
        self.assertEqual(state.claim_worker_id, winners[0].worker_id)

    def test_current_owner_takes_the_task_once_and_the_other_worker_never_sees_it(self) -> None:
        service = self.service()
        admission = self.admit(service)
        first = service.claim_next(worker_id="worker-1", now=NOW)
        self.assertIsNotNone(first)
        other = self.service(repository=self.connection())
        self.assertIsNone(other.claim_next(worker_id="worker-2", now=NOW + timedelta(seconds=1)))
        state = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertEqual(state.claim_worker_id, "worker-1")
        self.assertEqual(state.claim_generation, 1)

    def test_simultaneous_admissions_never_overbook_the_shared_capacity(self) -> None:
        barrier = threading.Barrier(6)
        outcomes: list[object] = []
        lock = threading.Lock()

        def admit(index: int) -> None:
            repository = SQLiteTaskRepository(self.database)
            try:
                contender = self.service(capacity=1, repository=repository)
                barrier.wait(timeout=10)
                try:
                    outcome = self.admit(contender, request_id=f"request-{index}")
                except TaskQueueFull as error:
                    outcome = error
            finally:
                repository.close()
            with lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=admit, args=(index,)) for index in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        admitted = [value for value in outcomes if not isinstance(value, Exception)]
        refused = [value for value in outcomes if isinstance(value, TaskQueueFull)]
        self.assertEqual(len(admitted), 1, outcomes)
        self.assertEqual(len(refused), 5, outcomes)
        self.assertEqual(self.service(capacity=1).capacity_use(), 1)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 1)
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM task_scheduling").fetchone()[0], 1
            )

    def test_admission_from_real_separate_processes_keeps_one_slot(self) -> None:
        service = self.service(capacity=1)
        self.assertIsNone(service.state("nonexistent"))
        processes = [
            subprocess.Popen(
                [sys.executable, "-c", _ADMIT_PROCESS, str(self.database), f"request-{index}"],
                cwd=str(REPOSITORY_ROOT),
                env={**os.environ, "PYTHONPATH": str(REPOSITORY_ROOT)},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for index in range(3)
        ]
        outputs = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=120)
            self.assertEqual(process.returncode, 0, stderr)
            outputs.append(stdout.strip())
        self.assertEqual(sum(output.startswith("admitted") for output in outputs), 1, outputs)
        self.assertEqual(sum(output == "refused" for output in outputs), 2, outputs)
        self.assertEqual(self.service(capacity=1).capacity_use(), 1)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 1)


class ClaimFenceTests(FencingTestCase):
    def test_only_the_current_generation_can_publish(self) -> None:
        service = self.service()
        admission = self.admit(service)
        first = service.claim_next(worker_id="worker-1", now=NOW)
        self.assertIsNotNone(first)
        # The claim expires before the running boundary, so a second Worker may
        # take over the work that provably never started.
        later = NOW + timedelta(minutes=1)
        self.repository.heartbeat_worker("worker-2", later)
        takeover = self.service(repository=self.connection()).claim_next(
            worker_id="worker-2", now=later
        )
        self.assertIsNotNone(takeover)
        assert takeover is not None and first is not None
        self.assertEqual(takeover.generation, first.generation + 1)
        takeover = service.begin_work(
            takeover, stage=TaskMachineStage.EXECUTION, now=later + timedelta(seconds=1)
        )

        # The stale owner can no longer extend, start, publish or settle.
        with self.assertRaises(TaskClaimFenceLost):
            service.heartbeat(first, now=NOW + timedelta(minutes=1, seconds=1))
        with self.assertRaises(TaskClaimFenceLost):
            service.begin_work(first, now=NOW + timedelta(minutes=1, seconds=1))
        item = self.item(service, takeover, now=later + timedelta(seconds=2))
        stale_item = replace(item, attempts=1, item_id="stale-item")
        with self.assertRaises(TaskClaimFenceLost):
            service.record_item(first, stale_item, now=later + timedelta(seconds=3))
        with self.assertRaises(TaskClaimFenceLost):
            service.begin_mutation(first, item, "move", now=later + timedelta(seconds=3))
        final = replace(
            self.repository.get_task(admission.task.task_id),
            status=PersistentTaskStatus.COMPLETED,
            completed_at=NOW + timedelta(minutes=2),
        )
        with self.assertRaises(TaskClaimFenceLost):
            service.settle(first, task=final, now=NOW + timedelta(minutes=2))

        # Nothing the stale owner attempted became durable.
        state = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertIsNone(state.mutation_state)
        self.assertEqual(self.repository.list_results(admission.task.task_id), ())
        # Only the current owner's boundary is durable; the stale frame's
        # aggregate publication wrote nothing.
        self.assertIs(
            self.repository.get_task(admission.task.task_id).status,
            PersistentTaskStatus.RUNNING,
        )

    def test_a_heartbeat_cannot_use_another_token_or_generation(self) -> None:
        service = self.service()
        self.admit(service)
        claim = service.claim_next(worker_id="worker-1", now=NOW)
        assert claim is not None
        for forged in (
            TaskClaimFence(claim.task_id, "worker-2", claim.claim_token, claim.generation, NOW),
            TaskClaimFence(claim.task_id, "worker-1", "another-token", claim.generation, NOW),
            TaskClaimFence(claim.task_id, "worker-1", claim.claim_token, 99, NOW),
        ):
            self.assertIsNone(self.repository.heartbeat_scheduled_claim(forged, lease_seconds=30))
        refreshed = service.heartbeat(claim, now=NOW + timedelta(seconds=5))
        self.assertGreater(refreshed.expires_at, claim.expires_at)

    def test_an_expired_claim_cannot_publish_anything(self) -> None:
        service = self.service()
        admission = self.admit(service)
        claim = self.started(service)
        item = self.item(service, claim)
        later = NOW + timedelta(minutes=5)
        with self.assertRaises(TaskClaimFenceLost):
            service.record_item(claim, item, now=later)
        with self.assertRaises(TaskClaimFenceLost):
            service.complete_item(
                claim,
                replace(item, status=TaskItemStatus.SUCCESS, updated_at=later),
                result=self.result(item),
                now=later,
            )
        self.assertEqual(self.repository.list_results(admission.task.task_id), ())
        self.assertIs(self.repository.get_item(item.item_id).status, TaskItemStatus.PROCESSING)

    def test_entered_work_is_not_reclaimed_after_its_lease_expires(self) -> None:
        service = self.service()
        admission = self.admit(service)
        claim = self.started(service)
        self.item(service, claim)
        later = NOW + timedelta(minutes=5)
        self.repository.heartbeat_worker("worker-2", later)
        # The Task entered a machine stage, so an expired lease alone is not
        # proof that nothing happened: it is never handed to another Worker.
        self.assertIsNone(
            self.service(repository=self.connection()).claim_next(worker_id="worker-2", now=later)
        )
        state = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertIs(state.queue_state, TaskQueueState.CLAIMED)
        self.assertEqual(state.claim_worker_id, "worker-1")
        self.assertEqual(state.claim_generation, 1)

    def test_queued_work_survives_a_restart_and_keeps_its_own_pin(self) -> None:
        service = self.service()
        admission = self.admit(service)
        self.repository.close()
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self.repository.close)

        pinned = self.connection()
        pinned.register_worker(
            "worker-pin",
            "pinned worker",
            5.0,
            ("organize",),
            "snapshot-1",
            "digest-1",
            SCHEMA_VERSION,
            NOW,
        )
        other = self.connection()
        other.register_worker(
            "worker-other-pin",
            "other pin worker",
            5.0,
            ("organize",),
            "snapshot-2",
            "digest-2",
            SCHEMA_VERSION,
            NOW,
        )
        self.assertIsNone(
            self.service(repository=other).claim_next(worker_id="worker-other-pin", now=NOW)
        )
        claim = self.service(repository=pinned).claim_next(worker_id="worker-pin", now=NOW)
        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual(claim.task.task_id, admission.task.task_id)
        self.assertEqual(claim.task.configuration_snapshot_id, "snapshot-1")
        self.assertEqual(claim.task.configuration_snapshot_digest, "digest-1")


class WorkerEligibilityTests(FencingTestCase):
    def test_only_an_eligible_registered_worker_claims(self) -> None:
        service = self.service()
        self.admit(service)
        with self.assertRaises(TaskWorkerRejected):
            service.claim_next(worker_id="unknown-worker", now=NOW)

        self.repository.stop_worker("worker-2", NOW)
        with self.assertRaises(TaskWorkerRejected):
            service.claim_next(worker_id="worker-2", now=NOW)

        self.repository.register_worker(
            "worker-old-schema",
            "old schema",
            5.0,
            ("organize",),
            None,
            None,
            SCHEMA_VERSION - 1,
            NOW,
        )
        with self.assertRaises(TaskWorkerRejected):
            service.claim_next(worker_id="worker-old-schema", now=NOW)

        self.repository.register_worker(
            "worker-other-command",
            "other command",
            5.0,
            ("files_transfer",),
            None,
            None,
            SCHEMA_VERSION,
            NOW,
        )
        self.assertIsNone(service.claim_next(worker_id="worker-other-command", now=NOW))

        self.repository.register_worker(
            "worker-no-command",
            "no command",
            5.0,
            (),
            None,
            None,
            SCHEMA_VERSION,
            NOW,
        )
        with self.assertRaises(TaskWorkerRejected):
            service.claim_next(worker_id="worker-no-command", now=NOW)

        # A live Worker with an elapsed heartbeat is not eligible either.
        with self.assertRaises(TaskWorkerRejected):
            service.claim_next(worker_id="worker-1", now=NOW + timedelta(minutes=10))

        self.assertIsNotNone(service.claim_next(worker_id="worker-1", now=NOW))


class ControlFenceTests(FencingTestCase):
    def test_a_heartbeat_never_invalidates_an_accepted_control_request(self) -> None:
        service = self.service()
        self.admit(service)
        claim = self.started(service)
        requested = service.request_control(
            claim.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=3)
        )
        self.assertEqual(requested.control_revision, 1)
        heartbeats = [
            service.heartbeat(claim, now=NOW + timedelta(seconds=4 + index)) for index in range(3)
        ]
        self.assertTrue(all(value.expires_at is not None for value in heartbeats))
        after = self.repository.get_task_scheduling(claim.task_id)
        self.assertIs(after.control_request, TaskControl.PAUSE)
        self.assertEqual(after.control_revision, 1)
        # The still-valid request acknowledges and settles normally.
        acknowledged = service.acknowledge_control(heartbeats[-1], now=NOW + timedelta(seconds=8))
        self.assertIs(acknowledged.queue_state, TaskQueueState.PAUSED)

    def test_an_acknowledgement_only_settles_the_request_it_observed(self) -> None:
        service = self.service()
        self.admit(service)
        claim = self.started(service)
        service.request_control(claim.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=3))
        # A concurrent escalation arrives between the owner's read and its ack.
        second = self.connection()
        self.service(repository=second).request_control(
            claim.task_id, TaskControl.CANCEL, now=NOW + timedelta(seconds=4)
        )
        observed = self.repository.get_task_scheduling(claim.task_id)
        self.assertEqual(observed.control_revision, 2)
        with self.assertRaises(TaskControlRejected):
            # The acknowledgement observed revision 1: it must not settle a
            # request the owner never saw.
            self.repository.release_scheduled_claim(
                claim.fence(NOW + timedelta(seconds=5)),
                task=replace(
                    self.repository.get_task(claim.task_id),
                    status=PersistentTaskStatus.PAUSED,
                ),
                items=(),
                queue_state=TaskQueueState.PAUSED,
                stage=None,
                expected_control_revision=1,
            )
        state = self.repository.get_task_scheduling(claim.task_id)
        self.assertIs(state.control_request, TaskControl.CANCEL)
        self.assertIs(state.queue_state, TaskQueueState.CLAIMED)
        settled = service.acknowledge_control(claim, now=NOW + timedelta(seconds=6))
        self.assertIs(settled.queue_state, TaskQueueState.SETTLED)
        self.assertIs(settled.control_request, TaskControl.CANCEL)

    def test_a_stale_owner_cannot_acknowledge_the_replacement_owners_claim(self) -> None:
        service = self.service()
        self.admit(service)
        first = service.claim_next(worker_id="worker-1", now=NOW)
        assert first is not None
        service.request_control(first.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=1))
        with self.assertRaises(TaskClaimFenceLost):
            service.acknowledge_control(
                replace(
                    first,
                    state=replace(first.state, claim_generation=first.generation + 5),
                ),
                now=NOW + timedelta(seconds=2),
            )
        self.assertIs(
            self.repository.get_task_scheduling(first.task_id).queue_state,
            TaskQueueState.CLAIMED,
        )

    def test_acknowledging_a_pause_retires_only_this_tasks_execution_locks(self) -> None:
        service = self.service()
        admission = self.admit(service)
        claim = self.started(service)
        self.repository.acquire(
            "local", "媒体/电影/A.mkv", claim.task_id, NOW, owner_token="round-1-a"
        )
        self.repository.acquire("local", "媒体/电影/A.srt", claim.task_id, NOW)
        other = self.admit(service, request_id="request-2", scope_path="媒体/剧集")
        self.repository.acquire("local", "媒体/剧集/B.mkv", other.task.task_id, NOW)
        service.request_control(claim.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=3))
        service.acknowledge_control(claim, now=NOW + timedelta(seconds=4))
        self.assertFalse(
            self.repository.lock_owned("local", "媒体/电影/A.mkv", claim.task_id, owner_token=None)
        )
        self.assertFalse(
            self.repository.lock_owned("local", "媒体/电影/A.srt", claim.task_id, owner_token=None)
        )
        self.assertTrue(self.repository.lock_owned("local", "媒体/剧集/B.mkv", other.task.task_id))
        self.assertEqual(self.service(capacity=2).capacity_use(), 1)
        self.assertIs(
            self.repository.get_task_scheduling(admission.task.task_id).queue_state,
            TaskQueueState.PAUSED,
        )

    def test_a_late_pause_cleanup_cannot_delete_the_next_rounds_lock(self) -> None:
        from mediaflow.application.task_scheduling import TaskSchedulingService

        service = self.service()
        admission = self.admit(service)
        claim = self.started(service)
        item = self.item(service, claim)
        self.repository.acquire(
            "local", item.source_path, claim.task_id, NOW, owner_token="round-1"
        )
        service.request_control(claim.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=3))
        paused_committed = threading.Event()

        original_release = self.repository.release_scheduled_claim

        def release_and_signal(*args, **kwargs):
            result = original_release(*args, **kwargs)
            if result is not None:
                paused_committed.set()
            return result

        self.repository.release_scheduled_claim = release_and_signal
        cleanup_release = threading.Event()

        class DelayedCleanup:
            def reclaim_task_locks(inner, task_id, *, owner_token=None):
                cleanup_release.wait(timeout=10)
                return self.repository.reclaim_task_locks(task_id, owner_token=owner_token)

        ack_service = TaskSchedulingService(self.repository, capacity=2, locks=DelayedCleanup())
        errors: list[BaseException] = []

        def acknowledge() -> None:
            try:
                ack_service.acknowledge_control(claim, now=NOW + timedelta(seconds=4))
            except BaseException as error:  # pragma: no cover - surfaced below
                errors.append(error)

        thread = threading.Thread(target=acknowledge)
        thread.start()
        self.assertTrue(paused_committed.wait(timeout=10))

        successor_repository = self.connection()
        successor = self.service(repository=successor_repository)
        requeued = successor.requeue(
            admission.task.task_id,
            expected_snapshot_id="snapshot-1",
            expected_snapshot_digest="digest-1",
            expected_control_revision=1,
            now=NOW + timedelta(seconds=5),
        )
        self.assertIs(requeued.queue_state, TaskQueueState.QUEUED)
        next_claim = successor.claim_next(worker_id="worker-2", now=NOW + timedelta(seconds=6))
        self.assertIsNotNone(next_claim)
        self.assertTrue(
            successor_repository.adopt_or_acquire(
                "local",
                item.source_path,
                admission.task.task_id,
                NOW + timedelta(seconds=7),
                owner_token="round-2",
            )
        )
        # The previous round's claim generation is stale: it cannot heartbeat,
        # publish or release the new owner's work even while its old token is
        # still in memory.
        stale_service = self.service(repository=self.connection())
        with self.assertRaises(TaskClaimFenceLost):
            stale_service.heartbeat(claim, now=NOW + timedelta(seconds=7))
        with self.assertRaises(TaskClaimFenceLost):
            stale_service.publish_task(
                claim,
                replace(
                    self.repository.get_task(admission.task.task_id),
                    updated_at=NOW + timedelta(seconds=7),
                ),
                now=NOW + timedelta(seconds=7),
            )

        cleanup_release.set()
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(
            successor_repository.lock_owned(
                "local",
                item.source_path,
                admission.task.task_id,
                owner_token="round-2",
            )
        )
        # The new owner's own conditional release is the only thing that may
        # retire its generation; a repeated cleanup is a harmless no-op.
        self.assertEqual(
            successor_repository.reclaim_task_locks(admission.task.task_id, owner_token="round-2"),
            1,
        )
        self.assertEqual(
            successor_repository.reclaim_task_locks(admission.task.task_id, owner_token="round-2"),
            0,
        )


class CancellationTests(FencingTestCase):
    def test_a_cancelled_human_wait_cannot_be_requeued(self) -> None:
        service = self.service()
        admission, claim, success_item = self.waiting_human(service, success_first=True)
        recorded = self.repository.list_results(admission.task.task_id)
        succeeded = self.repository.get_item(success_item.item_id)
        generation = self.repository.get_task_scheduling(admission.task.task_id).claim_generation

        cancelled = service.request_control(
            admission.task.task_id, TaskControl.CANCEL, now=NOW + timedelta(seconds=6)
        )
        self.assertIs(cancelled.queue_state, TaskQueueState.SETTLED)
        self.assertIs(cancelled.control_request, TaskControl.CANCEL)
        self.assertFalse(cancelled.holds_capacity)
        self.assertEqual(service.capacity_use(), 0)
        self.assertIs(
            self.repository.get_task(admission.task.task_id).status,
            PersistentTaskStatus.CANCELLED,
        )
        # A successful sibling and its Result are history, never rewritten by
        # the cancellation; the unfinished waiting sibling settles as cancelled.
        self.assertEqual(self.repository.get_item(success_item.item_id), succeeded)
        self.assertEqual(self.repository.list_results(admission.task.task_id), recorded)
        statuses = {
            item.item_id: item.status for item in self.repository.list_items(admission.task.task_id)
        }
        self.assertIs(statuses[success_item.item_id], TaskItemStatus.SUCCESS)
        waiting = next(
            item
            for item in self.repository.list_items(admission.task.task_id)
            if item.item_id != success_item.item_id
        )
        self.assertIs(waiting.status, TaskItemStatus.CANCELLED)

        with self.assertRaises(TaskControlRejected):
            service.requeue(
                admission.task.task_id,
                expected_snapshot_id="snapshot-1",
                expected_snapshot_digest="digest-1",
                expected_control_revision=cancelled.control_revision,
                now=NOW + timedelta(seconds=7),
            )
        repeated = service.request_control(
            admission.task.task_id, TaskControl.CANCEL, now=NOW + timedelta(seconds=8)
        )
        self.assertIs(repeated.queue_state, TaskQueueState.SETTLED)
        self.assertIs(repeated.control_request, TaskControl.CANCEL)
        stored = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertEqual(stored.claim_generation, generation)
        self.assertFalse(stored.holds_capacity)
        self.assertEqual(self.repository.list_results(admission.task.task_id), recorded)

    def test_a_cancelled_pause_cannot_be_requeued(self) -> None:
        service = self.service()
        admission = self.admit(service)
        claim = self.started(service)
        item = self.item(service, claim)
        self.repository.acquire(
            "local", item.source_path, claim.task_id, NOW, owner_token="round-1"
        )
        service.request_control(claim.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=3))
        paused = service.acknowledge_control(claim, now=NOW + timedelta(seconds=4))
        self.assertIs(paused.queue_state, TaskQueueState.PAUSED)
        generation = paused.claim_generation

        cancelled = service.request_control(
            claim.task_id, TaskControl.CANCEL, now=NOW + timedelta(seconds=5)
        )
        self.assertIs(cancelled.queue_state, TaskQueueState.SETTLED)
        self.assertIs(cancelled.control_request, TaskControl.CANCEL)
        self.assertEqual(service.capacity_use(), 0)
        self.assertIs(self.repository.get_item(item.item_id).status, TaskItemStatus.CANCELLED)
        self.assertFalse(
            self.repository.lock_owned("local", item.source_path, claim.task_id, owner_token=None)
        )
        with self.assertRaises(TaskControlRejected):
            service.requeue(
                admission.task.task_id,
                expected_snapshot_id="snapshot-1",
                expected_snapshot_digest="digest-1",
                expected_control_revision=cancelled.control_revision,
                now=NOW + timedelta(seconds=6),
            )
        stored = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertEqual(stored.claim_generation, generation)
        self.assertIs(stored.control_request, TaskControl.CANCEL)
        self.assertIs(
            self.repository.get_task(admission.task.task_id).status,
            PersistentTaskStatus.CANCELLED,
        )

    def test_cancel_and_requeue_resolve_in_transaction_order(self) -> None:
        service = self.service()
        admission, _, _ = self.waiting_human(service, request_id="request-cancel-first")
        other = self.service(repository=self.connection())
        cancelled = service.request_control(
            admission.task.task_id, TaskControl.CANCEL, now=NOW + timedelta(seconds=6)
        )
        with self.assertRaises(TaskControlRejected):
            other.requeue(
                admission.task.task_id,
                expected_snapshot_id="snapshot-1",
                expected_snapshot_digest="digest-1",
                expected_control_revision=cancelled.control_revision,
                now=NOW + timedelta(seconds=7),
            )
        self.assertIs(
            self.repository.get_task_scheduling(admission.task.task_id).queue_state,
            TaskQueueState.SETTLED,
        )

        second, _, _ = self.waiting_human(service, request_id="request-requeue-first")
        requeued = other.requeue(
            second.task.task_id,
            expected_snapshot_id="snapshot-1",
            expected_snapshot_digest="digest-1",
            expected_control_revision=0,
            now=NOW + timedelta(seconds=8),
        )
        self.assertIs(requeued.queue_state, TaskQueueState.QUEUED)
        cancelled_after = service.request_control(
            second.task.task_id, TaskControl.CANCEL, now=NOW + timedelta(seconds=9)
        )
        self.assertIs(cancelled_after.queue_state, TaskQueueState.SETTLED)
        self.assertIs(
            self.repository.get_task_scheduling(second.task.task_id).queue_state,
            TaskQueueState.SETTLED,
        )
        self.assertIs(
            self.repository.get_task(second.task.task_id).status,
            PersistentTaskStatus.CANCELLED,
        )
        self.assertEqual(service.capacity_use(), 0)


class MixedReleaseTests(FencingTestCase):
    def test_a_mixed_human_wait_keeps_the_slot_until_every_item_is_human(self) -> None:
        service = self.service(capacity=1)
        admission = self.admit(service)
        claim = self.started(service)
        waiting_item = self.item(service, claim, path="媒体/电影/A.mkv")
        processing_item = self.item(
            service, claim, path="媒体/电影/B.mkv", now=NOW + timedelta(seconds=3)
        )
        waiting = replace(
            waiting_item,
            status=TaskItemStatus.WAITING_CONFIRM,
            stage="waiting_confirm",
            updated_at=NOW + timedelta(seconds=4),
        )
        service.record_item(claim, waiting, now=NOW + timedelta(seconds=4))
        before_task = self.repository.get_task(claim.task_id)
        aggregate = replace(
            before_task,
            status=PersistentTaskStatus.PARTIAL_SUCCESS,
            total_items=2,
            completed_at=NOW + timedelta(seconds=4),
        )

        with self.assertRaises(TaskControlRejected):
            service.defer_to_human(
                claim, task=aggregate, items=(waiting,), now=NOW + timedelta(seconds=5)
            )
        state = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertIs(state.queue_state, TaskQueueState.CLAIMED)
        self.assertEqual(state.claim_worker_id, "worker-1")
        self.assertEqual(self.service(capacity=1).capacity_use(), 1)
        self.assertEqual(self.repository.get_task(admission.task.task_id), before_task)
        self.assertIs(
            self.repository.get_item(waiting_item.item_id).status,
            TaskItemStatus.WAITING_CONFIRM,
        )
        self.assertIs(
            self.repository.get_item(processing_item.item_id).status,
            TaskItemStatus.PROCESSING,
        )
        with self.assertRaises(TaskQueueFull):
            self.admit(
                self.service(capacity=1, repository=self.connection()),
                request_id="request-2",
            )

        service.complete_item(
            claim,
            replace(
                processing_item,
                status=TaskItemStatus.SUCCESS,
                stage="completed",
                updated_at=NOW + timedelta(seconds=6),
            ),
            result=self.result(processing_item),
            now=NOW + timedelta(seconds=6),
        )
        released = service.defer_to_human(
            claim, task=aggregate, items=(), now=NOW + timedelta(seconds=7)
        )
        self.assertIs(released.queue_state, TaskQueueState.WAITING_HUMAN)
        self.assertFalse(released.holds_capacity)
        self.assertEqual(self.service(capacity=1).capacity_use(), 0)
        with self.assertRaises(TaskClaimFenceLost):
            service.defer_to_human(claim, task=aggregate, items=(), now=NOW + timedelta(seconds=8))
        self.admit(service, request_id="request-2")
        self.assertEqual(self.service(capacity=1).capacity_use(), 1)


class WhollyHumanWaitingTests(FencingTestCase):
    def test_two_items_can_become_wholly_human_waiting_once(self) -> None:
        service = self.service(capacity=1)
        admission = self.admit(service)
        claim = self.started(service)
        first = self.item(service, claim, path="媒体/电影/A.mkv")
        second = self.item(service, claim, path="媒体/电影/B.mkv", now=NOW + timedelta(seconds=3))
        waiting_a = replace(
            first,
            status=TaskItemStatus.WAITING_CONFIRM,
            stage="waiting_confirm",
            updated_at=NOW + timedelta(seconds=4),
        )
        waiting_b = replace(
            second,
            status=TaskItemStatus.WAITING_METADATA,
            stage="waiting_metadata",
            updated_at=NOW + timedelta(seconds=4),
        )
        service.record_item(claim, waiting_a, now=NOW + timedelta(seconds=4))
        service.record_item(claim, waiting_b, now=NOW + timedelta(seconds=4))
        aggregate = replace(
            self.repository.get_task(claim.task_id),
            status=PersistentTaskStatus.PARTIAL_SUCCESS,
            total_items=2,
            completed_at=NOW + timedelta(seconds=4),
        )

        released = service.defer_to_human(
            claim, task=aggregate, items=(waiting_a,), now=NOW + timedelta(seconds=5)
        )
        self.assertIs(released.queue_state, TaskQueueState.WAITING_HUMAN)
        self.assertFalse(released.holds_capacity)
        self.assertEqual(self.service(capacity=1).capacity_use(), 0)
        # The successful release is not replayed by a late frame.
        with self.assertRaises(TaskClaimFenceLost):
            service.defer_to_human(claim, task=aggregate, items=(), now=NOW + timedelta(seconds=6))

        self.repository.close()
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self.repository.close)
        reopened = self.service(capacity=1)
        stored = reopened.state(admission.task.task_id)
        self.assertIs(stored.queue_state, TaskQueueState.WAITING_HUMAN)
        self.assertEqual(reopened.capacity_use(), 0)
        items = {item.item_id: item for item in self.repository.list_items(admission.task.task_id)}
        self.assertIs(items[first.item_id].status, TaskItemStatus.WAITING_CONFIRM)
        self.assertIs(items[second.item_id].status, TaskItemStatus.WAITING_METADATA)
        self.assertEqual(items[first.item_id].attempts, 1)
        self.assertEqual(items[second.item_id].attempts, 1)
        self.assertEqual(self.repository.list_results(admission.task.task_id), ())


class ReleaseAdmissionRaceTests(FencingTestCase):
    def test_a_release_and_a_new_admission_never_overbook_the_last_slot(self) -> None:
        service = self.service(capacity=1)
        self.admit(service)
        claim = self.started(service)
        item = self.item(service, claim)
        waiting = replace(
            item,
            status=TaskItemStatus.WAITING_CONFIRM,
            stage="waiting_confirm",
            updated_at=NOW + timedelta(seconds=3),
        )
        service.record_item(claim, waiting, now=NOW + timedelta(seconds=3))
        aggregate = replace(
            self.repository.get_task(claim.task_id),
            status=PersistentTaskStatus.PARTIAL_SUCCESS,
            total_items=1,
            completed_at=NOW + timedelta(seconds=3),
        )

        barrier = threading.Barrier(2)
        outcomes: dict[str, object] = {}
        guard = threading.Lock()

        def release() -> None:
            repository = SQLiteTaskRepository(self.database)
            try:
                contender = self.service(capacity=1, repository=repository)
                barrier.wait(timeout=10)
                try:
                    result = contender.defer_to_human(
                        claim, task=aggregate, items=(waiting,), now=NOW + timedelta(seconds=4)
                    )
                except (TaskControlRejected, TaskClaimFenceLost) as error:
                    result = error
            finally:
                repository.close()
            with guard:
                outcomes["release"] = result

        def admit_new() -> None:
            repository = SQLiteTaskRepository(self.database)
            try:
                contender = self.service(capacity=1, repository=repository)
                barrier.wait(timeout=10)
                try:
                    result = self.admit(contender, request_id="request-2")
                except TaskQueueFull as error:
                    result = error
            finally:
                repository.close()
            with guard:
                outcomes["admit"] = result

        threads = [threading.Thread(target=release), threading.Thread(target=admit_new)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        released = outcomes["release"]
        admitted = outcomes["admit"]
        self.assertNotIsInstance(released, Exception)
        if isinstance(admitted, TaskQueueFull):
            self.assertEqual(self.service(capacity=1).capacity_use(), 0)
        else:
            self.assertEqual(self.service(capacity=1).capacity_use(), 1)
        with sqlite3.connect(self.database) as connection:
            capacity_rows = connection.execute(
                "SELECT COUNT(*) FROM task_scheduling WHERE queue_state IN ('queued','claimed')"
            ).fetchone()[0]
            orphan_rows = connection.execute(
                "SELECT COUNT(*) FROM task_scheduling "
                "LEFT JOIN tasks ON tasks.task_id=task_scheduling.task_id "
                "WHERE tasks.task_id IS NULL"
            ).fetchone()[0]
        self.assertLessEqual(capacity_rows, 1)
        self.assertEqual(orphan_rows, 0)


class CrossTaskPublicationTests(FencingTestCase):
    def test_a_claim_can_only_publish_its_own_task(self) -> None:
        service = self.service()
        first = self.admit(service, request_id="request-a")
        second = self.admit(service, request_id="request-b")
        claim_a = self.started(service, worker="worker-1")
        claim_b = self.started(service, worker="worker-2")
        item_a = self.item(service, claim_a, path="媒体/电影/A.mkv")
        waiting_a = replace(
            item_a,
            status=TaskItemStatus.WAITING_CONFIRM,
            stage="waiting_confirm",
            updated_at=NOW + timedelta(seconds=3),
        )
        service.record_item(claim_a, waiting_a, now=NOW + timedelta(seconds=3))
        task_a = self.repository.get_task(first.task.task_id)
        state_a = self.repository.get_task_scheduling(first.task.task_id)
        state_b = self.repository.get_task_scheduling(second.task.task_id)

        with self.assertRaises(TaskSchedulingError):
            service.defer_to_human(
                claim_b,
                task=task_a,
                items=(waiting_a,),
                now=NOW + timedelta(seconds=4),
            )
        with self.assertRaises(TaskSchedulingError):
            self.repository.release_scheduled_claim(
                claim_b.fence(NOW + timedelta(seconds=4)),
                task=task_a,
                items=(waiting_a,),
                queue_state=TaskQueueState.WAITING_HUMAN,
                stage=None,
            )
        self.assertEqual(self.repository.get_task_scheduling(first.task.task_id), state_a)
        self.assertEqual(self.repository.get_task_scheduling(second.task.task_id), state_b)
        self.assertIs(
            self.repository.get_task(first.task.task_id).status,
            PersistentTaskStatus.RUNNING,
        )
        self.assertIs(
            self.repository.get_item(item_a.item_id).status,
            TaskItemStatus.WAITING_CONFIRM,
        )
        self.assertEqual(service.capacity_use(), 2)

        released = service.defer_to_human(
            claim_a,
            task=replace(
                task_a,
                status=PersistentTaskStatus.PARTIAL_SUCCESS,
                completed_at=NOW + timedelta(seconds=5),
            ),
            items=(),
            now=NOW + timedelta(seconds=5),
        )
        self.assertIs(released.queue_state, TaskQueueState.WAITING_HUMAN)
        self.assertIs(
            self.repository.get_task_scheduling(second.task.task_id).queue_state,
            TaskQueueState.CLAIMED,
        )


class UncertainEffectTests(FencingTestCase):
    def test_an_in_flight_mutation_is_never_reclaimed_or_replayed(self) -> None:
        service = self.service()
        admission = self.admit(service)
        claim = self.started(service)
        item = self.item(service, claim)
        service.begin_mutation(claim, item, "move", now=NOW + timedelta(seconds=3))
        state = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertEqual(state.mutation_state, TASK_MUTATION_IN_FLIGHT)
        self.assertEqual(state.mutation_item_id, item.item_id)
        self.assertEqual(state.mutation_action, "move")

        later = NOW + timedelta(minutes=5)
        self.repository.heartbeat_worker("worker-2", later)
        self.assertIsNone(
            self.service(repository=self.connection()).claim_next(worker_id="worker-2", now=later)
        )
        # Pausing, cancelling or settling is refused while the effect is unknown,
        # so a requested control can never force the slot (or the uncertainty)
        # away.  Recording the request itself stays possible: it is the operator's
        # durable intent, and the owner acknowledges it at a proven boundary.
        service.request_control(claim.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=4))
        with self.assertRaises(TaskControlRejected):
            service.acknowledge_control(claim, now=NOW + timedelta(seconds=5))

        self.repository.close()
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self.repository.close)
        restarted = self.service()
        persisted = restarted.state(admission.task.task_id)
        self.assertEqual(persisted.mutation_state, TASK_MUTATION_IN_FLIGHT)
        self.assertEqual(persisted.queue_state, TaskQueueState.CLAIMED)
        with self.assertRaises(TaskControlRejected):
            restarted.requeue(
                admission.task.task_id,
                expected_snapshot_id="snapshot-1",
                expected_snapshot_digest="digest-1",
                now=later,
            )

    def test_an_in_flight_mutation_blocks_a_second_boundary(self) -> None:
        service = self.service()
        self.admit(service)
        claim = self.started(service)
        first = self.item(service, claim)
        second = self.item(service, claim, path="媒体/电影/B.mkv")
        service.begin_mutation(claim, first, "move", now=NOW + timedelta(seconds=3))
        with self.assertRaises(TaskSchedulingError):
            service.begin_mutation(claim, second, "move", now=NOW + timedelta(seconds=4))
        state = self.repository.get_task_scheduling(claim.task_id)
        self.assertEqual(state.mutation_item_id, first.item_id)

    def test_the_verified_outcome_of_the_affected_item_clears_the_boundary(self) -> None:
        service = self.service()
        admission = self.admit(service)
        claim = self.started(service)
        item = self.item(service, claim)
        service.begin_mutation(claim, item, "move", now=NOW + timedelta(seconds=3))
        service.complete_item(
            claim,
            replace(
                item,
                status=TaskItemStatus.SUCCESS,
                stage="completed",
                updated_at=NOW + timedelta(seconds=4),
            ),
            result=self.result(item),
            now=NOW + timedelta(seconds=4),
        )
        state = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertIsNone(state.mutation_state)
        self.assertIsNone(state.mutation_item_id)
        final = replace(
            self.repository.get_task(claim.task_id),
            status=PersistentTaskStatus.COMPLETED,
            completed_at=NOW + timedelta(seconds=5),
            total_items=1,
            completed_items=1,
        )
        settled = service.settle(claim, task=final, now=NOW + timedelta(seconds=5))
        self.assertIs(settled.queue_state, TaskQueueState.SETTLED)
        self.assertEqual(self.service().capacity_use(), 0)


if __name__ == "__main__":
    unittest.main()
