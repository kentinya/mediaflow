from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from mediaflow.application.automation import (
    AutomationJobService,
    AutomationWorker,
    IntervalScheduler,
)
from mediaflow.application.automation_definition_occurrence import (
    AutomationDefinitionOccurrenceService,
)
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationDefinitionDueState,
    AutomationDefinitionOccurrence,
    AutomationJob,
    AutomationJobStatus,
    AutomationTaskDefinition,
    AutomationTaskRunMode,
    SchedulerConfigurationSnapshot,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.final_cli import _run_queued_workflow
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
DIGEST = "a" * 64


def definition(
    definition_id: str = "definition",
    *,
    resource: str = "resource",
    scope: str | None = "incoming",
    mode: AutomationTaskRunMode = AutomationTaskRunMode.SCAN_ONLY,
    interval: float | None = 60,
    cron: str | None = None,
    timezone: str | None = None,
    limit: int = 7,
    enabled: bool = True,
) -> AutomationTaskDefinition:
    return AutomationTaskDefinition(
        definition_id=definition_id,
        name=definition_id,
        resource_library_id=resource,
        source_scope=scope,
        mode=mode,
        interval_seconds=interval if cron is None else None,
        cron=cron,
        timezone=timezone,
        item_limit=limit,
        enabled=enabled,
    )


def snapshot(
    definitions: tuple[AutomationTaskDefinition, ...],
    *,
    revision_id: str = "revision-1",
    digest: str = DIGEST,
    version: int = 1,
    maximum_active_jobs: int = 10,
    resources: tuple[str, ...] = ("resource",),
    enabled_resources: tuple[str, ...] = ("resource",),
) -> SchedulerConfigurationSnapshot:
    return SchedulerConfigurationSnapshot(
        revision_id,
        digest,
        (),
        maximum_active_jobs,
        definitions,
        version,
        resources,
        enabled_resources,
    )


