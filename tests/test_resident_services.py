"""Resident-service startup, configuration adoption and infrastructure health.

These tests cover the boundary that a fresh installation actually exercises:
the API and all three resident services must start and stay alive from
deployment-owned authority alone, adopt an eligible configuration publication
without restarting, and report infrastructure readiness and work waiting as two
separate, truthful facts.

Every test here uses a temporary SQLite database, a minimal bootstrap document
and fake credentials.  No production path, media file, Provider or Webhook is
read or written.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.resident_runtime import (
    ResidentLoop,
    build_resident_runtime,
    register_resident_process,
    resident_instance_id,
)
from mediaflow.application.resident_services import ResidentServiceService
from mediaflow.domain.notification import (
    NotificationEventType,
    WebhookDefinition,
    WebhookRequest,
)
from mediaflow.domain.resident_services import (
    RESIDENT_SERVICES,
    ResidentServiceReadiness,
    ResidentServiceStatus,
    ResidentServiceWaiting,
)
from mediaflow.infrastructure.runtime_configuration import (
    is_minimal_management_bootstrap,
    load_minimal_management_bootstrap,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository

FAKE_TOKEN = "fake-resident-token"
FAKE_WEBHOOK_SECRET = "fake-webhook-secret"


def _bootstrap(database: str, token_env: str = "MF_ADMIN_TOKEN") -> dict:
    return {
        "version": 1,
        "persistence": {"databasePath": database},
        "api": {
            "principals": [
                {"id": "admin", "tokenEnv": token_env, "roles": ["admin"], "enabled": True}
            ]
        },
    }


class ResidentDeploymentFixture(unittest.TestCase):
    """A real deployment-shaped workspace: one bootstrap file, one database."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.database = str(self.data / "mediaflow.sqlite3")
        self.document = _bootstrap(self.database)
        self.config = self.root / "mediaflow.json"
        self.config.write_text(json.dumps(self.document, indent=2), encoding="utf-8")
        self.environment = patch.dict(
            os.environ, {"MF_ADMIN_TOKEN": FAKE_TOKEN, "PATH": os.environ.get("PATH", "")}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self._temporary.cleanup)

    def cli(self, *arguments: str) -> tuple[int, str, str]:
        """Run one real CLI command against this deployment."""

        from mediaflow.cli import main as cli_main

        out, err = io.StringIO(), io.StringIO()
        try:
            code = cli_main(["--config", str(self.config), *arguments], stdout=out, stderr=err)
        except SystemExit as exit_error:  # pragma: no cover - argparse exits
            code = int(exit_error.code or 0)
        except Exception as error:  # noqa: BLE001 - surface the real failure
            return -1, "", f"{type(error).__name__}: {error}"
        return code, out.getvalue(), err.getvalue()

    def publish_first_draft(self, document: dict) -> str:
        """Create, validate and activate the first Draft; return its revision ID."""

        from mediaflow.application.configuration_snapshot import ManagedConfigurationService
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )

        with SQLiteConfigurationRepository(self.database) as repository:
            service = ManagedConfigurationService(
                repository,
                bootstrap_database_path=self.database,
                bootstrap_document=self.document,
            )
            draft = service.create_first_draft(self.document, actor="test")
            service.validate(draft.revision_id, actor="test")
            activated = service.activate(
                draft.revision_id, expected_version=draft.version, actor="test"
            )
        return activated.revision_id

    def empty_baseline(self) -> dict:
        from mediaflow.application.configuration_snapshot import (
            build_first_setup_starter_document,
        )

        return build_first_setup_starter_document(load_minimal_management_bootstrap(self.document))

    def publish_successor(self, mutate) -> str:
        """Edit/validate/activate a successor of the current Active."""

        from mediaflow.application.configuration_snapshot import ManagedConfigurationService
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )

        with SQLiteConfigurationRepository(self.database) as repository:
            service = ManagedConfigurationService(
                repository,
                bootstrap_database_path=self.database,
                bootstrap_document=self.document,
            )
            active = service.active()
            document = json.loads(json.dumps(active.document))
            mutate(document)
            # A published revision is immutable, so a change becomes a new
            # Draft — which is exactly the supported A→B publication path.
            draft = service.import_draft(document, actor="test", source="test")
            validated = service.validate(draft.revision_id, actor="test")
            self.assertEqual(
                validated.status.value,
                "validated",
                msg=json.dumps(validated.summary(), ensure_ascii=False),
            )
            return service.activate(
                draft.revision_id, expected_version=validated.version, actor="test"
            ).revision_id

    def resident(self) -> ResidentServiceService:
        """A service over a repository this test keeps open for its duration."""

        repository = SQLiteTaskRepository(self.database)
        self.addCleanup(repository.close)
        return ResidentServiceService(repository, runtime_schema_version=SCHEMA_VERSION)


