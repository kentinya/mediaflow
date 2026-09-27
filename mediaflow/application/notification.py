from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from mediaflow.domain.notification import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEvent,
    NotificationEventType,
    NotificationRepository,
    WebhookDefinition,
    WebhookRequest,
    WebhookTransport,
)


class WebhookTransportError(RuntimeError):
    pass


def webhook_signature(secret: str, timestamp: str, body: bytes) -> str:
    """Return the sha256 signature used by signed MediaFlow webhook requests."""

    return hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()


def build_signed_request(
    definition: WebhookDefinition,
    secret: str,
    *,
    body: bytes,
    delivery_id: str,
    event_type: NotificationEventType,
    event_id: str,
    timestamp: str,
) -> WebhookRequest:
    """Build one bounded signed webhook request using the shared transport semantics."""

    signature = webhook_signature(secret, timestamp, body)
    return WebhookRequest(
        definition.url,
        body,
        {
            "Content-Type": "application/json; charset=utf-8",
            "X-MediaFlow-Delivery": delivery_id,
            "X-MediaFlow-Event": event_type.value,
            "X-MediaFlow-Event-ID": event_id,
            "X-MediaFlow-Signature": f"sha256={signature}",
            "X-MediaFlow-Timestamp": timestamp,
        },
        definition.timeout_seconds,
    )


