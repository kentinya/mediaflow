from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.recognition_review import (
    RecognitionRetryDecision,
    RecognitionReviewRepository,
    RecognitionReviewStatus,
)
from mediaflow.domain.task_persistence import TaskItemStatus


class RecognitionRetryService:
    MAX_ACTOR = 200
    MAX_NOTE = 500

    def __init__(self, repository: RecognitionReviewRepository) -> None:
        self._repository = repository

    def request(
        self,
        review_id: str,
        *,
        actor: str,
        note: str | None = None,
    ) -> RecognitionRetryDecision:
        normalized_actor = self._text(actor, self.MAX_ACTOR)
        if not normalized_actor:
            raise ValueError("recognition retry actor is required")
        review = self._repository.get_recognition_review(review_id)
        if review is None:
            raise LookupError(f"recognition review {review_id!r} was not found")
        if review.status is not RecognitionReviewStatus.PENDING:
            raise ValueError("recognition review is not pending")
        item = self._repository.get_item(review.item_id)
        if (
            item is None
            or item.task_id != review.task_id
            or item.status is not TaskItemStatus.WAITING_RECOGNITION
        ):
            raise ValueError("TaskItem is not waiting for this recognition review")
        now = datetime.now(UTC)
        decision = RecognitionRetryDecision(
            str(uuid4()),
            review.review_id,
            review.task_id,
            review.item_id,
            now,
            normalized_actor,
            self._text(note, self.MAX_NOTE),
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
        self._repository.request_recognition_retry(requested, decision, pending)
        return decision

    @staticmethod
    def _text(value: str | None, limit: int) -> str | None:
        normalized = " ".join(value.split())[:limit] if value is not None else ""
        return normalized or None
