"""The Task-owned scheduling lifecycle: admission → claim → publication → re-entry.

Every assertion runs against a real temporary SQLite database through the
application service, so the durable value — not an in-memory model — is what the
tests read back.  The kernel deliberately has no production entrance yet: these
tests are the only callers, which is exactly what T9 (a clean transition
boundary) has to prove alongside the legacy paths staying untouched.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.media_evidence import PipelineEvidence
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.domain.task_scheduling import (
    TASK_MUTATION_IN_FLIGHT,
    TaskAdmissionConflict,
    TaskControl,
    TaskControlRejected,
    TaskItemPublication,
    TaskMachineStage,
    TaskQueueFull,
    TaskQueueState,
    TaskResultConflict,
    TaskSchedulingBypass,
    TaskSchedulingError,
    TaskTrigger,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository


def mediaflow_package_path() -> str:
    import mediaflow

    return mediaflow.__file__ or ""


NOW = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)


def _admit(service, *, request_id="request-1", principal="operator", **overrides):
    arguments = {
        "execute_authorized": True,
        "trigger": TaskTrigger.MANUAL,
        "principal": principal,
        "request_id": request_id,
        "scope_path": "媒体/电影",
        "item_limit": 10,
        "configuration_snapshot_id": "snapshot-1",
        "configuration_snapshot_digest": "digest-1",
    }
    arguments.update(overrides)
    return service.admit("organize", **arguments)


def _result(item, *, status="success", certainty="verified_complete", uncertain_effects=()):
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
        status,
        datetime(2026, 10, 30, 9, 0, tzinfo=UTC),
        effect_certainty=certainty,
        uncertain_effects=tuple(uncertain_effects),
    )


def _evidence(item, *, outcome="planned"):
    return PipelineEvidence(
        evidence_id=f"evidence-{item.item_id}-{item.attempts}",
        task_id=item.task_id,
        item_id=item.item_id,
        attempts=item.attempts,
        source_storage_id=item.storage_id,
        source_path=item.source_path,
        captured_at=datetime(2026, 10, 30, 9, 0, tzinfo=UTC),
        configuration_snapshot_id="snapshot-1",
        configuration_snapshot_digest="digest-1",
        outcome=outcome,
        sections={},
    )


class SchedulingKernelTestCase(unittest.TestCase):
    """A real runtime database plus the kernel's application service."""

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

    def service(self, *, capacity=None, repository=None):
        from mediaflow.application.task_scheduling import TaskSchedulingService

        return TaskSchedulingService(
            repository or self.repository,
            capacity=self.capacity if capacity is None else capacity,
            locks=repository or self.repository,
        )

    def claimed(self, service, *, now=None, worker="worker-1"):
        claim = service.claim_next(worker_id=worker, now=now or NOW)
        self.assertIsNotNone(claim)
        assert claim is not None
        return service.begin_work(
            claim, stage=TaskMachineStage.ANALYSIS, now=(now or NOW) + timedelta(seconds=1)
        )

    def item(self, service, claim, path="媒体/电影/A.mkv", *, now=None):
        return service.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path=path,
            source_display=path,
            source_storage_path=path,
            now=now or NOW + timedelta(seconds=2),
        )

    def reopen(self):
        self.repository.close()
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self.repository.close)
        return self.repository

    def superseded_marker(self, item_id: str) -> str | None:
        row = self.repository._connection.execute(
            "SELECT superseded_by_task_id FROM task_items WHERE item_id=?", (item_id,)
        ).fetchone()
        return None if row is None else row["superseded_by_task_id"]

    def row_counts(self) -> dict[str, int]:
        names = ("tasks", "task_items", "task_results", "task_scheduling")
        with sqlite3.connect(self.database) as connection:
            return {
                name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in names
            }


class AdmissionTests(SchedulingKernelTestCase):
    def test_admission_commits_one_queued_task_with_its_own_slot(self) -> None:
        service = self.service()
        admission = _admit(service)

        self.assertFalse(admission.duplicate)
        self.assertIs(admission.task.status, PersistentTaskStatus.PENDING)
        self.assertIs(admission.state.queue_state, TaskQueueState.QUEUED)
        self.assertTrue(admission.state.holds_capacity)
        self.assertIsNone(admission.task.started_at)
        self.assertEqual(admission.task.configuration_snapshot_id, "snapshot-1")
        self.assertTrue(admission.task.execute_authorized)
        self.assertEqual(service.capacity_use(), 1)
        # One organizing work is one Task: the kernel mints no Job object.
        self.assertEqual(
            self.row_counts(),
            {
                "tasks": 1,
                "task_items": 0,
                "task_results": 0,
                "task_scheduling": 1,
            },
        )

        # Reopen: the same identity, pin, slot and admission facts read back.
        repository = self.reopen()
        reopened = self.service(repository=repository)
        task, state = reopened.inspect(admission.task.task_id)
        self.assertEqual(task.configuration_snapshot_id, "snapshot-1")
        self.assertEqual(task.configuration_snapshot_digest, "digest-1")
        self.assertEqual(task.scope_path, "媒体/电影")
        self.assertEqual(task.item_limit, 10)
        self.assertEqual(state.admission_principal, "operator")
        self.assertEqual(state.admission_request_id, "request-1")
        self.assertIs(state.admission_trigger, TaskTrigger.MANUAL)
        self.assertEqual(reopened.capacity_use(), 1)
        # Reading, constructing the service and reopening start no work.
        self.assertEqual(repository.list_items(task.task_id), ())
        self.assertEqual(repository.list_results(task.task_id), ())
        self.assertIsNone(repository.get_item("any-item"))

    def test_full_capacity_leaves_no_orphan_task_and_no_authority(self) -> None:
        service = self.service(capacity=1)
        first = _admit(service)
        before = self.row_counts()

        with self.assertRaises(TaskQueueFull):
            _admit(service, request_id="request-2", principal="other")

        self.assertEqual(self.row_counts(), before)
        self.assertEqual(service.capacity_use(), 1)
        # The existing waiting work is untouched and its authority unconsumed.
        task, state = service.inspect(first.task.task_id)
        self.assertIs(state.queue_state, TaskQueueState.QUEUED)
        self.assertTrue(task.execute_authorized)
        self.assertIsNone(task.completed_at)

    def test_exact_duplicate_converges_even_at_full_capacity(self) -> None:
        service = self.service(capacity=1)
        admission = _admit(service)

        duplicate = _admit(service)
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(duplicate.task.task_id, admission.task.task_id)
        self.assertEqual(service.capacity_use(), 1)

        with self.assertRaises(TaskAdmissionConflict):
            _admit(service, scope_path="媒体/剧集")
        with self.assertRaises(TaskAdmissionConflict):
            _admit(service, execute_authorized=False)

        # A different principal reusing the same request identity is not merged.
        other = self.service(capacity=2)
        separate = _admit(other, principal="another-operator")
        self.assertFalse(separate.duplicate)
        self.assertNotEqual(separate.task.task_id, admission.task.task_id)

    def test_repeated_request_of_completed_work_still_converges(self) -> None:
        service = self.service(capacity=1)
        admission = _admit(service)
        claim = self.claimed(service)
        final = replace(
            self.repository.get_task(claim.task_id),
            status=PersistentTaskStatus.COMPLETED,
            completed_at=NOW + timedelta(seconds=20),
        )
        service.settle(claim, task=final, now=NOW + timedelta(seconds=20))
        self.assertEqual(service.capacity_use(), 0)

        duplicate = _admit(service)
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(duplicate.task.task_id, admission.task.task_id)

    def test_machine_timed_stability_wait_keeps_one_slot(self) -> None:
        service = self.service(capacity=1)
        admission = _admit(
            service,
            stage=TaskMachineStage.STABILITY_WAIT,
            eligible_at=NOW + timedelta(minutes=5),
        )
        self.assertEqual(service.capacity_use(), 1)
        self.assertIsNone(service.claim_next(worker_id="worker-1", now=NOW))
        with self.assertRaises(TaskQueueFull):
            _admit(service, request_id="request-2")
        later = NOW + timedelta(minutes=6)
        self.repository.heartbeat_worker("worker-1", later)
        claim = service.claim_next(worker_id="worker-1", now=later)
        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual(claim.task.task_id, admission.task.task_id)

    def test_many_items_and_attempts_count_as_one_task(self) -> None:
        service = self.service(capacity=1)
        _admit(service)
        claim = self.claimed(service)
        for index in range(3):
            self.item(service, claim, path=f"媒体/电影/{index}.mkv")
        first = self.repository.list_items(claim.task_id)[0]
        # A provably effect-free attempt may continue; that is a new attempt of
        # the same source, not a replay of a settled outcome.
        service.complete_item(
            claim,
            replace(
                first,
                status=TaskItemStatus.FAILED,
                stage="failed",
                updated_at=NOW + timedelta(seconds=3),
            ),
            result=_result(first, status="failed", certainty="none"),
            now=NOW + timedelta(seconds=3),
        )
        second = service.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path=first.source_path,
            source_display=first.source_path,
            now=NOW + timedelta(seconds=10),
        )
        self.assertEqual(second.attempts, 2)
        self.assertEqual(service.capacity_use(), 1)
        self.assertEqual(len(self.repository.list_items(claim.task_id)), 3)

    def test_analysis_only_admission_never_becomes_execute_authorized(self) -> None:
        service = self.service()
        admission = _admit(service, execute_authorized=False)
        claim = self.claimed(service)
        item = self.item(service, claim)
        # A Worker publication may not upgrade the admitted authority.
        with self.assertRaises(TaskSchedulingError):
            service.publish_task(
                claim,
                replace(self.repository.get_task(claim.task_id), execute_authorized=True),
                now=NOW + timedelta(seconds=3),
            )
        service.complete_item(
            claim,
            replace(
                item,
                status=TaskItemStatus.DRY_RUN,
                stage="completed",
                updated_at=NOW + timedelta(seconds=3),
            ),
            result=_result(item, status="dry_run", certainty="none"),
            now=NOW + timedelta(seconds=3),
        )
        final = replace(
            self.repository.get_task(claim.task_id),
            status=PersistentTaskStatus.PARTIAL_SUCCESS,
            completed_at=NOW + timedelta(seconds=4),
        )
        service.settle(claim, task=final, now=NOW + timedelta(seconds=4))
        stored = self.repository.get_task(admission.task.task_id)
        self.assertFalse(stored.execute_authorized)
        self.assertFalse(self.repository.get_task_scheduling(admission.task.task_id).holds_capacity)
        self.assertEqual(self.service().capacity_use(), 0)

    def test_trigger_label_alone_grants_nothing(self) -> None:
        service = self.service(capacity=3)
        for trigger in (TaskTrigger.MANUAL, TaskTrigger.SCHEDULE, TaskTrigger.RUN_ONCE):
            admission = _admit(
                service,
                request_id=f"request-{trigger.value}",
                trigger=trigger,
                execute_authorized=False,
            )
            self.assertFalse(admission.task.execute_authorized)
            self.assertIs(admission.state.admission_trigger, trigger)


