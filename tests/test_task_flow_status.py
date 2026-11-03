"""Slice 48 Task 48.1 — the one shared Task flow settlement rule.

These tests prove the flow settlement contract end to end:

* the application-layer rule (:mod:`mediaflow.application.task_flow_settlement`)
  derives exactly one of the five flow statuses from the bounded facts a
  settlement boundary actually knows — never from the file population;
* the real automatic-pass settlement (a genuine SQLite repository, the
  scheduling kernel and the resident Task engine) publishes that rule for
  every scenario row of the Slice 48 TARGET table: all-success, mixed,
  all-failed, skipped/ignored, individually cancelled files, healthy empty
  scope, history-gated passes, human waiting, acknowledged cancellation and a
  technically ended attempt whose Result was never produced;
* file technical failures never reclassify the flow, and a missing Result
  never holds the shared slot — while acknowledged cancellation, Task-own
  orchestration failures and genuinely unfinished work keep their own
  truthful outcomes.

The automatic runner below is a deterministic stub of the media pipeline that
publishes every item/Result through the real claim-fenced kernel boundary, so
each settlement is produced by the production engine — never by planting a
completed row.
"""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
from mediaflow.application.media_organizer import MediaOrganizerBatchResult
from mediaflow.application.task_flow_settlement import (
    TaskFlowSettlementInputs,
    settle_task_flow,
)
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.application.task_scheduling import TaskSchedulingService
from mediaflow.domain.failure import decode_failure_explanation
from mediaflow.domain.scanner import ScanError
from mediaflow.domain.storage import StorageErrorCode
from mediaflow.domain.task_persistence import (
    HISTORY_EXCLUDED_ITEM_STAGE,
    PersistentResultRecord,
    PersistentTaskStatus,
    TaskItemStatus,
    task_item_counts,
    task_work_status,
)
from mediaflow.domain.task_scheduling import (
    TaskControl,
    TaskMachineStage,
    TaskQueueState,
    TaskTrigger,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository

NOW = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)


def _at(seconds: int) -> datetime:
    return NOW + timedelta(seconds=seconds)


class SettlementRuleTests(unittest.TestCase):
    """The precedence table of the one shared settlement rule."""

    @staticmethod
    def inputs(**overrides) -> TaskFlowSettlementInputs:
        base = {
            "ended_this_round": True,
            "machine_work_remaining": False,
            "human_decision_pending": False,
            "live_local_call": False,
            "scope_proven_complete": True,
            "orchestration_error": None,
            "acknowledged_cancellation": False,
        }
        base.update(overrides)
        return TaskFlowSettlementInputs(**base)

    def test_normal_closure_of_any_file_population_is_completed(self):
        # The file outcomes (success/failure/partial/skip/ignore/individual
        # cancellations/unknown effects/missing Results) are not inputs at all:
        # the rule reads the boundary facts, never the files.
        decision = settle_task_flow(self.inputs())
        self.assertIs(PersistentTaskStatus.COMPLETED, decision.status)
        self.assertTrue(decision.terminal)

    def test_acknowledged_cancellation_wins_over_everything(self):
        decision = settle_task_flow(
            self.inputs(
                acknowledged_cancellation=True,
                orchestration_error="also broken",
                machine_work_remaining=True,
            )
        )
        self.assertIs(PersistentTaskStatus.CANCELLED, decision.status)
        self.assertTrue(decision.terminal)

    def test_task_own_orchestration_error_is_failed(self):
        decision = settle_task_flow(self.inputs(orchestration_error="pin_corrupt"))
        self.assertIs(PersistentTaskStatus.FAILED, decision.status)
        self.assertTrue(decision.terminal)

    def test_scope_that_cannot_be_proven_complete_is_failed(self):
        decision = settle_task_flow(self.inputs(scope_proven_complete=False))
        self.assertIs(PersistentTaskStatus.FAILED, decision.status)
        self.assertTrue(decision.terminal)

    def test_real_remaining_work_keeps_the_flow_unfinished(self):
        for overrides in (
            {"ended_this_round": False},
            {"machine_work_remaining": True},
            {"live_local_call": True},
            {"human_decision_pending": True},
        ):
            with self.subTest(overrides=overrides):
                decision = settle_task_flow(self.inputs(**overrides))
                self.assertIs(PersistentTaskStatus.RUNNING, decision.status)
                self.assertFalse(decision.terminal)


