from __future__ import annotations

import io
import json
import os
import tempfile
import time
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediaflow.application.automation import (
    AutomationConfigurationUnavailable,
    AutomationWorker,
    IntervalScheduler,
)
from mediaflow.application.automation_definition_execution import (
    DefinitionScopedExecutionService,
)
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.read_only_storage import ReadOnlyStorageGuard
from mediaflow.application.strategy_test import (
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.application.unattended_execution import UnattendedExecutionGrantService
from mediaflow.domain.automation import (
    AutomationJobStatus,
    AutomationTaskDefinition,
    AutomationTaskRunMode,
    SchedulerConfigurationSnapshot,
)
from mediaflow.domain.library import FileStabilityPolicy, MediaLibrary, ResourceLibrary
from mediaflow.domain.metadata import (
    MediaCandidate,
    MediaType,
    MetadataError,
    MetadataErrorCode,
)
from mediaflow.domain.notification import NotificationEventType
from mediaflow.domain.organizer import ConflictStrategy
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.domain.task_persistence import PersistentTaskStatus, TaskItemStatus
from mediaflow.final_cli import _run_queued_workflow
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.runtime_configuration import (
    RuntimeConfiguration,
    StorageDefinition,
    with_managed_snapshot,
)
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import smoke_strategy_configuration
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 1, 1, tzinfo=UTC)
SNAPSHOT_ID = "revision-1"
SNAPSHOT_DIGEST = "a" * 64


def _definition(
    definition_id: str = "definition",
    *,
    scope: str | None = "incoming",
    mode: AutomationTaskRunMode = AutomationTaskRunMode.SCAN_ONLY,
    limit: int = 10,
    enabled: bool = True,
) -> AutomationTaskDefinition:
    return AutomationTaskDefinition(
        definition_id,
        definition_id,
        "resource",
        scope,
        mode,
        interval_seconds=60,
        item_limit=limit,
        enabled=enabled,
    )


def _snapshot(definition: AutomationTaskDefinition, *, version: int = 1):
    return SchedulerConfigurationSnapshot(
        SNAPSHOT_ID,
        SNAPSHOT_DIGEST,
        (),
        10,
        (definition,),
        version,
        ("resource",),
        ("resource",),
    )


def _tree(root: Path) -> tuple[tuple[str, str, bytes | None], ...]:
    values = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            values.append((relative, "directory", None))
        else:
            values.append((relative, "file", path.read_bytes()))
    return tuple(values)


class _DisabledPinnedDefinition(AutomationTaskDefinition):
    """A stale disabled snapshot retaining the originally emitted fingerprint."""

    def __init__(self, original: AutomationTaskDefinition) -> None:
        super().__init__(
            original.definition_id,
            original.name,
            original.resource_library_id,
            original.source_scope,
            original.mode,
            original.interval_seconds,
            original.cron,
            original.timezone,
            original.item_limit,
            False,
        )
        object.__setattr__(self, "_original_fingerprint", original.definition_fingerprint)

    @property
    def definition_fingerprint(self) -> str:
        return self._original_fingerprint