class SharedCapacityTests(SchedulingKernelTestCase):
    """One system-owned allowance is shared by every organizing origin."""

    def test_manual_and_automation_work_share_one_capacity_and_claim_queue(self) -> None:
        service = self.service(capacity=2)
        manual = _admit(service, request_id="manual-1")
        automation = _admit(
            service,
            request_id="automation-1",
            trigger=TaskTrigger.SCHEDULE,
            principal="automation-scheduler",
        )

        self.assertEqual(service.capacity_use(), 2)
        with self.assertRaises(TaskQueueFull):
            _admit(
                service,
                request_id="manual-2",
            )
        self.assertEqual(service.capacity_use(), 2)
        self.assertIs(service.state(manual.task.task_id).queue_state, TaskQueueState.QUEUED)
        self.assertIs(service.state(automation.task.task_id).queue_state, TaskQueueState.QUEUED)

        # One claim queue: the oldest admitted work is claimed regardless of the
        # origin label, and releasing it frees the shared slot for new work.
        claim = service.claim_next(worker_id="worker-1", now=NOW)
        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual(claim.task_id, manual.task.task_id)

    def test_requeue_uses_the_current_shared_allowance(self) -> None:
        service = self.service(capacity=1)
        first = _admit(service, request_id="manual-1")
        claim = self.claimed(service)
        service.defer_to_human(
            claim,
            task=replace(
                self.repository.get_task(first.task.task_id),
                status=PersistentTaskStatus.RUNNING,
                updated_at=NOW + timedelta(seconds=2),
            ),
            now=NOW + timedelta(seconds=2),
        )
        _admit(service, request_id="manual-2")
        with self.assertRaises(TaskQueueFull):
            service.requeue(
                first.task.task_id,
                expected_snapshot_id="snapshot-1",
                expected_snapshot_digest="digest-1",
                now=NOW + timedelta(seconds=3),
            )
        self.assertIs(service.state(first.task.task_id).queue_state, TaskQueueState.WAITING_HUMAN)


