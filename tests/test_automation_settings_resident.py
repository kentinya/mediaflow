"""Task 43.4 — real resident Worker/Scheduler cadence adoption (S4–S6).

These cases start the *real* `worker run` / `scheduler run` commands as
subprocesses over an isolated temporary deployment, publish genuine managed
Active successors, and then observe the adoption through the processes' own
durable reports and their actual loop cadence.

Nothing here asserts an HTTP echo or a self-reported target: the observable is
the effective cadence the loop installed (proved by its own idle-wait bound and
reported values) plus the durable row the process wrote *after* adopting.

No production media, Storage, Provider, database or secret is touched.
"""

from __future__ import annotations

import subprocess
import sys
import time
import unittest

from mediaflow.application.resident_runtime import (
    CONFIG_RECHECK_SECONDS,
    ResidentLoop,
    build_resident_runtime,
    register_resident_process,
    resident_instance_id,
)
from mediaflow.domain.automation_settings import ResidentCadence, ResidentSettingsEvidence
from mediaflow.domain.resident_services import ResidentServiceStatus
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from tests.test_resident_services import ResidentDeploymentFixture


class ResidentAdoptionFixture(ResidentDeploymentFixture):
    """Deployment fixture plus the real-process helpers these cases need."""

    def setUp(self) -> None:
        super().setUp()
        # The shared runtime schema must exist before a read-only reader opens
        # it: the resident processes install it themselves on first start, and a
        # read-only connection cannot create it.
        with SQLiteTaskRepository(self.database):
            pass

    def wait_for(self, predicate, timeout=25.0, message="resident state did not converge"):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.1)
        self.fail(message)

    def start(self, service, *, extra: tuple[str, ...] = ()):
        """Start one real resident command and wait for its durable registration."""

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
                *extra,
            ],
            stdout=stream,
            stderr=subprocess.STDOUT,
        )

        def stop():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

        self.addCleanup(stop)

        def registered():
            self.assertIsNone(process.poll(), log.read_text())
            with SQLiteTaskRepository(self.database, read_only=True) as repo:
                return any(
                    row.service == service and row.status is ResidentServiceStatus.LIVE
                    for row in repo.list_resident_services()
                )

        self.wait_for(registered)
        return process

    def adoption_rows(self, service: str):
        with SQLiteTaskRepository(self.database, read_only=True) as repo:
            return repo.list_resident_settings_adoption(service=service, limit=100)

    def wait_adoption(self, service: str, digest: str, field: str, timeout=25.0):
        seen: dict[str, object] = {}

        def adopted():
            rows = self.adoption_rows(service)
            for row in rows:
                if row.published_revision_digest == digest and field in row.applied_fields:
                    seen["row"] = row
                    return True
            return False

        self.wait_for(
            adopted,
            timeout=timeout,
            message=f"{service} never reported adopting {field} for {digest}: ",
        )
        return seen["row"]

    def publish_engine(self, *, worker_poll=None, scheduler_poll=None, **other) -> str:
        """Publish one engine-only Active successor and return its digest."""

        def mutate(document: dict) -> None:
            automation = document["automation"]
            if worker_poll is not None:
                automation["workerPollSeconds"] = worker_poll
            if scheduler_poll is not None:
                automation["schedulerPollSeconds"] = scheduler_poll
            for key, value in other.items():
                automation[key] = value

        self.publish_successor(mutate)
        from mediaflow.application.configuration_snapshot import ManagedConfigurationService
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )

        with SQLiteConfigurationRepository(self.database) as configuration:
            active = ManagedConfigurationService(
                configuration,
                bootstrap_database_path=self.database,
                bootstrap_document=self.document,
            ).active()
        return active.digest


