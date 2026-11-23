"""Task 40.3 correction: durable pins and read-only probes."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from mediaflow.application.notification import NotificationPublisher, NotificationWorker
from mediaflow.domain.notification import NotificationEvent, NotificationEventType
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from tests.test_notifications import FakeTransport, webhook
from tests.test_resident_services import ResidentDeploymentFixture


class ResidentCorrectionTests(ResidentDeploymentFixture):
    def test_changed_recipient_does_not_claim_pending_or_retry_after_restart(self):
        now = datetime.now(UTC)
        original = webhook()
        self.publish_first_draft(self.empty_baseline())
        self.publish_successor(
            lambda document: document.__setitem__("webhooks", [original.document()])
        )
        from mediaflow.resident_entry import _resolve_resident_configuration

        environment = patch.dict(os.environ, {original.secret_env: "fake"})
        environment.start()
        self.addCleanup(environment.stop)

        def targets():
            return _resolve_resident_configuration(str(self.config)).resolve_webhook_targets()

        with SQLiteTaskRepository(self.database) as repo:
            for index, status in enumerate(("pending", "retry")):
                event = NotificationEvent(
                    str(index), NotificationEventType.TASK_COMPLETED, now, {"jobId": str(index)}
                )
                delivery = NotificationPublisher(repo, (original,)).publish(event)[0]
                if status == "retry":
                    worker = NotificationWorker(
                        repo, {"ops": (original, "fake")}, FakeTransport(503), clock=lambda: now
                    )
                    # First pending event also stays independent of the second.
                    worker.run_next()
        self.publish_successor(
            lambda document: document["webhooks"][0].update(url="https://replacement.invalid/hook")
        )
        with SQLiteTaskRepository(self.database) as repo:
            before = repo.list_deliveries()
            transport = FakeTransport()
            worker = NotificationWorker(
                repo,
                targets,
                transport,
                clock=lambda: now + timedelta(hours=1),
            )
            self.assertIsNone(worker.run_next())
            self.assertEqual(repo.list_deliveries(), before)
            self.assertEqual(transport.requests, [])
            self.publish_successor(
                lambda document: document["webhooks"][0].update(url=original.url)
            )
            restored = NotificationWorker(
                repo,
                targets,
                FakeTransport(),
                clock=lambda: now + timedelta(hours=1),
            )
            self.assertEqual(restored.run_next().status.value, "delivered")
            self.assertEqual(
                repo.get_delivery(delivery.delivery_id).target_digest, original.target_digest
            )
