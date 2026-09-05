"""Shared resolved-decision collection for single-item recovery continuation.

The Worker re-analysis and the continued-manual continuation Preview must consume
the same saved Conflict / Metadata / Metadata-Correction / Classification /
Recognition decisions for the same current source occurrence.  A decision the
operator resolves on a linked single-item re-analysis TaskItem lives on that
TaskItem, not on the original manual item, so both analysis surfaces must look in
the same place.  Centralising that collection here keeps the two surfaces from
diverging after a saved decision is resolved.

Every record is keyed by ``(storage_id, source_path)`` and only RESOLVED records
with complete selection fields are collected.  The newest decision wins: the
original manual item is inspected first, then the analysis items of each prior
single-item re-analysis in oldest-to-newest order.
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
    """Return the items whose reviews/decisions belong to one continuation source.

    The durable original manual item comes first, followed by the analysis items
    of every prior single-item re-analysis of that item (oldest to newest).  The
    newest resolved decision therefore wins when consumers iterate this tuple.
    """

    item_ids = [source_item_id]
    reader = getattr(repository, "list_recovery_continuations", None)
    if callable(reader):
        continuations = tuple(reader(source_item_id, limit=limit))
        for continuation in reversed(continuations):
            new_task_id = getattr(continuation, "new_task_id", None)
            if not new_task_id:
                continue
            item_ids.extend(value.item_id for value in repository.list_items(new_task_id))
    return tuple(item_ids)


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

    return ResolvedContinuationDecisions(
        confirmations=confirmations,
        metadata_reviews=metadata_reviews,
        metadata_corrections=metadata_corrections,
        classification_reviews=classification_reviews,
        recognition_reviews=recognition_reviews,
    )