class ManagementOnlyStartupTests(ResidentDeploymentFixture):
    """Every resident service must start before any Active configuration exists."""

    def test_management_bootstrap_is_the_legal_first_setup_shape(self) -> None:
        # The precondition for the whole boundary: a fresh deployment document
        # really is a valid strict first-setup bootstrap.
        self.assertTrue(is_minimal_management_bootstrap(self.document))

    def test_scheduler_list_and_tick_start_without_active(self) -> None:
        """Reproduction of the reviewed defect.

        With a valid management-only bootstrap, ``scheduler list`` and
        ``scheduler tick`` previously raised AttributeError for
        ``automation_schedules`` and the resident ``run`` loop crashed on the
        same attribute.  All three must now work and emit nothing.
        """

        for arguments in (["scheduler", "list"], ["scheduler", "tick"]):
            with self.subTest(arguments=arguments):
                code, out, err = self.cli(*arguments)
                self.assertEqual(code, 0, msg=f"{arguments}: {err}")
                self.assertNotIn("AttributeError", err)
        code, out, err = self.cli("scheduler", "list")
        self.assertIn("INTERVAL SCHEDULES", out)
        self.assertIn("Total: 0", out)

    def test_notification_worker_waits_instead_of_crashing_without_active(self) -> None:
        """Reproduction of the reviewed defect.

        ``notification-worker run-next`` previously raised AttributeError for
        ``resolve_webhook_targets``.  It must now wait, exit successfully, and
        leave the durable outbox untouched.
        """

        code, out, err = self.cli("notification-worker", "run-next")
        self.assertEqual(code, 0, msg=err)
        self.assertNotIn("AttributeError", err)
        self.assertIn("waiting", out)
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual(repository.list_deliveries(limit=10), ())

    def test_worker_starts_and_registers_its_transfer_consumers(self) -> None:
        """The Worker keeps its pre-existing management-only bootstrap behavior."""

        code, out, err = self.cli("worker", "run-next")
        self.assertEqual(code, 0, msg=err)
        self.assertIn("No pending automation jobs", out)

    def test_reads_and_empty_activation_create_no_media_work_or_delivery(self) -> None:
        """Safety invariant: first setup and empty activation start nothing.

        Neither reading configuration state nor activating a valid empty
        baseline may create a Job, a delivery, a Task or a Storage mutation.
        """

        self.publish_first_draft(self.empty_baseline())
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual(repository.list_jobs(limit=50), ())
            self.assertEqual(repository.list_deliveries(limit=50), ())
            self.assertEqual(repository.list_tasks(limit=50), ())
        # Scheduler/Notification services remain no-ops against an empty Active.
        self.assertEqual(self.cli("scheduler", "tick")[0], 0)
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual(repository.list_jobs(limit=50), ())
            self.assertEqual(repository.list_deliveries(limit=50), ())