def count_rows(repository: SQLiteTaskRepository, table: str) -> int:
    return int(repository._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class AutomationDefinitionOccurrenceDomainTests(unittest.TestCase):
    def test_due_state_and_occurrence_contracts_are_bounded_and_pinned(self) -> None:
        value = definition(scope="safe")
        self.assertEqual(value.source_scope, "safe")
        self.assertEqual(len(value.definition_fingerprint), 64)
        state = AutomationDefinitionDueState(
            value.definition_id,
            NOW,
            NOW,
            last_occurrence_at=NOW,
            last_job_id="job-1",
            last_outcome="blocked",
            last_reason="queue capacity",
            last_next_action="wait and tick again",
            definition_fingerprint=value.definition_fingerprint,
        )
        self.assertEqual(state.last_reason, "queue capacity")
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            AutomationDefinitionDueState("definition", NOW, NOW, definition_fingerprint="short")
        with self.assertRaisesRegex(ValueError, "configuration digest"):
            AutomationDefinitionOccurrence(
                "occurrence",
                "definition",
                NOW,
                NOW,
                "job-1",
                value.definition_fingerprint,
                1,
                "revision-1",
                1,
                "short",
                AutomationTaskRunMode.SCAN_ONLY,
                "resource",
                "safe",
                7,
            )

    def test_interval_and_cron_due_ticks_pin_exact_identity_and_skip_future_due(self) -> None:
        interval = definition("interval", limit=11)
        cron = definition(
            "cron",
            scope=None,
            mode=AutomationTaskRunMode.SCAN_AND_PLAN,
            cron="30 1 * * *",
            timezone="America/New_York",
            limit=13,
        )
        future = definition("future")
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                tick_at = datetime(2026, 1, 1, 6, 30, tzinfo=UTC)
                repository.initialize_automation_definition_due_state(
                    future.definition_id,
                    tick_at + timedelta(minutes=5),
                    NOW,
                    definition_fingerprint=future.definition_fingerprint,
                )
                active = snapshot((interval, cron, future), version=4)
                scheduler = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: active,
                )
                emitted = scheduler.tick(tick_at)
                self.assertEqual({item.definition_id for item in emitted}, {"interval", "cron"})
                by_id = {item.definition_id: item for item in emitted}
                self.assertEqual(by_id["interval"].limit, 11)
                self.assertEqual(by_id["cron"].command, AutomationCommand.PREVIEW)
                self.assertEqual(by_id["cron"].source_scope, None)
                for job in emitted:
                    self.assertEqual(job.configuration_snapshot_id, "revision-1")
                    self.assertEqual(job.configuration_snapshot_digest, DIGEST)
                    self.assertEqual(job.configuration_snapshot_version, 4)
                    self.assertEqual(job.definition_version, 4)
                    self.assertEqual(
                        job.definition_fingerprint, by_id[job.definition_id].definition_fingerprint
                    )
                    self.assertIsNotNone(job.occurrence_at)
                self.assertIsNone(
                    repository.get_automation_definition_due_state("future").last_job_id
                )
                self.assertEqual(repository.list_automation_definition_occurrences("future"), ())

    def test_cron_due_in_timezone_ahead_of_utc_is_admitted_atomically(self) -> None:
        value = definition(
            "tokyo",
            scope=None,
            cron="0 9 * * *",
            timezone="Asia/Tokyo",
        )
        tick_at = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                emitted = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: snapshot((value,)),
                ).tick(tick_at)
                self.assertEqual([item.definition_id for item in emitted], ["tokyo"])
                self.assertEqual(
                    emitted[0].occurrence_at,
                    datetime(2026, 1, 1, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
                )

    def test_missed_interval_occurrences_are_coalesced_without_backlog_replay(self) -> None:
        value = definition("coalesced", interval=60)
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                current = [snapshot((value,))]
                scheduler = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: current[0],
                )
                scheduler.tick(NOW)
                emitted = scheduler.tick(NOW + timedelta(minutes=10))
                self.assertEqual(len(emitted), 1)
                occurrences = repository.list_automation_definition_occurrences("coalesced")
                self.assertEqual(len(occurrences), 2)
                self.assertEqual(occurrences[0].occurrence_at, NOW + timedelta(minutes=1))
                self.assertEqual(
                    repository.get_automation_definition_due_state("coalesced").next_run_at,
                    NOW + timedelta(minutes=11),
                )

    def test_cron_dst_transition_has_one_ambiguous_occurrence_and_skips_nonexistent_wall_time(
        self,
    ) -> None:
        spring = definition(
            "spring",
            scope=None,
            cron="30 2 * * *",
            timezone="America/New_York",
        )
        fall = definition(
            "fall",
            scope=None,
            cron="30 1 * * *",
            timezone="America/New_York",
        )
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                spring_snapshot = snapshot((spring,))
                scheduler = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: spring_snapshot,
                )
                spring_before_transition = datetime(2026, 3, 8, 6, 0, tzinfo=UTC)
                self.assertEqual(scheduler.tick(spring_before_transition), ())
                spring_state = repository.get_automation_definition_due_state("spring")
                self.assertEqual(
                    spring_state.next_run_at,
                    datetime(2026, 3, 9, 6, 30, tzinfo=UTC),
                )
                self.assertEqual(
                    scheduler.tick(datetime(2026, 3, 8, 7, 0, tzinfo=UTC)),
                    (),
                )
            with SQLiteTaskRepository(Path(directory, "fall.sqlite3")) as repository:
                fall_snapshot = snapshot((fall,))
                scheduler = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: fall_snapshot,
                )
                scheduler.tick(datetime(2026, 11, 1, 4, 0, tzinfo=UTC))
                emitted = scheduler.tick(datetime(2026, 11, 1, 7, 0, tzinfo=UTC))
                self.assertEqual(len(emitted), 1)
                self.assertEqual(
                    emitted[0].occurrence_at,
                    datetime(2026, 11, 1, 5, 30, tzinfo=UTC),
                )
                self.assertEqual(len(repository.list_automation_definition_occurrences("fall")), 1)


