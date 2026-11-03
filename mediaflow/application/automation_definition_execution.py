"""Definition-pinned Worker handoff for scheduled and explicit one-run organizing."""

from __future__ import annotations

import posixpath
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from mediaflow.application.automation import (
    AutomationCancelled,
    AutomationClaimLost,
    AutomationConfigurationUnavailable,
    AutomationWorkflowFailed,
)
from mediaflow.application.media_organizer import (
    IncompleteOrganizingScope,
    MediaOrganizerBatchResult,
    MediaOrganizerService,
)
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.scanner import StorageScanner, normalize_resource_root
from mediaflow.application.task_runtime import KernelTaskCoordinator, PersistentTaskCoordinator
from mediaflow.application.unattended_execution import (
    UnattendedExecutionGrantError,
    UnattendedExecutionGrantService,
)
from mediaflow.domain.automation import (
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

    Only a supported definition intent with explicit live authority can run.
    """

    def __init__(
        self,
        repository,
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
        self._configuration = configuration
        self._storage_factory = storage_factory or configuration.create_storages
        self._provider_factory = provider_factory
        self._strategy_factory = strategy_factory
        self._history_factory = history_factory
        self._unattended_grants = unattended_grant_service
        self._logger = logger

    def run(
        self,
        task,
        scheduling,
        claim,
        *,
        run_once: bool,
        cancellation_check: Callable[[], bool],
        clock=None,
        heartbeat: Callable[[], bool] | None = None,
    ) -> str:
        """Consume one already-admitted definition Task.

        The Task owns its identity, admitted pin, source scope, item limit and
        claim fence.  This service resolves the exact pinned definition from
        that pin and runs the one production pipeline; it never creates a
        second Task, Job or queue entry.  A recorded pre-amendment mode fails
        closed before any adapter or Provider call.
        """

        definition = self._resolve_definition(task)
        resource = self._resolve_resource_library(definition)
        scope_root = self._resolve_scope_root(resource, definition, task, run_once=run_once)

        if self._unattended_grants is None:
            raise self._failure(
                "automation_execution_authority_unavailable",
                "the definition-scoped execution authority is unavailable; no work was started",
                False,
                "restore the configured permission authority and let the next due occurrence "
                "or Run once command execute",
            )
        try:
            self._unattended_grants.authorize_task(
                task,
                definition,
                run_once=run_once,
            )
        except UnattendedExecutionGrantError as error:
            raise self._failure(
                error.code,
                error.durable_state,
                error.retry_safe,
                error.next_action,
            ) from error

        if cancellation_check():
            raise AutomationCancelled(task.task_id)

        if task.configuration_snapshot_id != self._configuration.configuration_snapshot_id or (
            task.configuration_snapshot_digest != self._configuration.configuration_snapshot_digest
        ):
            raise self._failure(
                "snapshot_digest_mismatch",
                "the Task's pinned configuration snapshot is not available to the Worker",
                False,
                "restore the exact saved published revision, then let the Task run",
            )
        if task.status is PersistentTaskStatus.CANCELLED:
            raise AutomationCancelled(task.task_id)
        if task.status not in {PersistentTaskStatus.PENDING, PersistentTaskStatus.RUNNING}:
            # A reclaimed intent must never scan a previously entered Task again:
            # completed/uncertain effects may still exist.
            raise AutomationWorkflowFailed(
                task.task_id,
                AutomationFailureEvidence(
                    "task_already_started",
                    "the admitted Task and prior item effects are retained",
                    "unknown",
                    False,
                    "inspect the existing task; completed or uncertain effects are never replayed",
                ),
            )

        source_storages = self._preflight_scope_storage(resource, scope_root)
        coordinator = self._coordinator((scheduling, claim), clock=clock, heartbeat=heartbeat)
        try:
            self._run_scan_and_plan(
                coordinator,
                task,
                resource,
                scope_root,
                source_storages,
                cancellation_check,
                execute=True,
                definition=definition,
                run_once=run_once,
                heartbeat=heartbeat,
            )
        except AutomationCancelled:
            self._cancel_task_if_running(coordinator, task.task_id)
            raise
        except AutomationClaimLost:
            raise
        except IncompleteOrganizingScope as error:
            self._fail_task(task.task_id, message=str(error))
            raise AutomationWorkflowFailed(
                task.task_id,
                AutomationFailureEvidence(
                    error.reason,
                    "complete scope proof failed before any media effect",
                    "none",
                    False,
                    "narrow the saved source scope or repair unreadable entries, "
                    "then start a new Run once; no prefix was executed",
                ),
            ) from error
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
        if coordinator.cancellation_observed(task.task_id):
            raise AutomationCancelled(task.task_id)
        return task.task_id

    def _resolve_definition(self, task) -> Any:
        reader = getattr(self._repository, "get_run_display_context", None)
        display = reader(task.task_id) if callable(reader) else None
        definition_id = display.origin_definition_id if display is not None else None
        if not isinstance(definition_id, str) or not definition_id.strip():
            raise self._failure(
                "definition_missing",
                "the admitted Task has no usable Automation Task Definition identity",
                False,
                "inspect the Task's durable definition origin and admit a new occurrence",
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
                "restore the saved definition snapshot or explicitly admit a new occurrence",
            )
        if not isinstance(definition, AutomationTaskDefinition):
            try:
                definition = AutomationTaskDefinition.from_document(definition)
            except (TypeError, ValueError) as error:
                raise self._failure(
                    "definition_invalid",
                    "pinned Automation Task Definition cannot be consumed safely",
                    False,
                    "validate and activate a corrected definition, then admit a new occurrence",
                ) from error
        try:
            AutomationTaskRunMode.parse(definition.mode)
        except ValueError as error:
            raise self._failure(
                "definition_invalid",
                "unsupported definition mode; no Task was created",
                False,
                "validate the definition configuration before submitting work",
            ) from error
        self._verify_definition_pins(task, definition)
        if (
            not getattr(display, "origin_kind", None) == "definition-run-once"
            and not definition.enabled
        ):
            raise self._failure(
                "definition_disabled",
                "pinned Automation Task Definition is disabled; no scheduled work was started",
                False,
                "enable the definition in a new checked published revision before scheduling it, "
                "or use Run once for one deliberate execution",
            )
        return definition

    def _verify_definition_pins(self, task, definition: AutomationTaskDefinition) -> None:
        configuration_id = getattr(self._configuration, "configuration_snapshot_id", None)
        configuration_digest = getattr(self._configuration, "configuration_snapshot_digest", None)
        if not task.configuration_snapshot_id or not task.configuration_snapshot_digest:
            raise self._failure(
                "task_snapshot_incomplete",
                "the admitted Task has no complete saved configuration snapshot pin",
                False,
                "restore the exact saved snapshot identity, then admit a new occurrence",
            )
        if (
            not configuration_id
            or not configuration_digest
            or configuration_id != task.configuration_snapshot_id
            or configuration_digest != task.configuration_snapshot_digest
        ):
            raise self._failure(
                "snapshot_missing",
                "the Task's pinned configuration snapshot is not available to the Worker",
                False,
                "restore the exact saved published revision, then admit a new occurrence",
            )
        expected_limit = _effective_item_limit(task.item_limit, definition)
        if task.item_limit is not None and task.item_limit != expected_limit:
            raise self._failure(
                "definition_pin_mismatch",
                "the admitted Task item limit does not match the saved definition identity",
                False,
                "inspect the admitted Task and admit a new occurrence from the saved definition",
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

    def _resolve_scope_root(self, resource, definition, task, *, run_once: bool) -> str:
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
            admitted_scope = AutomationTaskDefinition.normalize_scope(task.scope_path)
        except (TypeError, ValueError) as error:
            raise self._failure(
                "scope_root_invalid",
                "the admitted Task source scope is not a safe Storage-relative path",
                False,
                "inspect the admitted Task and admit a new occurrence from the saved definition",
            ) from error
        expected_scope = (
            normalize_resource_root(posixpath.join(library_root, definition.source_scope or ""))
            if run_once
            else definition.source_scope
        )
        # A Run once admission may persist either the definition-relative scope
        # or its resolved Storage-relative root, depending on the entrance.  Both
        # name the same admitted source; any other value is a pin mismatch.
        allowed_scopes = {expected_scope, definition.source_scope}
        if admitted_scope not in allowed_scopes:
            raise self._failure(
                "definition_pin_mismatch",
                "the admitted Task source scope does not match the saved definition",
                False,
                "inspect the admitted Task and admit a new occurrence from the saved definition",
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
        run_once: bool = False,
        heartbeat: Callable[[], bool] | None = None,
    ) -> None:
        if self._provider_factory is None or self._strategy_factory is None:
            raise RuntimeError("definition-scoped analysis factories are unavailable")
        if self._history_factory is None:
            raise RuntimeError("definition-scoped history factory is unavailable")
        storages = self._storage_factory(external=dict(source_storages))
        if heartbeat is not None:
            # A long Storage listing/stat is ordinary work, not a dead owner.
            # Every adapter call renews the Task and Worker before it starts and
            # after it returns; a real loss of ownership stops the next call.
            storages = {key: _HeartbeatStorage(value, heartbeat) for key, value in storages.items()}
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
        if heartbeat is not None:
            providers = _HeartbeatProviderRegistry(providers, heartbeat)
        strategy = self._strategy_factory(
            self._configuration.strategy,
            providers,
            storages=storages,
        )
        scoped = replace(resource, root_path=scope_root, scan_mode=ScanMode.INCREMENTAL)
        # Plan identity must use the same Storage-relative source as native
        # item recovery. A configured display/host root must not change its ID.
        display_root = resource.root_path
        if scoped_root_scope := _relative_scope(resource.root_path, scope_root):
            display_root = posixpath.join(display_root, scoped_root_scope)

        def workflow_stop() -> bool:
            return bool(
                cancellation_check()
                or coordinator.pause_requested(task.task_id)
                or coordinator.cancellation_observed(task.task_id)
            )

        from mediaflow.application.automation_execution_intent import BoundedScopeReader

        scanner_storages = (
            {key: BoundedScopeReader(value, root=scope_root) for key, value in storages.items()}
            if run_once
            else storages
        )
        service = MediaOrganizerService(
            strategy,
            StorageScanner(scanner_storages, logger=self._logger),
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
            persist_failure_explanations=True,
            # B46.3-05: a scheduled occurrence is an existing entrance into the
            # same concrete sources a Files admission may already own.  Its own
            # item admission therefore asks the shared durable ownership boundary
            # inside the same decision, so a queued/paused/decision-pending Files
            # source can never be consumed (moved, deleted on the source side or
            # re-analyzed as this run's own work) by a later occurrence.  A source
            # that is genuinely free still runs exactly as before, and the
            # refused sibling is published as its own per-item outcome.
            enforce_source_ownership=True,
            # Slice 47 RO-6: a definition due/Run once pass excludes a file whose
            # same-version latest formal organizing outcome is failed/partial —
            # per file, before any Provider call.  A deliberate manual request is
            # never excluded by that history; it reaches its own summary instead.
            exclude_failed_history=True,
            mutation_authority=(
                (
                    lambda _plan, _boundary: self._unattended_grants.assert_live_task(
                        task, definition, run_once=run_once
                    )
                )
                if execute and self._unattended_grants is not None
                else None
            ),
        )
        summary = service.process_library(
            scoped,
            execute=execute,
            limit=task.item_limit,
            cancellation_check=workflow_stop,
            require_complete_scope=run_once,
            # A due pass and a Run once both refuse to execute a readable
            # prefix when any admitted directory could not be enumerated.
            # Run once additionally proves its complete saved scope fits the
            # admitted bound (``require_complete_scope``).
            require_readable_scope=True,
        )
        if cancellation_check():
            self._cancel_task_if_running(coordinator, task.task_id)
            raise AutomationCancelled(task.task_id)
        if coordinator.pause_requested(task.task_id):
            coordinator.acknowledge_pause(task.task_id)
            return
        coordinator.finish(task.task_id, summary)

    def _cancel_task_if_running(self, coordinator, task_id: str) -> None:
        task = self._repository.get_task(task_id)
        if task is not None and task.status is PersistentTaskStatus.RUNNING:
            coordinator.cancel(task_id)

    def _fail_task(
        self,
        task_id: str,
        *,
        message: str = "definition-scoped workflow failed before Task completion",
    ) -> None:
        task = self._repository.get_task(task_id)
        if task is None or task.status is not PersistentTaskStatus.RUNNING:
            return
        if self._kernel_managed(task_id):
            # A kernel-managed Task is only published FAILED by its resident Task
            # engine under the live claim fence; a generic writer is refused.
            return
        self._repository.update_task(
            replace(
                task,
                status=PersistentTaskStatus.FAILED,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error=message,
            )
        )

    def _kernel_managed(self, task_id: str) -> bool:
        """Whether this Task is published by the scheduling kernel.

        A generic Task writer must never publish a kernel-managed Task; the
        resident Task engine owns its terminal settlement under the claim fence.
        """

        reader = getattr(self._repository, "get_task_scheduling", None)
        if not callable(reader):
            return False
        try:
            return reader(task_id) is not None
        except Exception:  # noqa: BLE001 - an unreadable kernel row fails closed
            return True

    def run_legacy_schedule(
        self,
        task,
        scheduling,
        claim,
        *,
        cancellation_check: Callable[[], bool],
        clock=None,
        heartbeat: Callable[[], bool] | None = None,
    ) -> str:
        """Advance one already-admitted legacy interval/Cron occurrence.

        The occurrence is the Task itself.  This reuses the same production
        ``MediaOrganizerService``/``OrganizerExecutor`` pipeline and the same
        claim-fenced publication coordinator as a definition occurrence; the
        only difference is that a legacy schedule has no saved definition, so
        its admitted scope is every configured ResourceLibrary.
        """

        if getattr(claim, "task_id", None) != getattr(task, "task_id", None):
            raise ValueError("legacy schedule Task claim identity does not match")
        if not task.execute_authorized:
            raise RuntimeError("legacy schedule Task lacks persisted execute authorization")
        if self._provider_factory is None or self._strategy_factory is None:
            raise RuntimeError("legacy schedule analysis factories are unavailable")
        if self._history_factory is None:
            raise RuntimeError("legacy schedule history factory is unavailable")
        storages = self._storage_factory(external={})
        if heartbeat is not None:
            storages = {key: _HeartbeatStorage(value, heartbeat) for key, value in storages.items()}
        provider_ids = tuple(
            dict.fromkeys(
                policy.provider_id
                for policy in getattr(self._configuration.strategy, "metadata_policies", ())
                if getattr(policy, "enabled", True) and getattr(policy, "provider_id", None)
            )
        ) or ("tmdb",)
        providers = self._provider_factory(provider_ids)
        if heartbeat is not None:
            providers = _HeartbeatProviderRegistry(providers, heartbeat)
        strategy = self._strategy_factory(
            self._configuration.strategy,
            providers,
            storages=storages,
        )
        coordinator = KernelTaskCoordinator(
            self._repository,
            self._repository,
            scheduling,
            claim,
            clock=clock,
            heartbeat=heartbeat,
        )

        def workflow_stop() -> bool:
            return bool(
                cancellation_check()
                or coordinator.pause_requested(task.task_id)
                or coordinator.cancellation_observed(task.task_id)
            )

        service = MediaOrganizerService(
            strategy,
            StorageScanner(storages, logger=self._logger),
            storages,
            {item.library_id: item for item in getattr(self._configuration, "media_libraries", ())},
            self._configuration.strategy.recognition_type_policies,
            self._history_factory(self._configuration.history_path),
            executor=OrganizerExecutor(self._logger),
            source_display_roots=dict(getattr(self._configuration, "resource_display_roots", ())),
            logger=self._logger,
            task_coordinator=coordinator,
            task_id=task.task_id,
            retry_policy=self._configuration.workflow_retry_policy,
            retry_cancellation_check=workflow_stop,
            secret_free_errors=True,
            persist_failure_explanations=True,
            enforce_source_ownership=True,
            # RO-6: a legacy interval/Cron occurrence is the same automatic
            # entrance as a managed due occurrence and excludes per file whose
            # same-version latest formal organizing outcome is failed/partial.
            exclude_failed_history=True,
        )
        summary = service.process_all_libraries(
            self._configuration.resource_libraries,
            execute=True,
            limit=task.item_limit,
            cancellation_check=workflow_stop,
            require_readable_scope=True,
        )
        if cancellation_check():
            raise AutomationCancelled(task.task_id)
        coordinator.finish(task.task_id, summary)
        return task.task_id

    def run_direct_organize(
        self,
        task,
        scheduling,
        claim,
        *,
        cancellation_check: Callable[[], bool],
        clock=None,
        heartbeat: Callable[[], bool] | None = None,
    ) -> str:
        """Advance one already-admitted remote-ticket or direct CLI organize Task.

        This is the same production ``MediaOrganizerService``/
        ``OrganizerExecutor`` pipeline and claim-fenced publication coordinator
        a definition occurrence uses.  The Task's own admitted scope decides the
        shape: no scope runs every configured ResourceLibrary, a directory scope
        runs its containing ResourceLibrary and a file scope runs that exact
        source — the same semantics the direct CLI path always had, now under
        the shared kernel admission, claim fence and results.
        """

        if getattr(claim, "task_id", None) != getattr(task, "task_id", None):
            raise ValueError("direct organize Task claim identity does not match")
        if not task.execute_authorized:
            raise RuntimeError("direct organize Task lacks persisted execute authorization")
        if self._provider_factory is None or self._strategy_factory is None:
            raise RuntimeError("direct organize analysis factories are unavailable")
        if self._history_factory is None:
            raise RuntimeError("direct organize history factory is unavailable")
        storages = self._storage_factory(external={})
        if heartbeat is not None:
            storages = {key: _HeartbeatStorage(value, heartbeat) for key, value in storages.items()}
        provider_ids = tuple(
            dict.fromkeys(
                policy.provider_id
                for policy in getattr(self._configuration.strategy, "metadata_policies", ())
                if getattr(policy, "enabled", True) and getattr(policy, "provider_id", None)
            )
        ) or ("tmdb",)
        providers = self._provider_factory(provider_ids)
        if heartbeat is not None:
            providers = _HeartbeatProviderRegistry(providers, heartbeat)
        strategy = self._strategy_factory(
            self._configuration.strategy,
            providers,
            storages=storages,
        )
        coordinator = KernelTaskCoordinator(
            self._repository,
            self._repository,
            scheduling,
            claim,
            clock=clock,
            heartbeat=heartbeat,
        )

        def workflow_stop() -> bool:
            return bool(
                cancellation_check()
                or coordinator.pause_requested(task.task_id)
                or coordinator.cancellation_observed(task.task_id)
            )

        service = MediaOrganizerService(
            strategy,
            StorageScanner(storages, logger=self._logger),
            storages,
            {item.library_id: item for item in getattr(self._configuration, "media_libraries", ())},
            self._configuration.strategy.recognition_type_policies,
            self._history_factory(self._configuration.history_path),
            executor=OrganizerExecutor(self._logger),
            source_display_roots=dict(getattr(self._configuration, "resource_display_roots", ())),
            logger=self._logger,
            task_coordinator=coordinator,
            task_id=task.task_id,
            retry_policy=self._configuration.workflow_retry_policy,
            retry_cancellation_check=workflow_stop,
            secret_free_errors=True,
            persist_failure_explanations=True,
            enforce_source_ownership=True,
        )
        scope = (task.scope_path or "").strip() if isinstance(task.scope_path, str) else ""
        if not scope:
            summary = service.process_all_libraries(
                self._configuration.resource_libraries,
                execute=True,
                limit=task.item_limit,
                cancellation_check=workflow_stop,
                require_readable_scope=True,
            )
        else:
            library, display_root = self._resolve_direct_scope(scope)
            from pathlib import Path

            candidate = Path(scope).resolve(strict=False)
            if candidate.is_file():
                storage_path = _storage_relative_path(library.root_path, display_root, candidate)
                item = service.process_file(
                    candidate.as_posix(),
                    resource_library=library,
                    storage_path=storage_path,
                    execute=True,
                )
                summary = MediaOrganizerBatchResult((item,))
            else:
                summary = service.process_library(
                    library,
                    execute=True,
                    limit=task.item_limit,
                    cancellation_check=workflow_stop,
                    require_readable_scope=True,
                )
        if cancellation_check():
            raise AutomationCancelled(task.task_id)
        coordinator.finish(task.task_id, summary)
        return task.task_id

    def _resolve_direct_scope(self, scope: str):
        """The pinned ResourceLibrary one direct organize scope belongs to."""

        from pathlib import Path

        candidate = Path(scope).resolve(strict=False)
        roots = []
        libraries = {
            item.library_id: item for item in getattr(self._configuration, "resource_libraries", ())
        }
        for library_id, value in dict(
            getattr(self._configuration, "resource_display_roots", ()) or ()
        ).items():
            root = Path(value).resolve(strict=False)
            if candidate == root or root in candidate.parents:
                roots.append((len(root.parts), library_id, root.as_posix()))
        if not roots:
            raise AutomationConfigurationUnavailable(
                AutomationFailureEvidence(
                    "direct_scope_unresolved",
                    "the admitted organize scope is not inside a configured ResourceLibrary",
                    "none",
                    False,
                    "inspect the admitted Task's recorded scope; no media effect was started",
                )
            )
        _, library_id, root = max(roots)
        library = libraries.get(library_id)
        if library is None:
            raise AutomationConfigurationUnavailable(
                AutomationFailureEvidence(
                    "direct_scope_unresolved",
                    "the admitted organize scope's ResourceLibrary is unavailable",
                    "none",
                    False,
                    "inspect the admitted Task's recorded scope; no media effect was started",
                )
            )
        return library, root

    def _coordinator(self, task_context, *, clock=None, heartbeat=None):
        """The publication coordinator for this run.

        A kernel ``(scheduling, claim)`` context routes every machine write
        through the live claim fence; otherwise the original generic coordinator
        keeps the legacy behavior unchanged.
        """

        if task_context and task_context[1] is not None:
            return KernelTaskCoordinator(
                self._repository,
                self._repository,
                task_context[0],
                task_context[1],
                clock=clock,
                heartbeat=heartbeat,
            )
        return PersistentTaskCoordinator(self._repository, self._repository)

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


def _effective_item_limit(item_limit: int | None, definition: AutomationTaskDefinition) -> int:
    """The admitted primary bound of this exact Task.

    A normal due occurrence keeps the saved definition ceiling.  Run once keeps
    its longstanding effective bound ``min(definition.itemLimit, 100)``; its Task
    admission already stores that exact value, so this fallback never widens it.
    """

    if item_limit is not None:
        return min(item_limit, definition.item_limit)
    return min(definition.item_limit, 100)


def _contains(parent: str, child: str) -> bool:
    return not parent or child == parent or child.startswith(parent.rstrip("/") + "/")


def _storage_relative_path(library_root: str, display_root: str, candidate) -> str:
    """The Storage-relative path of one direct organize file scope.

    The admitted scope is the operator's display path; the pipeline consumes the
    exact Storage-relative media path, exactly as the direct CLI always built it.
    """

    from pathlib import Path

    relative = candidate.relative_to(Path(display_root).resolve(strict=False)).as_posix()
    return "/".join(value.strip("/") for value in (library_root, relative) if value.strip("/"))


def _relative_scope(library_root: str, scope_root: str) -> str | None:
    base = normalize_resource_root(library_root)
    if not base:
        return scope_root or None
    if scope_root == base:
        return None
    return scope_root.removeprefix(base + "/")


def _heartbeat_call(heartbeat: Callable[[], bool]) -> None:
    """Fail closed before the next call when the Task ownership was lost."""

    try:
        kept = bool(heartbeat())
    except Exception:
        kept = False
    if not kept:
        raise AutomationClaimLost("the Task claim was lost during a long automatic call")


class _HeartbeatProviderRegistry:
    """Renew Task ownership around every real Provider boundary call."""

    def __init__(self, registry, heartbeat: Callable[[], bool]) -> None:
        self._registry = registry
        self._heartbeat = heartbeat

    def resolve(self, provider_id: str):
        return _HeartbeatProvider(self._registry.resolve(provider_id), self._heartbeat)


class _HeartbeatProvider:
    def __init__(self, value, heartbeat: Callable[[], bool]) -> None:
        self._value = value
        self._heartbeat = heartbeat

    @property
    def provider_id(self):
        return self._value.provider_id

    def __getattr__(self, name: str):
        value = getattr(self._value, name)
        if not callable(value):
            return value

        def call(*args, **kwargs):
            _heartbeat_call(self._heartbeat)
            result = value(*args, **kwargs)
            _heartbeat_call(self._heartbeat)
            return result

        return call


class _HeartbeatStorage:
    """Renew Task ownership around every real Storage adapter call."""

    def __init__(self, value, heartbeat: Callable[[], bool]) -> None:
        self._value = value
        self._heartbeat = heartbeat

    def __getattr__(self, name: str):
        value = getattr(self._value, name)
        if not callable(value):
            return value

        def call(*args, **kwargs):
            _heartbeat_call(self._heartbeat)
            result = value(*args, **kwargs)
            _heartbeat_call(self._heartbeat)
            return result

        return call


__all__ = ["DefinitionScopedExecutionService"]
