from __future__ import annotations

import posixpath
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from mediaflow.application.attachments import AttachmentDiscovery, AttachmentPlanner
from mediaflow.application.conflict_resolution import ConflictResolver
from mediaflow.application.duplicates import apply_hash_duplicate_detection
from mediaflow.application.evidence_capture import build_pipeline_evidence
from mediaflow.application.failure_explanation import (
    classify_failure,
    failure_explanation,
    sanitize_execution_errors,
)
from mediaflow.application.library_pipeline import MediaLibraryResolver
from mediaflow.application.organizer import OrganizePlanner, OrganizerExecutor
from mediaflow.application.scan_filters import (
    ObservedSource,
    StabilityVerdict,
    stability_decision,
    stability_wait_seconds,
)
from mediaflow.application.strategy_test import StrategyTestResult, StrategyTestRunner
from mediaflow.application.workflow_retry import (
    RetryExhausted,
    RetryInterrupted,
    RetrySignal,
    WorkflowRetryController,
    classify_retryable_error,
)
from mediaflow.domain.classification import ClassificationStatus
from mediaflow.domain.classification_review import ClassificationSelection
from mediaflow.domain.failure import FailureExplanation
from mediaflow.domain.history import OperationHistoryRecord, OperationHistoryRepository
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.logging import Logger, LogLevel
from mediaflow.domain.media_evidence import PipelineEvidence
from mediaflow.domain.metadata import MetadataError, MetadataIdentificationStatus
from mediaflow.domain.metadata_correction import MetadataCorrectionSelection
from mediaflow.domain.metadata_review import MetadataSelection
from mediaflow.domain.organizer import (
    ConflictStrategy,
    ConflictType,
    ExecutionResult,
    ExecutionStatus,
    OrganizePlan,
    PlanOperation,
    PlanStatus,
)
from mediaflow.domain.recognition import RecognitionStatus, RecognitionTypePolicy
from mediaflow.domain.recognition_review import RecognitionSelection
from mediaflow.domain.scanner import (
    CancellationToken,
    DiscoveredFile,
    FileChange,
    FileScanStatus,
    ScanError,
    Scanner,
)
from mediaflow.domain.source_evidence import OccurrenceState, occurrence_id_for, source_fingerprint
from mediaflow.domain.storage import (
    Storage,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
)
from mediaflow.domain.workflow_retry import RetryEvent, WorkflowRetryPolicy

if TYPE_CHECKING:
    from mediaflow.application.task_runtime import PersistentTaskCoordinator
    from mediaflow.domain.task_persistence import ConflictConfirmation, PersistentTaskItem


@dataclass(frozen=True)
class MediaOrganizerItemResult:
    source: str
    strategy: StrategyTestResult | None = None
    plan: OrganizePlan | None = None
    execution: ExecutionResult | None = None
    error: str | None = None
    retry_events: tuple[RetryEvent, ...] = ()
    evidence: PipelineEvidence | None = None
    failure: FailureExplanation | None = None


@dataclass(frozen=True)
class MediaOrganizerBatchResult:
    items: tuple[MediaOrganizerItemResult, ...]
    scan_errors: tuple[ScanError, ...] = ()
    bound_reached: bool = False

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def matched(self) -> int:
        return sum(
            item.strategy is not None
            and item.strategy.metadata is not None
            and item.strategy.metadata.identity is not None
            for item in self.items
        )

    @property
    def conflicts(self) -> int:
        return sum(bool(item.plan and item.plan.conflicts) for item in self.items)

    @property
    def moved(self) -> int:
        return sum(
            item.execution is not None
            and item.execution.status is ExecutionStatus.SUCCESS
            and item.execution.operation.value == "MOVE"
            for item in self.items
        )

    @property
    def failed(self) -> int:
        return len(self.scan_errors) + sum(
            bool(
                item.error
                or (
                    item.execution
                    and item.execution.status in {ExecutionStatus.FAILED, ExecutionStatus.PARTIAL}
                )
            )
            for item in self.items
        )


ProgressReporter = Callable[[int, int | None, str], None]
CancellationCheck = Callable[[], bool]

#: A required stable-size interval is proven by *real* elapsed time.  A
#: synchronous command only waits when the remaining interval is short enough to
#: finish promptly; a longer configured interval is recorded as an honest waiting
#: item (with a retry next action) rather than blocking the command.
_MAX_STABILITY_WAIT_SECONDS = 60.0


@dataclass(frozen=True)
class _ObservedEntry:
    """The bounded entry facts a stability wait needs from one observation."""

    modified_at: datetime