class CapacityTransitionTests(SchedulingKernelTestCase):
    def test_wholly_human_waiting_releases_the_slot_but_keeps_the_work(self) -> None:
        service = self.service(capacity=1)
        admission = _admit(service)
        claim = self.claimed(service)
        waiting = self.item(service, claim)
        waiting = replace(
            waiting,
            status=TaskItemStatus.WAITING_CONFIRM,
            stage="waiting_confirm",
            updated_at=NOW + timedelta(seconds=3),
        )
        aggregate = replace(
            self.repository.get_task(claim.task_id),
            status=PersistentTaskStatus.PARTIAL_SUCCESS,
            total_items=1,
            completed_items=0,
            completed_at=NOW + timedelta(seconds=3),
        )
        released = service.defer_to_human(
            claim,
            task=aggregate,
            items=(waiting,),
            now=NOW + timedelta(seconds=3),
        )
        self.assertIs(released.queue_state, TaskQueueState.WAITING_HUMAN)
        self.assertFalse(released.holds_capacity)
        self.assertEqual(service.capacity_use(), 0)
        # The source still belongs to this Task and its saved decision survives.
        items = self.repository.list_items(admission.task.task_id)
        self.assertEqual([item.status for item in items], [TaskItemStatus.WAITING_CONFIRM])
        duplicate = _admit(service)
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(duplicate.task.task_id, admission.task.task_id)
        # The freed slot admits a genuinely different work.
        _admit(service, request_id="request-2")
        self.assertEqual(service.capacity_use(), 1)

    def test_finished_boundary_does_not_release_a_processing_sibling(self) -> None:
        """The CLI's finished-pass flag never hides real remaining machine work."""

        service = self.service(capacity=1)
        _admit(service)
        claim = self.claimed(service)
        failed = self.item(service, claim, "媒体/电影/A.mkv")
        self.item(service, claim, "媒体/电影/B.mkv", now=NOW + timedelta(seconds=3))
        service.begin_mutation(claim, failed, "COPY", now=NOW + timedelta(seconds=3))
        service.complete_item(
            claim,
            replace(
                failed,
                status=TaskItemStatus.PARTIAL,
                stage="failed",
                updated_at=NOW + timedelta(seconds=4),
            ),
            result=_result(
                failed,
                status="partial",
                certainty="attempted_unverified",
                uncertain_effects=("mutation_outcome",),
            ),
            now=NOW + timedelta(seconds=4),
        )
        items = self.repository.list_items(claim.task_id)
        with self.assertRaises(TaskControlRejected):
            service.settle(
                claim,
                task=replace(
                    self.repository.get_task(claim.task_id),
                    status=PersistentTaskStatus.PARTIAL_SUCCESS,
                    completed_at=NOW + timedelta(seconds=5),
                ),
                items=items,
                now=NOW + timedelta(seconds=5),
                close_recorded_unknown_boundary=True,
            )
        state = self.repository.get_task_scheduling(claim.task_id)
        self.assertEqual(TaskQueueState.CLAIMED, state.queue_state)
        self.assertTrue(state.mutation_in_flight)
        self.assertEqual(1, service.capacity_use())
        self.assertIs(
            self.repository.get_item(failed.item_id).status,
            TaskItemStatus.PARTIAL,
        )

    def test_finished_settlement_counts_a_superseded_item_without_republishing_it(self):
        """A batch whose failed file was handed to newer work still settles.

        The old owner must include that file's recorded outcome in its honest
        aggregate, but it may never re-publish the handed-off row; reading the
        old terminal state and writing a new one are different acts.
        """

        service = self.service(capacity=1)
        _admit(service)
        claim = self.claimed(service)
        superseded = self.item(service, claim, "媒体/电影/A.mkv")
        sibling = self.item(service, claim, "媒体/电影/B.mkv", now=NOW + timedelta(seconds=3))
        service.begin_mutation(claim, superseded, "COPY", now=NOW + timedelta(seconds=3))
        superseded = replace(
            superseded,
            status=TaskItemStatus.FAILED,
            stage="failed",
            updated_at=NOW + timedelta(seconds=4),
        )
        service.complete_item(
            claim,
            superseded,
            result=_result(
                superseded,
                status="failed",
                certainty="attempted_unverified",
                uncertain_effects=("mutation_outcome",),
            ),
            now=NOW + timedelta(seconds=4),
        )
        self.assertTrue(self.repository.get_task_scheduling(claim.task_id).mutation_in_flight)
        handoff = self.repository.hand_off_superseded_source_owner(
            storage_id=superseded.storage_id,
            source_path=superseded.source_path,
            storage_path=superseded.source_storage_path,
            resource_library_id=superseded.resource_library_id,
            successor_task_id="newer-confirmed-task",
            now=NOW + timedelta(seconds=5),
        )
        self.assertIsNotNone(handoff)
        # The sibling is real remaining work: the old batch keeps its claim and
        # its one slot while the handed-off file is fenced per file.
        kept = self.repository.get_task_scheduling(claim.task_id)
        self.assertEqual(TaskQueueState.CLAIMED, kept.queue_state)
        self.assertEqual(service.capacity_use(), 1)
        self.assertIsNone(kept.mutation_state)
        self.assertEqual("newer-confirmed-task", self.superseded_marker(superseded.item_id))

        # The remaining sibling finishes normally.
        finished_sibling = service.complete_item(
            claim,
            replace(
                sibling,
                status=TaskItemStatus.SUCCESS,
                stage="completed",
                updated_at=NOW + timedelta(seconds=6),
            ),
            result=_result(sibling),
            now=NOW + timedelta(seconds=6),
        )
        items = self.repository.list_items(claim.task_id)
        kept_superseded = self.repository.get_item(superseded.item_id)
        self.assertEqual("newer-confirmed-task", self.superseded_marker(superseded.item_id))
        self.assertIs(kept_superseded.status, TaskItemStatus.FAILED)
        (kept_result,) = tuple(
            result
            for result in self.repository.list_results(claim.task_id)
            if result.item_id == superseded.item_id
        )
        self.assertEqual("attempted_unverified", kept_result.effect_certainty)
        self.assertEqual(("mutation_outcome",), kept_result.uncertain_effects)

        final = replace(
            self.repository.get_task(claim.task_id),
            status=PersistentTaskStatus.PARTIAL_SUCCESS,
            completed_at=NOW + timedelta(seconds=7),
        )
        settled = service.settle(
            claim,
            task=final,
            items=items,
            now=NOW + timedelta(seconds=7),
        )
        self.assertEqual(TaskQueueState.SETTLED, settled.queue_state)
        self.assertEqual(service.capacity_use(), 0)
        # The handed-off row and its Result were read for the aggregate, never
        # rewritten by the old owner.
        after = self.repository.get_item(superseded.item_id)
        self.assertEqual(kept_superseded, after)
        self.assertEqual(
            (kept_result,),
            tuple(
                result
                for result in self.repository.list_results(claim.task_id)
                if result.item_id == superseded.item_id
            ),
        )
        self.assertIs(
            self.repository.get_item(finished_sibling.item_id).status,
            TaskItemStatus.SUCCESS,
        )

    def test_claimed_work_keeps_its_slot_until_the_owner_acknowledges_pause(self) -> None:
        service = self.service(capacity=1)
        _admit(service)
        claim = self.claimed(service)
        item = self.item(service, claim)

        requested = service.request_control(
            claim.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=3)
        )
        self.assertIs(requested.control_request, TaskControl.PAUSE)
        self.assertIs(requested.queue_state, TaskQueueState.CLAIMED)
        self.assertEqual(service.capacity_use(), 1)
        self.assertTrue(requested.holds_capacity)
        # Work cannot start again while the accepted request is unacknowledged.
        with self.assertRaises(TaskControlRejected):
            service.begin_work(claim, now=NOW + timedelta(seconds=4))

        acknowledged = service.acknowledge_control(claim, now=NOW + timedelta(seconds=5))
        self.assertIs(acknowledged.queue_state, TaskQueueState.PAUSED)
        self.assertFalse(acknowledged.holds_capacity)
        self.assertIsNotNone(acknowledged.control_acknowledged_at)
        self.assertEqual(service.capacity_use(), 0)
        paused_task = self.repository.get_task(claim.task_id)
        self.assertIs(paused_task.status, PersistentTaskStatus.PAUSED)
        self.assertFalse(paused_task.pause_requested)
        self.assertEqual(
            [value.status for value in self.repository.list_items(claim.task_id)],
            [TaskItemStatus.PAUSED],
        )
        # The paused source is still owned by this Task.
        self.assertEqual(self.repository.get_item(item.item_id).attempts, 1)

    def test_cancel_settles_the_slot_and_keeps_the_accepted_request(self) -> None:
        service = self.service(capacity=1)
        _admit(service)
        claim = self.claimed(service)
        self.item(service, claim)
        service.request_control(claim.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=3))
        escalated = service.request_control(
            claim.task_id, TaskControl.CANCEL, now=NOW + timedelta(seconds=4)
        )
        self.assertIs(escalated.control_request, TaskControl.CANCEL)
        self.assertEqual(escalated.control_revision, 2)
        with self.assertRaises(TaskControlRejected):
            service.request_control(
                claim.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=5)
            )

        acknowledged = service.acknowledge_control(claim, now=NOW + timedelta(seconds=6))
        self.assertIs(acknowledged.queue_state, TaskQueueState.SETTLED)
        self.assertIs(acknowledged.control_request, TaskControl.CANCEL)
        self.assertIs(
            self.repository.get_task(claim.task_id).status, PersistentTaskStatus.CANCELLED
        )
        self.assertEqual(
            [value.status for value in self.repository.list_items(claim.task_id)],
            [TaskItemStatus.CANCELLED],
        )
        self.assertEqual(service.capacity_use(), 0)

    def test_an_accepted_cancel_is_never_overwritten_by_a_terminal_outcome(self) -> None:
        service = self.service(capacity=1)
        _admit(service)
        claim = self.claimed(service)
        service.request_control(claim.task_id, TaskControl.CANCEL, now=NOW + timedelta(seconds=3))
        finished = replace(
            self.repository.get_task(claim.task_id),
            status=PersistentTaskStatus.COMPLETED,
            completed_at=NOW + timedelta(seconds=4),
        )
        with self.assertRaises(TaskControlRejected):
            service.settle(claim, task=finished, now=NOW + timedelta(seconds=4))
        stored = self.repository.get_task(claim.task_id)
        self.assertIs(stored.status, PersistentTaskStatus.RUNNING)
        acknowledged = service.acknowledge_control(claim, now=NOW + timedelta(seconds=5))
        self.assertIs(acknowledged.queue_state, TaskQueueState.SETTLED)
        self.assertIs(
            self.repository.get_task(claim.task_id).status, PersistentTaskStatus.CANCELLED
        )

    def test_pause_of_unclaimed_queued_work_settles_immediately(self) -> None:
        service = self.service(capacity=1)
        admission = _admit(service)
        state = service.request_control(admission.task.task_id, TaskControl.PAUSE, now=NOW)
        self.assertIs(state.queue_state, TaskQueueState.PAUSED)
        self.assertEqual(service.capacity_use(), 0)
        self.assertIsNone(service.claim_next(worker_id="worker-1", now=NOW + timedelta(seconds=1)))
        self.assertIs(
            self.repository.get_task(admission.task.task_id).status, PersistentTaskStatus.PAUSED
        )

    def test_requeue_reuses_the_same_task_and_rechecks_capacity(self) -> None:
        service = self.service(capacity=1)
        admission = _admit(service)
        claim = self.claimed(service)
        item = self.item(service, claim)
        service.complete_item(
            claim,
            replace(
                item,
                status=TaskItemStatus.SUCCESS,
                stage="completed",
                destination_storage_id="local",
                destination_path="Media/A/A.mkv",
                updated_at=NOW + timedelta(seconds=3),
            ),
            result=_result(item),
            now=NOW + timedelta(seconds=3),
        )
        service.request_control(claim.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=4))
        service.acknowledge_control(claim, now=NOW + timedelta(seconds=5))
        self.assertEqual(service.capacity_use(), 0)
        results_before = self.repository.list_results(admission.task.task_id)

        other = _admit(service, request_id="request-2")
        self.assertEqual(service.capacity_use(), 1)
        with self.assertRaises(TaskQueueFull):
            service.requeue(
                admission.task.task_id,
                expected_snapshot_id="snapshot-1",
                expected_snapshot_digest="digest-1",
                now=NOW + timedelta(seconds=6),
            )
        # Refusal changed nothing: state, saved results and pin stay exactly as
        # they were and no automatic continuation was registered.
        refused = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertIs(refused.queue_state, TaskQueueState.PAUSED)
        self.assertEqual(self.repository.list_results(admission.task.task_id), results_before)
        self.assertIs(
            self.repository.get_task(admission.task.task_id).status,
            PersistentTaskStatus.PAUSED,
        )

        # Once capacity is free again the *same* Task is re-admitted.
        claim_other = self.claimed(service, now=NOW + timedelta(seconds=7))
        service.settle(
            claim_other,
            task=replace(
                self.repository.get_task(other.task.task_id),
                status=PersistentTaskStatus.COMPLETED,
                completed_at=NOW + timedelta(seconds=8),
            ),
            now=NOW + timedelta(seconds=8),
        )
        requeued = service.requeue(
            admission.task.task_id,
            expected_snapshot_id="snapshot-1",
            expected_snapshot_digest="digest-1",
            now=NOW + timedelta(seconds=9),
        )
        self.assertIs(requeued.queue_state, TaskQueueState.QUEUED)
        self.assertIsNone(requeued.control_request)
        self.assertEqual(requeued.claim_generation, refused.claim_generation + 1)
        readmitted = self.repository.get_task(admission.task.task_id)
        self.assertIs(readmitted.status, PersistentTaskStatus.PENDING)
        self.assertEqual(readmitted.task_id, admission.task.task_id)
        self.assertEqual(readmitted.configuration_snapshot_id, "snapshot-1")
        self.assertTrue(readmitted.execute_authorized)
        self.assertEqual(len(self.repository.list_results(readmitted.task_id)), 1)

    def test_named_claim_takes_only_the_explicit_task(self) -> None:
        """A synchronous caller never leases an unrelated older queued Task."""

        service = self.service(capacity=2)
        older = _admit(service, request_id="older")
        own = _admit(service, request_id="own")
        older_claim = self.claimed(service)
        self.assertEqual(older.task.task_id, older_claim.task_id)
        self.repository.register_worker(
            "cli-worker",
            "cli worker",
            5.0,
            ("organize",),
            None,
            None,
            SCHEMA_VERSION,
            NOW,
        )
        self.repository.register_worker(
            "other-worker",
            "other worker",
            5.0,
            ("organize",),
            None,
            None,
            SCHEMA_VERSION,
            NOW,
        )

        # The named claim takes the caller's own Task even though the older
        # Task is still owned and would sort first in a global claim.
        own_claim = service.claim(
            own.task.task_id, worker_id="cli-worker", now=NOW + timedelta(seconds=1)
        )
        self.assertIsNotNone(own_claim)
        self.assertEqual(own.task.task_id, own_claim.task_id)
        self.assertEqual("cli-worker", own_claim.worker_id)

        # The same named Task cannot be taken by a second live owner, and the
        # older Task is still exactly where its first owner left it.
        self.assertIsNone(
            service.claim(
                own.task.task_id, worker_id="other-worker", now=NOW + timedelta(seconds=2)
            )
        )
        older_state = self.repository.get_task_scheduling(older.task.task_id)
        self.assertIs(older_state.queue_state, TaskQueueState.CLAIMED)
        self.assertEqual(older_claim.worker_id, older_state.claim_worker_id)

    def test_requeue_records_the_claiming_operator_separately(self) -> None:
        service = self.service(capacity=1)
        admission = _admit(service, principal="automation-scheduler")
        claim = self.claimed(service)
        service.request_control(claim.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=1))
        service.acknowledge_control(claim, now=NOW + timedelta(seconds=2))
        requeued = service.requeue(
            admission.task.task_id,
            expected_snapshot_id="snapshot-1",
            expected_snapshot_digest="digest-1",
            continuation_actor="operator-2",
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual("operator-2", requeued.continuation_actor)
        self.assertEqual("automation-scheduler", requeued.admission_principal)
        # Reopening the database reads the same two separate identities.
        with SQLiteTaskRepository(self.database) as reopened:
            state = reopened.get_task_scheduling(admission.task.task_id)
            self.assertEqual("operator-2", state.continuation_actor)
            self.assertEqual("automation-scheduler", state.admission_principal)

    def test_requeue_verifies_the_original_pin_and_observed_revision(self) -> None:
        service = self.service()
        admission = _admit(service)
        claim = self.claimed(service)
        service.request_control(claim.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=3))
        service.acknowledge_control(claim, now=NOW + timedelta(seconds=4))
        with self.assertRaises(TaskControlRejected):
            service.requeue(
                admission.task.task_id,
                expected_snapshot_id="other-snapshot",
                expected_snapshot_digest="digest-1",
                now=NOW + timedelta(seconds=5),
            )
        with self.assertRaises(TaskControlRejected):
            service.requeue(
                admission.task.task_id,
                expected_snapshot_id="snapshot-1",
                expected_snapshot_digest="digest-1",
                expected_control_revision=99,
                now=NOW + timedelta(seconds=5),
            )
        self.assertIs(
            self.repository.get_task_scheduling(admission.task.task_id).queue_state,
            TaskQueueState.PAUSED,
        )
        requeued = service.requeue(
            admission.task.task_id,
            expected_snapshot_id="snapshot-1",
            expected_snapshot_digest="digest-1",
            expected_control_revision=1,
            now=NOW + timedelta(seconds=6),
        )
        self.assertIs(requeued.queue_state, TaskQueueState.QUEUED)


