"""Exact reviewed-plan manual organization execution boundary.

This service owns admission and durable orchestration, while
``OrganizerExecutor`` remains the only component allowed to invoke mutating
Storage methods.  It never accepts a source path, destination or operation
from the request; those values are reconstructed from the persisted Preview
document and checked against the pinned runtime snapshot.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from uuid import uuid4

from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.domain.manual_execution import (
    MANUAL_EXECUTION_PERMISSION,
    MAX_MANUAL_EXECUTION_ITEMS,
    ManualExecution,
    ManualExecutionAuthorization,
    ManualExecutionAuthorizationAudit,
    ManualExecutionAuthorizationStatus,
    ManualExecutionEffect,
    ManualExecutionError,
    ManualExecutionItem,
    ManualExecutionItemStatus,
    ManualExecutionScopeItem,
    ManualExecutionStatus,
)
from mediaflow.domain.manual_safety import (
    contains_manual_secret,
    redact_manual_value,
    safe_manual_error,
)
from mediaflow.domain.metadata import MediaIdentity, MediaType
from mediaflow.domain.organizer import (
    AttachmentPlan,
    AttachmentType,
    DirectoryCleanupMode,
    DirectoryCleanupPolicy,
    ExecutionEffectCertainty,
    ExecutionResult,
    ExecutionStatus,
    OrganizeOperationType,
    OrganizePlan,
    PlanOperation,
    PlanStatus,
    RollbackPolicy,
    StorageLocation,
)
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTaskStatus,
    TaskItemStatus,
)

_MAX_TEXT = 512
_MAX_TTL_SECONDS = 900
_MAX_EFFECTS = 256


class ManualOrganizeExecutionService:
    """Authorize, admit and execute only the current exact Preview scope."""

    MAX_ITEMS = MAX_MANUAL_EXECUTION_ITEMS

    def __init__(
        self,
        repository,
        preview_service,
        intent_service=None,
        *,
        configuration_service=None,
        runtime_resolver=None,
        configuration=None,
        storages: Mapping[str, object] | None = None,
        storage_factory=None,
        executor: OrganizerExecutor | None = None,
        checkpoint_service: ProcessingCheckpointService | None = None,
        clock=lambda: datetime.now(UTC),
        maximum_ttl_seconds: int = _MAX_TTL_SECONDS,
        max_items: int = MAX_MANUAL_EXECUTION_ITEMS,
    ) -> None:
        if isinstance(maximum_ttl_seconds, bool) or not isinstance(maximum_ttl_seconds, int):
            raise ValueError("manual execution maximum TTL must be an integer")
        if not 1 <= maximum_ttl_seconds <= _MAX_TTL_SECONDS:
            raise ValueError("manual execution maximum TTL must be between 1 and 900 seconds")
        if isinstance(max_items, bool) or not 1 <= max_items <= MAX_MANUAL_EXECUTION_ITEMS:
            raise ValueError(
                f"manual execution item limit must be between 1 and {MAX_MANUAL_EXECUTION_ITEMS}"
            )
        self._repository = repository
        self._preview_service = preview_service
        self._intent_service = intent_service or getattr(preview_service, "_intent_service", None)
        self._configuration_service = configuration_service or getattr(
            preview_service, "_configuration_service", None
        )
        self._runtime_resolver = runtime_resolver or getattr(
            preview_service, "_runtime_resolver", None
        )
        self._configuration = configuration or getattr(preview_service, "_configuration", None)
        self._storages = dict(storages or getattr(preview_service, "_storages", {}) or {})
        self._storage_factory = storage_factory or getattr(
            preview_service, "_storage_factory", None
        )
        self._executor = executor or OrganizerExecutor()
        self._checkpoint_service = checkpoint_service or ProcessingCheckpointService(
            repository, snapshot_validator=self._validate_checkpoint_snapshot
        )
        self._clock = clock
        self._maximum_ttl_seconds = maximum_ttl_seconds
        self._max_items = max_items

    @property
    def repository(self):
        return self._repository

    def authorize(
        self,
        preview_id: str,
        item_ids: Sequence[str],
        *,
        expected_intent_version: int | None = None,
        expected_item_versions: Mapping[str, int] | Sequence[int] | None = None,
        snapshot_id: str | None = None,
        snapshot_digest: str | None = None,
        actor: str,
        permission: str = "execute_manual_organize",
        confirmation: bool,
        allow_overwrite: bool = False,
        allow_source_cleanup: bool = False,
        ttl_seconds: int | None = None,
        note: str | None = None,
    ) -> ManualExecutionAuthorization:
        actor = self._actor(actor)
        permission = self._permission(permission)
        self._require_confirmation(confirmation)
        self._require_bool(allow_overwrite, "allowOverwrite")
        self._require_bool(allow_source_cleanup, "allowSourceCleanup")
        ttl = self._ttl(ttl_seconds)
        if note is not None and (
            not isinstance(note, str)
            or not note.strip()
            or len(note) > _MAX_TEXT
            or "\x00" in note
            or contains_manual_secret(note)
        ):
            raise ManualExecutionError("execution note is invalid", code="invalid_note")
        preview = self._preview(preview_id)
        self._validate_preview_parent(preview, snapshot_id, snapshot_digest)
        intent = self._intent(preview.intent_id)
        if getattr(intent.status, "value", intent.status) != "open":
            raise ManualExecutionError(
                "the manual intent is not open",
                code="intent_not_open",
                next_action="create a new manual intent from current Files",
            )
        if expected_intent_version is not None:
            self._positive_version(expected_intent_version, "expectedVersion")
            if expected_intent_version != preview.intent_version:
                raise ManualExecutionError(
                    "the reviewed intent version is stale",
                    code="intent_stale",
                    next_action="reload the current Preview and request a fresh authorization",
                )
        selected = self._select_preview_items(preview, item_ids)
        versions = self._versions(selected, expected_item_versions)
        scopes: list[ManualExecutionScopeItem] = []
        for item in selected:
            if not item.current or item.status.value != "previewed" or item.plan is None:
                raise ManualExecutionError(
                    "a selected Preview item is not executable",
                    code="item_blocked",
                    next_action=item.next_action,
                    details={"itemId": item.item_id, "status": item.status.value},
                )
            if item.plan_fingerprint is None or item.truncated:
                raise ManualExecutionError(
                    "a selected Preview item does not contain a complete exact plan",
                    code="plan_unavailable",
                    next_action="request a fresh untruncated Preview for this item",
                    details={"itemId": item.item_id},
                )
            if item.plan_fingerprint != _fingerprint(item.plan):
                raise ManualExecutionError(
                    "the persisted Preview plan fingerprint does not match its content",
                    code="plan_stale",
                    next_action="request a fresh exact Preview for this item",
                    details={"itemId": item.item_id},
                )
            if versions[item.item_id] != item.item_version:
                raise ManualExecutionError(
                    "a selected Preview item version is stale",
                    code="item_stale",
                    next_action="reload the current intent and request a fresh Preview",
                    details={"itemId": item.item_id},
                )
            self._validate_plan_authority(item.plan, allow_overwrite, allow_source_cleanup)
            scopes.append(
                ManualExecutionScopeItem(
                    item.item_id,
                    item.preview_item_id,
                    item.item_version,
                    item.source_fingerprint,
                    item.plan_fingerprint,
                    item.source,
                    item.choice,
                )
            )
        now = self._clock()
        value = ManualExecutionAuthorization(
            str(uuid4()),
            preview.preview_id,
            preview.intent_id,
            preview.intent_version,
            preview.configuration_snapshot_id,
            preview.configuration_snapshot_digest,
            actor,
            permission,
            True,
            allow_overwrite,
            allow_source_cleanup,
            tuple(scopes),
            now,
            now + timedelta(seconds=ttl),
            note=note,
        )
        creator = getattr(self._repository, "create_manual_execution_authorization", None)
        if not callable(creator):
            raise ManualExecutionError(
                "manual execution authorization persistence is unavailable",
                code="execution_unavailable",
                status=503,
            )
        creator(value)
        return value

    issue_authorization = authorize
    authorize_preview = authorize

    def get_authorization(
        self, authorization_id: str, *, expire: bool = True
    ) -> ManualExecutionAuthorization:
        if expire:
            expirer = getattr(self._repository, "expire_manual_execution_authorizations", None)
            if callable(expirer):
                expirer(self._clock())
        getter = getattr(self._repository, "get_manual_execution_authorization", None)
        value = getter(authorization_id) if callable(getter) else None
        if value is None:
            raise ManualExecutionError(
                "manual execution authorization was not found",
                code="authorization_not_found",
                status=404,
            )
        return value

    def authorization_document(self, authorization_id: str) -> dict[str, object]:
        value = self.get_authorization(authorization_id, expire=False)
        document = value.document()
        audit_reader = getattr(self._repository, "list_manual_execution_authorization_audit", None)
        document["audit"] = (
            [item.document() for item in audit_reader(value.authorization_id)]
            if callable(audit_reader)
            else []
        )
        document["links"] = self._authorization_links(value)
        return redact_manual_value(document)

    def execute(
        self,
        authorization_id: str,
        *,
        actor: str,
        permission: str = "execute_manual_organize",
        confirmation: bool,
    ) -> ManualExecution:
        actor = self._actor(actor)
        permission = self._permission(permission)
        self._require_confirmation(confirmation)
        authority = self.get_authorization(authorization_id)
        if authority.status is not ManualExecutionAuthorizationStatus.ACTIVE:
            if authority.status is ManualExecutionAuthorizationStatus.EXPIRED:
                raise ManualExecutionError(
                    "manual execution authorization is expired",
                    code="authorization_expired",
                    next_action="request a fresh exact Preview and authorization",
                )
            if authority.status is ManualExecutionAuthorizationStatus.REVOKED:
                raise ManualExecutionError(
                    "manual execution authorization is revoked",
                    code="authorization_revoked",
                    next_action="inspect the authorization audit and request a fresh authorization",
                )
            raise ManualExecutionError(
                f"manual execution authorization is {authority.status.value}",
                code="authorization_consumed",
                next_action="inspect the linked execution; this authority cannot be reused",
            )
        if authority.actor != actor:
            raise ManualExecutionError(
                "execution actor does not match the authorization subject",
                code="authorization_actor_mismatch",
                status=403,
            )
        if permission != authority.permission:
            raise ManualExecutionError(
                "current permission does not match the authorization subject",
                code="authorization_permission_mismatch",
                status=403,
            )
        if authority.expires_at <= self._clock():
            raise ManualExecutionError(
                "manual execution authorization is expired",
                code="authorization_expired",
                next_action="request a fresh exact Preview and authorization",
            )
        preview = self._preview(authority.preview_id)
        self._validate_preview_parent(
            preview,
            authority.configuration_snapshot_id,
            authority.configuration_snapshot_digest,
        )
        intent = self._intent(authority.intent_id)
        if getattr(intent.status, "value", intent.status) != "open":
            raise ManualExecutionError(
                "the manual intent is no longer open",
                code="intent_stale",
                next_action="create a new manual intent and Preview",
            )
        if intent.version != authority.intent_version:
            raise ManualExecutionError(
                "the manual intent changed after authorization",
                code="intent_stale",
                next_action="request a fresh Preview and authorization",
            )
        selected = self._selected_authorized_items(preview, authority)
        runtime = self._load_runtime(
            authority.configuration_snapshot_id, authority.configuration_snapshot_digest
        )
        storage_ids = set()
        for item in selected:
            storage_ids.update(self._plan_storage_ids(item.plan))
        storages = self._create_storages(runtime, storage_ids)
        prepared: dict[
            str, tuple[ManualExecutionItem, OrganizePlan, tuple[tuple[str, str], ...]]
        ] = {}
        for item in selected:
            record = self._current_source(intent, item)
            self._validate_plan_authority(
                item.plan,
                authority.allow_overwrite,
                authority.allow_source_cleanup,
            )
            plan = self._plan_from_document(item.plan, item, runtime)
            self._validate_runtime_policy(plan, item, runtime)
            self._validate_current_storage(plan, item, authority, storages)
            locks = self._plan_locks(plan)
            execution_item = self._execution_item(authority, item)
            prepared[item.item_id] = (execution_item, plan, locks)
            del record
        plan_by_item = {item_id: value[1] for item_id, value in prepared.items()}
        execution_id = str(uuid4())
        task_id = str(uuid4())
        now = self._clock()
        execution_items = tuple(
            replace(
                value[0],
                execution_id=execution_id,
                preview_id=authority.preview_id,
                task_id=task_id,
                task_item_id=str(uuid4()),
            )
            for value in (prepared[item.item_id] for item in selected)
        )
        locks = tuple(sorted({lock for item in selected for lock in prepared[item.item_id][2]}))
        selected_ids = {scope.item_id for scope in authority.scope}
        unselected_item_ids = tuple(
            item.item_id for item in intent.items if item.item_id not in selected_ids
        )
        execution = ManualExecution(
            execution_id,
            authority.preview_id,
            authority.intent_id,
            authority.authorization_id,
            task_id,
            authority.actor,
            authority.intent_version,
            authority.configuration_snapshot_id,
            authority.configuration_snapshot_digest,
            tuple(item.item_id for item in selected),
            unselected_item_ids,
            execution_items,
            ManualExecutionStatus.ADMITTED,
            (
                "admission committed; reconcile this execution before any mutation if startup "
                "is interrupted"
            ),
            allow_overwrite=authority.allow_overwrite,
            allow_source_cleanup=authority.allow_source_cleanup,
            created_at=now,
            updated_at=now,
        )
        admit = getattr(self._repository, "admit_manual_execution", None)
        if not callable(admit):
            raise ManualExecutionError(
                "manual execution admission persistence is unavailable",
                code="execution_unavailable",
                status=503,
            )
        admitted = admit(authority, execution, execution_items, locks, now)
        try:
            if not self._locks_owned(admitted.task_id, locks):
                raise ManualExecutionError(
                    "the exact Storage fence was lost before execution",
                    code="concurrent_execution",
                    next_action="inspect the admitted Task and request a fresh Preview",
                )
            execution = replace(
                admitted,
                status=ManualExecutionStatus.RUNNING,
                next_action="inspect each independent execution item after it completes",
                updated_at=self._clock(),
            )
            self._repository.update_manual_execution(execution)
        except Exception:
            self._reconcile_unfinished(
                admitted,
                plan_by_item,
                audit_action="admission_interrupted",
                audit_details={"boundary": "before_organizer_executor"},
            )
            raise
        for item in admitted.items:
            execution_item, plan, item_locks = prepared[item.item_id]
            execution_item = replace(
                execution_item,
                execution_id=admitted.execution_id,
                task_id=admitted.task_id,
                task_item_id=item.task_item_id,
                status=ManualExecutionItemStatus.RUNNING,
                stage="organizing",
                updated_at=self._clock(),
            )
            try:
                task_item = self._repository.get_item(item.task_item_id)
                task = self._repository.get_task(admitted.task_id)
                if task_item is None or task is None:
                    raise ManualExecutionError(
                        "admitted Task scope could not be reloaded",
                        code="execution_unavailable",
                        status=503,
                    )
                task_item = replace(
                    task_item,
                    status=TaskItemStatus.PROCESSING,
                    stage="organizing",
                    attempts=task_item.attempts + 1,
                    updated_at=execution_item.updated_at,
                )
                self._repository.upsert_item(task_item)
                self._repository.update_manual_execution_item(execution_item)
            except Exception:
                self._reconcile_unfinished(
                    execution,
                    plan_by_item,
                    storages=storages,
                    audit_action="execution_start_interrupted",
                    audit_details={"boundary": "before_organizer_executor"},
                )
                raise
            result = (
                self._execute_plan(plan, storages)
                if self._locks_owned(admitted.task_id, item_locks)
                else ExecutionResult(
                    ExecutionStatus.FAILED,
                    plan.operation,
                    plan.source,
                    plan.target,
                    plan_id=plan.plan_id,
                    resolved_destination=plan.target,
                    errors=("the exact Storage fence was lost before mutation",),
                    effect_certainty=ExecutionEffectCertainty.NONE,
                )
            )
            result_record = self._result_record(admitted, execution_item, plan, result)
            effects = self._effects(execution_item, plan, result)
            terminal_item = replace(
                execution_item,
                status=self._item_status(result.status),
                stage=self._item_stage(result),
                result_id=result_record.result_id,
                effect_certainty=result.effect_certainty.value,
                completed_operations=result.completed_operations,
                uncertain_effects=result.uncertain_effects,
                error=self._result_error(result),
                next_action=self._next_action(result),
                effects=effects,
                updated_at=self._clock(),
            )
            terminal_task_item = replace(
                task_item,
                status=self._task_item_status(terminal_item.status),
                stage=terminal_item.stage,
                updated_at=terminal_item.updated_at,
                plan_id=plan.plan_id,
                destination_storage_id=plan.target_storage_id,
                destination_path=plan.target,
                execution_status=result.status.value,
                error=terminal_item.error,
            )
            current_items = tuple(
                terminal_item if value.item_id == terminal_item.item_id else value
                for value in execution.items
            )
            execution = replace(
                execution,
                items=current_items,
                **self._aggregate_execution(current_items),
                updated_at=terminal_item.updated_at,
            )
            task = self._task_after_item(task, terminal_task_item, current_items, execution)
            try:
                self._repository.complete_manual_execution_item(
                    execution,
                    terminal_item,
                    terminal_task_item,
                    task,
                    result_record,
                    effects,
                    item_locks,
                )
            except Exception:
                recovery_execution = replace(
                    execution,
                    items=tuple(
                        execution_item if value.item_id == terminal_item.item_id else value
                        for value in execution.items
                    ),
                )
                uncertain_result = self._uncertain_publication_result(result)
                self._reconcile_unfinished(
                    recovery_execution,
                    plan_by_item,
                    uncertain_results={terminal_item.item_id: uncertain_result},
                    storages=storages,
                    audit_action="result_publication_interrupted",
                    audit_details={"boundary": "after_organizer_executor"},
                )
                raise
            loaded = self._repository.get_manual_execution(admitted.execution_id)
            if loaded is None:
                raise ManualExecutionError(
                    "manual execution result could not be reloaded",
                    code="execution_unavailable",
                    status=503,
                )
            execution = loaded
        final = self._repository.get_manual_execution(admitted.execution_id)
        if final is None:
            raise ManualExecutionError(
                "manual execution could not be reloaded after completion",
                code="execution_unavailable",
                status=503,
            )
        return final

    consume = execute
    execute_authorized = execute

    def get(self, execution_id: str) -> ManualExecution:
        getter = getattr(self._repository, "get_manual_execution", None)
        value = getter(execution_id) if callable(getter) else None
        if value is None:
            raise ManualExecutionError(
                "manual execution was not found", code="execution_not_found", status=404
            )
        return value

    get_execution = get

    def reconcile(
        self,
        execution_id: str,
        *,
        actor: str,
        permission: str = "execute_manual_organize",
        confirmation: bool,
    ) -> ManualExecution:
        """Close an interrupted exact execution without invoking OrganizerExecutor.

        ``ADMITTED`` means no item has published a running boundary.  ``RUNNING`` means the
        executor may have crossed the Storage mutation boundary.  Both states therefore require
        an explicit, authenticated reconciliation action; this method never retries or rebuilds
        the reviewed plan.
        """

        actor = self._actor(actor)
        permission = self._permission(permission)
        self._require_confirmation(confirmation)
        execution = self.get(execution_id)
        authority = self.get_authorization(execution.authorization_id)
        if authority.actor != actor or execution.actor != actor:
            raise ManualExecutionError(
                "execution actor does not match the durable execution subject",
                code="authorization_actor_mismatch",
                status=403,
            )
        if permission != authority.permission:
            raise ManualExecutionError(
                "current permission does not match the durable execution subject",
                code="authorization_permission_mismatch",
                status=403,
            )
        if execution.status in {
            ManualExecutionStatus.COMPLETED,
            ManualExecutionStatus.PARTIAL_SUCCESS,
            ManualExecutionStatus.FAILED,
            ManualExecutionStatus.CANCELLED,
        }:
            return execution
        if execution.status not in {
            ManualExecutionStatus.ADMITTED,
            ManualExecutionStatus.RUNNING,
        }:
            raise ManualExecutionError(
                "manual execution is not in an interruptible state",
                code="execution_state_invalid",
                next_action="inspect the durable execution and Task checkpoint",
            )
        plan_by_item = {item.item_id: self._recovery_plan(item) for item in execution.items}
        return self._reconcile_unfinished(
            execution,
            plan_by_item,
            storages=self._recovery_storages(execution, plan_by_item),
            audit_action="manual_execution_reconciled",
            audit_details={"boundary": "explicit_restart_reconciliation"},
        )

    reconcile_execution = reconcile

    def document(self, execution_id: str) -> dict[str, object]:
        value = self.get(execution_id)
        document = value.document()
        for item in document["items"]:
            task_item_id = item["taskItemId"]
            try:
                checkpoint = self._checkpoint_service.get(task_item_id, task_id=value.task_id)
            except (LookupError, ValueError):
                checkpoint = None
            item["checkpoint"] = checkpoint.document() if checkpoint is not None else None
            item["checkpointPath"] = f"/api/v1/tasks/{value.task_id}/items/{task_item_id}"
        audit_reader = getattr(self._repository, "list_manual_execution_authorization_audit", None)
        if callable(audit_reader):
            item = document.get("authorizationId")
            document["authorizationAudit"] = [value.document() for value in audit_reader(item)]
        document["links"] = self._execution_links(value)
        return redact_manual_value(document)

    execution_document = document

    def discovery_for_intent(self, intent_id: str, *, limit: int = 100) -> dict[str, object]:
        limit = self._discovery_limit(limit)
        authorizations, auth_truncated = self._related_authorizations("intent", intent_id, limit)
        executions, execution_truncated = self._related_executions("intent", intent_id, limit)
        return self._discovery_document(
            authorizations,
            executions,
            truncated=auth_truncated or execution_truncated,
        )

    def discovery_for_preview(self, preview_id: str, *, limit: int = 100) -> dict[str, object]:
        limit = self._discovery_limit(limit)
        authorizations, auth_truncated = self._related_authorizations("preview", preview_id, limit)
        executions, execution_truncated = self._related_executions("preview", preview_id, limit)
        return self._discovery_document(
            authorizations,
            executions,
            truncated=auth_truncated or execution_truncated,
        )

    def discovery_for_task(self, task_id: str, *, limit: int = 100) -> dict[str, object]:
        limit = self._discovery_limit(limit)
        executions, truncated = self._related_executions("task", task_id, limit)
        return self._discovery_document((), executions, truncated=truncated)

    def discovery_for_task_item(
        self, task_id: str, task_item_id: str, *, limit: int = 100
    ) -> dict[str, object]:
        limit = self._discovery_limit(limit)
        reader = getattr(self._repository, "list_manual_executions_for_task_item", None)
        executions, truncated = self._bounded_related(reader, (task_id, task_item_id), limit)
        return self._discovery_document((), executions, truncated=truncated)

    def discovery_for_source(
        self, storage_id: str, path: str, *, limit: int = 100
    ) -> dict[str, object]:
        limit = self._discovery_limit(limit)
        reader = getattr(self._repository, "list_manual_executions_for_source", None)
        executions, truncated = self._bounded_related(reader, (storage_id, path), limit)
        return self._discovery_document((), executions, truncated=truncated)

    @staticmethod
    def _discovery_limit(limit: int) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("manual execution discovery limit must be between 1 and 100")
        return limit

    def _related_authorizations(
        self, relation: str, value: str, limit: int
    ) -> tuple[tuple[ManualExecutionAuthorization, ...], bool]:
        reader = getattr(
            self._repository,
            f"list_manual_execution_authorizations_for_{relation}",
            None,
        )
        return self._bounded_related(reader, (value,), limit)

    def _related_executions(
        self, relation: str, value: str, limit: int
    ) -> tuple[tuple[ManualExecution, ...], bool]:
        reader = getattr(self._repository, f"list_manual_executions_for_{relation}", None)
        return self._bounded_related(reader, (value,), limit)

    @staticmethod
    def _bounded_related(reader, arguments: tuple[object, ...], limit: int):
        if not callable(reader):
            return (), False
        values = tuple(reader(*arguments, limit=limit + 1))
        return values[:limit], len(values) > limit

    @classmethod
    def _discovery_document(
        cls,
        authorizations: Sequence[ManualExecutionAuthorization],
        executions: Sequence[ManualExecution],
        *,
        truncated: bool,
    ) -> dict[str, object]:
        document = {
            "authorizations": [cls._authorization_summary(value) for value in authorizations],
            "executions": [cls._execution_summary(value) for value in executions],
            "truncated": truncated,
            "sideEffects": "none",
            "nextAction": (
                "inspect the linked authorization or execution; reconcile admitted or running "
                "execution explicitly"
                if any(
                    value.status
                    in {
                        ManualExecutionStatus.ADMITTED,
                        ManualExecutionStatus.RUNNING,
                    }
                    for value in executions
                )
                else "inspect the linked authorization or durable execution state"
            ),
        }
        return redact_manual_value(document)

    @classmethod
    def _authorization_summary(cls, value: ManualExecutionAuthorization) -> dict[str, object]:
        return {
            "authorizationId": value.authorization_id,
            "previewId": value.preview_id,
            "intentId": value.intent_id,
            "actor": value.actor,
            "status": value.status.value,
            "scopeItemIds": [item.item_id for item in value.scope],
            "executionId": value.execution_id,
            "createdAt": value.created_at.isoformat(),
            "expiresAt": value.expires_at.isoformat(),
            "links": cls._authorization_links(value),
            "nextAction": value.document()["nextAction"],
        }

    @classmethod
    def _execution_summary(cls, value: ManualExecution) -> dict[str, object]:
        return {
            "executionId": value.execution_id,
            "authorizationId": value.authorization_id,
            "previewId": value.preview_id,
            "intentId": value.intent_id,
            "taskId": value.task_id,
            "actor": value.actor,
            "status": value.status.value,
            "selectedItemIds": list(value.selected_item_ids),
            "unselectedItemIds": list(value.unselected_item_ids),
            "items": [
                {
                    "itemId": item.item_id,
                    "taskItemId": item.task_item_id,
                    "status": item.status.value,
                    "resultId": item.result_id,
                    "checkpointPath": f"/api/v1/tasks/{item.task_id}/items/{item.task_item_id}",
                }
                for item in value.items
            ],
            "createdAt": value.created_at.isoformat(),
            "updatedAt": value.updated_at.isoformat(),
            "links": cls._execution_links(value),
            "nextAction": value.next_action,
        }

    @staticmethod
    def _authorization_links(value: ManualExecutionAuthorization) -> dict[str, str]:
        links = {
            "authorization": (
                f"/api/v1/manual-execution-authorizations/{quote(value.authorization_id, safe='')}"
            ),
            "preview": f"/api/v1/manual-previews/{quote(value.preview_id, safe='')}",
            "intent": f"/api/v1/manual-intents/{quote(value.intent_id, safe='')}",
        }
        if value.execution_id:
            links["execution"] = f"/api/v1/manual-executions/{quote(value.execution_id, safe='')}"
        return links

    @staticmethod
    def _execution_links(value: ManualExecution) -> dict[str, str]:
        links = {
            "execution": f"/api/v1/manual-executions/{quote(value.execution_id, safe='')}",
            "authorization": (
                f"/api/v1/manual-execution-authorizations/{quote(value.authorization_id, safe='')}"
            ),
            "preview": f"/api/v1/manual-previews/{quote(value.preview_id, safe='')}",
            "intent": f"/api/v1/manual-intents/{quote(value.intent_id, safe='')}",
            "task": f"/api/v1/tasks/{quote(value.task_id, safe='')}",
        }
        if value.status in {ManualExecutionStatus.ADMITTED, ManualExecutionStatus.RUNNING}:
            links["reconcile"] = (
                f"/api/v1/manual-executions/{quote(value.execution_id, safe='')}/reconcile"
            )
        return links

    def _preview(self, preview_id):
        try:
            return self._preview_service.get(preview_id)
        except ManualExecutionError:
            raise
        except Exception as error:
            if getattr(error, "status", None) == 404:
                raise ManualExecutionError(
                    "manual Preview was not found",
                    code="preview_not_found",
                    status=404,
                ) from error
            raise ManualExecutionError(
                self._safe_error(error),
                code=getattr(error, "code", "preview_unavailable"),
                status=getattr(error, "status", 409),
                next_action=getattr(
                    error,
                    "next_action",
                    "reload the manual intent and request a fresh Preview",
                ),
                details=getattr(error, "details", {}),
            ) from error

    def _intent(self, intent_id):
        if self._intent_service is None:
            raise ManualExecutionError(
                "manual intent service is unavailable", code="execution_unavailable", status=503
            )
        try:
            return self._intent_service.get(intent_id)
        except Exception as error:
            raise ManualExecutionError(
                "manual intent could not be reloaded",
                code="intent_unavailable",
                status=404 if getattr(error, "status", None) == 404 else 503,
            ) from error

    @staticmethod
    def _validate_preview_parent(preview, snapshot_id, snapshot_digest) -> None:
        if not preview.current:
            raise ManualExecutionError(
                "the reviewed Preview is historical or stale",
                code="preview_stale",
                next_action="request a fresh Preview from the current intent",
            )
        if snapshot_id is not None and snapshot_id != preview.configuration_snapshot_id:
            raise ManualExecutionError(
                "the Preview configuration snapshot does not match the request",
                code="snapshot_stale",
            )
        if snapshot_digest is not None and snapshot_digest != preview.configuration_snapshot_digest:
            raise ManualExecutionError(
                "the Preview configuration digest does not match the request",
                code="snapshot_stale",
            )

    def _select_preview_items(self, preview, item_ids):
        if isinstance(item_ids, (str, bytes)):
            raise ManualExecutionError(
                "itemIds must be a bounded array", code="malformed_selection"
            )
        try:
            values = tuple(item_ids)
        except TypeError as error:
            raise ManualExecutionError(
                "itemIds must be a bounded array", code="malformed_selection"
            ) from error
        if not 1 <= len(values) <= self._max_items:
            raise ManualExecutionError(
                f"execution selection must contain between 1 and {self._max_items} items",
                code="execution_over_limit" if values else "selection_empty",
            )
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ManualExecutionError(
                "itemIds must contain non-empty strings", code="malformed_selection"
            )
        if len(set(values)) != len(values):
            raise ManualExecutionError(
                "itemIds must not contain duplicates", code="duplicate_selection"
            )
        by_id = {item.item_id: item for item in preview.items}
        missing = [value for value in values if value not in by_id]
        if missing:
            raise ManualExecutionError(
                "selected item is not part of this Preview",
                code="item_not_found",
                status=404,
                details={"itemId": missing[0]},
            )
        return tuple(sorted((by_id[value] for value in values), key=lambda item: item.position))

    @staticmethod
    def _versions(items, supplied):
        if supplied is None:
            return {item.item_id: item.item_version for item in items}
        if isinstance(supplied, Mapping):
            if set(supplied) != {item.item_id for item in items}:
                raise ManualExecutionError(
                    "expectedItemVersions must cover exactly the selected items",
                    code="malformed_version",
                )
            values = dict(supplied)
        else:
            if isinstance(supplied, (str, bytes)):
                raise ManualExecutionError(
                    "expectedItemVersions must be an object", code="malformed_version"
                )
            try:
                sequence = tuple(supplied)
            except TypeError as error:
                raise ManualExecutionError(
                    "expectedItemVersions must be an object", code="malformed_version"
                ) from error
            if len(sequence) != len(items):
                raise ManualExecutionError(
                    "expectedItemVersions must cover exactly the selected items",
                    code="malformed_version",
                )
            values = {item.item_id: sequence[index] for index, item in enumerate(items)}
        for item_id, value in values.items():
            ManualOrganizeExecutionService._positive_version(
                value, f"expectedItemVersions[{item_id}]"
            )
        return values

    @staticmethod
    def _positive_version(value, label):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ManualExecutionError(
                f"{label} must be a positive integer", code="malformed_version"
            )

    @staticmethod
    def _actor(actor):
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 200:
            raise ManualExecutionError("execution actor is invalid", code="invalid_actor")
        return actor.strip()

    @staticmethod
    def _permission(permission):
        if permission != MANUAL_EXECUTION_PERMISSION:
            raise ManualExecutionError(
                "manual execution permission is invalid",
                code="invalid_permission",
                status=403,
            )
        return permission

    @staticmethod
    def _require_confirmation(value):
        if value is not True:
            raise ManualExecutionError(
                "explicit execution confirmation is required",
                code="confirmation_required",
                status=400,
            )

    @staticmethod
    def _require_bool(value, label):
        if not isinstance(value, bool):
            raise ManualExecutionError(
                f"{label} must be boolean", code="malformed_request", status=400
            )

    def _ttl(self, value):
        if value is None:
            return self._maximum_ttl_seconds
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= self._maximum_ttl_seconds
        ):
            raise ManualExecutionError(
                f"ttlSeconds must be between 1 and {self._maximum_ttl_seconds}",
                code="invalid_ttl",
                status=400,
            )
        return value

    @staticmethod
    def _validate_plan_authority(plan, allow_overwrite, allow_source_cleanup):
        if not isinstance(plan, dict) or not plan.get("zeroMutation", False):
            raise ManualExecutionError(
                "the persisted Preview plan is unavailable or invalid",
                code="plan_unavailable",
                next_action="request a fresh Preview",
            )
        execution_plan = plan.get("executionPlan")
        if not isinstance(execution_plan, dict):
            raise ManualExecutionError(
                "the persisted Preview does not contain exact executor input",
                code="plan_unavailable",
                next_action="request a fresh Preview",
            )
        if bool(execution_plan.get("overwriteAuthorized")) and not allow_overwrite:
            raise ManualExecutionError(
                "the reviewed plan requires explicit overwrite authority",
                code="overwrite_authority_required",
                next_action="explicitly confirm the authorized overwrite in a fresh request",
            )
        if allow_overwrite and not bool(execution_plan.get("overwriteAuthorized")):
            raise ManualExecutionError(
                "overwrite authority cannot broaden a reviewed plan",
                code="scope_changed",
            )
        cleanup = execution_plan.get("sourceDirectoryCleanup")
        cleanup_enabled = isinstance(cleanup, dict) and cleanup.get("mode") not in {None, "none"}
        if cleanup_enabled and not allow_source_cleanup:
            raise ManualExecutionError(
                "the reviewed plan requires explicit source-cleanup authority",
                code="source_cleanup_authority_required",
                next_action="explicitly confirm source cleanup or choose a plan without cleanup",
            )
        if allow_source_cleanup and not cleanup_enabled:
            raise ManualExecutionError(
                "source-cleanup authority cannot broaden a reviewed plan", code="scope_changed"
            )
        capabilities = plan.get("capabilities")
        if not isinstance(capabilities, dict):
            raise ManualExecutionError(
                "the persisted Preview capability evidence is invalid",
                code="plan_unavailable",
            )
        if capabilities.get("verdict") == "capability_gap":
            raise ManualExecutionError(
                "the reviewed plan has a Storage capability gap",
                code="capability_gap",
                next_action="repair the configured Storage capability and request a fresh Preview",
            )
        if plan.get("conflicts"):
            raise ManualExecutionError(
                "the reviewed plan still has unresolved conflicts",
                code="conflict_pending",
                next_action="resolve the affected conflict and request a fresh Preview",
            )

    def _selected_authorized_items(self, preview, authority):
        ids = tuple(scope.item_id for scope in authority.scope)
        items = self._select_preview_items(preview, ids)
        by_id = {scope.item_id: scope for scope in authority.scope}
        for item in items:
            scope = by_id[item.item_id]
            if (
                item.plan_fingerprint != _fingerprint(item.plan)
                or item.preview_item_id != scope.preview_item_id
                or item.item_version != scope.item_version
                or item.source_fingerprint != scope.source_fingerprint
                or item.plan_fingerprint != scope.plan_fingerprint
                or item.source.document() != scope.source.document()
                or item.choice.document() != scope.choice.document()
            ):
                raise ManualExecutionError(
                    "a reviewed Preview item changed after authorization",
                    code="item_stale",
                    next_action="request a fresh Preview and authorization",
                    details={"itemId": item.item_id},
                )
        return items

    def _current_source(self, intent, item):
        resolver = getattr(self._intent_service, "_resolve_file", None)
        if not callable(resolver):
            raise ManualExecutionError(
                "File catalog is unavailable", code="source_unavailable", status=503
            )
        try:
            record = resolver(item.source.file_id)
        except Exception as error:
            raise ManualExecutionError(
                "the reviewed source file is unavailable",
                code="source_missing",
                next_action="refresh Files and request a new manual intent",
            ) from error
        validator = getattr(self._intent_service, "_assert_source_unchanged", None)
        try:
            if callable(validator):
                validator(item.source, record)
            elif item.source.document() != type(item.source).from_file_record(record).document():
                raise ValueError("source identity changed")
        except Exception as error:
            raise ManualExecutionError(
                "the indexed source identity changed after Preview",
                code="source_stale",
                next_action="reload Files and request a fresh intent and Preview",
                details={"itemId": item.item_id},
            ) from error
        return record

    def _load_runtime(self, snapshot_id, snapshot_digest):
        loader = getattr(self._preview_service, "_load_runtime", None)
        if callable(loader):
            try:
                return loader(snapshot_id, snapshot_digest)
            except Exception as error:
                raise ManualExecutionError(
                    "the pinned configuration snapshot is unavailable",
                    code="snapshot_unavailable",
                    status=503,
                    next_action="inspect managed Active configuration and request a fresh Preview",
                ) from error
        if self._runtime_resolver is not None:
            try:
                try:
                    runtime = self._runtime_resolver(snapshot_id, snapshot_digest)
                except TypeError:
                    runtime = self._runtime_resolver()
            except Exception as error:
                raise ManualExecutionError(
                    "the pinned configuration snapshot is unavailable",
                    code="snapshot_unavailable",
                    status=503,
                ) from error
            return runtime
        if self._configuration is not None:
            runtime = self._configuration
            if (
                getattr(runtime, "configuration_snapshot_id", None) != snapshot_id
                or getattr(runtime, "configuration_snapshot_digest", None) != snapshot_digest
            ):
                raise ManualExecutionError(
                    "pinned configuration identity is unavailable", code="snapshot_stale"
                )
            return runtime
        raise ManualExecutionError(
            "manual execution runtime configuration is unavailable",
            code="snapshot_unavailable",
            status=503,
        )

    def _validate_checkpoint_snapshot(self, snapshot_id: str, snapshot_digest: str) -> None:
        """Validate the pinned snapshot without substituting the current Active revision."""

        if self._configuration_service is not None:
            validate = getattr(self._configuration_service, "validate_runtime_snapshot", None)
            require = getattr(self._configuration_service, "require", None)
            verify = getattr(self._configuration_service, "verify_integrity", None)
            if not all(callable(value) for value in (validate, require, verify)):
                raise ValueError("managed snapshot validator is unavailable")
            validate(snapshot_id, snapshot_digest)
            revision = require(snapshot_id)
            verify(revision)
            return
        if self._runtime_resolver is not None:
            try:
                try:
                    runtime = self._runtime_resolver(snapshot_id, snapshot_digest)
                except TypeError:
                    runtime = self._runtime_resolver()
            except Exception as error:
                raise ValueError("pinned runtime snapshot is unavailable") from error
            if isinstance(runtime, Mapping) or not hasattr(runtime, "strategy"):
                raise ValueError("pinned runtime snapshot is invalid")
            if (
                getattr(runtime, "configuration_authority", None) != "MANAGED"
                or getattr(runtime, "configuration_snapshot_id", None) != snapshot_id
                or getattr(runtime, "configuration_snapshot_digest", None) != snapshot_digest
            ):
                raise ValueError("pinned runtime snapshot identity does not match")
            return
        if self._configuration is not None:
            if (
                getattr(self._configuration, "configuration_authority", None) != "MANAGED"
                or getattr(self._configuration, "configuration_snapshot_id", None) != snapshot_id
                or getattr(self._configuration, "configuration_snapshot_digest", None)
                != snapshot_digest
            ):
                raise ValueError("pinned configuration snapshot identity does not match")
            return
        raise ValueError("pinned configuration snapshot is unavailable")

    def _create_storages(self, runtime, ids):
        helper = getattr(self._preview_service, "_create_storages", None)
        try:
            values = (
                helper(runtime, set(ids))
                if callable(helper)
                else runtime.create_storages(external=self._storages, storage_ids=set(ids))
            )
        except Exception as error:
            raise ManualExecutionError(
                "a configured Storage required by the reviewed plan is unavailable",
                code="storage_unavailable",
                status=503,
            ) from error
        result = dict(values)
        missing = sorted(set(ids).difference(result))
        if missing:
            raise ManualExecutionError(
                "a configured Storage required by the reviewed plan is unavailable",
                code="storage_unavailable",
                status=503,
                details={"storageIds": missing},
            )
        return result

    @staticmethod
    def _plan_storage_ids(plan):
        values = plan.get("executionPlan", {}).get("attachments", [])
        ids = {
            plan.get("executionPlan", {}).get("sourceStorageId"),
            plan.get("executionPlan", {}).get("targetStorageId"),
        }
        for value in values if isinstance(values, list) else ():
            if isinstance(value, dict):
                for key in ("source", "destination"):
                    location = value.get(key)
                    if isinstance(location, dict):
                        ids.add(location.get("storageId"))
        return {value for value in ids if isinstance(value, str) and value}

    def _plan_from_document(self, document, item, runtime) -> OrganizePlan:
        execution = document.get("executionPlan")
        if not isinstance(execution, dict):
            raise ManualExecutionError("exact executor input is missing", code="plan_unavailable")
        source_storage_id = execution.get("sourceStorageId")
        target_storage_id = execution.get("targetStorageId")
        source = execution.get("sourcePath")
        target = execution.get("targetPath")
        operation_raw = execution.get("operation")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (source_storage_id, target_storage_id, source, target, operation_raw)
        ):
            raise ManualExecutionError("exact executor input is malformed", code="plan_unavailable")
        if source_storage_id != item.source.storage_id or source != item.source.path:
            raise ManualExecutionError(
                "the reviewed plan source no longer matches the selected File",
                code="plan_stale",
            )
        policies = document.get("policies")
        if not isinstance(policies, dict):
            raise ManualExecutionError(
                "reviewed policy identity is invalid", code="plan_unavailable"
            )
        try:
            operation = PlanOperation(operation_raw)
        except ValueError as error:
            raise ManualExecutionError(
                "the reviewed operation is unsupported", code="unsupported_operation"
            ) from error
        link_operation = None
        raw_link = execution.get("linkOperation")
        if raw_link is not None:
            try:
                link_operation = OrganizeOperationType(raw_link)
            except ValueError as error:
                raise ManualExecutionError(
                    "the reviewed link operation is unsupported", code="unsupported_operation"
                ) from error
        try:
            source_location = StorageLocation(source_storage_id, source)
            destination_location = StorageLocation(target_storage_id, target)
        except ValueError as error:
            raise ManualExecutionError(
                "the reviewed Storage path is invalid", code="plan_unavailable"
            ) from error
        type_policy = next(
            (
                value
                for value in runtime.strategy.recognition_type_policies
                if value.recognition_type_id == item.choice.recognition_type_id
            ),
            None,
        )
        if type_policy is None or not type_policy.enabled:
            raise ManualExecutionError(
                "the pinned RecognitionType policy is unavailable",
                code="policy_unavailable",
                status=503,
            )
        attachments = []
        raw_attachments = execution.get("attachments", [])
        if not isinstance(raw_attachments, list) or len(raw_attachments) > self._max_items * 64:
            raise ManualExecutionError(
                "reviewed attachment evidence is invalid", code="plan_unavailable"
            )
        for value in raw_attachments:
            if not isinstance(value, dict):
                raise ManualExecutionError(
                    "reviewed attachment evidence is invalid", code="plan_unavailable"
                )
            try:
                source_value = value["source"]
                destination_value = value["destination"]
                attachments.append(
                    AttachmentPlan(
                        StorageLocation(source_value["storageId"], source_value["path"]),
                        StorageLocation(destination_value["storageId"], destination_value["path"]),
                        AttachmentType(value["type"]),
                        operation,
                        str(value.get("suffix", "")),
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ManualExecutionError(
                    "reviewed attachment evidence is invalid", code="plan_unavailable"
                ) from error
        rollback_doc = execution.get("rollback")
        configured_rollback = type_policy.organize_policy.rollback
        rollback = RollbackPolicy(
            bool(rollback_doc.get("enabled"))
            if isinstance(rollback_doc, dict)
            else configured_rollback.enabled,
            bool(rollback_doc.get("cleanupCreatedDirectories"))
            if isinstance(rollback_doc, dict)
            else configured_rollback.cleanup_created_directories,
        )
        cleanup_doc = execution.get("sourceDirectoryCleanup")
        cleanup = type_policy.organize_policy.source_directory_cleanup
        if isinstance(cleanup_doc, dict):
            try:
                cleanup = DirectoryCleanupPolicy(
                    DirectoryCleanupMode(cleanup_doc.get("mode", "none")),
                    int(cleanup_doc.get("maxParentDirectories", 1)),
                    tuple(cleanup_doc.get("ignorePatterns", ())),
                    int(cleanup_doc.get("maxEntries", 100)),
                )
            except (TypeError, ValueError) as error:
                raise ManualExecutionError(
                    "reviewed source cleanup policy is invalid", code="plan_unavailable"
                ) from error
        identity = self._media_identity(
            document.get("mediaIdentity"), item.choice.recognition_type_id
        )
        plan_status = PlanStatus.NOOP if operation is PlanOperation.SKIP else PlanStatus.READY
        plan_id = execution.get("planId") or document.get("planId")
        if not isinstance(plan_id, str) or not plan_id.strip():
            raise ManualExecutionError("reviewed plan identity is missing", code="plan_unavailable")
        if execution.get("planId") not in {None, plan_id} or document.get("planId") not in {
            None,
            plan_id,
        }:
            raise ManualExecutionError("reviewed plan identity is inconsistent", code="plan_stale")
        return OrganizePlan(
            source_storage_id,
            target_storage_id,
            source,
            target,
            str(document.get("recognitionType") or item.choice.recognition_type_id),
            str(policies.get("namingPolicyId") or item.choice.naming_policy_id),
            str(policies.get("classificationPolicyId") or item.choice.classification_policy_id),
            str(policies.get("organizePolicyId") or item.choice.organize_policy_id),
            (),
            operation,
            identity,
            None,
            None,
            (),
            (),
            plan_status,
            plan_id,
            link_operation,
            str(execution.get("mediaLibraryRoot") or ""),
            str(execution.get("relativeDestination") or ""),
            source_location,
            None,
            destination_location,
            bool(execution.get("overwriteAuthorized", False)),
            tuple(attachments),
            rollback,
            str(execution.get("sourceLibraryRoot") or ""),
            cleanup,
        )

    @staticmethod
    def _media_identity(value, recognition_type):
        if not isinstance(value, dict):
            return None
        try:
            media_type = MediaType(value["mediaType"])
            episodes = tuple(int(item) for item in value.get("episodes", ()))
            return MediaIdentity(
                provider=value["provider"],
                provider_id=value["providerId"],
                media_type=media_type,
                title=value["title"],
                original_title=value.get("originalTitle"),
                year=value.get("year"),
                season=value.get("season"),
                episode=value.get("episode"),
                episodes=episodes,
                episode_title=value.get("episodeTitle"),
                genres=tuple(value.get("genres", ())),
                countries=tuple(value.get("countries", ())),
                languages=tuple(value.get("languages", ())),
                matched_by=value.get("matchedBy"),
                recognition_type_id=recognition_type,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ManualExecutionError(
                "reviewed media identity is invalid", code="plan_unavailable"
            ) from error

    @staticmethod
    def _validate_runtime_policy(plan, item, runtime):
        policy_document = item.plan.get("policies", {})
        if not isinstance(policy_document, dict):
            raise ManualExecutionError(
                "reviewed policy identity is invalid", code="plan_unavailable"
            )
        type_policy = next(
            (
                value
                for value in runtime.strategy.recognition_type_policies
                if value.recognition_type_id == item.choice.recognition_type_id
            ),
            None,
        )
        if type_policy is None or (
            policy_document.get("recognitionTypePolicyId") != type_policy.policy_id
            or policy_document.get("metadataPolicyId") != type_policy.metadata_policy_id
            or plan.naming_policy_id != type_policy.naming_policy_id
            or plan.classification_policy_id != type_policy.classification_policy_id
            or plan.organize_policy_id != type_policy.organize_policy.policy_id
        ):
            raise ManualExecutionError(
                "the reviewed policy authority no longer matches the pinned snapshot",
                code="policy_stale",
                next_action="request a fresh Preview under the current permitted snapshot",
            )
        if plan.recognition_type_id != item.choice.recognition_type_id:
            raise ManualExecutionError(
                "RecognitionType changed in the reviewed plan", code="plan_stale"
            )
        configured_operation = type_policy.organize_policy.operation
        expected_operation = {
            OrganizeOperationType.MOVE: PlanOperation.MOVE,
            OrganizeOperationType.COPY: PlanOperation.COPY,
            OrganizeOperationType.HARD_LINK: PlanOperation.LINK,
            OrganizeOperationType.SOFT_LINK: PlanOperation.LINK,
        }.get(configured_operation)
        if plan.operation not in {PlanOperation.NOOP, PlanOperation.SKIP} and (
            expected_operation is None or plan.operation is not expected_operation
        ):
            raise ManualExecutionError(
                "the reviewed operation no longer matches the pinned OrganizePolicy",
                code="policy_stale",
                next_action="request a fresh Preview under the current permitted snapshot",
            )
        if plan.operation is PlanOperation.LINK and plan.link_operation is not configured_operation:
            raise ManualExecutionError(
                "the reviewed link operation no longer matches the pinned OrganizePolicy",
                code="policy_stale",
                next_action="request a fresh Preview under the current permitted snapshot",
            )

    def _validate_current_storage(self, plan, item, authority, storages):
        try:
            source_storage = storages[plan.source_storage_id]
            target_storage = storages[plan.target_storage_id]
        except KeyError as error:
            raise ManualExecutionError(
                "reviewed Storage is unavailable", code="storage_unavailable", status=503
            ) from error
        if plan.operation in {PlanOperation.NOOP, PlanOperation.SKIP}:
            return
        try:
            if plan.operation not in {
                PlanOperation.NOOP,
                PlanOperation.SKIP,
            } and not source_storage.exists(
                plan.source_location.path if plan.source_location else plan.source
            ):
                raise ManualExecutionError(
                    "reviewed source no longer exists",
                    code="source_missing",
                    next_action="refresh Files and request a fresh Preview",
                )
            required = _required_capabilities(plan)
            missing = []
            for capability in required:
                storage = source_storage if capability == "can_delete" else target_storage
                if capability == "same_storage_link":
                    missing.append(capability)
                elif not getattr(storage.capabilities, capability, False):
                    missing.append(capability)
            if missing:
                raise ManualExecutionError(
                    "current Storage capabilities no longer satisfy the reviewed plan",
                    code="capability_gap",
                    next_action="repair the Storage capability or request a fresh Preview",
                    details={"missing": missing},
                )
            target_path = (
                plan.destination_location.path if plan.destination_location else plan.target
            )
            target_exists = target_storage.exists(target_path)
            if (
                target_exists
                and not plan.overwrite_authorized
                and plan.operation not in {PlanOperation.SKIP, PlanOperation.NOOP}
            ):
                raise ManualExecutionError(
                    "reviewed destination changed before admission",
                    code="destination_changed",
                    next_action="inspect the destination and request a fresh Preview",
                )
            if plan.overwrite_authorized and not authority.allow_overwrite:
                raise ManualExecutionError(
                    "overwrite authority is not present for this reviewed plan",
                    code="overwrite_authority_required",
                )
            for attachment in plan.attachment_plans:
                attachment_source = storages[attachment.source.storage_id]
                attachment_target = storages[attachment.destination.storage_id]
                if not attachment_source.exists(attachment.source.path):
                    raise ManualExecutionError(
                        "a reviewed attachment source no longer exists",
                        code="attachment_source_missing",
                        next_action="refresh the sidecar set and request a fresh Preview",
                    )
                if (
                    attachment_target.exists(attachment.destination.path)
                    and not plan.overwrite_authorized
                ):
                    raise ManualExecutionError(
                        "a reviewed attachment destination changed before admission",
                        code="destination_changed",
                        next_action="inspect the destination and request a fresh Preview",
                    )
            if plan.source_directory_cleanup.mode is not DirectoryCleanupMode.NONE:
                if not authority.allow_source_cleanup:
                    raise ManualExecutionError(
                        "source cleanup authority is not present for this reviewed plan",
                        code="source_cleanup_authority_required",
                    )
                if not source_storage.capabilities.can_delete:
                    raise ManualExecutionError(
                        "source cleanup requires current delete capability",
                        code="capability_gap",
                    )
        except ManualExecutionError:
            raise
        except Exception as error:
            raise ManualExecutionError(
                "current Storage state could not be safely revalidated",
                code="storage_unavailable",
                status=503,
            ) from error

    @staticmethod
    def _plan_locks(plan):
        values = {
            (
                plan.source_storage_id,
                plan.source_location.path if plan.source_location else plan.source,
            ),
            (
                plan.target_storage_id,
                plan.destination_location.path if plan.destination_location else plan.target,
            ),
        }
        values.update((item.source.storage_id, item.source.path) for item in plan.attachment_plans)
        values.update(
            (item.destination.storage_id, item.destination.path) for item in plan.attachment_plans
        )
        return tuple(sorted(values))

    def _locks_owned(self, task_id: str, locks: Sequence[tuple[str, str]]) -> bool:
        checker = getattr(self._repository, "lock_owned", None)
        if not callable(checker):
            # Older in-memory adapters do not expose the optional fence query;
            # SQLiteTaskRepository does, and remains the production boundary.
            return True
        try:
            return all(checker(storage_id, path, task_id) for storage_id, path in locks)
        except Exception:
            return False

    @staticmethod
    def _execution_item(authority, preview_item):
        return ManualExecutionItem(
            str(uuid4()),
            "execution-pending",
            "preview-pending",
            preview_item.preview_item_id,
            authority.intent_id,
            preview_item.item_id,
            "task-pending",
            "task-item-pending",
            preview_item.item_version,
            preview_item.source_fingerprint,
            preview_item.plan_fingerprint or "0" * 64,
            preview_item.source,
            preview_item.choice,
            preview_item.plan or {},
            created_at=authority.created_at,
            updated_at=authority.created_at,
            next_action=(
                "admission committed; reconcile this execution before any mutation if startup "
                "is interrupted"
            ),
        )

    def _recovery_plan(self, item: ManualExecutionItem) -> OrganizePlan:
        """Reconstruct only the persisted exact plan needed to record an interruption."""

        document = item.plan
        execution = document.get("executionPlan")
        policies = document.get("policies")
        if not isinstance(execution, dict) or not isinstance(policies, dict):
            raise ManualExecutionError(
                "the persisted exact plan cannot be reconciled safely",
                code="plan_unavailable",
                status=503,
                next_action="inspect the durable execution and request a fresh Preview",
            )
        values = {
            "sourceStorageId": execution.get("sourceStorageId"),
            "targetStorageId": execution.get("targetStorageId"),
            "sourcePath": execution.get("sourcePath"),
            "targetPath": execution.get("targetPath"),
            "planId": execution.get("planId") or document.get("planId"),
        }
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise ManualExecutionError(
                "the persisted exact plan is incomplete",
                code="plan_unavailable",
                status=503,
                next_action="inspect the durable execution and request a fresh Preview",
            )
        try:
            operation = PlanOperation(execution["operation"])
            source_location = StorageLocation(values["sourceStorageId"], values["sourcePath"])
            destination_location = StorageLocation(values["targetStorageId"], values["targetPath"])
        except (KeyError, TypeError, ValueError) as error:
            raise ManualExecutionError(
                "the persisted exact plan operation or location is invalid",
                code="plan_unavailable",
                status=503,
                next_action="inspect the durable execution and request a fresh Preview",
            ) from error
        link_operation = None
        if execution.get("linkOperation") is not None:
            try:
                link_operation = OrganizeOperationType(execution["linkOperation"])
            except ValueError as error:
                raise ManualExecutionError(
                    "the persisted exact link operation is invalid",
                    code="plan_unavailable",
                    status=503,
                ) from error
        attachments: list[AttachmentPlan] = []
        for value in execution.get("attachments", ()):
            if not isinstance(value, dict):
                continue
            try:
                attachments.append(
                    AttachmentPlan(
                        StorageLocation(value["source"]["storageId"], value["source"]["path"]),
                        StorageLocation(
                            value["destination"]["storageId"], value["destination"]["path"]
                        ),
                        AttachmentType(value["type"]),
                        operation,
                        str(value.get("suffix", "")),
                    )
                )
            except (KeyError, TypeError, ValueError):
                # Admission already validated this document.  If a legacy row is malformed,
                # retain the primary plan and the investigation-only handoff rather than guess.
                continue
        identity = None
        try:
            identity = self._media_identity(
                document.get("mediaIdentity"), item.choice.recognition_type_id
            )
        except ManualExecutionError:
            pass
        return OrganizePlan(
            source_storage_id=values["sourceStorageId"],
            target_storage_id=values["targetStorageId"],
            source=values["sourcePath"],
            target=values["targetPath"],
            recognition_type_id=str(
                document.get("recognitionType") or item.choice.recognition_type_id
            ),
            naming_policy_id=str(policies.get("namingPolicyId") or item.choice.naming_policy_id),
            classification_policy_id=str(
                policies.get("classificationPolicyId") or item.choice.classification_policy_id
            ),
            organize_policy_id=str(
                policies.get("organizePolicyId") or item.choice.organize_policy_id
            ),
            operation=operation,
            media_identity=identity,
            status=PlanStatus.NOOP if operation is PlanOperation.SKIP else PlanStatus.READY,
            plan_id=values["planId"],
            link_operation=link_operation,
            source_location=source_location,
            destination_location=destination_location,
            overwrite_authorized=bool(execution.get("overwriteAuthorized", False)),
            attachment_plans=tuple(attachments),
        )

    def _recovery_storages(
        self, execution: ManualExecution, plans: Mapping[str, OrganizePlan]
    ) -> dict[str, object]:
        values = dict(self._storages)
        # The persisted plan is the only input here; Storage is read only and unavailable Storage
        # must not prevent the durable investigation handoff.
        ids = {
            storage_id
            for plan in plans.values()
            for storage_id in {
                plan.source_storage_id,
                plan.target_storage_id,
                *(value.source.storage_id for value in plan.attachment_plans),
                *(value.destination.storage_id for value in plan.attachment_plans),
            }
        }
        try:
            runtime = self._load_runtime(
                execution.configuration_snapshot_id,
                execution.configuration_snapshot_digest,
            )
            values.update(self._create_storages(runtime, ids))
        except Exception:
            pass
        return values

    @staticmethod
    def _observed_completed_operations(plan: OrganizePlan, storages) -> tuple[str, ...]:
        if plan.operation in {PlanOperation.NOOP, PlanOperation.SKIP}:
            return ()
        try:
            source = storages[plan.source_storage_id]
            target = storages[plan.target_storage_id]
            source_path = plan.source_location.path if plan.source_location else plan.source
            target_path = (
                plan.destination_location.path if plan.destination_location else plan.target
            )
            if not target.exists(target_path):
                return ()
            if plan.operation is PlanOperation.MOVE and source.exists(source_path):
                return ()
            return (plan.operation.value,)
        except Exception:
            return ()

    @staticmethod
    def _interrupted_result(
        plan: OrganizePlan, *, before_executor: bool, storages
    ) -> ExecutionResult:
        if before_executor:
            return ExecutionResult(
                ExecutionStatus.FAILED,
                plan.operation,
                plan.source,
                plan.target,
                plan_id=plan.plan_id,
                resolved_destination=plan.target,
                errors=(
                    "manual execution was interrupted before OrganizerExecutor started; "
                    "Storage was not mutated",
                ),
                effect_certainty=ExecutionEffectCertainty.NONE,
            )
        return ExecutionResult(
            ExecutionStatus.PARTIAL,
            plan.operation,
            plan.source,
            plan.target,
            completed_operations=ManualOrganizeExecutionService._observed_completed_operations(
                plan, storages
            ),
            plan_id=plan.plan_id,
            resolved_destination=plan.target,
            errors=(
                "manual execution was interrupted before its durable outcome was published; "
                "Storage state requires investigation",
            ),
            effect_certainty=ExecutionEffectCertainty.UNKNOWN,
            uncertain_effects=("process_interruption",),
        )

    @staticmethod
    def _uncertain_publication_result(result: ExecutionResult) -> ExecutionResult:
        uncertain_effects = tuple(dict.fromkeys((*result.uncertain_effects, "result_persistence")))
        errors = tuple(
            dict.fromkeys(
                (
                    *result.errors,
                    "durable result publication failed after OrganizerExecutor; Storage state "
                    "requires investigation",
                )
            )
        )
        return replace(
            result,
            status=ExecutionStatus.PARTIAL,
            errors=errors,
            effect_certainty=ExecutionEffectCertainty.UNKNOWN,
            uncertain_effects=uncertain_effects,
        )

    def _reconcile_unfinished(
        self,
        execution: ManualExecution,
        plan_by_item: Mapping[str, OrganizePlan],
        *,
        uncertain_results: Mapping[str, ExecutionResult] | None = None,
        storages: Mapping[str, object] | None = None,
        audit_action: str,
        audit_details: dict[str, object],
    ) -> ManualExecution:
        reconciler = getattr(self._repository, "reconcile_manual_execution", None)
        if not callable(reconciler):
            raise ManualExecutionError(
                "manual execution reconciliation persistence is unavailable",
                code="execution_unavailable",
                status=503,
                next_action=(
                    "inspect the durable Task and release the execution through an administrator"
                ),
            )
        task = self._repository.get_task(execution.task_id)
        if task is None:
            raise ManualExecutionError(
                "interrupted manual execution Task could not be reloaded",
                code="execution_unavailable",
                status=503,
            )
        storage_values = storages or {}
        overrides = uncertain_results or {}
        final_items: list[ManualExecutionItem] = []
        changed_task_items = []
        results = []
        effects = []
        for item in execution.items:
            if item.status in {
                ManualExecutionItemStatus.SUCCESS,
                ManualExecutionItemStatus.SKIPPED,
                ManualExecutionItemStatus.FAILED,
                ManualExecutionItemStatus.PARTIAL,
                ManualExecutionItemStatus.CANCELLED,
            }:
                final_items.append(item)
                continue
            plan = plan_by_item.get(item.item_id)
            if plan is None:
                raise ManualExecutionError(
                    "interrupted manual execution plan could not be reloaded",
                    code="plan_unavailable",
                    status=503,
                )
            result = overrides.get(item.item_id)
            if result is None:
                result = self._interrupted_result(
                    plan,
                    before_executor=item.status is ManualExecutionItemStatus.ADMITTED,
                    storages=storage_values,
                )
            result_record = self._result_record(execution, item, plan, result)
            item_effects = self._effects(item, plan, result)
            terminal_item = replace(
                item,
                status=self._item_status(result.status),
                stage=(
                    "admission_interrupted"
                    if item.status is ManualExecutionItemStatus.ADMITTED
                    and result.effect_certainty is ExecutionEffectCertainty.NONE
                    else self._item_stage(result)
                ),
                result_id=result_record.result_id,
                effect_certainty=result.effect_certainty.value,
                completed_operations=result.completed_operations,
                uncertain_effects=result.uncertain_effects,
                error=self._result_error(result),
                next_action=self._next_action(result),
                effects=item_effects,
                updated_at=self._clock(),
            )
            task_item = self._repository.get_item(item.task_item_id)
            if task_item is None:
                raise ManualExecutionError(
                    "interrupted manual execution TaskItem could not be reloaded",
                    code="execution_unavailable",
                    status=503,
                )
            terminal_task_item = replace(
                task_item,
                status=self._task_item_status(terminal_item.status),
                stage=terminal_item.stage,
                updated_at=terminal_item.updated_at,
                plan_id=plan.plan_id,
                destination_storage_id=plan.target_storage_id,
                destination_path=plan.target,
                execution_status=result.status.value,
                error=terminal_item.error,
            )
            final_items.append(terminal_item)
            changed_task_items.append(terminal_task_item)
            results.append(result_record)
            effects.extend(item_effects)
        # The durable repository method also protects a late recovery call against a terminal
        # execution.  Do not manufacture a second result when no item is unfinished.
        if not changed_task_items:
            return self.get(execution.execution_id)
        current_items = tuple(final_items)
        aggregate = self._aggregate_execution(current_items)
        has_uncertain = any(
            item.effect_certainty in {"unknown", "attempted_unverified"} for item in current_items
        )
        recovery_error = (
            "manual execution was interrupted before durable outcomes were published; "
            "inspect uncertain effects and do not replay automatically"
            if has_uncertain
            else "manual execution was interrupted before OrganizerExecutor started; "
            "Storage was not mutated"
        )
        updated_at = self._clock()
        final_execution = replace(
            execution,
            items=current_items,
            **aggregate,
            error=recovery_error,
            updated_at=updated_at,
        )
        latest_task_item = changed_task_items[-1]
        final_task = self._task_after_item(
            task, replace(latest_task_item, updated_at=updated_at), current_items, final_execution
        )
        audit = ManualExecutionAuthorizationAudit(
            str(uuid4()),
            execution.authorization_id,
            audit_action,
            updated_at,
            execution.actor,
            execution.execution_id,
            audit_details,
        )
        reconciler(
            final_execution,
            current_items,
            tuple(changed_task_items),
            final_task,
            tuple(results),
            tuple(effects),
            audit,
        )
        return self.get(execution.execution_id)

    def _execute_plan(self, plan, storages):
        try:
            return self._executor.execute(
                plan,
                storages,
                execute=True,
                source_storage_path=plan.source_location.path
                if plan.source_location
                else plan.source,
                destination_storage_path=plan.destination_location.path
                if plan.destination_location
                else plan.target,
                resolved_destination=plan.target,
            )
        except Exception:
            # An executor exception after admission is not safe to classify as
            # retryable: the invocation may have crossed the mutation boundary.
            return ExecutionResult(
                ExecutionStatus.PARTIAL,
                plan.operation,
                plan.source,
                plan.target,
                plan_id=plan.plan_id,
                resolved_destination=plan.target,
                errors=(
                    "OrganizerExecutor invocation failed; Storage state requires investigation",
                ),
                effect_certainty=ExecutionEffectCertainty.UNKNOWN,
                uncertain_effects=("executor_invocation",),
            )

    @staticmethod
    def _item_status(status):
        return {
            ExecutionStatus.SUCCESS: ManualExecutionItemStatus.SUCCESS,
            ExecutionStatus.SKIPPED: ManualExecutionItemStatus.SKIPPED,
            ExecutionStatus.FAILED: ManualExecutionItemStatus.FAILED,
            ExecutionStatus.PARTIAL: ManualExecutionItemStatus.PARTIAL,
        }.get(status, ManualExecutionItemStatus.FAILED)

    @staticmethod
    def _task_item_status(status):
        return {
            ManualExecutionItemStatus.SUCCESS: TaskItemStatus.SUCCESS,
            ManualExecutionItemStatus.SKIPPED: TaskItemStatus.SKIPPED,
            ManualExecutionItemStatus.FAILED: TaskItemStatus.FAILED,
            ManualExecutionItemStatus.PARTIAL: TaskItemStatus.PARTIAL,
        }.get(status, TaskItemStatus.FAILED)

    @staticmethod
    def _item_stage(result):
        if result.status is ExecutionStatus.SUCCESS:
            return "completed"
        if result.status is ExecutionStatus.SKIPPED:
            return "skipped"
        if result.effect_certainty in {
            ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
            ExecutionEffectCertainty.UNKNOWN,
        }:
            return "uncertain_effects"
        return "failed"

    @staticmethod
    def _result_error(result):
        if not result.errors:
            return None
        return _safe_error("; ".join(result.errors))

    @staticmethod
    def _next_action(result):
        if result.status is ExecutionStatus.SUCCESS:
            return "inspect the verified Result; no recovery replay is required"
        if result.status is ExecutionStatus.SKIPPED:
            return "item was skipped without mutation; request a fresh Preview only if needed"
        if result.effect_certainty is ExecutionEffectCertainty.NONE:
            return "inspect the pre-mutation failure, repair it, then request a fresh Preview"
        return (
            "investigate current Storage state and the Processing Checkpoint; "
            "automatic replay is refused"
        )

    def _result_record(self, execution, item, plan, result):
        identity = plan.media_identity
        policies = item.plan.get("policies", {})
        return PersistentResultRecord(
            str(uuid4()),
            execution.task_id,
            item.task_item_id,
            plan.source_storage_id,
            plan.source_location.path if plan.source_location else plan.source,
            plan.target_storage_id,
            plan.destination_location.path if plan.destination_location else plan.target,
            plan.recognition_type_id,
            identity.provider if identity else None,
            identity.provider_id if identity else None,
            policies.get("metadataPolicyId") if isinstance(policies, dict) else None,
            plan.naming_policy_id,
            plan.classification_policy_id,
            plan.organize_policy_id,
            result.operation.value,
            result.status.value,
            self._clock(),
            identity.title if identity else None,
            self._result_error(result),
            result.completed_operations,
            len(plan.attachment_plans),
            0,
            "manual_execution",
            result.cleanup_status.value,
            len(result.cleanup_steps),
            result.effect_certainty.value,
            result.uncertain_effects,
        )

    def _effects(self, item, plan, result):
        values: list[ManualExecutionEffect] = []
        certainty = result.effect_certainty.value
        verified = result.effect_certainty is ExecutionEffectCertainty.VERIFIED_COMPLETE
        attachment_by_source = {value.source.path: value for value in plan.attachment_plans}
        for operation in result.completed_operations:
            source_path = plan.source_location.path if plan.source_location else plan.source
            destination_path = (
                plan.destination_location.path if plan.destination_location else plan.target
            )
            details: dict[str, object] = {}
            action = operation
            if operation.startswith("ATTACHMENT:"):
                parts = operation.split(":", 2)
                attachment = attachment_by_source.get(parts[2]) if len(parts) == 3 else None
                if attachment is not None:
                    source_path = attachment.source.path
                    destination_path = attachment.destination.path
                    details["attachmentType"] = attachment.attachment_type.value
            elif operation == "CREATE_DIRECTORY" and result.created_directories:
                destination_path = result.created_directories[
                    min(len(values), len(result.created_directories) - 1)
                ]
            values.append(
                ManualExecutionEffect(
                    str(uuid4()),
                    item.execution_item_id,
                    len(values),
                    action[:128],
                    plan.source_storage_id,
                    source_path,
                    plan.target_storage_id,
                    destination_path,
                    verified,
                    certainty,
                    details,
                    self._clock(),
                )
            )
        for step in result.cleanup_steps:
            if len(values) >= _MAX_EFFECTS:
                break
            values.append(
                ManualExecutionEffect(
                    str(uuid4()),
                    item.execution_item_id,
                    len(values),
                    step.action,
                    plan.source_storage_id,
                    step.path,
                    plan.source_storage_id,
                    step.path,
                    bool(step.success and verified),
                    certainty,
                    {"reason": step.reason} if step.reason else {},
                    self._clock(),
                )
            )
        for step in result.rollback_steps:
            if len(values) >= _MAX_EFFECTS:
                break
            values.append(
                ManualExecutionEffect(
                    str(uuid4()),
                    item.execution_item_id,
                    len(values),
                    step.action,
                    step.storage_id,
                    step.source,
                    step.storage_id,
                    step.destination,
                    bool(step.success and verified),
                    certainty,
                    {"rollback": True, "error": step.error} if step.error else {"rollback": True},
                    self._clock(),
                )
            )
        if not values and result.effect_certainty in {
            ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
            ExecutionEffectCertainty.UNKNOWN,
        }:
            values.append(
                ManualExecutionEffect(
                    str(uuid4()),
                    item.execution_item_id,
                    0,
                    "UNCERTAIN_EXECUTOR_INVOCATION",
                    plan.source_storage_id,
                    plan.source,
                    plan.target_storage_id,
                    plan.target,
                    False,
                    certainty,
                    {"automaticReplay": False},
                    self._clock(),
                )
            )
        return tuple(values[:_MAX_EFFECTS])

    @staticmethod
    def _aggregate_execution(items):
        terminal = all(
            value.status
            in {
                ManualExecutionItemStatus.SUCCESS,
                ManualExecutionItemStatus.SKIPPED,
                ManualExecutionItemStatus.FAILED,
                ManualExecutionItemStatus.PARTIAL,
                ManualExecutionItemStatus.CANCELLED,
            }
            for value in items
        )
        failures = sum(
            value.status in {ManualExecutionItemStatus.FAILED, ManualExecutionItemStatus.PARTIAL}
            for value in items
        )
        uncertain = any(
            value.effect_certainty in {"unknown", "attempted_unverified"} for value in items
        )
        if not terminal:
            status = ManualExecutionStatus.RUNNING
            action = "inspect each independent execution item after it completes"
            completed = None
        elif failures == 0:
            status = ManualExecutionStatus.COMPLETED
            action = "inspect verified Results; no recovery replay is required"
            completed = True
        elif uncertain:
            status = ManualExecutionStatus.PARTIAL_SUCCESS
            action = "investigate uncertain effects through each Processing Checkpoint"
            completed = True
        elif failures == len(items):
            status = ManualExecutionStatus.FAILED
            action = "inspect pre-mutation failures and request fresh Previews"
            completed = True
        else:
            status = ManualExecutionStatus.PARTIAL_SUCCESS
            action = "inspect independent failed items and their Processing Checkpoints"
            completed = True
        return {
            "status": status,
            "next_action": action,
            "completed_at": datetime.now(UTC) if completed else None,
        }

    @staticmethod
    def _task_after_item(task, task_item, items, execution):
        terminal = all(
            value.status
            in {
                ManualExecutionItemStatus.SUCCESS,
                ManualExecutionItemStatus.SKIPPED,
                ManualExecutionItemStatus.FAILED,
                ManualExecutionItemStatus.PARTIAL,
                ManualExecutionItemStatus.CANCELLED,
            }
            for value in items
        )
        completed_items = sum(
            value.status in {ManualExecutionItemStatus.SUCCESS, ManualExecutionItemStatus.SKIPPED}
            for value in items
        )
        failed_items = sum(
            value.status in {ManualExecutionItemStatus.FAILED, ManualExecutionItemStatus.PARTIAL}
            for value in items
        )
        if not terminal:
            status = PersistentTaskStatus.RUNNING
        elif failed_items == 0:
            status = PersistentTaskStatus.COMPLETED
        elif failed_items == len(items):
            status = PersistentTaskStatus.FAILED
        else:
            status = PersistentTaskStatus.PARTIAL_SUCCESS
        return replace(
            task,
            status=status,
            updated_at=task_item.updated_at,
            completed_at=task_item.updated_at if terminal else None,
            total_items=len(items),
            completed_items=completed_items,
            failed_items=failed_items,
            error=execution.error,
        )


def _required_capabilities(plan: OrganizePlan) -> tuple[str, ...]:
    if plan.operation in {PlanOperation.NOOP, PlanOperation.SKIP}:
        return ()
    if plan.operation is PlanOperation.MOVE:
        primary = (
            ("can_move",)
            if plan.source_storage_id == plan.target_storage_id
            else (
                "can_copy",
                "can_delete",
            )
        )
    elif plan.operation is PlanOperation.COPY:
        primary = ("can_copy",)
    elif plan.operation is PlanOperation.LINK:
        primary = (
            (
                "can_hard_link"
                if plan.link_operation is OrganizeOperationType.HARD_LINK
                else "can_soft_link"
                if plan.link_operation is OrganizeOperationType.SOFT_LINK
                else "can_hard_link",
            )
            if plan.source_storage_id == plan.target_storage_id
            else ("same_storage_link",)
        )
    else:
        primary = ()
    return tuple(dict.fromkeys(primary))


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _safe_error(value: object) -> str:
    return safe_manual_error(value, "manual execution failed")


# Compatibility aliases for callers that use the shorter Preview terminology.
ManualExecutionService = ManualOrganizeExecutionService
ManualOrganizeExecutorService = ManualOrganizeExecutionService
