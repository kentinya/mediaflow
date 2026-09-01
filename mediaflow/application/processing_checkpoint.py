"""Application projection for durable per-item processing checkpoints."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

from mediaflow.domain.configuration_management import RuntimeSnapshotUnavailable
from mediaflow.domain.manual_safety import redact_evidence_text
from mediaflow.domain.processing_checkpoint import (
    CheckpointAction,
    CheckpointAudit,
    CheckpointBlocker,
    CheckpointConfiguration,
    CheckpointResult,
    CheckpointStage,
    EffectCertainty,
    ErrorCategory,
    ProcessingCheckpoint,
    ProcessingCheckpointContext,
    RetrySafety,
)
from mediaflow.domain.task_persistence import TaskItemStatus

_RAW_STAGE_MAP: dict[str, CheckpointStage] = {
    "pipeline": CheckpointStage.SCANNING,
    "scanned": CheckpointStage.SCANNING,
    "lock": CheckpointStage.STORAGE,
    "strategy": CheckpointStage.RECOGNITION,
    "waiting_confirm": CheckpointStage.WAITING_CONFIRM,
    "waiting_recognition": CheckpointStage.WAITING_RECOGNITION,
    "waiting_metadata": CheckpointStage.WAITING_METADATA,
    "waiting_metadata_correction": CheckpointStage.WAITING_METADATA_CORRECTION,
    "waiting_classification": CheckpointStage.WAITING_CLASSIFICATION,
    "paused": CheckpointStage.PAUSED,
    "cancelled": CheckpointStage.CANCELLED,
    "completed": CheckpointStage.COMPLETED,
    "failed": CheckpointStage.FAILED,
    "ignored_by_operator": CheckpointStage.IGNORED,
}

_WAITING_STATUS_TO_KIND = {
    TaskItemStatus.WAITING_CONFIRM: "conflict",
    TaskItemStatus.WAITING_RECOGNITION: "recognition",
    TaskItemStatus.WAITING_METADATA: "metadata",
    TaskItemStatus.WAITING_METADATA_CORRECTION: "metadata_correction",
    TaskItemStatus.WAITING_CLASSIFICATION: "classification",
}

_BLOCKER_PRIORITY = ("conflict", "recognition", "metadata", "metadata_correction", "classification")
_SNAPSHOT_REASONS = {
    "active_missing",
    "active_unreadable",
    "digest_corrupt",
    "job_snapshot_incomplete",
    "job_snapshot_missing",
    "runtime_invalid",
    "schema_unsupported",
    "snapshot_digest_mismatch",
    "snapshot_missing",
    "snapshot_not_published",
    "snapshot_unreadable",
}


class ProcessingCheckpointService:
    """Build one bounded, side-effect-free checkpoint for an existing TaskItem."""

    def __init__(self, repository, *, snapshot_validator: Callable[[str, str], None] | None = None):
        self._repository = repository
        self._snapshot_validator = snapshot_validator

    def get(
        self,
        item_id: str,
        *,
        task_id: str | None = None,
        result_limit: int = 32,
        audit_limit: int = 64,
    ) -> ProcessingCheckpoint:
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError("TaskItem ID is required")
        if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
            raise ValueError("Task ID is required")
        context = self._context(item_id, result_limit=result_limit, audit_limit=audit_limit)
        if context is None or (task_id is not None and context.item.task_id != task_id):
            # Keep unknown IDs and cross-Task IDs indistinguishable at the transport boundary.
            raise LookupError("TaskItem was not found")
        return self._project(context)

    project = get

    def summary(self, item_id: str, *, task_id: str | None = None) -> dict[str, object]:
        return self.get(item_id, task_id=task_id).summary()

    def _context(
        self, item_id: str, *, result_limit: int, audit_limit: int
    ) -> ProcessingCheckpointContext | None:
        if (
            isinstance(result_limit, bool)
            or not isinstance(result_limit, int)
            or not 1 <= result_limit <= 100
        ):
            raise ValueError("checkpoint result limit must be between 1 and 100")
        if (
            isinstance(audit_limit, bool)
            or not isinstance(audit_limit, int)
            or not 1 <= audit_limit <= 200
        ):
            raise ValueError("checkpoint audit limit must be between 1 and 200")
        reader = getattr(self._repository, "get_processing_checkpoint_context", None)
        if callable(reader):
            return reader(item_id, result_limit=result_limit, audit_limit=audit_limit)
        return self._fallback_context(item_id, result_limit=result_limit, audit_limit=audit_limit)

    def _fallback_context(
        self, item_id: str, *, result_limit: int, audit_limit: int
    ) -> ProcessingCheckpointContext | None:
        item = self._repository.get_item(item_id)
        if item is None:
            return None
        task = self._repository.get_task(item.task_id)
        if task is None:
            return None
        list_for_item = getattr(self._repository, "list_results_for_item", None)
        if callable(list_for_item):
            results = tuple(list_for_item(item_id, limit=result_limit))
        else:
            results = tuple(
                value
                for value in self._repository.list_results(item.task_id, limit=result_limit)
                if value.item_id == item_id
            )
        blockers: list[CheckpointBlocker] = []
        review_specs = (
            ("recognition", "get_recognition_review_for_item", "/api/v1/recognition-reviews/"),
            ("metadata", "get_metadata_review_for_item", "/api/v1/metadata-reviews/"),
            (
                "metadata_correction",
                "get_metadata_correction_for_item",
                "/api/v1/metadata-corrections/",
            ),
            (
                "classification",
                "get_classification_review_for_item",
                "/api/v1/classification-reviews/",
            ),
        )
        for kind, method_name, path_prefix in review_specs:
            getter = getattr(self._repository, method_name, None)
            review = getter(item_id) if callable(getter) else None
            if review is not None:
                blockers.append(
                    CheckpointBlocker(
                        kind,
                        review.review_id,
                        _enum_value(review.status),
                        review.task_id,
                        review.item_id,
                        path_prefix + review.review_id,
                    )
                )
        confirmations = getattr(self._repository, "list_confirmations", None)
        if callable(confirmations):
            for confirmation in confirmations(limit=100):
                if confirmation.item_id == item_id:
                    blockers.append(
                        CheckpointBlocker(
                            "conflict",
                            confirmation.confirmation_id,
                            _enum_value(confirmation.status),
                            confirmation.task_id,
                            confirmation.item_id,
                            "/api/v1/confirmations/" + confirmation.confirmation_id,
                        )
                    )
        audits: list[CheckpointAudit] = []
        audit_specs = (
            ("task_retry", "list_task_retry_audit"),
            ("recognition_retry", "list_recognition_retry_audit"),
            ("manual_ignore", "list_manual_ignore_audit"),
        )
        for kind, method_name in audit_specs:
            getter = getattr(self._repository, method_name, None)
            if not callable(getter):
                continue
            for value in getter(item_id):
                audits.append(
                    CheckpointAudit(
                        value.decision_id,
                        kind,
                        value.decided_at,
                        getattr(value, "actor", None),
                    )
                )
        review_audit_specs = (
            (
                "recognition_review",
                "get_recognition_review_for_item",
                "list_recognition_review_audit",
            ),
            ("metadata_review", "get_metadata_review_for_item", "list_metadata_review_audit"),
            (
                "metadata_correction",
                "get_metadata_correction_for_item",
                "list_metadata_correction_audit",
            ),
            (
                "classification_review",
                "get_classification_review_for_item",
                "list_classification_review_audit",
            ),
        )
        for kind, review_method, audit_method in review_audit_specs:
            review_getter = getattr(self._repository, review_method, None)
            audit_getter = getattr(self._repository, audit_method, None)
            review = review_getter(item_id) if callable(review_getter) else None
            if review is None or not callable(audit_getter):
                continue
            for value in audit_getter(review.review_id):
                audits.append(
                    CheckpointAudit(
                        value.audit_id,
                        kind,
                        value.decided_at,
                        getattr(value, "actor", None),
                    )
                )
        confirmation_getter = getattr(self._repository, "list_confirmations", None)
        confirmation_audit_getter = getattr(self._repository, "list_confirmation_audit", None)
        if callable(confirmation_getter) and callable(confirmation_audit_getter):
            for confirmation in confirmation_getter(limit=100):
                if confirmation.item_id != item_id:
                    continue
                for value in confirmation_audit_getter(confirmation.confirmation_id):
                    audits.append(
                        CheckpointAudit(
                            value.audit_id,
                            "conflict_decision",
                            value.decided_at,
                            getattr(value, "actor", None),
                        )
                    )
        audits.sort(key=lambda value: (value.occurred_at, value.audit_id))
        request_reader = getattr(self._repository, "list_recovery_requests", None)
        recovery_requests = (
            tuple(request_reader(item_id, limit=32)) if callable(request_reader) else ()
        )
        audits.extend(
            CheckpointAudit(
                value.request_id,
                "recovery_request",
                value.requested_at,
                value.actor,
            )
            for value in recovery_requests
        )
        continuation_reader = getattr(self._repository, "list_recovery_continuations", None)
        recovery_continuations = (
            tuple(continuation_reader(item_id, limit=32)) if callable(continuation_reader) else ()
        )
        audits.sort(key=lambda value: (value.occurred_at, value.audit_id))
        return ProcessingCheckpointContext(
            task=task,
            item=item,
            results=results,
            blockers=tuple(blockers),
            audits=tuple(audits[-audit_limit:]),
            recovery_requests=recovery_requests,
            recovery_continuations=recovery_continuations,
        )

    def _project(self, context: ProcessingCheckpointContext) -> ProcessingCheckpoint:
        task = context.task
        item = context.item
        item_status = _item_status(item.status)
        stage = _stage(item_status, item.stage)
        results = tuple(
            sorted(
                (self._result(value) for value in context.results),
                key=lambda value: (value.created_at, value.result_id),
                reverse=True,
            )
        )
        blockers = tuple(_safe_blocker(value) for value in context.blockers)
        audits = tuple(_safe_audit(value) for value in context.audits)
        recovery_requests = tuple(
            _safe_recovery_request(value) for value in context.recovery_requests
        )
        recovery_continuations = tuple(
            _safe_recovery_continuation(value) for value in context.recovery_continuations
        )
        active_request = next(
            (value for value in reversed(recovery_requests) if value.active), None
        )
        current_continuation = recovery_continuations[0] if recovery_continuations else None
        latest = results[0] if results else None
        prior = results[1:]
        certainty = latest.effect_certainty if latest else EffectCertainty.UNKNOWN
        completed = latest.completed_operations if latest else ()
        uncertain = latest.uncertain_effects if latest else ()
        error_category = _error_category(item_status, item.stage, latest)
        blocker = _select_blocker(item_status, blockers)
        configuration = self._configuration(
            task.configuration_snapshot_id, task.configuration_snapshot_digest
        )
        retry_safety, actions, refusal = _actions(
            item_status,
            stage,
            certainty,
            blocker,
            configuration.resolvable,
            raw_stage=_bounded(item.stage),
            recovery_request=active_request,
            recovery_continuation=current_continuation,
        )
        payload = {
            "task_id": item.task_id,
            "item_id": item.item_id,
            "status": item_status.value,
            "raw_stage": _bounded(item.stage),
            "stage": stage.value,
            "attempts": item.attempts,
            "source_storage_id": _bounded(item.storage_id),
            "resource_library_id": _bounded(item.resource_library_id),
            "source_path": _safe_path(item.source_path),
            "plan_id": _bounded(item.plan_id),
            "destination_storage_id": _bounded(item.destination_storage_id),
            "destination_path": _safe_path(item.destination_path),
            "configuration": {
                "snapshot_id": _bounded(configuration.snapshot_id),
                "snapshot_digest": _bounded(configuration.snapshot_digest),
                "resolvable": configuration.resolvable,
                "reason": configuration.reason,
            },
            "results": [self._result_payload(value) for value in results],
            "blockers": [self._blocker_payload(value) for value in blockers],
            "audits": [
                {
                    "audit_id": _bounded(value.audit_id),
                    "kind": _bounded(value.kind),
                    "occurred_at": value.occurred_at.isoformat(),
                    "actor": _bounded(value.actor),
                }
                for value in audits
            ],
            "recovery_requests": [value.document() for value in recovery_requests],
            "recovery_continuation": (
                current_continuation.document() if current_continuation is not None else None
            ),
        }
        checkpoint_version = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return ProcessingCheckpoint(
            task_id=item.task_id,
            item_id=item.item_id,
            status=item_status.value,
            raw_stage=_bounded(item.stage),
            stage=stage,
            attempts=item.attempts,
            source_storage_id=_bounded(item.storage_id),
            resource_library_id=_bounded(item.resource_library_id),
            source_path=_safe_path(item.source_path),
            plan_id=_bounded(item.plan_id),
            destination_storage_id=_bounded(item.destination_storage_id),
            destination_path=_safe_path(item.destination_path),
            configuration=configuration,
            latest_result=latest,
            prior_results=prior,
            blockers=blockers,
            blocker=blocker,
            audits=audits,
            recovery_requests=recovery_requests,
            recovery_continuation=current_continuation,
            effect_certainty=certainty,
            completed_operations=tuple(_bounded(value, 128) for value in completed),
            uncertain_effects=tuple(_bounded(value, 128) for value in uncertain),
            error_category=error_category,
            retry_safety=retry_safety,
            actions=actions,
            refusal_reason=refusal,
            checkpoint_version=checkpoint_version,
            updated_at=item.updated_at,
        )

    def _configuration(
        self, snapshot_id: str | None, digest: str | None
    ) -> CheckpointConfiguration:
        if not snapshot_id or not digest:
            return CheckpointConfiguration(snapshot_id, digest, False, "snapshot_missing")
        if self._snapshot_validator is None:
            return CheckpointConfiguration(snapshot_id, digest, None, "not_checked")
        try:
            self._snapshot_validator(snapshot_id, digest)
        except RuntimeSnapshotUnavailable as error:
            reason = (
                error.reason
                if isinstance(error.reason, str) and error.reason in _SNAPSHOT_REASONS
                else "snapshot_unreadable"
            )
            return CheckpointConfiguration(snapshot_id, digest, False, reason)
        except (LookupError, ValueError):
            return CheckpointConfiguration(snapshot_id, digest, False, "snapshot_unreadable")
        except Exception:
            # The projection is a read path; a validator failure is evidence of unavailable
            # configuration, never a reason to substitute the current Active revision.
            return CheckpointConfiguration(snapshot_id, digest, False, "snapshot_unreadable")
        return CheckpointConfiguration(snapshot_id, digest, True, None)

    @staticmethod
    def _result(value) -> CheckpointResult:
        certainty = _certainty(getattr(value, "effect_certainty", EffectCertainty.UNKNOWN))
        return CheckpointResult(
            result_id=_bounded(value.result_id),
            status=_bounded(value.status),
            created_at=value.created_at,
            recognition_type=_bounded(value.recognition_type),
            provider=_bounded(value.provider),
            provider_id=_bounded(value.provider_id),
            metadata_policy_id=_bounded(value.metadata_policy_id),
            naming_policy_id=_bounded(value.naming_policy_id),
            classification_policy_id=_bounded(value.classification_policy_id),
            organize_policy_id=_bounded(value.organize_policy_id),
            operation=_bounded(value.operation),
            destination_storage_id=_bounded(value.destination_storage_id),
            destination_path=_safe_path(value.destination_path),
            completed_operations=tuple(_safe_effect(item) for item in value.completed_operations),
            effect_certainty=certainty,
            uncertain_effects=tuple(
                _safe_effect(item) for item in getattr(value, "uncertain_effects", ())
            ),
            error_category=_result_error_category(value, certainty),
            retry_attempts=value.retry_attempts,
            cleanup_status=_bounded(value.cleanup_status),
        )

    @staticmethod
    def _result_payload(value: CheckpointResult) -> dict[str, object]:
        return {
            "result_id": value.result_id,
            "status": value.status,
            "created_at": value.created_at.isoformat(),
            "recognition_type": value.recognition_type,
            "provider": value.provider,
            "provider_id": value.provider_id,
            "metadata_policy_id": value.metadata_policy_id,
            "naming_policy_id": value.naming_policy_id,
            "classification_policy_id": value.classification_policy_id,
            "organize_policy_id": value.organize_policy_id,
            "effect_certainty": value.effect_certainty.value,
            "uncertain_effects": list(value.uncertain_effects),
            "error_category": value.error_category.value,
            "operation": value.operation,
            "destination_storage_id": value.destination_storage_id,
            "destination_path": value.destination_path,
            "completed_operations": list(value.completed_operations),
            "retry_attempts": value.retry_attempts,
            "cleanup_status": value.cleanup_status,
        }

    @staticmethod
    def _blocker_payload(value: CheckpointBlocker) -> dict[str, object]:
        return {
            "kind": value.kind,
            "id": value.blocker_id,
            "status": value.status,
            "task_id": value.task_id,
            "item_id": value.item_id,
            "resolution_path": value.resolution_path,
        }


# Explicit aliases make the service easy to discover while keeping one projection implementation.
CheckpointProjectionService = ProcessingCheckpointService


def _enum_value(value) -> str:
    return str(getattr(value, "value", value))


def _item_status(value) -> TaskItemStatus:
    try:
        return value if isinstance(value, TaskItemStatus) else TaskItemStatus(_enum_value(value))
    except ValueError:
        # Malformed legacy data remains non-actionable instead of acquiring an unsafe retry.
        return TaskItemStatus.PROCESSING


def _bounded(value, limit: int = 4096):
    if value is None:
        return None
    text = str(value)
    return text[:limit]


def _safe_path(value) -> str | None:
    text = _bounded(value)
    if text is None:
        return None
    text = redact_evidence_text(text)
    if text.startswith(("/", "\\")) or "\\" in text or "\x00" in text:
        return "[absolute path redacted]"
    return text


def _safe_effect(value) -> str:
    text = _bounded(value, 128)
    if text is None:
        return "[unavailable]"
    text = redact_evidence_text(text)
    if "/" in text or "\\" in text or "\x00" in text:
        return "[path redacted]"
    return text


def _safe_identifier(value) -> str:
    text = _bounded(value, 256)
    if text is None:
        return "[unavailable]"
    if "/" in text or "\\" in text or "\x00" in text:
        return "[redacted]"
    return text


def _safe_blocker(value: CheckpointBlocker) -> CheckpointBlocker:
    blocker_id = _safe_identifier(value.blocker_id)
    return CheckpointBlocker(
        _safe_identifier(value.kind),
        blocker_id,
        _safe_identifier(value.status),
        _safe_identifier(value.task_id),
        _safe_identifier(value.item_id),
        "/api/v1/"
        + {
            "recognition": "recognition-reviews/",
            "metadata": "metadata-reviews/",
            "metadata_correction": "metadata-corrections/",
            "classification": "classification-reviews/",
            "conflict": "confirmations/",
        }.get(value.kind, "checkpoints/")
        + blocker_id,
    )


def _safe_audit(value: CheckpointAudit) -> CheckpointAudit:
    return CheckpointAudit(
        _safe_identifier(value.audit_id),
        _safe_identifier(value.kind),
        value.occurred_at,
        _bounded(value.actor, 256),
    )


def _safe_recovery_request(value):
    """Keep request projection bounded and path/secret-safe at the read boundary."""

    from dataclasses import replace

    request = replace(
        value,
        request_id=_safe_identifier(value.request_id),
        task_id=_safe_identifier(value.task_id),
        item_id=_safe_identifier(value.item_id),
        action_id=_safe_identifier(value.action_id),
        checkpoint_version=_safe_identifier(value.checkpoint_version),
        source_storage_id=_safe_identifier(value.source_storage_id),
        source_path=_safe_path(value.source_path) or "[unavailable]",
        configuration_snapshot_id=(
            _safe_identifier(value.configuration_snapshot_id)
            if value.configuration_snapshot_id is not None
            else None
        ),
        configuration_snapshot_digest=(
            _safe_identifier(value.configuration_snapshot_digest)
            if value.configuration_snapshot_digest is not None
            else None
        ),
        actor=_bounded(value.actor, 256),
        note=_bounded(value.note, 500),
        authority_statement=_bounded(value.authority_statement, 256),
        next_action=_bounded(value.next_action, 256),
        review_kind=_safe_identifier(value.review_kind) if value.review_kind is not None else None,
        review_id=_safe_identifier(value.review_id) if value.review_id is not None else None,
    )
    return request


def _safe_recovery_continuation(value):
    """Keep continuation projection bounded and path/secret-safe at the read boundary."""

    from dataclasses import replace

    return replace(
        value,
        continuation_id=_safe_identifier(value.continuation_id),
        request_id=_safe_identifier(value.request_id),
        source_task_id=_safe_identifier(value.source_task_id),
        source_item_id=_safe_identifier(value.source_item_id),
        checkpoint_version=_safe_identifier(value.checkpoint_version),
        configuration_snapshot_id=(
            _safe_identifier(value.configuration_snapshot_id)
            if value.configuration_snapshot_id is not None
            else None
        ),
        configuration_snapshot_digest=(
            _safe_identifier(value.configuration_snapshot_digest)
            if value.configuration_snapshot_digest is not None
            else None
        ),
        boundary=_bounded(value.boundary, 256),
        actor=_bounded(value.actor, 256),
        job_id=_safe_identifier(value.job_id),
        new_task_id=_safe_identifier(value.new_task_id) if value.new_task_id else None,
        new_result_id=_safe_identifier(value.new_result_id) if value.new_result_id else None,
        error=_bounded(value.error, 512),
        recovery=_bounded(value.recovery, 512),
        authority_statement=_bounded(value.authority_statement, 256),
    )


def _certainty(value) -> EffectCertainty:
    try:
        return EffectCertainty(_enum_value(value))
    except ValueError:
        return EffectCertainty.UNKNOWN


def _stage(status: TaskItemStatus, raw_stage: str) -> CheckpointStage:
    status = _item_status(status)
    if status is TaskItemStatus.PENDING:
        return CheckpointStage.QUEUED
    if status is TaskItemStatus.PROCESSING:
        mapped = _RAW_STAGE_MAP.get(raw_stage)
        if mapped is not None:
            return mapped
        if raw_stage.endswith("_resolved") or raw_stage.endswith("_retry_requested"):
            return CheckpointStage.PROCESSING
        return CheckpointStage.PROCESSING
    if status in {TaskItemStatus.DRY_RUN, TaskItemStatus.SUCCESS, TaskItemStatus.SKIPPED}:
        return CheckpointStage.COMPLETED
    if status is TaskItemStatus.PARTIAL or status is TaskItemStatus.FAILED:
        return CheckpointStage.FAILED
    if status is TaskItemStatus.CANCELLED:
        return CheckpointStage.CANCELLED
    if status is TaskItemStatus.PAUSED:
        return CheckpointStage.PAUSED
    if status is TaskItemStatus.IGNORED:
        return CheckpointStage.IGNORED
    waiting = _WAITING_STATUS_TO_KIND.get(status)
    if waiting:
        return {
            "conflict": CheckpointStage.WAITING_CONFIRM,
            "recognition": CheckpointStage.WAITING_RECOGNITION,
            "metadata": CheckpointStage.WAITING_METADATA,
            "metadata_correction": CheckpointStage.WAITING_METADATA_CORRECTION,
            "classification": CheckpointStage.WAITING_CLASSIFICATION,
        }[waiting]
    return _RAW_STAGE_MAP.get(raw_stage, CheckpointStage.UNKNOWN)


def _select_blocker(
    status: TaskItemStatus, blockers: tuple[CheckpointBlocker, ...]
) -> CheckpointBlocker | None:
    status = _item_status(status)
    expected = _WAITING_STATUS_TO_KIND.get(status)
    if expected:
        matching = [
            value for value in blockers if value.kind == expected and value.status == "pending"
        ]
        if matching:
            return matching[0]
    pending = [value for value in blockers if value.status == "pending"]
    if pending:
        return min(
            pending,
            key=lambda value: (
                _BLOCKER_PRIORITY.index(value.kind)
                if value.kind in _BLOCKER_PRIORITY
                else len(_BLOCKER_PRIORITY),
                value.blocker_id,
            ),
        )
    return None


def _result_error_category(value, certainty: EffectCertainty) -> ErrorCategory:
    retry_category = str(getattr(value, "retry_category", "") or "")
    if retry_category == "timeout":
        return ErrorCategory.TIMEOUT
    if retry_category in {"connection", "rate_limited", "provider_unavailable"}:
        return ErrorCategory.TRANSFER
    if certainty is EffectCertainty.ATTEMPTED_UNVERIFIED:
        return ErrorCategory.TRANSFER
    status = str(getattr(value, "status", "")).upper()
    if status in {"FAILED", "PARTIAL"}:
        return ErrorCategory.UNKNOWN
    return ErrorCategory.NONE


def _error_category(
    status: TaskItemStatus, raw_stage: str, latest: CheckpointResult | None
) -> ErrorCategory:
    status = _item_status(status)
    if status not in {TaskItemStatus.FAILED, TaskItemStatus.PARTIAL}:
        return ErrorCategory.NONE
    if latest is not None and latest.error_category is not ErrorCategory.NONE:
        return latest.error_category
    mapped = _RAW_STAGE_MAP.get(raw_stage)
    return {
        CheckpointStage.STORAGE: ErrorCategory.STORAGE,
        CheckpointStage.RECOGNITION: ErrorCategory.RECOGNITION,
        CheckpointStage.METADATA: ErrorCategory.METADATA,
        CheckpointStage.CLASSIFICATION: ErrorCategory.CLASSIFICATION,
        CheckpointStage.PARSING: ErrorCategory.PARSE,
    }.get(mapped, ErrorCategory.UNKNOWN)


def _actions(
    status: TaskItemStatus,
    stage: CheckpointStage,
    certainty: EffectCertainty,
    blocker: CheckpointBlocker | None,
    snapshot_resolvable: bool | None,
    *,
    raw_stage: str = "",
    recovery_request=None,
    recovery_continuation=None,
) -> tuple[RetrySafety, tuple[CheckpointAction, ...], str | None]:
    status = _item_status(status)
    if status in {
        TaskItemStatus.SUCCESS,
        TaskItemStatus.DRY_RUN,
        TaskItemStatus.SKIPPED,
        TaskItemStatus.IGNORED,
    }:
        reason = "replay_not_offered: item has a terminal outcome"
        if status is TaskItemStatus.DRY_RUN:
            reason = "replay_not_offered: DryRun produced no mutation and is already recorded"
        return RetrySafety.UNSAFE, (), reason
    if blocker is not None:
        action = CheckpointAction(
            f"resolve_{blocker.kind}",
            f"Resolve {blocker.kind.replace('_', ' ')} review",
            True,
            "review_decision",
            blocker.resolution_path,
            False,
        )
        if blocker.kind in {"recognition", "metadata", "metadata_correction"}:
            ignore = CheckpointAction(
                "ignore",
                "Ignore item",
                True,
                "review_decision",
                None,
                True,
            )
            return RetrySafety.UNSAFE, (action, ignore), None
        return RetrySafety.UNSAFE, (action,), None
    if raw_stage == "admission_interrupted":
        return (
            RetrySafety.UNSAFE,
            (CheckpointAction("investigate", "Investigate interrupted admission", False, "none"),),
            "manual_execution_reconciliation_required: exact authority was consumed before "
            "the execution state was published",
        )
    if certainty in {EffectCertainty.ATTEMPTED_UNVERIFIED, EffectCertainty.UNKNOWN}:
        return (
            RetrySafety.UNKNOWN,
            (CheckpointAction("investigate", "Investigate effect state", False, "none"),),
            "automatic_replay_refused: effect certainty is not verified",
        )
    if status is TaskItemStatus.FAILED and certainty is EffectCertainty.NONE:
        if snapshot_resolvable is not True:
            reason = (
                "automatic_replay_refused: pinned configuration is unavailable"
                if snapshot_resolvable is False
                else "automatic_replay_refused: pinned configuration is not validated"
            )
            return (
                RetrySafety.UNSAFE,
                (
                    CheckpointAction(
                        "investigate",
                        "Inspect unavailable configuration",
                        False,
                        "none",
                        None,
                        False,
                    ),
                ),
                reason,
            )
        return (
            RetrySafety.SAFE,
            (CheckpointAction("retry", "Retry safe analysis", True, "task_recovery", None, True),),
            None,
        )
    if status is TaskItemStatus.PENDING and raw_stage == "task_retry_requested":
        if recovery_request is not None and recovery_request.active:
            if recovery_continuation is not None and recovery_continuation.active:
                return (
                    RetrySafety.UNKNOWN,
                    (),
                    "continuation_in_flight: the admitted recovery request is already "
                    "continued; wait for it to reach a terminal state",
                )
            return (
                RetrySafety.UNKNOWN,
                (
                    CheckpointAction(
                        "continue",
                        "Continue safe analysis",
                        True,
                        "task_recovery",
                        None,
                        True,
                    ),
                ),
                None,
            )
        if snapshot_resolvable is not True:
            reason = (
                "automatic_replay_refused: pinned configuration is unavailable"
                if snapshot_resolvable is False
                else "automatic_replay_refused: pinned configuration is not validated"
            )
            return (
                RetrySafety.UNSAFE,
                (
                    CheckpointAction(
                        "investigate",
                        "Inspect unavailable configuration",
                        False,
                        "none",
                        None,
                        False,
                    ),
                ),
                reason,
            )
        return (
            RetrySafety.SAFE,
            (CheckpointAction("retry", "Retry safe analysis", True, "task_recovery", None, True),),
            None,
        )
    if status is TaskItemStatus.PAUSED:
        return (
            RetrySafety.UNKNOWN,
            (
                CheckpointAction(
                    "resume", "Resume from checkpoint", True, "task_recovery", None, False
                ),
            ),
            None,
        )
    return (
        RetrySafety.UNKNOWN,
        (
            CheckpointAction(
                "investigate", "Investigate current checkpoint", False, "none", None, False
            ),
        ),
        "recovery_action_refused: current stage has no verified safe continuation",
    )