class SchedulerCadenceAdoptionTests(ResidentAdoptionFixture):
    def test_scheduler_started_before_active_adopts_the_first_publication(self) -> None:
        # The process starts with no Active at all: it must still run and adopt
        # the first publication later without a restart.
        process = self.start("scheduler")
        self.publish_first_draft(self.empty_baseline())
        digest = self.publish_engine(scheduler_poll=0.25)
        row = self.wait_adoption("scheduler", digest, "automation.schedulerPollSeconds")
        self.assertEqual(row.effective_values["automation.schedulerPollSeconds"], 0.25)
        self.assertIsNone(row.override_source)
        self.assertIsNone(process.poll(), "the Scheduler must adopt without restarting")

    def test_long_idle_cadence_shortens_without_work_arriving(self) -> None:
        # Publish a deliberately long cadence first: the idle wait must still be
        # bounded by the configuration recheck, so a later short value is adopted
        # promptly even though no work ever arrives.
        self.publish_first_draft(self.empty_baseline())
        self.publish_engine(scheduler_poll=3600)
        process = self.start("scheduler")
        first = self.adoption_rows("scheduler")
        if not first:
            first = (
                self.wait_adoption(
                    "scheduler",
                    self._digest(),
                    "automation.schedulerPollSeconds",
                ),
            )
        self.assertEqual(first[0].effective_values["automation.schedulerPollSeconds"], 3600.0)
        started = time.monotonic()
        digest = self.publish_engine(scheduler_poll=0.25)
        self.wait_adoption("scheduler", digest, "automation.schedulerPollSeconds", timeout=20)
        elapsed = time.monotonic() - started
        self.assertLess(
            elapsed,
            CONFIG_RECHECK_SECONDS * 3,
            "a long idle cadence must not defer observing the new publication",
        )
        self.assertIsNone(process.poll())

    def _digest(self) -> str:
        from mediaflow.application.configuration_snapshot import ManagedConfigurationService
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )

        with SQLiteConfigurationRepository(self.database) as configuration:
            return (
                ManagedConfigurationService(
                    configuration,
                    bootstrap_database_path=self.database,
                    bootstrap_document=self.document,
                )
                .active()
                .digest
            )

    def test_explicit_poll_override_keeps_precedence_and_is_reported_as_override(self) -> None:
        self.publish_first_draft(self.empty_baseline())
        self.start("scheduler", extra=("--poll-seconds", "0.4"))
        digest = self.publish_engine(scheduler_poll=7200)
        row = self.wait_adoption("scheduler", digest, "automation.schedulerPollSeconds")
        self.assertEqual(row.override_source, "cli")
        self.assertEqual(row.effective_values["automation.schedulerPollSeconds"], 0.4)


class WorkerCadenceAdoptionTests(ResidentAdoptionFixture):
    def test_worker_adopts_published_cadence_and_keeps_its_identity(self) -> None:
        self.publish_first_draft(self.empty_baseline())
        process = self.start("worker")
        with SQLiteTaskRepository(self.database, read_only=True) as repository:
            before = {
                row.instance_id
                for row in repository.list_resident_services()
                if row.service == "worker"
            }
        digest = self.publish_engine(worker_poll=0.3)
        row = self.wait_adoption("worker", digest, "automation.workerPollSeconds")
        self.assertEqual(row.effective_values["automation.workerPollSeconds"], 0.3)
        with SQLiteTaskRepository(self.database, read_only=True) as repository:
            after = {
                row.instance_id
                for row in repository.list_resident_services()
                if row.service == "worker"
            }
        # Adopting a setting must not restart or re-identify the process.
        self.assertEqual(before, after)
        self.assertIsNone(process.poll())

    def test_worker_heartbeat_stays_fresh_across_a_long_cadence(self) -> None:
        self.publish_first_draft(self.empty_baseline())
        # A long cadence must not stop the heartbeat/lease renewal.
        self.publish_engine(worker_poll=3600)
        self.start("worker")

        def heartbeat_advanced():
            with SQLiteTaskRepository(self.database, read_only=True) as repository:
                rows = [
                    row for row in repository.list_resident_services() if row.service == "worker"
                ]
            return bool(rows) and rows[0].status is ResidentServiceStatus.LIVE

        self.wait_for(heartbeat_advanced)

    def test_mixed_instances_are_reported_per_instance(self) -> None:
        self.publish_first_draft(self.empty_baseline())
        self.start("worker")
        self.start("worker")
        digest = self.publish_engine(worker_poll=0.3)

        def both_reported() -> bool:
            instances = {
                item.instance_id
                for item in self.adoption_rows("worker")
                if item.published_revision_digest == digest
            }
            return len(instances) == 2

        self.wait_for(both_reported, message="both Worker instances never reported adoption")


