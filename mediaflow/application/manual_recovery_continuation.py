"""Exact one-shot continuation authority for a manual Organize recovery item.

The service keeps the original manual TaskItem as the durable anchor while a
completed single-item re-analysis (DryRun) proves that the current source can be
planned again.  It then creates a fresh exact Preview on the original manual
intent and consumes the existing one-shot manual execution authorization path.
The resulting link is persisted beside the original TaskItem so API and Web can
return to the original Organize journey after reload.
"""

from __future__ import annotations

from datetime import UTC, datetime

from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.domain.manual_execution import (
    MANUAL_EXECUTION_PERMISSION,
    ManualExecution,
    ManualExecutionError,
)
from mediaflow.domain.manual_recovery import (
    ManualRecoveryPreparation,
    ManualRecoveryPreparationStatus,
)
from mediaflow.domain.task_persistence import TaskItemStatus

#: Prefix that marks a *synthetic* same-page summary of a kernel-managed Task's
#: own linked Files preparation.  It is not a persisted
#: ``manual_recovery_preparations`` row: the durable summary already exists as
#: the Task's linked bounded discovery plus its exact Preview, so the Task
#: Center reads and confirms that same record instead of minting a second
#: preparation or a legacy recovery chain.
NATIVE_PREPARATION_PREFIX = "native:"


def native_preparation_id(discovery_id: str, preview_id: str) -> str:
    """The stable, operator-readable identity of one native Task summary.

    The identity binds the Task's own linked bounded discovery to the *exact
    immutable Preview* the operator reviewed.  Re-running the analysis
    supersedes that Preview, so the older summary can never be confirmed
    against a newer plan merely because it belongs to the same discovery.
    """

    return f"{NATIVE_PREPARATION_PREFIX}{discovery_id}:{preview_id}"


def native_preparation_ref(preparation_id: str) -> tuple[str, str] | None:
    """The ``(discovery_id, preview_id)`` a native summary names, or ``None``."""

    if not isinstance(preparation_id, str) or not preparation_id.startswith(
        NATIVE_PREPARATION_PREFIX
    ):
        return None
    body = preparation_id[len(NATIVE_PREPARATION_PREFIX) :]
    discovery_id, separator, preview_id = body.partition(":")
    if not separator or not discovery_id or not preview_id:
        return None
    return discovery_id, preview_id


def native_preparation_discovery_id(preparation_id: str) -> str | None:
    """The discovery a native summary confirmation names, or ``None``."""

    ref = native_preparation_ref(preparation_id)
    return ref[0] if ref is not None else None


