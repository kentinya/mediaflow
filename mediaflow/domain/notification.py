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
# Default delivery-lease window used when no managed runtime configuration is
# available to an operator surface.  The signed Notification Worker uses the
# same 300-second default when the runtime document does not override it.
DELIVERY_LEASE_DEFAULT_SECONDS = 300.0
# The bounded value used to replace an already-persisted Webhook endpoint URL
# that carries a credential channel (userinfo, query or fragment) whenever it
# is projected.  It matches the existing managed-document secret redaction
# marker so operators can recognise a suppressed value, and it can never be
# mistaken for a real endpoint.
WEBHOOK_URL_REDACTED_VALUE = "***REDACTED***"


def webhook_url_validation_error(url: str) -> str | None:
    """Return one bounded reason an HTTPS Webhook URL is unsafe, else None.

    This is the single canonical endpoint rule shared by the domain validator,
    the runtime loader, managed typed-object validation and every projection
    decision.  The returned messages are constant and never echo the URL or
    any value it carries.  The query component is an unbounded
    credential-smuggling channel (names such as ``token``, ``api_key``,
    ``access_token``, ``client_secret``, ``secret``, ``password``,
    ``authorization``, ``credential``, ``signature``, ``access_key`` and
    ``secret_key``, in any casing/separator spelling, cannot be proven absent),
    so any query fails closed entirely instead of retaining a bypass.
    """

    try:
        parsed = urlsplit(url)
    except ValueError:
        return "Webhook URL must be HTTPS without userinfo, query or fragment"
    if parsed.scheme != "https" or not parsed.hostname:
        return "Webhook URL must be HTTPS with a hostname"
    if parsed.username is not None or parsed.password is not None:
        return "Webhook URL must not include userinfo credentials"
    if parsed.query:
        return "Webhook URL must not include a query string"
    if parsed.fragment:
        return "Webhook URL must not include a fragment"
    return None


def webhook_url_hides_value(url: object) -> bool:
    """Return True when a persisted Webhook URL value must never be serialized.

    Already-persisted/legacy Webhook definitions may predate the canonical
    endpoint rule.  Whenever such a stored URL carries a credential channel
    (userinfo, query or fragment) it must be suppressed or replaced by the
    bounded redaction marker on every projection, export, audit and error
    surface while the revision stays explicitly correctable.
    """

    if not isinstance(url, str) or not url:
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return bool(parsed.username or parsed.password or parsed.query or parsed.fragment)


def redact_webhook_url_value(url: object) -> object:
    """Return the bounded marker for a stored Webhook URL that must be hidden."""

    return WEBHOOK_URL_REDACTED_VALUE if webhook_url_hides_value(url) else url


def _webhook_item_lists(document: Mapping[str, object]):
    """Yield each mutable Webhook item list in a configuration document.

    The canonical managed spelling is the root ``webhooks`` section; the
    historical ``notifications.webhooks`` spelling is accepted for legacy
    documents.  Lists are yielded by reference so callers that own a deep copy
    can redact items in place.
    """

    root = document.get("webhooks")
    if isinstance(root, list):
        yield root
    notifications = document.get("notifications")
    if isinstance(notifications, Mapping):
        nested = notifications.get("webhooks")
        if isinstance(nested, list):
            yield nested


def redact_webhook_urls(document: Mapping[str, object]) -> int:
    """Replace unsafe Webhook ``url`` values in place on a mutable copy.

    Returns the number of values replaced.  Callers must only pass a document
    they own (a deep copy); persisted revisions are never mutated here.
    """

    count = 0
    for section in _webhook_item_lists(document):
        for item in section:
            if not isinstance(item, dict) or "url" not in item:
                continue
            original = item["url"]
            item["url"] = redact_webhook_url_value(original)
            if item["url"] != original:
                count += 1
    return count


def webhook_url_items(document: Mapping[str, object]) -> tuple[tuple[str, object], ...]:
    """Return every (webhook id, raw url) pair in a configuration document."""

    values: list[tuple[str, object]] = []
    for section in _webhook_item_lists(document):
        for item in section:
            if not isinstance(item, Mapping) or "url" not in item:
                continue
            webhook_id = item.get("id")
            identifier = str(webhook_id) if isinstance(webhook_id, str) and webhook_id else ""
            values.append((identifier, item["url"]))
    return tuple(values)


def unsafe_webhook_url_items(
    document: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    """Return the (webhook id, url) pairs whose URL must never be serialized."""

    return tuple(
        (identifier, url)
        for identifier, url in webhook_url_items(document)
        if webhook_url_hides_value(url)
    )


class NotificationDeliveryConflict(RuntimeError):
    """One delivery recovery/state conflict with bounded durable evidence.

    Raised when an operator action cannot be applied because the delivery is
    missing, its durable state no longer matches the exact state the operator
    observed, the lease has not expired yet, or the delivery is not eligible
    for the requested action.  ``delivery`` carries the current durable row so
    API/Web can show the actual state and a safe next action without exposing
    the delivery body or any secret material.
    """

    def __init__(
        self,
        message: str,
        *,
        delivery: NotificationDelivery | None = None,
        action: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.delivery = delivery
        self.action = action
        self.reason = reason


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
        url_problem = webhook_url_validation_error(self.url)
        if url_problem is not None:
            raise ValueError(url_problem)
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
    def requeue_dead_letter(
        self,
        delivery_id: str,
        now: datetime,
        *,
        expected_updated_at: datetime | None = None,
    ) -> NotificationDelivery: ...
    def resolve_stale_delivery(
        self,
        delivery_id: str,
        *,
        stale_before: datetime,
        now: datetime,
        expected_updated_at: datetime,
    ) -> NotificationDelivery: ...


@dataclass(frozen=True)
class WebhookRequest:
    url: str
    body: bytes
    headers: dict[str, str]
    timeout_seconds: float


class WebhookTransport(Protocol):
    def send(self, request: WebhookRequest) -> int: ...