class AggregateDerivationTests(unittest.TestCase):
    """``task_work_status``/``task_item_counts`` separate flow from file facts."""

    @staticmethod
    def item(status: TaskItemStatus, stage: str = "completed"):
        from types import SimpleNamespace

        return SimpleNamespace(status=status, stage=stage)

    def test_any_unsettled_source_is_running(self):
        for status in (
            TaskItemStatus.PENDING,
            TaskItemStatus.PROCESSING,
            TaskItemStatus.WAITING_CONFIRM,
            TaskItemStatus.WAITING_METADATA,
            TaskItemStatus.PAUSED,
        ):
            with self.subTest(status=status):
                self.assertIs(
                    PersistentTaskStatus.RUNNING,
                    task_work_status([self.item(status)]),
                )

    def test_every_settled_population_is_completed(self):
        populations = (
            [TaskItemStatus.SUCCESS],
            [TaskItemStatus.SUCCESS, TaskItemStatus.FAILED],
            [TaskItemStatus.FAILED, TaskItemStatus.FAILED],
            [TaskItemStatus.PARTIAL],
            [TaskItemStatus.SKIPPED, TaskItemStatus.IGNORED],
            [TaskItemStatus.CANCELLED, TaskItemStatus.CANCELLED],
            [TaskItemStatus.SUCCESS, TaskItemStatus.CANCELLED, TaskItemStatus.FAILED],
            [TaskItemStatus.DRY_RUN],
        )
        for statuses in populations:
            with self.subTest(statuses=statuses):
                self.assertIs(
                    PersistentTaskStatus.COMPLETED,
                    task_work_status([self.item(status) for status in statuses]),
                )

    def test_empty_population_is_running(self):
        self.assertIs(PersistentTaskStatus.RUNNING, task_work_status([]))

    def test_counts_separate_ended_progress_from_file_failures(self):
        statuses = (
            TaskItemStatus.SUCCESS,
            TaskItemStatus.FAILED,
            TaskItemStatus.PARTIAL,
            TaskItemStatus.SKIPPED,
            TaskItemStatus.IGNORED,
            TaskItemStatus.CANCELLED,
            TaskItemStatus.WAITING_CONFIRM,
        )
        total, ended, failed = task_item_counts([self.item(status) for status in statuses])
        self.assertEqual(7, total)
        # Every settled attempt is ended progress; only failed/partial are
        # file failures — a strict subset of the ended work.
        self.assertEqual(6, ended)
        self.assertEqual(2, failed)
        self.assertLessEqual(failed, ended)


class CoordinatorScopeSettlementTests(unittest.TestCase):
    """The legacy coordinator passes real discovery failures to the shared rule."""

    def test_unreadable_scope_is_a_failed_flow_not_a_healthy_empty_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteTaskRepository(Path(directory, "runtime.sqlite3"))
            self.addCleanup(repository.close)
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("organize", execute_authorized=False)
            batch = MediaOrganizerBatchResult(
                (),
                (
                    ScanError(
                        "Media",
                        "list",
                        StorageErrorCode.PERMISSION_DENIED,
                        NOW,
                    ),
                ),
            )
            final = coordinator.finish(task.task_id, batch)
            self.assertIs(PersistentTaskStatus.FAILED, final.status)
            self.assertEqual(
                (0, 0, 0), (final.total_items, final.completed_items, final.failed_items)
            )
            explanation = decode_failure_explanation(final.error)
            self.assertIsNotNone(explanation, final.error)
            self.assertIn("无法完整读取来源目录", explanation.message)
            self.assertEqual("none", explanation.side_effects)
            self.assertEqual("storage_failure", explanation.category)