class ResidentRegistryTests(ResidentDeploymentFixture):
    """The durable presence rows that make readiness an observed fact."""

    def test_registration_heartbeat_and_stop(self) -> None:
        runtime = build_resident_runtime(self.database)
        instance = resident_instance_id("scheduler")
        register_resident_process(runtime, "scheduler", instance, heartbeat_interval_seconds=5.0)
        readiness = runtime.service.evaluate_readiness("scheduler")
        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["condition"], ResidentServiceReadiness.READY.value)

        self.assertTrue(runtime.service.heartbeat(instance))
        runtime.service.stop(instance)
        self.assertFalse(runtime.service.evaluate_readiness("scheduler")["ready"])

    def test_waiting_service_remains_infrastructure_ready(self) -> None:
        """A correctly-waiting service is healthy; only liveness gates readiness.

        Conflating "running" with "has work" is what made the previous health
        surfaces lie in both directions.  Readiness must be true while the
        waiting reason is reported separately.
        """

        runtime = build_resident_runtime(self.database)
        instance = resident_instance_id("scheduler")
        register_resident_process(runtime, "scheduler", instance, heartbeat_interval_seconds=5.0)
        runtime.service.record_wait_state(
            "scheduler",
            instance,
            waiting_reason=ResidentServiceWaiting.UNCONFIGURED.value,
            waiting_detail="no Active configuration is published",
        )
        readiness = runtime.service.evaluate_readiness("scheduler")
        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["condition"], ResidentServiceReadiness.READY.value)
        projection = runtime.service.deployment_readiness()["services"]["scheduler"]
        self.assertTrue(projection["waiting"])
        self.assertEqual(projection["waitingReason"], ResidentServiceWaiting.UNCONFIGURED.value)

    def test_absent_service_is_not_ready_and_never_crashes(self) -> None:
        runtime = build_resident_runtime(self.database)
        for service in RESIDENT_SERVICES:
            with self.subTest(service=service):
                readiness = runtime.service.evaluate_readiness(service)
                self.assertFalse(readiness["ready"])
                self.assertEqual(readiness["condition"], ResidentServiceReadiness.NO_SERVICE.value)
                self.assertNotEqual(readiness["nextAction"], "none")
                # Bounded: no exception detail may reach the operator surface.
                self.assertLessEqual(len(str(readiness["durableState"])), 200)

    def test_stale_and_schema_mismatched_registration_fail_closed(self) -> None:
        runtime = build_resident_runtime(self.database)
        instance = resident_instance_id("worker")
        runtime.service.register("worker", instance, heartbeat_interval_seconds=5.0)
        stale = datetime.now(UTC) + timedelta(minutes=5)
        self.assertEqual(
            runtime.service.evaluate_readiness("worker", stale)["condition"],
            ResidentServiceReadiness.STALE_SERVICE.value,
        )
        # A registration that only an older image could have written is
        # reported as incompatible rather than silently accepted.
        with SQLiteTaskRepository(self.database) as repository:
            repository.register_resident_service(
                "scheduler", "old-image", 5.0, SCHEMA_VERSION - 1, None, datetime.now(UTC)
            )
        self.assertEqual(
            runtime.service.evaluate_readiness("scheduler")["condition"],
            ResidentServiceReadiness.SCHEMA_MISMATCH.value,
        )
        self.assertIn("upgrade", runtime.service.evaluate_readiness("scheduler")["nextAction"])

    def test_unknown_service_name_is_rejected(self) -> None:
        runtime = build_resident_runtime(self.database)
        with self.assertRaises(ValueError):
            runtime.service.evaluate_readiness("not-a-service")

    def test_waiting_reason_must_be_a_bounded_known_value(self) -> None:
        """Operator text must not become an unbounded status field."""

        runtime = build_resident_runtime(self.database)
        instance = resident_instance_id("scheduler")
        register_resident_process(runtime, "scheduler", instance, heartbeat_interval_seconds=5.0)
        with self.assertRaises(ValueError):
            runtime.service.record_wait_state(
                "scheduler", instance, waiting_reason="raw error text with a token"
            )

    def test_deployment_readiness_covers_every_declared_service(self) -> None:
        projection = self.resident().deployment_readiness()
        self.assertEqual(set(projection["services"]), set(RESIDENT_SERVICES))
        self.assertFalse(projection["infrastructureReady"])
        # No secret or private path may appear in the projection.
        rendered = json.dumps(projection, ensure_ascii=False)
        self.assertNotIn(FAKE_TOKEN, rendered)
        self.assertNotIn(str(self.root), rendered)

    def test_resident_registration_survives_reopening_the_database(self) -> None:
        runtime = build_resident_runtime(self.database)
        instance = resident_instance_id("notification-worker")
        register_resident_process(
            runtime, "notification-worker", instance, heartbeat_interval_seconds=5.0
        )
        reopened = build_resident_runtime(self.database)
        registration = reopened.service.get("notification-worker", instance)
        self.assertIsNotNone(registration)
        self.assertIs(registration.status, ResidentServiceStatus.LIVE)


