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

from mediaflow.application.automation import IntervalScheduler
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.notification import NotificationPublisher, NotificationWorker
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.notification import (
    NotificationDeliveryStatus,
    NotificationEvent,
    NotificationEventType,
    WebhookDefinition,
)
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.resident_entry_fixtures import run_resident_step
from tests.test_media_discovery import _DiscoveryFixture

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
        document["notifications"] = {"pollSeconds": 3}
        document["webhooks"] = [
            {
                "id": "ops",
                "url": "https://example.invalid/hook",
                "secretEnv": "MEDIAFLOW_WEBHOOK_SECRET",
                "events": ["task.completed", "task.failed"],
            }
        ]
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
            value["webhooks"][0]["url"] = invalid
            with self.subTest(url=invalid), self.assertRaises(ValueError):
                load_runtime_configuration(value)
        literal = copy.deepcopy(document)
        literal["webhooks"][0]["secret"] = "forbidden"
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
            with SQLiteConfigurationRepository(database) as configuration_repository:
                service = ManagedConfigurationService(
                    configuration_repository, bootstrap_document=document
                )
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
            with SQLiteTaskRepository(database) as repository:
                publish(repository)
                api = MediaFlowApi(
                    repository,
                    principals=(
                        __import__(
                            "mediaflow.domain.security", fromlist=["ResolvedApiPrincipal"]
                        ).ResolvedApiPrincipal(
                            "admin",
                            "api-secret",
                            frozenset(
                                __import__(
                                    "mediaflow.domain.security", fromlist=["ApiPermission"]
                                ).ApiPermission
                            ),
                        ),
                    ),
                )
                statuses = []
                environ = {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": "/api/notifications",
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

    def test_scheduler_emission_enters_outbox_for_the_admitted_task(self) -> None:
        """A real due occurrence publishes its schedule event for one Task."""

        from mediaflow.application.task_scheduling import TaskSchedulingService
        from mediaflow.domain.automation import (
            AutomationTaskDefinition,
            AutomationTaskRunMode,
            SchedulerConfigurationSnapshot,
        )

        definitions = (webhook(events=(NotificationEventType.SCHEDULE_EMITTED,)),)
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                definition = AutomationTaskDefinition(
                    "hourly",
                    "Hourly organize",
                    "library",
                    None,
                    AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
                    3600,
                    None,
                    None,
                    5,
                    True,
                )
                publisher = NotificationPublisher(repository, definitions)
                scheduler = IntervalScheduler(
                    repository,
                    publisher,
                    scheduling_service=TaskSchedulingService(repository, capacity=10),
                    configuration_snapshot_resolver=lambda: SchedulerConfigurationSnapshot(
                        "revision-hourly",
                        "a" * 64,
                        10,
                        (definition,),
                        1,
                        ("library",),
                        ("library",),
                    ),
                )
                (task,) = scheduler.tick(NOW)
                (delivery,) = repository.list_deliveries()
                self.assertEqual(delivery.event_type, NotificationEventType.SCHEDULE_EMITTED)
                body = json.loads(delivery.body)["data"]
                self.assertEqual(body["taskId"], task.task_id)
                self.assertEqual(body["definitionId"], "hourly")
                self.assertIsNotNone(
                    repository.get_task_scheduling(task.task_id),
                    "the schedule event must name the one admitted organizing Task",
                )


class TerminalTaskNotificationTests(_DiscoveryFixture):
    """A real admission, the production Worker and the durable outbox.

    Each case starts at the supported Files entrance, advances the admitted
    Task through one real resident Worker step (the same composition with
    its Task engine and terminal observer), and reads the real notification
    outbox.  No test calls the publisher to fake the terminal publication.
    """

    WEBHOOK_EVENTS = ["task.completed", "task.cancelled"]

    def _document(self) -> dict:
        document = self.document()
        # A real rule answer for the fixture's own library identity, so the
        # journey parks at its exact plan summary instead of an undecided
        # Recognition problem.
        document["recognitionRules"] = [
            {
                "id": "movies",
                "name": "Movies",
                "priority": 100,
                "score": 100,
                "stopOnMatch": True,
                "condition": {"field": "extension", "operator": "in", "value": ["mkv", "mp4"]},
                "outputRecognitionType": "A",
            }
        ]
        document["automationTaskDefinitions"] = [
            {
                "id": "nightly",
                "name": "Nightly",
                "resourceLibraryId": "library",
                "mode": "automatic-organization",
                "intervalSeconds": 3600,
                "itemLimit": 10,
                "enabled": False,
                "sourceScope": "Movies",
            }
        ]
        document["webhooks"] = [
            {
                "id": "terminal-events",
                "url": "https://example.invalid/mediaflow/events",
                "secretEnv": "MEDIAFLOW_TERMINAL_WEBHOOK_SECRET",
                "events": list(self.WEBHOOK_EVENTS),
                "enabled": True,
            }
        ]
        return document

    def _journey(self, document):
        return self.journey(task_scheduling=True, provider=self._provider())

    @staticmethod
    def _provider():
        return SyntheticMetadataProvider(
            (MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),)
        )

    def _write_config(self, document: dict) -> Path:
        config = self.root / "config.json"
        config.write_text(json.dumps(document), encoding="utf-8")
        return config

    def _admit(self, value, path: str):
        return self.request(
            value,
            "/api/resource-libraries/library/files/discoveries",
            "POST",
            {"paths": [path], "autoPrepare": True},
        )

    def _run_worker(self, config: Path):
        from mediaflow.application.metadata import MetadataProviderRegistry

        with patch(
            "mediaflow.resident_entry.metadata_provider_registry_from_environment",
            return_value=MetadataProviderRegistry((self._provider(),)),
        ):
            code, output = run_resident_step("worker", config)
        return code, output, ""

    def _confirm_summary(self, value, task_id: str, item_id: str):
        status, detail = self.request(value, f"/api/tasks/{task_id}/items/{item_id}/recovery")
        self.assertEqual(200, status, detail)
        preparation = detail["manualRecoveryPreparation"]
        self.assertIsNotNone(preparation, detail)
        status, preview = self.request(
            value, f"/api/operations/organize/previews/{preparation['preview_id']}"
        )
        self.assertEqual(200, status, preview)
        ready = [item["itemId"] for item in preview["items"] if item["status"] == "previewed"]
        self.assertEqual(1, len(ready), preview)
        status, confirmed = self.request(
            value,
            f"/api/operations/organize/previews/{preparation['preview_id']}/execute",
            "POST",
            {
                "preparationId": preparation["preparation_id"],
                "itemIds": ready,
                "confirmation": True,
                "expectedIntentVersion": preview["intentVersion"],
                "allowOverwrite": False,
                "allowSourceCleanup": False,
            },
        )
        self.assertEqual(202, status, confirmed)
        return confirmed

    def _drive_worker(self, value, config, task_id, *, until, steps=8):
        """Run the production Worker until the exact Task reaches a boundary."""

        transcripts = []
        for _ in range(steps):
            code, output, errors = self._run_worker(config)
            transcripts.append((code, output, errors))
            task = value.repository.get_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            if until == "terminal" and task.status.value in {
                "completed",
                "partial_success",
                "failed",
                "cancelled",
            }:
                return transcripts
            if (
                until == "human"
                and state is not None
                and state.queue_state.value == "waiting_human"
            ):
                return transcripts
        return transcripts

    def _deliveries(self):
        with SQLiteTaskRepository(self.database) as repository:
            return repository.list_deliveries()

    def test_run_once_completion_publishes_one_task_event_and_reopen_keeps_it(self) -> None:
        self.media("Movies/One.2001.mkv")
        document = self._document()
        config = self._write_config(document)
        with self._journey(document) as value:
            self.publish_policy(value, document=document)
            status, admitted = self.request(
                value,
                "/api/operations/automation/task-definitions/nightly/run-once",
                "POST",
                {"admissionRequestId": "terminal-1"},
            )
            self.assertIn(status, (200, 202), admitted)
            task_id = admitted.get("taskId")
            self.assertIsInstance(task_id, str, admitted)

            transcripts = self._drive_worker(value, config, task_id, until="terminal")
            self.assertEqual(
                "completed",
                value.repository.get_task(task_id).status.value,
                (transcripts, value.repository.get_task(task_id)),
            )
            task = value.repository.get_task(task_id)
            results = value.repository.list_results(task_id)
            items = value.repository.list_items(task_id)
            self.assertEqual("completed", task.status.value, task.error)
            self.assertEqual(1, len(results), results)
            self.assertEqual(["success"], [entry.status.value for entry in items])
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            organized = list((self.target_root / "Organized/Movies").rglob("*.mkv"))
            self.assertEqual(1, len(organized))

            (delivery,) = self._deliveries()
            payload = json.loads(delivery.body)
            self.assertEqual(NotificationEventType.TASK_COMPLETED, delivery.event_type)
            self.assertEqual("terminal-events", delivery.webhook_id)
            self.assertEqual(
                payload["data"],
                {"taskId": task_id, "status": "completed", "command": "organize"},
            )
            self.assertEqual(payload["eventId"], f"task:{task_id}:completed")
            self.assertNotIn("secret", delivery.body.lower())

            # A second Worker pass finds no work: the completed source is not
            # replayed and the terminal event is not published twice.
            code, output, errors = self._run_worker(config)
            self.assertEqual(0, code, errors)
            self.assertIn("Worker stopped", output)
            self.assertEqual(1, len(self._deliveries()))
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())

        # Same-version reopen keeps the Task outcome and its one outbox row.
        with SQLiteTaskRepository(self.database) as reopened:
            self.assertEqual("completed", reopened.get_task(task_id).status.value)
            self.assertEqual(1, len(reopened.list_deliveries()))

    def test_queued_cancellation_publishes_one_event_without_media_effect(self) -> None:
        self.media("Movies/One.2001.mkv")
        document = self._document()
        with self._journey(document) as value:
            self.publish_policy(value, document=document)
            status, admitted = self._admit(value, "Movies/One.2001.mkv")
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]

            status, cancelled = self.request(value, f"/api/tasks/{task_id}/cancel", "POST")
            self.assertEqual(200, status, cancelled)
            task = value.repository.get_task(task_id)
            self.assertEqual("cancelled", task.status.value)
            self.assertTrue((self.source_root / "Movies/One.2001.mkv").exists())

            (delivery,) = self._deliveries()
            self.assertEqual(NotificationEventType.TASK_CANCELLED, delivery.event_type)
            self.assertEqual(
                json.loads(delivery.body)["data"],
                {"taskId": task_id, "status": "cancelled", "command": "manual_organize"},
            )

            # The idempotent repeat is refused at the same boundary (already
            # cancelled) and must not create a second outbox row.
            status, repeat = self.request(value, f"/api/tasks/{task_id}/cancel", "POST")
            self.assertEqual(409, status, repeat)
            self.assertEqual(1, len(self._deliveries()))
            with SQLiteTaskRepository(self.database) as reopened:
                self.assertEqual("cancelled", reopened.get_task(task_id).status.value)
                self.assertEqual(1, len(reopened.list_deliveries()))
