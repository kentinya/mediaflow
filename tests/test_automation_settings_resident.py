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
from datetime import UTC, datetime

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


class SchedulerBusinessPollTests(ResidentAdoptionFixture):
    """B43.4-R3/R4 proved by a real `scheduler run` process.

    The production Scheduler step writes its own bounded wait state on every
    *business* poll, so the durable ``updated_at`` of that row is a real
    observable of the loop's tick cadence — not a self-reported value and not an
    HTTP echo.  With a 30s published cadence, configuration rechecks may wake
    every <=5s but must not produce extra steps.
    """

    def wait_state_times(self, service: str, instance_id: str):
        with SQLiteTaskRepository(self.database, read_only=True) as repository:
            state = repository.get_resident_service_wait_state(service, instance_id)
        return state.updated_at if state is not None else None

    def scheduler_instance(self) -> str:
        with SQLiteTaskRepository(self.database, read_only=True) as repository:
            rows = [
                row
                for row in repository.list_resident_services()
                if row.service == "scheduler" and row.status is ResidentServiceStatus.LIVE
            ]
        self.assertTrue(rows, "the real Scheduler never registered")
        return rows[0].instance_id

    def test_long_cadence_is_not_shortened_by_configuration_rechecks(self) -> None:
        self.publish_first_draft(self.empty_baseline())
        self.publish_engine(scheduler_poll=30)
        process = self.start("scheduler")
        instance = self.scheduler_instance()

        observed: dict[float, object] = {}

        def record() -> bool:
            value = self.wait_state_times("scheduler", instance)
            if value is not None:
                observed[value.timestamp()] = value
            return True

        self.wait_for(record, timeout=10.0, message="the Scheduler never wrote its wait state")
        first = self.wait_state_times("scheduler", instance)
        self.assertIsNotNone(first)
        started = time.monotonic()
        # Watch a full 5s+ recheck window: at least one configuration wake must
        # happen, and it must not produce a business step.
        while time.monotonic() - started < 8.0:
            record()
            time.sleep(0.2)
        latest = self.wait_state_times("scheduler", instance)
        self.assertIsNone(process.poll(), "the Scheduler must stay running")
        self.assertEqual(
            latest,
            first,
            "a configuration recheck must not run the Scheduler step early",
        )

    def test_unchanged_live_consumer_keeps_refreshing_its_own_report(self) -> None:
        """B43.4-R4: an unchanged but healthy consumer must stay reported.

        Readback treats a report older than ``max(3 * heartbeat, 10s)`` as stale,
        so a live-but-idle consumer used to decay into "stale" with no
        publication change.  The owning process now re-reports on the bounded
        refresh; observed here from its own durable row.
        """

        self.publish_first_draft(self.empty_baseline())
        digest = self.publish_engine(scheduler_poll=60)
        self.start("scheduler")
        row = self.wait_adoption("scheduler", digest, "automation.schedulerPollSeconds")
        first_reported = row.reported_at
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            rows = [
                item
                for item in self.adoption_rows("scheduler")
                if item.published_revision_digest == digest
            ]
            if rows and (rows[0].reported_at - first_reported).total_seconds() >= 5.0:
                # A second report for the *same*, unchanged publication.  The
                # controlled-clock case proves the refresh gap stays <= 5.5s,
                # which is inside readback's staleness window.
                return
            time.sleep(0.25)
        self.fail("the unchanged live Scheduler never refreshed its adoption report")


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

    def test_worker_heartbeat_advances_across_a_long_cadence(self) -> None:
        """B43.4 verification note: liveness alone does not prove advancement.

        A 3600s cadence must still renew the heartbeat on its own bounded
        interval; the assertion is that the durable ``last_heartbeat_at`` moves
        forward while the loop is idle, not merely that the row reads "live".
        """

        self.publish_first_draft(self.empty_baseline())
        # A long cadence must not stop the heartbeat/lease renewal.
        self.publish_engine(worker_poll=3600)
        self.start("worker")

        def heartbeat_timestamp():
            with SQLiteTaskRepository(self.database, read_only=True) as repository:
                rows = [
                    row for row in repository.list_resident_services() if row.service == "worker"
                ]
            if not rows:
                return None
            self.assertIs(rows[0].status, ResidentServiceStatus.LIVE)
            return rows[0].last_heartbeat_at

        first = None

        def first_beat() -> bool:
            nonlocal first
            first = heartbeat_timestamp()
            return first is not None

        self.wait_for(first_beat, timeout=10.0, message="the Worker never registered")
        advanced: dict[str, object] = {}

        def beat_advanced() -> bool:
            current = heartbeat_timestamp()
            if current is not None and first is not None and current > first:
                advanced["value"] = current
                return True
            return False

        self.wait_for(
            beat_advanced,
            timeout=20.0,
            message="the idle Worker's heartbeat never advanced under a long cadence",
        )

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