class MediaOrganizerService:
    """Thin orchestration over production stages; business decisions stay in their engines."""

    def __init__(
        self,
        strategy: StrategyTestRunner,
        scanner: Scanner,
        storages: dict[str, Storage],
        media_libraries: dict[str, MediaLibrary],
        type_policies: tuple[RecognitionTypePolicy, ...],
        history: OperationHistoryRepository,
        executor: OrganizerExecutor | None = None,
        source_display_roots: dict[str, str] | None = None,
        logger: Logger | None = None,
        task_coordinator: PersistentTaskCoordinator | None = None,
        task_id: str | None = None,
        previous_observations: dict[str, ObservedSource] | None = None,
        conflict_decisions: dict[tuple[str, str], ConflictConfirmation] | None = None,
        metadata_selections: dict[tuple[str, str], MetadataSelection] | None = None,
        classification_selections: dict[tuple[str, str], ClassificationSelection] | None = None,
        retry_policy: WorkflowRetryPolicy = WorkflowRetryPolicy(),
        retry_controller: WorkflowRetryController | None = None,
        retry_cancellation_check: CancellationCheck | None = None,
        recognition_selections: dict[tuple[str, str], RecognitionSelection] | None = None,
        metadata_corrections: dict[tuple[str, str], MetadataCorrectionSelection] | None = None,
        secret_free_errors: bool = False,
        persist_failure_explanations: bool = False,
        mutation_authority: Callable[[OrganizePlan, str], object] | None = None,
        analysis_only: bool = False,
    ) -> None:
        self._strategy = strategy
        self._scanner = scanner
        self._storages = storages
        self._media_libraries = media_libraries
        self._media_library_resolver = MediaLibraryResolver(
            tuple(media_libraries.values()), storages
        )
        self._type_policies = {item.policy_id: item for item in type_policies}
        self._history = history
        self._executor = executor or OrganizerExecutor()
        self._source_display_roots = source_display_roots or {}
        self._logger = logger
        self._task_coordinator = task_coordinator
        self._task_id = task_id
        # The caller's own durable observations of this exact scope.  Only used
        # to prove a configured stable-size interval across two real
        # observations; it is never a substitute for a first observation.
        self._previous_observations = dict(previous_observations or {})
        self._conflict_decisions = conflict_decisions or {}
        self._metadata_selections = metadata_selections or {}
        self._classification_selections = classification_selections or {}
        self._retry_policy = retry_policy
        self._retry_controller = retry_controller or WorkflowRetryController()
        self._retry_cancellation_check = retry_cancellation_check
        self._recognition_selections = recognition_selections or {}
        self._metadata_corrections = metadata_corrections or {}
        self._secret_free_errors = secret_free_errors
        self._persist_failure_explanations = persist_failure_explanations
        self._mutation_authority = mutation_authority
        self._analysis_only = bool(analysis_only)

    def process_file(
        self,
        source: str,
        *,
        resource_library: ResourceLibrary,
        storage_path: str,
        execute: bool = False,
        source_occurrence_id: str | None = None,
        source_fingerprint: str | None = None,
        source_fingerprint_state: str = "unverified",
        source_observed_at: datetime | None = None,
        resolve_source_evidence: bool = True,
    ) -> MediaOrganizerItemResult:
        tracked_item: PersistentTaskItem | None = None
        try:
            # A first explicit selection establishes its own exact source
            # evidence from one live Storage stat before any Provider call, so
            # the durable TaskItem/Result can later prove the same occurrence.
            # A continuation/retry passes ``resolve_source_evidence=False`` and
            # may only compare the evidence the original work already saved: a
            # replaced file must never be re-bound to the old review.
            if (
                resolve_source_evidence
                and source_occurrence_id is None
                and source_fingerprint is None
            ):
                evidence, pending, observed_at = self._observe_direct_source(
                    resource_library, storage_path
                )
                if pending and evidence is not None:
                    # The source is still inside its configured stable-size
                    # interval after a real wait, so this explicit selection is
                    # recorded as an honest waiting item with zero Provider
                    # calls and zero mutation instead of a first-stat shortcut.
                    return self._direct_waiting_item(
                        source, resource_library, storage_path, *evidence, observed_at
                    )
                if evidence is not None:
                    source_occurrence_id, source_fingerprint, source_fingerprint_state = evidence
                    source_observed_at = observed_at
            elif not resolve_source_evidence:
                # A continuation/retry may only consume the evidence the original
                # work already saved.  Prove the live source still matches it
                # before any Provider analysis, so a replacement at the same path
                # is refused with zero Provider calls and zero mutation.
                refusal = self._persisted_source_refusal(
                    resource_library,
                    storage_path,
                    source_occurrence_id,
                    source_fingerprint,
                    source_fingerprint_state,
                )
                if refusal is not None:
                    return self._refused_source_item(
                        source,
                        resource_library,
                        storage_path,
                        source_occurrence_id,
                        source_fingerprint,
                        source_fingerprint_state,
                        source_observed_at,
                        refusal,
                    )
                # A trusted, unchanged fingerprint proves *identity*, never
                # elapsed stability.  The configured stability policy under the
                # work's original pin must be satisfied against a live
                # re-observation before any Provider analysis or mutation, so an
                # immediate Retry/Continue only continues waiting.
                deadline = self._stability_deadline_refusal(
                    resource_library, storage_path, source_observed_at
                )
                if deadline is not None:
                    return self._continuation_waiting_item(
                        source,
                        resource_library,
                        storage_path,
                        source_occurrence_id,
                        source_fingerprint,
                        source_fingerprint_state,
                        deadline,
                    )
            if self._task_coordinator and self._task_id:
                tracked_item = self._task_coordinator.begin_item(
                    self._task_id,
                    resource_library.storage_id,
                    resource_library.library_id,
                    storage_path,
                    source,
                    source_occurrence_id=source_occurrence_id,
                    source_fingerprint=source_fingerprint,
                    source_fingerprint_state=source_fingerprint_state,
                    source_observed_at=source_observed_at,
                )
            retry_outcome = self._retry_controller.execute(
                lambda: self._run_read_only_strategy(
                    source, resource_library=resource_library, storage_path=storage_path
                ),
                self._retry_policy,
                stage="strategy",
                cancellation_check=self._retry_cancellation_check,
                on_retry=self._log_retry,
            )
            strategy = retry_outcome.value
            retry_events = retry_outcome.events
            self._log(
                LogLevel.DEBUG,
                "media parsed and recognized",
                source=source,
                title=strategy.parsed.title_candidate,
                recognition_type=strategy.recognition.recognition_type_id,
            )
            if strategy.recognition.status is RecognitionStatus.UNRECOGNIZED:
                if self._task_coordinator and tracked_item:
                    item = MediaOrganizerItemResult(source, strategy, retry_events=retry_events)
                    item = self._attach_evidence(item, tracked_item)
                    self._record(item, tracked_item, persist_evidence=False)
                    self._task_coordinator.wait_for_recognition(
                        tracked_item,
                        strategy.recognition,
                        tuple(policy.recognition_type for policy in self._type_policies.values()),
                        evidence=item.evidence,
                    )
                    return item
                return self._failed(
                    source, strategy, "recognition type is unavailable", tracked_item, retry_events
                )
            if not strategy.metadata or not strategy.metadata.identity:
                if (
                    strategy.metadata
                    and strategy.metadata.status
                    in {
                        MetadataIdentificationStatus.NEED_CONFIRM,
                        MetadataIdentificationStatus.AMBIGUOUS,
                    }
                    and self._task_coordinator
                    and tracked_item
                ):
                    item = MediaOrganizerItemResult(source, strategy, retry_events=retry_events)
                    item = self._attach_evidence(item, tracked_item)
                    self._record(item, tracked_item, persist_evidence=False)
                    self._task_coordinator.wait_for_metadata(
                        tracked_item,
                        strategy.metadata,
                        strategy.policy.metadata_policy_id,
                        evidence=item.evidence,
                    )
                    return item
                if (
                    strategy.metadata
                    and strategy.metadata.status is MetadataIdentificationStatus.NOT_FOUND
                    and strategy.metadata_policy
                    and self._task_coordinator
                    and tracked_item
                ):
                    item = MediaOrganizerItemResult(source, strategy, retry_events=retry_events)
                    item = self._attach_evidence(item, tracked_item)
                    self._record(item, tracked_item, persist_evidence=False)
                    self._task_coordinator.wait_for_metadata_correction(
                        tracked_item,
                        strategy.metadata,
                        strategy.metadata_policy,
                        strategy.parsed,
                        evidence=item.evidence,
                    )
                    return item
                return self._failed(
                    source,
                    strategy,
                    "metadata identity is unavailable",
                    tracked_item,
                    retry_events,
                )
            if not strategy.naming:
                return self._failed(
                    source,
                    strategy,
                    strategy.naming_error or "naming failed",
                    tracked_item,
                    retry_events,
                )
            if not strategy.classification or not strategy.classification.media_library_id:
                if (
                    strategy.classification
                    and strategy.classification.status is ClassificationStatus.UNCLASSIFIED
                    and self._task_coordinator
                    and tracked_item
                ):
                    item = MediaOrganizerItemResult(source, strategy, retry_events=retry_events)
                    item = self._attach_evidence(item, tracked_item)
                    self._record(item, tracked_item, persist_evidence=False)
                    self._task_coordinator.wait_for_classification(
                        tracked_item,
                        strategy.classification,
                        self._strategy.classification_policy(
                            strategy.policy.classification_policy_id
                        ),
                        strategy.metadata.identity,
                        evidence=item.evidence,
                    )
                    return item
                return self._failed(
                    source,
                    strategy,
                    strategy.classification_error or "classification failed",
                    tracked_item,
                    retry_events,
                )
            resolved_library = self._media_library_resolver.resolve(strategy.classification)
            media_library = resolved_library.media_library
            self._log(
                LogLevel.DEBUG,
                "metadata naming and classification completed",
                source=source,
                provider_id=strategy.metadata.identity.provider_id,
                naming=strategy.naming.filename,
                classification=strategy.classification.relative_path,
            )
            type_policy = self._type_policies[strategy.policy.type_policy_id]
            plan = OrganizePlanner().plan(
                source_storage_id=resource_library.storage_id,
                source=source,
                source_storage_path=storage_path,
                source_library_root=resource_library.root_path,
                recognition=strategy.recognition,
                type_policy=type_policy,
                media_library=media_library,
                naming=strategy.naming,
                classification=strategy.classification,
                media_identity=strategy.metadata.identity,
                target_storage=resolved_library.storage,
            )
            hash_policy = type_policy.organize_policy.duplicate_detection
            plan = apply_hash_duplicate_detection(
                plan,
                self._storages[resource_library.storage_id],
                resolved_library.storage,
                hash_policy,
            )
            attachment_policy = type_policy.organize_policy.attachments
            if attachment_policy.enabled and plan.source_location is not None:
                file_set = AttachmentDiscovery().discover(
                    self._storages[resource_library.storage_id],
                    plan.source_location,
                    attachment_policy,
                )
                plan = AttachmentPlanner().plan(plan, file_set, resolved_library.storage)
            resolver = ConflictResolver()
            decision = self._conflict_decisions.get((resource_library.storage_id, storage_path))
            replacement = None
            if decision and decision.plan_id == plan.plan_id and decision.selected_strategy:
                selected = ConflictStrategy(decision.selected_strategy)
                if selected is ConflictStrategy.SKIP:
                    replacement = replace(
                        plan, operation=PlanOperation.SKIP, status=PlanStatus.NOOP, conflicts=()
                    )
                elif selected is ConflictStrategy.RENAME:
                    replacement = resolver.rename(plan, resolved_library.storage)
                elif selected is ConflictStrategy.OVERWRITE:
                    replacement = resolver.overwrite(
                        plan,
                        type_policy.organize_policy,
                        confirmed=decision.overwrite_authorized,
                    )
            else:
                replacement = resolver.apply_configured(
                    plan, type_policy.organize_policy, resolved_library.storage
                )
            if replacement is None:
                if self._persist_failure_explanations and any(
                    conflict.type is ConflictType.UNKNOWN for conflict in plan.conflicts
                ):
                    return self._failed(
                        source,
                        strategy,
                        "Storage state could not be verified",
                        tracked_item,
                        retry_events,
                        plan=plan,
                        stage="storage",
                    )
                if plan.status is PlanStatus.INVALID or any(
                    conflict.type is ConflictType.INVALID_DESTINATION for conflict in plan.conflicts
                ):
                    return self._failed(
                        source,
                        strategy,
                        "invalid destination",
                        tracked_item,
                        retry_events,
                        plan=plan,
                    )
                item = MediaOrganizerItemResult(source, strategy, plan, retry_events=retry_events)
                item = self._attach_evidence(item, tracked_item)
                if self._task_coordinator and tracked_item:
                    if self._analysis_only:
                        # An analysis-only Preview must keep the organize-plan
                        # conflict as an inspectable durable finding.  It never
                        # creates a PENDING ConflictConfirmation, a WAITING_CONFIRM
                        # TaskItem or a real Conflicts backlog item; the operator
                        # must use the explicit real Organize journey for that.
                        return self._complete(item, tracked_item, analysis_only=True)
                    self._record(item, tracked_item, persist_evidence=False)
                    self._task_coordinator.wait_for_confirmation(
                        tracked_item,
                        plan,
                        type_policy.organize_policy,
                        evidence=item.evidence,
                    )
                else:
                    self._record(item, tracked_item, persist_evidence=False)
                return item
            plan = replacement
            execution = self._executor.execute(
                plan,
                self._storages,
                execute=execute,
                mutation_authority=self._mutation_authority,
                resolved_destination=(
                    f"{plan.destination_location.storage_id}:{plan.destination_location.path}"
                    if plan.destination_location
                    else plan.target
                ),
            )
            failure = None
            if execution.errors or execution.status in {
                ExecutionStatus.FAILED,
                ExecutionStatus.PARTIAL,
            }:
                failure = classify_failure(execution=execution)
                if self._secret_free_errors:
                    execution = sanitize_execution_errors(execution, failure)
            self._log(
                LogLevel.INFO,
                "organize plan processed",
                source=source,
                plan_id=plan.plan_id,
                destination=plan.target,
                execution_status=execution.status.value,
            )
            item = MediaOrganizerItemResult(
                source,
                strategy,
                plan,
                execution,
                error=(failure.message if failure and self._persist_failure_explanations else None),
                retry_events=retry_events,
                failure=failure if self._persist_failure_explanations else None,
            )
            return self._complete(item, tracked_item)
        except RetryInterrupted:
            return MediaOrganizerItemResult(source, error="workflow retry interrupted")
        except RetryExhausted as error:
            return self._failed(source, None, error, tracked_item, error.events)
        except Exception as error:
            from mediaflow.application.task_runtime import (
                TaskClaimLost,
                TaskLockError,
                TaskPauseRequested,
            )

            if tracked_item is None and not isinstance(
                error, (TaskLockError, TaskPauseRequested, TaskClaimLost)
            ):
                # A failure raised before any TaskItem was begun (for example a
                # pre-Provider source/Storage boundary) must still publish its
                # own durable failed item.  Otherwise the aggregate would read
                # an empty item set and falsely report Completed/0.  Task
                # control-flow exceptions already published their own refusal
                # inside ``begin_item`` and keep their existing handling.
                return self._refused_source_item(
                    source,
                    resource_library,
                    storage_path,
                    source_occurrence_id,
                    source_fingerprint,
                    source_fingerprint_state,
                    source_observed_at,
                    classify_failure(error),
                )
            return self._failed(source, None, error, tracked_item)

    def _persisted_source_refusal(
        self,
        resource_library: ResourceLibrary,
        storage_path: str,
        occurrence: str | None,
        fingerprint: str | None,
        state: str,
    ) -> FailureExplanation | None:
        """Prove a continued/retried source still matches its saved evidence.

        Returns a bounded refusal when the live source cannot be proven, or
        ``None`` when it matches.  Missing, half-written, legacy and unverified
        evidence is refused; the live current stat is never promoted into a
        fabricated original identity.  The categories are the closed, shared
        failure set so the persisted per-item Result explains whether the source
        changed, disappeared, was unverifiable, or the Storage connection failed.
        """

        if not occurrence or not fingerprint or state != OccurrenceState.VERIFIED.value:
            return failure_explanation("source_unverified", durable="failed", side_effects="none")
        storage = self._storages.get(resource_library.storage_id)
        if storage is None:
            return failure_explanation(
                "storage_failure", durable="failed", side_effects="none", retry_safe=True
            )
        try:
            entry = storage.stat(storage_path)
        except StorageError as error:
            if error.code is StorageErrorCode.NOT_FOUND:
                return failure_explanation("source_missing", durable="failed", side_effects="none")
            return failure_explanation(
                "storage_failure", durable="failed", side_effects="none", retry_safe=True
            )
        except (OSError, ValueError, KeyError):
            return failure_explanation(
                "storage_failure", durable="failed", side_effects="none", retry_safe=True
            )
        if entry is None or entry.entry_type is not StorageEntryType.FILE:
            return failure_explanation("source_missing", durable="failed", side_effects="none")
        observed = source_fingerprint(
            resource_library.storage_id, resource_library.library_id, entry
        )
        live_occurrence = occurrence_id_for(
            resource_library.storage_id, resource_library.library_id, entry.path, observed.value
        )
        if (
            observed.state is not OccurrenceState.VERIFIED
            or observed.value != fingerprint
            or live_occurrence != occurrence
        ):
            return failure_explanation("source_changed", durable="failed", side_effects="none")
        return None

    def _stability_deadline_refusal(
        self,
        resource_library: ResourceLibrary,
        storage_path: str,
        source_observed_at: datetime | None,
    ) -> datetime | None:
        """The observation instant when a continued source is still waiting.

        A trusted, unchanged fingerprint proves *identity*; it never proves an
        elapsed stable-size interval.  This applies the configured stability
        policy under the work's original pin against a live re-observation of
        the exact source, using the work's own durable first-observation
        instant.  Returns the (possibly new) observation start when the interval
        is not yet satisfied, or ``None`` when the source is stable.  Missing
        observation evidence restarts the interval from now instead of being
        treated as satisfied.
        """

        policy = resource_library.stability_policy
        if policy.stable_size_duration_seconds == 0 and (
            policy.minimum_age_seconds == 0 and policy.modified_threshold_seconds == 0
        ):
            return None
        storage = self._storages.get(resource_library.storage_id)
        if storage is None:
            # A missing Storage is a real refusal elsewhere; treat it as still
            # waiting rather than silently analyzing.
            return source_observed_at or datetime.now(UTC)
        entry = self._stat_entry(storage, storage_path)
        if entry is None or entry.entry_type is not StorageEntryType.FILE:
            return source_observed_at or datetime.now(UTC)
        now = datetime.now(UTC)
        start = source_observed_at or now
        unchanged = source_observed_at is not None
        verdict = stability_decision(
            policy,
            entry,
            now=now,
            unchanged_previous=unchanged,
            observed_since=start,
        )
        if verdict is StabilityVerdict.STABLE:
            return None
        return start

    def _observe_direct_source(
        self, resource_library: ResourceLibrary, storage_path: str
    ) -> tuple[tuple[str, str, str] | None, bool, datetime | None]:
        """Observe one directly selected source, proving the stable interval.

        Returns ``(evidence, pending, observed_at)``.  ``pending`` is ``True``
        only when the source is still inside a configured stable-size interval
        after a real elapsed wait and a second live observation; the caller then
        records an honest waiting item whose durable ``observed_at`` lets a
        later retry/continuation prove the interval instead of a first-stat
        shortcut.  A configured ``stableSizeDurationSeconds`` of 0 keeps the
        historical immediate behavior.
        """

        storage = self._storages.get(resource_library.storage_id)
        if storage is None:
            return None, False, None
        entry = self._stat_entry(storage, storage_path)
        if entry is None or entry.entry_type is not StorageEntryType.FILE:
            return None, False, None
        observed = source_fingerprint(
            resource_library.storage_id, resource_library.library_id, entry
        )
        if observed.state is not OccurrenceState.VERIFIED or observed.value is None:
            return None, False, None
        occurrence = occurrence_id_for(
            resource_library.storage_id, resource_library.library_id, entry.path, observed.value
        )
        policy = resource_library.stability_policy
        first = datetime.now(UTC)
        verdict = stability_decision(
            policy, entry, now=first, unchanged_previous=False, observed_since=None
        )
        if verdict is StabilityVerdict.STABLE:
            return (occurrence, observed.value, observed.state.value), False, first
        remaining = stability_wait_seconds(
            resource_library, entry, now=first, unchanged_previous=False, observed_since=None
        )
        if remaining <= 0 or remaining > _MAX_STABILITY_WAIT_SECONDS:
            # A long configured interval is not blocked synchronously; the
            # caller records an honest waiting item whose durable observation
            # start lets a later retry prove the interval.
            return (occurrence, observed.value, observed.state.value), True, first
        time.sleep(remaining + 0.05)
        second = self._stat_entry(storage, storage_path)
        if second is None or second.entry_type is not StorageEntryType.FILE:
            return (occurrence, observed.value, observed.state.value), True, first
        observed_second = source_fingerprint(
            resource_library.storage_id, resource_library.library_id, second
        )
        unchanged = (
            second.size == entry.size
            and second.modified_at == entry.modified_at
            and observed_second.value == observed.value
        )
        verdict_second = stability_decision(
            policy,
            second,
            now=datetime.now(UTC),
            unchanged_previous=unchanged,
            observed_since=first,
        )
        if verdict_second is StabilityVerdict.STABLE and observed_second.value is not None:
            occurrence_second = occurrence_id_for(
                resource_library.storage_id,
                resource_library.library_id,
                second.path,
                observed_second.value,
            )
            return (
                (occurrence_second, observed_second.value, observed_second.state.value),
                False,
                first,
            )
        # The source changed during the wait, so the interval resets from the
        # second observation; a later retry must prove the interval from there.
        return (occurrence, observed.value, observed.state.value), True, datetime.now(UTC)

    @staticmethod
    def _stat_entry(storage: Storage, storage_path: str):
        try:
            return storage.stat(storage_path)
        except (StorageError, OSError, ValueError, KeyError):
            return None

    def _direct_waiting_item(
        self,
        source: str,
        resource_library: ResourceLibrary,
        storage_path: str,
        occurrence: str | None,
        fingerprint: str | None,
        state: str,
        observed_at: datetime | None,
    ) -> MediaOrganizerItemResult:
        """Record one still-waiting direct selection without analysis or mutation."""

        tracked: PersistentTaskItem | None = None
        if self._task_coordinator and self._task_id:
            tracked = self._task_coordinator.begin_item(
                self._task_id,
                resource_library.storage_id,
                resource_library.library_id,
                storage_path,
                source,
                source_occurrence_id=occurrence,
                source_fingerprint=fingerprint,
                source_fingerprint_state=state,
                source_observed_at=observed_at,
            )
        failure = classify_failure(stage="scanning")
        return self._complete(
            MediaOrganizerItemResult(source, error=failure.message, failure=failure), tracked
        )

    def _refused_source_item(
        self,
        source: str,
        resource_library: ResourceLibrary,
        storage_path: str,
        occurrence: str | None,
        fingerprint: str | None,
        state: str,
        observed_at: datetime | None,
        failure: FailureExplanation,
    ) -> MediaOrganizerItemResult:
        """Publish one rejected continuation source as this attempt's item/Result.

        The refusal happens before any Provider call or mutation, but it is still
        an admitted attempt and must be recorded as its own durable TaskItem and
        Result.  The original occurrence/fingerprint/trust state and observation
        instant are carried forward unchanged; the current live stat is never
        promoted into a new identity.  This keeps a reopened Task truthful (a
        failed item with a bounded reason) instead of a false Completed/0 run.
        """

        tracked: PersistentTaskItem | None = None
        if self._task_coordinator and self._task_id:
            tracked = self._task_coordinator.begin_item(
                self._task_id,
                resource_library.storage_id,
                resource_library.library_id,
                storage_path,
                source,
                source_occurrence_id=occurrence,
                source_fingerprint=fingerprint,
                source_fingerprint_state=state,
                source_observed_at=observed_at,
            )
        return self._failed(source, None, failure, tracked, ())

    def _continuation_waiting_item(
        self,
        source: str,
        resource_library: ResourceLibrary,
        storage_path: str,
        occurrence: str | None,
        fingerprint: str | None,
        state: str,
        observed_at: datetime | None,
    ) -> MediaOrganizerItemResult:
        """Record one continued source still inside its stable-size interval.

        A retry/continue that cannot yet prove the configured interval keeps
        zero Provider calls and zero mutation; it only continues waiting, and
        the durable observation start is preserved so a later real observation
        can prove the interval.
        """

        tracked: PersistentTaskItem | None = None
        if self._task_coordinator and self._task_id:
            tracked = self._task_coordinator.begin_item(
                self._task_id,
                resource_library.storage_id,
                resource_library.library_id,
                storage_path,
                source,
                source_occurrence_id=occurrence,
                source_fingerprint=fingerprint,
                source_fingerprint_state=state,
                source_observed_at=observed_at,
            )
        failure = classify_failure(stage="scanning")
        return self._complete(
            MediaOrganizerItemResult(source, error=failure.message, failure=failure), tracked
        )

    def _run_read_only_strategy(
        self, source: str, *, resource_library: ResourceLibrary, storage_path: str
    ) -> StrategyTestResult:
        strategy = self._strategy.run_path(
            source,
            live_metadata=True,
            show_naming=True,
            show_classification=True,
            resource_library_id=resource_library.library_id,
            storage_id=resource_library.storage_id,
            metadata_selection=self._metadata_selections.get(
                (resource_library.storage_id, storage_path)
            ),
            metadata_correction=self._metadata_corrections.get(
                (resource_library.storage_id, storage_path)
            ),
            classification_selection=self._classification_selections.get(
                (resource_library.storage_id, storage_path)
            ),
            recognition_selection=self._recognition_selections.get(
                (resource_library.storage_id, storage_path)
            ),
            storage_path=storage_path,
        )
        if (
            strategy.metadata
            and strategy.metadata.status is MetadataIdentificationStatus.PROVIDER_ERROR
            and strategy.metadata.error
        ):
            category = classify_retryable_error(strategy.metadata.error)
            if category and self._retry_policy.enabled:
                raise RetrySignal(category)
        return strategy

    def _log_retry(self, event: RetryEvent) -> None:
        self._log(
            LogLevel.WARN,
            "read-only workflow retry scheduled",
            stage=event.stage,
            attempt=event.attempt,
            category=event.category.value,
            delay_seconds=event.delay_seconds,
        )

    def process_library(
        self,
        library: ResourceLibrary,
        *,
        execute: bool = False,
        limit: int | None = None,
        progress: ProgressReporter | None = None,
        cancellation_check: CancellationCheck | None = None,
        skip_sources: set[tuple[str, str]] | None = None,
        source_display_root: str | None = None,
    ) -> MediaOrganizerBatchResult:
        items: list[MediaOrganizerItemResult] = []
        selected_count = 0
        bound_reached = False
        cancellation = CancellationToken()
        display_root = source_display_root or self._source_display_roots.get(
            library.library_id, library.root_path
        )
        self._log(LogLevel.INFO, "library scan started", library_id=library.library_id)
        # One bounded discovery pass of this exact scope.  The discovered
        # evidence (occurrence/fingerprint and the real stable interval) is the
        # work's own durable observation; a required stable-size interval that
        # is not yet proven is waited out in real time and then re-observed
        # instead of being reported as a completed zero-item run.
        ready_files, waiting_files, scan_errors = self._discover_ready_files(
            library,
            cancellation=cancellation,
            cancellation_check=cancellation_check,
        )
        if waiting_files and not ready_files:
            # Record this pass's real observation time *before* waiting, so the
            # later re-observation measures a genuine elapsed interval instead of
            # the instant the wait ended.
            self._previous_observations = {
                **self._previous_observations,
                **self._observation_map(library, ready_files + waiting_files),
            }
            remaining = min(self._wait_seconds(library, file) for file in waiting_files)
            if 0 < remaining <= _MAX_STABILITY_WAIT_SECONDS and not (
                cancellation_check and cancellation_check()
            ):
                # A real elapsed interval.  A longer configured interval is not
                # blocked synchronously: the candidate stays an honest waiting
                # item with a retry next action.
                time.sleep(remaining + 0.05)
                # The later observation consumes this pass's durable evidence, so
                # a stable interval is proven by real elapsed time, never by a
                # first-stat shortcut.
                ready_files, waiting_files, scan_errors = self._discover_ready_files(
                    library,
                    cancellation=cancellation,
                    cancellation_check=cancellation_check,
                )
        # Keep this pass's live observations for the work's own continuation and
        # for any still-waiting candidate the caller re-runs later.
        self._previous_observations = {
            **self._previous_observations,
            **self._observation_map(library, ready_files + waiting_files),
        }

        def handle(file: DiscoveredFile) -> None:
            nonlocal selected_count, bound_reached
            if cancellation_check and cancellation_check():
                cancellation.cancel()
                return
            if file.status is not FileScanStatus.READY:
                if file.status is FileScanStatus.UNSTABLE:
                    items.append(self._waiting_item(library, file, display_root))
                return
            if (library.storage_id, file.path) in (skip_sources or set()):
                return
            source = self._display_source(file.path, library, display_root)
            selected_count += 1
            items.append(
                self.process_file(
                    source,
                    resource_library=library,
                    storage_path=file.path,
                    execute=execute,
                    source_occurrence_id=file.occurrence_id,
                    source_fingerprint=file.fingerprint,
                    source_fingerprint_state=file.fingerprint_state,
                    # The discovery walk already proved this exact source stable
                    # (or this is the configured zero-duration path), so the
                    # durable observation start is the interval it proved.
                    source_observed_at=file.stable_since or file.discovered_at,
                    resolve_source_evidence=False,
                )
            )
            if progress:
                progress(len(items), limit, source)
            if limit is not None and selected_count >= limit:
                bound_reached = True
                cancellation.cancel()

        scan_errors: tuple[ScanError, ...] = scan_errors
        # The discovery pass already consumed this exact scope; process the same
        # observation it just proved stable.
        for file in ready_files + waiting_files:
            handle(file)
            if cancellation.is_cancelled:
                break
        self._log(
            LogLevel.INFO,
            "library scan completed",
            library_id=library.library_id,
            files=len(items),
            errors=len(scan_errors),
        )
        return MediaOrganizerBatchResult(tuple(items), scan_errors, bound_reached)

    def _discover_ready_files(
        self,
        library: ResourceLibrary,
        *,
        cancellation: CancellationToken,
        cancellation_check: CancellationCheck | None,
    ) -> tuple[list[DiscoveredFile], list[DiscoveredFile], tuple[ScanError, ...]]:
        """One bounded, metadata-only walk split into ready and waiting files."""

        ready: list[DiscoveredFile] = []
        waiting: list[DiscoveredFile] = []

        def collect(file: DiscoveredFile) -> None:
            if cancellation_check and cancellation_check():
                cancellation.cancel()
                return
            if file.status is FileScanStatus.READY:
                ready.append(file)
            elif file.status is FileScanStatus.UNSTABLE:
                waiting.append(file)

        result = self._scanner.scan(
            library,
            cancellation=cancellation,
            on_discovered=collect,
            previous=self._previous_observations,
        )
        return ready, waiting, result.errors

    @staticmethod
    def _observation_map(
        library: ResourceLibrary, files: list[DiscoveredFile]
    ) -> dict[str, ObservedSource]:
        observed_at = datetime.now(UTC)
        values: dict[str, ObservedSource] = {}
        for file in files:
            values[file.path] = ObservedSource(
                file.path,
                file.size,
                file.modified_at,
                file.fingerprint,
                observed_at,
                file.stable_since,
            )
        return values

    @staticmethod
    def _wait_seconds(library: ResourceLibrary, file: DiscoveredFile) -> float:
        entry = _ObservedEntry(file.modified_at)
        return stability_wait_seconds(
            library,
            entry,
            now=datetime.now(UTC),
            unchanged_previous=file.change is FileChange.UNCHANGED,
            observed_since=file.stable_since,
        )

    def _waiting_item(
        self,
        library: ResourceLibrary,
        file: DiscoveredFile,
        display_root: str,
    ) -> MediaOrganizerItemResult:
        """Record one still-waiting candidate without a mutation or execution right."""

        source = self._display_source(file.path, library, display_root)
        failure = classify_failure(stage="scanning")
        tracked = None
        if self._task_coordinator and self._task_id:
            tracked = self._task_coordinator.begin_item(
                self._task_id,
                library.storage_id,
                library.library_id,
                file.path,
                source,
                source_occurrence_id=file.occurrence_id,
                source_fingerprint=file.fingerprint,
                source_fingerprint_state=file.fingerprint_state,
                # The durable instant this explicit work first observed the
                # source; a later retry measures the configured interval from
                # here instead of treating an unchanged fingerprint as stable.
                source_observed_at=file.discovered_at,
            )
        return self._complete(
            MediaOrganizerItemResult(
                source,
                error=failure.message,
                failure=failure,
            ),
            tracked,
        )

    @staticmethod
    def _display_source(path: str, library: ResourceLibrary, display_root: str) -> str:
        relative_display_path = path
        library_root = library.root_path.strip("/")
        if library_root and path.startswith(f"{library_root}/"):
            relative_display_path = path[len(library_root) + 1 :]
        return posixpath.join(display_root, relative_display_path)

    def process_all_libraries(
        self,
        libraries: tuple[ResourceLibrary, ...],
        *,
        execute: bool = False,
        limit: int | None = None,
        progress: ProgressReporter | None = None,
        cancellation_check: CancellationCheck | None = None,
        skip_sources: set[tuple[str, str]] | None = None,
    ) -> MediaOrganizerBatchResult:
        """Process all enabled configured libraries without local-path assumptions."""
        items: list[MediaOrganizerItemResult] = []
        errors: list[ScanError] = []
        selected_count = 0
        ready_files, waiting_files, first_errors = self._discover_all_libraries(
            libraries, cancellation_check=cancellation_check
        )
        errors.extend(first_errors)
        if waiting_files and not ready_files:
            # Record this pass's real observation time *before* waiting, so the
            # later re-observation measures a genuine elapsed interval instead of
            # the instant the wait ended.
            self._previous_observations = {
                **self._previous_observations,
                **self._observation_map_multi(ready_files + waiting_files),
            }
            remaining = min(self._wait_seconds(library, file) for library, file in waiting_files)
            if 0 < remaining <= _MAX_STABILITY_WAIT_SECONDS and not (
                cancellation_check and cancellation_check()
            ):
                time.sleep(remaining + 0.05)
                ready_files, waiting_files, later_errors = self._discover_all_libraries(
                    libraries, cancellation_check=cancellation_check
                )
                errors = list(later_errors)
        self._previous_observations = {
            **self._previous_observations,
            **self._observation_map_multi(ready_files + waiting_files),
        }

        def handle(library: ResourceLibrary, file: DiscoveredFile) -> None:
            nonlocal selected_count
            if cancellation_check and cancellation_check():
                return
            if limit is not None and selected_count >= limit:
                return
            if file.status is not FileScanStatus.READY:
                if file.status is FileScanStatus.UNSTABLE:
                    items.append(self._waiting_item(library, file, library.root_path))
                return
            if (library.storage_id, file.path) in (skip_sources or set()):
                return
            selected_count += 1
            source = f"{library.storage_id}:{file.path}"
            items.append(
                self.process_file(
                    source,
                    resource_library=library,
                    storage_path=file.path,
                    execute=execute,
                    source_occurrence_id=file.occurrence_id,
                    source_fingerprint=file.fingerprint,
                    source_fingerprint_state=file.fingerprint_state,
                    source_observed_at=file.stable_since or file.discovered_at,
                    resolve_source_evidence=False,
                )
            )
            if progress:
                progress(len(items), limit, source)

        for library, file in ready_files + waiting_files:
            handle(library, file)
            if limit is not None and selected_count >= limit:
                break
        return MediaOrganizerBatchResult(
            tuple(items),
            tuple(errors),
            limit is not None and selected_count >= limit,
        )

    def _discover_all_libraries(
        self,
        libraries: tuple[ResourceLibrary, ...],
        *,
        cancellation_check: CancellationCheck | None,
    ) -> tuple[
        list[tuple[ResourceLibrary, DiscoveredFile]],
        list[tuple[ResourceLibrary, DiscoveredFile]],
        list[ScanError],
    ]:
        """One bounded discovery pass across every enabled library.

        Each library keeps its own observation scope so a same-named relative
        path in two libraries is never the same source.  A missing Storage or a
        disabled library is skipped exactly like the shared library scanner.
        """

        ready: list[tuple[ResourceLibrary, DiscoveredFile]] = []
        waiting: list[tuple[ResourceLibrary, DiscoveredFile]] = []
        errors: list[ScanError] = []
        for library in libraries:
            if not library.enabled or library.storage_id not in self._storages:
                continue
            if cancellation_check and cancellation_check():
                break

            def collect(file: DiscoveredFile, _library=library) -> None:
                if file.status is FileScanStatus.READY:
                    ready.append((_library, file))
                elif file.status is FileScanStatus.UNSTABLE:
                    waiting.append((_library, file))

            result = self._scanner.scan(
                library,
                on_discovered=collect,
                previous=self._observations_for_library(library),
            )
            errors.extend(result.errors)
        return ready, waiting, errors

    def _observations_for_library(
        self, library: ResourceLibrary
    ) -> Mapping[str, ObservedSource] | None:
        """This library's own durable observations from the multi-library map.

        A caller may have constructed the service with the historical flat
        ``{path: ObservedSource}`` map; that form is returned unchanged because
        it can only ever describe one library scope.
        """

        if all(isinstance(key, str) for key in self._previous_observations):
            return dict(self._previous_observations) or None
        selected = {
            key[1]: value
            for key, value in self._previous_observations.items()
            if isinstance(key, tuple) and len(key) == 2 and key[0] == library.library_id
        }
        return selected or None

    @staticmethod
    def _observation_map_multi(
        values: list[tuple[ResourceLibrary, DiscoveredFile]],
    ) -> dict[tuple[str, str], ObservedSource]:
        observed_at = datetime.now(UTC)
        result: dict[tuple[str, str], ObservedSource] = {}
        for library, file in values:
            result[(library.library_id, file.path)] = ObservedSource(
                file.path,
                file.size,
                file.modified_at,
                file.fingerprint,
                observed_at,
                file.stable_since,
            )
        return result

    def _failed(
        self,
        source: str,
        strategy: StrategyTestResult | None,
        error: str | Exception,
        tracked_item: PersistentTaskItem | None = None,
        retry_events: tuple[RetryEvent, ...] = (),
        *,
        plan: OrganizePlan | None = None,
        stage: str | None = None,
    ) -> MediaOrganizerItemResult:
        failure = classify_failure(error, strategy=strategy, stage=stage)
        # A pre-classified bounded refusal (for example the exact source-identity
        # refusal) must reach the durable TaskItem/Result as its own category even
        # on the CLI path, so a reopened Task can explain whether the source
        # changed, disappeared or was unverifiable.  Ordinary string/exception
        # failures keep the existing secret-free rendering switch.
        bounded = self._persist_failure_explanations or isinstance(error, FailureExplanation)
        message = failure.message if bounded else self._failure_message(error)
        item = MediaOrganizerItemResult(
            source,
            strategy,
            plan,
            error=message,
            retry_events=retry_events,
            failure=failure if bounded else None,
        )
        self._log(LogLevel.ERROR, "media workflow failed", source=source, error=message)
        return self._complete(item, tracked_item)

    def _failure_message(self, error: str | Exception) -> str:
        if isinstance(error, FailureExplanation):
            return error.message
        if not self._secret_free_errors:
            return str(error)
        if isinstance(error, MetadataError):
            return f"metadata provider error: {error.code.value}"
        if isinstance(error, StorageError):
            return f"storage operation error: {error.code.value}"
        if isinstance(error, RetryExhausted):
            return f"workflow retry exhausted: {error.category.value}"
        safe_message = getattr(error, "safe_message", None)
        if isinstance(safe_message, str) and safe_message.strip():
            return safe_message[:1000]
        return "single-item DryRun analysis failed"

    def _complete(
        self,
        item: MediaOrganizerItemResult,
        tracked_item: PersistentTaskItem | None,
        *,
        analysis_only: bool = False,
    ) -> MediaOrganizerItemResult:
        item = self._attach_evidence(item, tracked_item)
        self._record(item, tracked_item, persist_evidence=False)
        if self._task_coordinator and tracked_item:
            self._task_coordinator.complete_item(tracked_item, item, analysis_only=analysis_only)
        return item

    def _log(self, level: LogLevel, message: str, **context: object) -> None:
        if self._logger:
            if self._task_id and "task_id" not in context:
                # One run of the tracked pipeline attributes its own operational
                # logs with the exact persisted Task ID.  A plan ID alone is not
                # run-unique (two attempts at one source share a plan), so the
                # durable run linkage is written at emission time — never
                # inferred later from time, text or the plan ID.
                context = {**context, "task_id": self._task_id}
            self._logger.log(level, message, **context)

    def _record(
        self,
        item: MediaOrganizerItemResult,
        tracked_item: PersistentTaskItem | None = None,
        *,
        persist_evidence: bool = True,
    ) -> None:
        if (
            persist_evidence
            and item.evidence is not None
            and tracked_item is not None
            and self._task_coordinator is not None
        ):
            self._task_coordinator.record_evidence(item.evidence)
        identity = (
            item.strategy.metadata.identity if item.strategy and item.strategy.metadata else None
        )
        execution = item.execution
        self._history.append(
            OperationHistoryRecord.now(
                execution.plan_id if execution else f"failed:{len(self._history.list())}",
                item.source,
                execution.resolved_destination if execution else "",
                execution.operation.value if execution else "SKIP",
                (
                    execution.status.value
                    if execution
                    else "WAITING_METADATA"
                    if item.strategy
                    and item.strategy.metadata
                    and item.strategy.metadata.status
                    in {
                        MetadataIdentificationStatus.NEED_CONFIRM,
                        MetadataIdentificationStatus.AMBIGUOUS,
                    }
                    else "WAITING_METADATA_CORRECTION"
                    if item.strategy
                    and item.strategy.metadata
                    and item.strategy.metadata.status is MetadataIdentificationStatus.NOT_FOUND
                    and not item.error
                    else "WAITING_CLASSIFICATION"
                    if item.strategy
                    and item.strategy.classification
                    and item.strategy.classification.status is ClassificationStatus.UNCLASSIFIED
                    else "WAITING_RECOGNITION"
                    if item.strategy
                    and item.strategy.recognition.status is RecognitionStatus.UNRECOGNIZED
                    and not item.error
                    else "DRY_RUN"
                    if self._analysis_only and item.plan and item.plan.conflicts and not item.error
                    else "WAITING_CONFIRM"
                    if item.plan and item.plan.conflicts and not item.error
                    else "FAILED"
                ),
                provider_id=identity.provider_id if identity else None,
                title=identity.title if identity else None,
                error=item.error or ("; ".join(execution.errors) if execution else None),
            )
        )

    def _attach_evidence(
        self,
        item: MediaOrganizerItemResult,
        tracked_item: PersistentTaskItem | None,
    ) -> MediaOrganizerItemResult:
        if item.evidence is not None or tracked_item is None or self._task_coordinator is None:
            return item
        task = self._task_coordinator.repository.get_task(tracked_item.task_id)
        if task is None:
            return item
        organize_policy = None
        if item.strategy is not None and item.strategy.policy is not None:
            resolved = self._type_policies.get(item.strategy.policy.type_policy_id)
            if resolved is not None:
                organize_policy = resolved.organize_policy
        evidence = build_pipeline_evidence(
            task,
            tracked_item,
            strategy=item.strategy,
            plan=item.plan,
            execution=item.execution,
            error=item.error,
            outcome=self._evidence_outcome(item),
            storages=self._storages,
            organize_policy=organize_policy,
            conflict_finding=bool(
                self._analysis_only and item.plan is not None and bool(item.plan.conflicts)
            ),
        )
        return replace(item, evidence=evidence)

    def _evidence_outcome(self, item: MediaOrganizerItemResult) -> str:
        if item.execution is not None:
            return item.execution.status.value.lower()
        if item.error:
            return "failed"
        strategy = item.strategy
        if strategy is not None:
            if strategy.recognition.status is RecognitionStatus.UNRECOGNIZED:
                return "waiting_recognition"
            metadata = strategy.metadata
            if metadata is not None:
                if metadata.status in {
                    MetadataIdentificationStatus.NEED_CONFIRM,
                    MetadataIdentificationStatus.AMBIGUOUS,
                }:
                    return "waiting_metadata"
                if metadata.status is MetadataIdentificationStatus.NOT_FOUND:
                    return "waiting_metadata_correction"
            if (
                strategy.classification is not None
                and strategy.classification.status is ClassificationStatus.UNCLASSIFIED
            ):
                return "waiting_classification"
        if item.plan is not None:
            if item.plan.conflicts or item.plan.status.value in {"conflict", "invalid"}:
                return "dry_run" if self._analysis_only else "waiting_confirm"
            if item.plan.operation in {PlanOperation.NOOP, PlanOperation.SKIP}:
                return "skipped"
        return "processing"
