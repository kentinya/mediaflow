from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from mediaflow.domain.metadata import (
    MediaQueryType,
    MediaType,
    MetadataIdentificationResult,
    MetadataIdentificationStatus,
    MetadataPolicy,
)
from mediaflow.domain.metadata_correction import (
    MetadataCorrectionBatchResolveRequest,
    MetadataCorrectionDecisionAudit,
    MetadataCorrectionRepository,
    MetadataCorrectionReview,
    MetadataCorrectionStatus,
)
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.task_persistence import PersistentTaskItem, TaskItemStatus

_PROVIDER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}")


class MetadataCorrectionService:
    MAX_QUERY = 500
    MAX_TEXT = 500
    MAX_BATCH_SIZE = 100

    def __init__(
        self,
        repository: MetadataCorrectionRepository,
        policies: tuple[MetadataPolicy, ...],
    ) -> None:
        self._repository = repository
        self._policies = {item.policy_id: item for item in policies if item.enabled}

    def create(
        self,
        item: PersistentTaskItem,
        identification: MetadataIdentificationResult,
        policy: MetadataPolicy,
        parsed: ParseResult,
    ) -> MetadataCorrectionReview:
        if identification.status is not MetadataIdentificationStatus.NOT_FOUND:
            raise ValueError("metadata correction requires NotFound outcome")
        now = datetime.now(UTC)
        media_type = {
            MediaQueryType.MOVIE: MediaType.MOVIE,
            MediaQueryType.TV: MediaType.TV,
        }.get(policy.query_type, MediaType.TV if parsed.season is not None else MediaType.MOVIE)
        review = MetadataCorrectionReview(
            str(uuid5(NAMESPACE_URL, f"metadata-correction:{item.item_id}")),
            item.task_id,
            item.item_id,
            item.storage_id,
            item.source_path,
            identification.recognition_type_id,
            policy.policy_id,
            policy.provider_id,
            identification.query[: self.MAX_QUERY],
            parsed.year,
            media_type.value,
            identification.status.value,
            MetadataCorrectionStatus.PENDING,
            now,
            now,
        )
        waiting = replace(
            item,
            status=TaskItemStatus.WAITING_METADATA_CORRECTION,
            stage="waiting_metadata_correction",
            updated_at=now,
            error=None,
        )
        self._repository.create_metadata_correction(review, waiting)
        return review

    def resolve(
        self,
        review_id: str,
        *,
        query: str | None,
        year: int | None,
        media_type: str,
        provider_id: str | None = None,
        actor: str | None = None,
        note: str | None = None,
    ) -> MetadataCorrectionReview:
        review = self._repository.get_metadata_correction(review_id)
        if review is None:
            raise LookupError(f"metadata correction {review_id!r} was not found")
        if review.status is not MetadataCorrectionStatus.PENDING:
            raise ValueError("metadata correction is already resolved")
        policy = self._policies.get(review.metadata_policy_id)
        if policy is None or policy.provider_id != review.provider_id:
            raise ValueError("MetadataPolicy or provider is no longer enabled or configured")
        normalized_query = self._text(query, self.MAX_QUERY)
        normalized_provider_id = self._text(provider_id, 200)
        if not normalized_query and not normalized_provider_id:
            raise ValueError("corrected query or direct provider ID is required")
        if normalized_provider_id and not _PROVIDER_ID.fullmatch(normalized_provider_id):
            raise ValueError("direct provider ID is invalid")
        if year is not None and (
            isinstance(year, bool) or not isinstance(year, int) or not 1870 <= year <= 2100
        ):
            raise ValueError("corrected year must be between 1870 and 2100")
        try:
            selected_type = MediaType(media_type)
        except ValueError as error:
            raise ValueError("corrected media type must be movie or tv") from error
        if policy.query_type is MediaQueryType.NONE:
            raise ValueError("MetadataPolicy no longer permits lookup")
        item = self._repository.get_item(review.item_id)
        if item is None or item.status is not TaskItemStatus.WAITING_METADATA_CORRECTION:
            raise ValueError("TaskItem is not waiting for metadata correction")
        now = datetime.now(UTC)
        actor_value = self._text(actor, 200)
        resolved = replace(
            review,
            status=MetadataCorrectionStatus.RESOLVED,
            updated_at=now,
            corrected_query=normalized_query,
            corrected_year=year,
            corrected_media_type=selected_type.value,
            direct_provider_id=normalized_provider_id,
            decided_at=now,
            actor=actor_value,
        )
        audit = MetadataCorrectionDecisionAudit(
            str(uuid4()),
            review_id,
            normalized_query,
            year,
            selected_type.value,
            normalized_provider_id,
            now,
            actor_value,
            self._text(note, self.MAX_TEXT),
        )
        pending = replace(
            item,
            status=TaskItemStatus.PENDING,
            stage="metadata_correction_resolved",
            updated_at=now,
            error=None,
        )
        self._repository.resolve_metadata_correction(resolved, audit, pending)
        return resolved

    def resolve_pending(
        self,
        *,
        query: str | None,
        year: int | None = None,
        media_type: str,
        provider_id: str | None = None,
        actor: str,
        note: str | None = None,
        limit: int = 100,
        task_id: str | None = None,
    ) -> tuple[MetadataCorrectionReview, ...]:
        normalized_query = self._text(query, self.MAX_QUERY)
        normalized_provider_id = self._text(provider_id, 200)
        if not normalized_query and not normalized_provider_id:
            raise ValueError("corrected query or direct provider ID is required")
        if normalized_provider_id and not _PROVIDER_ID.fullmatch(normalized_provider_id):
            raise ValueError("direct provider ID is invalid")
        if year is not None and (
            isinstance(year, bool) or not isinstance(year, int) or not 1870 <= year <= 2100
        ):
            raise ValueError("corrected year must be between 1870 and 2100")
        try:
            selected_type = MediaType(media_type)
        except ValueError as error:
            raise ValueError("corrected media type must be movie or tv") from error
        normalized_actor = self._text(actor, 200)
        if not normalized_actor:
            raise ValueError("metadata correction actor is required")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= self.MAX_BATCH_SIZE
        ):
            raise ValueError(
                f"metadata correction batch limit must be between 1 and {self.MAX_BATCH_SIZE}"
            )
        reviews = self._repository.list_pending_metadata_corrections(limit=limit, task_id=task_id)
        if not reviews:
            raise ValueError("no pending metadata corrections were selected")

        now = datetime.now(UTC)
        normalized_note = self._text(note, self.MAX_TEXT)
        requests: list[MetadataCorrectionBatchResolveRequest] = []
        for review in reviews:
            policy = self._policies.get(review.metadata_policy_id)
            if policy is None or policy.provider_id != review.provider_id:
                raise ValueError("MetadataPolicy or provider is no longer enabled or configured")
            if policy.query_type is MediaQueryType.NONE:
                raise ValueError("MetadataPolicy no longer permits lookup")
            item = self._repository.get_item(review.item_id)
            if (
                item is None
                or item.task_id != review.task_id
                or item.status is not TaskItemStatus.WAITING_METADATA_CORRECTION
            ):
                raise ValueError("TaskItem is not waiting for metadata correction")
            resolved = replace(
                review,
                status=MetadataCorrectionStatus.RESOLVED,
                updated_at=now,
                corrected_query=normalized_query,
                corrected_year=year,
                corrected_media_type=selected_type.value,
                direct_provider_id=normalized_provider_id,
                decided_at=now,
                actor=normalized_actor,
            )
            audit = MetadataCorrectionDecisionAudit(
                str(uuid4()),
                review.review_id,
                normalized_query,
                year,
                selected_type.value,
                normalized_provider_id,
                now,
                normalized_actor,
                normalized_note,
            )
            pending = replace(
                item,
                status=TaskItemStatus.PENDING,
                stage="metadata_correction_resolved",
                updated_at=now,
                error=None,
            )
            requests.append(MetadataCorrectionBatchResolveRequest(resolved, audit, pending))

        self._repository.resolve_metadata_corrections_batch(tuple(requests))
        return tuple(request.review for request in requests)

    @staticmethod
    def _text(value: str | None, limit: int) -> str | None:
        normalized = " ".join(value.split())[:limit] if value is not None else ""
        return normalized or None