class BusyStepAdoptionBoundaryTests(ResidentAdoptionFixture):
    """B43.4-R3/S4/S6: adoption waits for the existing safe boundary.

    A real :class:`ResidentLoop` runs a step that stays busy while a genuine
    managed publication happens.  The loop may not repin, replay or cancel
    admitted work, and it may not change its cadence in the middle of that step;
    it adopts at the next boundary.  The admitted Job's immutable pin is observed
    before and after.
    """

    def test_publication_during_a_busy_step_waits_for_the_boundary(self) -> None:
        import io

        from mediaflow.application.resident_runtime import resident_cadence_adoption
        from mediaflow.domain.automation import (
            AutomationCommand,
            AutomationJob,
            AutomationJobStatus,
        )
        from mediaflow.final_cli import _resident_published_cadence_resolver

        self.publish_first_draft(self.empty_baseline())
        self.publish_engine(scheduler_poll=1.0)

        runtime = build_resident_runtime(self.database)
        instance = resident_instance_id("scheduler")
        register_resident_process(runtime, "scheduler", instance, heartbeat_interval_seconds=5.0)
        resolver, reporter = resident_cadence_adoption(
            runtime,
            "scheduler",
            instance,
            field_path="automation.schedulerPollSeconds",
            published_resolver=_resident_published_cadence_resolver(str(self.config), "scheduler"),
        )
        with SQLiteTaskRepository(self.database) as repository:
            repository.create_job(
                AutomationJob(
                    "job-busy-1",
                    AutomationCommand.ORGANIZE,
                    AutomationJobStatus.PENDING,
                    datetime.now(UTC),
                    datetime.now(UTC),
                    limit=1,
                )
            )
            admitted = repository.list_jobs()[0]
            admitted_pin = (
                admitted.configuration_snapshot_id,
                admitted.configuration_snapshot_digest,
            )

        observations: dict[str, object] = {}

        def step(loop) -> int:
            observations["cadence_at_step_entry"] = loop.poll_seconds
            # A genuine managed publication while this step is busy.
            self.publish_engine(scheduler_poll=3.0)
            observations["cadence_inside_step"] = loop.poll_seconds
            loop.clear_waiting()
            return 0

        loop = ResidentLoop(
            runtime,
            "scheduler",
            instance,
            heartbeat_interval_seconds=5.0,
            poll_seconds=1.0,
            stdout=io.StringIO(),
            step=step,
            cadence_resolver=resolver,
            adoption_reporter=reporter,
        )

        def stop() -> bool:
            return loop.poll_seconds == 3.0 and "cadence_inside_step" in observations

        loop.run(stop, lambda seconds: time.sleep(min(seconds, 0.1)))
        # Inside the busy step the installed cadence never changed; adoption
        # happened only at the next safe boundary.
        self.assertEqual(observations["cadence_at_step_entry"], 1.0)
        self.assertEqual(observations["cadence_inside_step"], 1.0)
        self.assertEqual(loop.poll_seconds, 3.0)
        self.assertIsNotNone(loop.applied_cadence)
        self.assertEqual(loop.applied_cadence.poll_seconds, 3.0)
        with SQLiteTaskRepository(self.database, read_only=True) as repository:
            jobs = repository.list_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(
            (jobs[0].configuration_snapshot_id, jobs[0].configuration_snapshot_digest),
            admitted_pin,
        )
        self.assertEqual(jobs[0].status, AutomationJobStatus.PENDING)
        self.assertIsNone(jobs[0].claim_token)


