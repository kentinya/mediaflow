"""Task 40.3 correction: real processes, durable pins and read-only probes."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from mediaflow.application.notification import NotificationPublisher, NotificationWorker
from mediaflow.domain.notification import NotificationEvent, NotificationEventType
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from tests.test_notifications import FakeTransport, webhook
from tests.test_resident_services import ResidentDeploymentFixture


class ResidentCorrectionTests(ResidentDeploymentFixture):
    def wait_for(self, predicate, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.1)
        self.fail("resident state did not converge")

    def start(self, service):
        log = self.root / f"{service}.log"
        stream = log.open("w+")
        self.addCleanup(stream.close)
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from mediaflow.cli import main; raise SystemExit(main())",
                "--config",
                str(self.config),
                service,
                "run",
                "--poll-seconds",
                "0.1",
            ],
            stdout=stream,
            stderr=stream,
        )

        def stop():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

        self.addCleanup(stop)

        def registered():
            self.assertIsNone(process.poll(), log.read_text())
            with SQLiteTaskRepository(self.database, read_only=True) as repo:
                return any(
                    row.service == service
                    and repo.get_resident_service_wait_state(
                        service, row.instance_id
                    ).waiting_reason
                    in {"unconfigured", "configuration_unavailable"}
                    for row in repo.list_resident_services()
                )

        self.wait_for(registered)
        return process

    def test_changed_recipient_does_not_claim_pending_or_retry_after_restart(self):
        now = datetime.now(UTC)
        original = webhook()
        self.publish_first_draft(self.empty_baseline())
        self.publish_successor(
            lambda document: document["notifications"].update(webhooks=[original.document()])
        )
        from mediaflow.final_cli import _resolve_resident_configuration

        environment = patch.dict(os.environ, {original.secret_env: "fake"})
        environment.start()
        self.addCleanup(environment.stop)

        def targets():
            return _resolve_resident_configuration(str(self.config)).resolve_webhook_targets()

        with SQLiteTaskRepository(self.database) as repo:
            for index, status in enumerate(("pending", "retry")):
                event = NotificationEvent(
                    str(index), NotificationEventType.JOB_COMPLETED, now, {"jobId": str(index)}
                )
                delivery = NotificationPublisher(repo, (original,)).publish(event)[0]
                if status == "retry":
                    worker = NotificationWorker(
                        repo, {"ops": (original, "fake")}, FakeTransport(503), clock=lambda: now
                    )
                    # First pending event also stays independent of the second.
                    worker.run_next()
        self.publish_successor(
            lambda document: document["notifications"]["webhooks"][0].update(
                url="https://replacement.invalid/hook"
            )
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
                lambda document: document["notifications"]["webhooks"][0].update(url=original.url)
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
