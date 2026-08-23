from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.task_persistence import PersistentTaskItem


class RecognitionReviewStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    IGNORED = "ignored"
    RETRY_REQUESTED = "retry_requested"


@dataclass(frozen=True)
class RecognitionReviewChoice:
    review_id: str
    recognition_type_id: str
    name: str
    description: str = ""


@dataclass(frozen=True)
class RecognitionReview:
    review_id: str
    task_id: str
    item_id: str
    source_storage_id: str
    source_path: str
    status: RecognitionReviewStatus
    created_at: datetime
    updated_at: datetime
    selected_recognition_type: str | None = None
    decided_at: datetime | None = None
    actor: str | None = None


@dataclass(frozen=True)
class RecognitionReviewDecisionAudit:
    audit_id: str
    review_id: str
    recognition_type_id: str
    decided_at: datetime
    actor: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class RecognitionRetryDecision:
    decision_id: str
    review_id: str
    task_id: str
    item_id: str
    decided_at: datetime
    actor: str
    note: str | None = None


@dataclass(frozen=True)
class RecognitionSelection:
    recognition_type_id: str


class RecognitionReviewRepository(Protocol):
    def create_recognition_review(
        self,
        review: RecognitionReview,
        choices: tuple[RecognitionReviewChoice, ...],
        item: PersistentTaskItem,
    ) -> None: ...

    def get_recognition_review(self, review_id: str) -> RecognitionReview | None: ...
    def get_recognition_review_for_item(self, item_id: str) -> RecognitionReview | None: ...
    def list_recognition_reviews(self, *, limit: int = 100) -> tuple[RecognitionReview, ...]: ...
    def list_recognition_review_choices(
        self, review_id: str
    ) -> tuple[RecognitionReviewChoice, ...]: ...
    def resolve_recognition_review(
        self,
        review: RecognitionReview,
        audit: RecognitionReviewDecisionAudit,
        item: PersistentTaskItem,
    ) -> None: ...
    def list_recognition_review_audit(
        self, review_id: str
    ) -> tuple[RecognitionReviewDecisionAudit, ...]: ...
    def request_recognition_retry(
        self,
        review: RecognitionReview,
        decision: RecognitionRetryDecision,
        item: PersistentTaskItem,
    ) -> None: ...
    def list_recognition_retry_audit(
        self, review_id: str
    ) -> tuple[RecognitionRetryDecision, ...]: ...