class ResidentLoopTests(ResidentDeploymentFixture):
    """The fault-tolerant loop that keeps a resident process alive."""

    def test_loop_survives_a_failing_step_and_keeps_heartbeating(self) -> None:
        """A recoverable fault must not end the process.

        Killing a resident service never repairs a configuration or a database
        and always loses in-flight progress, so an exception inside the loop
        body is a bounded waiting state, not a crash.
        """

        runtime = build_resident_runtime(self.database)
        instance = resident_instance_id("scheduler")
        register_resident_process(runtime, "scheduler", instance, heartbeat_interval_seconds=0.1)
        attempts = {"count": 0}

        def step(loop: ResidentLoop) -> int:
            """Fail twice, then report real work exactly once."""

            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("Active configuration is temporarily unreadable")
            if attempts["count"] == 3:
                return 1
            return 0

        slept: list[float] = []
        log = io.StringIO()
        loop = ResidentLoop(
            runtime,
            "scheduler",
            instance,
            heartbeat_interval_seconds=0.1,
            poll_seconds=0.01,
            stdout=log,
            step=step,
        )
        ticks = {"count": 0}

        def stop() -> bool:
            ticks["count"] += 1
            return ticks["count"] > 8

        processed = loop.run(stop, lambda seconds: slept.append(seconds))
        # The two recoverable faults were survived, and the one real unit of
        # work after recovery was reported exactly once.
        self.assertEqual(processed, 1)
        self.assertGreaterEqual(attempts["count"], 3)
        # Idle iterations slept instead of spinning.
        self.assertTrue(slept)
        # The transient fault was reported once as a bounded, known waiting
        # reason instead of crashing or being silently swallowed, and the raw
        # exception text never reaches the operator surface.
        log_text = log.getvalue()
        self.assertIn(ResidentServiceWaiting.CONFIGURATION_UNAVAILABLE.value, log_text)
        self.assertNotIn("Active configuration is temporarily unreadable", log_text)
        self.assertEqual(log_text.count("waiting:"), 1)
        # The process must still be registered live when it exits cleanly.
        registration = runtime.service.get("scheduler", instance)
        self.assertIsNotNone(registration)
        self.assertIs(registration.status, ResidentServiceStatus.STOPPED)

    def test_loop_rejects_a_non_positive_poll_interval(self) -> None:
        runtime = build_resident_runtime(self.database)
        with self.assertRaises(ValueError):
            ResidentLoop(
                runtime,
                "scheduler",
                "instance",
                heartbeat_interval_seconds=1.0,
                poll_seconds=0,
                stdout=io.StringIO(),
                step=lambda loop: 0,
            )