class _ResidentLoopFixture(ResidentDeploymentFixture):
    """Builds a real ResidentLoop over this isolated deployment."""

    def _loop(self, *, poll: float, cadence=None, reporter=None, clock=None, step=None):
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
            step=step or (lambda loop: 0),
            cadence_resolver=cadence,
            adoption_reporter=reporter,
            monotonic=clock,
        )


class ResidentLoopCadenceUnitTests(_ResidentLoopFixture):
    """Controlled-clock proof of the wait deadline, stop and fault behaviour."""

    def test_idle_wait_is_capped_by_the_configuration_recheck(self) -> None:
        loop = self._loop(poll=3600)
        self.assertEqual(loop.effective_poll_deadline(), CONFIG_RECHECK_SECONDS)
        self.assertEqual(loop.business_poll_deadline(), 3600)
        short = self._loop(poll=0.2)
        self.assertEqual(short.effective_poll_deadline(), 0.2)
        self.assertEqual(short.business_poll_deadline(), 0.2)

    def test_configuration_wakes_do_not_become_business_polls(self) -> None:
        """B43.4-R3: a bounded recheck must never tick/claim early.

        A real ``scheduler run`` configured 60s performed four actual
        ``IntervalScheduler.tick`` calls at ~5s because the capped sleep fed the
        step again.  This controlled-clock proof runs the same loop shape with a
        step counter and a real sleeping clock: the step must run once per
        business cadence, not once per configuration wake.
        """

        clock = _FakeClock()
        steps: list[float] = []
        sleeps: list[float] = []

        def step(loop) -> int:
            steps.append(clock.now)
            return 0

        loop = self._loop(poll=60.0, clock=clock.advance_getter(), step=step)

        def stop() -> bool:
            return clock.now >= 130.0

        def sleep(seconds: float) -> None:
            sleeps.append(seconds)
            clock.advance(seconds)

        loop.run(stop, sleep)
        # Step times: 0s, 60s, 120s.  The 5s configuration wakes in between must
        # not have produced extra steps.
        self.assertEqual([round(item) for item in steps], [0, 60, 120])
        self.assertTrue(all(item <= CONFIG_RECHECK_SECONDS for item in sleeps))
        self.assertGreater(len(sleeps), len(steps))

    def test_shorter_adoption_shortens_a_pending_long_wait(self) -> None:
        clock = _FakeClock()
        steps: list[float] = []
        cadence = ResidentCadence(
            service="scheduler",
            field_path="automation.schedulerPollSeconds",
            poll_seconds=2.0,
            published_revision_id="rev-short",
            published_revision_version=2,
            published_revision_digest="digest-short",
        )
        resolves = {"current": None}

        def resolver():
            return resolves["current"]

        def step(loop) -> int:
            steps.append(clock.now)
            if len(steps) == 1:
                # The publication arrives after the first long-cadence step.
                resolves["current"] = cadence
            return 0

        loop = self._loop(poll=600.0, clock=clock.advance_getter(), cadence=resolver, step=step)

        def stop() -> bool:
            return clock.now > 30.0

        def sleep(seconds: float) -> None:
            clock.advance(seconds)

        loop.run(stop, sleep)
        # The 600s wait must not be honoured: the 2s adoption shortens it.
        self.assertEqual(
            [round(item) for item in steps],
            [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30],
        )

    def test_unchanged_consumer_refreshes_its_own_report(self) -> None:
        """B43.4-R4: a live, unchanged consumer must not decay to stale."""

        clock = _FakeClock()
        reports: list[tuple[float, ResidentSettingsEvidence]] = []
        cadence = ResidentCadence(
            service="scheduler",
            field_path="automation.schedulerPollSeconds",
            poll_seconds=1.0,
            published_revision_id="rev-1",
            published_revision_version=1,
            published_revision_digest="digest-1",
        )

        def reporter(item: ResidentCadence) -> None:
            reports.append(
                (
                    clock.now,
                    ResidentSettingsEvidence(
                        service="scheduler",
                        instance_id="scheduler-x",
                        published_revision_id=item.published_revision_id,
                        published_revision_version=item.published_revision_version,
                        published_revision_digest=item.published_revision_digest,
                        applied_fields=(item.field_path,),
                        effective_values={item.field_path: item.poll_seconds},
                        override_source=item.override_source,
                        reported_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
                    ),
                )
            )

        loop = self._loop(
            poll=1.0, clock=clock.advance_getter(), cadence=lambda: cadence, reporter=reporter
        )

        def stop() -> bool:
            return clock.now >= 25.0

        def sleep(seconds: float) -> None:
            clock.advance(seconds)

        loop.run(stop, sleep)
        times = [item[0] for item in reports]
        # The same unchanged publication is re-reported on the bounded refresh,
        # so readback never expires a live consumer that simply had nothing new.
        self.assertGreaterEqual(len(reports), 3)
        gaps = [b - a for a, b in zip(times, times[1:], strict=False)]
        self.assertTrue(all(gap <= 5.5 for gap in gaps), gaps)

    def test_failed_report_is_retried_for_the_unchanged_publication(self) -> None:
        """B43.4-R4: a failed report write must not be remembered as adopted."""

        clock = _FakeClock()
        attempts: list[float] = []
        cadence = ResidentCadence(
            service="scheduler",
            field_path="automation.schedulerPollSeconds",
            poll_seconds=1.0,
            published_revision_id="rev-1",
            published_revision_version=1,
            published_revision_digest="digest-1",
        )

        def reporter(item: ResidentCadence) -> None:
            attempts.append(clock.now)
            raise RuntimeError("shared database briefly unavailable")

        loop = self._loop(
            poll=1.0, clock=clock.advance_getter(), cadence=lambda: cadence, reporter=reporter
        )
        loop.adopt_cadence()
        # The cadence is installed, but it is never acknowledged as adopted and
        # the next boundary retries the write for the *same* publication.
        self.assertEqual(loop.poll_seconds, 1.0)
        self.assertIsNone(loop.applied_cadence)
        self.assertEqual(loop.adoption_report_failures, 1)
        clock.advance(1.0)
        loop.adopt_cadence()
        self.assertEqual(loop.adoption_report_failures, 2)
        self.assertEqual(attempts, [0.0, 1.0])


