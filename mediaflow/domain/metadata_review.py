from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.task_persistence import PersistentTaskItem


class MetadataReviewStatus(StrEnum):
    PENDING = "pending"


@dataclass(frozen=True)
class MetadataReviewScoreComponent:
    name: str
    score: float
    reason: str


@dataclass(frozen=True)
class MetadataReviewCandidate:
    review_id: str
    rank: int
    provider: str
    provider_id: str
    media_type: str
    title: str
    original_title: str | None
    canonical_year: int | None
    regional_year: int | None
    total_score: float
    matched_provider_title: str | None
    matched_title_source: str | None
    score_components: tuple[MetadataReviewScoreComponent, ...] = ()


@dataclass(frozen=True)
class MetadataReview:
    review_id: str
    task_id: str
    item_id: str
    source_storage_id: str
    source_path: str
    recognition_type: str
    metadata_policy_id: str
    query: str
    outcome: str
    status: MetadataReviewStatus
    created_at: datetime
    updated_at: datetime


class MetadataReviewRepository(Protocol):
    def create_metadata_review(
        self,
        review: MetadataReview,
        candidates: tuple[MetadataReviewCandidate, ...],
        item: PersistentTaskItem,
    ) -> None: ...

    def get_metadata_review(self, review_id: str) -> MetadataReview | None: ...
    def list_metadata_reviews(self, *, limit: int = 100) -> tuple[MetadataReview, ...]: ...
    def list_metadata_review_candidates(
        self, review_id: str
    ) -> tuple[MetadataReviewCandidate, ...]: ...
