from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

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

    def __init__(self, repository: TaskRetryRepository) -> None:
        self._repository = repository

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
                error=None,
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
    ) -> TaskRetryRequestDecision:
        normalized_actor = self._text(actor, self.MAX_ACTOR)
        if not normalized_actor:
            raise ValueError("task retry actor is required")
        item = self._repository.get_item(item_id)
        if item is None:
            raise LookupError(f"TaskItem {item_id!r} was not found")
        if item.status not in {TaskItemStatus.FAILED, TaskItemStatus.PARTIAL}:
            raise ValueError("TaskItem is not failed or partial")
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
            error=None,
        )
        self._repository.request_task_retries((TaskRetryBatchRequest(decision, pending),))
        return decision

    @staticmethod
    def _text(value: str | None, limit: int) -> str | None:
        normalized = " ".join(value.split())[:limit] if value is not None else ""
        return normalized or None
