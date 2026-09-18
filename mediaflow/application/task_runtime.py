from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from mediaflow.application.media_organizer import (
    MediaOrganizerBatchResult,
    MediaOrganizerItemResult,
)
from mediaflow.domain.media_evidence import PipelineEvidence
from mediaflow.domain.organizer import (
    ExecutionEffectCertainty,
    ExecutionStatus,
    OrganizePlan,
    OrganizePolicy,
)
from mediaflow.domain.task_persistence import (
    FileOperationLockRepository,
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskRepository,
    PersistentTaskStatus,
    TaskItemStatus,
)


class TaskLockError(RuntimeError):
    pass


class TaskPauseRequested(RuntimeError):
    pass


class TaskClaimLost(RuntimeError):
    """A guarded Task publication found the Worker's claim no longer current."""


class PersistentTaskCoordinator:
    """Persists orchestration state without owning any media strategy decision."""

    def __init__(
        self,
        repository: PersistentTaskRepository,
        locks: FileOperationLockRepository,
    ) -> None:
        self.repository = repository
        self.locks = locks

    def create(
        self,
        command: str,
        *,
        execute_authorized: bool,
        scope_path: str | None = None,
        item_limit: int | None = None,
        configuration_snapshot_id: str | None = None,
        configuration_snapshot_digest: str | None = None,
        require_configuration_snapshot: bool = False,
        status: PersistentTaskStatus | None = None,
    ) -> PersistentTask:
        if item_limit is not None and item_limit < 1:
            raise ValueError("task item limit must be positive")
        if (configuration_snapshot_id is None) != (configuration_snapshot_digest is None):
            raise ValueError("Task configuration snapshot ID and digest must be provided together")
        if require_configuration_snapshot and (
            not configuration_snapshot_id or not configuration_snapshot_digest
        ):
            raise ValueError("managed Task creation requires a configuration snapshot pin")
        now = datetime.now(UTC)
        task = PersistentTask(
            str(uuid4()),
            command,
            status or PersistentTaskStatus.RUNNING,
            execute_authorized,
            now,
            now,
            started_at=now if status is PersistentTaskStatus.RUNNING or status is None else None,
            scope_path=scope_path,
            item_limit=item_limit,
            configuration_snapshot_id=configuration_snapshot_id,
            configuration_snapshot_digest=configuration_snapshot_digest,
        )
        self.repository.create_task(task)
        return task

    def begin_queued(
        self,
        task_id: str,
        *,
        transfer_fence: tuple[str, str, datetime] | None = None,
    ) -> PersistentTask:
        """Publish the running boundary of one admitted (queued) Task.

        The resident Worker calls this after a successful claim, immediately
        before the first OrganizerExecutor call: a queued transfer Task only
        becomes running under the Worker's claim fence, never inside the
        admitting HTTP request.  When a fence is supplied the publish is
        compare-and-set against the live claim, so a Worker that already lost
        ownership cannot mark the Task running.
        """

        task = self.require(task_id)
        if task.status is PersistentTaskStatus.RUNNING:
            return task
        if task.status is not PersistentTaskStatus.PENDING:
            raise RuntimeError(f"task {task_id!r} is not queued")
        now = datetime.now(UTC)
        running = replace(
            task,
            status=PersistentTaskStatus.RUNNING,
            updated_at=now,
            started_at=now,
        )
        if transfer_fence is not None:
            transfer_id, claim_token, claim_now = transfer_fence
            guarded = getattr(self.repository, "update_task_guarded", None)
            if callable(guarded) and not guarded(
                running,
                transfer_id=transfer_id,
                claim_token=claim_token,
                now=claim_now,
            ):
                raise TaskClaimLost()
            return running
        self.repository.update_task(running)
        return running

    def reopen(self, task_id: str, *, execute: bool) -> PersistentTask:
        task = self.require(task_id)
        if execute and not task.execute_authorized:
            raise ValueError(
                "original task was not execute-authorized; retry cannot enable execute"
            )
        now = datetime.now(UTC)
        reopened = replace(
            task,
            status=PersistentTaskStatus.RUNNING,
            updated_at=now,
            completed_at=None,
            error=None,
            pause_requested=False,
        )
        self.locks.reclaim_task_locks(task_id)
        self.repository.update_task(reopened)
        return reopened

    def require(self, task_id: str) -> PersistentTask:
        task = self.repository.get_task(task_id)
        if task is None:
            raise LookupError(f"task {task_id!r} was not found")
        return task

    def begin_item(
        self,
        task_id: str,
        storage_id: str,
        resource_library_id: str,
        source_path: str,
        source_display: str,
        *,
        transfer_fence: tuple[str, str, datetime] | None = None,
        adopt_existing: bool = False,
    ) -> PersistentTaskItem:
        task = self.require(task_id)
        if task.status is not PersistentTaskStatus.RUNNING:
            raise RuntimeError(f"task {task_id!r} is not running")
        if task.pause_requested or self.repository.task_pause_requested(task_id):
            raise TaskPauseRequested(f"task {task_id!r} pause was requested")
        item_id = str(uuid5(NAMESPACE_URL, f"{task_id}:{storage_id}:{source_path}"))
        previous = self.repository.get_item(item_id)
        now = datetime.now(UTC)
        # A transfer continuation is one claim-fenced ownership boundary: this
        # frame must own the live claim *and* its exact lock generation before
        # any TaskItem write.  Publishing the started row first would let a
        # frame that already lost its claim erase the live owner's durable
        # recovery checkpoint and consume an attempt.
        fenced = transfer_fence if (adopt_existing and transfer_fence is not None) else None
        # The generation is minted per acquisition and never persisted on the
        # item, published in an operator document or logged.
        lock_owner_token = f"{task_id}:{uuid4().hex}"
        # A continuation of a takeover must hand the exclusion over *without*
        # ever deleting it: the row is rotated in place, so a competing Task can
        # never acquire the normalized path in the gap between a blanket
        # reclaim and this acquisition.  A fresh item still inserts normally.
        acquirer = getattr(self.locks, "adopt_or_acquire", None) if adopt_existing else None
        if callable(acquirer):
            acquired = bool(
                acquirer(
                    storage_id,
                    source_path,
                    task_id,
                    now,
                    owner_token=lock_owner_token,
                    transfer_fence=transfer_fence,
                )
            )
        else:
            acquired = self.locks.acquire(
                storage_id, source_path, task_id, now, owner_token=lock_owner_token
            )
        if not acquired:
            if fenced is not None and not self._claim_is_current(fenced):
                # The lease lapsed before the boundary was crossed.  Stop with
                # *zero* writes, so the current owner's TaskItem, Result,
                # transfer mutation boundary and replacement lock generation
                # stay exactly as they were: no attempt is consumed and no
                # user-visible business failure is fabricated.
                raise TaskClaimLost()
            # A conflict against a live claim is a real refusal, and it is
            # published under that same fence so a claim lost between the
            # acquisition attempt and this write can never surface as a stale
            # failure.  The bounded lock failure is terminal, so the row carries
            # no resume checkpoint; a frame whose claim already lapsed raises
            # TaskClaimLost above and writes nothing at all.
            conflict = PersistentTaskItem(
                item_id,
                task_id,
                storage_id,
                resource_library_id,
                source_path,
                source_display,
                TaskItemStatus.FAILED,
                "lock",
                (previous.attempts if previous else 0) + 1,
                previous.created_at if previous else now,
                datetime.now(UTC),
                error="source is locked by another active task",
            )
            if not self._publish_item_start(conflict, fenced):
                raise TaskClaimLost()
            raise TaskLockError(conflict.error)
        if fenced is not None and previous is not None:
            # A valid continuation keeps the predecessor's durable recovery
            # checkpoint.  That row is the only authority a crash between this
            # boundary and the first new progress write leaves behind, so it
            # survives `begin_item` intact and is superseded only by a later
            # claim-guarded progress or terminal publication.
            started = replace(
                previous,
                resource_library_id=resource_library_id,
                source_display=source_display,
                status=TaskItemStatus.PROCESSING,
                stage="pipeline",
                attempts=previous.attempts + 1,
                updated_at=now,
                error=None,
            )
        else:
            started = PersistentTaskItem(
                item_id,
                task_id,
                storage_id,
                resource_library_id,
                source_path,
                source_display,
                TaskItemStatus.PROCESSING,
                "pipeline",
                (previous.attempts if previous else 0) + 1,
                previous.created_at if previous else now,
                now,
            )
        if not self._publish_item_start(started, fenced):
            # The claim lapsed between the acquisition and this publication.
            # Release **only** this frame's exact generation and stop: if a
            # replacement owner has already rotated this Task's rows, this
            # delete matches nothing and its row is untouched, and the
            # exclusion invariant still arbitrates because whichever Task holds
            # the row makes every other acquisition fail closed.  No
            # compensating TaskItem write is ever performed.
            self.locks.release(storage_id, source_path, task_id, owner_token=lock_owner_token)
            raise TaskClaimLost()
        persisted_item = self.repository.get_item(item_id)
        if persisted_item is not None:
            started = persisted_item
        # The generation travels with the execution frame for the whole item
        # lifetime: every terminal/publication path releases exactly it.
        return replace(started, lock_owner_token=lock_owner_token)

    def _claim_is_current(self, fence: tuple[str, str, datetime]) -> bool:
        """Whether the exact live Worker claim named by ``fence`` still holds.

        A repository that cannot answer the question fails closed, so an
        unprovable ownership boundary is always treated as lost.
        """

        check = getattr(self.repository, "transfer_claim_is_current", None)
        if not callable(check):
            return False
        return bool(check(fence[0], fence[1], fence[2]))

    def _publish_item_start(
        self,
        item: PersistentTaskItem,
        fence: tuple[str, str, datetime] | None,
    ) -> bool:
        """Publish one transfer start under the claim fence when one applies.

        The guarded write is compare-and-set against the live claim, so a frame
        that lost ownership writes nothing at all.  It can be reused here
        because the transfer path resolves any recorded ``mutation_in_flight``
        boundary *before* executing items, so the boundary is already clear and
        the guard's atomic clear is a no-op.  An unfenced caller (Organize, the
        manual execution path) keeps the historical unguarded write.
        """

        if fence is not None:
            guarded = getattr(self.repository, "upsert_item_guarded", None)
            if callable(guarded):
                transfer_id, claim_token, claim_now = fence
                return bool(
                    guarded(
                        item,
                        transfer_id=transfer_id,
                        claim_token=claim_token,
                        now=claim_now,
                    )
                )
        self.repository.upsert_item(item)
        return True

    def release_item_lock(self, item: PersistentTaskItem) -> None:
        """Release exactly the acquisition generation this frame owns.

        ``item.lock_owner_token`` is set only by ``begin_item`` on the frame
        that actually acquired the row.  An item reloaded from the repository
        (or written by an older/adapter implementation) carries no generation:
        releasing it as a task-level delete would let a stale owner remove a
        replacement owner's row, so such a frame releases nothing and the lock
        is retired only by the authorized Task-level transition that owns the
        Task at that moment (takeover, cancel, pause, reclaim).
        """

        token = getattr(item, "lock_owner_token", None)
        if not isinstance(token, str) or not token:
            return
        self.locks.release(
            item.storage_id,
            item.source_path,
            item.task_id,
            owner_token=token,
        )

    def cancel(self, task_id: str) -> PersistentTask:
        task = self.require(task_id)
        now = datetime.now(UTC)
        for item in self.repository.list_items(task_id):
            if item.status in {
                TaskItemStatus.PENDING,
                TaskItemStatus.PROCESSING,
                TaskItemStatus.PAUSED,
            }:
                self.repository.upsert_item(
                    replace(
                        item,
                        status=TaskItemStatus.CANCELLED,
                        stage="cancelled",
                        updated_at=now,
                        error="task cancelled",
                    )
                )
        cancelled = replace(
            task,
            status=PersistentTaskStatus.CANCELLED,
            updated_at=now,
            completed_at=now,
            error="task cancelled",
        )
        self.repository.update_task(cancelled)
        self.locks.reclaim_task_locks(task_id)
        return cancelled

    def request_pause(self, task_id: str) -> PersistentTask:
        return self.repository.request_task_pause(task_id, datetime.now(UTC))

    def requeue(self, task_id: str) -> PersistentTask:
        """Re-admit one paused Task for Worker pickup without executing it.

        The queued state is only an admission state: the resident Worker later
        publishes the running boundary under its own claim fence.  No Storage
        work happens inside the caller's request.
        """

        task = self.require(task_id)
        if task.status is PersistentTaskStatus.PENDING:
            return task
        if task.status is not PersistentTaskStatus.PAUSED:
            raise ValueError("only a paused task can be re-queued")
        now = datetime.now(UTC)
        queued = replace(
            task,
            status=PersistentTaskStatus.PENDING,
            updated_at=now,
            completed_at=None,
            error=None,
            pause_requested=False,
        )
        self.repository.update_task(queued)
        return queued

    def pause_requested(self, task_id: str) -> bool:
        return self.repository.task_pause_requested(task_id)

    def cancellation_observed(self, task_id: str) -> bool:
        """Whether one durable cooperative cancellation was accepted for this Task.

        A running handler polls this at its supported item boundary: the
        accepted transition is durable, so the handler stops admitting new work
        instead of relying on an in-memory signal, and the in-flight item keeps
        its confinement lock until its own outcome is recorded.
        """

        task = self.repository.get_task(task_id)
        return task is not None and task.status is PersistentTaskStatus.CANCELLED

    def acknowledge_pause(self, task_id: str) -> PersistentTask:
        task = self.require(task_id)
        if task.status is PersistentTaskStatus.PAUSED:
            return task
        if task.status is not PersistentTaskStatus.RUNNING or not task.pause_requested:
            raise ValueError("only a running task with a pause request can be paused")
        now = datetime.now(UTC)
        for item in self.repository.list_items(task_id):
            if item.status in {TaskItemStatus.PENDING, TaskItemStatus.PROCESSING}:
                self.repository.upsert_item(
                    replace(
                        item,
                        status=TaskItemStatus.PAUSED,
                        stage="paused",
                        updated_at=now,
                        error=None,
                    )
                )
        paused = replace(
            task,
            status=PersistentTaskStatus.PAUSED,
            updated_at=now,
            completed_at=None,
            error=None,
            pause_requested=False,
        )
        self.repository.update_task(paused)
        self.locks.reclaim_task_locks(task_id)
        return paused

    def record_discovered(
        self,
        task_id: str,
        storage_id: str,
        resource_library_id: str,
        source_path: str,
        source_display: str,
    ) -> PersistentTaskItem:
        now = datetime.now(UTC)
        item = PersistentTaskItem(
            str(uuid5(NAMESPACE_URL, f"{task_id}:{storage_id}:{source_path}")),
            task_id,
            storage_id,
            resource_library_id,
            source_path,
            source_display,
            TaskItemStatus.SKIPPED,
            "scanned",
            0,
            now,
            now,
        )
        self.repository.upsert_item(item)
        persisted_item = self.repository.get_item(item.item_id)
        if persisted_item is not None:
            item = persisted_item
        return item

    def complete_item(
        self,
        item: PersistentTaskItem,
        result: MediaOrganizerItemResult,
        *,
        analysis_only: bool = False,
    ) -> None:
        now = datetime.now(UTC)
        execution = result.execution
        if execution is None:
            if result.error:
                status = TaskItemStatus.FAILED
            elif analysis_only:
                # An analysis-only Preview outcome: the full read-only planning
                # chain completed and persisted its findings, but no executor
                # operation ran.  DRY_RUN is the accurate existing completion
                # state (no new TaskItemStatus is authorized).
                status = TaskItemStatus.DRY_RUN
            else:
                status = TaskItemStatus.SKIPPED
        else:
            status = {
                ExecutionStatus.SUCCESS: TaskItemStatus.SUCCESS,
                ExecutionStatus.DRY_RUN: TaskItemStatus.DRY_RUN,
                ExecutionStatus.PARTIAL: TaskItemStatus.PARTIAL,
                ExecutionStatus.FAILED: TaskItemStatus.FAILED,
                ExecutionStatus.SKIPPED: TaskItemStatus.SKIPPED,
            }[execution.status]
            if result.error and status not in {TaskItemStatus.PARTIAL, TaskItemStatus.FAILED}:
                status = TaskItemStatus.FAILED
        plan = result.plan
        completed = replace(
            item,
            status=status,
            stage="completed" if not status.retryable else "failed",
            updated_at=now,
            plan_id=plan.plan_id if plan else None,
            destination_storage_id=(
                plan.destination_location.storage_id if plan and plan.destination_location else None
            ),
            destination_path=(
                plan.destination_location.path if plan and plan.destination_location else None
            ),
            execution_status=execution.status.value if execution else None,
            error=(
                result.failure.encode()
                if result.failure is not None
                else result.error
                or ("; ".join(execution.errors) if execution and execution.errors else None)
            ),
        )
        try:
            atomic = getattr(self.repository, "complete_item_with_evidence", None)
            if callable(atomic):
                atomic(completed, self._result(completed, result, now), result.evidence)
            else:
                self.repository.append_result(self._result(completed, result, now))
                self.repository.upsert_item(completed)
                if result.evidence is not None:
                    self.record_evidence(result.evidence)
        finally:
            self.release_item_lock(item)

    def record_evidence(self, evidence: PipelineEvidence) -> None:
        """Persist one bounded evidence record at a TaskItem boundary."""

        append = getattr(self.repository, "append_evidence", None)
        if callable(append):
            append(evidence)

    def complete_direct_item(
        self,
        item: PersistentTaskItem,
        *,
        status: TaskItemStatus,
        operation: str,
        target_path: str | None = None,
        error: str | None = None,
        effect_certainty: str = "none",
        uncertain_effects: tuple[str, ...] = (),
        destination_storage_id: str | None = None,
        completed_operations: tuple[str, ...] = (),
        execution_status: str | None = None,
        stage: str | None = None,
        transfer_fence: tuple[str, str, datetime] | None = None,
    ) -> bool:
        """Persist one direct Files command outcome and release its lock.

        Direct commands carry no media identity or policy evidence: the
        durable record is the bounded operation, status and executor-owned
        effect evidence only.  The persisted source/target identity is the
        bounded logical ResourceLibrary-relative path, never the host root.
        A transfer item persists its exact destination Storage identity and
        its executor-owned completed checkpoints, so reloading the Task or
        Result detail reproduces the truthful known state without the original
        HTTP response.

        ``transfer_fence`` is the Worker-side claim comparison
        ``(transfer_id, claim_token, now)``: when supplied, the TaskItem and
        its Result commit only while this Worker still owns the live claim, and
        a lost claim returns ``False`` without writing anything.
        """

        now = datetime.now(UTC)
        source_display = item.source_display if item.source_display else item.source_path
        target_display = (
            target_path if isinstance(target_path, str) and target_path else source_display
        )
        completed = replace(
            item,
            status=status,
            stage=stage or ("completed" if not status.retryable else "failed"),
            updated_at=now,
            destination_storage_id=destination_storage_id or item.storage_id,
            destination_path=target_display,
            execution_status=(
                execution_status
                if execution_status is not None
                else (ExecutionStatus.SUCCESS.value if status is TaskItemStatus.SUCCESS else None)
            ),
            error=error,
            # The in-flight progress marker is consumed by the terminal outcome.
            progress=None,
        )
        record = PersistentResultRecord(
            f"{item.item_id}:{item.attempts}",
            item.task_id,
            item.item_id,
            item.storage_id,
            source_display,
            completed.destination_storage_id,
            target_display,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            operation,
            status.value,
            now,
            error=error,
            completed_operations=tuple(completed_operations),
            effect_certainty=effect_certainty,
            uncertain_effects=uncertain_effects,
        )
        try:
            if transfer_fence is not None:
                transfer_id, claim_token, claim_now = transfer_fence
                guarded = getattr(self.repository, "complete_item_with_evidence_guarded", None)
                if callable(guarded):
                    return bool(
                        guarded(
                            completed,
                            record,
                            None,
                            transfer_id=transfer_id,
                            claim_token=claim_token,
                            now=claim_now,
                        )
                    )
            atomic = getattr(self.repository, "complete_item_with_evidence", None)
            if callable(atomic):
                atomic(completed, record, None)
            else:
                self.repository.append_result(record)
                self.repository.upsert_item(completed)
        finally:
            # This unconditional cleanup is exactly the stale-owner race B
            # reproduced: the guarded CAS above may have returned False after a
            # replacement Worker re-acquired the same Task/path.  The release is
            # therefore bound to this frame's own acquisition generation, so it
            # deletes nothing when the row now belongs to the replacement owner.
            self.release_item_lock(item)
        return True

    def record_transfer_progress(
        self,
        item: PersistentTaskItem,
        *,
        destination_storage_id: str,
        destination_resource_library_id: str,
        destination_path: str,
        operation: str,
        conflict_mode: str,
        status: TaskItemStatus,
        confirmed_entries: tuple[tuple[str, str, str], ...],
        confirmed_truncated: bool,
        entries: tuple[dict[str, object], ...],
        completed_entries: int,
        failed_entries: int,
        skipped_entries: int,
        truncated: bool,
        transfer_fence: tuple[str, str, datetime] | None = None,
    ) -> bool:
        """Persist the bounded in-flight progress of one transfer item.

        The snapshot is the process-interruption authority: a TaskItem left
        ``PROCESSING`` keeps its confirmed per-entry scope, its endpoint
        identities and its recorded per-entry outcomes durable, so recovery
        continues only from the recorded known-safe state instead of guessing
        or re-enumerating a possibly changed source.  Both lists are bounded;
        the aggregate counters stay exact even when a list is truncated.

        ``transfer_fence`` is the Worker-side claim comparison
        ``(transfer_id, claim_token, now)``: when supplied, progress is
        published only while this Worker still owns the live claim, and a lost
        claim returns ``False`` without writing a stale snapshot.
        """

        payload = json.dumps(
            {
                "version": 1,
                "status": status.value,
                "operation": operation,
                "conflictMode": conflict_mode,
                "destinationStorageId": destination_storage_id,
                "destinationResourceLibraryId": destination_resource_library_id,
                "destinationPath": destination_path,
                "confirmedEntries": [list(entry) for entry in confirmed_entries],
                "confirmedTruncated": confirmed_truncated,
                "completedEntries": completed_entries,
                "failedEntries": failed_entries,
                "skippedEntries": skipped_entries,
                "truncated": truncated,
                "entries": entries,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        snapshot = replace(
            item,
            status=status,
            stage=item.stage,
            updated_at=datetime.now(UTC),
            destination_storage_id=destination_storage_id,
            destination_path=destination_path,
            progress=payload,
        )
        if transfer_fence is not None:
            transfer_id, claim_token, claim_now = transfer_fence
            guarded = getattr(self.repository, "upsert_item_guarded", None)
            if callable(guarded):
                return bool(
                    guarded(
                        snapshot,
                        transfer_id=transfer_id,
                        claim_token=claim_token,
                        now=claim_now,
                    )
                )
        self.repository.upsert_item(snapshot)
        return True

    def wait_for_confirmation(
        self,
        item: PersistentTaskItem,
        plan: OrganizePlan,
        policy: OrganizePolicy,
        *,
        evidence: PipelineEvidence | None = None,
    ) -> None:
        from mediaflow.application.conflict_resolution import ConfirmationService

        now = datetime.now(UTC)
        waiting = replace(
            item,
            status=TaskItemStatus.WAITING_CONFIRM,
            stage="waiting_confirm",
            updated_at=now,
            plan_id=plan.plan_id,
            destination_storage_id=plan.target_storage_id,
            destination_path=(
                plan.destination_location.path if plan.destination_location else plan.target
            ),
            error=None,
        )
        ConfirmationService(self.repository).create(
            task_id=item.task_id,
            item_id=item.item_id,
            plan=plan,
            policy=policy,
            item=waiting,
            evidence=evidence,
        )
        self.release_item_lock(item)

    def wait_for_metadata(
        self,
        item,
        identification,
        metadata_policy_id: str,
        *,
        evidence: PipelineEvidence | None = None,
    ) -> None:
        from mediaflow.application.metadata_review import MetadataReviewService

        MetadataReviewService(self.repository).create(
            item, identification, metadata_policy_id, evidence=evidence
        )
        self.release_item_lock(item)

    def wait_for_recognition(
        self,
        item,
        recognition,
        recognition_types,
        *,
        evidence: PipelineEvidence | None = None,
    ) -> None:
        from mediaflow.application.recognition_review import RecognitionReviewService

        RecognitionReviewService(self.repository, recognition_types).create(
            item, recognition, evidence=evidence
        )
        self.release_item_lock(item)

    def wait_for_metadata_correction(
        self,
        item,
        identification,
        policy,
        parsed,
        *,
        evidence: PipelineEvidence | None = None,
    ) -> None:
        from mediaflow.application.metadata_correction import MetadataCorrectionService

        MetadataCorrectionService(self.repository, (policy,)).create(
            item, identification, policy, parsed, evidence=evidence
        )
        self.release_item_lock(item)

    def wait_for_classification(
        self,
        item,
        result,
        policy,
        identity,
        *,
        evidence: PipelineEvidence | None = None,
    ) -> None:
        from mediaflow.application.classification_review import ClassificationReviewService

        ClassificationReviewService(self.repository).create(
            item, result, policy, identity, evidence=evidence
        )
        self.release_item_lock(item)

    def finish(
        self,
        task_id: str,
        batch: MediaOrganizerBatchResult,
        *,
        transfer_fence: tuple[str, str, datetime] | None = None,
    ) -> PersistentTask:
        task = self.require(task_id)
        if task.status is PersistentTaskStatus.CANCELLED:
            # A durable cooperative cancellation is never overwritten by a later
            # completion: the operator's accepted request stays the Task outcome
            # and the items/results keep their own recorded state.
            return task
        items = self.repository.list_items(task_id)
        failed = sum(
            item.status in {TaskItemStatus.FAILED, TaskItemStatus.PARTIAL} for item in items
        )
        waiting_statuses = {
            TaskItemStatus.WAITING_CONFIRM,
            TaskItemStatus.WAITING_RECOGNITION,
            TaskItemStatus.WAITING_METADATA,
            TaskItemStatus.WAITING_METADATA_CORRECTION,
            TaskItemStatus.WAITING_CLASSIFICATION,
        }
        waiting = sum(item.status in waiting_statuses for item in items)
        ignored = sum(item.status is TaskItemStatus.IGNORED for item in items)
        completed = sum(
            not item.status.retryable
            and item.status not in waiting_statuses
            and item.status is not TaskItemStatus.IGNORED
            for item in items
        )
        status = (
            PersistentTaskStatus.PARTIAL_SUCCESS
            if waiting or ignored or (failed and completed)
            else PersistentTaskStatus.FAILED
            if failed or batch.scan_errors
            else PersistentTaskStatus.COMPLETED
        )
        now = datetime.now(UTC)
        final = replace(
            task,
            status=status,
            updated_at=now,
            completed_at=now,
            total_items=len(items),
            completed_items=completed,
            failed_items=failed + len(batch.scan_errors),
            error="scan errors occurred" if batch.scan_errors else None,
        )
        if transfer_fence is not None:
            transfer_id, claim_token, claim_now = transfer_fence
            guarded = getattr(self.repository, "update_task_guarded", None)
            if callable(guarded):
                # A Worker that lost its claim must not publish the aggregate:
                # the replacement owner owns the Task's terminal state.
                if not guarded(
                    final,
                    transfer_id=transfer_id,
                    claim_token=claim_token,
                    now=claim_now,
                ):
                    return self.require(task_id)
                return final
        self.repository.update_task(final)
        return final

    def retryable_items(self, task_id: str, *, failed_only: bool) -> tuple[PersistentTaskItem, ...]:
        self.require(task_id)
        statuses = (
            {TaskItemStatus.FAILED, TaskItemStatus.PARTIAL}
            if failed_only
            else {
                TaskItemStatus.PENDING,
                TaskItemStatus.PROCESSING,
                TaskItemStatus.FAILED,
                TaskItemStatus.PARTIAL,
                TaskItemStatus.CANCELLED,
                TaskItemStatus.PAUSED,
            }
        )
        successful_results = {
            result.item_id
            for result in self.repository.list_results(task_id)
            if result.status
            in {
                TaskItemStatus.SUCCESS.value,
                TaskItemStatus.DRY_RUN.value,
                TaskItemStatus.SKIPPED.value,
            }
        }
        return tuple(
            item
            for item in self.repository.list_items(task_id)
            if item.status in statuses and item.item_id not in successful_results
        )

    @staticmethod
    def _result(
        item: PersistentTaskItem,
        result: MediaOrganizerItemResult,
        timestamp: datetime,
    ) -> PersistentResultRecord:
        strategy = result.strategy
        identity = strategy.metadata.identity if strategy and strategy.metadata else None
        plan = result.plan
        execution = result.execution
        effect_certainty, uncertain_effects = _effect_evidence(execution)
        return PersistentResultRecord(
            f"{item.item_id}:{item.attempts}",
            item.task_id,
            item.item_id,
            item.storage_id,
            item.source_path,
            item.destination_storage_id,
            item.destination_path,
            strategy.recognition.recognition_type_id if strategy else None,
            identity.provider if identity else None,
            identity.provider_id if identity else None,
            strategy.policy.metadata_policy_id if strategy and strategy.policy else None,
            strategy.policy.naming_policy_id if strategy and strategy.policy else None,
            strategy.policy.classification_policy_id if strategy and strategy.policy else None,
            strategy.policy.organize_policy_id if strategy and strategy.policy else None,
            execution.operation.value if execution else (plan.operation.value if plan else None),
            item.status.value,
            timestamp,
            identity.title if identity else None,
            item.error,
            execution.completed_operations if execution else (),
            len(plan.attachment_plans) if plan else 0,
            len(result.retry_events),
            (
                result.failure.category
                if result.failure is not None
                else result.retry_events[-1].category.value
                if result.retry_events
                else None
            ),
            execution.cleanup_status.value if execution else None,
            len(execution.cleanup_steps) if execution else 0,
            effect_certainty,
            uncertain_effects,
            item.source_occurrence_id,
            item.source_fingerprint,
            item.source_fingerprint_state,
        )


def _effect_evidence(execution) -> tuple[str, tuple[str, ...]]:
    """Persist only executor-owned effect evidence, never status/error inference."""
    if execution is None:
        # A failure before planning/execution is known to have no mutation in this invocation.
        return "none", ()
    try:
        certainty = ExecutionEffectCertainty(execution.effect_certainty)
    except (AttributeError, ValueError):
        return "unknown", ()
    return certainty.value, tuple(execution.uncertain_effects)
