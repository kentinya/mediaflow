from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.manual_ignore import (
    ManualIgnoreDecision,
    ManualIgnoreRepository,
    ManualReviewKind,
)
from mediaflow.domain.metadata_correction import MetadataCorrectionStatus
from mediaflow.domain.metadata_review import MetadataReviewStatus
from mediaflow.domain.recognition_review import RecognitionReviewStatus
from mediaflow.domain.task_persistence import PersistentTaskItem, TaskItemStatus


class ManualIgnoreService:
    MAX_ACTOR = 200
    MAX_NOTE = 500

    def __init__(self, repository: ManualIgnoreRepository) -> None:
        self._repository = repository

    def ignore(
        self,
        task_id: str,
        item_id: str,
        *,
        actor: str,
        note: str | None = None,
    ) -> ManualIgnoreDecision:
        normalized_actor = self._text(actor, self.MAX_ACTOR)
        if not normalized_actor:
            raise ValueError("ignore actor is required")
        item = self._repository.get_item(item_id)
        if item is None or item.task_id != task_id:
            raise LookupError("TaskItem was not found in the specified Task")
        review_kind, review = self._pending_review(item)
        now = datetime.now(UTC)
        decision = ManualIgnoreDecision(
            str(uuid4()),
            task_id,
            item_id,
            review_kind,
            review.review_id,
            now,
            normalized_actor,
            self._text(note, self.MAX_NOTE),
        )
        ignored = replace(
            item,
            status=TaskItemStatus.IGNORED,
            stage="ignored_by_operator",
            updated_at=now,
            error=None,
        )
        self._repository.ignore_waiting_item(decision, ignored)
        return decision

    def _pending_review(self, item: PersistentTaskItem):
        mappings = {
            TaskItemStatus.WAITING_RECOGNITION: (
                ManualReviewKind.RECOGNITION,
                self._repository.get_recognition_review_for_item,
                RecognitionReviewStatus.PENDING,
            ),
            TaskItemStatus.WAITING_METADATA: (
                ManualReviewKind.METADATA,
                self._repository.get_metadata_review_for_item,
                MetadataReviewStatus.PENDING,
            ),
            TaskItemStatus.WAITING_METADATA_CORRECTION: (
                ManualReviewKind.METADATA_CORRECTION,
                self._repository.get_metadata_correction_for_item,
                MetadataCorrectionStatus.PENDING,
            ),
        }
        selected = mappings.get(item.status)
        if selected is None:
            raise ValueError("TaskItem is not in a supported manual-review waiting state")
        kind, getter, pending = selected
        review = getter(item.item_id)
        if review is None or review.status is not pending:
            raise ValueError("TaskItem has no matching pending manual review")
        return kind, review

    @staticmethod
    def _text(value: str | None, limit: int) -> str | None:
        normalized = " ".join(value.split())[:limit] if value is not None else ""
        return normalized or None