class _KernelHarness(unittest.TestCase):
    """One real SQLite repository, scheduling kernel and resident engine."""

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.database = Path(self._directory.name, "runtime.sqlite3")
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.repository.close)
        self.repository.register_worker(
            "worker-1", "worker one", 5.0, ("organize",), None, None, SCHEMA_VERSION, NOW
        )
        self.scheduling = TaskSchedulingService(self.repository, capacity=2, locks=self.repository)

    def tearDown(self) -> None:
        self.repository.close()

    def admit(self, *, request_id="request-1"):
        return self.scheduling.admit(
            "organize",
            execute_authorized=True,
            trigger=TaskTrigger.SCHEDULE,
            principal="scheduler",
            request_id=request_id,
            scope_path="Media",
            item_limit=10,
            configuration_snapshot_id="snapshot-1",
            configuration_snapshot_digest="digest-1",
            now=NOW,
        )

    def claimed(self, *, worker="worker-1"):
        claim = self.scheduling.claim_next(worker_id=worker, now=NOW)
        self.assertIsNotNone(claim)
        assert claim is not None
        return self.scheduling.begin_work(claim, stage=TaskMachineStage.EXECUTION, now=_at(1))

    def publish(self, claim, path: str, status: TaskItemStatus, *, result_status=None):
        """One real claim-fenced item/Result publication of the pipeline stub."""

        item = self.scheduling.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path=path,
            source_display=path,
            now=_at(2),
        )
        settled = replace(item, status=status, stage="completed", updated_at=_at(3))
        self.scheduling.complete_item(
            claim,
            settled,
            result=self.result(settled, result_status or status.value),
            now=_at(3),
        )
        return settled

    @staticmethod
    def result(item: object, status: str) -> PersistentResultRecord:
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
            _at(3),
            effect_certainty="verified_complete",
        )

    def engine(self, runner, *, clock=None):
        return ManualTaskEngineWorker(
            self.repository,
            self.scheduling,
            None,
            None,
            worker_id="worker-1",
            clock=clock or (lambda: _at(4)),
            automatic_runner=runner,
            notice=lambda line: None,
        )