class AutomationDefinitionOccurrenceEmissionTests(unittest.TestCase):
    def test_capacity_disabled_and_resource_failures_are_durable_and_independent(self) -> None:
        capacity_one = snapshot(
            (definition("first"), definition("second")),
            maximum_active_jobs=1,
        )
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                scheduler = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: capacity_one,
                )
                first_tick = scheduler.tick(NOW)
                self.assertEqual([item.definition_id for item in first_tick], ["first"])
                second_state = repository.get_automation_definition_due_state("second")
                self.assertEqual(second_state.last_outcome, "blocked")
                self.assertIn("capacity", second_state.last_reason)
                self.assertTrue(second_state.last_next_action)
                AutomationWorker(repository, lambda job, cancelled: None).run_next()
                second_tick = scheduler.tick(NOW)
                self.assertEqual([item.definition_id for item in second_tick], ["second"])

            missing = definition("missing", resource="removed")
            healthy = definition("healthy")
            with SQLiteTaskRepository(Path(directory, "resource.sqlite3")) as repository:
                scheduler = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: snapshot(
                        (missing, healthy),
                        resources=("resource",),
                        enabled_resources=("resource",),
                    ),
                )
                emitted = scheduler.tick(NOW)
                self.assertEqual([item.definition_id for item in emitted], ["healthy"])
                missing_state = repository.get_automation_definition_due_state("missing")
                self.assertIn("missing", missing_state.last_reason)
                self.assertTrue(missing_state.last_next_action)

    def test_disabled_definition_preserves_history_and_reenable_emits_new_identity(self) -> None:
        enabled = definition("toggle")
        disabled = definition("toggle", enabled=False)
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                current = [snapshot((enabled,), revision_id="rev-1", version=1)]
                scheduler = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: current[0],
                )
                self.assertEqual(len(scheduler.tick(NOW)), 1)
                current[0] = snapshot((disabled,), revision_id="rev-2", digest="b" * 64, version=2)
                self.assertEqual(scheduler.tick(NOW + timedelta(minutes=1)), ())
                disabled_state = repository.get_automation_definition_due_state("toggle")
                self.assertEqual(disabled_state.last_outcome, "disabled")
                self.assertTrue(disabled_state.last_next_action)
                current[0] = snapshot((enabled,), revision_id="rev-3", digest="c" * 64, version=3)
                self.assertEqual(len(scheduler.tick(NOW + timedelta(minutes=2))), 1)
                history = repository.list_automation_definition_occurrences("toggle")
                self.assertEqual(len(history), 2)
                self.assertEqual(history[0].configuration_revision_id, "rev-3")
                self.assertEqual(history[1].configuration_revision_id, "rev-1")

    def test_fail_closed_snapshot_schedule_and_clock_boundaries_do_not_advance_due_time(
        self,
    ) -> None:
        value = definition("unavailable")
        bad_schedule = SimpleNamespace(
            definition_id="bad-schedule",
            enabled=True,
            resource_library_id="resource",
            source_scope=None,
            mode=AutomationTaskRunMode.SCAN_ONLY,
            interval_seconds=0,
            cron=None,
            timezone=None,
            item_limit=1,
        )
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                unavailable = IntervalScheduler(
                    repository,
                    (),
                    automation_task_definitions=(value,),
                    configuration_snapshot_resolver=lambda: (_ for _ in ()).throw(
                        RuntimeError("private provider token must not be persisted")
                    ),
                )
                self.assertEqual(unavailable.tick(NOW), ())
                state = repository.get_automation_definition_due_state("unavailable")
                self.assertEqual(state.last_outcome, "blocked")
                self.assertEqual(state.last_reason, "managed Active configuration is unavailable")
                self.assertIn("activate", state.last_next_action)
                due_before_failure = state.next_run_at

            with SQLiteTaskRepository(Path(directory, "bad.sqlite3")) as repository:
                scheduler = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: snapshot((bad_schedule,)),
                )
                self.assertEqual(scheduler.tick(NOW), ())
                state = repository.get_automation_definition_due_state("bad-schedule")
                self.assertEqual(state.last_outcome, "blocked")
                self.assertIn("invalid", state.last_reason)
                self.assertEqual(state.next_run_at, NOW)

            with SQLiteTaskRepository(Path(directory, "clock.sqlite3")) as repository:
                current = [snapshot((value,))]
                scheduler = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: current[0],
                )
                self.assertEqual(len(scheduler.tick(NOW)), 1)
                state = repository.get_automation_definition_due_state("unavailable")
                due_before_clock_failure = state.next_run_at
                scheduler.tick(NOW - timedelta(seconds=1))
                state = repository.get_automation_definition_due_state("unavailable")
                self.assertEqual(state.last_outcome, "blocked")
                self.assertIn("backwards", state.last_reason)
                self.assertEqual(state.next_run_at, due_before_clock_failure)
                self.assertEqual(due_before_failure, NOW)

    def test_atomic_failure_restart_and_concurrent_ticks_publish_at_most_one_occurrence(
        self,
    ) -> None:
        value = definition("atomic")
        active = snapshot((value,))
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                state = repository.initialize_automation_definition_due_state(
                    value.definition_id,
                    NOW,
                    NOW,
                    definition_fingerprint=value.definition_fingerprint,
                )
                job = AutomationJob(
                    "job-failed",
                    AutomationCommand.SCAN,
                    AutomationJobStatus.PENDING,
                    NOW,
                    NOW,
                    limit=value.item_limit,
                    definition_id=value.definition_id,
                    definition_fingerprint=value.definition_fingerprint,
                    definition_version=1,
                    occurrence_at=NOW,
                    run_mode=value.mode,
                    resource_library_id=value.resource_library_id,
                    source_scope=value.source_scope,
                    configuration_snapshot_id=active.snapshot_id,
                    configuration_snapshot_digest=active.snapshot_digest,
                    configuration_snapshot_version=1,
                )
                occurrence = AutomationDefinitionOccurrence(
                    "occurrence-failed",
                    value.definition_id,
                    NOW,
                    NOW,
                    job.job_id,
                    value.definition_fingerprint,
                    1,
                    active.snapshot_id,
                    1,
                    active.snapshot_digest,
                    value.mode,
                    value.resource_library_id,
                    value.source_scope,
                    value.item_limit,
                )
                original_insert = repository._insert_job

                def insert_then_fail(candidate):
                    original_insert(candidate)
                    raise RuntimeError("simulated process stop")

                with patch.object(repository, "_insert_job", side_effect=insert_then_fail):
                    with self.assertRaisesRegex(RuntimeError, "simulated process stop"):
                        repository.enqueue_due_automation_definition(
                            value.definition_id,
                            job,
                            occurrence,
                            NOW + timedelta(minutes=1),
                            NOW,
                            10,
                        )
                self.assertEqual(repository.list_jobs(), ())
                self.assertEqual(repository.list_automation_definition_occurrences("atomic"), ())
                self.assertEqual(
                    repository.get_automation_definition_due_state("atomic").next_run_at,
                    state.next_run_at,
                )
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.list_jobs(), ())
                self.assertEqual(reopened.list_automation_definition_occurrences("atomic"), ())

            barrier = Barrier(2)
            results: list[tuple] = []
            errors: list[BaseException] = []

            def tick() -> None:
                try:
                    with SQLiteTaskRepository(database) as repository:
                        scheduler = IntervalScheduler(
                            repository,
                            (),
                            configuration_snapshot_resolver=lambda: active,
                        )
                        barrier.wait(timeout=5)
                        results.append(scheduler.tick(NOW))
                except BaseException as error:  # pragma: no cover - failure is asserted below
                    errors.append(error)

            threads = [Thread(target=tick) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            self.assertEqual(errors, [])
            self.assertEqual(sum(len(value) for value in results), 1)
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(len(repository.list_jobs()), 1)
                self.assertEqual(
                    len(repository.list_automation_definition_occurrences("atomic")), 1
                )

    def test_close_reopen_and_definition_edit_preserve_old_pins(self) -> None:
        first = definition("edited", scope="one", limit=4)
        second = definition("edited", scope="two", limit=9)
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            current = [snapshot((first,), revision_id="revision-1", version=1)]
            with SQLiteTaskRepository(database) as repository:
                scheduler = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: current[0],
                )
                first_job = scheduler.tick(NOW)[0]
                current[0] = snapshot(
                    (second,), revision_id="revision-2", digest="d" * 64, version=2
                )
                second_job = scheduler.tick(NOW + timedelta(minutes=1))[0]
                self.assertEqual(first_job.configuration_snapshot_id, "revision-1")
                self.assertEqual(first_job.source_scope, "one")
                self.assertEqual(second_job.configuration_snapshot_id, "revision-2")
                self.assertEqual(second_job.source_scope, "two")
                self.assertEqual(repository.get_job(first_job.job_id).source_scope, "one")
            with SQLiteTaskRepository(database) as repository:
                jobs = {item.job_id: item for item in repository.list_jobs()}
                self.assertEqual(jobs[first_job.job_id].configuration_snapshot_version, 1)
                self.assertEqual(jobs[second_job.job_id].configuration_snapshot_version, 2)
                values = repository.list_automation_definition_occurrences("edited", limit=1)
                self.assertEqual(values[0].configuration_revision_id, "revision-2")
                self.assertEqual(
                    repository.get_latest_automation_definition_occurrence("edited").job_id,
                    second_job.job_id,
                )

    def test_bounded_latest_and_cursor_listing_is_deterministic(self) -> None:
        value = definition("listed", interval=60)
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                scheduler = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: snapshot((value,)),
                )
                for minute in range(3):
                    scheduler.tick(NOW + timedelta(minutes=minute))
                newest = repository.list_automation_definition_occurrences("listed", limit=1)
                self.assertEqual(len(newest), 1)
                self.assertEqual(
                    newest[0],
                    repository.get_latest_automation_definition_occurrence("listed"),
                )
                cursor = newest[0]
                older = repository.list_automation_definition_occurrences(
                    "listed",
                    limit=1,
                    after=(cursor.emitted_at, cursor.occurrence_id),
                )
                self.assertEqual(len(older), 1)
                self.assertLess(older[0].emitted_at, cursor.emitted_at)
                self.assertEqual(
                    repository.list_automation_definition_occurrences(
                        "listed", limit=1, before=(older[0].emitted_at, older[0].occurrence_id)
                    )[0].occurrence_id,
                    cursor.occurrence_id,
                )
                with self.assertRaisesRegex(ValueError, "between 1 and 100"):
                    repository.list_automation_definition_occurrences("listed", limit=0)

    def test_scheduler_tick_constructs_no_pipeline_objects_and_creates_no_work_rows(self) -> None:
        value = definition("no-pipeline")
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                with (
                    patch(
                        "mediaflow.application.scanner.StorageScanner", side_effect=AssertionError
                    ),
                    patch(
                        "mediaflow.application.media_parser.MediaParserService",
                        side_effect=AssertionError,
                    ),
                    patch(
                        "mediaflow.application.metadata.MetadataProviderRegistry",
                        side_effect=AssertionError,
                    ),
                    patch(
                        "mediaflow.application.organizer.OrganizePlanner",
                        side_effect=AssertionError,
                    ),
                ):
                    self.assertEqual(
                        len(
                            IntervalScheduler(
                                repository,
                                (),
                                configuration_snapshot_resolver=lambda: snapshot((value,)),
                            ).tick(NOW)
                        ),
                        1,
                    )
                for table in (
                    "tasks",
                    "task_items",
                    "task_results",
                    "execution_authorizations",
                    "manual_execution_authorizations",
                ):
                    self.assertEqual(count_rows(repository, table), 0, table)

    def test_definition_pinned_job_is_refused_before_legacy_pipeline_and_submit_rejects_it(
        self,
    ) -> None:
        value = definition("guarded")
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: snapshot((value,)),
                ).tick(NOW)[0]
                with patch(
                    "mediaflow.final_cli.final_main", side_effect=AssertionError("pipeline called")
                ) as main:
                    result = AutomationWorker(
                        repository,
                        lambda candidate, cancelled: _run_queued_workflow(
                            candidate, None, cancelled
                        ),
                    ).run_next()
                self.assertEqual(result.status, AutomationJobStatus.FAILED)
                self.assertEqual(result.failure_category, "definition_scoped_worker_unavailable")
                self.assertEqual(result.failure_side_effects, "none")
                self.assertFalse(result.failure_retry_safe)
                self.assertTrue(result.failure_next_action)
                main.assert_not_called()
                with self.assertRaisesRegex(
                    ValueError, "must be emitted by the Automation Scheduler"
                ):
                    AutomationJobService(repository).submit(
                        "scan", definition_id=value.definition_id
                    )


