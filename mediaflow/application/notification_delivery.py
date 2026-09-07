from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from mediaflow.domain.notification import (
    DELIVERY_LEASE_DEFAULT_SECONDS,
    NotificationDelivery,
    NotificationDeliveryConflict,
    NotificationDeliveryStatus,
    NotificationRepository,
)
from mediaflow.domain.security import SecurityAuditRecord


class NotificationDeliveryService:
    """One shared application authority for delivery detail and recovery.

    The service is the single place that turns a durable delivery row into the
    bounded operator projection (lease/staleness, known effects, retry safety,
    next action and the explicitly available recovery actions) and that applies
    a dead-letter requeue or stale-delivery recovery under optimistic
    concurrency on the exact ``status`` + ``updated_at`` the operator observed.
    API and Web both call through this authority so permissions, validation,
    state transitions, audit, redaction and recovery semantics cannot diverge.

    Delivery bodies, secrets, authorization material, cookies and remote
    response content are never read into the projection; only the durable
    bounded columns of ``notification_deliveries`` are exposed.
    """

    def __init__(
        self,
        repository: NotificationRepository,
        *,
        audit_repository: object | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_repository = audit_repository
        self._clock = clock or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------
    # Read projection

    def detail(
        self,
        delivery_id: str,
        *,
        lease_seconds: float = DELIVERY_LEASE_DEFAULT_SECONDS,
    ) -> dict[str, object]:
        delivery = self._require(delivery_id)
        return self.delivery_document(
            delivery,
            now=self._clock(),
            lease_seconds=lease_seconds,
        )

    # ------------------------------------------------------------------
    # Recovery actions

    def requeue_dead_letter(
        self,
        delivery_id: str,
        *,
        expected_status: str,
        expected_updated_at: str,
        lease_seconds: float = DELIVERY_LEASE_DEFAULT_SECONDS,
        actor: str = "operator",
    ) -> dict[str, object]:
        now = self._clock()
        expected = self._expected_state(expected_status, expected_updated_at)
        delivery = self._require(delivery_id)
        self._verify_current(delivery, expected, action="requeue-dead-letter")
        if delivery.status is not NotificationDeliveryStatus.DEAD_LETTER:
            raise self._conflict(
                delivery,
                action="requeue-dead-letter",
                message="only a dead-letter delivery can be explicitly requeued",
            )
        try:
            updated = self._repository.requeue_dead_letter(
                delivery_id,
                now,
                expected_updated_at=expected.updated_at,
            )
        except ValueError:
            raise self._conflict(
                self._current_or_missing(delivery_id),
                action="requeue-dead-letter",
                message="the delivery state changed before it could be requeued",
            ) from None
        return self._recovery_document(
            updated,
            previous=delivery,
            action="requeue-dead-letter",
            actor=actor,
            lease_seconds=lease_seconds,
        )

    def resolve_stale(
        self,
        delivery_id: str,
        *,
        expected_status: str,
        expected_updated_at: str,
        lease_seconds: float = DELIVERY_LEASE_DEFAULT_SECONDS,
        actor: str = "operator",
    ) -> dict[str, object]:
        now = self._clock()
        expected = self._expected_state(expected_status, expected_updated_at)
        delivery = self._require(delivery_id)
        self._verify_current(delivery, expected, action="resolve-stale")
        stale_before = now - timedelta(seconds=lease_seconds)
        if delivery.status is not NotificationDeliveryStatus.DELIVERING:
            raise self._conflict(
                delivery,
                action="resolve-stale",
                message="only an in-progress delivery with an expired lease can be resolved",
            )
        if delivery.updated_at > stale_before:
            raise self._conflict(
                delivery,
                action="resolve-stale",
                message="the delivery lease has not expired yet; no stale recovery is eligible",
            )
        try:
            updated = self._repository.resolve_stale_delivery(
                delivery_id,
                stale_before=stale_before,
                now=now,
                expected_updated_at=expected.updated_at,
            )
        except ValueError:
            raise self._conflict(
                self._current_or_missing(delivery_id),
                action="resolve-stale",
                message="the delivery state changed before it could be resolved",
            ) from None
        return self._recovery_document(
            updated,
            previous=delivery,
            action="resolve-stale",
            actor=actor,
            lease_seconds=lease_seconds,
        )

    # ------------------------------------------------------------------
    # Projection helpers

    def delivery_document(
        self,
        delivery: NotificationDelivery,
        *,
        now: datetime,
        lease_seconds: float = DELIVERY_LEASE_DEFAULT_SECONDS,
    ) -> dict[str, object]:
        plan = self._plan(delivery, now=now, lease_seconds=lease_seconds)
        return {
            "deliveryId": delivery.delivery_id,
            "webhookId": delivery.webhook_id,
            "eventId": delivery.event_id,
            "eventType": delivery.event_type.value,
            "status": delivery.status.value,
            "attempts": delivery.attempts,
            "createdAt": delivery.created_at.isoformat(),
            "updatedAt": delivery.updated_at.isoformat(),
            "deliveredAt": (delivery.delivered_at.isoformat() if delivery.delivered_at else None),
            "nextAttemptAt": delivery.next_attempt_at.isoformat(),
            "failureCategory": delivery.failure_category,
            "responseStatus": delivery.response_status,
            "lease": plan["lease"],
            "knownEffects": plan["known_effects"],
            "retrySafe": plan["retry_safe"],
            "nextAction": plan["next_action"],
            "recovery": {
                "availableActions": [action["name"] for action in plan["actions"]],
                "reason": plan["reason"],
                "actions": plan["actions"],
            },
        }

    @staticmethod
    def _expected_state(expected_status: str, expected_updated_at: str):
        if not isinstance(expected_status, str) or not expected_status:
            raise ValueError("delivery recovery expectedStatus is required")
        if not isinstance(expected_updated_at, str) or not expected_updated_at:
            raise ValueError("delivery recovery expectedUpdatedAt is required")
        try:
            status = NotificationDeliveryStatus(expected_status)
        except ValueError as error:
            raise ValueError("delivery recovery expectedStatus is invalid") from error
        try:
            updated_at = datetime.fromisoformat(expected_updated_at)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "delivery recovery expectedUpdatedAt must be an ISO timestamp"
            ) from error
        if updated_at.tzinfo is None:
            raise ValueError("delivery recovery expectedUpdatedAt must include a timezone")
        return _ExpectedState(status, updated_at)

    def _verify_current(
        self,
        delivery: NotificationDelivery,
        expected: _ExpectedState,
        *,
        action: str,
    ) -> None:
        if delivery.status is not expected.status or delivery.updated_at != expected.updated_at:
            raise self._conflict(
                delivery,
                action=action,
                message=(
                    "the delivery state is newer than the state you inspected; "
                    "reload the delivery before recovering it"
                ),
            )

    def _plan(
        self,
        delivery: NotificationDelivery,
        *,
        now: datetime,
        lease_seconds: float,
    ) -> dict[str, object]:
        status = delivery.status
        if status is NotificationDeliveryStatus.PENDING:
            return self._plain_plan(
                delivery,
                known_effects="No outbound request for this delivery has completed.",
                retry_safe=True,
                next_action=(
                    "No manual action required; the notification worker will claim this "
                    "delivery when it is due."
                ),
                reason="This delivery is pending automatic delivery.",
            )
        if status is NotificationDeliveryStatus.RETRY:
            return self._plain_plan(
                delivery,
                known_effects=(
                    "Earlier attempts did not return a successful HTTP 2xx confirmation; "
                    "whether the receiver processed an earlier request is unknown."
                ),
                retry_safe=True,
                next_action=(
                    "No manual action required; an automatic retry is scheduled for "
                    f"{delivery.next_attempt_at.astimezone(UTC).isoformat()}."
                ),
                reason="An automatic retry is already scheduled.",
            )
        if status is NotificationDeliveryStatus.DELIVERING:
            expired = delivery.updated_at <= now - timedelta(seconds=lease_seconds)
            lease = {
                "state": "expired" if expired else "active",
                "leaseSeconds": lease_seconds,
                "claimedAt": delivery.updated_at.isoformat(),
                "expiresAt": (delivery.updated_at + timedelta(seconds=lease_seconds)).isoformat(),
            }
            if expired:
                action = {
                    "name": "resolve-stale",
                    "durableState": (
                        "the delivery stays one row with the same identity and attempts; "
                        "the queue state returns to pending"
                    ),
                    "sideEffects": (
                        "no new delivery and no media, Task, Job, schedule or Storage "
                        "change; the notification worker will send the event again"
                    ),
                    "retrySafe": True,
                    "duplicateImplication": (
                        "the original attempt may have reached the receiver before the "
                        "worker stopped; resolving re-enqueues the same delivery identity, "
                        "so the receiver may process the event more than once "
                        "(at-least-once)"
                    ),
                    "nextAction": (
                        "explicitly resolve the stale delivery, then refresh; the worker "
                        "reclaims it automatically"
                    ),
                }
                return {
                    "lease": lease,
                    "known_effects": (
                        "the delivery lease expired without a durable terminal outcome; "
                        "the receiver may have processed the original request before the "
                        "worker stopped (at-least-once)"
                    ),
                    "retry_safe": True,
                    "next_action": (
                        "resolve the stale delivery to return it to the pending queue, or "
                        "refresh if the worker is only slow"
                    ),
                    "reason": "The delivery lease expired without a terminal outcome.",
                    "actions": [action],
                }
            return {
                "lease": lease,
                "known_effects": (
                    "an outbound request is in progress; the receiver may or may not have "
                    "processed it"
                ),
                "retry_safe": True,
                "next_action": (
                    "wait for the notification worker; if the lease expires without a "
                    "terminal outcome this delivery becomes stale and can be explicitly "
                    "resolved"
                ),
                "reason": "The notification worker currently holds an unexpired lease.",
                "actions": [],
            }
        if status is NotificationDeliveryStatus.DELIVERED:
            status_text = (
                f"HTTP {delivery.response_status}"
                if delivery.response_status is not None
                else "a successful response"
            )
            return self._plain_plan(
                delivery,
                known_effects=(
                    f"The receiver confirmed the signed request with {status_text}; this "
                    "delivery completed successfully."
                ),
                retry_safe=True,
                next_action="No action required.",
                reason="The delivery already completed successfully.",
            )
        # DEAD_LETTER is the only remaining durable status.
        transient = self._dead_letter_is_retryable(delivery)
        if delivery.failure_category == "configuration":
            next_action = (
                "the Webhook target is not available in the current Active configuration; "
                "enable or re-add the definition, then explicitly requeue this delivery"
            )
        elif transient:
            next_action = (
                "confirm the endpoint is reachable and healthy, then explicitly requeue "
                "this delivery"
            )
        else:
            next_action = (
                "the receiver rejected the signed request; correct the endpoint or "
                "definition, then explicitly requeue this delivery"
            )
        action = {
            "name": "requeue-dead-letter",
            "durableState": (
                "the delivery stays one row with the same identity; attempts are reset "
                "and the queue state returns to pending"
            ),
            "sideEffects": (
                "no new delivery and no media, Task, Job, schedule or Storage change; "
                "the notification worker will send the event again"
            ),
            "retrySafe": transient,
            "duplicateImplication": (
                "the receiver never confirmed the earlier attempts, so requeueing is not "
                "expected to duplicate; under at-least-once semantics a receiver that did "
                "process an unconfirmed request may still see the event again"
            ),
            "nextAction": (
                "explicitly requeue this delivery, then refresh; the worker delivers it "
                "automatically"
            ),
        }
        category = delivery.failure_category or "unknown"
        return {
            "lease": {"state": "not_leased"},
            "known_effects": (
                "the receiver never confirmed success after the configured attempts "
                f"(last failure: {category}); whether an earlier request was processed is "
                "unknown"
            ),
            "retry_safe": transient,
            "next_action": next_action,
            "reason": "The delivery reached the terminal dead-letter state.",
            "actions": [action],
        }

    @staticmethod
    def _plain_plan(
        delivery: NotificationDelivery,
        *,
        known_effects: str,
        retry_safe: bool,
        next_action: str,
        reason: str,
    ) -> dict[str, object]:
        return {
            "lease": {"state": "not_leased"},
            "known_effects": known_effects,
            "retry_safe": retry_safe,
            "next_action": next_action,
            "reason": reason,
            "actions": [],
        }

    @staticmethod
    def _dead_letter_is_retryable(delivery: NotificationDelivery) -> bool:
        category = delivery.failure_category or ""
        if category in {"transport", "timeout", "configuration"}:
            return True
        if not category.startswith("http_"):
            return True
        try:
            status = int(category.removeprefix("http_"))
        except ValueError:
            return True
        return status == 429 or status >= 500

    def _recovery_document(
        self,
        updated: NotificationDelivery,
        *,
        previous: NotificationDelivery,
        action: str,
        actor: str,
        lease_seconds: float,
    ) -> dict[str, object]:
        duplicate = (
            "the original attempt may have reached the receiver before the worker "
            "stopped; the receiver may process the event more than once (at-least-once)"
            if action == "resolve-stale"
            else (
                "the receiver never confirmed the earlier attempts, so duplicate delivery "
                "is not expected; under at-least-once semantics an unconfirmed request may "
                "still have been processed"
            )
        )
        document = {
            "action": action,
            "outcome": "success",
            "deliveryId": updated.delivery_id,
            "previousStatus": previous.status.value,
            "status": updated.status.value,
            "attempts": updated.attempts,
            "durableState": (
                "stale_delivery_returned_to_queue_same_identity"
                if action == "resolve-stale"
                else "dead_letter_requeued_same_identity"
            ),
            "sideEffects": ("delivery_queue_state_only_no_new_row_no_media_change"),
            "retrySafe": True,
            "atLeastOnce": (
                "recovery preserves the stable delivery identity; the worker sends the "
                "event again, so receivers must tolerate duplicates"
            ),
            "duplicateImplication": duplicate,
            "nextAction": (
                "the delivery is pending again; refresh this delivery and the list to "
                "watch the worker reclaim and deliver it"
            ),
            "delivery": self.delivery_document(
                updated,
                now=self._clock(),
                lease_seconds=lease_seconds,
            ),
        }
        self._audit(actor=actor, previous=previous, updated=updated, action=action)
        return document

    def _require(self, delivery_id: str) -> NotificationDelivery:
        delivery = self._repository.get_delivery(delivery_id)
        if delivery is None:
            raise LookupError(f"notification delivery {delivery_id!r} was not found")
        return delivery

    def _current_or_missing(self, delivery_id: str) -> NotificationDelivery | None:
        return self._repository.get_delivery(delivery_id)

    @staticmethod
    def _conflict(
        delivery: NotificationDelivery | None,
        *,
        action: str,
        message: str,
    ) -> NotificationDeliveryConflict:
        return NotificationDeliveryConflict(
            message,
            delivery=delivery,
            action=action,
        )

    def _audit(
        self,
        *,
        actor: str,
        previous: NotificationDelivery,
        updated: NotificationDelivery,
        action: str,
    ) -> None:
        repository = getattr(self._audit_repository, "append_security_audit", None)
        if not callable(repository):
            return
        route = (
            f"/api/v1/notifications/{previous.delivery_id}/{action}"
            f"?from={previous.status.value}&to={updated.status.value}"
            f"&attempts={updated.attempts}"
        )
        try:
            repository(
                SecurityAuditRecord(
                    str(uuid4()),
                    self._clock(),
                    actor,
                    "POST",
                    route[:500],
                    "notification-recovery",
                    "success",
                    200,
                    str(uuid4()),
                    None,
                )
            )
        except Exception:
            # Audit failure must never block an already-bounded recovery outcome.
            return


class _ExpectedState:
    __slots__ = ("status", "updated_at")

    def __init__(self, status: NotificationDeliveryStatus, updated_at: datetime) -> None:
        self.status = status
        self.updated_at = updated_at
