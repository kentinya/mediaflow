from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from uuid import uuid4

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.notification import WebhookTransportError, webhook_signature
from mediaflow.domain.configuration_management import (
    ConfigurationVersionConflict,
    ManagedConfigurationRevision,
)
from mediaflow.domain.notification import (
    NotificationEventType,
    WebhookDefinition,
    WebhookRequest,
    accepted_webhook_definition,
)
from mediaflow.domain.security import SecurityAuditRecord


@dataclass(frozen=True)
class _WebhookTestEvidence:
    """The bounded proof one successful probe leaves for its exact form."""

    test_id: str
    actor: str
    webhook_id: str
    url: str
    secret_env: str
    baseline_revision_id: str
    baseline_version: int
    created_at: datetime


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
    EVIDENCE_TTL = timedelta(minutes=15)
    EVIDENCE_LIMIT = 128

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
        # A successful test proves only the exact tested form against the exact
        # Active baseline that was displayed. Evidence stays in this process,
        # bounded by count and a short lifetime; it is never durable
        # configuration and never a second publish authority.
        self._evidence: dict[str, _WebhookTestEvidence] = {}
        self._evidence_lock = Lock()

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
            definition = accepted_webhook_definition(raw)
        except ValueError as error:
            return self._result(
                revision=revision,
                webhook_id=webhook_id,
                definition=None,
                actor=actor,
                category="invalid_definition",
                message=self._bounded_text(str(error), 384),
                response_status=None,
            )
        return self._send(
            definition,
            webhook_id=webhook_id,
            actor=actor,
            revision=revision,
            baseline=revision,
        )

    def test_definition(
        self,
        raw: Mapping[str, object],
        *,
        webhook_id: str,
        actor: str,
        baseline: ManagedConfigurationRevision,
    ) -> dict[str, object]:
        """Send exactly one signed probe for this unsaved form and baseline."""

        try:
            definition = accepted_webhook_definition(raw)
        except ValueError as error:
            return self._result(
                revision=None,
                webhook_id=webhook_id,
                definition=None,
                actor=actor,
                category="invalid_definition",
                message=self._bounded_text(str(error), 384),
                response_status=None,
            )
        if definition.webhook_id != webhook_id:
            raise ValueError("Webhook test definition ID must match the route")
        return self._send(
            definition,
            webhook_id=webhook_id,
            actor=actor,
            revision=None,
            baseline=baseline,
        )

    def _send(
        self,
        definition: WebhookDefinition,
        *,
        webhook_id: str,
        actor: str,
        revision: ManagedConfigurationRevision | None,
        baseline: ManagedConfigurationRevision,
    ) -> dict[str, object]:
        secret_env = definition.secret_env
        secret = os.environ.get(secret_env)
        if not secret:
            return self._result(
                revision=revision,
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
                revision=revision,
                webhook_id=webhook_id,
                definition=definition,
                actor=actor,
                category="timeout",
                message="the Webhook test timed out before a response",
                response_status=None,
            )
        except (WebhookTransportError, OSError, RuntimeError):
            return self._result(
                revision=revision,
                webhook_id=webhook_id,
                definition=definition,
                actor=actor,
                category="transport",
                message="the Webhook transport could not send the signed test request",
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
        evidence_id = (
            self._remember_evidence(
                definition,
                webhook_id=webhook_id,
                actor=actor,
                baseline=baseline,
            )
            if outcome == "success"
            else None
        )
        return self._result(
            revision=revision,
            webhook_id=webhook_id,
            definition=definition,
            actor=actor,
            category=category,
            message=message,
            response_status=status,
            outcome=outcome,
            test_id=test_id,
            test_evidence_id=evidence_id,
        )

    # ------------------------------------------------------------------

    def _result(
        self,
        *,
        revision: ManagedConfigurationRevision | None,
        webhook_id: str,
        definition: WebhookDefinition | None,
        actor: str,
        category: str,
        message: str,
        response_status: int | None,
        outcome: str = "failure",
        test_id: str | None = None,
        test_evidence_id: str | None = None,
    ) -> dict[str, object]:
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
            "testEvidenceId": test_evidence_id,
            "webhook": webhook_document,
            "revision": (
                {
                    "revisionId": revision.revision_id,
                    "version": revision.version,
                    "digest": revision.digest,
                    "status": revision.status.value,
                }
                if revision is not None
                else None
            ),
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
            revision=revision,
            webhook_id=webhook_id,
            category=category,
            outcome=outcome,
        )
        return document

    # ------------------------------------------------------------------
    # Successful-test evidence used by the checked object publication

    def _remember_evidence(
        self,
        definition: WebhookDefinition,
        *,
        webhook_id: str,
        actor: str,
        baseline: ManagedConfigurationRevision,
    ) -> str:
        evidence_id = str(uuid4())
        evidence = _WebhookTestEvidence(
            evidence_id,
            actor,
            webhook_id,
            definition.url,
            definition.secret_env,
            baseline.revision_id,
            baseline.version,
            self._clock(),
        )
        with self._evidence_lock:
            self._prune_evidence_locked(evidence.created_at)
            if len(self._evidence) >= self.EVIDENCE_LIMIT:
                oldest = min(self._evidence.values(), key=lambda item: item.created_at)
                self._evidence.pop(oldest.test_id, None)
            self._evidence[evidence_id] = evidence
        return evidence_id

    def verify_evidence(
        self,
        evidence_id: object,
        *,
        webhook_id: str,
        url: object,
        secret_env: object,
        baseline_revision_id: str,
        baseline_version: int,
        actor: str,
    ) -> None:
        """Require one successful probe for this exact form and baseline.

        The check runs before any candidate is staged, so a missing, expired
        or mismatched result cannot publish, advance an Active revision or add
        a publication audit. A changed address or secret reference is a
        different form and therefore a different proof.
        """

        evidence = None
        if isinstance(evidence_id, str) and evidence_id.strip():
            with self._evidence_lock:
                evidence = self._evidence.get(evidence_id)
                if evidence is not None:
                    self._prune_evidence_locked(self._clock())
                    evidence = self._evidence.get(evidence_id)
        if evidence is None:
            raise ConfigurationVersionConflict(
                "a successful signature test of this form is required before applying",
                durable_state="active_preserved",
                next_action=(
                    "run one signed test on the current form, then apply without changing "
                    "its address or secret reference"
                ),
            )
        active = self._configuration.active()
        if (
            evidence.actor != actor
            or evidence.webhook_id != webhook_id
            or not isinstance(url, str)
            or evidence.url != url
            or not isinstance(secret_env, str)
            or evidence.secret_env != secret_env
            or evidence.baseline_revision_id != baseline_revision_id
            or evidence.baseline_version != baseline_version
            or active is None
            or active.revision_id != evidence.baseline_revision_id
            or active.version != evidence.baseline_version
        ):
            raise ConfigurationVersionConflict(
                "the successful signature test does not match this form, operator, or "
                "current effective baseline; test the current form again before applying",
                durable_state="active_preserved",
                next_action=(
                    "run one signed test on the current form, then apply without changing "
                    "its address or secret reference"
                ),
            )

    def consume_evidence(self, evidence_id: object) -> None:
        if not isinstance(evidence_id, str):
            return
        with self._evidence_lock:
            self._evidence.pop(evidence_id, None)

    def _prune_evidence_locked(self, now: datetime) -> None:
        expired = [
            key for key, item in self._evidence.items() if now - item.created_at > self.EVIDENCE_TTL
        ]
        for key in expired:
            self._evidence.pop(key, None)

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
        revision: ManagedConfigurationRevision | None,
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
                        (
                            f"/api/configuration/revisions/{revision.revision_id}/objects/webhooks/"
                            f"{webhook_id}/test?version={revision.version}&digest={revision.digest}"
                            f"&category={category}"
                        )
                        if revision is not None
                        else (
                            f"/api/operations/notifications/webhooks/{webhook_id}/test"
                            f"?category={category}"
                        )
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
