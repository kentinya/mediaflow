from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from mediaflow.application.automation import IntervalScheduler
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationDefinitionDueState,
    AutomationDefinitionOccurrence,
    AutomationTaskDefinition,
    AutomationTaskRunMode,
    SchedulerConfigurationSnapshot,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

NOW = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
DIGEST = "a" * 64


def definition(
    definition_id: str = "definition",
    *,
    resource: str = "resource",
    scope: str | None = "incoming",
    mode: AutomationTaskRunMode = AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
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
            last_task_id="task-1",
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
                AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
                "resource",
                "safe",
                7,
            )

    def test_interval_and_cron_due_ticks_pin_exact_identity_and_skip_future_due(self) -> None:
        interval = definition("interval", limit=11)
        cron = definition(
            "cron",
            scope=None,
            mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
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
                origin = {
                    item.task_id: repository.get_run_display_context(item.task_id)
                    for item in emitted
                }
                self.assertEqual(
                    {item.origin_definition_id for item in origin.values()}, {"interval", "cron"}
                )
                by_id = {origin[item.task_id].origin_definition_id: item for item in emitted}
                self.assertEqual(by_id["interval"].item_limit, 11)
                self.assertEqual(by_id["cron"].command, AutomationCommand.ORGANIZE.value)
                self.assertEqual(by_id["cron"].scope_path, None)
                for task in emitted:
                    self.assertEqual(task.configuration_snapshot_id, "revision-1")
                    self.assertEqual(task.configuration_snapshot_digest, DIGEST)
                    occurrence = repository.get_latest_automation_definition_occurrence(
                        origin[task.task_id].origin_definition_id
                    )
                    self.assertEqual(occurrence.configuration_revision_version, 4)
                    self.assertEqual(occurrence.definition_version, 4)
                    self.assertEqual(occurrence.task_id, task.task_id)
                self.assertIsNone(
                    repository.get_automation_definition_due_state("future").last_task_id
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
                self.assertEqual(len(emitted), 1)
                self.assertEqual(
                    repository.get_latest_automation_definition_occurrence("tokyo").occurrence_at,
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
                    repository.get_latest_automation_definition_occurrence("fall").occurrence_at,
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
                self.assertEqual(len(first_tick), 1)
                self.assertEqual(
                    repository.get_run_display_context(first_tick[0].task_id).origin_definition_id,
                    "first",
                )
                second_state = repository.get_automation_definition_due_state("second")
                self.assertEqual(second_state.last_outcome, "blocked")
                self.assertIn("capacity", second_state.last_reason)
                self.assertTrue(second_state.last_next_action)
                # Settle the occupying Task at its safe control boundary.
                from mediaflow.application.operations_lifecycle import TaskLifecycleService

                TaskLifecycleService(repository).cancel(
                    first_tick[0].task_id, expected_version=None
                )
                second_tick = scheduler.tick(NOW)
                self.assertEqual(len(second_tick), 1)
                self.assertEqual(
                    repository.get_run_display_context(second_tick[0].task_id).origin_definition_id,
                    "second",
                )

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
                self.assertEqual(len(emitted), 1)
                self.assertEqual(
                    repository.get_run_display_context(emitted[0].task_id).origin_definition_id,
                    "healthy",
                )
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
            mode="automatic-organization",
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

    def test_recorded_removed_mode_emits_no_occurrence_and_no_job(self) -> None:
        """A recorded pre-amendment mode is unsupported, never converted.

        The scheduler records the bounded ``unsupported`` outcome and emits no
        occurrence and no Job, so the removed mode can never acquire execution
        authority or a compatible scan/plan executor.
        """

        recorded = SimpleNamespace(
            definition_id="recorded",
            enabled=True,
            resource_library_id="resource",
            source_scope=None,
            mode="scan-only",
            interval_seconds=60,
            cron=None,
            timezone=None,
            item_limit=7,
        )
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                scheduler = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: snapshot((recorded,)),
                )
                self.assertEqual(scheduler.tick(NOW), ())
                state = repository.get_automation_definition_due_state("recorded")
                self.assertEqual(state.last_outcome, "unsupported")
                self.assertTrue(state.last_next_action)
                # The recorded occurrence history and the due state stay
                # readable, but no work was admitted.
                self.assertEqual(repository.list_automation_definition_occurrences("recorded"), ())
                self.assertEqual(repository.list_tasks(), ())
                for table in ("tasks", "task_items", "task_results"):
                    self.assertEqual(count_rows(repository, table), 0, table)

    def test_atomic_failure_restart_and_concurrent_ticks_publish_at_most_one_occurrence(
        self,
    ) -> None:
        value = definition("atomic")
        active = snapshot((value,))
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                repository.initialize_automation_definition_due_state(
                    value.definition_id,
                    NOW,
                    NOW,
                    definition_fingerprint=value.definition_fingerprint,
                )
                # The first tick admits the occurrence Task; a repository close
                # and reopen preserves exactly that one Task and occurrence.
                admitted = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: active,
                ).tick(NOW)
                self.assertEqual(len(admitted), 1)
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(len(reopened.list_tasks()), 1)
                self.assertEqual(len(reopened.list_automation_definition_occurrences("atomic")), 1)
                for task in reopened.list_tasks():
                    # The occurrence and its Task are the same durable identity.
                    occurrence = reopened.get_latest_automation_definition_occurrence("atomic")
                    self.assertEqual(occurrence.task_id, task.task_id)
                # Reset to the same due slot for the concurrency proof.
                with reopened._lock:
                    reopened._connection.execute(
                        "DELETE FROM automation_definition_occurrences WHERE definition_id=?",
                        ("atomic",),
                    )
                    reopened._connection.execute(
                        "DELETE FROM tasks WHERE task_id=?",
                        (admitted[0].task_id,),
                    )
                    reopened._connection.execute(
                        "DELETE FROM task_scheduling WHERE task_id=?",
                        (admitted[0].task_id,),
                    )
                    reopened._connection.execute(
                        "UPDATE automation_definition_due_state SET next_run_at=? "
                        "WHERE definition_id=?",
                        (NOW.isoformat(), "atomic"),
                    )
                    reopened._connection.commit()

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
                self.assertEqual(len(repository.list_tasks()), 1)
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
                first_task = scheduler.tick(NOW)[0]
                current[0] = snapshot(
                    (second,), revision_id="revision-2", digest="d" * 64, version=2
                )
                second_task = scheduler.tick(NOW + timedelta(minutes=1))[0]
                self.assertEqual(first_task.configuration_snapshot_id, "revision-1")
                self.assertEqual(first_task.scope_path, "one")
                self.assertEqual(second_task.configuration_snapshot_id, "revision-2")
                self.assertEqual(second_task.scope_path, "two")
                self.assertEqual(repository.get_task(first_task.task_id).scope_path, "one")
            with SQLiteTaskRepository(database) as repository:
                tasks = {item.task_id: item for item in repository.list_tasks()}
                self.assertEqual(tasks[first_task.task_id].configuration_snapshot_id, "revision-1")
                self.assertEqual(tasks[second_task.task_id].configuration_snapshot_id, "revision-2")
                values = repository.list_automation_definition_occurrences("edited", limit=1)
                self.assertEqual(values[0].configuration_revision_id, "revision-2")
                self.assertEqual(
                    repository.get_latest_automation_definition_occurrence("edited").task_id,
                    second_task.task_id,
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
                self.assertEqual(count_rows(repository, "tasks"), 1)
                for table in (
                    "task_items",
                    "task_results",
                    "execution_authorizations",
                    "manual_execution_authorizations",
                ):
                    self.assertEqual(count_rows(repository, table), 0, table)