class PublicationTests(SchedulingKernelTestCase):
    def test_item_result_and_evidence_commit_together(self) -> None:
        service = self.service()
        _admit(service)
        claim = self.claimed(service)
        item = self.item(service, claim)
        completed = replace(
            item,
            status=TaskItemStatus.SUCCESS,
            stage="completed",
            destination_storage_id="local",
            destination_path="Media/A/A.mkv",
            updated_at=NOW + timedelta(seconds=3),
        )
        service.complete_item(
            claim,
            completed,
            result=_result(item),
            evidence=_evidence(item),
            now=NOW + timedelta(seconds=3),
        )
        stored = self.repository.get_item(item.item_id)
        self.assertIs(stored.status, TaskItemStatus.SUCCESS)
        self.assertEqual(stored.destination_path, "Media/A/A.mkv")
        results = self.repository.list_results(item.task_id)
        self.assertEqual([value.result_id for value in results], [f"{item.item_id}:1"])
        self.assertEqual(len(self.repository.list_evidence_for_item(item.item_id)), 1)

    def test_a_later_attempt_cannot_replace_a_recorded_outcome(self) -> None:
        service = self.service()
        admission = _admit(service)
        claim = self.claimed(service)
        first = self.item(service, claim)
        # A failed analysis attempt that proves no effect may continue; a
        # success/ignore/dry-run outcome would not be allowed to start again.
        service.complete_item(
            claim,
            replace(
                first,
                status=TaskItemStatus.FAILED,
                stage="failed",
                updated_at=NOW + timedelta(seconds=3),
            ),
            result=_result(first, status="failed", certainty="none"),
            now=NOW + timedelta(seconds=3),
        )
        recorded = self.repository.list_results(first.task_id)

        second = service.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path=first.source_path,
            source_display=first.source_path,
            now=NOW + timedelta(seconds=4),
        )
        self.assertEqual(second.attempts, 2)
        # The previous attempt's Result is not writable again.
        with self.assertRaises(TaskResultConflict):
            self.repository.publish_scheduled_item_outcome(
                claim.fence(NOW + timedelta(seconds=5)),
                second,
                _result(first),
                None,
                clear_mutation=False,
            )
        self.assertEqual(self.repository.list_results(admission.task.task_id), recorded)
        service.complete_item(
            claim,
            replace(
                second,
                status=TaskItemStatus.SUCCESS,
                stage="completed",
                updated_at=NOW + timedelta(seconds=5),
            ),
            result=_result(second),
            now=NOW + timedelta(seconds=5),
        )
        self.assertEqual(
            [value.result_id for value in self.repository.list_results(first.task_id)],
            [f"{first.item_id}:1", f"{first.item_id}:2"],
        )

    def test_a_publication_cannot_re_point_an_item_or_result(self) -> None:
        service = self.service()
        _admit(service)
        claim = self.claimed(service)
        item = self.item(service, claim)
        with self.assertRaises(TaskSchedulingError):
            service.record_item(
                claim,
                replace(item, source_path="媒体/电影/other.mkv"),
                now=NOW + timedelta(seconds=3),
            )
        with self.assertRaises(TaskSchedulingError):
            service.complete_item(
                claim,
                replace(
                    item,
                    status=TaskItemStatus.SUCCESS,
                    updated_at=NOW + timedelta(seconds=3),
                ),
                result=replace(_result(item), item_id="another-item"),
                now=NOW + timedelta(seconds=3),
            )
        with self.assertRaises(TaskSchedulingError):
            service.complete_item(
                claim,
                replace(
                    item,
                    status=TaskItemStatus.SUCCESS,
                    updated_at=NOW + timedelta(seconds=3),
                ),
                result=replace(_result(item), source_path="媒体/电影/other.mkv"),
                now=NOW + timedelta(seconds=3),
            )
        self.assertEqual(self.repository.list_results(item.task_id), ())
        self.assertEqual(self.repository.get_item(item.item_id).status, TaskItemStatus.PROCESSING)

    def test_a_worker_cannot_rewrite_the_admitted_authority_or_pin(self) -> None:
        service = self.service()
        admission = _admit(service)
        claim = self.claimed(service)
        task = self.repository.get_task(claim.task_id)
        for changed in (
            replace(task, execute_authorized=True)
            if not task.execute_authorized
            else replace(task, execute_authorized=False),
            replace(task, configuration_snapshot_id="snapshot-2"),
            replace(task, item_limit=1),
            replace(task, scope_path="媒体/剧集"),
            replace(task, command="files_transfer"),
        ):
            with self.assertRaises(TaskSchedulingError):
                service.publish_task(claim, changed, now=NOW + timedelta(seconds=3))
        stored = self.repository.get_task(admission.task.task_id)
        self.assertEqual(stored.configuration_snapshot_id, "snapshot-1")
        self.assertEqual(stored.item_limit, 10)
        self.assertEqual(stored.scope_path, "媒体/电影")
        self.assertEqual(stored.command, "organize")

    def test_legacy_unfenced_writers_refuse_a_kernel_managed_task(self) -> None:
        service = self.service()
        admission = _admit(service)
        claim = self.claimed(service)
        item = self.item(service, claim)
        task = self.repository.get_task(claim.task_id)
        confirmed = self.repository.get_task(admission.task.task_id)

        with self.assertRaises(TaskSchedulingBypass):
            self.repository.update_task(replace(confirmed, status=PersistentTaskStatus.COMPLETED))
        with self.assertRaises(TaskSchedulingBypass):
            self.repository.upsert_item(item)
        with self.assertRaises(TaskSchedulingBypass):
            self.repository.append_result(_result(item))
        with self.assertRaises(TaskSchedulingBypass):
            self.repository.append_evidence(_evidence(item))
        with self.assertRaises(TaskSchedulingBypass):
            self.repository.complete_item_with_evidence(item, _result(item), None)
        with self.assertRaises(TaskSchedulingBypass):
            self.repository.request_task_pause(claim.task_id, NOW + timedelta(seconds=3))
        with self.assertRaises(TaskSchedulingBypass):
            self.repository.cancel_task_if_current(claim.task_id, updated_at=NOW)
        self.assertIs(self.repository.get_task(task.task_id).status, PersistentTaskStatus.RUNNING)
        self.assertEqual(self.repository.list_results(task.task_id), ())

    def test_legacy_work_keeps_its_original_writer_semantics(self) -> None:
        coordinator = PersistentTaskCoordinator(self.repository, self.repository)
        legacy = coordinator.create("organize", execute_authorized=True, scope_path="Media")
        self.assertIsNone(self.repository.get_task_scheduling(legacy.task_id))
        item = coordinator.begin_item(legacy.task_id, "local", "library", "In/a.mkv", "In/a.mkv")
        self.assertIs(item.status, TaskItemStatus.PROCESSING)
        coordinator.request_pause(legacy.task_id)
        paused = coordinator.acknowledge_pause(legacy.task_id)
        self.assertIs(paused.status, PersistentTaskStatus.PAUSED)
        # A legacy pending Task is never silently adopted by the kernel.
        service = self.service()
        self.assertIsNone(service.claim_next(worker_id="worker-1", now=NOW))
        self.assertEqual(service.capacity_use(), 0)


