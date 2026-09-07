from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread
from unittest.mock import patch

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.notification import NotificationPublisher, NotificationWorker
from mediaflow.application.notification_delivery import NotificationDeliveryService
from mediaflow.domain.notification import (
    NotificationDeliveryStatus,
    NotificationEvent,
    NotificationEventType,
    WebhookDefinition,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
LEASE_SECONDS = 300.0


class FakeTransport:
    def __init__(self, *results) -> None:
        self.results = list(results or (204,))
        self.requests = []

    def send(self, request) -> int:
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def webhook(**changes) -> WebhookDefinition:
    values = {
        "webhook_id": "ops",
        "url": "https://example.invalid/hooks/mediaflow",
        "secret_env": "MEDIAFLOW_WEBHOOK_SECRET",
        "events": (NotificationEventType.JOB_COMPLETED,),
        "max_attempts": 3,
        "base_retry_seconds": 2,
        "max_retry_seconds": 10,
    }
    values.update(changes)
    return WebhookDefinition(**values)


def publish(repository, *, definition=None, event_id="event-1", occurred_at=NOW):
    event = NotificationEvent(
        event_id,
        NotificationEventType.JOB_COMPLETED,
        occurred_at,
        {"jobId": event_id, "title": "千与千寻"},
    )
    created = NotificationPublisher(repository, (definition or webhook(),)).publish(event)
    if not created:
        raise AssertionError(f"delivery for event {event_id!r} was not created")
    return created[0]


def run_worker(repository, definition=None, transport=None, *, clock=None):
    arguments = {} if clock is None else {"clock": clock}
    return NotificationWorker(
        repository,
        {"ops": (definition or webhook(), "secret")},
        transport or FakeTransport(204),
        **arguments,
    ).run_next()


def request(
    api,
    path,
    *,
    method="GET",
    body=b"",
    token="admin-token",
):
    statuses = []
    environment = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(body)),
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(body),
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token else "",
    }
    payload = b"".join(api(environment, lambda status, headers: statuses.append(status)))
    parsed = json.loads(payload) if payload else {}
    return int(statuses[0].split()[0]), parsed


class DeliveryManagementHarness:
    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.repository = SQLiteTaskRepository(self.directory / "runtime.sqlite3")
        admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        self.api = MediaFlowApi(self.repository, None, principals=(admin, viewer))

    def close(self):
        self.repository.close()


class ManagedWebhookHarness:
    """Harness with a managed Draft/Active Webhook used by the isolation test."""

    def __init__(self, directory: str, transport=None):
        self.directory = Path(directory)
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        runtime_database = str(self.directory / "runtime.sqlite3")
        document["persistence"]["databasePath"] = runtime_database
        self.runtime_database = runtime_database
        self.configuration_repository = SQLiteConfigurationRepository(
            self.directory / "configuration.sqlite3"
        )
        self.configuration = ManagedConfigurationService(
            self.configuration_repository,
            bootstrap_database_path=runtime_database,
        )
        self.draft = self.configuration.import_draft(document, actor="bootstrap")
        self.repository = SQLiteTaskRepository(self.directory / "runtime.sqlite3")
        admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        self.api = MediaFlowApi(
            self.repository,
            None,
            principals=(admin, viewer),
            configuration_service=self.configuration,
            bootstrap_document=document,
            webhook_transport=transport or FakeTransport(204),
        )

    def close(self):
        self.repository.close()
        self.configuration_repository.close()


def webhook_document(**changes):
    value = {
        "id": "ops-webhook",
        "url": "https://example.invalid/hooks/mediaflow",
        "secretEnv": "MEDIAFLOW_WEBHOOK_SECRET",
        "events": ["job.completed"],
        "enabled": True,
        "timeoutSeconds": 10,
        "maxAttempts": 5,
        "baseRetrySeconds": 5,
        "maxRetrySeconds": 300,
    }
    value.update(changes)
    return value


