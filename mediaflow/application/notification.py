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
    NotificationRepository,
    WebhookDefinition,
    WebhookRequest,
    WebhookTransport,
)


class WebhookTransportError(RuntimeError):
    pass


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
    def __init__(
        self,
        repository: NotificationRepository,
        targets: dict[str, tuple[WebhookDefinition, str]],
        transport: WebhookTransport,
        *,
        delivery_lease_seconds: float = 300.0,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if delivery_lease_seconds <= 0:
            raise ValueError("notification delivery lease must be positive")
        self._repository = repository
        self._targets = targets
        self._transport = transport
        self._delivery_lease_seconds = delivery_lease_seconds
        self._clock = clock

    def run_next(self) -> NotificationDelivery | None:
        now = self._clock()
        delivery = self._repository.claim_next_delivery(
            now, now - timedelta(seconds=self._delivery_lease_seconds)
        )
        if delivery is None:
            return None
        target = self._targets.get(delivery.webhook_id)
        if target is None:
            return self._finish(
                delivery, NotificationDeliveryStatus.DEAD_LETTER, "configuration", None
            )
        definition, secret = target
        timestamp = str(int(self._clock().timestamp()))
        body = delivery.body.encode("utf-8")
        signature = hmac.new(
            secret.encode("utf-8"), timestamp.encode("ascii") + b"." + body, hashlib.sha256
        ).hexdigest()
        request = WebhookRequest(
            definition.url,
            body,
            {
                "Content-Type": "application/json; charset=utf-8",
                "X-MediaFlow-Delivery": delivery.delivery_id,
                "X-MediaFlow-Event": delivery.event_type.value,
                "X-MediaFlow-Event-ID": delivery.event_id,
                "X-MediaFlow-Signature": f"sha256={signature}",
                "X-MediaFlow-Timestamp": timestamp,
            },
            definition.timeout_seconds,
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
            if self.run_next() is None:
                sleep(poll_seconds)
            else:
                processed += 1
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
