from __future__ import annotations

import copy
import hashlib
import hmac
import io
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread
from unittest.mock import patch

from mediaflow.application.automation import (
    AutomationJobService,
    AutomationWorker,
    IntervalScheduler,
)
from mediaflow.application.notification import NotificationPublisher, NotificationWorker
from mediaflow.domain.automation import IntervalSchedule
from mediaflow.domain.notification import (
    NotificationDeliveryStatus,
    NotificationEvent,
    NotificationEventType,
    WebhookDefinition,
)
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


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


def publish(repository, definition=None):
    event = NotificationEvent(
        "event-1",
        NotificationEventType.JOB_COMPLETED,
        NOW,
        {"title": "千与千寻", "jobId": "job-1"},
    )
    return NotificationPublisher(repository, (definition or webhook(),)).publish(event)


class NotificationTests(unittest.TestCase):
    def test_publisher_is_durable_canonical_subscribed_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                first = publish(repository)
                second = publish(repository)
                self.assertEqual(len(first), 1)
                self.assertEqual(second, ())
                delivery = repository.list_deliveries()[0]
                self.assertEqual(delivery.status, NotificationDeliveryStatus.PENDING)
                self.assertEqual(json.loads(delivery.body)["data"]["title"], "千与千寻")
                self.assertNotIn(" ", delivery.body)

    def test_disabled_and_unsubscribed_webhooks_create_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                self.assertEqual(publish(repository, webhook(enabled=False)), ())
                self.assertEqual(
                    publish(
                        repository,
                        webhook(events=(NotificationEventType.JOB_FAILED,)),
                    ),
                    (),
                )

    def test_signature_covers_timestamp_dot_exact_body(self) -> None:
        transport = FakeTransport(204)
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                publish(repository)
                result = NotificationWorker(
                    repository, {"ops": (webhook(), "secret")}, transport, clock=lambda: NOW
                ).run_next()
                self.assertEqual(result.status, NotificationDeliveryStatus.DELIVERED)
                request = transport.requests[0]
                timestamp = request.headers["X-MediaFlow-Timestamp"]
                expected = hmac.new(
                    b"secret", timestamp.encode() + b"." + request.body, hashlib.sha256
                ).hexdigest()
                self.assertEqual(request.headers["X-MediaFlow-Signature"], f"sha256={expected}")

    def test_retry_dead_letter_and_explicit_requeue(self) -> None:
        transport = FakeTransport(429, 503, 400)
        clock = [NOW]
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                publish(repository)
                worker = NotificationWorker(
                    repository,
                    {"ops": (webhook(), "secret")},
                    transport,
                    clock=lambda: clock[0],
                )
                first = worker.run_next()
                self.assertEqual(first.status, NotificationDeliveryStatus.RETRY)
                self.assertEqual(first.next_attempt_at, NOW + timedelta(seconds=2))
                clock[0] = first.next_attempt_at
                second = worker.run_next()
                self.assertEqual(second.next_attempt_at, clock[0] + timedelta(seconds=4))
                clock[0] = second.next_attempt_at
                dead = worker.run_next()
                self.assertEqual(dead.status, NotificationDeliveryStatus.DEAD_LETTER)
                requeued = repository.requeue_dead_letter(dead.delivery_id, clock[0])
                self.assertEqual(requeued.status, NotificationDeliveryStatus.PENDING)
                self.assertEqual(requeued.attempts, 0)

    def test_transport_error_is_redacted_and_bounded(self) -> None:
        transport = FakeTransport(RuntimeError("token=super-secret"))
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                publish(repository, webhook(max_attempts=1))
                result = NotificationWorker(
                    repository,
                    {"ops": (webhook(max_attempts=1), "secret")},
                    transport,
                    clock=lambda: NOW,
                ).run_next()
                self.assertEqual(result.status, NotificationDeliveryStatus.DEAD_LETTER)
                self.assertEqual(result.failure_category, "transport")
                self.assertNotIn("super-secret", repr(result))

    def test_claim_is_atomic_between_repository_connections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                publish(repository)
            barrier = Barrier(2)
            results = []

            def claim() -> None:
                with SQLiteTaskRepository(database) as repository:
                    barrier.wait()
                    results.append(repository.claim_next_delivery(NOW, NOW - timedelta(minutes=5)))

            threads = [Thread(target=claim), Thread(target=claim)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sum(item is not None for item in results), 1)

    def test_fresh_delivery_lease_is_not_reclaimed_but_expired_is(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                original = publish(repository)[0]
                claimed = repository.claim_next_delivery(NOW, NOW - timedelta(minutes=5))
                self.assertEqual(claimed.attempts, 1)
                self.assertIsNone(
                    repository.claim_next_delivery(
                        NOW + timedelta(seconds=299), NOW - timedelta(seconds=1)
                    )
                )
                self.assertEqual(repository.list_stale_deliveries(NOW - timedelta(seconds=1)), ())
                self.assertEqual(
                    repository.list_stale_deliveries(NOW + timedelta(seconds=1)), (claimed,)
                )
                reclaimed = repository.claim_next_delivery(
                    NOW + timedelta(seconds=301), NOW + timedelta(seconds=1)
                )
                self.assertEqual(reclaimed.delivery_id, original.delivery_id)
                self.assertEqual(reclaimed.event_id, original.event_id)
                self.assertEqual(reclaimed.body, original.body)
                self.assertEqual(reclaimed.attempts, 2)

    def test_restart_worker_reclaims_expired_and_dead_letters_exhausted_attempt(self) -> None:
        clock = [NOW]
        definition = webhook(max_attempts=1)
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                publish(repository, definition)
                repository.claim_next_delivery(NOW, NOW - timedelta(seconds=300))
            clock[0] += timedelta(seconds=301)
            with SQLiteTaskRepository(database) as restarted:
                result = NotificationWorker(
                    restarted,
                    {"ops": (definition, "secret")},
                    FakeTransport(503),
                    delivery_lease_seconds=300,
                    clock=lambda: clock[0],
                ).run_next()
                self.assertEqual(result.status, NotificationDeliveryStatus.DEAD_LETTER)
                self.assertEqual(result.attempts, 2)

    def test_concurrent_workers_reclaim_one_expired_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                publish(repository)
                repository.claim_next_delivery(NOW, NOW - timedelta(minutes=5))
            barrier = Barrier(2)
            results = []

            def reclaim() -> None:
                with SQLiteTaskRepository(database) as repository:
                    barrier.wait()
                    results.append(
                        repository.claim_next_delivery(
                            NOW + timedelta(minutes=6), NOW + timedelta(minutes=1)
                        )
                    )

            threads = [Thread(target=reclaim), Thread(target=reclaim)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sum(item is not None for item in results), 1)

    def test_configuration_validation_and_secret_resolution(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["notifications"] = {
            "pollSeconds": 3,
            "webhooks": [
                {
                    "id": "ops",
                    "url": "https://example.invalid/hook",
                    "secretEnv": "MEDIAFLOW_WEBHOOK_SECRET",
                    "events": ["job.completed", "job.failed"],
                }
            ],
        }
        loaded = load_runtime_configuration(copy.deepcopy(document))
        self.assertEqual(loaded.notification_poll_seconds, 3)
        self.assertEqual(loaded.notification_delivery_lease_seconds, 300)
        with self.assertRaisesRegex(ValueError, "MEDIAFLOW_WEBHOOK_SECRET"):
            loaded.resolve_webhook_targets()
        with patch.dict(os.environ, {"MEDIAFLOW_WEBHOOK_SECRET": "top-secret"}):
            self.assertEqual(loaded.resolve_webhook_targets()["ops"][1], "top-secret")
        for invalid in (
            "http://example.invalid/hook",
            "https://user:pass@example.invalid/hook",
            "https://example.invalid/hook#fragment",
        ):
            value = copy.deepcopy(document)
            value["notifications"]["webhooks"][0]["url"] = invalid
            with self.subTest(url=invalid), self.assertRaises(ValueError):
                load_runtime_configuration(value)
        literal = copy.deepcopy(document)
        literal["notifications"]["webhooks"][0]["secret"] = "forbidden"
        with self.assertRaises(ValueError):
            load_runtime_configuration(literal)
        custom = copy.deepcopy(document)
        custom["notifications"]["deliveryLeaseSeconds"] = 45
        self.assertEqual(load_runtime_configuration(custom).notification_delivery_lease_seconds, 45)
        invalid_lease = copy.deepcopy(document)
        invalid_lease["notifications"]["deliveryLeaseSeconds"] = 0
        with self.assertRaises(ValueError):
            load_runtime_configuration(invalid_lease)

    def test_cli_and_api_visibility_omit_body_and_secret(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            document["persistence"] = {"databasePath": str(database)}
            config = Path(directory, "config.json")
            config.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                publish(repository)
                api = MediaFlowApi(repository, "api-secret")
                statuses = []
                environ = {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": "/api/v1/notifications",
                    "CONTENT_LENGTH": "0",
                    "HTTP_AUTHORIZATION": "Bearer api-secret",
                    "wsgi.input": io.BytesIO(),
                }
                body = b"".join(api(environ, lambda value, headers: statuses.append(value)))
                self.assertEqual(statuses[0].split()[0], "200")
                self.assertNotIn(b'"body"', body)
                api_item = json.loads(body)["items"][0]
                self.assertIn("updatedAt", api_item)
                self.assertEqual(api_item["attempts"], 0)
            output, error = io.StringIO(), io.StringIO()
            code = final_main(
                ["--config", str(config), "notifications", "list"],
                stdout=output,
                stderr=error,
            )
            self.assertEqual(code, 0, error.getvalue())
            self.assertNotIn("千与千寻", output.getvalue())
            self.assertNotIn("secret", output.getvalue())
            self.assertIn("updated=", output.getvalue())

    def test_schema_six_migrates_to_notification_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            connection = sqlite3.connect(database)
            connection.executescript(
                "CREATE TABLE schema_version "
                "(component TEXT PRIMARY KEY, version INTEGER NOT NULL);"
                "INSERT INTO schema_version VALUES ('runtime', 6);"
            )
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, 16)
                self.assertEqual(repository.list_deliveries(), ())

    def test_terminal_job_and_schedule_events_enter_outbox(self) -> None:
        definitions = (
            webhook(
                events=(
                    NotificationEventType.JOB_COMPLETED,
                    NotificationEventType.SCHEDULE_EMITTED,
                )
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                publisher = NotificationPublisher(repository, definitions)
                AutomationJobService(repository).submit("scan")
                finished = AutomationWorker(
                    repository, lambda job, cancelled: "task-1", publisher
                ).run_next()
                self.assertEqual(finished.status.value, "completed")
                schedule = IntervalSchedule("hourly", "preview", 3600)
                self.assertEqual(
                    len(IntervalScheduler(repository, (schedule,), publisher).tick(NOW)), 1
                )
                self.assertEqual(
                    {item.event_type for item in repository.list_deliveries()},
                    {
                        NotificationEventType.JOB_COMPLETED,
                        NotificationEventType.SCHEDULE_EMITTED,
                    },
                )


if __name__ == "__main__":
    unittest.main()