class ReplaySafetyTests(SchedulingKernelTestCase):
    def test_a_successful_item_is_never_started_or_mutated_again(self) -> None:
        service = self.service()
        _admit(service)
        claim = self.claimed(service)
        item = self.item(service, claim)
        service.complete_item(
            claim,
            replace(
                item,
                status=TaskItemStatus.SUCCESS,
                stage="completed",
                destination_storage_id="local",
                destination_path="Media/A/A.mkv",
                updated_at=NOW + timedelta(seconds=3),
            ),
            result=_result(item),
            now=NOW + timedelta(seconds=3),
        )
        recorded = self.repository.list_results(item.task_id)
        succeeded = self.repository.get_item(item.item_id)

        with self.assertRaises(TaskSchedulingError):
            service.begin_item(
                claim,
                storage_id=item.storage_id,
                resource_library_id=item.resource_library_id,
                source_path=item.source_path,
                source_display=item.source_path,
                now=NOW + timedelta(seconds=4),
            )
        with self.assertRaises(TaskSchedulingError):
            service.begin_mutation(claim, succeeded, "move", now=NOW + timedelta(seconds=4))
        with self.assertRaises(TaskSchedulingError):
            service.record_item(
                claim,
                replace(
                    succeeded,
                    status=TaskItemStatus.PROCESSING,
                    stage="pipeline",
                    updated_at=NOW + timedelta(seconds=4),
                ),
                now=NOW + timedelta(seconds=4),
            )
        # A direct repository start is refused by the same transaction rule.
        with self.assertRaises(TaskSchedulingError):
            self.repository.upsert_scheduled_item(
                claim.fence(NOW + timedelta(seconds=5)),
                replace(
                    succeeded,
                    status=TaskItemStatus.PROCESSING,
                    stage="pipeline",
                    attempts=2,
                    updated_at=NOW + timedelta(seconds=5),
                ),
                stage=TaskItemPublication.START,
            )

        stored = self.repository.get_item(item.item_id)
        self.assertEqual(stored.attempts, 1)
        self.assertIs(stored.status, TaskItemStatus.SUCCESS)
        self.assertEqual(self.repository.list_results(item.task_id), recorded)

    def test_an_uncertain_outcome_keeps_the_mutation_boundary_and_is_never_replayed(self) -> None:
        service = self.service()
        admission = _admit(service)
        claim = self.claimed(service)
        item = self.item(service, claim)
        service.begin_mutation(claim, item, "move", now=NOW + timedelta(seconds=3))
        service.complete_item(
            claim,
            replace(
                item,
                status=TaskItemStatus.FAILED,
                stage="failed",
                error="move outcome could not be verified",
                updated_at=NOW + timedelta(seconds=4),
            ),
            result=_result(
                item,
                status="failed",
                certainty="attempted_unverified",
                uncertain_effects=("move",),
            ),
            now=NOW + timedelta(seconds=4),
        )
        state = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertEqual(state.mutation_state, TASK_MUTATION_IN_FLIGHT)
        self.assertEqual(state.mutation_item_id, item.item_id)

        with self.assertRaises(TaskSchedulingError):
            service.begin_item(
                claim,
                storage_id=item.storage_id,
                resource_library_id=item.resource_library_id,
                source_path=item.source_path,
                source_display=item.source_path,
                now=NOW + timedelta(seconds=5),
            )
        with self.assertRaises(TaskSchedulingError):
            service.begin_mutation(
                claim,
                self.repository.get_item(item.item_id),
                "move",
                now=NOW + timedelta(seconds=5),
            )
        # Even a live claim cannot start a fresh attempt over the persisted
        # uncertain Result; the refusal does not depend on the lease expiring.
        with self.assertRaises(TaskSchedulingError):
            self.repository.upsert_scheduled_item(
                claim.fence(NOW + timedelta(seconds=5)),
                replace(
                    self.repository.get_item(item.item_id),
                    status=TaskItemStatus.PROCESSING,
                    stage="pipeline",
                    attempts=2,
                    updated_at=NOW + timedelta(seconds=5),
                ),
                stage=TaskItemPublication.START,
            )

        # Timeout, a lost lease and a restart are not proof that the effect did
        # not happen: the uncertain boundary survives all of them.
        later = NOW + timedelta(minutes=5)
        self.repository.heartbeat_worker("worker-1", later)
        self.assertIsNone(
            self.service(repository=self.reopen()).claim_next(worker_id="worker-1", now=later)
        )
        restarted = self.service()
        persisted = restarted.state(admission.task.task_id)
        self.assertEqual(persisted.mutation_state, TASK_MUTATION_IN_FLIGHT)
        with self.assertRaises(TaskControlRejected):
            restarted.requeue(
                admission.task.task_id,
                expected_snapshot_id="snapshot-1",
                expected_snapshot_digest="digest-1",
                now=later,
            )
        with self.assertRaises(TaskSchedulingError):
            restarted.begin_item(
                claim,
                storage_id=item.storage_id,
                resource_library_id=item.resource_library_id,
                source_path=item.source_path,
                source_display=item.source_path,
                now=later,
            )
        self.assertEqual(
            [value.result_id for value in self.repository.list_results(item.task_id)],
            [f"{item.item_id}:1"],
        )

    def test_a_zero_certainty_result_that_still_names_effects_is_not_replayable(self) -> None:
        service = self.service()
        _admit(service)
        claim = self.claimed(service)
        item = self.item(service, claim)
        service.complete_item(
            claim,
            replace(
                item,
                status=TaskItemStatus.FAILED,
                stage="failed",
                updated_at=NOW + timedelta(seconds=3),
            ),
            result=replace(
                _result(item, status="failed", certainty="none"),
                completed_operations=("move",),
            ),
            now=NOW + timedelta(seconds=3),
        )
        with self.assertRaises(TaskSchedulingError):
            service.begin_item(
                claim,
                storage_id=item.storage_id,
                resource_library_id=item.resource_library_id,
                source_path=item.source_path,
                source_display=item.source_path,
                now=NOW + timedelta(seconds=4),
            )
        self.assertEqual(self.repository.get_item(item.item_id).attempts, 1)

    def test_a_proven_no_effect_attempt_can_continue_without_replay(self) -> None:
        service = self.service()
        _admit(service)
        claim = self.claimed(service)
        item = self.item(service, claim)
        service.begin_mutation(claim, item, "move", now=NOW + timedelta(seconds=3))
        service.complete_item(
            claim,
            replace(
                item,
                status=TaskItemStatus.FAILED,
                stage="failed",
                updated_at=NOW + timedelta(seconds=4),
            ),
            result=_result(item, status="failed", certainty="none"),
            now=NOW + timedelta(seconds=4),
        )
        state = self.repository.get_task_scheduling(claim.task_id)
        self.assertIsNone(state.mutation_state)

        second = service.begin_item(
            claim,
            storage_id=item.storage_id,
            resource_library_id=item.resource_library_id,
            source_path=item.source_path,
            source_display=item.source_path,
            now=NOW + timedelta(seconds=5),
        )
        self.assertEqual(second.attempts, 2)
        self.assertIs(second.status, TaskItemStatus.PROCESSING)
        service.begin_mutation(claim, second, "move", now=NOW + timedelta(seconds=6))
        self.assertEqual(
            self.repository.get_task_scheduling(claim.task_id).mutation_item_id,
            second.item_id,
        )


