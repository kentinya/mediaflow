from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.recovery import RecoveryAdmissionError, RecoveryAdmissionReason
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.domain.task_retry import (
    TaskRetryBatchRequest,
    TaskRetryRepository,
    TaskRetryRequestDecision,
)


class TaskRetryRequestService:
    MAX_ACTOR = 200
    MAX_NOTE = 500
    MAX_BATCH_SIZE = 100

    def __init__(
        self, repository: TaskRetryRepository, *, recovery_admission=None, snapshot_validator=None
    ) -> None:
        self._repository = repository
        if recovery_admission is None and snapshot_validator is not None:
            from mediaflow.application.recovery_admission import RecoveryAdmissionService

            recovery_admission = RecoveryAdmissionService(
                repository, snapshot_validator=snapshot_validator
            )
        self._recovery_admission = recovery_admission

    def request(
        self,
        *,
        actor: str,
        note: str | None = None,
        limit: int = 100,
        task_id: str | None = None,
    ) -> tuple[TaskRetryRequestDecision, ...]:
        normalized_actor = self._text(actor, self.MAX_ACTOR)
        if not normalized_actor:
            raise ValueError("task retry actor is required")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= self.MAX_BATCH_SIZE
        ):
            raise ValueError(f"task retry batch limit must be between 1 and {self.MAX_BATCH_SIZE}")
        items = self._repository.list_failed_items(limit=limit, task_id=task_id)
        if not items:
            raise ValueError("no failed task items were selected")
        if self._recovery_admission is not None:
            prepared = []
            for item in items:
                checkpoint = self._recovery_admission.checkpoint_service.get(
                    item.item_id, task_id=item.task_id
                )
                if "retry" not in checkpoint.permitted_action_ids:
                    raise RecoveryAdmissionError(
                        RecoveryAdmissionReason.ACTION_NOT_PERMITTED,
                        "retry is not permitted for one selected TaskItem",
                        current_checkpoint_version=checkpoint.checkpoint_version,
                    )
                prepared.append((item, checkpoint))
            decisions: list[TaskRetryRequestDecision] = []
            for item, checkpoint in prepared:
                request = self._recovery_admission.admit(
                    item.task_id,
                    item.item_id,
                    action_id="retry",
                    expected_checkpoint_version=checkpoint.checkpoint_version,
                    actor=normalized_actor,
                    note=note,
                )
                decisions.append(
                    TaskRetryRequestDecision(
                        request.request_id,
                        request.task_id,
                        request.item_id,
                        request.requested_at,
                        request.actor,
                        request.note,
                    )
                )
            return tuple(decisions)
        now = datetime.now(UTC)
        normalized_note = self._text(note, self.MAX_NOTE)
        requests: list[TaskRetryBatchRequest] = []
        for item in items:
            decision = TaskRetryRequestDecision(
                str(uuid4()),
                item.task_id,
                item.item_id,
                now,
                normalized_actor,
                normalized_note,
            )
            pending = replace(
                item,
                status=TaskItemStatus.PENDING,
                stage="task_retry_requested",
                updated_at=now,
            )
            requests.append(TaskRetryBatchRequest(decision, pending))
        self._repository.request_task_retries(tuple(requests))
        return tuple(request.decision for request in requests)

    def request_item(
        self,
        item_id: str,
        *,
        actor: str,
        note: str | None = None,
        expected_checkpoint_version: str | None = None,
    ) -> TaskRetryRequestDecision:
        from mediaflow.application.recovery_admission import RecoveryAdmissionService

        admission = self._recovery_admission or RecoveryAdmissionService(self._repository)
        expected = expected_checkpoint_version
        if expected is None:
            expected = admission.checkpoint_service.get(item_id).checkpoint_version
        item = self._repository.get_item(item_id)
        if item is None:
            raise LookupError(f"TaskItem {item_id!r} was not found")
        request = admission.admit(
            item.task_id if item else "",
            item_id,
            action_id="retry",
            expected_checkpoint_version=expected,
            actor=actor,
            note=note,
        )
        return TaskRetryRequestDecision(
            request.request_id,
            request.task_id,
            request.item_id,
            request.requested_at,
            request.actor,
            request.note,
        )

    def _legacy_request_item(
        self,
        item_id: str,
        *,
        actor: str,
        note: str | None = None,
    ) -> TaskRetryRequestDecision:
        normalized_actor = self._text(actor, self.MAX_ACTOR)
        if not normalized_actor:
            raise ValueError("task retry actor is required")
        item = self._repository.get_item(item_id)
        if item is None:
            raise LookupError(f"TaskItem {item_id!r} was not found")
        if item.status is not TaskItemStatus.FAILED:
            raise ValueError("TaskItem is not failed")
        now = datetime.now(UTC)
        decision = TaskRetryRequestDecision(
            str(uuid4()),
            item.task_id,
            item.item_id,
            now,
            normalized_actor,
            self._text(note, self.MAX_NOTE),
        )
        pending = replace(
            item,
            status=TaskItemStatus.PENDING,
            stage="task_retry_requested",
            updated_at=now,
        )
        self._repository.request_task_retries((TaskRetryBatchRequest(decision, pending),))
        return decision

    @staticmethod
    def _text(value: str | None, limit: int) -> str | None:
        normalized = " ".join(value.split())[:limit] if value is not None else ""
        return normalized or None