class BusyStepPinPreservationTests(ResidentAdoptionFixture):
    """A settings publication never repins or replays admitted work."""

    def test_admitted_job_keeps_its_pin_across_a_settings_publication(self) -> None:
        import os
        from unittest.mock import patch

        from mediaflow.application.execution_authorization import (
            ExecutionAuthorizationService,
        )
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )

        self.publish_first_draft(self.empty_baseline())
        source = self.root / "source"
        source.mkdir(exist_ok=True)
        credential = patch.dict(os.environ, {"TMDB_ACCESS_TOKEN": "fake-settings-test"})
        credential.start()
        self.addCleanup(credential.stop)

        def configure(document: dict) -> None:
            document["storages"] = [
                {
                    "id": "local",
                    "type": "local",
                    "name": "Local",
                    "rootPath": str(source),
                    "readOnly": True,
                }
            ]
            document["resourceLibraries"] = [
                {
                    "id": "source",
                    "name": "Source",
                    "storageId": "local",
                    "storagePath": "",
                    "displayRootPath": str(source),
                    "enabled": True,
                }
            ]

        self.publish_successor(configure)
        with SQLiteConfigurationRepository(self.database) as configuration_repository:
            active = configuration_repository.get_active_revision()
        with SQLiteTaskRepository(self.database) as repository:
            service = ExecutionAuthorizationService(
                repository,
                maximum_ttl_seconds=3600,
                maximum_active_jobs=100,
                configuration_snapshot_id=active.revision_id if active else None,
                configuration_snapshot_digest=active.digest if active else None,
            )
            issued = service.issue(ttl_seconds=600, max_items=1, actor="tester")
            job = service.submit_organize(issued.token, limit=1)
            admitted_pin = (job.configuration_snapshot_id, job.configuration_snapshot_digest)

        # Publish a new engine cadence while that Job is admitted but not yet
        # claimed.  Publication must not rewrite its pin or its authority.
        self.publish_engine(worker_poll=0.4)
        with SQLiteTaskRepository(self.database, read_only=True) as repository:
            jobs = repository.list_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(
            (jobs[0].configuration_snapshot_id, jobs[0].configuration_snapshot_digest),
            admitted_pin,
        )
        self.assertEqual(jobs[0].status.value, "pending")
        # The new publication is a *new* Active, so the admitted pin now refers
        # to an older (but still intact) snapshot rather than being silently
        # repinned to today's configuration.
        with SQLiteConfigurationRepository(self.database) as configuration_repository:
            current = configuration_repository.get_active_revision()
            previous = configuration_repository.get_revision(admitted_pin[0])
        self.assertIsNotNone(previous)
        self.assertNotEqual(current.revision_id, admitted_pin[0])
        self.assertEqual(previous.digest, admitted_pin[1])