class SourceVersionIntegrityTests(SchedulingKernelTestCase):
    """A resumed Task may not silently start working on another source version."""

    path = "媒体/电影/A.mkv"

    def setUp(self) -> None:
        super().setUp()
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

    def versioned_item(self, service, claim, *, observed=None, now=None):
        at = now or NOW + timedelta(seconds=2)
        return service.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path=self.path,
            source_display=self.path,
            source_occurrence_id="occ-v1",
            source_fingerprint="fingerprint-A",
            source_fingerprint_state="verified",
            source_observed_at=observed or NOW + timedelta(seconds=2),
            source_storage_path=self.path,
            now=at,
        )

    def paused_and_requeued(self, service):
        admission = _admit(service)
        first = self.claimed(service)
        item = self.versioned_item(service, first)
        service.request_control(
            admission.task.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=3)
        )
        service.acknowledge_control(first, now=NOW + timedelta(seconds=3))
        service.requeue(
            admission.task.task_id,
            expected_snapshot_id="snapshot-1",
            expected_snapshot_digest="digest-1",
            expected_control_revision=1,
            now=NOW + timedelta(seconds=4),
        )
        second = self.claimed(service, now=NOW + timedelta(seconds=5), worker="worker-2")
        return admission, item, second

    def test_resuming_an_item_cannot_replace_its_known_source_version(self) -> None:
        service = self.service()
        admission, original, claim = self.paused_and_requeued(service)

        with self.assertRaises(TaskSchedulingError):
            service.begin_item(
                claim,
                storage_id="local",
                resource_library_id="library",
                source_path=self.path,
                source_display=self.path,
                source_occurrence_id="occ-v2",
                source_fingerprint="fingerprint-B",
                source_fingerprint_state="verified",
                source_observed_at=NOW + timedelta(seconds=7),
                source_storage_path=self.path,
                now=NOW + timedelta(seconds=7),
            )

        stored = self.repository.get_item(original.item_id)
        self.assertEqual(stored.attempts, 1)
        self.assertIs(stored.status, TaskItemStatus.PAUSED)
        self.assertEqual(stored.source_occurrence_id, "occ-v1")
        self.assertEqual(stored.source_fingerprint, "fingerprint-A")
        self.assertEqual(stored.source_fingerprint_state, "verified")
        self.assertEqual(stored.source_observed_at, NOW + timedelta(seconds=2))
        self.assertEqual(stored.source_storage_path, self.path)
        self.assertIsNone(
            self.repository.get_task_scheduling(admission.task.task_id).mutation_state
        )
        # The refused work never entered a mutation boundary either.
        with self.assertRaises(TaskSchedulingError):
            service.begin_mutation(claim, stored, "move", now=NOW + timedelta(seconds=8))

        # The legitimate continuation keeps the known version and the first
        # observation even when the caller passes a newer observation instant.
        resumed = service.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path=self.path,
            source_display=self.path,
            source_occurrence_id="occ-v1",
            source_fingerprint="fingerprint-A",
            source_fingerprint_state="verified",
            source_observed_at=NOW + timedelta(seconds=8),
            source_storage_path=self.path,
            now=NOW + timedelta(seconds=8),
        )
        self.assertEqual(resumed.attempts, 2)
        self.assertEqual(resumed.source_occurrence_id, "occ-v1")
        self.assertEqual(resumed.source_fingerprint, "fingerprint-A")
        self.assertEqual(resumed.source_observed_at, NOW + timedelta(seconds=2))
        service.begin_mutation(claim, resumed, "move", now=NOW + timedelta(seconds=9))
        self.assertEqual(
            self.repository.get_task_scheduling(admission.task.task_id).mutation_item_id,
            original.item_id,
        )

    def test_omitted_identity_arguments_keep_the_known_source_and_observation(self) -> None:
        service = self.service()
        _admission, _original, claim = self.paused_and_requeued(service)

        resumed = service.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path=self.path,
            source_display=self.path,
            now=NOW + timedelta(seconds=7),
        )
        self.assertEqual(resumed.attempts, 2)
        self.assertEqual(resumed.source_occurrence_id, "occ-v1")
        self.assertEqual(resumed.source_fingerprint, "fingerprint-A")
        self.assertEqual(resumed.source_fingerprint_state, "verified")
        self.assertEqual(resumed.source_observed_at, NOW + timedelta(seconds=2))
        self.assertEqual(resumed.source_storage_path, self.path)

        completed = replace(
            resumed,
            status=TaskItemStatus.SUCCESS,
            stage="completed",
            updated_at=NOW + timedelta(seconds=8),
        )
        service.complete_item(
            claim, completed, result=_result(resumed), now=NOW + timedelta(seconds=8)
        )
        stored_result = self.repository.list_results(resumed.task_id)[0]
        self.assertEqual(stored_result.source_occurrence_id, "occ-v1")
        self.assertEqual(stored_result.source_fingerprint, "fingerprint-A")
        self.assertEqual(stored_result.source_observed_at, NOW + timedelta(seconds=2))

    def test_missing_legacy_evidence_is_not_invented_by_omission(self) -> None:
        service = self.service()
        admission = _admit(service)
        first = self.claimed(service)
        legacy_path = "媒体/电影/legacy.mkv"
        item = service.begin_item(
            first,
            storage_id="local",
            resource_library_id="library",
            source_path=legacy_path,
            source_display=legacy_path,
            source_observed_at=NOW + timedelta(seconds=2),
            now=NOW + timedelta(seconds=2),
        )
        self.assertIsNone(item.source_occurrence_id)
        self.assertIsNone(item.source_fingerprint)
        self.assertEqual(item.source_fingerprint_state, "unverified")
        service.request_control(
            admission.task.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=3)
        )
        service.acknowledge_control(first, now=NOW + timedelta(seconds=3))
        service.requeue(
            admission.task.task_id,
            expected_snapshot_id="snapshot-1",
            expected_snapshot_digest="digest-1",
            expected_control_revision=1,
            now=NOW + timedelta(seconds=4),
        )
        claim = self.claimed(service, now=NOW + timedelta(seconds=5), worker="worker-2")
        resumed = service.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path=legacy_path,
            source_display=legacy_path,
            now=NOW + timedelta(seconds=7),
        )
        self.assertEqual(resumed.attempts, 2)
        self.assertIsNone(resumed.source_occurrence_id)
        self.assertIsNone(resumed.source_fingerprint)
        self.assertEqual(resumed.source_fingerprint_state, "unverified")
        self.assertEqual(resumed.source_observed_at, NOW + timedelta(seconds=2))

    def test_verified_evidence_can_legally_fill_a_previously_unknown_source(self) -> None:
        service = self.service()
        admission = _admit(service)
        first = self.claimed(service)
        legacy_path = "媒体/电影/legacy.mkv"
        service.begin_item(
            first,
            storage_id="local",
            resource_library_id="library",
            source_path=legacy_path,
            source_display=legacy_path,
            source_observed_at=NOW + timedelta(seconds=2),
            now=NOW + timedelta(seconds=2),
        )
        service.request_control(
            admission.task.task_id, TaskControl.PAUSE, now=NOW + timedelta(seconds=3)
        )
        service.acknowledge_control(first, now=NOW + timedelta(seconds=3))
        service.requeue(
            admission.task.task_id,
            expected_snapshot_id="snapshot-1",
            expected_snapshot_digest="digest-1",
            expected_control_revision=1,
            now=NOW + timedelta(seconds=4),
        )
        claim = self.claimed(service, now=NOW + timedelta(seconds=5), worker="worker-2")
        resumed = service.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path=legacy_path,
            source_display=legacy_path,
            source_occurrence_id="occ-v1",
            source_fingerprint="fingerprint-A",
            source_fingerprint_state="verified",
            source_observed_at=NOW + timedelta(seconds=6),
            source_storage_path=legacy_path,
            now=NOW + timedelta(seconds=7),
        )
        self.assertEqual(resumed.attempts, 2)
        self.assertEqual(resumed.source_occurrence_id, "occ-v1")
        self.assertEqual(resumed.source_fingerprint, "fingerprint-A")
        self.assertEqual(resumed.source_fingerprint_state, "verified")
        self.assertEqual(resumed.source_observed_at, NOW + timedelta(seconds=2))

    def test_an_outcome_cannot_name_another_source_version(self) -> None:
        service = self.service()
        admission = _admit(service)
        claim = self.claimed(service)
        item = self.versioned_item(service, claim)
        service.begin_mutation(claim, item, "move", now=NOW + timedelta(seconds=3))
        completed = replace(
            item,
            status=TaskItemStatus.SUCCESS,
            stage="completed",
            updated_at=NOW + timedelta(seconds=4),
        )
        other_version = replace(
            _result(item),
            source_occurrence_id="occ-v2",
            source_fingerprint="fingerprint-B",
            source_fingerprint_state="verified",
        )
        with self.assertRaises(TaskSchedulingError):
            service.complete_item(
                claim, completed, result=other_version, now=NOW + timedelta(seconds=4)
            )

        stored = self.repository.get_item(item.item_id)
        self.assertEqual(stored.attempts, 1)
        self.assertIs(stored.status, TaskItemStatus.PROCESSING)
        self.assertEqual(stored.source_occurrence_id, "occ-v1")
        self.assertEqual(self.repository.list_results(item.task_id), ())
        self.assertEqual(self.repository.list_evidence_for_item(item.item_id), ())
        refused = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertEqual(refused.mutation_state, TASK_MUTATION_IN_FLIGHT)
        self.assertEqual(refused.mutation_item_id, item.item_id)

        # Closing and reopening the database does not turn the refused attempt
        # into an accepted Result or clear the in-flight boundary.
        self.reopen()
        restarted = self.service()
        persisted = restarted.state(admission.task.task_id)
        self.assertEqual(persisted.mutation_state, TASK_MUTATION_IN_FLIGHT)
        self.assertEqual(self.repository.list_results(item.task_id), ())
        self.assertIs(self.repository.get_item(item.item_id).status, TaskItemStatus.PROCESSING)

        restarted.complete_item(
            claim,
            completed,
            result=_result(item),
            evidence=_evidence(item),
            now=NOW + timedelta(seconds=5),
        )
        stored_result = self.repository.list_results(item.task_id)[0]
        self.assertEqual(stored_result.source_occurrence_id, "occ-v1")
        self.assertEqual(stored_result.source_fingerprint, "fingerprint-A")
        self.assertIsNone(
            self.repository.get_task_scheduling(admission.task.task_id).mutation_state
        )
        self.assertEqual(len(self.repository.list_evidence_for_item(item.item_id)), 1)

    def test_evidence_cannot_replace_the_admitted_configuration_pin(self) -> None:
        service = self.service()
        admission = _admit(service)
        claim = self.claimed(service)
        sibling_path = "媒体/电影/sibling.mkv"
        sibling = service.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path=sibling_path,
            source_display=sibling_path,
            source_occurrence_id="occ-sibling",
            source_fingerprint="fingerprint-sibling",
            source_fingerprint_state="verified",
            source_storage_path=sibling_path,
            now=NOW + timedelta(seconds=2),
        )
        service.complete_item(
            claim,
            replace(
                sibling,
                status=TaskItemStatus.SUCCESS,
                stage="completed",
                updated_at=NOW + timedelta(seconds=3),
            ),
            result=_result(sibling),
            now=NOW + timedelta(seconds=3),
        )
        recorded = self.repository.list_results(admission.task.task_id)
        item = self.versioned_item(service, claim, now=NOW + timedelta(seconds=3))
        service.begin_mutation(claim, item, "move", now=NOW + timedelta(seconds=4))
        completed = replace(
            item,
            status=TaskItemStatus.SUCCESS,
            stage="completed",
            updated_at=NOW + timedelta(seconds=5),
        )
        other_pin = replace(
            _evidence(item),
            configuration_snapshot_id="snapshot-other",
            configuration_snapshot_digest="digest-other",
        )
        with self.assertRaises(TaskSchedulingError):
            service.complete_item(
                claim,
                completed,
                result=_result(item),
                evidence=other_pin,
                now=NOW + timedelta(seconds=5),
            )

        # The independent successful sibling keeps its verified result/history.
        self.assertEqual(self.repository.list_results(item.task_id), recorded)
        self.assertIs(self.repository.get_item(sibling.item_id).status, TaskItemStatus.SUCCESS)
        self.assertEqual(self.repository.list_evidence_for_item(item.item_id), ())
        self.assertIs(self.repository.get_item(item.item_id).status, TaskItemStatus.PROCESSING)
        state = self.repository.get_task_scheduling(admission.task.task_id)
        self.assertEqual(state.mutation_state, TASK_MUTATION_IN_FLIGHT)

        service.complete_item(
            claim,
            completed,
            result=_result(item),
            evidence=_evidence(item),
            now=NOW + timedelta(seconds=6),
        )
        self.assertIsNone(
            self.repository.get_task_scheduling(admission.task.task_id).mutation_state
        )
        self.assertEqual(len(self.repository.list_evidence_for_item(item.item_id)), 1)
        self.assertEqual(len(self.repository.list_results(item.task_id)), len(recorded) + 1)

    def test_progress_and_direct_repository_writes_cannot_replace_the_source(self) -> None:
        service = self.service()
        _admit(service)
        claim = self.claimed(service)
        item = self.versioned_item(service, claim)
        replaced = replace(
            item,
            source_occurrence_id="occ-v2",
            source_fingerprint="fingerprint-B",
            source_fingerprint_state="verified",
            source_observed_at=NOW + timedelta(seconds=3),
            source_storage_path="媒体/电影/other.mkv",
            updated_at=NOW + timedelta(seconds=3),
        )
        with self.assertRaises(TaskSchedulingError):
            service.record_item(claim, replaced, now=NOW + timedelta(seconds=3))
        with self.assertRaises(TaskSchedulingError):
            self.repository.upsert_scheduled_item(claim.fence(NOW + timedelta(seconds=3)), replaced)
        with self.assertRaises(TaskSchedulingError):
            self.repository.upsert_scheduled_item(
                claim.fence(NOW + timedelta(seconds=3)),
                replace(
                    replaced,
                    status=TaskItemStatus.PROCESSING,
                    stage="pipeline",
                    attempts=2,
                ),
                stage=TaskItemPublication.START,
            )
        with self.assertRaises(TaskSchedulingError):
            self.repository.publish_scheduled_item_outcome(
                claim.fence(NOW + timedelta(seconds=3)),
                replace(
                    replaced,
                    status=TaskItemStatus.SUCCESS,
                    stage="completed",
                ),
                replace(
                    _result(item),
                    source_occurrence_id="occ-v2",
                    source_fingerprint="fingerprint-B",
                    source_fingerprint_state="verified",
                ),
                None,
                clear_mutation=False,
            )

        stored = self.repository.get_item(item.item_id)
        self.assertEqual(stored.attempts, 1)
        self.assertIs(stored.status, TaskItemStatus.PROCESSING)
        self.assertEqual(stored.source_occurrence_id, "occ-v1")
        self.assertEqual(stored.source_fingerprint, "fingerprint-A")
        self.assertEqual(stored.source_observed_at, NOW + timedelta(seconds=2))
        self.assertEqual(stored.source_storage_path, self.path)
        self.assertEqual(self.repository.list_results(item.task_id), ())


