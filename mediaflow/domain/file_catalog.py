from __future__ import annotations

from dataclasses import dataclass

from mediaflow.domain.file_index import FileIndexRecord
from mediaflow.domain.task_persistence import PersistentResultRecord


@dataclass(frozen=True)
class FileCatalogEnrichedRecord:
    file: FileIndexRecord
    result: PersistentResultRecord | None


@dataclass(frozen=True)
class FileReviewLink:
    kind: str
    review_id: str
    status: str
    task_id: str
    item_id: str | None = None