class NotificationDeliveryDetailTests(unittest.TestCase):
    def test_detail_projection_is_bounded_and_missing_id_is_404(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = DeliveryManagementHarness(directory)
            try:
                delivery = publish(harness.repository)
                status, detail = request(
                    harness.api,
                    f"/api/v1/notifications/{delivery.delivery_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(detail["deliveryId"], delivery.delivery_id)
                self.assertEqual(detail["webhookId"], "ops")
                self.assertEqual(detail["eventId"], "event-1")
                self.assertEqual(detail["eventType"], "job.completed")
                self.assertEqual(detail["status"], "pending")
                self.assertEqual(detail["attempts"], 0)
                self.assertEqual(detail["lease"], {"state": "not_leased"})
                self.assertIn("No outbound request", detail["knownEffects"])
                self.assertIn("nextAction", detail)
                self.assertEqual(detail["recovery"]["availableActions"], [])
                self.assertIn("pending automatic delivery", detail["recovery"]["reason"])
                # Delivery body, event data and any secret-like material are never
                # projected.
                encoded = json.dumps(detail)
                self.assertNotIn("body", detail)
                self.assertNotIn("千与千寻", encoded)
                self.assertNotIn("secret", encoded.lower())
                self.assertNotIn("authorization", encoded.lower())

                # List and detail use the same deterministic delivery identity.
                status, listing = request(
                    harness.api,
                    "/api/v1/notifications",
                )
                self.assertEqual(status, 200)
                self.assertEqual(len(listing["items"]), 1)
                self.assertEqual(listing["items"][0]["deliveryId"], delivery.delivery_id)
                self.assertEqual(listing["items"][0]["deliveryId"], detail["deliveryId"])

                # The same bounded projection is available to the read authority.
                status, viewed = request(
                    harness.api,
                    f"/api/v1/notifications/{delivery.delivery_id}",
                    token="viewer-token",
                )
                self.assertEqual(status, 200)
                self.assertEqual(viewed["deliveryId"], delivery.delivery_id)

                for missing in ("missing-delivery", "../missing", "x" * 400):
                    status, error = request(
                        harness.api,
                        f"/api/v1/notifications/{missing}",
                    )
                    self.assertEqual(status, 404, missing)
                    self.assertEqual(error["error"]["code"], "not_found")
            finally:
                harness.close()

    def test_permission_denial_for_recovery_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = DeliveryManagementHarness(directory)
            try:
                dead = publish(harness.repository, event_id="dead-1")
                run_worker(
                    harness.repository,
                    webhook(max_attempts=1),
                    FakeTransport(400),
                )
                stale = publish(harness.repository, event_id="stale-1")
                harness.repository.claim_next_delivery(
                    datetime.now(UTC) - timedelta(hours=2),
                    datetime.now(UTC) - timedelta(hours=3),
                )
                for delivery_id, action in (
                    (dead.delivery_id, "requeue"),
                    (stale.delivery_id, "resolve-stale"),
                ):
                    with self.subTest(action=action):
                        status, denied = request(
                            harness.api,
                            f"/api/v1/notifications/{delivery_id}/{action}",
                            method="POST",
                            body=json.dumps(
                                {
                                    "expectedStatus": "dead-letter"
                                    if action == "requeue"
                                    else "delivering",
                                    "expectedUpdatedAt": NOW.isoformat(),
                                }
                            ).encode(),
                            token="viewer-token",
                        )
                        self.assertEqual(status, 403)
                        self.assertEqual(denied["error"]["code"], "forbidden")
                        self.assertTrue(
                            any(
                                item.action == "permission"
                                and item.outcome == "denied"
                                and item.http_status == 403
                                for item in harness.repository.list_security_audit(limit=100)
                            )
                        )
            finally:
                harness.close()

    def test_all_durable_statuses_are_visible_with_lease_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                delivered = publish(repository, event_id="delivered-1")
                run_worker(repository, webhook(max_attempts=3), FakeTransport(204))
                retry = publish(repository, event_id="retry-1")
                run_worker(repository, webhook(max_attempts=3), FakeTransport(429))
                dead = publish(repository, event_id="dead-1")
                run_worker(repository, webhook(max_attempts=3), FakeTransport(400))
                active = publish(
                    repository,
                    event_id="active-1",
                    occurred_at=NOW - timedelta(hours=3),
                )
                repository.claim_next_delivery(
                    NOW - timedelta(seconds=60), NOW - timedelta(minutes=10)
                )
                stale = publish(
                    repository,
                    event_id="stale-1",
                    occurred_at=NOW - timedelta(hours=3),
                )
                repository.claim_next_delivery(NOW - timedelta(hours=2), NOW - timedelta(hours=3))
                service = NotificationDeliveryService(
                    repository,
                    clock=lambda: NOW,
                )
                with self.subTest(state="delivered"):
                    document = service.detail(delivered.delivery_id, lease_seconds=LEASE_SECONDS)
                    self.assertEqual(document["status"], "delivered")
                    self.assertEqual(document["lease"]["state"], "not_leased")
                    self.assertTrue(document["retrySafe"])
                    self.assertEqual(document["nextAction"], "No action required.")
                    self.assertEqual(document["recovery"]["availableActions"], [])
                with self.subTest(state="retry"):
                    document = service.detail(retry.delivery_id, lease_seconds=LEASE_SECONDS)
                    self.assertEqual(document["status"], "retry")
                    self.assertIn("automatic retry", document["nextAction"])
                    self.assertEqual(document["recovery"]["availableActions"], [])
                with self.subTest(state="dead-letter"):
                    document = service.detail(dead.delivery_id, lease_seconds=LEASE_SECONDS)
                    self.assertEqual(document["status"], "dead-letter")
                    self.assertEqual(
                        document["recovery"]["availableActions"], ["requeue-dead-letter"]
                    )
                    action = document["recovery"]["actions"][0]
                    self.assertIn("at-least-once", action["duplicateImplication"])
                    self.assertIn("requeue", action["nextAction"])
                with self.subTest(state="delivering-active-lease"):
                    document = service.detail(active.delivery_id, lease_seconds=LEASE_SECONDS)
                    self.assertEqual(document["status"], "delivering")
                    self.assertEqual(document["lease"]["state"], "active")
                    self.assertEqual(document["lease"]["leaseSeconds"], LEASE_SECONDS)
                    self.assertEqual(document["recovery"]["availableActions"], [])
                    self.assertIn("unexpired lease", document["recovery"]["reason"])
                with self.subTest(state="delivering-stale-lease"):
                    document = service.detail(stale.delivery_id, lease_seconds=LEASE_SECONDS)
                    self.assertEqual(document["status"], "delivering")
                    self.assertEqual(document["lease"]["state"], "expired")
                    self.assertEqual(document["recovery"]["availableActions"], ["resolve-stale"])
                    action = document["recovery"]["actions"][0]
                    self.assertIn("at-least-once", action["duplicateImplication"])
                    self.assertIn("resolve", action["nextAction"])
                    self.assertTrue(document["retrySafe"])
                    self.assertIn("expired", document["knownEffects"])


class NotificationDeliveryRecoveryTests(unittest.TestCase):
    def test_dead_letter_requeue_succeeds_and_ineligible_or_stale_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = DeliveryManagementHarness(directory)
            try:
                dead = publish(harness.repository, event_id="dead-1")
                run_worker(harness.repository, webhook(max_attempts=1), FakeTransport(400))
                status, detail = request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(detail["status"], "dead-letter")

                before = harness.repository.list_deliveries()
                status, requeued = request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedStatus": detail["status"],
                            "expectedUpdatedAt": detail["updatedAt"],
                        }
                    ).encode(),
                )
                self.assertEqual(status, 200)
                self.assertEqual(requeued["action"], "requeue-dead-letter")
                self.assertEqual(requeued["outcome"], "success")
                self.assertEqual(requeued["deliveryId"], dead.delivery_id)
                self.assertEqual(requeued["previousStatus"], "dead-letter")
                self.assertEqual(requeued["status"], "pending")
                self.assertEqual(requeued["attempts"], 0)
                self.assertIn("stable delivery identity", requeued["atLeastOnce"])
                after = harness.repository.list_deliveries()
                self.assertEqual(len(after), len(before))
                self.assertEqual(
                    {item.delivery_id for item in after},
                    {item.delivery_id for item in before},
                )
                self.assertEqual(
                    harness.repository.get_delivery(dead.delivery_id).status,
                    NotificationDeliveryStatus.PENDING,
                )

                # A second requeue with the now-stale observed state fails closed.
                status, conflict = request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedStatus": "dead-letter",
                            "expectedUpdatedAt": detail["updatedAt"],
                        }
                    ).encode(),
                )
                self.assertEqual(status, 409)
                self.assertEqual(conflict["error"]["code"], "notification_delivery_conflict")
                self.assertEqual(
                    conflict["error"]["details"]["durableState"],
                    "delivery_preserved_no_change",
                )
                self.assertEqual(conflict["error"]["details"]["delivery"]["status"], "pending")
                self.assertTrue(
                    any(
                        item.action == "notification-recovery"
                        and item.outcome == "denied"
                        and item.http_status == 409
                        for item in harness.repository.list_security_audit(limit=100)
                    )
                )

                # Requeue of an already-delivered delivery is ineligible.
                delivered = publish(harness.repository, event_id="delivered-1")
                run_worker(harness.repository, webhook(max_attempts=3), FakeTransport(204))
                status, detail2 = request(
                    harness.api,
                    f"/api/v1/notifications/{delivered.delivery_id}",
                )
                status, ineligible = request(
                    harness.api,
                    f"/api/v1/notifications/{delivered.delivery_id}/requeue",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedStatus": detail2["status"],
                            "expectedUpdatedAt": detail2["updatedAt"],
                        }
                    ).encode(),
                )
                self.assertEqual(status, 409)
                self.assertEqual(ineligible["error"]["code"], "notification_delivery_conflict")
                self.assertEqual(ineligible["error"]["details"]["delivery"]["status"], "delivered")
            finally:
                harness.close()

    def test_stale_resolve_succeeds_and_unexpired_or_other_state_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = DeliveryManagementHarness(directory)
            try:
                stale = publish(harness.repository, event_id="stale-1")
                harness.repository.claim_next_delivery(
                    datetime.now(UTC) - timedelta(hours=2),
                    datetime.now(UTC) - timedelta(hours=3),
                )
                status, detail = request(
                    harness.api,
                    f"/api/v1/notifications/{stale.delivery_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(detail["lease"]["state"], "expired")
                self.assertEqual(detail["recovery"]["availableActions"], ["resolve-stale"])
                attempts_before = detail["attempts"]
                self.assertGreaterEqual(attempts_before, 1)

                status, resolved = request(
                    harness.api,
                    f"/api/v1/notifications/{stale.delivery_id}/resolve-stale",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedStatus": detail["status"],
                            "expectedUpdatedAt": detail["updatedAt"],
                        }
                    ).encode(),
                )
                self.assertEqual(status, 200)
                self.assertEqual(resolved["action"], "resolve-stale")
                self.assertEqual(resolved["outcome"], "success")
                self.assertEqual(resolved["status"], "pending")
                self.assertEqual(resolved["previousStatus"], "delivering")
                # Attempts are deliberately preserved, never silently reset.
                self.assertEqual(resolved["attempts"], attempts_before)
                self.assertIn("more than once", resolved["duplicateImplication"])
                current = harness.repository.get_delivery(stale.delivery_id)
                self.assertEqual(current.status, NotificationDeliveryStatus.PENDING)
                self.assertEqual(current.attempts, attempts_before)

                # An unexpired (active) delivering lease is not eligible.
                active = publish(harness.repository, event_id="active-1")
                harness.repository.claim_next_delivery(
                    datetime.now(UTC) - timedelta(seconds=60),
                    datetime.now(UTC) - timedelta(minutes=10),
                )
                status, detail2 = request(
                    harness.api,
                    f"/api/v1/notifications/{active.delivery_id}",
                )
                self.assertEqual(detail2["lease"]["state"], "active")
                status, unexpired = request(
                    harness.api,
                    f"/api/v1/notifications/{active.delivery_id}/resolve-stale",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedStatus": detail2["status"],
                            "expectedUpdatedAt": detail2["updatedAt"],
                        }
                    ).encode(),
                )
                self.assertEqual(status, 409)
                self.assertEqual(
                    unexpired["error"]["details"]["durableState"],
                    "delivery_preserved_no_change",
                )

                # A delivered delivery cannot be resolved as stale.
                delivered = publish(harness.repository, event_id="delivered-1")
                run_worker(harness.repository, webhook(max_attempts=3), FakeTransport(204))
                status, detail3 = request(
                    harness.api,
                    f"/api/v1/notifications/{delivered.delivery_id}",
                )
                status, not_delivering = request(
                    harness.api,
                    f"/api/v1/notifications/{delivered.delivery_id}/resolve-stale",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedStatus": detail3["status"],
                            "expectedUpdatedAt": detail3["updatedAt"],
                        }
                    ).encode(),
                )
                self.assertEqual(status, 409)
            finally:
                harness.close()

    def test_concurrent_recovery_has_one_winner_and_preserves_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                first = publish(
                    repository,
                    event_id="first-1",
                    occurred_at=NOW - timedelta(hours=3),
                )
                second = publish(
                    repository,
                    event_id="second-1",
                    occurred_at=NOW - timedelta(hours=3),
                )
                repository.claim_next_delivery(NOW - timedelta(hours=2), NOW - timedelta(hours=3))
                repository.claim_next_delivery(NOW - timedelta(hours=2), NOW - timedelta(hours=3))
                stale_token = repository.get_delivery(first.delivery_id).updated_at.isoformat()
                sibling = repository.get_delivery(second.delivery_id)
            barrier = Barrier(2)
            outcomes = []

            def resolve(which: str) -> None:
                with SQLiteTaskRepository(database) as repository:
                    service = NotificationDeliveryService(repository, clock=lambda: NOW)
                    barrier.wait()
                    try:
                        service.resolve_stale(
                            which,
                            expected_status="delivering",
                            expected_updated_at=stale_token,
                            lease_seconds=LEASE_SECONDS,
                            actor="operator",
                        )
                        outcomes.append("ok")
                    except Exception:
                        outcomes.append("conflict")

            threads = [
                Thread(target=resolve, args=(first.delivery_id,)),
                Thread(target=resolve, args=(first.delivery_id,)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sorted(outcomes), ["conflict", "ok"])
            with SQLiteTaskRepository(database) as repository:
                rows = repository.list_deliveries()
                self.assertEqual(len(rows), 2)
                by_id = {item.delivery_id: item for item in rows}
                self.assertEqual(
                    by_id[first.delivery_id].status, NotificationDeliveryStatus.PENDING
                )
                # The unrelated sibling delivery is untouched.
                self.assertEqual(by_id[second.delivery_id].status, sibling.status)
                self.assertEqual(by_id[second.delivery_id].attempts, sibling.attempts)
                self.assertEqual(by_id[second.delivery_id].updated_at, sibling.updated_at)

    def test_recovery_audit_redaction_and_no_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = DeliveryManagementHarness(directory)
            try:
                dead = publish(harness.repository, event_id="dead-1")
                run_worker(harness.repository, webhook(max_attempts=1), FakeTransport(400))
                sibling = publish(harness.repository, event_id="sibling-1")
                jobs_before = harness.repository.list_jobs()
                tasks_before = harness.repository.list_tasks()
                schedules_before = harness.repository.list_schedule_states()
                deliveries_before = harness.repository.list_deliveries()
                audits_before = harness.repository.list_security_audit(limit=500)
                status, detail = request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}",
                )
                self.assertEqual(status, 200)
                status, result = request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedStatus": detail["status"],
                            "expectedUpdatedAt": detail["updatedAt"],
                        }
                    ).encode(),
                )
                self.assertEqual(status, 200)
                encoded = json.dumps(result)
                self.assertNotIn("千与千寻", encoded)
                self.assertNotIn("body", result.get("delivery", {}))
                self.assertNotIn("secret", encoded.lower())
                deliveries_after = harness.repository.list_deliveries()
                self.assertEqual(len(deliveries_after), len(deliveries_before))
                self.assertEqual(
                    {item.delivery_id for item in deliveries_after},
                    {item.delivery_id for item in deliveries_before},
                )
                self.assertEqual(harness.repository.list_jobs(), jobs_before)
                self.assertEqual(harness.repository.list_tasks(), tasks_before)
                self.assertEqual(harness.repository.list_schedule_states(), schedules_before)
                updated = harness.repository.get_delivery(dead.delivery_id)
                self.assertEqual(updated.status, NotificationDeliveryStatus.PENDING)
                # The sibling delivery is untouched (still pending, never claimed).
                self.assertEqual(
                    harness.repository.get_delivery(sibling.delivery_id).status,
                    NotificationDeliveryStatus.PENDING,
                )
                audits = harness.repository.list_security_audit(limit=500)
                self.assertGreater(len(audits), len(audits_before))
                self.assertTrue(
                    any(
                        item.action == "notification-recovery"
                        and item.outcome == "success"
                        and item.route.startswith(
                            f"/api/v1/notifications/{dead.delivery_id}/requeue"
                        )
                        for item in audits
                    )
                )
            finally:
                harness.close()


