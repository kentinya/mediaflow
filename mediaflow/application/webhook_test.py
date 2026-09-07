from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.notification import WebhookTransportError, webhook_signature
from mediaflow.domain.configuration_management import (
    ConfigurationVersionConflict,
)
from mediaflow.domain.notification import NotificationEventType, WebhookDefinition, WebhookRequest
from mediaflow.domain.security import SecurityAuditRecord


def webhook_events_supported() -> tuple[str, ...]:
    return tuple(event.value for event in NotificationEventType)


class WebhookTestService:
    """Run an explicit, bounded HTTPS test against one exact managed revision.

    The test deliberately shares the signed transport semantics of the durable
    notification worker but never enqueues a delivery, never retries, never
    admits scheduler/workflow work and never mutates Storage or configuration.
    Remote bodies and exception text are reduced to safe categories.
    """

    MAX_TEST_BODY_BYTES = 64 * 1024

    def __init__(
        self,
        configuration_service: ManagedConfigurationService,
        transport: Any,
        *,
        clock: Callable[[], datetime] | None = None,
        audit_repository: Any = None,
    ) -> None:
        self._configuration = configuration_service
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._audit_repository = audit_repository

    def test(
        self,
        revision_id: str,
        webhook_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
    ) -> dict[str, object]:
        if isinstance(expected_version, bool) or not isinstance(expected_version, int):
            raise ConfigurationVersionConflict("webhook test expectedVersion must be an integer")
        if not isinstance(expected_digest, str) or not expected_digest:
            raise ConfigurationVersionConflict(
                "webhook test expectedDigest must be a non-empty string"
            )
        revision = self._configuration.require(revision_id)
        if revision.version != expected_version or revision.digest != expected_digest:
            raise ConfigurationVersionConflict(
                "the selected Webhook revision is stale; reload before testing",
                revision_id=revision.revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
                durable_state="configuration_preserved",
                next_action=(
                    "reload the configuration revision and test the exact current revision again"
                ),
            )
        raw = self._definition_document(revision.document, webhook_id)
        if raw is None:
            raise LookupError(
                f"Webhook definition {webhook_id!r} was not found in revision "
                f"{revision.revision_id!r}"
            )
        try:
            definition = WebhookDefinition.from_document(raw)
        except ValueError as error:
            return self._result(
                revision_id=revision_id,
                webhook_id=webhook_id,
                definition=None,
                actor=actor,
                category="invalid_definition",
                message=self._bounded_text(str(error), 384),
                response_status=None,
            )
        secret_env = definition.secret_env
        secret = os.environ.get(secret_env)
        if not secret:
            return self._result(
                revision_id=revision_id,
                webhook_id=webhook_id,
                definition=definition,
                actor=actor,
                category="missing_secret",
                message=(
                    f"Webhook {webhook_id!r} references environment variable "
                    f"{secret_env} which is not set in this process"
                ),
                response_status=None,
            )
        test_id = str(uuid4())
        timestamp = str(int(self._clock().timestamp()))
        body = json.dumps(
            {
                "type": "webhook.test",
                "testId": test_id,
                "timestamp": self._clock().astimezone(UTC).isoformat(),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        signature = webhook_signature(secret, timestamp, body)
        request = WebhookRequest(
            definition.url,
            body,
            {
                "Content-Type": "application/json; charset=utf-8",
                "X-MediaFlow-Test": test_id,
                "X-MediaFlow-Webhook": webhook_id,
                "X-MediaFlow-Signature": f"sha256={signature}",
                "X-MediaFlow-Timestamp": timestamp,
            },
            definition.timeout_seconds,
        )
        try:
            status = self._transport.send(request)
        except TimeoutError:
            return self._result(
                revision_id=revision_id,
                webhook_id=webhook_id,
                definition=definition,
                actor=actor,
                category="timeout",
                message="the Webhook test timed out before a response",
                response_status=None,
            )
        except (WebhookTransportError, OSError, RuntimeError) as error:
            category = "transport"
            message = "the Webhook transport failed before a bounded response"
            if isinstance(error, WebhookTransportError):
                message = "the Webhook transport could not send the signed test request"
            return self._result(
                revision_id=revision_id,
                webhook_id=webhook_id,
                definition=definition,
                actor=actor,
                category=category,
                message=message,
                response_status=None,
            )
        if 200 <= status < 300:
            outcome = "success"
            category = f"http_{status}"
            message = f"the Webhook endpoint returned HTTP {status}"
        elif status == 429 or status >= 500:
            outcome = "failure"
            category = f"http_{status}"
            message = (
                f"the Webhook endpoint returned HTTP {status}; retry after fixing the "
                "endpoint or its availability"
            )
        else:
            outcome = "failure"
            category = f"http_{status}"
            message = f"the Webhook endpoint rejected the signed test with HTTP {status}"
        return self._result(
            revision_id=revision_id,
            webhook_id=webhook_id,
            definition=definition,
            actor=actor,
            category=category,
            message=message,
            response_status=status,
            outcome=outcome,
            test_id=test_id,
        )

    # ------------------------------------------------------------------

    def _result(
        self,
        *,
        revision_id: str,
        webhook_id: str,
        definition: WebhookDefinition | None,
        actor: str,
        category: str,
        message: str,
        response_status: int | None,
        outcome: str = "failure",
        test_id: str | None = None,
    ) -> dict[str, object]:
        revision = self._configuration.require(revision_id)
        webhook_document = (
            {
                "id": definition.webhook_id,
                "url": definition.url,
                "events": [event.value for event in definition.events],
                "enabled": definition.enabled,
                "secretEnv": definition.secret_env,
            }
            if definition is not None
            else {"id": webhook_id}
        )
        transient = category in {
            "timeout",
            "transport",
            "missing_secret",
            "invalid_definition",
        }
        retry_safe = (
            transient
            or (response_status is not None and 200 <= response_status < 300)
            or (response_status is not None and response_status == 429)
            or (response_status is not None and response_status >= 500)
        )
        next_action = {
            "timeout": (
                "confirm the endpoint is reachable and within the configured timeout, then "
                "test the exact revision again"
            ),
            "transport": (
                "confirm the endpoint and network path, then test the exact revision again"
            ),
            "missing_secret": (
                "set the referenced deployment environment variable, then test the exact "
                "revision again"
            ),
            "invalid_definition": (
                "correct the Webhook definition in a Draft, validate, then test the "
                "intended revision"
            ),
        }.get(
            category,
            ("confirm the endpoint accepts the signed request, then test the exact revision again"),
        )
        if response_status is not None and 200 <= response_status < 300:
            next_action = "no further action required; the endpoint accepted the signed test"
        document = {
            "testId": test_id,
            "webhook": webhook_document,
            "revision": {
                "revisionId": revision.revision_id,
                "version": revision.version,
                "digest": revision.digest,
                "status": revision.status.value,
            },
            "outcome": outcome,
            "category": category,
            "responseStatus": response_status,
            "message": message,
            "durableState": "no_delivery_created_no_configuration_change",
            "sideEffects": "none",
            "retrySafe": retry_safe,
            "nextAction": next_action,
        }
        self._audit(
            actor=actor,
            revision_id=revision.revision_id,
            webhook_id=webhook_id,
            category=category,
            outcome=outcome,
        )
        return document

    @classmethod
    def _definition_document(
        cls,
        document: Mapping[str, object],
        webhook_id: str,
    ) -> dict[str, object] | None:
        values = document.get("webhooks")
        if not isinstance(values, list):
            notifications = document.get("notifications")
            if isinstance(notifications, Mapping):
                values = notifications.get("webhooks")
        if not isinstance(values, list):
            return None
        for item in values:
            if isinstance(item, Mapping) and item.get("id") == webhook_id:
                return dict(item)
        return None

    @staticmethod
    def _bounded_text(value: str, maximum: int) -> str:
        encoded = value.encode("utf-8")
        if len(encoded) <= maximum:
            return value
        return encoded[:maximum].decode("utf-8", errors="ignore")

    def _audit(
        self,
        *,
        actor: str,
        revision_id: str,
        webhook_id: str,
        category: str,
        outcome: str,
    ) -> None:
        repository = getattr(self._audit_repository, "append_security_audit", None)
        if not callable(repository):
            return
        try:
            repository(
                SecurityAuditRecord(
                    str(uuid4()),
                    self._clock(),
                    actor,
                    "POST",
                    (
                        f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks/"
                        f"{webhook_id}/test?category={category}"
                    )[:500],
                    "webhook-test",
                    outcome,
                    0,
                    str(uuid4()),
                    None,
                )
            )
        except Exception:
            # Audit failure must never block or leak an already-bounded test
            # outcome to the operator.
            return
