from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class NotificationEventType(StrEnum):
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"
    SCHEDULE_EMITTED = "schedule.emitted"


class NotificationDeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERING = "delivering"
    RETRY = "retry"
    DELIVERED = "delivered"
    DEAD_LETTER = "dead-letter"


@dataclass(frozen=True)
class WebhookDefinition:
    webhook_id: str
    url: str
    secret_env: str
    events: tuple[NotificationEventType, ...]
    enabled: bool = True
    timeout_seconds: float = 10.0
    max_attempts: int = 5
    base_retry_seconds: float = 5.0
    max_retry_seconds: float = 300.0


@dataclass(frozen=True)
class NotificationEvent:
    event_id: str
    event_type: NotificationEventType
    occurred_at: datetime
    data: dict[str, object]


@dataclass(frozen=True)
class NotificationDelivery:
    delivery_id: str
    webhook_id: str
    event_id: str
    event_type: NotificationEventType
    body: str
    status: NotificationDeliveryStatus
    attempts: int
    next_attempt_at: datetime
    created_at: datetime
    updated_at: datetime
    delivered_at: datetime | None = None
    failure_category: str | None = None
    response_status: int | None = None


class NotificationRepository(Protocol):
    def create_delivery(self, delivery: NotificationDelivery) -> bool: ...
    def get_delivery(self, delivery_id: str) -> NotificationDelivery | None: ...
    def list_deliveries(
        self,
        *,
        status: NotificationDeliveryStatus | None = None,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[NotificationDelivery, ...]: ...
    def claim_next_delivery(
        self, now: datetime, stale_before: datetime
    ) -> NotificationDelivery | None: ...
    def list_stale_deliveries(
        self, stale_before: datetime, *, limit: int | None = None
    ) -> tuple[NotificationDelivery, ...]: ...
    def update_delivery(self, delivery: NotificationDelivery) -> None: ...
    def requeue_dead_letter(self, delivery_id: str, now: datetime) -> NotificationDelivery: ...


@dataclass(frozen=True)
class WebhookRequest:
    url: str
    body: bytes
    headers: dict[str, str]
    timeout_seconds: float


class WebhookTransport(Protocol):
    def send(self, request: WebhookRequest) -> int: ...
