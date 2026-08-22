from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from mediaflow.domain.classification import (
    ClassificationPolicy,
    ClassificationResult,
    ClassificationStatus,
)
from mediaflow.domain.classification_review import (
    ClassificationReview,
    ClassificationReviewChoice,
    ClassificationReviewDecisionAudit,
    ClassificationReviewRepository,
    ClassificationReviewStatus,
)
from mediaflow.domain.metadata import MediaIdentity
from mediaflow.domain.task_persistence import PersistentTaskItem, TaskItemStatus


class ClassificationReviewService:
    MAX_CHOICES = 100
    MAX_TEXT = 500

    def __init__(self, repository: ClassificationReviewRepository) -> None:
        self._repository = repository

    def create(
        self,
        item: PersistentTaskItem,
        result: ClassificationResult,
        policy: ClassificationPolicy,
        identity: MediaIdentity,
    ) -> ClassificationReview:
        if result.status is not ClassificationStatus.UNCLASSIFIED:
            raise ValueError("classification review requires an unclassified outcome")
        if result.policy_id != policy.policy_id:
            raise ValueError("classification result policy does not match review policy")
        rules = tuple(
            sorted(
                (rule for rule in policy.rules if rule.enabled),
                key=lambda rule: (-rule.priority, rule.rule_id),
            )[: self.MAX_CHOICES]
        )
        if not rules:
            raise ValueError("classification review requires configured enabled rule choices")
        now = datetime.now(UTC)
        review_id = str(uuid5(NAMESPACE_URL, f"classification-review:{item.item_id}"))
        review = ClassificationReview(
            review_id,
            item.task_id,
            item.item_id,
            item.storage_id,
            item.source_path,
            result.recognition_type_id,
            policy.policy_id,
            identity.provider[:100],
            identity.provider_id[:200],
            identity.media_type.value,
            identity.title[: self.MAX_TEXT],
            identity.canonical_year,
            ClassificationReviewStatus.PENDING,
            now,
            now,
        )
        choices = tuple(
            ClassificationReviewChoice(
                review_id,
                rank,
                rule.rule_id[:200],
                rule.name[: self.MAX_TEXT],
                rule.media_library_id[:200],
                rule.relative_category_path or "",
                rule.priority,
                rule.description[: self.MAX_TEXT],
            )
            for rank, rule in enumerate(rules, 1)
        )
        waiting = replace(
            item,
            status=TaskItemStatus.WAITING_CLASSIFICATION,
            stage="waiting_classification",
            updated_at=now,
            error=None,
        )
        self._repository.create_classification_review(review, choices, waiting)
        return review

    def resolve(
        self,
        review_id: str,
        choice_rank: int,
        *,
        actor: str | None = None,
        note: str | None = None,
    ) -> ClassificationReview:
        if isinstance(choice_rank, bool) or not isinstance(choice_rank, int):
            raise ValueError("classification review choice rank must be an integer")
        review = self._repository.get_classification_review(review_id)
        if review is None:
            raise LookupError(f"classification review {review_id!r} was not found")
        if review.status is not ClassificationReviewStatus.PENDING:
            raise ValueError("classification review is already resolved")
        choice = next(
            (
                value
                for value in self._repository.list_classification_review_choices(review_id)
                if value.rank == choice_rank
            ),
            None,
        )
        if choice is None:
            raise ValueError("selected choice rank is not present in the classification review")
        item = self._repository.get_item(review.item_id)
        if item is None or item.status is not TaskItemStatus.WAITING_CLASSIFICATION:
            raise ValueError("classification review TaskItem is not waiting for classification")
        now = datetime.now(UTC)
        resolved = replace(
            review,
            status=ClassificationReviewStatus.RESOLVED,
            updated_at=now,
            selected_rank=choice.rank,
            selected_rule_id=choice.rule_id,
            selected_media_library_id=choice.media_library_id,
            selected_relative_path=choice.relative_path,
            decided_at=now,
            actor=self._text(actor, 200),
        )
        audit = ClassificationReviewDecisionAudit(
            str(uuid4()),
            review.review_id,
            choice.rank,
            choice.rule_id,
            choice.media_library_id,
            choice.relative_path,
            now,
            self._text(actor, 200),
            self._text(note, self.MAX_TEXT),
        )
        pending = replace(
            item,
            status=TaskItemStatus.PENDING,
            stage="classification_resolved",
            updated_at=now,
            error=None,
        )
        self._repository.resolve_classification_review(resolved, audit, pending)
        return resolved

    @staticmethod
    def _text(value: str | None, limit: int) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())[:limit]
        return normalized or None