class AutomationDefinitionOccurrenceMigrationAndReadModelTests(unittest.TestCase):
    def test_schema_28_migration_preserves_legacy_schedule_job_audit_and_preview_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "schema-28.sqlite3")
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_version VALUES ('runtime', 28);
                CREATE TABLE automation_jobs (
                    job_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, limit_value INTEGER,
                    started_at TEXT, completed_at TEXT, task_id TEXT, error TEXT,
                    cancellation_requested INTEGER NOT NULL DEFAULT 0, schedule_id TEXT,
                    execute_authorized INTEGER NOT NULL DEFAULT 0, claim_token TEXT,
                    configuration_snapshot_id TEXT, configuration_snapshot_digest TEXT,
                    failure_category TEXT, failure_durable_state TEXT,
                    failure_side_effects TEXT, failure_retry_safe INTEGER,
                    failure_next_action TEXT
                );
                CREATE TABLE automation_schedules (
                    schedule_id TEXT PRIMARY KEY, next_run_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, last_job_id TEXT
                );
                CREATE TABLE schedule_audit (
                    audit_id TEXT PRIMARY KEY, schedule_id TEXT NOT NULL,
                    occurrence_at TEXT NOT NULL, emitted_at TEXT NOT NULL,
                    job_id TEXT NOT NULL UNIQUE, command TEXT NOT NULL,
                    next_run_at TEXT NOT NULL
                );
                CREATE TABLE automation_task_definition_previews (
                    preview_id TEXT PRIMARY KEY, definition_id TEXT NOT NULL,
                    definition_fingerprint TEXT NOT NULL,
                    configuration_revision_id TEXT NOT NULL,
                    configuration_revision_version INTEGER NOT NULL,
                    configuration_revision_digest TEXT NOT NULL,
                    configuration_status TEXT NOT NULL,
                    resource_library_id TEXT NOT NULL, storage_id TEXT NOT NULL,
                    source_scope TEXT, run_mode TEXT NOT NULL,
                    effective_item_limit INTEGER NOT NULL, counts_json TEXT NOT NULL,
                    status TEXT NOT NULL, actor TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    next_action TEXT NOT NULL, error TEXT,
                    zero_mutation INTEGER NOT NULL, current INTEGER NOT NULL DEFAULT 1,
                    stale_reason TEXT, truncated INTEGER NOT NULL DEFAULT 0,
                    boundary_errors_json TEXT NOT NULL
                );
                """,
            )
            connection.execute(
                "INSERT INTO automation_jobs VALUES ("
                "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?"
                ")",
                (
                    "legacy-job",
                    "scan",
                    "pending",
                    NOW.isoformat(),
                    NOW.isoformat(),
                    3,
                    None,
                    None,
                    None,
                    None,
                    0,
                    "legacy-schedule",
                    0,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            connection.execute(
                "INSERT INTO automation_schedules VALUES (?, ?, ?, ?)",
                ("legacy-schedule", NOW.isoformat(), NOW.isoformat(), "legacy-job"),
            )
            connection.execute(
                "INSERT INTO schedule_audit VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "legacy-audit",
                    "legacy-schedule",
                    NOW.isoformat(),
                    NOW.isoformat(),
                    "legacy-job",
                    "scan",
                    (NOW + timedelta(minutes=1)).isoformat(),
                ),
            )
            connection.execute(
                "INSERT INTO automation_task_definition_previews VALUES ("
                "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?"
                ")",
                (
                    "preview-1",
                    "definition-1",
                    "a" * 64,
                    "revision-1",
                    1,
                    "b" * 64,
                    "active",
                    "resource",
                    "storage",
                    None,
                    "scan-only",
                    7,
                    '{"discovered": 0, "selected": 0, "permitted": 0, '
                    '"excludedIgnored": 0, "unstable": 0, "truncatedByLimit": 0}',
                    "previewed",
                    "tester",
                    NOW.isoformat(),
                    NOW.isoformat(),
                    "inspect",
                    None,
                    1,
                    1,
                    None,
                    0,
                    "[]",
                ),
            )
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                self.assertEqual(repository.list_jobs()[0].job_id, "legacy-job")
                self.assertEqual(
                    repository.list_schedule_states()[0].schedule_id, "legacy-schedule"
                )
                self.assertEqual(repository.list_schedule_audit()[0].audit_id, "legacy-audit")
                self.assertIsNotNone(repository.get_automation_task_definition_preview("preview-1"))
                self.assertEqual(count_rows(repository, "automation_definition_due_state"), 0)
                self.assertEqual(count_rows(repository, "automation_definition_occurrences"), 0)
                columns = {
                    row[1]
                    for row in repository._connection.execute(
                        "PRAGMA table_info(automation_jobs)"
                    ).fetchall()
                }
                self.assertIn("definition_id", columns)
                self.assertIn("configuration_snapshot_version", columns)

    def test_bulk_projection_uses_bounded_bulk_reads_and_api_web_expose_same_state(self) -> None:
        first = definition("first")
        second = definition("second")

        class BulkSpy:
            def __init__(self) -> None:
                self.state_calls = 0
                self.latest_calls = 0

            def list_automation_definition_due_states(self, *, definition_ids, limit):
                self.state_calls += 1
                return ()

            def list_latest_automation_definition_occurrences(self, definition_ids):
                self.latest_calls += 1
                return ()

            def get_automation_definition_due_state(self, definition_id):
                raise AssertionError("definition projection used an N+1 due-state query")

            def get_latest_automation_definition_occurrence(self, definition_id):
                raise AssertionError("definition projection used an N+1 latest query")

        spy = BulkSpy()
        projected = AutomationDefinitionOccurrenceService(spy).project_definitions((first, second))
        self.assertEqual(len(projected), 2)
        self.assertEqual(spy.state_calls, 1)
        self.assertEqual(spy.latest_calls, 1)

        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                current = snapshot((first,), revision_id="revision-1", version=1)
                IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: current,
                ).tick(NOW)
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer",
                            "viewer-token",
                            frozenset({ApiPermission.READ}),
                        ),
                    ),
                )
                active = SimpleNamespace(
                    revision_id="revision-1",
                    version=1,
                    revision_sequence=1,
                    digest=DIGEST,
                )
                active.summary = lambda: {
                    "revisionId": active.revision_id,
                    "version": active.version,
                    "revisionSequence": active.revision_sequence,
                    "digest": active.digest,
                }
                api._configuration_service = SimpleNamespace(active=lambda: active)
                api._configuration_objects = SimpleNamespace(
                    revision_detail=lambda revision_id: {
                        "objects": {"automationTaskDefinitions": [first.document()]}
                    }
                )
                before_audit = count_rows(repository, "security_audit")
                list_status, list_body = self._request(api, "/api/v1/automation/task-definitions")
                detail_status, detail_body = self._request(
                    api, "/api/v1/automation/task-definitions/first"
                )
                occurrence_status, occurrence_body = self._request(
                    api,
                    "/api/v1/automation/task-definitions/first/occurrences",
                    query="limit=1",
                )
                self.assertEqual((list_status, detail_status, occurrence_status), (200, 200, 200))
                self.assertEqual(
                    list_body["items"][0]["occurrenceState"],
                    detail_body["definition"]["occurrenceState"],
                )
                self.assertEqual(
                    list_body["items"][0]["definitionFingerprint"],
                    occurrence_body["items"][0]["definitionFingerprint"],
                )
                self.assertEqual(
                    occurrence_body["items"][0]["configurationRevisionId"],
                    "revision-1",
                )
                self.assertEqual(count_rows(repository, "security_audit"), before_audit)
                missing_status, missing_body = self._request(
                    api,
                    "/api/v1/automation/task-definitions/missing/occurrences",
                    query="limit=1",
                )
                self.assertEqual(missing_status, 404)
                self.assertNotIn("viewer-token", json.dumps(missing_body))

        script = APP_JS.decode("utf-8")
        self.assertIn("occurrences?limit=10`", script)
        self.assertIn("Scheduled occurrences", script)
        self.assertIn("Definition fingerprint", script)
        self.assertIn("Failure reason", script)
        self.assertIn("Last outcome", script)

    @staticmethod
    def _request(api, path: str, *, query: str = ""):
        statuses: list[str] = []
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "CONTENT_LENGTH": "0",
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": "Bearer viewer-token",
            "wsgi.input": io.BytesIO(),
        }
        result = b"".join(api(environ, lambda status, headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(result)


if __name__ == "__main__":
    unittest.main()