class AutomaticPassSettlementTests(_KernelHarness):
    """The Slice 48 scenario table through the real engine settlement."""

    def scenario(self, outcomes, *, request_id="request-1"):
        """Admit, claim and settle one automatic pass with the given files."""

        def runner(task, claim, clock=None, heartbeat=None):
            for path, status in outcomes:
                self.publish(claim, path, status)

        admission = self.admit(request_id=request_id)
        self.engine(runner).run_next()
        return self.repository.get_task(admission.task.task_id)

    def test_all_success_completes(self):
        task = self.scenario(
            [("Media/A.mkv", TaskItemStatus.SUCCESS), ("Media/B.mkv", TaskItemStatus.SUCCESS)]
        )
        self.assertIs(PersistentTaskStatus.COMPLETED, task.status)
        self.assertEqual((2, 2, 0), (task.total_items, task.completed_items, task.failed_items))
        self.assertIsNotNone(task.completed_at)

    def test_mixed_population_completes_with_independent_file_facts(self):
        task = self.scenario(
            [
                ("Media/A.mkv", TaskItemStatus.SUCCESS),
                ("Media/B.mkv", TaskItemStatus.FAILED),
                ("Media/C.mkv", TaskItemStatus.PARTIAL),
                ("Media/D.mkv", TaskItemStatus.SKIPPED),
                ("Media/E.mkv", TaskItemStatus.IGNORED),
            ]
        )
        self.assertIs(PersistentTaskStatus.COMPLETED, task.status)
        self.assertEqual((5, 5, 2), (task.total_items, task.completed_items, task.failed_items))

    def test_all_failed_population_still_completes_the_flow(self):
        task = self.scenario(
            [("Media/A.mkv", TaskItemStatus.FAILED), ("Media/B.mkv", TaskItemStatus.FAILED)]
        )
        self.assertIs(PersistentTaskStatus.COMPLETED, task.status)
        self.assertEqual((2, 2, 2), (task.total_items, task.completed_items, task.failed_items))

    def test_individually_cancelled_files_never_derive_a_cancelled_task(self):
        task = self.scenario(
            [("Media/A.mkv", TaskItemStatus.CANCELLED), ("Media/B.mkv", TaskItemStatus.CANCELLED)]
        )
        self.assertIs(PersistentTaskStatus.COMPLETED, task.status)

    def test_healthy_empty_scope_completes(self):
        task = self.scenario([])
        self.assertIs(PersistentTaskStatus.COMPLETED, task.status)
        self.assertEqual((0, 0, 0), (task.total_items, task.completed_items, task.failed_items))

    def test_history_gated_pass_completes_with_its_own_reason(self):
        def runner(task, claim, clock=None, heartbeat=None):
            item = self.scheduling.begin_item(
                claim,
                storage_id="local",
                resource_library_id="library",
                source_path="Media/A.mkv",
                source_display="Media/A.mkv",
                now=_at(2),
            )
            self.scheduling.record_item(
                claim,
                replace(
                    item,
                    status=TaskItemStatus.SKIPPED,
                    stage=HISTORY_EXCLUDED_ITEM_STAGE,
                    error="history gate: excluded",
                    updated_at=_at(3),
                ),
                now=_at(3),
            )

        admission = self.admit()
        self.engine(runner).run_next()
        task = self.repository.get_task(admission.task.task_id)
        # Slice 48: a recorded history exclusion is a completed flow with a
        # truthful "nothing was processed" reason — never a fabricated success
        # and never a flow failure.
        self.assertIs(PersistentTaskStatus.COMPLETED, task.status)
        self.assertIn("history gate", task.error or "")

    def test_human_waiting_keeps_the_flow_unfinished_and_releases_the_slot(self):
        def runner(task, claim, clock=None, heartbeat=None):
            self.publish(claim, "Media/A.mkv", TaskItemStatus.SUCCESS)
            item = self.scheduling.begin_item(
                claim,
                storage_id="local",
                resource_library_id="library",
                source_path="Media/B.mkv",
                source_display="Media/B.mkv",
                now=_at(2),
            )
            self.scheduling.record_item(
                claim,
                replace(
                    item,
                    status=TaskItemStatus.WAITING_CONFIRM,
                    stage="waiting_confirm",
                    updated_at=_at(3),
                ),
                now=_at(3),
            )

        admission = self.admit()
        self.engine(runner).run_next()
        task = self.repository.get_task(admission.task.task_id)
        state = self.scheduling.state(admission.task.task_id)
        self.assertIs(PersistentTaskStatus.RUNNING, task.status)
        self.assertIsNone(task.completed_at)
        self.assertIs(TaskQueueState.WAITING_HUMAN, state.queue_state)
        self.assertEqual(0, self.scheduling.capacity_use())
        # Successful siblings are not replayed by further passes.
        before = tuple(self.repository.list_results(admission.task.task_id))
        self.engine(lambda *_args: None).run_next()
        self.assertEqual(before, tuple(self.repository.list_results(admission.task.task_id)))

    def test_an_accepted_cancel_is_never_overwritten_by_a_normal_closure(self):
        def runner(task, claim, clock=None, heartbeat=None):
            self.publish(claim, "Media/A.mkv", TaskItemStatus.SUCCESS)
            # The operator's cancel arrives at the safe boundary between the
            # file publication and the pass's own settlement.
            self.scheduling.request_control(task.task_id, TaskControl.CANCEL, now=_at(3))

        admission = self.admit()
        self.engine(runner).run_next()
        task = self.repository.get_task(admission.task.task_id)
        self.assertIs(PersistentTaskStatus.CANCELLED, task.status)
        # The acknowledged cancellation is the outcome; the completed file
        # keeps its own recorded Result.
        self.assertEqual(1, len(self.repository.list_results(admission.task.task_id)))


