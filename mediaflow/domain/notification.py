from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlsplit

WEBHOOK_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Deployment-owned secret references are bounded to the same maximum as the
# runtime configuration loader so a typed Webhook definition can never smuggle
# an arbitrary execution/locator field into the document.
WEBHOOK_TIMEOUT_MIN = 0.1
WEBHOOK_TIMEOUT_MAX = 120.0
WEBHOOK_ATTEMPTS_MAX = 20
WEBHOOK_RETRY_MIN = 0.1
WEBHOOK_RETRY_MAX = 86400.0


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

    def __post_init__(self) -> None:
        if (
            not isinstance(self.webhook_id, str)
            or not self.webhook_id.strip()
            or len(self.webhook_id) > 64
            or any(character in self.webhook_id for character in "/\\\x00")
        ):
            raise ValueError("Webhook id must be a bounded string without slashes or NUL")
        if (
            not isinstance(self.url, str)
            or not self.url.strip()
            or len(self.url) > 2048
            or "\x00" in self.url
        ):
            raise ValueError("Webhook URL must be bounded text")
        parsed = urlsplit(self.url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("Webhook URL must be HTTPS without credentials or fragment")
        if not isinstance(self.secret_env, str) or not WEBHOOK_ENV_NAME.fullmatch(self.secret_env):
            raise ValueError("Webhook secretEnv must be a valid environment variable name")
        if (
            not isinstance(self.events, tuple)
            or not self.events
            or len(self.events) > 64
            or any(not isinstance(event, NotificationEventType) for event in self.events)
            or len(self.events) != len(set(self.events))
        ):
            raise ValueError(
                "Webhook events must be a non-empty unique collection of supported events"
            )
        if not isinstance(self.enabled, bool):
            raise ValueError("Webhook enabled must be boolean")
        timeout = float(self.timeout_seconds)
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not WEBHOOK_TIMEOUT_MIN <= timeout <= WEBHOOK_TIMEOUT_MAX
        ):
            raise ValueError("Webhook timeoutSeconds must be a bounded positive number")
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or not 1 <= self.max_attempts <= WEBHOOK_ATTEMPTS_MAX
        ):
            raise ValueError("Webhook maxAttempts must be a bounded positive integer")
        for name, value in (
            ("baseRetrySeconds", self.base_retry_seconds),
            ("maxRetrySeconds", self.max_retry_seconds),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not WEBHOOK_RETRY_MIN <= float(value) <= WEBHOOK_RETRY_MAX
            ):
                raise ValueError(f"Webhook {name} must be a bounded positive number")
        if float(self.max_retry_seconds) < float(self.base_retry_seconds):
            raise ValueError("Webhook maxRetrySeconds must be at least baseRetrySeconds")

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> WebhookDefinition:
        """Parse and validate one canonical Webhook definition document.

        This is the single validation/normalization path shared by the runtime
        JSON loader and the managed configuration object graph so a typed edit
        can never accept, reject or normalize a Webhook differently from the
        Active snapshot.
        """

        if not isinstance(value, Mapping):
            raise ValueError("Webhook definition must be an object")
        allowed = {
            "id",
            "url",
            "secretEnv",
            "events",
            "enabled",
            "timeoutSeconds",
            "maxAttempts",
            "baseRetrySeconds",
            "maxRetrySeconds",
        }
        if unknown := set(value).difference(allowed):
            raise ValueError(f"Webhook field {sorted(unknown)[0]!r} is unsupported")
        forbidden = {"secret", "token", "authorization", "execute"}.intersection(value)
        if forbidden:
            raise ValueError(f"Webhook field {sorted(forbidden)[0]!r} is forbidden")
        webhook_id = value.get("id")
        url = value.get("url")
        secret_env = value.get("secretEnv")
        raw_events = value.get("events")
        if not isinstance(raw_events, list) or not raw_events:
            raise ValueError("Webhook events must be a non-empty array")
        events = []
        try:
            for item in raw_events:
                events.append(NotificationEventType(item))
        except (TypeError, ValueError) as error:
            raise ValueError("Webhook contains an unsupported event") from error
        if len(events) != len(set(events)):
            raise ValueError("Webhook events must be unique")
        enabled = value.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError("Webhook enabled must be boolean")
        timeout_seconds = value.get("timeoutSeconds", 10.0)
        max_attempts = value.get("maxAttempts", 5)
        base_retry_seconds = value.get("baseRetrySeconds", 5.0)
        max_retry_seconds = value.get("maxRetrySeconds", 300.0)
        for field, item in (
            ("timeoutSeconds", timeout_seconds),
            ("baseRetrySeconds", base_retry_seconds),
            ("maxRetrySeconds", max_retry_seconds),
        ):
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ValueError(f"Webhook {field} must be numeric")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int):
            raise ValueError("Webhook maxAttempts must be an integer")
        return cls(
            webhook_id,  # type: ignore[arg-type]
            url,  # type: ignore[arg-type]
            secret_env,  # type: ignore[arg-type]
            tuple(events),
            enabled=enabled,
            timeout_seconds=timeout_seconds,  # type: ignore[arg-type]
            max_attempts=max_attempts,
            base_retry_seconds=base_retry_seconds,  # type: ignore[arg-type]
            max_retry_seconds=max_retry_seconds,  # type: ignore[arg-type]
        )

    def document(self) -> dict[str, object]:
        """Return the canonical secret-free managed document for this definition."""

        return {
            "id": self.webhook_id,
            "url": self.url,
            "secretEnv": self.secret_env,
            "events": [event.value for event in self.events],
            "enabled": self.enabled,
            "timeoutSeconds": self.timeout_seconds,
            "maxAttempts": self.max_attempts,
            "baseRetrySeconds": self.base_retry_seconds,
            "maxRetrySeconds": self.max_retry_seconds,
        }


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