class NotificationPublisher:
    """Writes deterministic subscribed deliveries; it never performs network I/O."""

    def __init__(
        self,
        repository: NotificationRepository,
        webhooks: tuple[WebhookDefinition, ...],
    ) -> None:
        self._repository = repository
        self._webhooks = webhooks

    def publish(self, event: NotificationEvent) -> tuple[NotificationDelivery, ...]:
        body = json.dumps(
            {
                "data": event.data,
                "eventId": event.event_id,
                "eventType": event.event_type.value,
                "occurredAt": event.occurred_at.astimezone(UTC).isoformat(),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        created = []
        for webhook in self._webhooks:
            if not webhook.enabled or event.event_type not in webhook.events:
                continue
            now = event.occurred_at.astimezone(UTC)
            delivery = NotificationDelivery(
                str(uuid5(NAMESPACE_URL, f"{webhook.webhook_id}:{event.event_id}")),
                webhook.webhook_id,
                event.event_id,
                event.event_type,
                body,
                NotificationDeliveryStatus.PENDING,
                0,
                now,
                now,
                now,
            )
            if self._repository.create_delivery(delivery):
                created.append(delivery)
        return tuple(created)


class NotificationWorker:
    """Deliver signed webhook notifications for durably claimed deliveries.

    Delivery configuration is resolved **per claim**, not captured at startup.
    That is what lets a resident Notification Worker start before any webhook is
    configured, adopt a later valid publication without a restart, and still
    refuse to deliver against a target that has since been removed, changed or
    disabled.

    The resolution contract is deliberately asymmetric, because the two failure
    directions have very different consequences:

    * **no valid configuration at all** (never configured, Active missing, or
      secret absent) is a *waiting* state.  The worker does not claim anything,
      does not burn an attempt and does not dead-letter a delivery.  The
      delivery stays pending and claimable, and the resident loop retries.
    * **a specific delivery whose target no longer exists or no longer matches**
      is a *per-delivery* fault.  Claiming it would consume an attempt and
      silently discard a durable notification, so the worker must know before
      it claims.  It therefore asks the resolver whether *this* webhook is
      deliverable, and leaves an undeliverable delivery untouched.

    A changed target is never silently accepted either: the resolver returns the
    definition that the current Active actually publishes, and the worker
    compares the durable ``webhook_id`` identity before using it.
    """

    def __init__(
        self,
        repository: NotificationRepository,
        targets: (
            dict[str, tuple[WebhookDefinition, str]]
            | Callable[[], dict[str, tuple[WebhookDefinition, str]]]
        ),
        transport: WebhookTransport,
        *,
        delivery_lease_seconds: float = 300.0,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if delivery_lease_seconds <= 0:
            raise ValueError("notification delivery lease must be positive")
        self._repository = repository
        if callable(targets):
            self._target_resolver: Callable[[], dict[str, tuple[WebhookDefinition, str]]] = targets
        else:
            static = dict(targets)
            self._target_resolver = lambda: static
        self._transport = transport
        self._delivery_lease_seconds = delivery_lease_seconds
        self._clock = clock
        #: The reason the most recent resolution attempt could not produce a
        #: usable target.  The resident loop reads it to report a bounded
        #: waiting state without this class knowing anything about services.
        self.last_unavailable_reason: str | None = None

    def resolve_targets(self) -> dict[str, tuple[WebhookDefinition, str]]:
        """Resolve the current deliverable targets, or fail with a bounded reason.

        A missing webhook secret is a configuration fault, not a process fault:
        the resident process must stay alive and wait for the secret, so the
        resolution failure is recorded on ``last_unavailable_reason`` and raised
        as a ``ValueError`` the caller can classify.
        """

        try:
            targets = self._target_resolver()
        except Exception as error:
            self.last_unavailable_reason = (
                f"{type(error).__name__}: the current delivery configuration could not be read"
            )
            raise
        self.last_unavailable_reason = (
            None if targets else "no enabled Webhook target is configured"
        )
        return dict(targets)

    def available_webhook_ids(
        self, targets: dict[str, tuple[WebhookDefinition, str]]
    ) -> tuple[str, ...]:
        """The durable target identities this Worker may lawfully claim for.

        Passing this to the repository claim is what prevents a delivery naming
        a removed or disabled webhook from being claimed — and therefore from
        burning an attempt — merely because it happened to sort first.
        """

        return tuple(sorted(targets))

    def run_next(self) -> NotificationDelivery | None:
        targets = self.resolve_targets()
        if not targets:
            # Nothing is deliverable.  Claiming here would burn an attempt and
            # dead-letter a perfectly good durable delivery.
            return None
        now = self._clock()
        delivery = self._repository.claim_next_delivery(
            now,
            now - timedelta(seconds=self._delivery_lease_seconds),
            webhook_ids=self.available_webhook_ids(targets),
        )
        if delivery is None:
            return None
        target = targets.get(delivery.webhook_id)
        if target is None:
            # The durable delivery names a target that current configuration no
            # longer publishes.  This is a genuine per-delivery fault: the
            # delivery can never succeed as written, so it must converge rather
            # than stay claimable forever.  It is *not* silent retargeting —
            # the recorded failure names the missing target.
            return self._finish(
                delivery, NotificationDeliveryStatus.DEAD_LETTER, "configuration", None
            )
        definition, secret = target
        timestamp = str(int(self._clock().timestamp()))
        body = delivery.body.encode("utf-8")
        request = build_signed_request(
            definition,
            secret,
            body=body,
            delivery_id=delivery.delivery_id,
            event_type=delivery.event_type,
            event_id=delivery.event_id,
            timestamp=timestamp,
        )
        try:
            status = self._transport.send(request)
        except Exception:
            return self._retry_or_dead(delivery, definition, "transport", None)
        if 200 <= status < 300:
            return self._finish(delivery, NotificationDeliveryStatus.DELIVERED, None, status)
        if status == 429 or status >= 500:
            return self._retry_or_dead(delivery, definition, f"http_{status}", status)
        return self._finish(
            delivery, NotificationDeliveryStatus.DEAD_LETTER, f"http_{status}", status
        )

    def run(
        self,
        stop_requested: Callable[[], bool],
        *,
        poll_seconds: float,
        sleep: Callable[[float], None],
    ) -> int:
        if poll_seconds <= 0:
            raise ValueError("notification poll interval must be positive")
        processed = 0
        while not stop_requested():
            try:
                if self.run_next() is None:
                    sleep(poll_seconds)
                else:
                    processed += 1
            except Exception:
                # Target resolution is the only expected failure here.  Waiting
                # is the correct behaviour: never exit, never claim, never
                # discard a delivery because a secret is temporarily absent.
                sleep(poll_seconds)
        return processed

    def _retry_or_dead(
        self,
        delivery: NotificationDelivery,
        definition: WebhookDefinition,
        category: str,
        response_status: int | None,
    ) -> NotificationDelivery:
        if delivery.attempts >= definition.max_attempts:
            return self._finish(
                delivery, NotificationDeliveryStatus.DEAD_LETTER, category, response_status
            )
        delay = min(
            definition.max_retry_seconds,
            definition.base_retry_seconds * (2 ** (delivery.attempts - 1)),
        )
        now = self._clock()
        updated = replace(
            delivery,
            status=NotificationDeliveryStatus.RETRY,
            next_attempt_at=now + timedelta(seconds=delay),
            updated_at=now,
            failure_category=category,
            response_status=response_status,
        )
        self._repository.update_delivery(updated)
        return updated

    def _finish(
        self,
        delivery: NotificationDelivery,
        status: NotificationDeliveryStatus,
        category: str | None,
        response_status: int | None,
    ) -> NotificationDelivery:
        now = self._clock()
        updated = replace(
            delivery,
            status=status,
            updated_at=now,
            delivered_at=now if status is NotificationDeliveryStatus.DELIVERED else None,
            failure_category=category,
            response_status=response_status,
        )
        self._repository.update_delivery(updated)
        return updated