class ConfigurationAdoptionTests(ResidentDeploymentFixture):
    """Current Active governs new work; nothing is bound at process start."""

    def test_current_runtime_configuration_is_none_without_active(self) -> None:
        from mediaflow.final_cli import _current_runtime_configuration

        self.assertIsNone(_current_runtime_configuration(str(self.config)))
        self.publish_first_draft(self.empty_baseline())
        resolved = _current_runtime_configuration(str(self.config))
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.configuration_authority, "MANAGED")

    def test_a_new_activation_is_visible_to_a_running_process_without_restart(self) -> None:
        """The same resolved path is re-evaluated, never cached at startup."""

        from mediaflow.final_cli import _current_runtime_configuration

        self.publish_first_draft(self.empty_baseline())
        first = _current_runtime_configuration(str(self.config))
        self.assertEqual(first.automation_schedules, ())

        def add_schedule(document: dict) -> None:
            document["automation"]["schedules"] = [
                {
                    "id": "nightly",
                    "command": "preview",
                    "intervalSeconds": 3600,
                    "enabled": True,
                }
            ]

        second_revision = self.publish_successor(add_schedule)
        second = _current_runtime_configuration(str(self.config))
        self.assertEqual([item.schedule_id for item in second.automation_schedules], ["nightly"])
        # The pinned identity really did change, so this is a new authority and
        # not a stale in-memory object.
        self.assertNotEqual(first.configuration_snapshot_id, second.configuration_snapshot_id)
        self.assertEqual(second.configuration_snapshot_id, second_revision)

    def test_corrupt_active_stops_admission_without_falling_back(self) -> None:
        """A broken Active must yield "nothing to admit", never stale work.

        Falling back to the JSON bootstrap or a previous Active would let a
        resident process issue work under authority the operator never
        published.
        """

        from mediaflow.final_cli import _current_runtime_configuration

        self.publish_first_draft(self.empty_baseline())
        self.assertIsNotNone(_current_runtime_configuration(str(self.config)))
        with SQLiteTaskRepository(self.database) as repository:
            repository._connection.execute(
                "UPDATE managed_configuration_revisions SET payload=? WHERE status='active'",
                (json.dumps({"persistence": {"databasePath": self.database}}),),
            )
            repository._connection.commit()
        self.assertIsNone(_current_runtime_configuration(str(self.config)))

    def test_scheduler_tick_under_unavailable_active_emits_nothing(self) -> None:
        """No Active means no occurrence, and no advancing of a due one."""

        code, out, err = self.cli("scheduler", "tick")
        self.assertEqual(code, 0, msg=err)
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual(repository.list_jobs(limit=50), ())

    def test_worker_publishes_no_delivery_without_a_configured_webhook(self) -> None:
        self.publish_first_draft(self.empty_baseline())
        code, out, err = self.cli("worker", "run-next")
        self.assertEqual(code, 0, msg=err)
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual(repository.list_deliveries(limit=50), ())