class NotificationDeliveryCompatibilityTests(unittest.TestCase):
    def test_worker_retry_and_claim_fencing_still_work_after_manual_recovery(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = DeliveryManagementHarness(directory)
            try:
                # Dead-letter then operator-requeue, then the Worker delivers.
                dead = publish(harness.repository, event_id="dead-1")
                transport = FakeTransport(400)
                run_worker(harness.repository, webhook(max_attempts=1), transport)
                status, detail = request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}",
                )
                self.assertEqual(detail["status"], "dead-letter")
                status, requeued = request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedStatus": detail["status"],
                            "expectedUpdatedAt": detail["updatedAt"],
                        }
                    ).encode(),
                )
                self.assertEqual(status, 200)
                self.assertEqual(requeued["status"], "pending")
                worker_transport = FakeTransport(204)
                delivered = NotificationWorker(
                    harness.repository,
                    {"ops": (webhook(max_attempts=1), "secret")},
                    worker_transport,
                    clock=lambda: datetime.now(UTC) + timedelta(minutes=5),
                ).run_next()
                self.assertEqual(delivered.status, NotificationDeliveryStatus.DELIVERED)
                self.assertEqual(delivered.delivery_id, dead.delivery_id)
                self.assertEqual(len(harness.repository.list_deliveries()), 1)

                # Stale then operator-resolve, then the Worker reclaims and delivers.
                stale = publish(
                    harness.repository,
                    event_id="stale-1",
                    occurred_at=NOW - timedelta(hours=3),
                )
                harness.repository.claim_next_delivery(
                    NOW - timedelta(hours=2), NOW - timedelta(hours=3)
                )
                status, detail2 = request(
                    harness.api,
                    f"/api/v1/notifications/{stale.delivery_id}",
                )
                self.assertEqual(detail2["lease"]["state"], "expired")
                status, resolved = request(
                    harness.api,
                    f"/api/v1/notifications/{stale.delivery_id}/resolve-stale",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedStatus": detail2["status"],
                            "expectedUpdatedAt": detail2["updatedAt"],
                        }
                    ).encode(),
                )
                self.assertEqual(status, 200)
                reclaimed = NotificationWorker(
                    harness.repository,
                    {"ops": (webhook(max_attempts=5), "secret")},
                    FakeTransport(204),
                    clock=lambda: datetime.now(UTC) + timedelta(minutes=5),
                ).run_next()
                self.assertEqual(reclaimed.delivery_id, stale.delivery_id)
                self.assertEqual(reclaimed.status, NotificationDeliveryStatus.DELIVERED)
                # No second row is ever created by manual or worker recovery.
                self.assertEqual(len(harness.repository.list_deliveries()), 2)
            finally:
                harness.close()

    def test_definition_test_isolation_remains_with_delivery_recovery_surface(
        self,
    ) -> None:
        transport = FakeTransport(204)
        with tempfile.TemporaryDirectory() as directory:
            harness = ManagedWebhookHarness(directory, transport=transport)
            try:
                revision_id = harness.draft.revision_id
                status, created = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps({"object": webhook_document(), "expectedVersion": 1}).encode(),
                )
                self.assertEqual(status, 200)
                validated = harness.configuration.validate(revision_id, actor="bootstrap")
                active = harness.configuration.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="bootstrap",
                )
                # A durable delivery exists for the same Webhook id.
                delivery = publish(
                    harness.repository,
                    definition=webhook(webhook_id="ops-webhook"),
                    event_id="event-1",
                )
                deliveries_before = harness.repository.list_deliveries()
                with patch.dict(os.environ, {"MEDIAFLOW_WEBHOOK_SECRET": "top-secret-value"}):
                    status, test_result = request(
                        harness.api,
                        f"/api/v1/configuration/revisions/{active.revision_id}"
                        "/objects/webhooks/ops-webhook/test",
                        method="POST",
                        body=json.dumps(
                            {
                                "expectedVersion": active.version,
                                "expectedDigest": active.digest,
                            }
                        ).encode(),
                    )
                self.assertEqual(status, 200)
                self.assertEqual(test_result["outcome"], "success")
                # The explicit definition test never created or altered a delivery.
                self.assertEqual(harness.repository.list_deliveries(), deliveries_before)
                self.assertEqual(len(harness.repository.list_deliveries()), 1)
                # The delivery detail/recovery surface is still reachable.
                status, detail = request(
                    harness.api,
                    f"/api/v1/notifications/{delivery.delivery_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(detail["deliveryId"], delivery.delivery_id)
            finally:
                harness.close()

    def test_web_uses_the_same_detail_and_exact_payload_recovery_endpoints(self) -> None:
        script = APP_JS.decode("utf-8")
        self.assertIn("/api/v1/notifications?limit=100&status=", script)
        self.assertIn("renderDeliveryDetail(items[index].deliveryId, status)", script)
        self.assertIn("Inspect delivery", script)
        self.assertIn("/api/v1/notifications/${encodeURIComponent(deliveryId)}", script)
        self.assertIn("expectedStatus: detail.status", script)
        self.assertIn("expectedUpdatedAt: detail.updatedAt", script)
        self.assertIn("requeue-dead-letter", script)
        self.assertIn("resolve-stale", script)
        self.assertIn("Requeue dead-letter delivery", script)
        self.assertIn("Resolve stale delivery", script)
        self.assertIn("Duplicate implication", script)
        self.assertIn("duplicateImplication", script)
        self.assertIn("expectedStatus: detail.status", script)
        self.assertIn("Back to notifications", script)
        self.assertIn("Opening a delivery shows its durable state", script)
        self.assertIn("never requeues, never resolves and never creates a delivery", script)


if __name__ == "__main__":
    unittest.main()
