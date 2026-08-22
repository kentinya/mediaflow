from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from mediaflow.domain.metadata import (
    MetadataIdentificationResult,
    MetadataIdentificationStatus,
)
from mediaflow.domain.metadata_review import (
    MetadataReview,
    MetadataReviewCandidate,
    MetadataReviewRepository,
    MetadataReviewScoreComponent,
    MetadataReviewStatus,
)
from mediaflow.domain.task_persistence import PersistentTaskItem, TaskItemStatus


class MetadataReviewService:
    """Snapshots an existing matcher outcome; it never calls a provider or selects a result."""

    MAX_CANDIDATES = 20
    MAX_COMPONENTS = 16
    MAX_TEXT = 500

    def __init__(self, repository: MetadataReviewRepository) -> None:
        self._repository = repository

    def create(
        self,
        item: PersistentTaskItem,
        identification: MetadataIdentificationResult,
        metadata_policy_id: str,
    ) -> MetadataReview:
        if identification.status not in {
            MetadataIdentificationStatus.NEED_CONFIRM,
            MetadataIdentificationStatus.AMBIGUOUS,
        }:
            raise ValueError("metadata review requires NeedConfirm or Ambiguous outcome")
        if identification.match is None or not identification.match.candidate_scores:
            raise ValueError("metadata review requires scored candidates")
        now = datetime.now(UTC)
        review_id = str(uuid5(NAMESPACE_URL, f"metadata-review:{item.item_id}"))
        review = MetadataReview(
            review_id,
            item.task_id,
            item.item_id,
            item.storage_id,
            item.source_path,
            identification.recognition_type.type_id,
            metadata_policy_id,
            identification.query[: self.MAX_TEXT],
            identification.status.value,
            MetadataReviewStatus.PENDING,
            now,
            now,
        )
        candidates = tuple(
            self._candidate(review_id, rank, score)
            for rank, score in enumerate(
                identification.match.candidate_scores[: self.MAX_CANDIDATES], 1
            )
        )
        waiting = replace(
            item,
            status=TaskItemStatus.WAITING_METADATA,
            stage="waiting_metadata",
            updated_at=now,
            error=None,
        )
        self._repository.create_metadata_review(review, candidates, waiting)
        return review

    def _candidate(self, review_id, rank, score) -> MetadataReviewCandidate:
        candidate = score.candidate
        return MetadataReviewCandidate(
            review_id,
            rank,
            candidate.provider[:100],
            candidate.provider_id[:200],
            candidate.media_type.value,
            candidate.title[: self.MAX_TEXT],
            candidate.original_title[: self.MAX_TEXT] if candidate.original_title else None,
            candidate.canonical_year,
            candidate.regional_year,
            score.total_score,
            (
                score.matched_provider_title[: self.MAX_TEXT]
                if score.matched_provider_title
                else None
            ),
            score.matched_title_source[:100] if score.matched_title_source else None,
            tuple(
                MetadataReviewScoreComponent(
                    component.name[:100],
                    component.score,
                    component.reason[: self.MAX_TEXT],
                )
                for component in score.components[: self.MAX_COMPONENTS]
            ),
        )