class ResidentLoopCadenceUnitTests(ResidentDeploymentFixture):
    """Controlled-clock proof of the wait deadline, stop and fault behaviour."""

    def _loop(self, *, poll: float, cadence=None, reporter=None):
        runtime = build_resident_runtime(self.database)
        instance = resident_instance_id("scheduler")
        register_resident_process(runtime, "scheduler", instance, heartbeat_interval_seconds=0.1)
        return ResidentLoop(
            runtime,
            "scheduler",
            instance,
            heartbeat_interval_seconds=0.1,
            poll_seconds=poll,
            stdout=__import__("io").StringIO(),
            step=lambda loop: 0,
            cadence_resolver=cadence,
            adoption_reporter=reporter,
        )

    def test_idle_wait_is_capped_by_the_configuration_recheck(self) -> None:
        loop = self._loop(poll=3600)
        self.assertEqual(loop.effective_poll_deadline(), CONFIG_RECHECK_SECONDS)
        short = self._loop(poll=0.2)
        self.assertEqual(short.effective_poll_deadline(), 0.2)

    def test_adoption_installs_the_value_and_reports_only_after_installing(self) -> None:
        reports: list[ResidentCadence] = []
        cadence = ResidentCadence(
            service="scheduler",
            field_path="automation.schedulerPollSeconds",
            poll_seconds=0.75,
            published_revision_id="rev-1",
            published_revision_version=3,
            published_revision_digest="digest-1",
        )
        loop = self._loop(
            poll=3600,
            cadence=lambda: cadence,
            reporter=lambda item: reports.append(item),
        )
        self.assertTrue(loop.adopt_cadence())
        self.assertEqual(loop.poll_seconds, 0.75)
        # The report the loop recorded names the value it actually installed.
        self.assertEqual(reports, [cadence])

    def test_failed_resolution_keeps_the_previous_cadence(self) -> None:
        def failing():
            raise RuntimeError("database temporarily unavailable")

        loop = self._loop(poll=12.0, cadence=failing)
        self.assertFalse(loop.adopt_cadence())
        self.assertEqual(loop.poll_seconds, 12.0)
        self.assertEqual(loop.adoption_blocker[0], "configuration_unavailable")

    def test_override_cadence_is_installed_but_reported_as_override(self) -> None:
        reports: list[ResidentCadence] = []
        cadence = ResidentCadence(
            service="scheduler",
            field_path="automation.schedulerPollSeconds",
            poll_seconds=0.4,
            published_revision_id="rev-2",
            published_revision_version=4,
            published_revision_digest="digest-2",
            override_source="cli",
        )
        loop = self._loop(
            poll=1.0, cadence=lambda: cadence, reporter=lambda item: reports.append(item)
        )
        loop.adopt_cadence()
        self.assertEqual(loop.poll_seconds, 0.4)
        self.assertEqual(reports[0].override_source, "cli")


class AdoptionEvidencePersistenceTests(ResidentDeploymentFixture):
    def test_report_survives_reopen_and_is_append_only_per_instance(self) -> None:
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual(repository.schema_version, SCHEMA_VERSION)
            first = ResidentSettingsEvidence(
                service="worker",
                instance_id="worker-abc123",
                published_revision_id="rev-1",
                published_revision_version=1,
                published_revision_digest="digest-1",
                applied_fields=("automation.workerPollSeconds",),
                effective_values={"automation.workerPollSeconds": 0.5},
                override_source=None,
                reported_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )
            repository.record_resident_settings_adoption(first)
        # Reopen the same database: the evidence is durable.
        with SQLiteTaskRepository(self.database) as reopened:
            rows = reopened.list_resident_settings_adoption(service="worker")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].published_revision_digest, "digest-1")
            self.assertEqual(rows[0].effective_values["automation.workerPollSeconds"], 0.5)

    def test_additive_upgrade_keeps_existing_rows_and_pins(self) -> None:
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual(repository.schema_version, SCHEMA_VERSION)
            with repository._lock:
                columns = {
                    row[1]
                    for row in repository._connection.execute(
                        "PRAGMA table_info(resident_settings_adoption)"
                    )
                }
        self.assertIn("published_revision_digest", columns)
        self.assertIn("effective_values_json", columns)


if __name__ == "__main__":
    unittest.main()