class DefinitionScopedExecutionTests(unittest.TestCase):
    def _configuration(
        self,
        root: Path,
        definition: AutomationTaskDefinition,
        *,
        resource: ResourceLibrary | None = None,
        strategy=None,
        version: int = 1,
    ) -> RuntimeConfiguration:
        source = root / "source"
        target = root / "target"
        (source / "Media").mkdir(parents=True, exist_ok=True)
        (target / "Movies").mkdir(parents=True, exist_ok=True)
        (target / "TV").mkdir(parents=True, exist_ok=True)
        resource = resource or ResourceLibrary("resource", "Resource", "source", "Media")
        return with_managed_snapshot(
            RuntimeConfiguration(
                strategy or smoke_strategy_configuration(),
                (
                    StorageDefinition("source", "local", str(source), "Source"),
                    StorageDefinition("target", "local", str(target), "Target"),
                ),
                (resource,),
                (),
                (
                    MediaLibrary("movies", "Movies", "target", "Movies"),
                    MediaLibrary("tv", "TV", "target", "TV"),
                ),
                str(root / "history.jsonl"),
                str(root / "runtime.sqlite3"),
                automation_task_definitions=(definition,),
            ),
            snapshot_id=SNAPSHOT_ID,
            digest=SNAPSHOT_DIGEST,
            version=version,
        )

    def _guarded_storage_factory(self, configuration):
        source = ReadOnlyStorageGuard(
            LocalStorage("source", configuration.storage_definitions[0].root_path)
        )
        target = ReadOnlyStorageGuard(
            LocalStorage("target", configuration.storage_definitions[1].root_path)
        )
        values = {"source": source, "target": target}

        def factory(external=None, storage_ids=None):
            selected = values
            if storage_ids is not None:
                selected = {key: value for key, value in values.items() if key in storage_ids}
            if external:
                selected = {**selected, **external}
            return selected

        return source, target, factory

    def _service(
        self,
        repository,
        file_index,
        configuration,
        storage_factory,
        provider=None,
        unattended_grant_service=None,
    ):
        def provider_factory(provider_ids):
            if provider is None:
                raise AssertionError("the scan-only handoff must not construct a Provider")
            self.assertEqual(tuple(provider_ids), ("tmdb",))
            return MetadataProviderRegistry((provider,))

        return DefinitionScopedExecutionService(
            repository,
            file_index,
            configuration,
            storage_factory=storage_factory,
            provider_factory=provider_factory,
            strategy_factory=strategy_runner_from_configuration,
            history_factory=JsonLinesOperationHistoryRepository,
            unattended_grant_service=unattended_grant_service,
        )

    @staticmethod
    def _emit(repository, definition):
        emitted = IntervalScheduler(
            repository,
            (),
            configuration_snapshot_resolver=lambda: _snapshot(definition),
        ).tick(NOW)
        if len(emitted) != 1:
            raise AssertionError(f"expected one emitted occurrence, got {len(emitted)}")
        return emitted[0]

    @staticmethod
    def _run(repository, service):
        return AutomationWorker(
            repository,
            lambda job, cancelled: service.run(job, cancelled),
        ).run_next()

    def test_scan_only_is_scoped_bounded_dry_and_reloadable(self) -> None:
        definition = _definition(limit=1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            incoming = source / "Media" / "incoming"
            sibling = source / "Media" / "sibling"
            incoming.mkdir(parents=True)
            sibling.mkdir()
            (incoming / "first.mkv").write_bytes(b"first")
            (incoming / "second.mkv").write_bytes(b"second")
            (sibling / "not-selected.mkv").write_bytes(b"sibling")
            (source / "above-root.mkv").write_bytes(b"outside")
            before_source = _tree(source)

            configuration = self._configuration(root, definition)
            source_guard, target_guard, storage_factory = self._guarded_storage_factory(
                configuration
            )
            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                job = self._emit(repository, definition)
                service = self._service(repository, file_index, configuration, storage_factory)
                finished = self._run(repository, service)
                self.assertIsNotNone(finished)
                self.assertEqual(finished.status, AutomationJobStatus.COMPLETED)
                self.assertIsNotNone(finished.task_id)
                task = repository.get_task(finished.task_id)
                self.assertIsNotNone(task)
                self.assertEqual(
                    task.status,
                    PersistentTaskStatus.COMPLETED,
                    (
                        task,
                        repository.list_items(task.task_id),
                        repository.list_results(task.task_id),
                    ),
                )
                self.assertEqual(task.scope_path, "Media/incoming")
                self.assertEqual(task.item_limit, 1)
                items = repository.list_items(task.task_id)
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0].source_path, "Media/incoming/first.mkv")
                self.assertEqual(items[0].status, TaskItemStatus.SKIPPED)
                self.assertEqual(repository.list_results(task.task_id), ())
                self.assertNotIn(
                    "Media/sibling/not-selected.mkv", {item.source_path for item in items}
                )
                self.assertNotIn("above-root.mkv", {item.source_path for item in items})

                occurrence = repository.get_latest_automation_definition_occurrence(
                    definition.definition_id
                )
                self.assertEqual(occurrence.job_id, job.job_id)
                self.assertEqual(occurrence.task_id, task.task_id)
                self.assertEqual(occurrence.outcome, "completed")
                self.assertIsNone(occurrence.failure_category)
            with SQLiteTaskRepository(configuration.database_path) as reopened:
                task = reopened.get_task(finished.task_id)
                occurrence = reopened.get_latest_automation_definition_occurrence(
                    definition.definition_id
                )
                self.assertEqual(task.status, PersistentTaskStatus.COMPLETED)
                self.assertEqual(occurrence.task_id, finished.task_id)
                self.assertEqual(occurrence.outcome, "completed")

            self.assertEqual(_tree(source), before_source)
            self.assertEqual(
                source_guard.mutation_calls, {key: 0 for key in source_guard.mutation_calls}
            )
            self.assertEqual(
                target_guard.mutation_calls, {key: 0 for key in target_guard.mutation_calls}
            )

    def test_scope_without_subscope_uses_library_root_and_never_parent(self) -> None:
        definition = _definition("root", scope=None, limit=10)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "source" / "Media"
            (media / "nested").mkdir(parents=True)
            (media / "root.mkv").write_bytes(b"root")
            (media / "nested" / "nested.mkv").write_bytes(b"nested")
            (root / "source" / "parent.mkv").write_bytes(b"parent")
            configuration = self._configuration(root, definition)
            source_guard, _target_guard, storage_factory = self._guarded_storage_factory(
                configuration
            )
            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                self._emit(repository, definition)
                finished = self._run(
                    repository,
                    self._service(repository, file_index, configuration, storage_factory),
                )
                task = repository.get_task(finished.task_id)
                self.assertEqual(task.scope_path, "Media")
                self.assertEqual(
                    {item.source_path for item in repository.list_items(task.task_id)},
                    {"Media/root.mkv", "Media/nested/nested.mkv"},
                )
            self.assertEqual(source_guard.mutation_calls["Move"], 0)

    def test_scan_and_plan_preserves_mixed_recognition_types_and_c(self) -> None:
        definition = _definition(mode=AutomationTaskRunMode.SCAN_AND_PLAN)
        candidates = (
            MediaCandidate(
                "tmdb",
                "movie-a",
                MediaType.MOVIE,
                "Alpha Movie",
                year=2024,
                genres=("Animation",),
                countries=("JP",),
            ),
            MediaCandidate("tmdb", "show-b", MediaType.TV, "Bravo Show", year=2024),
            MediaCandidate(
                "tmdb",
                "movie-c",
                MediaType.MOVIE,
                "Charlie Movie",
                year=2024,
                genres=("Animation",),
                countries=("JP",),
            ),
        )
        provider = SyntheticMetadataProvider(candidates, episodes=(1,))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for recognition_type, filename in (
                ("A", "Alpha.Movie.2024.mkv"),
                ("B", "Bravo.Show.2024.S01E01.mkv"),
                ("C", "Charlie.Movie.2024.mkv"),
            ):
                path = root / "source" / "Media" / "incoming" / recognition_type
                path.mkdir(parents=True)
                (path / filename).write_bytes(recognition_type.encode())
            before_source = _tree(root / "source")
            configuration = self._configuration(root, definition)
            source_guard, target_guard, storage_factory = self._guarded_storage_factory(
                configuration
            )
            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                self._emit(repository, definition)
                finished = self._run(
                    repository,
                    self._service(
                        repository,
                        file_index,
                        configuration,
                        storage_factory,
                        provider,
                    ),
                )
                self.assertEqual(finished.status, AutomationJobStatus.COMPLETED)
                task = repository.get_task(finished.task_id)
                self.assertEqual(
                    task.status,
                    PersistentTaskStatus.COMPLETED,
                    (
                        task,
                        repository.list_items(task.task_id),
                        repository.list_results(task.task_id),
                    ),
                )
                self.assertEqual(task.total_items, 3)
                items = repository.list_items(task.task_id)
                results = repository.list_results(task.task_id)
                self.assertEqual(len(items), 3)
                self.assertEqual(len(results), 3)
                by_source = {Path(item.source_path).name: item for item in results}
                expected = {
                    "Alpha.Movie.2024.mkv": ("A", "A", "A", "A"),
                    "Bravo.Show.2024.S01E01.mkv": ("B", "B", "B", "B"),
                    "Charlie.Movie.2024.mkv": ("C", "C", "A", "A"),
                }
                for filename, policies in expected.items():
                    result = by_source[filename]
                    self.assertEqual(result.status, TaskItemStatus.DRY_RUN.value)
                    self.assertEqual(
                        (
                            result.recognition_type,
                            result.metadata_policy_id,
                            result.naming_policy_id,
                            result.classification_policy_id,
                        ),
                        policies,
                    )
                    self.assertEqual(result.organize_policy_id, policies[3])
                    self.assertEqual(result.operation, "MOVE")
            self.assertEqual(_tree(root / "source"), before_source)
            self.assertEqual(source_guard.mutation_calls["Move"], 0)
            self.assertEqual(target_guard.mutation_calls["Move"], 0)

    def test_per_item_failure_does_not_hide_successful_sibling(self) -> None:
        definition = _definition(mode=AutomationTaskRunMode.SCAN_AND_PLAN)
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "movie-c",
                    MediaType.MOVIE,
                    "Charlie Movie",
                    year=2024,
                    genres=("Animation",),
                    countries=("JP",),
                ),
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "source" / "Media" / "incoming"
            (incoming / "C").mkdir(parents=True)
            (incoming / "unknown").mkdir()
            (incoming / "C" / "Charlie.Movie.2024.mkv").write_bytes(b"good")
            (incoming / "unknown" / "Unrecognized.Movie.2024.mkv").write_bytes(b"unknown")
            configuration = self._configuration(root, definition)
            _source_guard, _target_guard, storage_factory = self._guarded_storage_factory(
                configuration
            )
            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                self._emit(repository, definition)
                finished = self._run(
                    repository,
                    self._service(
                        repository,
                        file_index,
                        configuration,
                        storage_factory,
                        provider,
                    ),
                )
                task = repository.get_task(finished.task_id)
                self.assertEqual(task.status, PersistentTaskStatus.PARTIAL_SUCCESS)
                items = {
                    Path(item.source_path).name: item
                    for item in repository.list_items(task.task_id)
                }
                self.assertEqual(items["Charlie.Movie.2024.mkv"].status, TaskItemStatus.DRY_RUN)
                self.assertEqual(
                    items["Unrecognized.Movie.2024.mkv"].status,
                    TaskItemStatus.WAITING_RECOGNITION,
                )
                self.assertEqual(len(repository.list_results(task.task_id)), 1)

    def test_post_task_failure_marks_job_occurrence_and_notification_failed(self) -> None:
        definition = _definition("post-task-failure", mode=AutomationTaskRunMode.SCAN_AND_PLAN)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Media" / "incoming").mkdir(parents=True)
            configuration = self._configuration(root, definition)
            _source_guard, _target_guard, storage_factory = self._guarded_storage_factory(
                configuration
            )
            events = []

            def fail_strategy(*_args, **_kwargs):
                raise RuntimeError("private-failure-detail-8675309")

            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                self._emit(repository, definition)
                service = DefinitionScopedExecutionService(
                    repository,
                    file_index,
                    configuration,
                    storage_factory=storage_factory,
                    provider_factory=lambda _ids: MetadataProviderRegistry(
                        (SyntheticMetadataProvider(()),)
                    ),
                    strategy_factory=fail_strategy,
                    history_factory=JsonLinesOperationHistoryRepository,
                )
                finished = AutomationWorker(
                    repository,
                    lambda job, cancelled: service.run(job, cancelled),
                    SimpleNamespace(publish=events.append),
                ).run_next()

                self.assertEqual(finished.status, AutomationJobStatus.FAILED)
                self.assertTrue(finished.task_id)
                self.assertEqual(
                    finished.failure_category,
                    "definition_scoped_workflow_failed",
                )
                self.assertEqual(finished.failure_side_effects, "none")
                self.assertTrue(finished.failure_retry_safe)
                self.assertTrue(finished.failure_next_action)
                task = repository.get_task(finished.task_id)
                self.assertEqual(task.status, PersistentTaskStatus.FAILED)
                occurrence = repository.get_latest_automation_definition_occurrence(
                    definition.definition_id
                )
                self.assertEqual(occurrence.task_id, task.task_id)
                self.assertEqual(occurrence.outcome, "failed")
                self.assertEqual(
                    occurrence.failure_category,
                    "definition_scoped_workflow_failed",
                )
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0].event_type, NotificationEventType.JOB_FAILED)
                persisted = json.dumps(
                    {
                        "job": {
                            "error": finished.error,
                            "failureCategory": finished.failure_category,
                            "failureDurableState": finished.failure_durable_state,
                            "failureNextAction": finished.failure_next_action,
                        },
                        "occurrence": occurrence.document(),
                        "taskError": task.error,
                    }
                )
                self.assertNotIn("private-failure-detail-8675309", persisted)

                api = self._api(repository, (definition,))
                status, body = self._request(
                    api,
                    "/api/v1/automation/task-definitions/post-task-failure/occurrences",
                )
                self.assertEqual(status, 200, body)
                self.assertEqual(body["items"][0]["taskId"], task.task_id)
                self.assertEqual(body["items"][0]["outcome"], "failed")
                self.assertEqual(
                    body["items"][0]["failureCategory"],
                    "definition_scoped_workflow_failed",
                )

    def test_automatic_mode_fails_before_adapters_task_or_executor(self) -> None:
        definition = _definition(mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configuration = self._configuration(root, definition)
            counts = {"storage": 0, "provider": 0, "strategy": 0, "history": 0}

            def storage_factory(*, storage_ids=None, external=None):
                counts["storage"] += 1
                raise AssertionError("automatic mode constructed Storage")

            def provider_factory(_provider_ids):
                counts["provider"] += 1
                raise AssertionError("automatic mode constructed Provider")

            def strategy_factory(*_args, **_kwargs):
                counts["strategy"] += 1
                raise AssertionError("automatic mode constructed strategy")

            def history_factory(_path):
                counts["history"] += 1
                raise AssertionError("automatic mode constructed history")

            with SQLiteTaskRepository(configuration.database_path) as repository:
                self._emit(repository, definition)
                service = DefinitionScopedExecutionService(
                    repository,
                    object(),
                    configuration,
                    storage_factory=storage_factory,
                    provider_factory=provider_factory,
                    strategy_factory=strategy_factory,
                    history_factory=history_factory,
                )
                with patch(
                    "mediaflow.application.automation_definition_execution.OrganizerExecutor",
                    side_effect=AssertionError("automatic mode constructed executor"),
                ):
                    finished = self._run(repository, service)
                self.assertEqual(finished.status, AutomationJobStatus.FAILED)
                self.assertEqual(
                    finished.failure_category,
                    "unattended_execution_authority_missing",
                )
                self.assertEqual(finished.failure_side_effects, "none")
                self.assertFalse(finished.failure_retry_safe)
                self.assertTrue(finished.failure_next_action)
                self.assertEqual(counts, {key: 0 for key in counts})
                self.assertEqual(repository.list_tasks(), ())
                occurrence = repository.get_latest_automation_definition_occurrence(
                    definition.definition_id
                )
                self.assertEqual(occurrence.outcome, "blocked")
                self.assertEqual(
                    occurrence.failure_category,
                    "unattended_execution_authority_missing",
                )

    def test_authorized_automatic_mode_executes_normal_chain_and_c_stays_c(self) -> None:
        definition = _definition(
            "authorized",
            mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
            limit=2,
        )
        candidates = (
            MediaCandidate(
                "tmdb",
                "movie-a",
                MediaType.MOVIE,
                "Alpha Movie",
                year=2024,
                genres=("Animation",),
                countries=("JP",),
            ),
            MediaCandidate(
                "tmdb",
                "movie-c",
                MediaType.MOVIE,
                "Charlie Movie",
                year=2024,
                genres=("Animation",),
                countries=("JP",),
            ),
        )
        provider = SyntheticMetadataProvider(candidates)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for recognition_type, filename in (
                ("A", "Alpha.Movie.2024.mkv"),
                ("C", "Charlie.Movie.2024.mkv"),
            ):
                path = root / "source" / "Media" / "incoming" / recognition_type
                path.mkdir(parents=True)
                (path / filename).write_bytes(filename.encode())
            configuration = self._configuration(root, definition)
            storages = {
                "source": LocalStorage("source", str(root / "source")),
                "target": LocalStorage("target", str(root / "target")),
            }

            def storage_factory(external=None, storage_ids=None):
                selected = storages
                if storage_ids is not None:
                    selected = {key: value for key, value in storages.items() if key in storage_ids}
                if external:
                    selected = {**selected, **external}
                return selected

            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                job = self._emit(repository, definition)
                grant_service = UnattendedExecutionGrantService(repository)
                grant_service.grant(
                    definition,
                    configuration_snapshot_id=job.configuration_snapshot_id,
                    configuration_snapshot_digest=job.configuration_snapshot_digest,
                    configuration_snapshot_version=job.configuration_snapshot_version,
                    actor="admin",
                    confirmation=True,
                )
                service = self._service(
                    repository,
                    file_index,
                    configuration,
                    storage_factory,
                    provider,
                    grant_service,
                )
                finished = self._run(repository, service)
                self.assertEqual(finished.status, AutomationJobStatus.COMPLETED)
                task = repository.get_task(finished.task_id)
                self.assertTrue(task.execute_authorized)
                self.assertEqual(task.status, PersistentTaskStatus.COMPLETED)
                results = repository.list_results(task.task_id)
                self.assertEqual(len(results), 2)
                self.assertEqual({result.recognition_type for result in results}, {"A", "C"})
                c_result = next(
                    result
                    for result in results
                    if result.source_path.endswith("Charlie.Movie.2024.mkv")
                )
                self.assertEqual(
                    (
                        c_result.recognition_type,
                        c_result.naming_policy_id,
                        c_result.classification_policy_id,
                    ),
                    ("C", "A", "A"),
                )
                self.assertEqual(
                    {result.status for result in results}, {TaskItemStatus.SUCCESS.value}
                )
                self.assertEqual(
                    repository.get_job(job.job_id).task_id,
                    task.task_id,
                )
            self.assertFalse(
                (root / "source" / "Media" / "incoming" / "A" / "Alpha.Movie.2024.mkv").exists()
            )
            self.assertFalse(
                (root / "source" / "Media" / "incoming" / "C" / "Charlie.Movie.2024.mkv").exists()
            )
            self.assertEqual(len(list((root / "target").rglob("*.mkv"))), 2)

    def test_unattended_overwrite_collision_waits_without_mutation(self) -> None:
        definition = _definition(
            "overwrite-collision",
            mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
            limit=1,
        )
        base_strategy = smoke_strategy_configuration()
        overwrite_policies = tuple(
            replace(
                type_policy,
                organize_policy=replace(
                    type_policy.organize_policy,
                    conflict_strategy=ConflictStrategy.OVERWRITE,
                ),
            )
            for type_policy in base_strategy.recognition_type_policies
        )
        strategy = replace(base_strategy, recognition_type_policies=overwrite_policies)
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "movie-a",
                    MediaType.MOVIE,
                    "Alpha Movie",
                    year=2024,
                    genres=("Animation",),
                    countries=("JP",),
                ),
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_file = root / "source/Media/incoming/A/Alpha.Movie.2024.mkv"
            source_file.parent.mkdir(parents=True)
            source_file.write_bytes(b"new")
            existing = root / "target/Movies/Anime/Alpha Movie (2024)/Alpha Movie (2024).mkv"
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"old")
            configuration = self._configuration(root, definition, strategy=strategy)
            storages = {
                "source": LocalStorage("source", str(root / "source")),
                "target": LocalStorage("target", str(root / "target")),
            }

            def storage_factory(external=None, storage_ids=None):
                selected = storages
                if storage_ids is not None:
                    selected = {key: value for key, value in storages.items() if key in storage_ids}
                if external:
                    selected = {**selected, **external}
                return selected

            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                job = self._emit(repository, definition)
                grant_service = UnattendedExecutionGrantService(repository)
                grant_service.grant(
                    definition,
                    configuration_snapshot_id=job.configuration_snapshot_id,
                    configuration_snapshot_digest=job.configuration_snapshot_digest,
                    configuration_snapshot_version=job.configuration_snapshot_version,
                    actor="admin",
                    confirmation=True,
                )
                finished = self._run(
                    repository,
                    DefinitionScopedExecutionService(
                        repository,
                        file_index,
                        configuration,
                        storage_factory=storage_factory,
                        provider_factory=lambda _ids: MetadataProviderRegistry((provider,)),
                        strategy_factory=strategy_runner_from_configuration,
                        history_factory=JsonLinesOperationHistoryRepository,
                        unattended_grant_service=grant_service,
                    ),
                )
                task = repository.get_task(finished.task_id)
                self.assertEqual(task.status, PersistentTaskStatus.PARTIAL_SUCCESS)
                item = repository.list_items(task.task_id)[0]
                self.assertEqual(item.status, TaskItemStatus.WAITING_CONFIRM)
                confirmation = repository.list_confirmations()[0]
                self.assertEqual(confirmation.configured_strategy, ConflictStrategy.OVERWRITE.value)
                self.assertFalse(confirmation.overwrite_authorized)
                self.assertEqual(existing.read_bytes(), b"old")
            self.assertEqual(source_file.read_bytes(), b"new")

    def test_authorized_conflict_strategies_preserve_independent_sibling_outcomes(self) -> None:
        candidates = (
            MediaCandidate(
                "tmdb",
                "movie-alpha",
                MediaType.MOVIE,
                "Alpha Movie",
                year=2024,
                genres=("Animation",),
                countries=("JP",),
            ),
            MediaCandidate(
                "tmdb",
                "movie-bravo",
                MediaType.MOVIE,
                "Bravo Movie",
                year=2024,
                genres=("Animation",),
                countries=("JP",),
            ),
        )
        for conflict_strategy in (
            ConflictStrategy.SKIP,
            ConflictStrategy.RENAME,
            ConflictStrategy.MANUAL,
        ):
            with (
                self.subTest(conflict_strategy=conflict_strategy),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                definition = _definition(
                    f"conflict-{conflict_strategy.value}",
                    mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
                    limit=2,
                )
                base_strategy = smoke_strategy_configuration()
                strategy = replace(
                    base_strategy,
                    recognition_type_policies=tuple(
                        replace(
                            type_policy,
                            organize_policy=replace(
                                type_policy.organize_policy,
                                conflict_strategy=conflict_strategy,
                            ),
                        )
                        for type_policy in base_strategy.recognition_type_policies
                    ),
                )
                incoming = root / "source/Media/incoming/A"
                incoming.mkdir(parents=True)
                alpha_source = incoming / "Alpha.Movie.2024.mkv"
                bravo_source = incoming / "Bravo.Movie.2024.mkv"
                alpha_source.write_bytes(b"alpha-new")
                bravo_source.write_bytes(b"bravo-new")
                alpha_target = root / (
                    "target/Movies/Anime/Alpha Movie (2024)/Alpha Movie (2024).mkv"
                )
                bravo_target = root / (
                    "target/Movies/Anime/Bravo Movie (2024)/Bravo Movie (2024).mkv"
                )
                alpha_target.parent.mkdir(parents=True)
                alpha_target.write_bytes(b"alpha-old")
                configuration = self._configuration(root, definition, strategy=strategy)
                storages = {
                    "source": LocalStorage("source", str(root / "source")),
                    "target": LocalStorage("target", str(root / "target")),
                }

                def storage_factory(external=None, storage_ids=None):
                    selected = storages
                    if storage_ids is not None:
                        selected = {
                            key: value for key, value in storages.items() if key in storage_ids
                        }
                    if external:
                        selected = {**selected, **external}
                    return selected

                with (
                    SQLiteTaskRepository(configuration.database_path) as repository,
                    SQLiteFileIndexRepository(configuration.database_path) as file_index,
                ):
                    job = self._emit(repository, definition)
                    grant_service = UnattendedExecutionGrantService(repository)
                    grant_service.grant(
                        definition,
                        configuration_snapshot_id=job.configuration_snapshot_id,
                        configuration_snapshot_digest=job.configuration_snapshot_digest,
                        configuration_snapshot_version=job.configuration_snapshot_version,
                        actor="admin",
                        confirmation=True,
                    )
                    finished = self._run(
                        repository,
                        self._service(
                            repository,
                            file_index,
                            configuration,
                            storage_factory,
                            SyntheticMetadataProvider(candidates),
                            grant_service,
                        ),
                    )
                    task = repository.get_task(finished.task_id)
                    items = {
                        Path(item.source_path).name: item
                        for item in repository.list_items(task.task_id)
                    }
                    results = {
                        Path(result.source_path).name: result
                        for result in repository.list_results(task.task_id)
                    }
                    self.assertEqual(
                        items[alpha_source.name].status,
                        {
                            ConflictStrategy.SKIP: TaskItemStatus.SKIPPED,
                            ConflictStrategy.RENAME: TaskItemStatus.SUCCESS,
                            ConflictStrategy.MANUAL: TaskItemStatus.WAITING_CONFIRM,
                        }[conflict_strategy],
                    )
                    self.assertEqual(items[bravo_source.name].status, TaskItemStatus.SUCCESS)
                    self.assertEqual(
                        task.status,
                        PersistentTaskStatus.PARTIAL_SUCCESS
                        if conflict_strategy is ConflictStrategy.MANUAL
                        else PersistentTaskStatus.COMPLETED,
                    )
                    self.assertEqual(
                        len(results), 1 if conflict_strategy is ConflictStrategy.MANUAL else 2
                    )
                    self.assertEqual(
                        results[bravo_source.name].status, TaskItemStatus.SUCCESS.value
                    )
                    self.assertEqual(bravo_target.read_bytes(), b"bravo-new")
                    self.assertEqual(alpha_target.read_bytes(), b"alpha-old")
                    if conflict_strategy is ConflictStrategy.SKIP:
                        self.assertEqual(results[alpha_source.name].operation, "SKIP")
                        self.assertTrue(alpha_source.exists())
                    elif conflict_strategy is ConflictStrategy.RENAME:
                        self.assertEqual(
                            results[alpha_source.name].status, TaskItemStatus.SUCCESS.value
                        )
                        renamed = root / "target" / results[alpha_source.name].destination_path
                        self.assertTrue(renamed.name.endswith("(1).mkv"))
                        self.assertEqual(renamed.read_bytes(), b"alpha-new")
                        self.assertFalse(alpha_source.exists())
                    else:
                        confirmations = repository.list_confirmations()
                        self.assertEqual(len(confirmations), 1)
                        self.assertEqual(confirmations[0].item_id, items[alpha_source.name].item_id)
                        checkpoint = ProcessingCheckpointService(
                            repository,
                            snapshot_validator=lambda _snapshot_id, _digest: None,
                        ).get(items[alpha_source.name].item_id)
                        self.assertEqual(checkpoint.blocker.kind, "conflict")
                        self.assertEqual(
                            checkpoint.blocker.resolution_path,
                            f"/api/v1/confirmations/{confirmations[0].confirmation_id}",
                        )
                        self.assertEqual(checkpoint.permitted_action_ids, ("resolve_conflict",))
                        self.assertTrue(alpha_source.exists())

    def test_authorized_invalid_destination_fails_closed_without_blocking_sibling(self) -> None:
        definition = _definition(
            "invalid-destination",
            mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
            limit=2,
        )
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "movie-alpha",
                    MediaType.MOVIE,
                    "Alpha Movie",
                    year=2024,
                    genres=("Animation",),
                    countries=("JP",),
                ),
                MediaCandidate(
                    "tmdb",
                    "show-bravo",
                    MediaType.TV,
                    "Bravo Show",
                    year=2024,
                ),
            ),
            episodes=(1,),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            alpha_source = root / "source/Media/incoming/A/Alpha.Movie.2024.mkv"
            bravo_source = root / "source/Media/incoming/B/Bravo.Show.2024.S01E01.mkv"
            alpha_source.parent.mkdir(parents=True)
            bravo_source.parent.mkdir(parents=True)
            alpha_source.write_bytes(b"alpha")
            bravo_source.write_bytes(b"bravo")
            configuration = self._configuration(root, definition)
            configuration = replace(
                configuration,
                media_libraries=(
                    MediaLibrary("movies", "Movies", "target", "target/.."),
                    configuration.media_libraries[1],
                ),
            )
            storages = {
                "source": LocalStorage("source", str(root / "source")),
                "target": LocalStorage("target", str(root / "target")),
            }

            def storage_factory(external=None, storage_ids=None):
                selected = storages
                if storage_ids is not None:
                    selected = {key: value for key, value in storages.items() if key in storage_ids}
                if external:
                    selected = {**selected, **external}
                return selected

            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                job = self._emit(repository, definition)
                grant_service = UnattendedExecutionGrantService(repository)
                grant_service.grant(
                    definition,
                    configuration_snapshot_id=job.configuration_snapshot_id,
                    configuration_snapshot_digest=job.configuration_snapshot_digest,
                    configuration_snapshot_version=job.configuration_snapshot_version,
                    actor="admin",
                    confirmation=True,
                )
                finished = self._run(
                    repository,
                    self._service(
                        repository,
                        file_index,
                        configuration,
                        storage_factory,
                        provider,
                        grant_service,
                    ),
                )
                task = repository.get_task(finished.task_id)
                self.assertEqual(task.status, PersistentTaskStatus.PARTIAL_SUCCESS)
                items = {
                    Path(item.source_path).name: item
                    for item in repository.list_items(task.task_id)
                }
                results = {
                    Path(result.source_path).name: result
                    for result in repository.list_results(task.task_id)
                }
                self.assertEqual(items[alpha_source.name].status, TaskItemStatus.FAILED)
                self.assertEqual(items[bravo_source.name].status, TaskItemStatus.SUCCESS)
                self.assertEqual(len(results), 2)
                checkpoint = ProcessingCheckpointService(
                    repository,
                    snapshot_validator=lambda _snapshot_id, _digest: None,
                ).get(items[alpha_source.name].item_id)
                self.assertEqual(checkpoint.error_category.value, "invalid_destination")
                self.assertEqual(checkpoint.failure.category, "invalid_destination")
                self.assertEqual(checkpoint.effect_certainty.value, "none")
                self.assertEqual(checkpoint.permitted_action_ids, ("investigate",))
                self.assertNotIn("retry", checkpoint.permitted_action_ids)
                self.assertEqual(results[alpha_source.name].effect_certainty, "none")
                self.assertEqual(results[bravo_source.name].status, TaskItemStatus.SUCCESS.value)
            self.assertTrue(alpha_source.exists())
            self.assertFalse(bravo_source.exists())
            self.assertFalse(
                any("Alpha Movie" in path.name for path in (root / "target").rglob("*"))
            )
            self.assertTrue(any("Bravo Show" in path.name for path in (root / "target").rglob("*")))

    def test_authorized_unstable_source_is_durable_and_not_counted_as_selected(self) -> None:
        definition = _definition(
            "unstable-source",
            mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
            limit=2,
        )
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "movie-alpha",
                    MediaType.MOVIE,
                    "Alpha Movie",
                    year=2024,
                    genres=("Animation",),
                    countries=("JP",),
                ),
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stable_source = root / "source/Media/incoming/A/Alpha.Movie.2024.mkv"
            unstable_source = root / "source/Media/incoming/A/Unstable.Movie.2024.mkv"
            stable_source.parent.mkdir(parents=True)
            stable_source.write_bytes(b"stable")
            unstable_source.write_bytes(b"unstable")
            old = time.time() - 7200
            os.utime(stable_source, (old, old))
            resource = ResourceLibrary(
                "resource",
                "Resource",
                "source",
                "Media",
                stability_policy=FileStabilityPolicy(minimum_age_seconds=3600),
            )
            configuration = self._configuration(root, definition, resource=resource)
            source_storage = LocalStorage("source", str(root / "source"))
            target_storage = LocalStorage("target", str(root / "target"))
            storages = {"source": source_storage, "target": target_storage}

            def storage_factory(external=None, storage_ids=None):
                selected = storages
                if storage_ids is not None:
                    selected = {key: value for key, value in storages.items() if key in storage_ids}
                if external:
                    selected = {**selected, **external}
                return selected

            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                job = self._emit(repository, definition)
                grant_service = UnattendedExecutionGrantService(repository)
                grant_service.grant(
                    definition,
                    configuration_snapshot_id=job.configuration_snapshot_id,
                    configuration_snapshot_digest=job.configuration_snapshot_digest,
                    configuration_snapshot_version=job.configuration_snapshot_version,
                    actor="admin",
                    confirmation=True,
                )
                finished = self._run(
                    repository,
                    self._service(
                        repository,
                        file_index,
                        configuration,
                        storage_factory,
                        provider,
                        grant_service,
                    ),
                )
                task = repository.get_task(finished.task_id)
                self.assertEqual(task.status, PersistentTaskStatus.PARTIAL_SUCCESS)
                items = {
                    Path(item.source_path).name: item
                    for item in repository.list_items(task.task_id)
                }
                results = {
                    Path(result.source_path).name: result
                    for result in repository.list_results(task.task_id)
                }
                self.assertEqual(items[stable_source.name].status, TaskItemStatus.SUCCESS)
                self.assertEqual(items[unstable_source.name].status, TaskItemStatus.FAILED)
                self.assertEqual(len(results), 2)
                unstable_checkpoint = ProcessingCheckpointService(
                    repository,
                    snapshot_validator=lambda _snapshot_id, _digest: None,
                ).get(items[unstable_source.name].item_id)
                self.assertEqual(unstable_checkpoint.failure.category, "unstable_source")
                self.assertEqual(unstable_checkpoint.effect_certainty.value, "none")
                self.assertEqual(unstable_checkpoint.retry_safety.value, "safe")
                self.assertEqual(unstable_checkpoint.permitted_action_ids, ("retry",))
                self.assertEqual(results[unstable_source.name].retry_category, "unstable_source")
                self.assertEqual(results[unstable_source.name].effect_certainty, "none")
                occurrence = repository.get_latest_automation_definition_occurrence(
                    definition.definition_id
                )
                self.assertEqual(occurrence.task_id, task.task_id)
                api = self._api(repository, (definition,))
                status, body = self._request(
                    api,
                    f"/api/v1/automation/task-definitions/{definition.definition_id}/occurrences",
                )
                self.assertEqual(status, 200, body)
                summary = body["items"][0]["outcomeSummary"]
                self.assertEqual(summary["totalItems"], 2)
                self.assertEqual(summary["counts"]["success"], 1)
                self.assertEqual(summary["counts"]["failed"], 1)
                self.assertFalse(summary["boundReached"])
                self.assertIn(
                    "Unstable source items remain recorded and were not selected.",
                    summary["bound"]["statement"],
                )
            self.assertFalse(stable_source.exists())
            self.assertTrue(unstable_source.exists())

    def test_authorized_provider_failure_preserves_first_sibling_and_never_auto_replays(
        self,
    ) -> None:
        definition = _definition(
            "provider-failure",
            mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
            limit=2,
        )
        candidates = (
            MediaCandidate(
                "tmdb",
                "movie-alpha",
                MediaType.MOVIE,
                "Alpha Movie",
                year=2024,
                genres=("Animation",),
                countries=("JP",),
            ),
            MediaCandidate(
                "tmdb",
                "movie-beta",
                MediaType.MOVIE,
                "Beta Movie",
                year=2024,
                genres=("Animation",),
                countries=("JP",),
            ),
        )

        class FailingMetadataProvider(SyntheticMetadataProvider):
            def search_movie(self, query, policy=None, **kwargs):
                if query.title_candidate == "Beta Movie":
                    raise MetadataError(
                        MetadataErrorCode.CONNECTION_FAILED,
                        "private-provider-token-should-not-persist",
                    )
                return super().search_movie(query, policy=policy, **kwargs)

        provider = FailingMetadataProvider(candidates)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "source/Media/incoming/A"
            incoming.mkdir(parents=True)
            alpha_source = incoming / "Alpha.Movie.2024.mkv"
            beta_source = incoming / "Beta.Movie.2024.mkv"
            alpha_source.write_bytes(b"alpha")
            beta_source.write_bytes(b"beta")
            configuration = self._configuration(root, definition)
            storages = {
                "source": LocalStorage("source", str(root / "source")),
                "target": LocalStorage("target", str(root / "target")),
            }

            def storage_factory(external=None, storage_ids=None):
                selected = storages
                if storage_ids is not None:
                    selected = {key: value for key, value in storages.items() if key in storage_ids}
                if external:
                    selected = {**selected, **external}
                return selected

            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                job = self._emit(repository, definition)
                grant_service = UnattendedExecutionGrantService(repository)
                grant_service.grant(
                    definition,
                    configuration_snapshot_id=job.configuration_snapshot_id,
                    configuration_snapshot_digest=job.configuration_snapshot_digest,
                    configuration_snapshot_version=job.configuration_snapshot_version,
                    actor="admin",
                    confirmation=True,
                )
                finished = self._run(
                    repository,
                    self._service(
                        repository,
                        file_index,
                        configuration,
                        storage_factory,
                        provider,
                        grant_service,
                    ),
                )
                task = repository.get_task(finished.task_id)
                self.assertEqual(task.status, PersistentTaskStatus.PARTIAL_SUCCESS)
                items = {
                    Path(item.source_path).name: item
                    for item in repository.list_items(task.task_id)
                }
                results = {
                    Path(result.source_path).name: result
                    for result in repository.list_results(task.task_id)
                }
                self.assertEqual(items[alpha_source.name].status, TaskItemStatus.SUCCESS)
                self.assertEqual(items[beta_source.name].status, TaskItemStatus.FAILED)
                self.assertEqual(results[alpha_source.name].status, TaskItemStatus.SUCCESS.value)
                self.assertEqual(results[beta_source.name].retry_category, "provider_failure")
                self.assertEqual(
                    len(repository.list_results_for_item(items[beta_source.name].item_id)), 1
                )
                self.assertEqual(items[beta_source.name].attempts, 1)
                checkpoint = ProcessingCheckpointService(
                    repository,
                    snapshot_validator=lambda _snapshot_id, _digest: None,
                ).get(items[beta_source.name].item_id)
                self.assertEqual(checkpoint.failure.category, "provider_failure")
                self.assertEqual(checkpoint.effect_certainty.value, "none")
                self.assertEqual(checkpoint.retry_safety.value, "safe")
                self.assertEqual(checkpoint.permitted_action_ids, ("retry",))
                self.assertNotIn("private-provider-token", json.dumps(checkpoint.document()))
                self.assertEqual(
                    repository.list_recovery_requests(items[beta_source.name].item_id), ()
                )
            self.assertFalse(alpha_source.exists())
            self.assertTrue(beta_source.exists())

    def test_authorized_mid_batch_storage_failure_preserves_first_sibling(self) -> None:
        definition = _definition(
            "storage-failure",
            mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
            limit=2,
        )
        candidates = (
            MediaCandidate(
                "tmdb",
                "movie-alpha",
                MediaType.MOVIE,
                "Alpha Movie",
                year=2024,
                genres=("Animation",),
                countries=("JP",),
            ),
            MediaCandidate(
                "tmdb",
                "movie-beta",
                MediaType.MOVIE,
                "Beta Movie",
                year=2024,
                genres=("Animation",),
                countries=("JP",),
            ),
        )

        class FailingTargetStorage(LocalStorage):
            def exists(self, path: str) -> bool:
                if path.endswith("Beta Movie (2024).mkv"):
                    raise StorageError(
                        StorageErrorCode.CONNECTION_LOST,
                        "exists",
                        path,
                        "private-storage-endpoint-should-not-persist",
                    )
                return super().exists(path)

        provider = SyntheticMetadataProvider(candidates)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "source/Media/incoming/A"
            incoming.mkdir(parents=True)
            alpha_source = incoming / "Alpha.Movie.2024.mkv"
            beta_source = incoming / "Beta.Movie.2024.mkv"
            alpha_source.write_bytes(b"alpha")
            beta_source.write_bytes(b"beta")
            configuration = self._configuration(root, definition)
            storages = {
                "source": LocalStorage("source", str(root / "source")),
                "target": FailingTargetStorage("target", str(root / "target")),
            }

            def storage_factory(external=None, storage_ids=None):
                selected = storages
                if storage_ids is not None:
                    selected = {key: value for key, value in storages.items() if key in storage_ids}
                if external:
                    selected = {**selected, **external}
                return selected

            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                job = self._emit(repository, definition)
                grant_service = UnattendedExecutionGrantService(repository)
                grant_service.grant(
                    definition,
                    configuration_snapshot_id=job.configuration_snapshot_id,
                    configuration_snapshot_digest=job.configuration_snapshot_digest,
                    configuration_snapshot_version=job.configuration_snapshot_version,
                    actor="admin",
                    confirmation=True,
                )
                finished = self._run(
                    repository,
                    self._service(
                        repository,
                        file_index,
                        configuration,
                        storage_factory,
                        provider,
                        grant_service,
                    ),
                )
                task = repository.get_task(finished.task_id)
                self.assertEqual(task.status, PersistentTaskStatus.PARTIAL_SUCCESS)
                items = {
                    Path(item.source_path).name: item
                    for item in repository.list_items(task.task_id)
                }
                results = {
                    Path(result.source_path).name: result
                    for result in repository.list_results(task.task_id)
                }
                self.assertEqual(items[alpha_source.name].status, TaskItemStatus.SUCCESS)
                self.assertEqual(items[beta_source.name].status, TaskItemStatus.FAILED)
                self.assertEqual(results[alpha_source.name].status, TaskItemStatus.SUCCESS.value)
                self.assertEqual(results[beta_source.name].retry_category, "storage_failure")
                self.assertEqual(
                    len(repository.list_results_for_item(items[beta_source.name].item_id)), 1
                )
                checkpoint = ProcessingCheckpointService(
                    repository,
                    snapshot_validator=lambda _snapshot_id, _digest: None,
                ).get(items[beta_source.name].item_id)
                self.assertEqual(checkpoint.failure.category, "storage_failure")
                self.assertEqual(checkpoint.effect_certainty.value, "none")
                self.assertEqual(checkpoint.retry_safety.value, "safe")
                self.assertEqual(checkpoint.permitted_action_ids, ("retry",))
                self.assertNotIn("private-storage-endpoint", json.dumps(checkpoint.document()))
                self.assertEqual(
                    repository.list_recovery_requests(items[beta_source.name].item_id), ()
                )
            self.assertFalse(alpha_source.exists())
            self.assertTrue(beta_source.exists())

    def test_revoked_automatic_mode_fails_before_task_and_mutation(self) -> None:
        definition = _definition(
            "revoked",
            mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "source" / "Media" / "incoming"
            incoming.mkdir(parents=True)
            media = incoming / "Alpha.Movie.2024.mkv"
            media.write_bytes(b"unchanged")
            before = _tree(root / "source")
            configuration = self._configuration(root, definition)
            source_guard, _target_guard, storage_factory = self._guarded_storage_factory(
                configuration
            )
            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                job = self._emit(repository, definition)
                grant_service = UnattendedExecutionGrantService(repository)
                grant = grant_service.grant(
                    definition,
                    configuration_snapshot_id=job.configuration_snapshot_id,
                    configuration_snapshot_digest=job.configuration_snapshot_digest,
                    configuration_snapshot_version=job.configuration_snapshot_version,
                    actor="admin",
                    confirmation=True,
                )
                grant_service.revoke(grant.grant_id, actor="admin")
                service = self._service(
                    repository,
                    file_index,
                    configuration,
                    storage_factory,
                    unattended_grant_service=grant_service,
                )
                finished = self._run(repository, service)
                self.assertEqual(finished.failure_category, "unattended_execution_grant_revoked")
                self.assertEqual(finished.failure_side_effects, "none")
                self.assertTrue(finished.failure_retry_safe)
                self.assertTrue(finished.failure_next_action)
                self.assertEqual(repository.list_tasks(), ())
                self.assertEqual(source_guard.mutation_calls["Move"], 0)
            self.assertEqual(_tree(root / "source"), before)

    def test_revocation_is_reread_between_items_and_preserves_first_result(self) -> None:
        definition = _definition(
            "boundary",
            mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
            limit=2,
        )
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "movie-a",
                    MediaType.MOVIE,
                    "Alpha Movie",
                    year=2024,
                    genres=("Animation",),
                    countries=("JP",),
                ),
                MediaCandidate(
                    "tmdb",
                    "movie-d",
                    MediaType.MOVIE,
                    "Delta Movie",
                    year=2025,
                    genres=("Animation",),
                    countries=("JP",),
                ),
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "source" / "Media" / "incoming" / "A"
            incoming.mkdir(parents=True)
            first = incoming / "Alpha.Movie.2024.mkv"
            second = incoming / "Delta.Movie.2025.mkv"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            configuration = self._configuration(root, definition)
            storages = {
                "source": LocalStorage("source", str(root / "source")),
                "target": LocalStorage("target", str(root / "target")),
            }

            def storage_factory(external=None, storage_ids=None):
                selected = storages
                if storage_ids is not None:
                    selected = {key: value for key, value in storages.items() if key in storage_ids}
                if external:
                    selected = {**selected, **external}
                return selected

            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                job = self._emit(repository, definition)
                grant_service = UnattendedExecutionGrantService(repository)
                grant = grant_service.grant(
                    definition,
                    configuration_snapshot_id=job.configuration_snapshot_id,
                    configuration_snapshot_digest=job.configuration_snapshot_digest,
                    configuration_snapshot_version=job.configuration_snapshot_version,
                    actor="admin",
                    confirmation=True,
                )

                class RevokingGrantService(UnattendedExecutionGrantService):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, **kwargs)
                        self.boundary_calls = 0

                    def assert_live(self, claimed_job, claimed_definition):
                        self.boundary_calls += 1
                        if self.boundary_calls == 2:
                            self.revoke(grant.grant_id, actor="admin", reason="boundary")
                        return super().assert_live(claimed_job, claimed_definition)

                revoking = RevokingGrantService(repository)
                service = self._service(
                    repository,
                    file_index,
                    configuration,
                    storage_factory,
                    provider,
                    revoking,
                )
                finished = self._run(repository, service)
                self.assertEqual(finished.status, AutomationJobStatus.COMPLETED)
                task = repository.get_task(finished.task_id)
                self.assertEqual(task.status, PersistentTaskStatus.PARTIAL_SUCCESS)
                items = {item.source_path: item for item in repository.list_items(task.task_id)}
                self.assertEqual(
                    items["Media/incoming/A/Alpha.Movie.2024.mkv"].status,
                    TaskItemStatus.SUCCESS,
                )
                self.assertEqual(
                    items["Media/incoming/A/Delta.Movie.2025.mkv"].status,
                    TaskItemStatus.FAILED,
                )
                self.assertIn(
                    "unattended_execution_grant_revoked",
                    items["Media/incoming/A/Delta.Movie.2025.mkv"].error,
                )
                results = repository.list_results(task.task_id)
                self.assertEqual(
                    [result.source_path for result in results],
                    [
                        "Media/incoming/A/Alpha.Movie.2024.mkv",
                        "Media/incoming/A/Delta.Movie.2025.mkv",
                    ],
                )
                self.assertEqual(results[0].status, TaskItemStatus.SUCCESS.value)
                self.assertEqual(results[1].status, TaskItemStatus.FAILED.value)
            self.assertFalse(first.exists())
            self.assertTrue(second.exists())

    def test_claim_boundary_failures_are_durable_and_do_not_create_tasks(self) -> None:
        scenarios = (
            (
                "version",
                lambda configuration, definition: replace(
                    configuration, configuration_snapshot_version=2
                ),
                "definition_version_mismatch",
            ),
            (
                "fingerprint",
                lambda configuration, definition: replace(
                    configuration,
                    automation_task_definitions=(
                        replace(definition, item_limit=definition.item_limit + 1),
                    ),
                ),
                "definition_fingerprint_mismatch",
            ),
            (
                "digest",
                lambda configuration, _definition: replace(
                    configuration, configuration_snapshot_digest="b" * 64
                ),
                "snapshot_digest_mismatch",
            ),
            (
                "missing-definition",
                lambda configuration, _definition: replace(
                    configuration, automation_task_definitions=()
                ),
                "definition_missing",
            ),
            (
                "disabled-definition",
                lambda configuration, definition: replace(
                    configuration,
                    automation_task_definitions=(_DisabledPinnedDefinition(definition),),
                ),
                "definition_disabled",
            ),
            (
                "missing-resource",
                lambda configuration, _definition: replace(configuration, resource_libraries=()),
                "resource_library_missing",
            ),
            (
                "disabled-resource",
                lambda configuration, definition: replace(
                    configuration,
                    resource_libraries=(
                        replace(configuration.resource_libraries[0], enabled=False),
                    ),
                ),
                "resource_library_disabled",
            ),
        )
        for name, mutate, category in scenarios:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                definition = _definition(name)
                configuration = self._configuration(root, definition)
                _source_guard, _target_guard, storage_factory = self._guarded_storage_factory(
                    configuration
                )
                with (
                    SQLiteTaskRepository(configuration.database_path) as repository,
                    SQLiteFileIndexRepository(configuration.database_path) as file_index,
                ):
                    self._emit(repository, definition)
                    drifted = mutate(configuration, definition)
                    finished = self._run(
                        repository,
                        self._service(repository, file_index, drifted, storage_factory),
                    )
                    self.assertEqual(finished.status, AutomationJobStatus.FAILED)
                    self.assertEqual(finished.failure_category, category)
                    self.assertTrue(finished.failure_durable_state)
                    self.assertEqual(finished.failure_side_effects, "none")
                    self.assertFalse(finished.failure_retry_safe)
                    self.assertTrue(finished.failure_next_action)
                    self.assertEqual(repository.list_tasks(), ())
                    occurrence = repository.get_latest_automation_definition_occurrence(name)
                    self.assertEqual(occurrence.outcome, "blocked")
                    self.assertEqual(occurrence.failure_category, category)

    def test_missing_non_directory_and_escaping_scope_fail_closed(self) -> None:
        cases = (
            ("missing", "missing", "scope_root_missing", None),
            ("file", "file", "scope_root_not_directory", "file"),
        )
        for name, scope, category, file_name in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                definition = _definition(name, scope=scope)
                configuration = self._configuration(root, definition)
                if file_name:
                    (root / "source" / "Media" / file_name).write_bytes(b"not-a-directory")
                _source_guard, _target_guard, storage_factory = self._guarded_storage_factory(
                    configuration
                )
                with (
                    SQLiteTaskRepository(configuration.database_path) as repository,
                    SQLiteFileIndexRepository(configuration.database_path) as file_index,
                ):
                    self._emit(repository, definition)
                    finished = self._run(
                        repository,
                        self._service(repository, file_index, configuration, storage_factory),
                    )
                    self.assertEqual(finished.failure_category, category)
                    self.assertEqual(repository.list_tasks(), ())
                    occurrence = repository.get_latest_automation_definition_occurrence(name)
                    self.assertEqual(occurrence.outcome, "blocked")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definition = _definition("escaping")
            configuration = self._configuration(root, definition)
            _source_guard, _target_guard, storage_factory = self._guarded_storage_factory(
                configuration
            )
            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                emitted = self._emit(repository, definition)
                service = self._service(repository, file_index, configuration, storage_factory)
                altered_job = replace(emitted, source_scope="../outside")
                with self.assertRaises(AutomationConfigurationUnavailable) as raised:
                    service.run(altered_job, lambda: False)
                self.assertEqual(raised.exception.evidence.category, "definition_pin_mismatch")
                self.assertEqual(repository.list_tasks(), ())

    def test_worker_uses_claimed_snapshot_identity_for_queued_definition(self) -> None:
        definition = _definition("pinned")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Media" / "incoming").mkdir(parents=True)
            (root / "source" / "Media" / "incoming" / "old.mkv").write_bytes(b"old")
            configuration = self._configuration(root, definition)
            newer = replace(
                configuration,
                automation_task_definitions=(replace(definition, source_scope="newer"),),
                configuration_snapshot_id="revision-2",
                configuration_snapshot_digest="c" * 64,
                configuration_snapshot_version=2,
            )
            with SQLiteTaskRepository(configuration.database_path) as repository:
                job = self._emit(repository, definition)
                calls = []

                def resolve(_path, **kwargs):
                    calls.append(kwargs)
                    self.assertEqual(kwargs["snapshot_id"], job.configuration_snapshot_id)
                    self.assertEqual(kwargs["snapshot_digest"], job.configuration_snapshot_digest)
                    return configuration

                with patch("mediaflow.final_cli._configuration", side_effect=resolve):
                    finished = AutomationWorker(
                        repository,
                        lambda candidate, cancelled: _run_queued_workflow(
                            candidate,
                            None,
                            cancelled,
                            repository=repository,
                        ),
                    ).run_next()
                self.assertEqual(finished.status, AutomationJobStatus.COMPLETED)
                self.assertEqual(len(calls), 1)
                self.assertEqual(finished.task_id is not None, True)
                task = repository.get_task(finished.task_id)
                self.assertEqual(task.scope_path, "Media/incoming")
                self.assertNotEqual(newer.configuration_snapshot_id, job.configuration_snapshot_id)

    def test_pending_cancellation_finalizes_definition_occurrence_without_task(self) -> None:
        definition = _definition("pending-cancel")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configuration = self._configuration(root, definition)
            with SQLiteTaskRepository(configuration.database_path) as repository:
                job = self._emit(repository, definition)
                cancelled = repository.request_job_cancellation(job.job_id, NOW)

                self.assertEqual(cancelled.status, AutomationJobStatus.CANCELLED)
                self.assertEqual(cancelled.failure_category, "workflow_cancelled")
                self.assertEqual(cancelled.failure_side_effects, "none")
                self.assertTrue(cancelled.failure_retry_safe)
                self.assertIn("no Task was created", cancelled.failure_durable_state)
                self.assertNotIn("linked Task", cancelled.failure_next_action)
                self.assertEqual(repository.list_tasks(), ())
                occurrence = repository.get_latest_automation_definition_occurrence(
                    definition.definition_id
                )
                self.assertEqual(occurrence.outcome, "cancelled")
                self.assertIsNone(occurrence.task_id)
                self.assertEqual(occurrence.failure_category, "workflow_cancelled")
                self.assertIn("no Task was created", occurrence.reason)
                self.assertNotIn("linked Task", occurrence.next_action)

                api = self._api(repository, (definition,))
                status, body = self._request(
                    api,
                    "/api/v1/automation/task-definitions/pending-cancel/occurrences",
                )
                self.assertEqual(status, 200, body)
                self.assertIsNone(body["items"][0]["taskId"])
                self.assertIn("no Task was created", body["items"][0]["reason"])
                self.assertNotIn("linked Task", body["items"][0]["nextAction"])
                status, body = self._request(api, "/api/v1/automation/task-definitions", query="")
                self.assertEqual(status, 200, body)
                state = body["items"][0]["occurrenceState"]
                self.assertIsNone(state["lastTaskId"])
                self.assertIn("no Task was created", state["lastReason"])
                self.assertNotIn("linked Task", state["nextAction"])

    def test_cancellation_preserves_completed_item_and_occurrence_evidence(self) -> None:
        definition = _definition("cancel", mode=AutomationTaskRunMode.SCAN_AND_PLAN)
        candidate = MediaCandidate(
            "tmdb",
            "movie-c",
            MediaType.MOVIE,
            "Charlie Movie",
            year=2024,
            genres=("Animation",),
            countries=("JP",),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "source" / "Media" / "incoming" / "C"
            incoming.mkdir(parents=True)
            (incoming / "Charlie.Movie.2024.mkv").write_bytes(b"one")
            (incoming / "Charlie.Movie.2025.mkv").write_bytes(b"two")
            configuration = self._configuration(root, definition)
            _source_guard, _target_guard, storage_factory = self._guarded_storage_factory(
                configuration
            )
            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                job = self._emit(repository, definition)
                cancellation_requested = False

                class CancellingProvider(SyntheticMetadataProvider):
                    def search_movie(self, query, policy=None, **kwargs):
                        nonlocal cancellation_requested
                        result = super().search_movie(query, policy=policy, **kwargs)
                        if not cancellation_requested:
                            cancellation_requested = True
                            repository.request_job_cancellation(job.job_id, datetime.now(UTC))
                        return result

                service = self._service(
                    repository,
                    file_index,
                    configuration,
                    storage_factory,
                    CancellingProvider((candidate,)),
                )
                finished = self._run(repository, service)
                self.assertEqual(finished.status, AutomationJobStatus.CANCELLED)
                self.assertTrue(finished.task_id)
                self.assertEqual(finished.failure_category, "workflow_cancelled")
                self.assertFalse(finished.failure_retry_safe)
                self.assertIn("completed Task items", finished.failure_durable_state)
                self.assertIn("linked Task", finished.failure_next_action)
                task = repository.get_task(finished.task_id)
                self.assertEqual(task.status, PersistentTaskStatus.CANCELLED)
                items = repository.list_items(task.task_id)
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0].status, TaskItemStatus.DRY_RUN)
                occurrence = repository.get_latest_automation_definition_occurrence(
                    definition.definition_id
                )
                self.assertEqual(occurrence.task_id, task.task_id)
                self.assertEqual(occurrence.outcome, "cancelled")
                self.assertEqual(occurrence.failure_category, "workflow_cancelled")
                self.assertIn("in-flight", occurrence.reason)
                self.assertIn("linked Task", occurrence.next_action)

                api = self._api(repository, (definition,))
                status, body = self._request(
                    api,
                    "/api/v1/automation/task-definitions/cancel/occurrences",
                )
                self.assertEqual(status, 200, body)
                self.assertEqual(body["items"][0]["taskId"], task.task_id)
                self.assertIn("completed Task items", body["items"][0]["reason"])
                self.assertIn("linked Task", body["items"][0]["nextAction"])

    def test_api_readback_links_task_without_audit_or_mutation(self) -> None:
        definition = _definition("api")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Media" / "incoming").mkdir(parents=True)
            (root / "source" / "Media" / "incoming" / "one.mkv").write_bytes(b"one")
            configuration = self._configuration(root, definition)
            _source_guard, _target_guard, storage_factory = self._guarded_storage_factory(
                configuration
            )
            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                self._emit(repository, definition)
                self._run(
                    repository,
                    self._service(repository, file_index, configuration, storage_factory),
                )
                api = self._api(repository, (definition,))
                before_audit = repository._connection.execute(
                    "SELECT COUNT(*) FROM security_audit"
                ).fetchone()[0]
                status, body = self._request(
                    api,
                    "/api/v1/automation/task-definitions/api/occurrences",
                )
                self.assertEqual(status, 200, body)
                task_id = repository.list_tasks()[0].task_id
                self.assertEqual(body["items"][0]["taskId"], task_id)
                self.assertEqual(body["items"][0]["outcome"], "completed")
                self.assertEqual(
                    repository._connection.execute(
                        "SELECT COUNT(*) FROM security_audit"
                    ).fetchone()[0],
                    before_audit,
                )
                status, body = self._request(api, "/api/v1/automation/task-definitions", query="")
                self.assertEqual(status, 200)
                self.assertEqual(
                    body["items"][0]["occurrenceState"]["lastTaskId"],
                    task_id,
                )

    @staticmethod
    def _api(repository, definitions):
        active = SimpleNamespace(
            revision_id=SNAPSHOT_ID,
            version=1,
            revision_sequence=1,
            digest=SNAPSHOT_DIGEST,
        )
        active.summary = lambda: {
            "revisionId": active.revision_id,
            "version": active.version,
            "revisionSequence": active.revision_sequence,
            "digest": active.digest,
        }
        api = MediaFlowApi(
            repository,
            None,
            principals=(
                ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
            ),
        )
        api._configuration_service = SimpleNamespace(active=lambda: active)
        api._configuration_objects = SimpleNamespace(
            revision_detail=lambda _revision_id: {
                "objects": {
                    "automationTaskDefinitions": [value.document() for value in definitions]
                }
            }
        )
        return api

    @staticmethod
    def _request(api, path: str, *, query: str = "limit=10"):
        statuses: list[str] = []
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "CONTENT_LENGTH": "0",
            "REMOTE_ADDR": "127.0.0.1",
            "wsgi.input": io.BytesIO(),
            "HTTP_AUTHORIZATION": "Bearer viewer-token",
        }
        result = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(result)


if __name__ == "__main__":
    unittest.main()
