"""Exact one-shot continuation authority for a manual Organize recovery item.

The service keeps the original manual TaskItem as the durable anchor while a
completed single-item re-analysis (DryRun) proves that the current source can be
planned again.  It then creates a fresh exact Preview on the original manual
intent and consumes the existing one-shot manual execution authorization path.
The resulting link is persisted beside the original TaskItem so API and Web can
return to the original Organize journey after reload.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.recovery_decisions import collect_resolved_continuation_decisions
from mediaflow.domain.manual_execution import (
    MANUAL_EXECUTION_PERMISSION,
    ManualExecution,
    ManualExecutionAuthorizationStatus,
    ManualExecutionError,
)
from mediaflow.domain.manual_organize import ManualIntentStatus
from mediaflow.domain.manual_organize_preview import ManualPreviewItemStatus
from mediaflow.domain.manual_recovery import (
    ManualRecoveryLink,
    ManualRecoveryLinkStatus,
    ManualRecoveryPreparation,
    ManualRecoveryPreparationStatus,
)
from mediaflow.domain.metadata import MediaIdentity, MediaType
from mediaflow.domain.recovery_continuation import RecoveryContinuationStatus
from mediaflow.domain.task_persistence import TaskItemStatus


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


@dataclass(frozen=True)
class PreparedContinuation:
    """The shared, non-authorizing preparation of one recovery item.

    It carries exactly the durable evidence both the read-only summary and the
    later explicit confirmation need: the original checkpoint/continuation, the
    completed linked re-analysis, the original manual execution item and its
    open intent item, and the freshly created exact zero-mutation Preview.
    Creating it never mints, consumes or stores execution authority.
    """

    checkpoint: object
    continuation: object
    manual_item: object
    intent: object
    intent_item: object
    preview: object
    preview_item: object


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

    def authorize_continued(
        self,
        source_task_id: str,
        source_item_id: str,
        *,
        expected_checkpoint_version: str,
        actor: str,
        permission: str = MANUAL_EXECUTION_PERMISSION,
        confirmation: bool = False,
        allow_overwrite: bool = False,
        allow_source_cleanup: bool = False,
        ttl_seconds: int | None = None,
        note: str | None = None,
    ) -> ManualRecoveryLink:
        """Create a fresh exact Preview and one-shot authority after analysis."""

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
        # A live or already-consumed link is the durable answer for this source
        # item; resolving it before any fresh Preview avoids minting a plan the
        # operator did not ask for.
        existing = self._repository.get_manual_recovery_link_by_source(
            source_task_id, source_item_id
        )
        reacquire_stale_link = False
        if existing is not None:
            authorization = self._execution.get_authorization(existing.authorization_id)
            if authorization.status is ManualExecutionAuthorizationStatus.ACTIVE:
                return existing
            if authorization.status is ManualExecutionAuthorizationStatus.CONSUMED:
                if authorization.execution_id is not None:
                    return replace(
                        existing,
                        status=ManualRecoveryLinkStatus.CONSUMED,
                        execution_id=authorization.execution_id,
                        updated_at=authorization.consumed_at or self._clock(),
                    )
                raise ManualRecoveryContinuationError(
                    "the continued manual execution authorization is already consumed",
                    code="authorization_consumed",
                )
            # An expired or revoked one-shot authority never executed, so the item may
            # acquire a fresh bounded authority once every gate below still passes.
            self._repository.mark_manual_recovery_link_stale(existing.link_id, now=self._clock())
            reacquire_stale_link = True
        prepared = self._prepare_continuation(
            source_task_id,
            source_item_id,
            expected_checkpoint_version=expected_checkpoint_version,
            actor=actor,
        )
        continuation = prepared.continuation
        manual_item = prepared.manual_item
        intent = prepared.intent
        preview = prepared.preview
        preview_item = prepared.preview_item

        authority = self._execution.authorize(
            preview.preview_id,
            [manual_item.item_id],
            expected_intent_version=preview.intent_version,
            expected_item_versions={manual_item.item_id: preview_item.item_version},
            snapshot_id=preview.configuration_snapshot_id,
            snapshot_digest=preview.configuration_snapshot_digest,
            actor=actor,
            permission=permission,
            confirmation=True,
            allow_overwrite=allow_overwrite,
            allow_source_cleanup=allow_source_cleanup,
            ttl_seconds=ttl_seconds,
            note=note,
        )
        now = self._clock()
        if reacquire_stale_link:
            link = self._repository.supersede_manual_recovery_link(
                existing.link_id,
                analysis_continuation_id=continuation.continuation_id,
                analysis_task_id=continuation.new_task_id,
                analysis_result_id=continuation.new_result_id,
                intent_id=intent.intent_id,
                preview_id=preview.preview_id,
                authorization_id=authority.authorization_id,
                actor=actor,
                now=now,
            )
        else:
            link = ManualRecoveryLink(
                str(uuid4()),
                source_task_id,
                source_item_id,
                continuation.continuation_id,
                continuation.new_task_id,
                continuation.new_result_id,
                intent.intent_id,
                preview.preview_id,
                authority.authorization_id,
                actor,
                ManualRecoveryLinkStatus.AUTHORIZED,
                now,
                now,
            )
            self._repository.create_manual_recovery_link(link)
        return link

    def prepare_summary(
        self,
        source_task_id: str,
        source_item_id: str,
        *,
        expected_checkpoint_version: str,
        actor: str,
    ) -> ManualRecoveryPreparation:
        """Create one non-authorizing plan summary for a recovery item.

        This is the read/prepare half of the native same-interface recovery
        journey.  It re-validates the original item, the completed linked
        re-analysis and the open pinned intent, then publishes one exact
        zero-mutation Preview and records a durable summary.  It mints **no**
        execution authority, consumes none, and performs zero Storage mutation;
        the operator must still explicitly confirm a ready subset.
        """

        actor = self._actor(actor)
        prepared = self._prepare_continuation(
            source_task_id,
            source_item_id,
            expected_checkpoint_version=expected_checkpoint_version,
            actor=actor,
        )
        checkpoint = prepared.checkpoint
        continuation = prepared.continuation
        preview = prepared.preview
        preview_item = prepared.preview_item
        now = self._clock()
        previous = self._repository.get_current_manual_recovery_preparation(
            source_task_id, source_item_id
        )
        if previous is not None:
            self._repository.supersede_manual_recovery_preparation(previous.preparation_id, now=now)
        preparation = ManualRecoveryPreparation(
            str(uuid4()),
            source_task_id,
            source_item_id,
            continuation.continuation_id,
            continuation.new_task_id,
            continuation.new_result_id,
            prepared.intent.intent_id,
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
        return preparation

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

    def _prepare_continuation(
        self,
        source_task_id: str,
        source_item_id: str,
        *,
        expected_checkpoint_version: str,
        actor: str,
    ) -> PreparedContinuation:
        """Shared non-authorizing preparation of one recovery item.

        Both the read-only summary and the explicit one-shot authorization call
        this so they can never diverge on the original item, the linked
        re-analysis, the pinned open intent, the resolved decisions or the exact
        zero-mutation Preview.
        """

        checkpoint = self._checkpoint_service.get(source_item_id, task_id=source_task_id)
        if expected_checkpoint_version != checkpoint.checkpoint_version:
            raise ManualRecoveryContinuationError(
                "the manual recovery checkpoint version is stale",
                code="stale_checkpoint",
                details={
                    "currentCheckpointVersion": checkpoint.checkpoint_version,
                },
            )
        if checkpoint.raw_stage != "task_retry_requested":
            raise ManualRecoveryContinuationError(
                "the original manual item is not in the retry-requested recovery stage",
                code="recovery_stage_invalid",
                details={"rawStage": checkpoint.raw_stage},
            )
        if checkpoint.active_recovery_request is not None:
            raise ManualRecoveryContinuationError(
                "the original manual item still has an active recovery request",
                code="recovery_request_active",
            )
        continuation = checkpoint.recovery_continuation
        if (
            continuation is None
            or continuation.status is not RecoveryContinuationStatus.COMPLETED
            or not continuation.new_task_id
            or not continuation.new_result_id
        ):
            raise ManualRecoveryContinuationError(
                "no completed linked single-item re-analysis exists for this item",
                code="analysis_not_completed",
                next_action=(
                    "continue the admitted recovery as a DryRun and wait for the Worker, "
                    "then return here"
                ),
            )
        analysis_task = self._repository.get_task(continuation.new_task_id)
        if analysis_task is None:
            raise ManualRecoveryContinuationError(
                "the linked re-analysis Task is unavailable",
                code="analysis_unavailable",
                status=503,
            )
        analysis_items = self._repository.list_items(analysis_task.task_id)
        analysis_results = self._repository.list_results(analysis_task.task_id)
        if len(analysis_items) != 1:
            raise ManualRecoveryContinuationError(
                "the linked re-analysis Task must contain exactly one item",
                code="analysis_scope_invalid",
            )
        analysis_item = analysis_items[0]
        analysis_result = next(
            (
                value
                for value in reversed(analysis_results)
                if value.item_id == analysis_item.item_id
            ),
            None,
        )
        # The durable identity the completed linked re-analysis resolved is a
        # reviewed fact about this exact source under this pin.  Reading it back
        # lets the summary reuse the plan without a second live Provider lookup;
        # it is only ever applied when it still matches the pinned policy.
        reuse_analysis_identity = self._reusable_analysis_identity(
            analysis_item.item_id, analysis_result
        )
        analysis_checkpoint = self._checkpoint_service.get(
            analysis_item.item_id, task_id=analysis_task.task_id
        )
        if analysis_checkpoint.blocker is not None or analysis_checkpoint.status in {
            "waiting_confirm",
            "waiting_recognition",
            "waiting_metadata",
            "waiting_metadata_correction",
            "waiting_classification",
        }:
            raise ManualRecoveryContinuationError(
                "the linked re-analysis item still requires a review or conflict decision",
                code="review_pending",
                next_action=(
                    "resolve the blocker on the linked TaskItem, then request a fresh "
                    "re-analysis and return here"
                ),
                details={
                    "analysisTaskId": analysis_task.task_id,
                    "analysisItemId": analysis_item.item_id,
                    "blockerKind": (
                        analysis_checkpoint.blocker.kind
                        if analysis_checkpoint.blocker is not None
                        else None
                    ),
                },
            )
        if (
            analysis_item.status is not TaskItemStatus.DRY_RUN
            or analysis_result is None
            or analysis_result.status != TaskItemStatus.DRY_RUN.value
            or analysis_result.error
            or analysis_item.source_path != checkpoint.source_path
            or analysis_item.storage_id != checkpoint.source_storage_id
            or analysis_task.configuration_snapshot_id != checkpoint.configuration.snapshot_id
            or analysis_task.configuration_snapshot_digest
            != checkpoint.configuration.snapshot_digest
        ):
            raise ManualRecoveryContinuationError(
                "the linked re-analysis did not produce one completed current DryRun plan",
                code="analysis_result_invalid",
                next_action=(
                    "open the linked Task/Result, resolve any blocker, and re-analyze "
                    "the exact item before continuing"
                ),
            )

        executions = self._repository.list_manual_executions_for_task_item(
            source_task_id, source_item_id
        )
        if len(executions) != 1:
            raise ManualRecoveryContinuationError(
                "the original TaskItem is not one exact manual Organize item",
                code="manual_item_not_found",
                status=404,
            )
        execution = executions[0]
        manual_item = next(
            (
                value
                for value in execution.items
                if value.task_item_id == source_item_id and value.task_id == source_task_id
            ),
            None,
        )
        if manual_item is None:
            raise ManualRecoveryContinuationError(
                "the original manual execution item is unavailable",
                code="manual_item_not_found",
                status=404,
            )
        intent = self._intents.get(execution.intent_id)
        if (
            intent.status is not ManualIntentStatus.OPEN
            or intent.snapshot_id != checkpoint.configuration.snapshot_id
            or intent.snapshot_digest != checkpoint.configuration.snapshot_digest
        ):
            raise ManualRecoveryContinuationError(
                "the original manual intent is no longer open under the pinned snapshot",
                code="intent_unavailable",
                next_action="create a fresh manual intent from the current FileIndex item",
            )
        intent_item = next(
            (value for value in intent.items if value.item_id == manual_item.item_id), None
        )
        if intent_item is None:
            raise ManualRecoveryContinuationError(
                "the original manual intent item is unavailable",
                code="manual_item_not_found",
                status=404,
            )
        # The fresh continuation Preview must consume the same resolved review and
        # conflict decisions the completed linked re-analysis consumed, otherwise a
        # decision that made the re-analysis succeed (for example a metadata
        # identity or a classification rule) is silently dropped and the Preview
        # blocks again on the same review.  The shared collector returns the newest
        # RESOLVED decisions for this source across the original item and its prior
        # single-item re-analysis items; the Preview binds them to this item's own
        # manual choice context and only applies them when they stay compatible.
        decisions = collect_resolved_continuation_decisions(
            self._repository,
            source_item_id=source_item_id,
        )
        # A linked Recognition decision may select a different RecognitionType
        # from the original manual intent.  The continuation authority is bound
        # to the original intent's downstream policy choice, so silently forcing
        # that old choice would execute a plan the linked re-analysis did not
        # review.  Fail closed until the operator creates a compatible manual
        # intent/Preview rather than mixing RecognitionType policy identities.
        recognition_decision = decisions.recognition_reviews.get(
            (checkpoint.source_storage_id, checkpoint.source_path)
        )
        if (
            recognition_decision is not None
            and recognition_decision.selected_recognition_type
            != manual_item.choice.recognition_type_id
        ):
            raise ManualRecoveryContinuationError(
                "the linked Recognition decision does not match the original manual choice",
                code="recognition_plan_mismatch",
                next_action=(
                    "create a fresh manual intent and Preview using the reviewed RecognitionType, "
                    "then continue that exact plan"
                ),
                details={
                    "reviewedRecognitionType": recognition_decision.selected_recognition_type,
                    "manualRecognitionType": manual_item.choice.recognition_type_id,
                },
            )
        preview = self._previews.create(
            intent.intent_id,
            [manual_item.item_id],
            expected_version=intent.version,
            expected_item_versions={manual_item.item_id: intent_item.version},
            snapshot_id=intent.snapshot_id,
            snapshot_digest=intent.snapshot_digest,
            actor=actor,
            review_decisions=decisions,
            reuse_analysis_identity=reuse_analysis_identity,
            require_durable_identity=True,
        )
        preview_item = next(
            (value for value in preview.items if value.item_id == manual_item.item_id), None
        )
        if (
            preview_item is None
            or preview_item.status is not ManualPreviewItemStatus.PREVIEWED
            or preview_item.plan is None
        ):
            raise ManualRecoveryContinuationError(
                "the fresh exact Preview for the original item is not executable",
                code="preview_blocked",
                next_action=(
                    "open the new Preview, repair the stated blocker, and request a "
                    "fresh current-source Preview before continuing"
                ),
                details={"previewId": preview.preview_id},
            )
        return PreparedContinuation(
            checkpoint=checkpoint,
            continuation=continuation,
            manual_item=manual_item,
            intent=intent,
            intent_item=intent_item,
            preview=preview,
            preview_item=preview_item,
        )

    def execute_continued(
        self,
        link_id: str,
        *,
        actor: str,
        permission: str = MANUAL_EXECUTION_PERMISSION,
        confirmation: bool = False,
    ) -> ManualRecoveryLink:
        """Execute the exact continued authority and persist its link outcome."""

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
        link = self._repository.get_manual_recovery_link(link_id)
        if link is None:
            raise ManualRecoveryContinuationError(
                "manual recovery link was not found",
                code="link_not_found",
                status=404,
            )
        if link.status is not ManualRecoveryLinkStatus.AUTHORIZED:
            raise ManualRecoveryContinuationError(
                "this continuation authority is not executable",
                code="authorization_not_active",
                next_action=link.next_action(),
            )
        authority = self._execution.get_authorization(link.authorization_id)
        if authority.status is not ManualExecutionAuthorizationStatus.ACTIVE:
            self._repository.mark_manual_recovery_link_stale(link.link_id, now=self._clock())
            raise ManualRecoveryContinuationError(
                "the continued manual execution authority is no longer active",
                code="authorization_inactive",
                next_action=(
                    "call the authorize-organize continuation route again to obtain a "
                    "fresh one-shot authority once the linked re-analysis and current "
                    "source evidence still hold"
                ),
            )
        try:
            run = self._execution.execute(
                authority.authorization_id,
                actor=actor,
                permission=permission,
                confirmation=True,
            )
        except Exception:
            current = self._execution.get_authorization(link.authorization_id)
            if (
                current.status is ManualExecutionAuthorizationStatus.CONSUMED
                and current.execution_id is not None
            ):
                return self._repository.complete_manual_recovery_link(
                    link.link_id,
                    execution_id=current.execution_id,
                    now=self._clock(),
                )
            raise
        return self._repository.complete_manual_recovery_link(
            link.link_id,
            execution_id=run.execution_id,
            now=self._clock(),
        )

    def discovery_for_source_item(
        self, source_task_id: str, source_item_id: str
    ) -> dict[str, object] | None:
        """Return the durable link projection for one original manual item."""

        link = self._repository.get_manual_recovery_link_by_source(source_task_id, source_item_id)
        if link is None:
            return None
        value = link.document()
        try:
            authorization = self._execution.get_authorization(link.authorization_id)
            value["authorization_status"] = authorization.status.value
            value["execution_id"] = value["execution_id"] or authorization.execution_id
            value["allow_overwrite"] = authorization.allow_overwrite
            value["allow_source_cleanup"] = authorization.allow_source_cleanup
            value["authorizationPath"] = (
                "/api/v1/manual-execution-authorizations/" + link.authorization_id
            )
        except Exception:
            pass
        return value

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
            return None
        value = preparation.document()
        value["hasExecutionAuthority"] = False
        return value

    def supports_source_item(self, source_task_id: str, source_item_id: str) -> bool:
        """Whether this exact item belongs to one persisted manual execution."""

        executions = self._repository.list_manual_executions_for_task_item(
            source_task_id, source_item_id
        )
        if len(executions) != 1:
            return False
        return any(
            item.task_id == source_task_id and item.task_item_id == source_item_id
            for item in executions[0].items
        )

    def _reusable_analysis_identity(self, analysis_item_id: str, analysis_result):
        """The durable identity one completed linked re-analysis resolved, if any.

        Preference order is the completed attempt's bounded pipeline evidence
        metadata section for the same item (the richest reviewed fact, including
        the classification-relevant facets), then the exact persisted Result
        identity.  A malformed or absent identity simply returns ``None`` so the
        caller blocks for a fresh analysis instead of inventing one.
        """

        reader = getattr(self._repository, "list_evidence_for_item", None)
        if callable(reader):
            try:
                evidence = tuple(reader(analysis_item_id, limit=16))
            except Exception:
                evidence = ()
            for value in evidence:
                section = getattr(value, "section", None)
                if not callable(section):
                    continue
                metadata = section("metadata")
                if metadata is None or not bool(getattr(metadata, "available", False)):
                    continue
                document = getattr(metadata, "value", None)
                identity = self._identity_from_document(document)
                if identity is not None:
                    return identity
        if analysis_result is not None:
            identity = self._identity_from_result(analysis_result)
            if identity is not None:
                return identity
        return None

    @staticmethod
    def _identity_from_result(result):
        provider = getattr(result, "provider", None)
        provider_id = getattr(result, "provider_id", None)
        recognition_type = getattr(result, "recognition_type", None)
        media_type = getattr(result, "media_type", None)
        title = getattr(result, "title", None)
        year = getattr(result, "year", None)
        return ManualRecoveryContinuationService._build_identity(
            provider, provider_id, media_type, title, year, recognition_type
        )

    @staticmethod
    def _identity_from_document(document):
        if not isinstance(document, dict):
            return None
        return ManualRecoveryContinuationService._build_identity(
            document.get("provider"),
            document.get("providerId"),
            document.get("mediaType"),
            document.get("title"),
            document.get("year"),
            document.get("recognitionTypeId"),
            original_title=document.get("originalTitle"),
            genres=document.get("genres"),
            countries=document.get("countries"),
            languages=document.get("languages"),
            season=document.get("season"),
            episode=document.get("episode"),
            episodes=document.get("episodes"),
        )

    @staticmethod
    def _build_identity(
        provider,
        provider_id,
        media_type,
        title,
        year,
        recognition_type,
        *,
        original_title=None,
        genres=None,
        countries=None,
        languages=None,
        season=None,
        episode=None,
        episodes=None,
    ):
        if not all(isinstance(value, str) and value for value in (provider, provider_id, title)):
            return None
        if not isinstance(media_type, str) or not media_type:
            return None

        def _text_tuple(value):
            if not isinstance(value, (list, tuple)):
                return ()
            return tuple(item for item in value if isinstance(item, str) and item)

        def _int(value):
            return value if isinstance(value, int) and not isinstance(value, bool) else None

        try:
            return MediaIdentity(
                provider=provider,
                provider_id=provider_id,
                media_type=MediaType(media_type),
                title=title,
                original_title=original_title if isinstance(original_title, str) else None,
                year=_int(year),
                season=_int(season),
                episode=_int(episode),
                episodes=tuple(
                    value
                    for value in (episodes or ())
                    if isinstance(value, int) and not isinstance(value, bool)
                ),
                genres=_text_tuple(genres),
                countries=_text_tuple(countries),
                languages=_text_tuple(languages),
                recognition_type_id=(
                    recognition_type if isinstance(recognition_type, str) else None
                ),
            )
        except ValueError:
            return None

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
