from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True)
class OperationHistoryRecord:
    record_id: str
    timestamp: datetime
    source: str
    destination: str
    operation: str
    status: str
    provider_id: str | None = None
    title: str | None = None
    error: str | None = None

    @classmethod
    def now(
        cls,
        record_id: str,
        source: str,
        destination: str,
        operation: str,
        status: str,
        *,
        provider_id: str | None = None,
        title: str | None = None,
        error: str | None = None,
    ) -> OperationHistoryRecord:
        return cls(
            record_id,
            datetime.now(UTC),
            source,
            destination,
            operation,
            status,
            provider_id,
            title,
            error,
        )


class OperationHistoryRepository(Protocol):
    def append(self, record: OperationHistoryRecord) -> None: ...

    def list(self, *, limit: int | None = None) -> tuple[OperationHistoryRecord, ...]: ...
