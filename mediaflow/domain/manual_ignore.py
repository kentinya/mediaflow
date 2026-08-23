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


class ManualIgnoreRepository(Protocol):
    def get_item(self, item_id: str) -> PersistentTaskItem | None: ...
    def get_recognition_review_for_item(self, item_id: str): ...
    def get_metadata_review_for_item(self, item_id: str): ...
    def get_metadata_correction_for_item(self, item_id: str): ...
    def ignore_waiting_item(
        self, decision: ManualIgnoreDecision, item: PersistentTaskItem
    ) -> None: ...
    def list_manual_ignore_audit(self, item_id: str) -> tuple[ManualIgnoreDecision, ...]: ...