class NotificationTargetIdentityTests(ResidentDeploymentFixture):
    """A delivery must never be claimed against a target it cannot use."""

    def setUp(self) -> None:
        super().setUp()
        os.environ["MF_WEBHOOK_SECRET"] = FAKE_WEBHOOK_SECRET
        self.addCleanup(os.environ.pop, "MF_WEBHOOK_SECRET", None)
        self.publish_first_draft(self.empty_baseline())

    def _webhook(self, webhook_id: str = "primary", *, enabled: bool = True) -> dict:
        return {
            "id": webhook_id,
            "url": "https://webhook.invalid/hook",
            "secretEnv": "MF_WEBHOOK_SECRET",
            "events": ["schedule.emitted"],
            "enabled": enabled,
        }

    def _add_delivery(self, webhook_id: str = "primary") -> None:
        from mediaflow.application.notification import NotificationPublisher
        from mediaflow.domain.notification import NotificationEvent

        # Publish through a real enabled Webhook so the durable delivery
        # genuinely exists; the worker under test is what later has to refuse
        # to claim it.
        with SQLiteTaskRepository(self.database) as repository:
            NotificationPublisher(repository, (self._definition(webhook_id),)).publish(
                NotificationEvent(
                    "event-1",
                    NotificationEventType.SCHEDULE_EMITTED,
                    datetime.now(UTC),
                    {"scheduleId": "nightly"},
                )
            )

    def _definition(self, webhook_id: str = "primary") -> WebhookDefinition:
        return WebhookDefinition(
            webhook_id,
            f"https://webhook.invalid/{webhook_id}",
            "MF_WEBHOOK_SECRET",
            (NotificationEventType.SCHEDULE_EMITTED,),
        )

    def _worker(self, targets):
        """Build a worker over a repository this test keeps open.

        The worker must outlive one call, so the repository is intentionally not
        closed when the helper returns.
        """

        from mediaflow.application.notification import NotificationWorker

        repository = SQLiteTaskRepository(self.database)
        self.addCleanup(repository.close)
        return NotificationWorker(repository, targets, _RecordingTransport())

    def test_no_configuration_means_no_claim_and_no_dead_letter(self) -> None:
        """Waiting must not consume a durable delivery.

        Claiming without a target would burn an attempt and dead-letter a
        perfectly good notification that a later publication could deliver.
        """

        self._add_delivery()
        worker = self._worker({})
        self.assertIsNone(worker.run_next())
        with SQLiteTaskRepository(self.database) as repository:
            delivery = repository.list_deliveries(limit=1)[0]
            self.assertEqual(delivery.status.value, "pending")
            self.assertEqual(delivery.attempts, 0)

    def test_unreadable_configuration_is_a_waiting_state_not_a_failure(self) -> None:
        def broken() -> dict:
            raise ValueError("no valid Active delivery configuration is published")

        self._add_delivery()
        worker = self._worker(broken)
        with self.assertRaises(ValueError):
            worker.run_next()
        self.assertIsNotNone(worker.last_unavailable_reason)
        self.assertNotIn(FAKE_WEBHOOK_SECRET, worker.last_unavailable_reason)
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual(repository.list_deliveries(limit=1)[0].attempts, 0)

    def test_claim_is_restricted_to_the_currently_deliverable_targets(self) -> None:
        """A delivery naming a removed target must not be claimed and blocked.

        Without the filter, the removed-target delivery sorts first, is claimed,
        burns an attempt and dead-letters, and the still-valid delivery behind
        it is never reached.
        """

        removed = "removed"
        kept = "kept"
        self._add_delivery(removed)
        with SQLiteTaskRepository(self.database) as repository:
            repository._connection.execute(
                "UPDATE notification_deliveries SET delivery_id='000-removed' WHERE webhook_id=?",
                (removed,),
            )
            repository._connection.execute(
                "INSERT INTO notification_deliveries VALUES "
                "('000-kept','kept','event-2','schedule.emitted','{}','pending',0,"
                "?,?,?,NULL,NULL,NULL)",
                (
                    datetime.now(UTC).isoformat(),
                    datetime.now(UTC).isoformat(),
                    datetime.now(UTC).isoformat(),
                ),
            )
            repository._connection.commit()

        definition = self._definition(kept)
        worker = self._worker({kept: (definition, FAKE_WEBHOOK_SECRET)})
        delivery = worker.run_next()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.delivery_id, "000-kept")
        self.assertEqual(delivery.status.value, "delivered")
        with SQLiteTaskRepository(self.database) as repository:
            untouched = repository.get_delivery("000-removed")
            self.assertEqual(untouched.status.value, "pending")
            self.assertEqual(untouched.attempts, 0)
        # The request really was signed for the retained target.
        self.assertEqual(worker._transport.sent[0].headers["X-MediaFlow-Delivery"], "000-kept")


class _RecordingTransport:
    """A transport that records requests instead of performing network I/O."""

    def __init__(self) -> None:
        self.sent: list[WebhookRequest] = []

    def send(self, request: WebhookRequest) -> int:
        self.sent.append(request)
        return 200


if __name__ == "__main__":
    unittest.main()


