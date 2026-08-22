from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.task_persistence import PersistentTaskItem


class ClassificationReviewStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class ClassificationReviewChoice:
    review_id: str
    rank: int
    rule_id: str
    rule_name: str
    media_library_id: str
    relative_path: str
    priority: int
    description: str = ""


@dataclass(frozen=True)
class ClassificationReview:
    review_id: str
    task_id: str
    item_id: str
    source_storage_id: str
    source_path: str
    recognition_type: str
    classification_policy_id: str
    provider: str
    provider_id: str
    media_type: str
    title: str
    canonical_year: int | None
    status: ClassificationReviewStatus
    created_at: datetime
    updated_at: datetime
    selected_rank: int | None = None
    selected_rule_id: str | None = None
    selected_media_library_id: str | None = None
    selected_relative_path: str | None = None
    decided_at: datetime | None = None
    actor: str | None = None


@dataclass(frozen=True)
class ClassificationReviewDecisionAudit:
    audit_id: str
    review_id: str
    selected_rank: int
    rule_id: str
    media_library_id: str
    relative_path: str
    decided_at: datetime
    actor: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class ClassificationSelection:
    recognition_type: str
    classification_policy_id: str
    rule_id: str
    media_library_id: str
    relative_path: str


class ClassificationReviewRepository(Protocol):
    def create_classification_review(
        self,
        review: ClassificationReview,
        choices: tuple[ClassificationReviewChoice, ...],
        item: PersistentTaskItem,
    ) -> None: ...
    def get_classification_review(self, review_id: str) -> ClassificationReview | None: ...
    def get_classification_review_for_item(self, item_id: str) -> ClassificationReview | None: ...
    def list_classification_reviews(
        self, *, limit: int = 100
    ) -> tuple[ClassificationReview, ...]: ...
    def list_classification_review_choices(
        self, review_id: str
    ) -> tuple[ClassificationReviewChoice, ...]: ...
    def resolve_classification_review(
        self,
        review: ClassificationReview,
        audit: ClassificationReviewDecisionAudit,
        item: PersistentTaskItem,
    ) -> None: ...
    def list_classification_review_audit(
        self, review_id: str
    ) -> tuple[ClassificationReviewDecisionAudit, ...]: ...
