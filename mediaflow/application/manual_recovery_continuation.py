"""Exact one-shot continuation authority for a manual Organize recovery item.

The service keeps the original manual TaskItem as the durable anchor while a
completed single-item re-analysis (DryRun) proves that the current source can be
planned again.  It then creates a fresh exact Preview on the original manual
intent and consumes the existing one-shot manual execution authorization path.
The resulting link is persisted beside the original TaskItem so API and Web can
return to the original Organize journey after reload.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.recovery_decisions import collect_resolved_continuation_decisions
from mediaflow.domain.manual_execution import (
    MANUAL_EXECUTION_PERMISSION,
    ManualExecutionAuthorizationStatus,
    ManualExecutionError,
)
from mediaflow.domain.manual_organize import ManualIntentStatus
from mediaflow.domain.manual_organize_preview import ManualPreviewItemStatus
from mediaflow.domain.manual_recovery import (
    ManualRecoveryLink,
    ManualRecoveryLinkStatus,
)
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
            value["authorizationPath"] = (
                "/api/v1/manual-execution-authorizations/" + link.authorization_id
            )
        except Exception:
            pass
        return value

    @staticmethod
    def _actor(value: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ManualRecoveryContinuationError(
                "manual recovery actor is required",
                code="invalid_actor",
                status=403,
            )
        return value.strip()
