"""Zero-mutation continuation analysis for one kernel-admitted automatic Task.

Slice 47 RO-1/RO-3 makes the admitted Task the only subject of its own work.
After an operator saves a Recognition/Metadata/Classification/Conflict decision
on a Scheduler due / Run once Task item, the same Task — never a Job, a child
Task or a second recovery system — re-enters its own bounded analysis:

1. the saved decision re-queues the Task through the scheduling kernel
   (:mod:`mediaflow.application.manual_task_continuation`);
2. this module is the resident engine's continuation pass: it re-analyzes only
   the sources this Task still allows, under the Task's admitted pin, with the
   saved decisions applied, through the *existing* intent/Preview analysis
   machinery;
3. a ready plan is published as the item's own exact plan summary
   (``waiting_confirm``) plus one durable non-authorizing preparation row, so
   the operator reviews and explicitly confirms the ready subset on this same
   Task; the confirmation then executes through the existing one-shot authority
   and same-Task admission.

Nothing here mutates Storage, calls ``OrganizerExecutor`` or consumes execution
authority.  A settled sibling (success/ignore/dry-run/failed/cancelled), a
source still waiting for its own decision and an unproved in-flight effect are
never re-analyzed or replayed.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.application.recovery_decisions import collect_resolved_continuation_decisions
from mediaflow.domain.manual_organize import ManualSourceIdentity
from mediaflow.domain.manual_organize_preview import (
    ManualPreviewItemStatus,
    manual_preview_plan_problem,
)
from mediaflow.domain.manual_recovery import (
    ManualRecoveryPreparation,
    ManualRecoveryPreparationStatus,
)
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    TaskItemStatus,
)
from mediaflow.domain.task_scheduling import ScheduledTaskClaim

#: The item stages a saved four-type decision produces.  Only these items are
#: continuable: the decision is the last word of the item and its required
#: analysis/summary/confirmation steps are still owed on this same Task.
_DECIDED_ITEM_STAGES = frozenset(
    {
        "recognition_resolved",
        "metadata_resolved",
        "metadata_correction_resolved",
        "classification_resolved",
        "conflict_resolved",
    }
)

_MAX_REASON = 200


class AutomaticTaskContinuationError(RuntimeError):
    """A bounded refusal that keeps the Task's durable state exactly as it was."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class AutomaticTaskContinuationService:
    """Run one continuation-analysis pass for one claimed automatic Task."""

    def __init__(self, repository, *, intent_service, preview_service, checkpoint_service) -> None:
        self._repository = repository
        self._intents = intent_service
        self._previews = preview_service
        self._checkpoints = checkpoint_service

    def continuable_items(self, task_id: str) -> tuple[PersistentTaskItem, ...]:
        """The Task's own items whose saved decision still owes its continuation."""

        values = []
        for item in self._repository.list_items(task_id):
            if item.status is TaskItemStatus.PENDING and item.stage in _DECIDED_ITEM_STAGES:
                values.append(item)
        return tuple(values)

    def run_pass(
        self,
        task: PersistentTask,
        scheduling,
        claim: ScheduledTaskClaim,
        *,
        clock=None,
        heartbeat=None,
    ) -> str:
        """Re-analyze every continuable source of this claimed Task, zero mutation.

        Returns ``"analysis"`` when at least one source was re-analyzed and
        ``"none"`` when the Task holds no continuable source.  Every processed
        item ends in a durable waiting or settled state, so the caller's
        aggregate decision never spins on machine work this pass did not finish.
        """

        now = (clock or (lambda: datetime.now(UTC)))()
        items = self.continuable_items(task.task_id)
        if not items:
            return "none"
        actor = self._task_actor(task.task_id)
        for item in items:
            self._continue_item(
                task,
                scheduling,
                claim,
                item,
                actor=actor,
                now=now,
                heartbeat=heartbeat,
            )
        return "analysis"

    # -- One item ------------------------------------------------------------

    def _continue_item(
        self,
        task: PersistentTask,
        scheduling,
        claim: ScheduledTaskClaim,
        item: PersistentTaskItem,
        *,
        actor: str,
        now: datetime,
        heartbeat=None,
    ) -> None:
        if heartbeat is not None and not heartbeat():
            raise AutomaticTaskContinuationError(
                "the Task claim was lost before the next continuation analysis",
                code="claim_lost",
            )
        owner = self._source_owner(task.task_id, item)
        if owner is not None:
            self._publish_failed(
                scheduling,
                claim,
                item,
                now,
                error="source_already_organizing",
                operation="analysis",
            )
            return
        started = scheduling.begin_item(
            claim,
            storage_id=item.storage_id,
            resource_library_id=item.resource_library_id,
            source_path=item.source_path,
            source_display=item.source_display or item.source_path,
            source_occurrence_id=item.source_occurrence_id,
            source_fingerprint=item.source_fingerprint,
            source_fingerprint_state=item.source_fingerprint_state,
            source_observed_at=item.source_observed_at,
            source_storage_path=item.source_storage_path,
            now=now,
        )
        try:
            outcome = self._analyze_item(task, started, actor=actor)
        except AutomaticTaskContinuationError:
            raise
        except Exception as error:  # noqa: BLE001 - one bounded per-item refusal
            self._publish_failed(
                scheduling,
                claim,
                started,
                now,
                error=getattr(error, "code", None) or type(error).__name__,
                operation="analysis",
            )
            return
        if outcome is None:
            self._publish_failed(
                scheduling,
                claim,
                started,
                now,
                error="continuation_analysis_unavailable",
                operation="analysis",
            )
            return
        preview_item, preview = outcome
        if preview_item.status is ManualPreviewItemStatus.PREVIEWED and preview_item.plan:
            self._publish_summary(
                scheduling,
                claim,
                started,
                preview_item,
                preview,
                actor=actor,
                now=now,
            )
            return
        problem = manual_preview_plan_problem(preview_item.plan)
        if problem is not None:
            # The shared analysis published a genuine business decision on this
            # same Task and item (Recognition/Metadata/Metadata-correction/
            # Classification/Conflict).  That is not a technical failure: keep
            # the durable waiting state, re-read the item and re-project the
            # exact state under this live claim fence so the operator can
            # resolve it through the existing four-type flow.  Zero effects.
            current = self._repository.get_item(started.item_id)
            if current is not None and current.status in {
                TaskItemStatus.WAITING_RECOGNITION,
                TaskItemStatus.WAITING_METADATA,
                TaskItemStatus.WAITING_METADATA_CORRECTION,
                TaskItemStatus.WAITING_CLASSIFICATION,
                TaskItemStatus.WAITING_CONFIRM,
            }:
                scheduling.record_item(
                    claim,
                    replace(current, updated_at=now),
                    now=now,
                )
                return
        self._publish_failed(
            scheduling,
            claim,
            started,
            now,
            error=preview_item.error or preview_item.status.value,
            operation="analysis",
        )

    def _analyze_item(self, task: PersistentTask, item: PersistentTaskItem, *, actor: str):
        """One exact zero-mutation re-analysis of one decided source.

        The persisted source evidence is re-proved against live pinned Storage
        first; a replaced, missing or unverifiable source is refused before any
        Provider call.  The saved decisions are then applied through the
        existing intent/Preview analysis boundary, which produces the exact
        zero-mutation plan summary.
        """

        if not task.configuration_snapshot_id or not task.configuration_snapshot_digest:
            raise AutomaticTaskContinuationError(
                "the Task's admitted configuration pin is unavailable",
                code="configuration_unavailable",
            )
        validator = getattr(self._intents, "_source_validator", None)
        if validator is None or not callable(getattr(validator, "validate_persisted_source", None)):
            raise AutomaticTaskContinuationError(
                "the pinned source authority required by this continuation is unavailable",
                code="source_authority_unavailable",
            )
        from mediaflow.application.manual_source_validation import PersistedSourceEvidence

        try:
            validated = validator.validate_persisted_source(
                PersistedSourceEvidence(
                    item.storage_id,
                    item.resource_library_id,
                    item.source_path,
                    item.source_occurrence_id,
                    item.source_fingerprint,
                    item.source_fingerprint_state,
                ),
                snapshot_id=task.configuration_snapshot_id,
                snapshot_digest=task.configuration_snapshot_digest,
            )
        except Exception as error:  # noqa: BLE001 - one bounded source refusal
            raise AutomaticTaskContinuationError(
                getattr(error, "code", None) or type(error).__name__,
                code="source_unavailable",
            ) from error
        entry = validated.entry
        source = ManualSourceIdentity(
            validated.occurrence_id,
            item.storage_id,
            item.resource_library_id,
            item.source_path,
            entry.name,
            entry.name.rsplit(".", 1)[-1].lower(),
            entry.size,
            entry.modified_at,
            datetime.now(UTC),
            item.source_observed_at,
            occurrence_id=validated.occurrence_id,
            fingerprint=validated.fingerprint,
            occurrence_state="verified",
        )
        recognition_type = self._decided_recognition_type(item)
        if not recognition_type:
            raise AutomaticTaskContinuationError(
                "the saved decision does not name a RecognitionType",
                code="decision_incomplete",
            )
        intent = self._intents.create_from_sources(
            (source,),
            actor=actor,
            snapshot_id=task.configuration_snapshot_id,
            snapshot_digest=task.configuration_snapshot_digest,
            pinned_snapshot=True,
        )
        intent_item = intent.items[0]
        intent = self._intents.update_choice(
            intent.intent_id,
            intent_item.item_id,
            {"recognitionTypeId": recognition_type},
            expected_version=intent.version,
            expected_item_version=intent_item.version,
            actor=actor,
            snapshot_id=intent.snapshot_id,
            snapshot_digest=intent.snapshot_digest,
        )
        decisions = collect_resolved_continuation_decisions(
            self._repository,
            source_item_id=item.item_id,
        )
        preview = self._previews.create(
            intent.intent_id,
            [intent_item.item_id],
            expected_version=intent.version,
            expected_item_versions={intent_item.item_id: intent.items[0].version},
            snapshot_id=intent.snapshot_id,
            snapshot_digest=intent.snapshot_digest,
            actor=actor,
            review_decisions=decisions,
            skip_current_snapshot_check=True,
            # A re-analysis that reaches a *different* native four-type problem
            # (for example a Recognition decision now failing Classification)
            # publishes that finding on this same Task instead of becoming a
            # technical failure.  The projector reuses the TaskItem this pass
            # already started for the same verified source.
            problem_task_id=task.task_id,
        )
        preview_item = next(
            (value for value in preview.items if value.item_id == intent_item.item_id),
            None,
        )
        if preview_item is None:
            return None
        return preview_item, preview

    def _decided_recognition_type(self, item: PersistentTaskItem) -> str | None:
        """The RecognitionType the item's own saved decision resolved under.

        A Recognition decision names the type directly.  A Metadata,
        Metadata-correction or Classification decision records the type its
        resolved analysis ran under.  A Conflict decision belongs to an item
        whose analysis already resolved the type, so the item's own durable
        evidence names it; a missing or unreadable evidence refuses instead of
        inventing a type.
        """

        review = self._repository.get_recognition_review_for_item(item.item_id)
        if (
            review is not None
            and getattr(review.status, "value", review.status) == "resolved"
            and review.selected_recognition_type
        ):
            return review.selected_recognition_type
        for reader in (
            self._repository.get_metadata_review_for_item,
            self._repository.get_metadata_correction_for_item,
            self._repository.get_classification_review_for_item,
        ):
            value = reader(item.item_id)
            if (
                value is not None
                and getattr(value.status, "value", value.status) == "resolved"
                and getattr(value, "recognition_type", None)
            ):
                return value.recognition_type
        for value in self._evidence_recognition_types(item.item_id):
            if value:
                return value
        return None

    def _evidence_recognition_types(self, item_id: str) -> tuple[str | None, ...]:
        reader = getattr(self._repository, "list_evidence_for_item", None)
        if not callable(reader):
            return ()
        try:
            evidence = tuple(reader(item_id, limit=16))
        except Exception:  # noqa: BLE001 - unreadable evidence refuses the type
            return ()
        values = []
        for value in reversed(evidence):
            section = getattr(value, "section", None)
            document = None
            if callable(section):
                try:
                    found = value.section("recognition")
                except Exception:  # noqa: BLE001 - one unreadable section is skipped
                    found = None
                document = getattr(found, "value", None) if found is not None else None
            if isinstance(document, dict):
                kind = document.get("recognitionTypeId")
                if isinstance(kind, str):
                    values.append(kind)
        return tuple(values)

    # -- Publications --------------------------------------------------------

    def _publish_summary(
        self,
        scheduling,
        claim: ScheduledTaskClaim,
        item: PersistentTaskItem,
        preview_item,
        preview,
        *,
        actor: str,
        now: datetime,
    ) -> None:
        """Park one ready plan as this same item's exact confirmable summary."""

        plan = preview_item.plan if isinstance(preview_item.plan, dict) else {}
        raw_execution_plan = plan.get("executionPlan")
        execution_plan = raw_execution_plan if isinstance(raw_execution_plan, dict) else {}
        waiting = replace(
            item,
            status=TaskItemStatus.WAITING_CONFIRM,
            stage="continuation_planned",
            updated_at=now,
            plan_id=plan.get("planId") if isinstance(plan.get("planId"), str) else None,
            destination_storage_id=(
                execution_plan.get("targetStorageId")
                if isinstance(execution_plan.get("targetStorageId"), str)
                else None
            ),
            destination_path=(
                execution_plan.get("targetPath")
                if isinstance(execution_plan.get("targetPath"), str)
                else None
            ),
            error=None,
        )
        scheduling.record_item(claim, waiting, now=now)
        checkpoint = self._checkpoints.get(item.item_id, task_id=claim.task_id)
        previous = self._repository.get_current_manual_recovery_preparation(
            claim.task_id, item.item_id
        )
        if previous is not None:
            self._repository.supersede_manual_recovery_preparation(previous.preparation_id, now=now)
        preparation = ManualRecoveryPreparation(
            str(uuid4()),
            claim.task_id,
            item.item_id,
            "",
            claim.task_id,
            "",
            preview.intent_id,
            preview.preview_id,
            preview.intent_version,
            checkpoint.checkpoint_version,
            preview_item.input_fingerprint,
            preview.configuration_snapshot_id,
            preview.configuration_snapshot_digest,
            actor,
            ManualRecoveryPreparationStatus.PREPARED,
            now,
            now,
        )
        self._repository.create_manual_recovery_preparation(preparation)

    def _publish_failed(
        self,
        scheduling,
        claim: ScheduledTaskClaim,
        item: PersistentTaskItem,
        now: datetime,
        *,
        error: str,
        operation: str,
    ) -> None:
        """Publish one effect-free failed continuation attempt under the claim."""

        completed = replace(
            item,
            status=TaskItemStatus.FAILED,
            stage="failed",
            updated_at=now,
            error=error[:_MAX_REASON],
        )
        result = PersistentResultRecord(
            f"{item.item_id}:{item.attempts}",
            item.task_id,
            item.item_id,
            item.storage_id,
            item.source_display or item.source_path,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            operation,
            TaskItemStatus.FAILED.value,
            now,
            error=error[:_MAX_REASON],
            effect_certainty="none",
            source_occurrence_id=item.source_occurrence_id,
            source_fingerprint=item.source_fingerprint,
            source_fingerprint_state=item.source_fingerprint_state,
            source_observed_at=item.source_observed_at,
        )
        scheduling.complete_item(claim, completed, result=result, now=now)

    # -- Helpers -------------------------------------------------------------

    def _source_owner(self, task_id: str, item: PersistentTaskItem):
        """Another unfinished work that owns this exact source, if any."""

        finder = getattr(self._repository, "find_owned_source_work", None)
        if not callable(finder):
            return None
        try:
            return finder(
                storage_id=item.storage_id,
                source_path=item.source_path,
                storage_path=item.source_storage_path,
                resource_library_id=item.resource_library_id,
                source_version=None,
                exclude_task_id=task_id,
            )
        except Exception:  # noqa: BLE001 - an unreadable boundary fails closed
            return object()

    def _task_actor(self, task_id: str) -> str:
        """The operator who requested this continuation, or the admission principal.

        A saved decision is continued by an authenticated operator.  That actor
        — not the Scheduler/Run once principal that originally admitted the
        Task — owns the analysis intent, its plan summary and the explicit
        confirmation, exactly like a Files preparation.  The original
        scheduling provenance remains ``admission_principal`` on the same row,
        so the two identities are never conflated or overwritten.
        """

        state = None
        reader = getattr(self._repository, "get_task_scheduling", None)
        if callable(reader):
            try:
                state = reader(task_id)
            except Exception:  # noqa: BLE001 - an unreadable row keeps the label
                state = None
        for value in (
            getattr(state, "continuation_actor", None),
            getattr(state, "admission_principal", None),
        ):
            if isinstance(value, str) and value.strip():
                return value.strip()[:200]
        return "automatic-task"


__all__ = ["AutomaticTaskContinuationError", "AutomaticTaskContinuationService"]
