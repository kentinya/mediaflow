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

    The oldest linked source item comes first, followed by every one-item
    analysis in its lineage, oldest to newest. The newest resolved decision
    therefore wins when consumers iterate this tuple.
    """

    reader = getattr(repository, "list_recovery_continuations", None)
    parent_reader = getattr(repository, "list_recovery_continuations_for_task", None)

    source_item = repository.get_item(source_item_id)
    source_task = repository.get_task(source_item.task_id) if source_item is not None else None
    if source_item is None or source_task is None:
        return (source_item_id,)

    # When the Worker is continuing a linked analysis item, include the
    # reviewed decisions from its exact parent continuation chain. Otherwise a
    # later analysis can forget an ancestor's explicit RecognitionType or
    # Metadata correction and create the same blocker again.
    lineage = [source_item_id]
    seen_lineage = {source_item_id}
    if callable(parent_reader):
        for _ in range(16):
            current_item = repository.get_item(lineage[-1])
            current_task = (
                repository.get_task(current_item.task_id) if current_item is not None else None
            )
            if current_item is None or current_task is None:
                break
            parents = tuple(parent_reader(current_task.task_id, limit=2))
            if len(parents) != 1:
                break
            parent = parents[0]
            if (
                parent.new_task_id != current_task.task_id
                or parent.configuration_snapshot_id != current_task.configuration_snapshot_id
                or parent.configuration_snapshot_digest
                != current_task.configuration_snapshot_digest
            ):
                break
            parent_item = repository.get_item(parent.source_item_id)
            parent_task = (
                repository.get_task(parent_item.task_id) if parent_item is not None else None
            )
            if (
                parent_item is None
                or parent_task is None
                or parent.source_task_id != parent_task.task_id
                or parent_item.item_id in seen_lineage
                or parent_item.storage_id != source_item.storage_id
                or parent_item.source_path != source_item.source_path
                or parent_task.configuration_snapshot_id != source_task.configuration_snapshot_id
                or parent_task.configuration_snapshot_digest
                != source_task.configuration_snapshot_digest
            ):
                break
            seen_lineage.add(parent_item.item_id)
            lineage.append(parent_item.item_id)
    lineage.reverse()
    item_ids = lineage[:limit]
    if not callable(reader) or len(item_ids) >= limit:
        return tuple(item_ids)

    seen_items = set(item_ids)
    seen_tasks = {
        item.task_id
        for linked_id in lineage
        if (item := repository.get_item(linked_id)) is not None
    }

    def visit(item_id: str, depth: int) -> None:
        if depth >= 16 or len(item_ids) >= limit:
            return
        current_item = repository.get_item(item_id)
        current_task = (
            repository.get_task(current_item.task_id) if current_item is not None else None
        )
        if current_item is None or current_task is None:
            return
        continuations = tuple(reader(item_id, limit=limit))
        # Repository reads are newest-first; visit oldest first so the newest
        # linked decision wins when the caller folds these IDs in order.
        for continuation in reversed(continuations):
            if len(item_ids) >= limit:
                return
            new_task_id = getattr(continuation, "new_task_id", None)
            if (
                getattr(continuation, "source_item_id", None) != item_id
                or getattr(continuation, "source_task_id", None) != current_task.task_id
                or getattr(continuation, "configuration_snapshot_id", None)
                != source_task.configuration_snapshot_id
                or getattr(continuation, "configuration_snapshot_digest", None)
                != source_task.configuration_snapshot_digest
                or not isinstance(new_task_id, str)
                or not new_task_id
                or new_task_id in seen_tasks
            ):
                continue
            seen_tasks.add(new_task_id)
            task = repository.get_task(new_task_id)
            if (
                task is None
                or task.configuration_snapshot_id != source_task.configuration_snapshot_id
                or task.configuration_snapshot_digest != source_task.configuration_snapshot_digest
            ):
                continue
            linked_items = tuple(repository.list_items(new_task_id))
            if len(linked_items) != 1:
                continue
            linked_item = linked_items[0]
            if (
                linked_item.storage_id != source_item.storage_id
                or linked_item.source_path != source_item.source_path
                or linked_item.item_id in seen_items
            ):
                continue
            seen_items.add(linked_item.item_id)
            item_ids.append(linked_item.item_id)
            visit(linked_item.item_id, depth + 1)

    visit(source_item_id, 0)
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