class TechnicalStopSettlementTests(_KernelHarness):
    """A technically ended attempt with no Result closes without holding a slot."""

    def test_ended_attempt_without_result_closes_completed(self):
        marker = {}

        def runner(task, claim, clock=None, heartbeat=None):
            self.publish(claim, "Media/A.mkv", TaskItemStatus.SUCCESS)
            item = self.scheduling.begin_item(
                claim,
                storage_id="local",
                resource_library_id="library",
                source_path="Media/B.mkv",
                source_display="Media/B.mkv",
                now=_at(2),
            )
            # The pipeline enters a real Storage mutation and then the call
            # raises: the pass ends technically with no Result at all.
            self.scheduling.begin_mutation(claim, item, "move", now=_at(3))
            marker["item"] = item.item_id
            raise RuntimeError("synthetic interrupted dispatch")

        admission = self.admit()
        self.engine(runner).run_next()
        task = self.repository.get_task(admission.task.task_id)
        state = self.scheduling.state(admission.task.task_id)
        # Slice 48 RO-2: the ended technical attempt closed the flow — no
        # remote-stop proof, no Result demanded, no slot held.
        self.assertIs(PersistentTaskStatus.COMPLETED, task.status)
        self.assertIsNone(state.mutation_state)
        self.assertIs(TaskQueueState.SETTLED, state.queue_state)
        self.assertEqual(0, self.scheduling.capacity_use())
        retired = self.repository.get_item(marker["item"])
        self.assertIsNotNone(retired)
        assert retired is not None
        # The attempt is retired with honest unknown-effect evidence — never a
        # fabricated Result and never a manufactured success.
        self.assertIs(TaskItemStatus.FAILED, retired.status)
        self.assertEqual("technical_stop", retired.stage)
        self.assertIn("unknown", retired.error or "")
        self.assertEqual(1, len(self.repository.list_results(admission.task.task_id)))
        # The settled Task is final for further passes and for a reopen.
        self.engine(lambda *_args: None).run_next()
        self.assertIs(
            PersistentTaskStatus.COMPLETED,
            self.repository.get_task(admission.task.task_id).status,
        )
        with SQLiteTaskRepository(self.database) as reopened:
            self.assertIs(
                PersistentTaskStatus.COMPLETED,
                reopened.get_task(admission.task.task_id).status,
            )
            self.assertIsNone(reopened.get_task_scheduling(admission.task.task_id).mutation_state)

    def test_missing_result_never_holds_the_slot_of_an_ended_boundary(self):
        """The repository close rule accepts a terminal item without a Result."""

        admission = self.admit()
        claim = self.claimed()
        item = self.scheduling.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path="Media/A.mkv",
            source_display="Media/A.mkv",
            now=_at(2),
        )
        # The exact Slice 48 boundary: the attempt entered a mutation, then
        # ended technically with a terminal item and no Result for that
        # attempt — recorded history, not a live call.
        self.repository.begin_scheduled_mutation(
            claim.fence(_at(3)), item_id=item.item_id, action="move"
        )
        self.scheduling.record_item(
            claim,
            replace(item, status=TaskItemStatus.FAILED, stage="technical_stop"),
            now=_at(4),
        )
        updated = self.scheduling.settle(
            claim,
            task=replace(
                self.repository.get_task(admission.task.task_id),
                status=PersistentTaskStatus.COMPLETED,
                completed_at=_at(4),
            ),
            items=(),
            now=_at(4),
            close_recorded_unknown_boundary=True,
        )
        self.assertIs(TaskQueueState.SETTLED, updated.queue_state)
        self.assertIsNone(updated.mutation_state)
        self.assertEqual(0, self.scheduling.capacity_use())


class TaskOwnFailureTests(_KernelHarness):
    """A Task-own orchestration failure stays failed with any file population."""

    def test_unlinked_task_is_a_flow_failure(self):
        def runner(task, claim, clock=None, heartbeat=None):
            raise AssertionError("an unlinked Task must never run the pipeline")

        admission = self.admit()
        # The engine's automatic branch is reached only with a scheduling row;
        # an automatic Task without a runner is the broken-orchestration case.
        worker = ManualTaskEngineWorker(
            self.repository,
            self.scheduling,
            None,
            None,
            worker_id="worker-1",
            clock=lambda: _at(4),
            automatic_runner=None,
            notice=lambda line: None,
        )
        worker.run_next()
        task = self.repository.get_task(admission.task.task_id)
        self.assertIs(PersistentTaskStatus.FAILED, task.status)
        self.assertIsNotNone(task.completed_at)

    def test_runner_exception_without_a_mutation_is_a_flow_failure(self):
        def runner(task, claim, clock=None, heartbeat=None):
            raise RuntimeError("synthetic orchestration crash")

        admission = self.admit()
        self.engine(runner).run_next()
        task = self.repository.get_task(admission.task.task_id)
        self.assertIs(PersistentTaskStatus.FAILED, task.status)
        state = self.scheduling.state(admission.task.task_id)
        self.assertIs(TaskQueueState.SETTLED, state.queue_state)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