class ManualRecoveryContinuationError(ManualExecutionError):
    """Bounded error for the manual recovery continuation authority."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "manual_recovery_continuation_rejected",
        status: int = 409,
        next_action: str = (
            "inspect the original manual Organize item and the linked single-item "
            "re-analysis evidence, then explicitly continue again"
        ),
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            next_action=next_action,
            status=status,
            details=details,
        )


class ManualRecoveryContinuationService:
    """Persistence/application boundary for continued manual execution."""

    MAX_ACTOR = 200
    MAX_NOTE = 500

    def __init__(
        self,
        repository,
        *,
        intent_service: ManualOrganizeIntentService,
        preview_service: ManualOrganizePreviewService,
        execution_service: ManualOrganizeExecutionService,
        checkpoint_service: ProcessingCheckpointService | None = None,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._intents = intent_service
        self._previews = preview_service
        self._execution = execution_service
        self._checkpoint_service = checkpoint_service or execution_service._checkpoint_service
        self._clock = clock

    @property
    def repository(self):
        return self._repository

    def confirm_prepared(
        self,
        preparation_id: str,
        *,
        item_ids,
        actor: str,
        permission: str = MANUAL_EXECUTION_PERMISSION,
        confirmation: bool = False,
        allow_overwrite: bool = False,
        allow_source_cleanup: bool = False,
    ) -> ManualExecution:
        """Confirm one exact ready subset of a prepared summary.

        The confirmation is bound to the persisted summary, its exact Preview,
        the original checkpoint version and the current actor.  Only the ready
        subset the operator selected is admitted through the existing one-shot
        authority path and the existing atomic admission; the summary is linked
        to the resulting execution inside that same transaction.  Unselected,
        not-ready, already-admitted or uncertain siblings are never implied.
        """

        actor = self._actor(actor)
        if permission != MANUAL_EXECUTION_PERMISSION:
            raise ManualRecoveryContinuationError(
                "continued manual execution permission is invalid",
                code="invalid_permission",
                status=403,
            )
        if confirmation is not True:
            raise ManualRecoveryContinuationError(
                "continued manual execution requires confirmation=true",
                code="confirmation_required",
            )
        preparation = self._repository.get_manual_recovery_preparation(preparation_id)
        if preparation is None:
            raise ManualRecoveryContinuationError(
                "the recovery plan summary was not found",
                code="preparation_not_found",
                status=404,
            )
        if preparation.actor != actor:
            raise ManualRecoveryContinuationError(
                "the recovery plan summary belongs to another actor",
                code="preparation_actor_mismatch",
                status=403,
            )
        selected = self._normalize_selection(item_ids)
        allow_overwrite = bool(allow_overwrite)
        allow_source_cleanup = bool(allow_source_cleanup)
        if preparation.status is ManualRecoveryPreparationStatus.CONFIRMED:
            return self._confirmed_equivalent_execution(
                preparation,
                selected=selected,
                allow_overwrite=allow_overwrite,
                allow_source_cleanup=allow_source_cleanup,
            )
        if preparation.status is not ManualRecoveryPreparationStatus.PREPARED:
            raise ManualRecoveryContinuationError(
                "this recovery plan summary is no longer the current plan",
                code="preparation_stale",
                next_action=preparation.next_action(),
            )
        current = self._repository.get_current_manual_recovery_preparation(
            preparation.source_task_id, preparation.source_item_id
        )
        if current is None or current.preparation_id != preparation.preparation_id:
            raise ManualRecoveryContinuationError(
                "a newer plan summary replaced this one",
                code="preparation_superseded",
                next_action="reload the current plan summary and confirm again",
            )
        # The preflight proves the item still carries the exact summary
        # checkpoint; the atomic admission re-projects the same bounded
        # checkpoint inside its own write transaction, so a concurrent change
        # between this read and admission is still refused.
        checkpoint = self._checkpoint_service.get(
            preparation.source_item_id, task_id=preparation.source_task_id
        )
        if checkpoint.checkpoint_version != preparation.checkpoint_version:
            raise ManualRecoveryContinuationError(
                "the item changed after the summary was prepared",
                code="stale_checkpoint",
                details={"currentCheckpointVersion": checkpoint.checkpoint_version},
            )
        try:
            execution = self._execution.begin_web_execution(
                preparation.preview_id,
                list(selected),
                expected_intent_version=preparation.intent_version,
                actor=actor,
                permission=permission,
                confirmation=True,
                allow_overwrite=allow_overwrite,
                allow_source_cleanup=allow_source_cleanup,
                preparation_id=preparation.preparation_id,
            )
        except ManualExecutionError as error:
            self._handle_confirm_failure(preparation, error)
            raise
        # The atomic admission linked the summary inside its own transaction;
        # reload the durable record so the caller sees the confirmed state.
        linked = self._repository.get_manual_recovery_preparation(preparation.preparation_id)
        if linked is not None and linked.status is not ManualRecoveryPreparationStatus.CONFIRMED:
            raise ManualRecoveryContinuationError(
                "the admitted execution was not linked to its plan summary",
                code="preparation_unlinked",
                status=503,
            )
        return execution

    def _confirmed_equivalent_execution(
        self,
        preparation: ManualRecoveryPreparation,
        *,
        selected: tuple[str, ...],
        allow_overwrite: bool,
        allow_source_cleanup: bool,
    ) -> ManualExecution:
        """Resolve a repeat confirmation only when it is exactly equivalent.

        A repeated submission may be folded into the already-admitted execution
        only when it reviewed the same principal, the same exact selected item
        set and the same destructive permissions.  Any different, narrower,
        overlapping or empty selection is a *different* submission and must be
        refused with its own reason instead of silently returning work the
        operator never selected.
        """

        if preparation.execution_id is None or preparation.authorization_id is None:
            raise ManualRecoveryContinuationError(
                "the confirmed summary has no durable execution",
                code="preparation_inconsistent",
            )
        if (
            set(selected) != set(preparation.selected_item_ids)
            or allow_overwrite != preparation.allow_overwrite
            or allow_source_cleanup != preparation.allow_source_cleanup
        ):
            raise ManualRecoveryContinuationError(
                "this confirmation differs from the already-admitted submission",
                code="confirmation_mismatch",
                next_action=(
                    "inspect the linked execution; a different selection or permission "
                    "requires a fresh plan summary and explicit confirmation"
                ),
                details={"executionId": preparation.execution_id},
            )
        execution = self._repository.get_manual_execution(preparation.execution_id)
        if execution is None:
            raise ManualRecoveryContinuationError(
                "the linked execution is unavailable",
                code="execution_unavailable",
                status=503,
            )
        return execution

    def _handle_confirm_failure(
        self, preparation: ManualRecoveryPreparation, error: ManualExecutionError
    ) -> None:
        """Keep an unconfirmed summary usable when confirmation is refused.

        A refusal that consumed no authority (for example a stale item or a
        selection outside the ready scope) leaves the summary inspectable so the
        operator can correct and retry; a summary whose authority was consumed
        is resolved by the repository's atomic link, never here.
        """

        return None

    def native_preparation_summary(
        self, source_task_id: str, source_item_id: str
    ) -> dict[str, object] | None:
        """The kernel-managed Task's own linked Files preparation as a summary.

        A Task admitted by the unified engine has already produced the exact
        zero-mutation plan summary as its linked bounded discovery and Preview.
        The Task Center therefore reads *that* durable record; it never mints a
        second preparation, Job or child Task.  The method is read-only and
        returns ``None`` for a Task that does not own a linked preparation, for
        an item that already settled with no admitted execution, or for a
        different principal's/ Task's item.

        The confirmed step is bound to the *exact source item* an execution
        admitted, never to "any execution of the same discovery".  A sibling
        that was not part of the confirmed subset therefore keeps its own
        pending summary instead of borrowing another file's execution.  The
        summary identity binds the discovery to the exact reviewed Preview, so
        the confirm path can prove the operator still reviewed the current plan.
        """

        finder = getattr(self._repository, "get_media_discovery_for_task", None)
        if not callable(finder):
            return None
        discovery = finder(source_task_id)
        if discovery is not None and discovery.organize_task_id == source_task_id:
            return self._files_native_summary(source_task_id, source_item_id, discovery)
        return self._automatic_native_summary(source_task_id, source_item_id)

    def _files_native_summary(self, source_task_id: str, source_item_id: str, discovery):
        """The Files-admitted Task's own linked discovery/preview summary."""

        item = self._repository.get_item(source_item_id)
        if item is None or item.task_id != source_task_id:
            return None
        preview_getter = getattr(self._repository, "get_manual_preview", None)
        if not callable(preview_getter):
            return None
        execution = self._native_admitted_execution_for_item(source_task_id, source_item_id)
        # The current discovery Preview is the product of the latest completed
        # analysis.  A source whose admitted execution reviewed an older Preview
        # has since been re-analyzed on this same Task, so that execution is
        # history rather than the confirmation identity of the new summary.
        recovery_execution = None
        if execution is not None and execution.preview_id != discovery.preview_id:
            recovery_execution = execution
            execution = None
        preview_id = (
            execution.preview_id
            if execution is not None
            else (
                discovery.preview_id
                or (recovery_execution.preview_id if recovery_execution is not None else None)
            )
        )
        if not preview_id:
            return None
        preview = preview_getter(preview_id)
        if preview is None:
            return None
        if execution is None:
            # The summary is only the operator's confirmable boundary once the
            # complete analysis parked this exact source at ``waiting_confirm``
            # *and* the source either really carries its own saved four-type
            # decision or this same Task re-analyzed it after an already admitted
            # execution.  A plain initial confirmation, a source still waiting on
            # another problem, or settled history is therefore never published as
            # a recovery summary.
            if item.status is not TaskItemStatus.WAITING_CONFIRM:
                return None
            problem_reader = getattr(self._repository, "has_current_four_type_problem", None)
            has_problem = callable(problem_reader) and problem_reader(source_item_id)
            decision_reader = getattr(self._repository, "has_resolved_four_type_decision", None)
            has_decision = callable(decision_reader) and decision_reader(source_item_id)
            if not has_problem and not has_decision and recovery_execution is None:
                return None
        document = self._native_summary_document(discovery, item, preview, execution=execution)
        if (
            document is not None
            and execution is None
            and self._preview_is_stale(preview.preview_id)
        ):
            # The reviewed Preview is no longer executable (for example a
            # confirmed sibling changed the shared evidence).  Report the
            # summary as stale so the page steers to the required fresh
            # analysis instead of offering a confirmation that can only be
            # refused; the durable history stays readable either way.
            document["status"] = ManualRecoveryPreparationStatus.STALE.value
        return document

    def _automatic_native_summary(self, source_task_id: str, source_item_id: str):
        """One kernel-admitted automatic Task's own durable continuation summary.

        A Scheduler due / Run once / remote or direct organize Task owns no Files
        discovery.  Its continuation analysis produces the same durable
        non-authorizing summary through a real ``manual_recovery_preparations``
        row the resident engine wrote for this exact TaskItem, so the Task Center
        reads and confirms that record instead of inventing a Files submission.
        The method is read-only and returns ``None`` for a Task the kernel does
        not own, an item without a current summary, or a different Task's item.
        """

        reader = getattr(self._repository, "get_task_scheduling", None)
        if not callable(reader):
            return None
        try:
            state = reader(source_task_id)
        except Exception:  # noqa: BLE001 - an unreadable kernel row keeps None
            return None
        if state is None:
            return None
        item = self._repository.get_item(source_item_id)
        if item is None or item.task_id != source_task_id:
            return None
        preparation = self._repository.get_current_manual_recovery_preparation(
            source_task_id, source_item_id
        )
        if preparation is None:
            return None
        preview_getter = getattr(self._repository, "get_manual_preview", None)
        if not callable(preview_getter):
            return None
        execution = self._native_admitted_execution_for_item(source_task_id, source_item_id)
        preview = preview_getter(preparation.preview_id)
        if preview is None:
            return None
        if execution is None and item.status is not TaskItemStatus.WAITING_CONFIRM:
            # A summary is only the operator's confirmable boundary while this
            # exact source is parked at its own plan summary.  A decided item
            # whose analysis has not run yet, a processing execution or settled
            # history is never published as a pending summary.
            return None
        document = dict(preparation.document())
        document["hasExecutionAuthority"] = False
        document["previewPath"] = "/api/v1/manual-previews/" + preparation.preview_id
        document["executionPath"] = (
            "/api/v1/manual-executions/" + execution.execution_id if execution is not None else None
        )
        document["next_action"] = preparation.next_action()
        if document.get(
            "status"
        ) == ManualRecoveryPreparationStatus.PREPARED.value and self._preview_is_stale(
            preparation.preview_id
        ):
            # The reviewed Preview is no longer executable; steer to the
            # required fresh analysis instead of offering a confirmation that
            # can only be refused.  The durable history stays readable.
            document["status"] = ManualRecoveryPreparationStatus.STALE.value
        return document

    def _preview_is_stale(self, preview_id: str) -> bool:
        reader = getattr(self._previews, "get_readonly", None)
        if not callable(reader):
            return False
        try:
            projected = reader(preview_id)
        except Exception:
            return False
        return projected is not None and not projected.current

    def _native_summary_document(self, discovery, item, preview, *, execution):
        """One durable projection of the Task's own linked summary.

        The identity binds the discovery to the exact immutable Preview the
        operator reviewed.  A confirmed execution is reported only for the
        source item it actually admitted; every other sibling keeps its own
        prepared state and a fresh preview identity after any re-analysis.
        """

        try:
            checkpoint = self._checkpoint_service.get(
                item.item_id, task_id=discovery.organize_task_id
            )
        except LookupError:
            return None
        input_fingerprint = ""
        for value in preview.items:
            source = getattr(value, "source", None)
            matches_item = (
                getattr(source, "path", None) == item.source_path
                and getattr(source, "storage_id", None) == item.storage_id
            )
            if matches_item or not input_fingerprint:
                input_fingerprint = value.input_fingerprint or input_fingerprint
        confirmed = execution is not None
        return {
            "preparation_id": native_preparation_id(discovery.discovery_id, preview.preview_id),
            "source_task_id": discovery.organize_task_id,
            "source_item_id": item.item_id,
            "analysis_continuation_id": "",
            "analysis_task_id": discovery.organize_task_id,
            "analysis_result_id": "",
            "intent_id": preview.intent_id,
            "preview_id": preview.preview_id,
            "intent_version": preview.intent_version,
            "checkpoint_version": checkpoint.checkpoint_version,
            "input_fingerprint": input_fingerprint,
            "configuration_snapshot_id": discovery.snapshot_id,
            "configuration_snapshot_digest": discovery.snapshot_digest,
            "actor": discovery.actor,
            "status": (
                ManualRecoveryPreparationStatus.CONFIRMED.value
                if confirmed
                else ManualRecoveryPreparationStatus.PREPARED.value
            ),
            "authorization_id": None,
            "execution_id": execution.execution_id if execution is not None else None,
            "selected_item_ids": (
                list(execution.selected_item_ids) if execution is not None else []
            ),
            "allow_overwrite": execution.allow_overwrite if execution is not None else False,
            "allow_source_cleanup": (
                execution.allow_source_cleanup if execution is not None else False
            ),
            "created_at": discovery.created_at.isoformat(),
            "updated_at": discovery.updated_at.isoformat(),
            "hasExecutionAuthority": False,
            "next_action": (
                "inspect the linked execution and its independent Task/TaskItem/Result evidence"
                if confirmed
                else (
                    "review the current plan summary, select the ready subset and "
                    "explicitly confirm the exact Organize action"
                )
            ),
            "previewPath": "/api/v1/manual-previews/" + preview.preview_id,
            "executionPath": (
                "/api/v1/manual-executions/" + execution.execution_id
                if execution is not None
                else None
            ),
        }

    def _native_admitted_execution_for_item(self, task_id: str, task_item_id: str):
        """The one admitted execution that contains this exact TaskItem, if any.

        The relation is the durable ``manual_execution_items`` linkage of the
        exact ``(task_id, task_item_id)`` pair, not a time-, path- or
        list-order guess.  A sibling that was never selected therefore never
        matches, even though it belongs to the same discovery/preview.
        """

        reader = getattr(self._repository, "list_manual_executions_for_task", None)
        if not callable(reader):
            return None
        try:
            values = tuple(reader(task_id, limit=100))
        except Exception:
            return None
        for execution in values:
            if any(
                value.task_id == task_id and value.task_item_id == task_item_id
                for value in execution.items
            ):
                return execution
        return None

    def confirm_native_preparation(
        self,
        preparation_id: str,
        *,
        item_ids,
        actor: str,
        permission: str = MANUAL_EXECUTION_PERMISSION,
        confirmation: bool = False,
        allow_overwrite: bool = False,
        allow_source_cleanup: bool = False,
    ) -> ManualExecution:
        """Confirm the exact ready subset of a native Task's linked summary.

        This reuses the existing Files Preview/execution admission unchanged:
        the exact selected ready subset, its pinned configuration, capacity and
        one-shot authority are validated by the production execution service,
        and the resulting execution re-registers the *same* Task through the
        scheduling kernel.  It mints no Job, child Task or second preparation.

        The confirmation is bound to the exact immutable Preview the operator
        reviewed: if a newer analysis superseded that Preview, the old page is
        refused without consuming authority, mutating Storage or executing the
        newer, unreviewed plan.
        """

        ref = native_preparation_ref(preparation_id)
        if ref is None:
            raise ManualRecoveryContinuationError(
                "the recovery plan summary is not a native Task summary",
                code="preparation_not_found",
                status=404,
            )
        discovery_id, reviewed_preview_id = ref
        actor = self._actor(actor)
        if permission != MANUAL_EXECUTION_PERMISSION:
            raise ManualRecoveryContinuationError(
                "continued manual execution permission is invalid",
                code="invalid_permission",
                status=403,
            )
        if confirmation is not True:
            raise ManualRecoveryContinuationError(
                "continued manual execution requires confirmation=true",
                code="confirmation_required",
            )
        getter = getattr(self._repository, "get_media_discovery", None)
        discovery = getter(discovery_id) if callable(getter) else None
        if discovery is None or not discovery.organize_task_id or not discovery.preview_id:
            raise ManualRecoveryContinuationError(
                "the linked preparation for this summary is unavailable",
                code="preparation_stale",
                next_action="reload the organizing work and inspect its current state",
            )
        if discovery.preview_id != reviewed_preview_id:
            # A newer analysis replaced the Preview the operator reviewed.  The
            # old page must never execute the newer plan: nothing is consumed or
            # mutated, and the operator is pointed at the current summary.
            raise ManualRecoveryContinuationError(
                "a newer plan summary replaced the one you reviewed",
                code="preparation_stale",
                next_action=(
                    "reload the current plan summary, review it and confirm its ready subset again"
                ),
                details={"previewId": discovery.preview_id},
            )
        if discovery.actor != actor:
            raise ManualRecoveryContinuationError(
                "the linked preparation belongs to another operator",
                code="preparation_actor_mismatch",
                status=403,
                next_action=(
                    "open your own organizing work, or ask the admitting operator to confirm"
                ),
            )
        preview_getter = getattr(self._repository, "get_manual_preview", None)
        preview = preview_getter(reviewed_preview_id) if callable(preview_getter) else None
        if preview is None or not preview.current:
            raise ManualRecoveryContinuationError(
                "the reviewed plan summary is no longer current",
                code="preparation_stale",
                next_action="reload the current plan summary and confirm it again",
            )
        try:
            return self._execution.begin_web_execution(
                reviewed_preview_id,
                list(item_ids),
                expected_intent_version=preview.intent_version,
                actor=actor,
                permission=permission,
                confirmation=True,
                allow_overwrite=bool(allow_overwrite),
                allow_source_cleanup=bool(allow_source_cleanup),
            )
        except ManualExecutionError:
            raise
        except Exception as error:
            raise ManualRecoveryContinuationError(
                "the confirmation was not admitted",
                code="confirmation_rejected",
                next_action=("reload the current plan summary and confirm its ready subset again"),
            ) from error

    def prepare_native_summary(
        self,
        source_task_id: str,
        source_item_id: str,
        *,
        expected_checkpoint_version: str,
        actor: str,
    ) -> dict[str, object]:
        """Return the kernel-managed Task's existing linked summary.

        The native summary already exists as the Task's linked discovery and
        Preview, so "preparing" it is a bounded read that verifies the current
        checkpoint version.  It creates no new durable row, no authority and no
        mutation.
        """

        actor = self._actor(actor)
        summary = self.native_preparation_summary(source_task_id, source_item_id)
        if summary is None:
            raise ManualRecoveryContinuationError(
                "this Task has no linked plan summary to prepare",
                code="preparation_not_found",
                status=404,
            )
        try:
            checkpoint = self._checkpoint_service.get(source_item_id, task_id=source_task_id)
        except LookupError:
            raise ManualRecoveryContinuationError(
                "TaskItem was not found",
                code="not_found",
                status=404,
            ) from None
        if expected_checkpoint_version != checkpoint.checkpoint_version:
            raise ManualRecoveryContinuationError(
                "the item changed after the summary was opened",
                code="stale_checkpoint",
                details={"currentCheckpointVersion": checkpoint.checkpoint_version},
            )
        if summary["status"] != ManualRecoveryPreparationStatus.PREPARED.value:
            raise ManualRecoveryContinuationError(
                "the linked summary has already been confirmed",
                code="preparation_superseded",
                next_action=summary.get("next_action"),
            )
        return summary

    def discovery_for_preparation(
        self, source_task_id: str, source_item_id: str
    ) -> dict[str, object] | None:
        """Return the current non-authorizing plan summary for one source item.

        The projection is deliberately authority-free: it exposes only the
        durable preparation identity, its exact Preview and the safe next step.
        A confirmed preparation additionally names its linked execution so the
        operator can follow the real result.
        """

        preparation = self._repository.get_current_manual_recovery_preparation(
            source_task_id, source_item_id
        )
        if preparation is None:
            native = self.native_preparation_summary(source_task_id, source_item_id)
            if native is not None:
                return native
            return None
        value = preparation.document()
        value["hasExecutionAuthority"] = False
        return value

    def supports_source_item(self, source_task_id: str, source_item_id: str) -> bool:
        """Whether this exact item still has a current Task-owned summary path."""

        return self.native_preparation_summary(source_task_id, source_item_id) is not None

    def analysis_summary_available(self, source_task_id: str, source_item_id: str) -> bool:
        """Whether this exact item already has a prepared Task-owned summary."""

        native = self.native_preparation_summary(source_task_id, source_item_id)
        return (
            native is not None
            and native.get("status") == ManualRecoveryPreparationStatus.PREPARED.value
        )

    @staticmethod
    def _normalize_selection(item_ids) -> tuple[str, ...]:
        """Validate one exact, bounded, unique item selection before any admission."""

        if isinstance(item_ids, (str, bytes)):
            raise ManualRecoveryContinuationError(
                "the confirmed selection must be a bounded item list",
                code="malformed_selection",
                status=400,
            )
        try:
            values = tuple(item_ids)
        except TypeError as error:
            raise ManualRecoveryContinuationError(
                "the confirmed selection must be a bounded item list",
                code="malformed_selection",
                status=400,
            ) from error
        if not values:
            raise ManualRecoveryContinuationError(
                "at least one ready item must be selected",
                code="selection_empty",
                status=400,
            )
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ManualRecoveryContinuationError(
                "the confirmed selection must contain non-empty item IDs",
                code="malformed_selection",
                status=400,
            )
        if len(set(values)) != len(values):
            raise ManualRecoveryContinuationError(
                "the confirmed selection must not contain duplicates",
                code="duplicate_selection",
                status=400,
            )
        return values

    @staticmethod
    def _actor(value: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ManualRecoveryContinuationError(
                "manual recovery actor is required",
                code="invalid_actor",
                status=403,
            )
        return value.strip()
