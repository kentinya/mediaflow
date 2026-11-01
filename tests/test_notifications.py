from __future__ import annotations

import copy
import hashlib
import hmac
import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread
from unittest.mock import patch

import tests.test_v2_automation_run_once as automation_run_once_fixture
from mediaflow.application.automation import IntervalScheduler
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.notification import NotificationPublisher, NotificationWorker
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.automation import IntervalSchedule
from mediaflow.domain.metadata import MediaCandidate, MediaType, ProviderCapabilities
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
from tests.test_execution_authorization import request as remote_request
from tests.test_execution_authorization import service as authorization_service

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
        "events": (NotificationEventType.TASK_COMPLETED,),
        "max_attempts": 3,
        "base_retry_seconds": 2,
        "max_retry_seconds": 10,
    }
    values.update(changes)
    return WebhookDefinition(**values)


def publish(repository, definition=None):
    event = NotificationEvent(
        "event-1",
        NotificationEventType.TASK_COMPLETED,
        NOW,
        {"title": "千与千寻", "taskId": "task-1"},
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
                        webhook(events=(NotificationEventType.TASK_FAILED,)),
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
                    "events": ["task.completed", "task.failed"],
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

    def test_scheduler_emission_enters_outbox_for_the_admitted_task(self) -> None:
        """A real due occurrence publishes its schedule event for one Task."""

        definitions = (webhook(events=(NotificationEventType.SCHEDULE_EMITTED,)),)
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                schedule = IntervalSchedule("hourly", "organize", 3600)
                publisher = NotificationPublisher(repository, definitions)
                (task,) = IntervalScheduler(repository, (schedule,), publisher).tick(NOW)
                (delivery,) = repository.list_deliveries()
                self.assertEqual(delivery.event_type, NotificationEventType.SCHEDULE_EMITTED)
                self.assertEqual(
                    json.loads(delivery.body)["data"],
                    {
                        "command": "organize",
                        "scheduleId": "hourly",
                        "taskId": task.task_id,
                    },
                )
                self.assertIsNotNone(
                    repository.get_task_scheduling(task.task_id),
                    "the schedule event must name the one admitted organizing Task",
                )


class TerminalTaskNotificationTests(unittest.TestCase):
    """The supported organizer journey ends in the durable notification outbox.

    Each case starts at a real entrance (remote ``POST /api/v1/tasks`` or the
    Scheduler), advances the durable Task through the production CLI Worker or
    the supported control command, and reads the real outbox.  No test calls the
    publisher to fake the terminal publication.
    """

    WEBHOOK_EVENTS = ["job.completed", "job.failed", "job.cancelled"]

    def setUp(self) -> None:
        self.fixture = automation_run_once_fixture.RunOnceApiTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.media("Movies/One.2001.mkv")
        self.document = self.fixture.document(definitions=[])
        self.document["api"]["remoteExecution"] = {"enabled": True}
        self.document["notifications"] = {
            "webhooks": [
                {
                    "id": "terminal-events",
                    "url": "https://example.invalid/mediaflow/events",
                    "secretEnv": "MEDIAFLOW_TERMINAL_WEBHOOK_SECRET",
                    "events": list(self.WEBHOOK_EVENTS),
                    "enabled": True,
                }
            ]
        }
        self.config = self.fixture.root / "config.json"
        self.config.write_text(json.dumps(self.document), encoding="utf-8")
        self.database = self.fixture.root / "runtime.sqlite3"
        self.source = self.fixture.source_root / "Movies/One.2001.mkv"
        self.target_root = self.fixture.target_root
        # The configured subscription must be a real, loadable Webhook document
        # so this test cannot pass against a fixture the product would reject.
        loaded = load_runtime_configuration(copy.deepcopy(self.document))
        self.assertEqual([item.webhook_id for item in loaded.webhooks], ["terminal-events"])
        self.assertTrue(loaded.webhooks[0].enabled)

    def registry(self, provider=None):
        provider = provider or SyntheticMetadataProvider(
            (MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),)
        )
        return MetadataProviderRegistry((provider,))

    def submit_remote(self):
        with SQLiteTaskRepository(self.database) as repository:
            issued = authorization_service(repository, clock=lambda: datetime.now(UTC)).issue(
                ttl_seconds=60, max_items=1
            )
            api = MediaFlowApi(repository, "api-secret", remote_execution_enabled=True)
            status, submitted = remote_request(
                api,
                {"command": "organize", "execute": True, "limit": 1},
                execution_token=issued.token,
            )
        self.assertEqual(202, status, submitted)
        self.assertEqual("task_engine", submitted["executionMethod"], submitted)
        return submitted["taskId"]

    def run_worker(self, provider=None):
        output, errors = io.StringIO(), io.StringIO()
        with patch(
            "mediaflow.final_cli.metadata_provider_registry_from_environment",
            return_value=self.registry(provider),
        ):
            code = final_main(
                ["--config", str(self.config), "worker", "run-next"],
                stdout=output,
                stderr=errors,
            )
        return code, output.getvalue(), errors.getvalue()

    def deliveries(self):
        with SQLiteTaskRepository(self.database) as repository:
            return repository.list_deliveries()

    def test_remote_completion_publishes_one_task_event_without_second_effect(self) -> None:
        task_id = self.submit_remote()
        code, output, errors = self.run_worker()
        self.assertEqual(0, code, errors)
        self.assertIn(task_id, output)
        self.assertIn("completed", output)

        with SQLiteTaskRepository(self.database) as repository:
            task = repository.get_task(task_id)
            results = repository.list_results(task_id)
            items = repository.list_items(task_id)
        self.assertEqual("completed", task.status.value, task.error)
        self.assertEqual(1, len(results), results)
        self.assertEqual(["success"], [item.status.value for item in items])
        self.assertFalse(self.source.exists(), "the completed organize moved its source")
        organized = list((self.target_root / "Organized/Movies").rglob("*.mkv"))
        self.assertEqual(1, len(organized), organized)

        (delivery,) = self.deliveries()
        payload = json.loads(delivery.body)
        self.assertEqual(NotificationEventType.TASK_COMPLETED, delivery.event_type)
        self.assertEqual("terminal-events", delivery.webhook_id)
        self.assertEqual(
            payload["data"],
            {"taskId": task_id, "status": "completed", "command": "organize"},
        )
        self.assertEqual(payload["eventId"], f"task:{task_id}:completed")
        self.assertNotIn("secret", delivery.body.lower())

        # A second Worker pass finds no pending work: the original result is not
        # replayed, and the same original event is not written twice.
        code, output, errors = self.run_worker()
        self.assertEqual(0, code, errors)
        self.assertIn("No pending work", output)
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual(1, len(repository.list_results(task_id)))
            self.assertEqual(1, len(repository.list_items(task_id)))
        self.assertEqual(1, len(self.deliveries()))
        self.assertEqual(1, len(list((self.target_root / "Organized/Movies").rglob("*.mkv"))))
        self.assertFalse(self.source.exists())

        # Same-version reopen keeps the Task outcome and its one outbox row.
        with SQLiteTaskRepository(self.database) as reopened:
            self.assertEqual("completed", reopened.get_task(task_id).status.value)
            self.assertEqual(1, len(reopened.list_deliveries()))

    def test_remote_failure_publishes_task_failed_without_media_effect(self) -> None:
        class _UnavailableProvider:
            provider_id = "tmdb"
            capabilities = ProviderCapabilities(True)

            def search_movie(self, *_args, **_kwargs):
                raise RuntimeError("synthetic Provider outage")

            def get_movie(self, *_args, **_kwargs):
                raise RuntimeError("synthetic Provider outage")

        task_id = self.submit_remote()
        code, output, errors = self.run_worker(_UnavailableProvider())
        self.assertEqual(1, code, errors)
        self.assertIn("failed", output)

        with SQLiteTaskRepository(self.database) as repository:
            task = repository.get_task(task_id)
            items = repository.list_items(task_id)
            results = repository.list_results(task_id)
        self.assertEqual("failed", task.status.value)
        self.assertEqual(["failed"], [item.status.value for item in items])
        self.assertEqual(1, len(results))
        self.assertTrue(self.source.exists(), "a failed Provider lookup must not move the source")
        self.assertFalse(list((self.target_root / "Organized").rglob("*.mkv")))

        (delivery,) = self.deliveries()
        self.assertEqual(NotificationEventType.TASK_FAILED, delivery.event_type)
        self.assertEqual(
            json.loads(delivery.body)["data"],
            {"taskId": task_id, "status": "failed", "command": "organize"},
        )

    def test_cancelled_queued_task_publishes_one_cancelled_event(self) -> None:
        task_id = self.submit_remote()
        output, errors = io.StringIO(), io.StringIO()
        code = final_main(
            ["--config", str(self.config), "tasks", "cancel", task_id],
            stdout=output,
            stderr=errors,
        )
        self.assertEqual(0, code, errors.getvalue())
        self.assertIn("cancelled", output.getvalue())

        with SQLiteTaskRepository(self.database) as repository:
            task = repository.get_task(task_id)
            state = repository.get_task_scheduling(task_id)
        self.assertEqual("cancelled", task.status.value)
        self.assertEqual("settled", state.queue_state.value)
        self.assertTrue(self.source.exists(), "a queued cancel must not touch the source")

        (delivery,) = self.deliveries()
        self.assertEqual(NotificationEventType.TASK_CANCELLED, delivery.event_type)
        self.assertEqual(
            json.loads(delivery.body)["data"],
            {"taskId": task_id, "status": "cancelled", "command": "organize"},
        )

        # The idempotent repeat is the same durable intent, not a second run or
        # a second outbox row.
        code = final_main(
            ["--config", str(self.config), "tasks", "cancel", task_id],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
        self.assertEqual(0, code)
        self.assertEqual(1, len(self.deliveries()))
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual("cancelled", repository.get_task(task_id).status.value)


if __name__ == "__main__":
    unittest.main()