class PortConformanceTests(unittest.TestCase):
    def test_the_sqlite_repository_implements_the_declared_port(self) -> None:
        """The application depends on the port; the port must stay truthful."""

        import inspect

        from mediaflow.domain.task_scheduling import TaskSchedulingRepository

        declared = {
            name: member
            for name, member in vars(TaskSchedulingRepository).items()
            if not name.startswith("_") and callable(member)
        }
        self.assertGreaterEqual(len(declared), 14)
        for name in declared:
            with self.subTest(method=name):
                implemented = getattr(SQLiteTaskRepository, name, None)
                self.assertTrue(callable(implemented), f"{name} is not implemented")
                expected = [
                    item
                    for item in inspect.signature(declared[name]).parameters.values()
                    if item.name != "self"
                ]
                actual = [
                    item
                    for item in inspect.signature(implemented).parameters.values()
                    if item.name != "self"
                ]
                # Every declared parameter exists with the same kind; an
                # implementation may only add further *optional* parameters.
                self.assertEqual(
                    [(item.name, item.kind) for item in expected],
                    [(item.name, item.kind) for item in actual[: len(expected)]],
                )
                for extra in actual[len(expected) :]:
                    self.assertIsNot(extra.default, inspect.Parameter.empty, extra.name)


class TransitionBoundaryTests(unittest.TestCase):
    def test_only_the_named_production_files_wire_the_kernel(self) -> None:
        """Task47.2: the kernel is now consumed by the Files production path.

        Newly admitted Files manual work runs on one Task engine.  Exactly the
        named production modules may name the kernel, so no accidental second
        dispatch or a legacy runner silently claiming the same work appears.
        The legacy discovery/manual-execution claim queries explicitly exclude
        kernel-managed rows, which keeps the two ownership boundaries apart.
        """

        package = Path(mediaflow_package_path()).parent
        expected = {
            "application/automation.py",
            # Task47.3: definition Run once admits through the shared kernel
            # Task/slot/request identity instead of a Job.
            "application/automation_run_once.py",
            "application/automation_definition_execution.py",
            # Task47.3 round 3: the automatic Task's saved decision re-enters
            # its own zero-mutation analysis through the kernel re-entry
            # boundary, and the remote ticket consumes into a Task admission.
            "application/automatic_task_continuation.py",
            "application/execution_authorization.py",
            "application/manual_organize_execution.py",
            "application/manual_recovery_continuation.py",
            "application/manual_task_continuation.py",
            "application/manual_task_engine.py",
            "application/media_discovery.py",
            # Task Center pause/cancel for a kernel-managed Task routes to the
            # same Task control boundary the Files page uses instead of the
            # legacy version-checked writer.
            "application/operations_lifecycle.py",
            # Task47.3: the definition-scoped automatic pipeline adopts a
            # Scheduler/Run once kernel Task and publishes under its claim.
            "application/task_runtime.py",
            "application/unattended_execution.py",
            "final_cli.py",
            "interfaces/service_api.py",
            "domain/task_scheduling.py",
            "application/task_scheduling.py",
            "infrastructure/sqlite_runtime.py",
        }
        markers = ("task_scheduling", "TaskSchedulingService", "claim_next_scheduled_task")
        consumers = {
            str(path.relative_to(package))
            for path in package.rglob("*.py")
            if any(marker in path.read_text(encoding="utf-8") for marker in markers)
        }
        self.assertEqual(consumers, expected)
        # The legacy runners exclude kernel-managed rows, so a second Worker
        # can never claim the same new work through the old queue.
        runtime = (package / "infrastructure" / "sqlite_runtime.py").read_text(encoding="utf-8")
        self.assertIn("NOT EXISTS (SELECT 1 FROM task_scheduling", runtime)


if __name__ == "__main__":
    unittest.main()