class ManagementReadinessInfrastructureTests(ResidentDeploymentFixture):
    """The authenticated status surface must separate health from work readiness."""

    def _api(self, resident=None):
        from mediaflow.application.configuration_snapshot import ManagedConfigurationService
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )
        from mediaflow.interfaces.service_api import MediaFlowApi

        task_repository = SQLiteTaskRepository(self.database)
        configuration_repository = SQLiteConfigurationRepository(self.database)
        self.addCleanup(task_repository.close)
        self.addCleanup(configuration_repository.close)
        service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=self.database,
            bootstrap_document=self.document,
            management_only=True,
        )
        from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal

        return MediaFlowApi(
            task_repository,
            None,
            principals=(ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),),
            configuration_service=service,
            bootstrap_document=self.document,
            management_only=True,
            resident_services=resident
            or ResidentServiceService(task_repository, runtime_schema_version=SCHEMA_VERSION),
        )

    def _request(self, api, path: str) -> tuple[int, dict]:
        statuses: list[str] = []
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "CONTENT_LENGTH": "0",
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": "Bearer admin-token",
            "wsgi.input": io.BytesIO(),
        }
        body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(body)

    def test_readiness_separates_infrastructure_from_work_readiness(self) -> None:
        """One document answers both questions without conflating them.

        A fresh deployment has no Active at all, so work readiness is
        genuinely "not configured" — but that must not be reported as an
        infrastructure failure, or an operator would restart a healthy stack.
        """

        api = self._api()
        status, readiness = self._request(api, "/api/v1/management/readiness")
        self.assertEqual(status, 200)
        self.assertFalse(readiness["runtimeConfigured"])
        self.assertTrue(readiness["managementReady"])
        infrastructure = readiness["infrastructure"]
        self.assertTrue(infrastructure["available"])
        # Nothing registered yet, so infrastructure is honestly not ready.
        self.assertFalse(infrastructure["infrastructureReady"])
        self.assertEqual(set(infrastructure["services"]), set(RESIDENT_SERVICES))

    def test_a_live_waiting_service_is_infrastructure_ready_but_not_doing_work(self) -> None:
        runtime = build_resident_runtime(self.database)
        instance = resident_instance_id("scheduler")
        register_resident_process(runtime, "scheduler", instance, heartbeat_interval_seconds=5.0)
        runtime.service.record_wait_state(
            "scheduler",
            instance,
            waiting_reason=ResidentServiceWaiting.UNCONFIGURED.value,
            waiting_detail="no valid Active configuration is published",
        )
        api = self._api(runtime.service)
        status, readiness = self._request(api, "/api/v1/management/readiness")
        self.assertEqual(status, 200)
        scheduler = readiness["infrastructure"]["services"]["scheduler"]
        self.assertTrue(scheduler["ready"])
        self.assertTrue(scheduler["waiting"])
        self.assertEqual(scheduler["waitingReason"], ResidentServiceWaiting.UNCONFIGURED.value)
        # The infrastructure answer never claims the deployment is fully ready
        # while the API and Worker have not registered either.
        self.assertFalse(readiness["infrastructure"]["infrastructureReady"])
        # No secret or private path may reach the operator projection.
        rendered = json.dumps(readiness, ensure_ascii=False)
        self.assertNotIn(FAKE_TOKEN, rendered)
        self.assertNotIn(str(self.root), rendered)

    def test_health_endpoint_stays_liveness_only_and_side_effect_free(self) -> None:
        """``/health`` must not be widened into an infrastructure probe.

        It is the unauthenticated loopback liveness endpoint used by the
        container healthcheck.  Making it evaluate configuration, Storage or
        Providers would turn every transient fault into an outage.
        """

        api = self._api()
        status, health = self._request(api, "/health")
        self.assertEqual(status, 200)
        self.assertEqual(health, {"processAlive": True, "status": "ok"})

    def test_readiness_degrades_to_a_bounded_reason_when_presence_is_unavailable(self) -> None:
        """A shared-database fault during a read must stay a readable reason.

        This document is itself the recovery surface, so it must never raise
        while the operator is trying to repair exactly that database.
        """

        class Failing:
            def deployment_readiness(self):
                raise OSError("database file is not readable")

        api = self._api(Failing())
        status, readiness = self._request(api, "/api/v1/management/readiness")
        self.assertEqual(status, 200)
        infrastructure = readiness["infrastructure"]
        self.assertFalse(infrastructure["available"])
        self.assertFalse(infrastructure["infrastructureReady"])
        self.assertIn("OSError", infrastructure["durableState"])
        self.assertNotEqual(infrastructure["nextAction"], "")

    def test_deployment_without_a_resident_service_boundary_still_answers(self) -> None:
        """An embedded API without the registry must keep its existing surfaces."""

        api = self._api(resident=None)
        # Replace the auto-built service with an explicit absence.
        api._resident_services = None
        status, readiness = self._request(api, "/api/v1/management/readiness")
        self.assertEqual(status, 200)
        infrastructure = readiness["infrastructure"]
        self.assertFalse(infrastructure["available"])
        self.assertFalse(infrastructure["infrastructureReady"])
        self.assertTrue(readiness["managementReady"])


if __name__ == "__main__":
    unittest.main()
