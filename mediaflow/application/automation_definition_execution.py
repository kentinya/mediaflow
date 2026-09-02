"""Definition-pinned Worker handoff for scheduled, mutation-free runs."""

from __future__ import annotations

import posixpath
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from mediaflow.application.automation import (
    AutomationCancelled,
    AutomationClaimLost,
    AutomationConfigurationUnavailable,
    AutomationWorkflowFailed,
)
from mediaflow.application.library_pipeline import ResourceLibraryScanner
from mediaflow.application.media_organizer import MediaOrganizerBatchResult, MediaOrganizerService
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.scanner import StorageScanner, normalize_resource_root
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.application.unattended_execution import (
    UnattendedExecutionGrantError,
    UnattendedExecutionGrantService,
)
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationFailureEvidence,
    AutomationTaskDefinition,
    AutomationTaskRunMode,
)
from mediaflow.domain.library import ResourceLibrary, ScanMode
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.domain.task_persistence import PersistentTask, PersistentTaskStatus

StorageFactory = Callable[..., dict[str, object]]
ProviderFactory = Callable[[tuple[str, ...]], object]
StrategyFactory = Callable[..., object]
HistoryFactory = Callable[[str], object]


class DefinitionScopedExecutionService:
    """Run one Scheduler-emitted definition through existing authorities.

    The service deliberately separates pure pin/scope validation from adapter
    construction.  This keeps knowable fail-closed cases before Storage,
    Provider, Scanner, planner, and Task construction while reusing the normal
    ``MediaOrganizerService`` chain for scan-and-plan runs.
    """

    def __init__(
        self,
        repository,
        file_index,
        configuration,
        *,
        storage_factory: StorageFactory | None = None,
        provider_factory: ProviderFactory | None = None,
        strategy_factory: StrategyFactory | None = None,
        history_factory: HistoryFactory | None = None,
        unattended_grant_service: UnattendedExecutionGrantService | None = None,
        logger=None,
    ) -> None:
        self._repository = repository
        self._file_index = file_index
        self._configuration = configuration
        self._storage_factory = storage_factory or configuration.create_storages
        self._provider_factory = provider_factory
        self._strategy_factory = strategy_factory
        self._history_factory = history_factory
        self._unattended_grants = unattended_grant_service
        self._logger = logger

    def run(self, job, cancellation_check: Callable[[], bool]) -> str:
        """Consume a claimed definition Job and return its durable Task id."""

        definition = self._resolve_definition(job)
        resource = self._resolve_resource_library(definition)
        scope_root = self._resolve_scope_root(resource, definition, job)

        authority = None
        if definition.mode is AutomationTaskRunMode.AUTOMATIC_ORGANIZATION:
            if self._unattended_grants is None:
                raise self._failure(
                    "unattended_execution_authority_missing",
                    "automatic organization has no separate unattended execution grant; no Task "
                    "was created",
                    False,
                    "review the exact definition bounds and explicitly grant unattended execution",
                )
            try:
                authority = self._unattended_grants.authorize(job, definition)
            except UnattendedExecutionGrantError as error:
                raise self._failure(
                    error.code,
                    error.durable_state,
                    error.retry_safe,
                    error.next_action,
                ) from error

        if cancellation_check():
            raise AutomationCancelled()

        source_storages = self._preflight_scope_storage(resource, scope_root)
        coordinator = PersistentTaskCoordinator(self._repository, self._repository)
        task = coordinator.create(
            job.command.value,
            execute_authorized=authority is not None,
            scope_path=scope_root,
            item_limit=definition.item_limit,
            configuration_snapshot_id=job.configuration_snapshot_id,
            configuration_snapshot_digest=job.configuration_snapshot_digest,
            require_configuration_snapshot=True,
        )
        try:
            if definition.mode is AutomationTaskRunMode.SCAN_ONLY:
                self._run_scan_only(
                    coordinator,
                    task,
                    resource,
                    scope_root,
                    source_storages,
                    cancellation_check,
                )
            else:
                self._run_scan_and_plan(
                    coordinator,
                    task,
                    resource,
                    scope_root,
                    source_storages,
                    cancellation_check,
                    execute=authority is not None,
                    definition=definition,
                    job=job,
                )
        except AutomationCancelled:
            self._cancel_task_if_running(coordinator, task.task_id)
            raise
        except AutomationClaimLost:
            # The Worker no longer owns the Job.  Do not rewrite Task state
            # from a stale claimant.
            raise
        except Exception as error:
            if cancellation_check():
                self._cancel_task_if_running(coordinator, task.task_id)
                raise AutomationCancelled(task.task_id)
            self._fail_task(task.task_id)
            raise AutomationWorkflowFailed(
                task.task_id,
                AutomationFailureEvidence(
                    "definition_scoped_workflow_failed",
                    "linked Task failed before workflow completion; completed items are preserved",
                    "none",
                    True,
                    "inspect the linked Task and per-item state, repair the runtime condition, "
                    "then wait for a new occurrence",
                ),
            ) from error
        return task.task_id

    def _resolve_definition(self, job) -> Any:
        definition_id = getattr(job, "definition_id", None)
        if not isinstance(definition_id, str) or not definition_id.strip():
            raise self._failure(
                "definition_missing",
                "definition-pinned Job has no usable Automation Task Definition identity",
                False,
                "inspect the queued Job and emit a new occurrence from a valid Active definition",
            )
        definitions = tuple(getattr(self._configuration, "automation_task_definitions", ()))
        definition = next(
            (
                value
                for value in definitions
                if getattr(value, "definition_id", getattr(value, "id", None)) == definition_id
            ),
            None,
        )
        if definition is None:
            raise self._failure(
                "definition_missing",
                "pinned Automation Task Definition is absent from the saved configuration snapshot",
                False,
                "restore the saved definition snapshot or explicitly emit a new occurrence",
            )
        if not isinstance(definition, AutomationTaskDefinition):
            try:
                definition = AutomationTaskDefinition.from_document(definition)
            except (TypeError, ValueError) as error:
                raise self._failure(
                    "definition_invalid",
                    "pinned Automation Task Definition cannot be consumed safely",
                    False,
                    "validate and activate a corrected definition, then emit a new occurrence",
                ) from error
        self._verify_definition_pins(job, definition)
        if not definition.enabled:
            raise self._failure(
                "definition_disabled",
                "pinned Automation Task Definition is disabled; no work was started",
                False,
                "enable the definition in a new validated Active revision before scheduling it",
            )
        return definition

    def _verify_definition_pins(self, job, definition: AutomationTaskDefinition) -> None:
        configuration_id = getattr(self._configuration, "configuration_snapshot_id", None)
        configuration_digest = getattr(self._configuration, "configuration_snapshot_digest", None)
        if not job.configuration_snapshot_id or not job.configuration_snapshot_digest:
            raise self._failure(
                "job_snapshot_incomplete",
                "definition-pinned Job does not match one complete saved configuration snapshot",
                False,
                "restore the exact saved snapshot identity, then emit a new occurrence",
            )
        if (
            not configuration_id
            or not configuration_digest
            or configuration_id != job.configuration_snapshot_id
        ):
            raise self._failure(
                "snapshot_missing",
                "the Job's pinned configuration snapshot is not available to the Worker",
                False,
                "restore the exact saved published revision, then emit a new occurrence",
            )
        if configuration_digest != job.configuration_snapshot_digest:
            raise self._failure(
                "snapshot_digest_mismatch",
                "the Worker configuration digest does not match the Job's pinned snapshot",
                False,
                "restore the exact saved published revision, then emit a new occurrence",
            )
        configuration_version = getattr(self._configuration, "configuration_snapshot_version", None)
        if (
            isinstance(configuration_version, bool)
            or not isinstance(configuration_version, int)
            or configuration_version < 1
            or job.definition_version != configuration_version
        ):
            raise self._failure(
                "definition_version_mismatch",
                "pinned Automation Task Definition version does not match the saved snapshot",
                False,
                "activate the intended definition version and emit a new occurrence",
            )
        if definition.definition_fingerprint != job.definition_fingerprint:
            raise self._failure(
                "definition_fingerprint_mismatch",
                "pinned Automation Task Definition fingerprint does not match the saved snapshot",
                False,
                "activate the intended definition content and emit a new occurrence",
            )
        expected_mode = definition.mode
        expected_command = {
            AutomationTaskRunMode.SCAN_ONLY: AutomationCommand.SCAN,
            AutomationTaskRunMode.SCAN_AND_PLAN: AutomationCommand.PREVIEW,
            AutomationTaskRunMode.AUTOMATIC_ORGANIZATION: AutomationCommand.ORGANIZE,
        }[expected_mode]
        if (
            job.run_mode != expected_mode
            or job.command != expected_command
            or job.resource_library_id != definition.resource_library_id
            or job.source_scope != definition.source_scope
            or job.limit != definition.item_limit
        ):
            raise self._failure(
                "definition_pin_mismatch",
                "definition-pinned Job fields do not match the saved definition identity",
                False,
                "inspect the queued Job and emit a new occurrence from the saved definition",
            )

    def _resolve_resource_library(self, definition) -> ResourceLibrary:
        resource = next(
            (
                value
                for value in getattr(self._configuration, "resource_libraries", ())
                if value.library_id == definition.resource_library_id
            ),
            None,
        )
        if resource is None:
            raise self._failure(
                "resource_library_missing",
                "referenced ResourceLibrary is absent from the saved configuration snapshot",
                False,
                "repair the ResourceLibrary reference and activate a new definition snapshot",
            )
        if not resource.enabled:
            raise self._failure(
                "resource_library_disabled",
                "referenced ResourceLibrary is disabled; no work was started",
                False,
                "enable the ResourceLibrary in a new validated Active revision",
            )
        return resource

    def _resolve_scope_root(self, resource, definition, job) -> str:
        try:
            library_root = normalize_resource_root(resource.root_path)
            source_scope = AutomationTaskDefinition.normalize_scope(definition.source_scope)
            scoped_root = normalize_resource_root(posixpath.join(library_root, source_scope or ""))
        except (TypeError, ValueError) as error:
            raise self._failure(
                "scope_root_invalid",
                "configured Storage-relative source scope is invalid",
                False,
                "correct the definition scope inside the ResourceLibrary root and activate it "
                "again",
            ) from error
        if not _contains(library_root, scoped_root):
            raise self._failure(
                "scope_outside_resource_library",
                "resolved source scope is outside the configured ResourceLibrary root",
                False,
                "replace the scope with a normalized sub-scope inside the ResourceLibrary root",
            )
        try:
            job_scope = AutomationTaskDefinition.normalize_scope(job.source_scope)
        except (TypeError, ValueError) as error:
            raise self._failure(
                "scope_root_invalid",
                "pinned Job source scope is not a safe Storage-relative path",
                False,
                "discard the altered Job and emit a new occurrence from the saved definition",
            ) from error
        if job_scope != definition.source_scope:
            raise self._failure(
                "definition_pin_mismatch",
                "pinned Job source scope does not match the saved definition",
                False,
                "inspect the queued Job and emit a new occurrence from the saved definition",
            )
        return scoped_root

    def _preflight_scope_storage(self, resource, scope_root) -> dict[str, object]:
        try:
            storages = self._storage_factory(storage_ids={resource.storage_id})
            storage = storages.get(resource.storage_id)
            if storage is None:
                raise LookupError("source Storage adapter is unavailable")
            entry = storage.stat(scope_root)
        except StorageError as error:
            category = (
                "scope_root_missing"
                if error.code in {StorageErrorCode.NOT_FOUND, StorageErrorCode.INVALID_PATH}
                else "scope_root_unavailable"
            )
            raise self._failure(
                category,
                "configured source scope root is unavailable",
                False,
                "restore the configured source directory and explicitly retry the occurrence",
            ) from error
        except (LookupError, OSError, RuntimeError, ValueError) as error:
            raise self._failure(
                "scope_root_unavailable",
                "configured source scope root could not be opened safely",
                False,
                "repair the source Storage configuration and explicitly retry the occurrence",
            ) from error
        if not entry.is_directory:
            raise self._failure(
                "scope_root_not_directory",
                "configured source scope root is not a directory",
                False,
                "select a directory scope inside the ResourceLibrary and emit a new occurrence",
            )
        return storages

    def _run_scan_only(
        self,
        coordinator,
        task: PersistentTask,
        resource: ResourceLibrary,
        scope_root: str,
        storages: Mapping[str, object],
        cancellation_check: Callable[[], bool],
    ) -> None:
        self._require_file_index()
        scoped = replace(resource, root_path=scope_root, scan_mode=ScanMode.INCREMENTAL)
        cancellation = _CancellationBridge(cancellation_check)

        def on_discovered(library, file) -> None:
            if cancellation_check():
                cancellation.cancel()
                return
            coordinator.record_discovered(
                task.task_id,
                file.storage_id,
                library.library_id,
                file.path,
                f"{file.storage_id}:{file.path}",
            )

        batch = ResourceLibraryScanner(
            StorageScanner(dict(storages), self._file_index, logger=self._logger),
            (scoped,),
            storages,
        ).scan_all(
            limit=task.item_limit,
            on_discovered=on_discovered,
            cancellation_check=cancellation.should_stop,
        )
        if cancellation_check():
            self._cancel_task_if_running(coordinator, task.task_id)
            raise AutomationCancelled(task.task_id)
        if coordinator.pause_requested(task.task_id):
            coordinator.acknowledge_pause(task.task_id)
            return
        errors = tuple(error for result in batch.results for error in result.errors)
        coordinator.finish(task.task_id, MediaOrganizerBatchResult((), errors))

    def _run_scan_and_plan(
        self,
        coordinator,
        task: PersistentTask,
        resource: ResourceLibrary,
        scope_root: str,
        source_storages: Mapping[str, object],
        cancellation_check: Callable[[], bool],
        *,
        execute: bool = False,
        definition=None,
        job=None,
    ) -> None:
        self._require_file_index()
        if self._provider_factory is None or self._strategy_factory is None:
            raise RuntimeError("definition-scoped analysis factories are unavailable")
        if self._history_factory is None:
            raise RuntimeError("definition-scoped history factory is unavailable")
        storages = self._storage_factory(external=dict(source_storages))
        if resource.storage_id not in storages:
            raise RuntimeError("definition-scoped source Storage is unavailable")
        provider_ids = tuple(
            dict.fromkeys(
                policy.provider_id
                for policy in getattr(self._configuration.strategy, "metadata_policies", ())
                if getattr(policy, "enabled", True) and getattr(policy, "provider_id", None)
            )
        ) or ("tmdb",)
        providers = self._provider_factory(provider_ids)
        strategy = self._strategy_factory(
            self._configuration.strategy,
            providers,
            storages=storages,
        )
        scoped = replace(resource, root_path=scope_root, scan_mode=ScanMode.INCREMENTAL)
        display_root = dict(getattr(self._configuration, "resource_display_roots", ())).get(
            resource.library_id, resource.root_path
        )
        if scoped_root_scope := _relative_scope(resource.root_path, scope_root):
            display_root = posixpath.join(display_root, scoped_root_scope)

        def workflow_stop() -> bool:
            return bool(cancellation_check() or coordinator.pause_requested(task.task_id))

        service = MediaOrganizerService(
            strategy,
            StorageScanner(storages, self._file_index, logger=self._logger),
            storages,
            {item.library_id: item for item in getattr(self._configuration, "media_libraries", ())},
            self._configuration.strategy.recognition_type_policies,
            self._history_factory(self._configuration.history_path),
            executor=OrganizerExecutor(self._logger),
            source_display_roots={resource.library_id: display_root},
            logger=self._logger,
            task_coordinator=coordinator,
            task_id=task.task_id,
            retry_policy=self._configuration.workflow_retry_policy,
            retry_cancellation_check=workflow_stop,
            secret_free_errors=True,
            before_execute=(
                (lambda: self._unattended_grants.assert_live(job, definition))
                if execute and self._unattended_grants is not None
                else None
            ),
        )
        summary = service.process_library(
            scoped,
            execute=execute,
            limit=task.item_limit,
            cancellation_check=workflow_stop,
        )
        if cancellation_check():
            self._cancel_task_if_running(coordinator, task.task_id)
            raise AutomationCancelled(task.task_id)
        if coordinator.pause_requested(task.task_id):
            coordinator.acknowledge_pause(task.task_id)
            return
        coordinator.finish(task.task_id, summary)

    def _require_file_index(self) -> None:
        if self._file_index is None:
            raise RuntimeError("definition-scoped Task requires the persistent FileIndex")

    def _cancel_task_if_running(self, coordinator, task_id: str) -> None:
        task = self._repository.get_task(task_id)
        if task is not None and task.status is PersistentTaskStatus.RUNNING:
            coordinator.cancel(task_id)

    def _fail_task(self, task_id: str) -> None:
        task = self._repository.get_task(task_id)
        if task is None or task.status is not PersistentTaskStatus.RUNNING:
            return
        from datetime import UTC, datetime

        self._repository.update_task(
            replace(
                task,
                status=PersistentTaskStatus.FAILED,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error="definition-scoped workflow failed before Task completion",
            )
        )

    @staticmethod
    def _failure(category: str, state: str, retry_safe: bool, next_action: str):
        return AutomationConfigurationUnavailable(
            AutomationFailureEvidence(
                category,
                state,
                "none",
                retry_safe,
                next_action,
            )
        )


class _CancellationBridge:
    def __init__(self, callback: Callable[[], bool]) -> None:
        self._callback = callback
        self._cancelled = False

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    def should_stop(self) -> bool:
        if self._cancelled:
            return True
        if self._callback():
            self._cancelled = True
        return self._cancelled


def _contains(parent: str, child: str) -> bool:
    return not parent or child == parent or child.startswith(parent.rstrip("/") + "/")


def _relative_scope(library_root: str, scope_root: str) -> str | None:
    base = normalize_resource_root(library_root)
    if not base:
        return scope_root or None
    if scope_root == base:
        return None
    return scope_root.removeprefix(base + "/")


__all__ = ["DefinitionScopedExecutionService"]
