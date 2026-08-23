from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.recognition_review import (
    RecognitionRetryBatchRequest,
    RecognitionRetryDecision,
    RecognitionReviewRepository,
    RecognitionReviewStatus,
)
from mediaflow.domain.task_persistence import TaskItemStatus


class RecognitionBatchRetryService:
    MAX_ACTOR = 200
    MAX_NOTE = 500
    MAX_BATCH_SIZE = 100

    def __init__(self, repository: RecognitionReviewRepository) -> None:
        self._repository = repository

    def request_pending(
        self,
        *,
        actor: str,
        note: str | None = None,
        limit: int = 100,
        task_id: str | None = None,
    ) -> tuple[RecognitionRetryDecision, ...]:
        normalized_actor = self._text(actor, self.MAX_ACTOR)
        if not normalized_actor:
            raise ValueError("recognition retry actor is required")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= self.MAX_BATCH_SIZE
        ):
            raise ValueError(
                f"recognition retry batch limit must be between 1 and {self.MAX_BATCH_SIZE}"
            )
        reviews = self._repository.list_pending_recognition_reviews(limit=limit, task_id=task_id)
        if not reviews:
            raise ValueError("no pending recognition reviews were selected")

        now = datetime.now(UTC)
        normalized_note = self._text(note, self.MAX_NOTE)
        requests: list[RecognitionRetryBatchRequest] = []
        for review in reviews:
            item = self._repository.get_item(review.item_id)
            if (
                item is None
                or item.task_id != review.task_id
                or item.status is not TaskItemStatus.WAITING_RECOGNITION
            ):
                raise ValueError("recognition retry TaskItem is not waiting")
            decision = RecognitionRetryDecision(
                str(uuid4()),
                review.review_id,
                review.task_id,
                review.item_id,
                now,
                normalized_actor,
                normalized_note,
            )
            requested = replace(
                review,
                status=RecognitionReviewStatus.RETRY_REQUESTED,
                updated_at=now,
                decided_at=now,
                actor=normalized_actor,
            )
            pending = replace(
                item,
                status=TaskItemStatus.PENDING,
                stage="recognition_retry_requested",
                updated_at=now,
                error=None,
            )
            requests.append(RecognitionRetryBatchRequest(requested, decision, pending))

        self._repository.request_batch_recognition_retry(tuple(requests))
        return tuple(request.decision for request in requests)

    @staticmethod
    def _text(value: str | None, limit: int) -> str | None:
        normalized = " ".join(value.split())[:limit] if value is not None else ""
        return normalized or None
