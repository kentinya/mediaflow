"""Shared resolved-decision collection for single-item recovery continuation.

The Worker re-analysis and the continued-manual continuation Preview must consume
the same saved Conflict / Metadata / Metadata-Correction / Classification /
Recognition decisions for the same current source occurrence.  A decision the
operator resolves on a linked single-item re-analysis TaskItem lives on that
TaskItem, not on the original manual item, so both analysis surfaces must look in
the same place.  Centralising that collection here keeps the two surfaces from
diverging after a saved decision is resolved.

Every record is keyed by ``(storage_id, source_path)`` and only RESOLVED records
with complete selection fields are collected from the exact source item's own
same-Task analysis identity.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from mediaflow.domain.classification_review import (
    ClassificationReview,
    ClassificationReviewStatus,
)
from mediaflow.domain.metadata_correction import (
    MetadataCorrectionReview,
    MetadataCorrectionStatus,
)
from mediaflow.domain.metadata_review import MetadataReview, MetadataReviewStatus
from mediaflow.domain.recognition_review import (
    RecognitionReview,
    RecognitionReviewStatus,
)
from mediaflow.domain.task_persistence import ConfirmationStatus, ConflictConfirmation

MAX_DECISION_ANALYSIS_ITEMS = 32


@dataclass(frozen=True)
class ResolvedContinuationDecisions:
    """Newest resolved review/conflict decisions per source occurrence.

    Values are the raw persisted decision records so each consumer can bind them
    to its own analysis context: the Worker re-analysis binds them to the
    production recognition result while the manual continuation Preview binds
    them to the original manual choice.
    """

    confirmations: Mapping[tuple[str, str], ConflictConfirmation] = field(default_factory=dict)
    metadata_reviews: Mapping[tuple[str, str], MetadataReview] = field(default_factory=dict)
    metadata_corrections: Mapping[tuple[str, str], MetadataCorrectionReview] = field(
        default_factory=dict
    )
    classification_reviews: Mapping[tuple[str, str], ClassificationReview] = field(
        default_factory=dict
    )
    recognition_reviews: Mapping[tuple[str, str], RecognitionReview] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return not (
            self.confirmations
            or self.metadata_reviews
            or self.metadata_corrections
            or self.classification_reviews
            or self.recognition_reviews
        )


def continuation_decision_item_ids(
    repository,
    *,
    source_item_id: str,
    limit: int = MAX_DECISION_ANALYSIS_ITEMS,
) -> tuple[str, ...]:
    """Return the one item whose reviews/decisions belong to this continuation source.

    The current recovery continues the *same* TaskItem: the saved decision and
    its safe re-analysis stay on that identity, so the exact source item is the
    only member.  A missing item is still returned so the caller's own
    persisted-decision reads decide; no other item can substitute for it.
    """

    if not isinstance(source_item_id, str) or not source_item_id:
        return ()
    return (source_item_id,)[:limit]


def keep_newest_metadata_decisions(
    metadata_reviews: dict[tuple[str, str], object],
    metadata_corrections: dict[tuple[str, str], object],
) -> None:
    """Keep only the newest resolved Metadata decision per source.

    A candidate selection can prove season/episodes wrong on re-analysis and
    publish a newer correction for the same item; the opposite order is also
    possible when a later correction search finds ambiguous candidates.  Both
    decisions are legal history, but exactly one may drive the next analysis.
    """

    for key in set(metadata_reviews) & set(metadata_corrections):
        review_time = getattr(metadata_reviews[key], "updated_at", None)
        correction_time = getattr(metadata_corrections[key], "updated_at", None)
        if review_time is None or (correction_time is not None and correction_time >= review_time):
            metadata_reviews.pop(key, None)
        else:
            metadata_corrections.pop(key, None)


def collect_resolved_continuation_decisions(
    repository,
    *,
    source_item_id: str,
    limit: int = MAX_DECISION_ANALYSIS_ITEMS,
) -> ResolvedContinuationDecisions:
    """Collect the newest resolved decisions for one continuation source."""

    item_ids = continuation_decision_item_ids(
        repository, source_item_id=source_item_id, limit=limit
    )
    item_set = set(item_ids)

    confirmations: dict[tuple[str, str], ConflictConfirmation] = {}
    confirmation_reader = getattr(repository, "list_confirmations", None)
    if callable(confirmation_reader):
        try:
            resolved = tuple(confirmation_reader(status=ConfirmationStatus.RESOLVED))
        except TypeError:
            resolved = tuple(confirmation_reader(status=ConfirmationStatus.RESOLVED.value))
        by_item: dict[str, list[ConflictConfirmation]] = {}
        for confirmation in resolved:
            if confirmation.item_id in item_set:
                by_item.setdefault(confirmation.item_id, []).append(confirmation)
        # Oldest item first so the newest decision (last item) wins per source.
        for item_id in item_ids:
            for confirmation in by_item.get(item_id, ()):
                key = (confirmation.source_storage_id, confirmation.source_path)
                confirmations[key] = confirmation

    metadata_reviews: dict[tuple[str, str], MetadataReview] = {}
    for item_id in item_ids:
        review = repository.get_metadata_review_for_item(item_id)
        if review is None or review.status is not MetadataReviewStatus.RESOLVED:
            continue
        if not (
            review.selected_provider and review.selected_provider_id and review.selected_media_type
        ):
            continue
        metadata_reviews[(review.source_storage_id, review.source_path)] = review

    metadata_corrections: dict[tuple[str, str], MetadataCorrectionReview] = {}
    for item_id in item_ids:
        review = repository.get_metadata_correction_for_item(item_id)
        if review is None or review.status is not MetadataCorrectionStatus.RESOLVED:
            continue
        if not review.corrected_media_type:
            continue
        metadata_corrections[(review.source_storage_id, review.source_path)] = review

    classification_reviews: dict[tuple[str, str], ClassificationReview] = {}
    for item_id in item_ids:
        review = repository.get_classification_review_for_item(item_id)
        if review is None or review.status is not ClassificationReviewStatus.RESOLVED:
            continue
        if not (
            review.selected_rule_id
            and review.selected_media_library_id
            and review.selected_relative_path
        ):
            continue
        classification_reviews[(review.source_storage_id, review.source_path)] = review

    recognition_reviews: dict[tuple[str, str], RecognitionReview] = {}
    for item_id in item_ids:
        review = repository.get_recognition_review_for_item(item_id)
        if review is None or review.status is not RecognitionReviewStatus.RESOLVED:
            continue
        if not review.selected_recognition_type:
            continue
        recognition_reviews[(review.source_storage_id, review.source_path)] = review

    keep_newest_metadata_decisions(metadata_reviews, metadata_corrections)
    return ResolvedContinuationDecisions(
        confirmations=confirmations,
        metadata_reviews=metadata_reviews,
        metadata_corrections=metadata_corrections,
        classification_reviews=classification_reviews,
        recognition_reviews=recognition_reviews,
    )
