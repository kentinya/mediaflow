from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from mediaflow.domain.recognition import RecognitionStatus, RecognitionType
from mediaflow.domain.recognition_review import (
    RecognitionBatchResolveRequest,
    RecognitionReview,
    RecognitionReviewChoice,
    RecognitionReviewDecisionAudit,
    RecognitionReviewRepository,
    RecognitionReviewStatus,
)
from mediaflow.domain.task_persistence import PersistentTaskItem, TaskItemStatus


class RecognitionReviewService:
    MAX_TEXT = 500
    MAX_CHOICES = 100
    MAX_BATCH_SIZE = 100

    def __init__(
        self,
        repository: RecognitionReviewRepository,
        recognition_types: tuple[RecognitionType, ...],
    ) -> None:
        self._repository = repository
        self._types = {item.type_id: item for item in recognition_types if item.enabled}

    def create(self, item: PersistentTaskItem, recognition) -> RecognitionReview:
        if recognition.status is not RecognitionStatus.UNRECOGNIZED:
            raise ValueError("recognition review requires Unrecognized outcome")
        choices = tuple(self._types.values())
        if not choices:
            raise ValueError("recognition review requires enabled configured RecognitionTypes")
        if len(choices) > self.MAX_CHOICES:
            raise ValueError("recognition review choice limit exceeded")
        now = datetime.now(UTC)
        review_id = str(uuid5(NAMESPACE_URL, f"recognition-review:{item.item_id}"))
        review = RecognitionReview(
            review_id,
            item.task_id,
            item.item_id,
            item.storage_id,
            item.source_path,
            RecognitionReviewStatus.PENDING,
            now,
            now,
        )
        snapshots = tuple(
            RecognitionReviewChoice(
                review_id, value.type_id[:100], value.name[:200], value.description[: self.MAX_TEXT]
            )
            for value in choices
        )
        waiting = replace(
            item,
            status=TaskItemStatus.WAITING_RECOGNITION,
            stage="waiting_recognition",
            updated_at=now,
            error=None,
        )
        self._repository.create_recognition_review(review, snapshots, waiting)
        return review

    def resolve(
        self,
        review_id: str,
        recognition_type_id: str,
        *,
        actor: str | None = None,
        note: str | None = None,
    ) -> RecognitionReview:
        review = self._repository.get_recognition_review(review_id)
        if review is None:
            raise LookupError(f"recognition review {review_id!r} was not found")
        if review.status is not RecognitionReviewStatus.PENDING:
            raise ValueError("recognition review is already resolved")
        choice_ids = {
            item.recognition_type_id
            for item in self._repository.list_recognition_review_choices(review_id)
        }
        if recognition_type_id not in choice_ids:
            raise ValueError("RecognitionType is not present in the review snapshot")
        if recognition_type_id not in self._types:
            raise ValueError("RecognitionType is no longer enabled or configured")
        item = self._repository.get_item(review.item_id)
        if item is None or item.status is not TaskItemStatus.WAITING_RECOGNITION:
            raise ValueError("recognition review TaskItem is not waiting for recognition")
        now = datetime.now(UTC)
        actor_value = self._text(actor, 200)
        resolved = replace(
            review,
            status=RecognitionReviewStatus.RESOLVED,
            updated_at=now,
            selected_recognition_type=recognition_type_id,
            decided_at=now,
            actor=actor_value,
        )
        audit = RecognitionReviewDecisionAudit(
            str(uuid4()),
            review_id,
            recognition_type_id,
            now,
            actor_value,
            self._text(note, self.MAX_TEXT),
        )
        pending = replace(
            item,
            status=TaskItemStatus.PENDING,
            stage="recognition_resolved",
            updated_at=now,
            error=None,
        )
        self._repository.resolve_recognition_review(resolved, audit, pending)
        return resolved

    def resolve_pending(
        self,
        recognition_type_id: str,
        *,
        actor: str,
        note: str | None = None,
        limit: int = 100,
        task_id: str | None = None,
    ) -> tuple[RecognitionReview, ...]:
        if recognition_type_id not in self._types:
            raise ValueError("RecognitionType is not enabled or configured")
        normalized_actor = self._text(actor, 200)
        if not normalized_actor:
            raise ValueError("recognition review actor is required")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= self.MAX_BATCH_SIZE
        ):
            raise ValueError(
                f"recognition resolve batch limit must be between 1 and {self.MAX_BATCH_SIZE}"
            )
        reviews = self._repository.list_pending_recognition_reviews(limit=limit, task_id=task_id)
        if not reviews:
            raise ValueError("no pending recognition reviews were selected")

        now = datetime.now(UTC)
        normalized_note = self._text(note, self.MAX_TEXT)
        requests: list[RecognitionBatchResolveRequest] = []
        for review in reviews:
            choice_ids = {
                item.recognition_type_id
                for item in self._repository.list_recognition_review_choices(review.review_id)
            }
            if recognition_type_id not in choice_ids:
                raise ValueError("RecognitionType is not present in a review snapshot")
            item = self._repository.get_item(review.item_id)
            if (
                item is None
                or item.task_id != review.task_id
                or item.status is not TaskItemStatus.WAITING_RECOGNITION
            ):
                raise ValueError("recognition review TaskItem is not waiting")
            resolved = replace(
                review,
                status=RecognitionReviewStatus.RESOLVED,
                updated_at=now,
                selected_recognition_type=recognition_type_id,
                decided_at=now,
                actor=normalized_actor,
            )
            audit = RecognitionReviewDecisionAudit(
                str(uuid4()),
                review.review_id,
                recognition_type_id,
                now,
                normalized_actor,
                normalized_note,
            )
            pending = replace(
                item,
                status=TaskItemStatus.PENDING,
                stage="recognition_resolved",
                updated_at=now,
                error=None,
            )
            requests.append(RecognitionBatchResolveRequest(resolved, audit, pending))

        self._repository.resolve_recognition_reviews_batch(tuple(requests))
        return tuple(request.review for request in requests)

    @staticmethod
    def _text(value: str | None, limit: int) -> str | None:
        normalized = " ".join(value.split())[:limit] if value is not None else ""
        return normalized or None
