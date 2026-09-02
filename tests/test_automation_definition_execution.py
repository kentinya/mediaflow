from __future__ import annotations

import io
import json
import tempfile
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
from mediaflow.application.read_only_storage import ReadOnlyStorageGuard
from mediaflow.application.strategy_test import (
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.domain.automation import (
    AutomationJobStatus,
    AutomationTaskDefinition,
    AutomationTaskRunMode,
    SchedulerConfigurationSnapshot,
)
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
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

    def _service(self, repository, file_index, configuration, storage_factory, provider=None):
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
                self.assertFalse(cancelled.failure_retry_safe)
                self.assertEqual(repository.list_tasks(), ())
                occurrence = repository.get_latest_automation_definition_occurrence(
                    definition.definition_id
                )
                self.assertEqual(occurrence.outcome, "cancelled")
                self.assertIsNone(occurrence.task_id)
                self.assertEqual(occurrence.failure_category, "workflow_cancelled")
                self.assertIn("completed Task items", occurrence.reason)

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
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                )
                api._configuration_service = SimpleNamespace(active=lambda: active)
                api._configuration_objects = SimpleNamespace(
                    revision_detail=lambda _revision_id: {
                        "objects": {"automationTaskDefinitions": [definition.document()]}
                    }
                )
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
