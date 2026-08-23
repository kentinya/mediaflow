from __future__ import annotations

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.domain.metadata_correction import MetadataCorrectionReview


class FileMetadataCorrectionService:
    def __init__(
        self,
        file_catalog: FileCatalogService,
        metadata_correction: MetadataCorrectionService,
    ) -> None:
        self._file_catalog = file_catalog
        self._metadata_correction = metadata_correction

    def resolve(
        self,
        file_id: str,
        *,
        query: str | None,
        year: int | None = None,
        media_type: str,
        provider_id: str | None = None,
        actor: str,
        note: str | None = None,
    ) -> MetadataCorrectionReview:
        detail = self._file_catalog.detail(file_id)
        review = next(
            (
                item
                for item in detail.related_reviews
                if item.kind == "metadata_correction" and item.status == "pending"
            ),
            None,
        )
        if review is None:
            raise ValueError("file has no pending MetadataCorrectionReview")
        return self._metadata_correction.resolve(
            review.review_id,
            query=query,
            year=year,
            media_type=media_type,
            provider_id=provider_id,
            actor=actor,
            note=note,
        )
