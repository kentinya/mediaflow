from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.task_persistence import PersistentTaskItem


class ManualReviewKind(StrEnum):
    RECOGNITION = "recognition"
    METADATA = "metadata"
    METADATA_CORRECTION = "metadata_correction"


@dataclass(frozen=True)
class ManualIgnoreDecision:
    decision_id: str
    task_id: str
    item_id: str
    review_kind: ManualReviewKind
    review_id: str
    decided_at: datetime
    actor: str
    note: str | None = None


@dataclass(frozen=True)
class ManualIgnoreCandidate:
    item: PersistentTaskItem
    review_kind: ManualReviewKind
    review_id: str


@dataclass(frozen=True)
class ManualIgnoreBatchRequest:
    decision: ManualIgnoreDecision
    item: PersistentTaskItem


class ManualIgnoreRepository(Protocol):
    def get_item(self, item_id: str) -> PersistentTaskItem | None: ...
    def get_recognition_review_for_item(self, item_id: str): ...
    def get_metadata_review_for_item(self, item_id: str): ...
    def get_metadata_correction_for_item(self, item_id: str): ...
    def list_ignorable_waiting_items(
        self, *, limit: int = 100, task_id: str | None = None
    ) -> tuple[ManualIgnoreCandidate, ...]: ...
    def ignore_waiting_item(
        self, decision: ManualIgnoreDecision, item: PersistentTaskItem
    ) -> None: ...
    def ignore_waiting_items(self, requests: tuple[ManualIgnoreBatchRequest, ...]) -> None: ...
    def list_manual_ignore_audit(self, item_id: str) -> tuple[ManualIgnoreDecision, ...]: ...