class NotificationWorkerTimingTests(_ResidentLoopFixture):
    """B43.4-R3: the changed wake bound must not alter Notification timing.

    The shared loop is also the Notification Worker's loop, which owns no
    engine cadence.  Its business poll deadline must therefore be exactly the
    configured notification interval, with only bounded configuration wakes in
    between and no extra steps.
    """

    def test_notification_loop_preserves_its_business_cadence(self) -> None:
        clock = _FakeClock()
        steps: list[float] = []

        def step(loop) -> int:
            steps.append(clock.now)
            return 0

        loop = self._loop(poll=45.0, clock=clock.advance_getter(), step=step)

        def stop() -> bool:
            return clock.now > 100.0

        def sleep(seconds: float) -> None:
            clock.advance(seconds)

        loop.run(stop, sleep)
        self.assertEqual([round(item) for item in steps], [0, 45, 90])


class _FakeClock:
    """A monotonic clock a test advances explicitly, so nothing really sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def advance(self, seconds: float) -> None:
        self.now += max(0.0, float(seconds))

    def advance_getter(self):
        def value() -> float:
            return self.now

        return value


class ResidentLoopAdoptionUnitTests(_ResidentLoopFixture):
    """Controlled-clock proof that the loop installs *then* reports.

    These are ordinary discovered cases (B43.4 review note): they belong on a
    ``TestCase``, not on the clock helper, so their assertions are real evidence
    rather than silently uncollected code.
    """

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

    def test_additive_upgrade_from_the_prior_schema_keeps_rows_and_pins(self) -> None:
        """B43.4 verification note: the upgrade must start at the *prior* schema.

        The previous case only inspected a freshly created schema-50 database.
        This one starts from a genuine schema-49 shape (the table did not exist),
        with durable work, a pin and a resident registration already present, and
        proves the additive upgrade creates only the new evidence table.
        """

        from mediaflow.domain.automation import (
            AutomationCommand,
            AutomationJob,
            AutomationJobStatus,
        )

        self.publish_first_draft(self.empty_baseline())
        runtime = build_resident_runtime(self.database)
        register_resident_process(
            runtime, "worker", "worker-prior-1", heartbeat_interval_seconds=5.0
        )
        with SQLiteTaskRepository(self.database) as repository:
            self.assertEqual(repository.schema_version, SCHEMA_VERSION)
            repository.create_job(
                AutomationJob(
                    "job-prior-schema-1",
                    AutomationCommand.ORGANIZE,
                    AutomationJobStatus.PENDING,
                    datetime.now(UTC),
                    datetime.now(UTC),
                    limit=1,
                )
            )
            with repository._lock:
                # Simulate the supported *prior* schema: the additive table does
                # not exist yet and the recorded version is one behind.
                repository._connection.execute("DROP TABLE resident_settings_adoption")
                repository._connection.execute(
                    "UPDATE schema_version SET version=? WHERE component='runtime'",
                    (SCHEMA_VERSION - 1,),
                )
        with SQLiteTaskRepository(self.database) as upgraded:
            # Reopening performs the additive upgrade and nothing else.
            self.assertEqual(upgraded.schema_version, SCHEMA_VERSION)
            jobs = upgraded.list_jobs()
            self.assertEqual([item.job_id for item in jobs], ["job-prior-schema-1"])
            self.assertEqual(jobs[0].status, AutomationJobStatus.PENDING)
            self.assertIsNotNone(upgraded.get_resident_service("worker", "worker-prior-1"))
            self.assertEqual(upgraded.list_resident_settings_adoption(service="worker"), ())
            with upgraded._lock:
                columns = {
                    row[1]
                    for row in upgraded._connection.execute(
                        "PRAGMA table_info(resident_settings_adoption)"
                    )
                }
        self.assertIn("published_revision_digest", columns)
        self.assertIn("effective_values_json", columns)


class CurrentConsumerMembershipTests(ResidentAdoptionFixture):
    """A43-01 — a graceful restart must not leave the old identity in charge.

    The reproduction B confirmed: after a real graceful Scheduler restart both
    live instances had adopted, yet the aggregate stayed at 1/2 because the
    historical *stopped predecessor* still vetoed success.  These cases assert
    the required behaviour through the same supported entries: the real
    ``worker run`` / ``scheduler run`` commands, the real settings read model and
    the real WSGI settings route.  Nothing here deletes or rewrites a
    registration row; the retained lifecycle stays exactly as it was.
    """

    def settings_document(self) -> dict:
        """Read the operator document through the WSGI settings entry."""

        import io
        import json

        from mediaflow.application.configuration_snapshot import ManagedConfigurationService
        from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )
        from mediaflow.interfaces.service_api import MediaFlowApi

        with (
            SQLiteConfigurationRepository(self.database) as configuration,
            SQLiteTaskRepository(self.database) as repository,
        ):
            api = MediaFlowApi(
                repository,
                None,
                principals=(
                    ResolvedApiPrincipal("admin", "settings-read-token", frozenset(ApiPermission)),
                ),
                configuration_service=ManagedConfigurationService(
                    configuration,
                    bootstrap_database_path=self.database,
                    bootstrap_document=self.document,
                ),
                bootstrap_document=self.document,
            )
            statuses: list[str] = []
            environ = {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": "/api/v1/operations/automation/settings",
                "QUERY_STRING": "",
                "CONTENT_LENGTH": "0",
                "wsgi.input": io.BytesIO(b""),
                "REMOTE_ADDR": "127.0.0.1",
                "HTTP_AUTHORIZATION": "Bearer settings-read-token",
            }
            raw = b"".join(api(environ, lambda status, headers: statuses.append(status)))
        self.assertTrue(statuses and statuses[0].startswith("200"), (statuses, raw[:2000]))
        return json.loads(raw)

    def stop_gracefully(self, process) -> None:
        """Stop one real resident command the ordinary way (SIGTERM)."""

        self.assertIsNone(process.poll(), "the resident process died before it was stopped")
        process.terminate()
        self.assertEqual(process.wait(timeout=25), 0)

    def jobs(self) -> list:
        with SQLiteTaskRepository(self.database, read_only=True) as repository:
            return list(repository.list_jobs())

    def test_graceful_scheduler_restart_restores_current_adoption(self) -> None:
        self.publish_first_draft(self.empty_baseline())
        digest = self.publish_engine(worker_poll=0.4, scheduler_poll=0.4)
        # Both real cadence consumers run, so the deployment-wide claim is
        # observable both before and after the restart.
        self.start("worker")
        first = self.start("scheduler")
        self.wait_adoption("worker", digest, "automation.workerPollSeconds")
        self.wait_adoption("scheduler", digest, "automation.schedulerPollSeconds")
        before = self.settings_document()
        self.assertTrue(before["adoption"]["allAdopted"], before["adoption"])
        predecessors = {
            item["instanceId"] for item in before["consumers"]["scheduler"]["instances"]
        }
        self.assertEqual(len(predecessors), 1)

        # A normal graceful stop leaves the predecessor retained and stopped.
        self.stop_gracefully(first)
        stopped = self.settings_document()
        # Only the Scheduler lost its live consumer, so the deployment-wide
        # claim is honestly false while the still-live Worker remains adopted.
        self.assertFalse(stopped["adoption"]["allAdopted"])
        self.assertTrue(stopped["consumers"]["worker"]["adopted"])
        self.assertEqual(stopped["consumers"]["scheduler"]["instances"], [])
        self.assertEqual(stopped["consumers"]["scheduler"]["historyCount"], 1)
        self.assertEqual(stopped["consumers"]["scheduler"]["history"][0]["liveness"], "stopped")

        # The fresh replacement restores current service and collective adoption
        # with no operator workaround — and the retained identity is still there.
        self.start("scheduler")
        self.wait_for(
            lambda: self.settings_document()["adoption"]["allAdopted"],
            message="the fresh Scheduler replacement never restored current adoption",
        )
        after = self.settings_document()
        current = after["consumers"]["scheduler"]["instances"]
        self.assertEqual(len(current), 1)
        self.assertNotIn(current[0]["instanceId"], predecessors)
        self.assertEqual(current[0]["status"], "adopted")
        # History is diagnostic only: it cannot be mistaken for a live adopter.
        self.assertEqual(after["consumers"]["scheduler"]["historyCount"], 1)
        self.assertEqual(
            [item["instanceId"] for item in after["consumers"]["scheduler"]["history"]],
            sorted(predecessors),
        )
        self.assertIn(
            "retained, stopped registration",
            after["consumers"]["scheduler"]["history"][0]["nextAction"],
        )
        # The still-running Worker keeps its own single current instance, so a
        # Scheduler restart neither hides nor moves it.
        self.assertEqual(len(after["consumers"]["worker"]["instances"]), 1)
        self.assertEqual(after["consumers"]["worker"]["historyCount"], 0)
        # Nothing was admitted or replayed by any of these reads/restarts.
        self.assertEqual(self.jobs(), [])
        # Every registration row is still durable after reopening the database.
        with SQLiteTaskRepository(self.database) as reopened:
            retained = [
                row for row in reopened.list_resident_services() if row.service == "scheduler"
            ]
        self.assertEqual(len(retained), 2)

    def test_two_live_worker_replicas_must_both_adopt(self) -> None:
        self.publish_first_draft(self.empty_baseline())
        digest = self.publish_engine(worker_poll=0.3)
        self.start("worker")
        self.start("worker")
        self.wait_for(
            lambda: len(self.settings_document()["consumers"]["worker"]["instances"]) == 2,
            message="both live Worker replicas never appeared as current consumers",
        )
        with SQLiteTaskRepository(self.database, read_only=True) as repository:
            live = {
                row.instance_id
                for row in repository.list_resident_services()
                if row.service == "worker"
            }
        for instance in live:
            self.wait_adoption("worker", digest, "automation.workerPollSeconds")
        document = self.settings_document()
        worker = document["consumers"]["worker"]
        self.assertEqual({item["instanceId"] for item in worker["instances"]}, live)
        self.assertTrue(all(item["status"] == "adopted" for item in worker["instances"]))
        # The Scheduler never started, so its absence still blocks the
        # deployment-wide claim.
        self.assertFalse(document["adoption"]["allAdopted"])
        self.assertTrue(worker["adopted"])
        self.assertEqual(worker["historyCount"], 0)

    def test_override_on_one_live_replica_keeps_the_service_pending(self) -> None:
        self.publish_first_draft(self.empty_baseline())
        self.start("worker")
        self.start("worker", extra=("--poll-seconds", "0.4"))
        digest = self.publish_engine(worker_poll=0.3)

        def both_reported() -> bool:
            rows = self.adoption_rows("worker")
            return (
                len({row.instance_id for row in rows if row.published_revision_digest == digest})
                == 2
            )

        self.wait_for(both_reported, message="both Worker replicas never reported")
        document = self.settings_document()
        worker = document["consumers"]["worker"]
        self.assertEqual(len(worker["instances"]), 2)
        self.assertFalse(worker["adopted"])
        overrides = [item for item in worker["instances"] if item["status"] == "override"]
        self.assertEqual(len(overrides), 1)
        self.assertEqual(overrides[0]["overrideSource"], "cli")
        # A real live override keeps its own next action instead of being
        # collapsed into a generic "wait for the next boundary".
        self.assertIn("override", overrides[0]["nextAction"])

    def test_later_publication_is_pending_until_the_live_instance_adopts(self) -> None:
        self.publish_first_draft(self.empty_baseline())
        first_digest = self.publish_engine(scheduler_poll=0.4)
        self.start("scheduler")
        self.wait_adoption("scheduler", first_digest, "automation.schedulerPollSeconds")
        later = self.publish_engine(scheduler_poll=0.6)
        # The live instance is still current; its own report is what must move.
        pending = self.settings_document()
        scheduler = pending["consumers"]["scheduler"]
        self.assertEqual(len(scheduler["instances"]), 1)
        self.wait_adoption("scheduler", later, "automation.schedulerPollSeconds")
        adopted = self.settings_document()
        self.assertEqual(adopted["target"]["digest"], later)
        self.assertEqual(adopted["consumers"]["scheduler"]["instances"][0]["status"], "adopted")
        self.assertTrue(adopted["consumers"]["scheduler"]["adopted"])
        self.assertEqual(self.jobs(), [])


if __name__ == "__main__":
    unittest.main()
