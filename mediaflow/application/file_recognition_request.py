from __future__ import annotations

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.recognition_retry import RecognitionRetryService
from mediaflow.domain.recognition_review import RecognitionRetryDecision


class FileRecognitionRequestService:
    def __init__(
        self,
        file_catalog: FileCatalogService,
        retry_service: RecognitionRetryService,
    ) -> None:
        self._file_catalog = file_catalog
        self._retry_service = retry_service

    def request(
        self,
        file_id: str,
        *,
        actor: str,
        note: str | None = None,
    ) -> RecognitionRetryDecision:
        detail = self._file_catalog.detail(file_id)
        review = next(
            (
                item
                for item in detail.related_reviews
                if item.kind == "recognition" and item.status == "pending"
            ),
            None,
        )
        if review is None:
            raise ValueError("file has no pending RecognitionReview")
        return self._retry_service.request(review.review_id, actor=actor, note=note)
