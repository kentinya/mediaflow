"""Bounded readback of one library's ordinary file operations.

The Files and MediaLibrary pages admit ordinary maintenance (Create Folder/
Text, Rename, bounded text Save, Copy, Move, Delete) through the shared
direct-command, transfer and durable-Delete boundaries.  This module is the
*read* side of that work: an operator who opened the page fresh, changed
directory, switched library, closed the modal, reloaded, reconnected or
restarted the service can find exactly the operations that originated in the
library they are looking at.

Design boundaries:

* It reads durable Task/TaskItem/Result/transfer rows only.  It resolves no
  library, opens no Storage adapter, calls no Provider and never presents a
  superseded snapshot as current Active — so a removed, disabled or currently
  unreachable library keeps its history readable.
* Scope is decided *before* paging by exact durable identity: the Task command
  family (ordinary direct/transfer/Delete, with its MediaLibrary ``media_``
  twin) plus the scoped library identity every admitted TaskItem records.  A
  Result path, a display label, a filename, a Job link or today's Active
  configuration is never used to decide membership.
* Every read is count/page-consistent, newest-first and bounded.  Per-item
  outcomes stay reachable through the existing kind-scoped Delete/transfer
  projections and the Task detail read; this module does not duplicate them.
* Nothing here grants authority.  A control is only ever the backend-advertised
  lifecycle control of the exact Task the caller already reads, submitted
  through the existing Task lifecycle route.
"""

from __future__ import annotations

from datetime import datetime

from mediaflow.application.operations_lifecycle import bounded_failure_document
from mediaflow.domain.direct_files import LibraryKind, scoped_library_id
from mediaflow.domain.file_operation_history import (
    OrdinaryFileOperationRow,
    ordinary_file_commands,
    ordinary_operation_command,
    ordinary_operation_command_name,
    ordinary_operation_label,
)
from mediaflow.domain.organizer import ExecutionEffectCertainty
from mediaflow.domain.task_persistence import (
    FILES_DELETE_TASK_COMMAND,
    FILES_DIRECT_COMMAND_TASK,
    FILES_TRANSFER_TASK_COMMAND,
    TaskItemStatus,
)

__all__ = ["LibraryFileOperationHistoryService", "LibraryFileOperationError"]

_MAX_IDENTIFIER = 256
#: The bounded per-operation item evidence of one local detail read.  An
#: ordinary command admits one item per selected source (bounded by the domain's
#: own ``MAX_TRANSFER_PATHS``/``MAX_DELETE_PATHS``), so this cap is a defensive
#: bound rather than a routine truncation; when it does apply, the document says
#: so instead of silently dropping evidence.
_MAX_DETAIL_ITEMS = 100
_MAX_DETAIL_OUTCOMES = 400
_MAX_EFFECT_TEXT = 256
_FAMILY_LABELS = {
    FILES_DIRECT_COMMAND_TASK: "文件维护",
    FILES_TRANSFER_TASK_COMMAND: "复制/移动",
    FILES_DELETE_TASK_COMMAND: "删除",
}

#: The durable item status → the bounded disposition vocabulary the local detail
#: publishes.  The words are the same ones the Delete/transfer projections use,
#: so one ordinary operation never has two spellings in the page.
_DISPOSITIONS = {
    TaskItemStatus.SUCCESS: "SUCCESS",
    TaskItemStatus.PARTIAL: "PARTIAL",
    TaskItemStatus.FAILED: "FAILED",
    TaskItemStatus.SKIPPED: "SKIPPED",
    TaskItemStatus.IGNORED: "SKIPPED",
    TaskItemStatus.CANCELLED: "CANCELLED",
    TaskItemStatus.PAUSED: "PAUSED",
    TaskItemStatus.PROCESSING: "RUNNING",
    TaskItemStatus.PENDING: "QUEUED",
    TaskItemStatus.WAITING_CONFIRM: "QUEUED",
}

#: The durable effect certainty of one item, in the lifecycle projection's own
#: closed vocabulary so the dialog can render both with one label set.
_CERTAINTY = {
    ExecutionEffectCertainty.VERIFIED_COMPLETE.value: "verified_complete",
    ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED.value: "uncertain",
    ExecutionEffectCertainty.NONE.value: "none",
    ExecutionEffectCertainty.UNKNOWN.value: "unknown",
}


class LibraryFileOperationError(RuntimeError):
    """One bounded refusal of a library file-operation history read."""

    def __init__(self, code: str, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


class LibraryFileOperationHistoryService:
    """Kind-pinned, side-effect-free history of one library's ordinary work."""

    def __init__(self, repository, *, library_kind: LibraryKind) -> None:
        self._repository = repository
        self._kind = library_kind

    @property
    def library_kind(self) -> LibraryKind:
        return self._kind

    # ------------------------------------------------------------------
    # Bounded list
    # ------------------------------------------------------------------

    def window(
        self,
        *,
        library_id: str,
        limit: int = 20,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> dict[str, object]:
        """One page of this library's ordinary work plus its truthful total."""

        resolved_library = self._library_id(library_id)
        window = getattr(self._repository, "library_file_operations_window", None)
        if not callable(window):
            raise LibraryFileOperationError(
                "library_file_operations_unavailable",
                "the durable library file-operation history is unavailable",
                status=503,
            )
        tasks, total, has_next, has_previous = window(
            commands=ordinary_file_commands(self._kind),
            library_identity=self._scoped_id(resolved_library),
            limit=limit,
            after=after,
            before=before,
        )
        rows = self._rows(tasks)
        return {
            "items": [self._row_document(row, resolved_library) for row in rows],
            "libraryKind": self._kind.value,
            "libraryIdField": self._library_id_field(),
            "libraryId": resolved_library,
            self._library_id_field(): resolved_library,
            "limit": limit,
            "total": total,
            "hasNext": has_next,
            "hasPrevious": has_previous,
            "truncated": has_next,
            "sideEffects": "none",
            "retrySafe": True,
        }

    # ------------------------------------------------------------------
    # One exact entry and its deep-link resolution
    # ------------------------------------------------------------------

    def detail(self, *, library_id: str, task_id: str) -> dict[str, object]:
        """One ordinary operation of this library, or a bounded refusal.

        The document carries the Task aggregate *and* the exact per-item
        outcomes: an operator who reopened the page after a restart must be able
        to identify which selected file failed, what effect is known or
        uncertain and which safe next action applies — without the Task Center
        and without a raw durable error.
        """

        resolved_library = self._library_id(library_id)
        resolved_task = self._task_id(task_id)
        task = self._repository.get_task(resolved_task)
        if task is None or not self._belongs(task, resolved_library):
            raise LibraryFileOperationError(
                "library_file_operation_not_found",
                "no ordinary file operation of this library exists under this identity",
                status=404,
            )
        rows = self._rows((task,))
        if not rows:
            raise LibraryFileOperationError(
                "library_file_operation_not_found",
                "no ordinary file operation of this library exists under this identity",
                status=404,
            )
        document = self._row_document(rows[0], resolved_library)
        document["libraryIdField"] = self._library_id_field()
        document["sideEffects"] = "none"
        document["retrySafe"] = True
        document.update(self._item_evidence(task))
        return document

    def resolve(self, *, task_id: str) -> dict[str, object]:
        """Resolve one Task/run deep link to its exact owning library page.

        ``matched`` is ``True`` only when durable admitted evidence proves the
        Task is ordinary file work *and* names exactly one originating library.
        Everything else stays an explicit non-match so the caller can render
        bounded guidance instead of guessing a library or loading a generic
        organizing recovery surface.

        The kind is read from the Task's own durable command, so one shared
        deep-link route serves both library kinds: a MediaLibrary Task resolves
        to its MediaLibrary page and a ResourceLibrary Task to its
        ResourceLibrary page.  A caller-supplied kind never overrides the
        persisted one, and equal IDs across the two kinds cannot exchange
        origin, path or control authority.
        """

        resolved_task = self._task_id(task_id)
        task = self._repository.get_task(resolved_task)
        if task is None:
            raise LibraryFileOperationError(
                "library_file_operation_not_found",
                "no Task exists under this identity",
                status=404,
            )
        split = ordinary_operation_command(task.command)
        if split is None:
            return {
                "matched": False,
                "taskId": task.task_id,
                "reason": "not_ordinary_file_work",
                "nextAction": "open the exact Task detail in Operations",
                "sideEffects": "none",
            }
        kind, _family = split
        identities = self._task_item_identities(task.task_id)
        library_id = self._origin_for(kind, identities)
        if library_id is None:
            return {
                "matched": False,
                "taskId": task.task_id,
                "reason": "origin_unavailable",
                "nextAction": "open the exact Task detail in Operations",
                "sideEffects": "none",
            }
        field = "mediaLibraryId" if kind is LibraryKind.MEDIA else "resourceLibraryId"
        return {
            "matched": True,
            "taskId": task.task_id,
            "libraryKind": kind.value,
            "libraryIdField": field,
            "libraryId": library_id,
            field: library_id,
            "path": self._deep_link_path(task),
            "sideEffects": "none",
            "retrySafe": True,
        }

    # ------------------------------------------------------------------
    # Bounded historical origins of this kind
    # ------------------------------------------------------------------

    def origins(self, *, limit: int = 50) -> dict[str, object]:
        """The libraries of this kind that own durable ordinary work.

        The page header entry must keep working when the library it describes is
        disabled, removed, root-changed or currently unavailable.  This read
        therefore lists the *exact persisted origins* that still have ordinary
        work of this kind, so an operator can select one and inspect it without
        re-enabling it, without a live browse read and without the page silently
        falling back to another enabled library.

        The scope is decided from durable admitted identity only.  A library's
        current name/root is never read here: an origin that today's Active no
        longer configures is returned with an explicitly unavailable label rather
        than being hidden or rebound.
        """

        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise LibraryFileOperationError(
                "library_file_operation_invalid_request",
                "a bounded origin limit is required",
            )
        reader = getattr(self._repository, "library_file_operation_origins", None)
        if not callable(reader):
            raise LibraryFileOperationError(
                "library_file_operations_unavailable",
                "the durable library file-operation history is unavailable",
                status=503,
            )
        identities, observed = reader(
            commands=ordinary_file_commands(self._kind),
            media_library=self._kind is LibraryKind.MEDIA,
            media_prefix=scoped_library_id(LibraryKind.MEDIA, ""),
            limit=limit,
        )
        field = self._library_id_field()
        items: list[dict[str, object]] = []
        for persisted in identities:
            library_id = self._origin_for(self._kind, (persisted,))
            if library_id is None:
                # A persisted identity of the other kind never becomes this
                # kind's origin.
                continue
            items.append(
                {
                    "libraryKind": self._kind.value,
                    "libraryIdField": field,
                    "libraryId": library_id,
                    field: library_id,
                }
            )
        return {
            "items": items,
            "libraryKind": self._kind.value,
            "libraryIdField": field,
            "total": len(items),
            "truncated": observed > limit,
            "sideEffects": "none",
            "retrySafe": True,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _rows(self, tasks) -> tuple[OrdinaryFileOperationRow, ...]:
        task_ids = tuple(task.task_id for task in tasks)
        display_reader = getattr(self._repository, "library_file_operation_display", None)
        display = display_reader(task_ids) if callable(display_reader) else {}
        rows: list[OrdinaryFileOperationRow] = []
        for task in tasks:
            items = tuple(self._repository.list_items(task.task_id))
            success = sum(1 for item in items if item.status is TaskItemStatus.SUCCESS)
            failed = sum(
                1
                for item in items
                if item.status is TaskItemStatus.FAILED or item.status is TaskItemStatus.PARTIAL
            )
            skipped = sum(
                1
                for item in items
                if item.status is TaskItemStatus.SKIPPED or item.status is TaskItemStatus.IGNORED
            )
            cancelled = sum(1 for item in items if item.status is TaskItemStatus.CANCELLED)
            results = tuple(self._repository.list_results(task.task_id, limit=1))
            operation = results[-1].operation if results else None
            source_scope: str | None = None
            target_scope: str | None = None
            recorded = display.get(task.task_id) if isinstance(display, dict) else None
            if isinstance(recorded, tuple) and len(recorded) == 2:
                source_scope, target_scope = recorded
            rows.append(
                OrdinaryFileOperationRow(
                    task_id=task.task_id,
                    command=task.command,
                    status=task.status.value,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    item_total=len(items),
                    item_success=success,
                    item_failed=failed,
                    operation=operation,
                    source_scope=source_scope,
                    target_scope=target_scope,
                    pause_requested=task.pause_requested,
                    configuration_snapshot_id=task.configuration_snapshot_id,
                    item_skipped=skipped,
                    item_cancelled=cancelled,
                )
            )
        return tuple(rows)

    def _belongs(self, task, library_id: str) -> bool:
        split = ordinary_operation_command(task.command)
        if split is None or split[0] is not self._kind:
            return False
        return self._origin(self._task_item_identities(task.task_id)) == library_id

    def _task_item_identities(self, task_id: str) -> tuple[str, ...]:
        return tuple(item.resource_library_id for item in self._repository.list_items(task_id))

    def _origin(self, identities) -> str | None:
        """The exact configured library ID this collection of items proves."""

        return self._origin_for(self._kind, identities)

    @staticmethod
    def _origin_for(kind: LibraryKind, identities) -> str | None:
        """The exact configured library ID of one kind these items prove."""

        resolved = {identity for identity in identities if isinstance(identity, str) and identity}
        if len(resolved) != 1:
            return None
        persisted = resolved.pop()
        if kind is LibraryKind.MEDIA:
            prefix = scoped_library_id(LibraryKind.MEDIA, "")
            if not persisted.startswith(prefix) or len(persisted) == len(prefix):
                return None
            return persisted[len(prefix) :]
        if persisted.startswith(scoped_library_id(LibraryKind.MEDIA, "")):
            return None
        return persisted

    def _deep_link_path(self, task) -> str | None:
        """The exact reviewed scope a deep link may reopen, when proven.

        Only the recorded admission evidence is used, and only when it is a
        provably relative identity.  Nothing is read from live Storage.
        """

        reader = getattr(self._repository, "library_file_operation_display", None)
        recorded = reader((task.task_id,)) if callable(reader) else {}
        if isinstance(recorded, dict):
            entry = recorded.get(task.task_id)
            if isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], str):
                label = entry[0].strip()
                if "/" in label:
                    relative = label.split("/", 1)[1]
                    if relative and self._safe_relative(relative):
                        return relative
        scope = task.scope_path
        if not isinstance(scope, str) or not scope or not self._safe_relative(scope):
            return None
        return scope

    @staticmethod
    def _safe_relative(value: str) -> bool:
        if value.startswith(("/", "\\", "~")) or "\\" in value:
            return False
        if len(value) > 1 and value[1] == ":":
            return False
        return all(part not in {"", ".", ".."} for part in value.split("/"))

    # ------------------------------------------------------------------
    # Per-item evidence of one selected operation
    # ------------------------------------------------------------------

    def _item_evidence(self, task) -> dict[str, object]:
        """The exact per-item outcomes, effects and safe next action.

        Everything here is rebuilt from the durable TaskItem rows plus the
        Result each item already owns.  No Storage adapter, configuration
        resolution or Provider is consulted, so this survives a restart, a
        removed/disabled library and a currently unreachable Storage — and a
        read can never replay or complete anything.
        """

        items = tuple(self._repository.list_items(task.task_id))
        truncated = len(items) > _MAX_DETAIL_ITEMS
        selected = items[:_MAX_DETAIL_ITEMS]
        results: dict[str, object] = {}
        for record in self._repository.list_results(task.task_id):
            # The newest Result of one item is its factual outcome; an earlier
            # attempt stays durable history and is never replayed here.
            results.setdefault(record.item_id, record)
        outcomes: list[dict[str, object]] = []
        uncertain = False
        for item in selected:
            record = results.get(item.item_id)
            disposition = _DISPOSITIONS.get(item.status, "FAILED")
            certainty = _CERTAINTY.get(
                getattr(record, "effect_certainty", None)
                if record is not None
                else ExecutionEffectCertainty.UNKNOWN.value,
                "unknown",
            )
            if certainty == "uncertain":
                uncertain = True
                # A refused/partial mutation whose net effect could not be
                # verified is *uncertain*, never a settled failure: the existing
                # Delete/transfer projections call it the same thing, and the
                # operator must not read it as "nothing happened".
                if disposition in {"FAILED", "PARTIAL"}:
                    disposition = "UNCERTAIN"
            entry: dict[str, object] = {
                "itemId": item.item_id,
                "path": item.source_display or item.source_path,
                "destination": item.destination_path
                or (
                    ""
                    if item.status in {TaskItemStatus.PENDING, TaskItemStatus.PROCESSING}
                    else item.source_display
                ),
                "status": disposition,
                "stage": _bounded_text(item.stage),
                "attempts": item.attempts,
                "effect": _item_effect(disposition, certainty),
                "effectCertainty": certainty,
                "knownEffects": _known_effects(record, disposition),
            }
            failure = _item_failure(record, item, disposition)
            if failure is not None:
                entry["failure"] = failure
            entry["nextAction"] = _item_next_action(disposition, certainty, bool(failure))
            outcomes.append(entry)
            if len(outcomes) >= _MAX_DETAIL_OUTCOMES:
                truncated = True
                break
        document: dict[str, object] = {
            "items": outcomes,
            "itemsTruncated": truncated,
            "itemLimit": _MAX_DETAIL_ITEMS,
            "durableState": _durable_state(task, uncertain, outcomes),
            "effectCertainty": (
                "uncertain"
                if uncertain
                else (
                    "verified_complete"
                    if outcomes
                    and all(entry["effectCertainty"] == "verified_complete" for entry in outcomes)
                    else "unknown"
                    if not outcomes
                    else "none"
                )
            ),
        }
        document["nextAction"] = _operation_next_action(task, outcomes, uncertain)
        return document

    def _row_document(self, row: OrdinaryFileOperationRow, library_id: str) -> dict[str, object]:
        split = ordinary_operation_command(row.command)
        family = split[1] if split is not None else ""
        operation = ordinary_operation_command_name(
            row.operation,
            source_scope=row.source_scope,
            target_scope=row.target_scope,
        )
        document: dict[str, object] = {
            "taskId": row.task_id,
            "operation": operation,
            "operationLabel": ordinary_operation_label(
                row.command,
                row.operation,
                source_scope=row.source_scope,
                target_scope=row.target_scope,
            ),
            "command": row.command,
            "commandLabel": _FAMILY_LABELS.get(family, "未知文件操作"),
            "status": row.status,
            "terminal": row.terminal,
            "pauseRequested": row.pause_requested,
            "createdAt": row.created_at.isoformat(),
            "updatedAt": row.updated_at.isoformat(),
            "version": row.updated_at.isoformat(),
            "totalItems": row.item_total,
            "settledItems": row.item_total - row.item_pending,
            "succeededItems": row.item_success,
            "failedItems": row.item_failed,
            "skippedItems": row.item_skipped,
            "cancelledItems": row.item_cancelled,
            "pendingItems": row.item_pending,
            "allSucceeded": row.terminal and row.succeeded_all,
            "settled": row.settled,
            "sourceScope": row.source_scope,
            "targetScope": row.target_scope,
            "configurationSnapshotId": row.configuration_snapshot_id,
            self._library_id_field(): library_id,
        }
        return document

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _library_id(value: object) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > _MAX_IDENTIFIER:
            raise LibraryFileOperationError(
                "library_file_operation_invalid_request",
                "a bounded library identity is required",
            )
        return value

    @staticmethod
    def _task_id(value: object) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > _MAX_IDENTIFIER:
            raise LibraryFileOperationError(
                "library_file_operation_invalid_request",
                "a bounded Task identity is required",
            )
        return value

    def _scoped_id(self, library_id: str) -> str:
        return scoped_library_id(self._kind, library_id)

    def _library_id_field(self) -> str:
        return "mediaLibraryId" if self._kind is LibraryKind.MEDIA else "resourceLibraryId"


# ----------------------------------------------------------------------
# Bounded per-item evidence helpers
# ----------------------------------------------------------------------

_UNCERTAIN_EFFECTS = {"uncertain", "unknown"}


def _bounded_text(value: object, *, limit: int = _MAX_EFFECT_TEXT) -> str | None:
    """One bounded, secret-free durable label (never a raw adapter string)."""

    if not isinstance(value, str) or not value.strip():
        return None
    return value[:limit]


def _item_effect(disposition: str, certainty: str) -> str:
    """The net known effect of one item, in the projections' vocabulary."""

    if disposition == "SUCCESS":
        return "transferred" if certainty != "uncertain" else "uncertain"
    if disposition == "SKIPPED":
        return "skipped"
    if disposition == "PARTIAL":
        return "partial"
    if disposition == "UNCERTAIN" or certainty == "uncertain":
        return "uncertain"
    if disposition in {"RUNNING", "QUEUED", "PAUSED"}:
        return "in_progress"
    return "retained"


def _known_effects(record, disposition: str) -> list[str]:
    """The bounded completed/uncertain checkpoints one Result already records."""

    effects: list[str] = []
    completed = getattr(record, "completed_operations", ()) if record is not None else ()
    for value in completed:
        if isinstance(value, str) and value and len(effects) < 32:
            effects.append(value[:_MAX_EFFECT_TEXT])
    uncertain_effects = getattr(record, "uncertain_effects", ()) if record is not None else ()
    for value in uncertain_effects:
        if isinstance(value, str) and value and len(effects) < 32:
            effects.append(f"uncertain:{value[:_MAX_EFFECT_TEXT]}")
    del disposition
    return effects


def _item_failure(record, item, disposition: str) -> dict[str, object] | None:
    """The bounded refusal explanation of one non-successful item.

    ``bounded_failure_document`` decodes only this backend's own failure
    envelope and classifies anything else, so a raw durable error never reaches
    the document.
    """

    if disposition in {"SUCCESS", "SKIPPED"}:
        return None
    raw = getattr(record, "error", None) if record is not None else None
    if not raw:
        raw = item.error
    return bounded_failure_document(raw if isinstance(raw, str) else None)


def _item_next_action(disposition: str, certainty: str, has_failure: bool) -> str:
    """One safe next action per item, never an automatic repeat."""

    if certainty in _UNCERTAIN_EFFECTS:
        return "刷新来源与目标目录核实实际效果；不确定结果不会被自动重试"
    if disposition in {"SUCCESS", "SKIPPED"}:
        return "无需操作；刷新目录即可看到当前状态"
    if disposition == "RUNNING":
        return "等待 Worker 完成；关闭本窗口不会取消或重放该操作"
    if disposition == "QUEUED":
        return "排队等待 Worker；不要重复提交相同操作"
    if disposition == "PAUSED":
        return "在确认剩余范围安全后再明确继续该操作"
    if disposition == "CANCELLED":
        return "该条目已被取消，未执行的操作不会自动重放"
    if disposition == "UNCERTAIN":
        return "刷新来源与目标目录核实实际效果；不确定结果不会被自动重试"
    if has_failure:
        return "核对来源与实际状态后，明确选择需要的后续操作；不会自动重试"
    return "核实该条目当前状态后再决定下一步"


def _durable_state(task, uncertain: bool, outcomes: list[dict[str, object]]) -> str:
    """The bounded durable-state name of one selected operation."""

    if uncertain or task.error == "mutation_outcome":
        return "mutation_effect_uncertain"
    if task.status.value in {"completed", "partial_success", "failed", "cancelled"}:
        return f"task_{task.status.value}"
    if task.status.value == "paused":
        return "task_paused"
    if not outcomes:
        return "no_admitted_item"
    return "task_in_progress"


def _operation_next_action(task, outcomes: list[dict[str, object]], uncertain: bool) -> str:
    """The one safe next action of the whole selected operation."""

    if uncertain or task.error == "mutation_outcome":
        return "刷新来源目录核实实际状态；结果不确定的项目不会自动重试，也不会回滚已完成的成功项目"
    status = task.status.value
    if status in {"completed", "partial_success", "failed", "cancelled"}:
        failed = any(entry["status"] in {"FAILED", "PARTIAL"} for entry in outcomes)
        if failed:
            return (
                "查看下方逐项结果以确认哪些条目失败或部分完成；"
                "刷新目录核实当前状态后，明确选择需要的后续操作"
            )
        return "已无待处理条目；刷新目录即可看到当前状态"
    if status == "paused":
        return "确认剩余范围仍安全后，使用后端提供的继续控制；不会自动重试已完成项目"
    return "等待 Worker 在安全边界处理；关闭本窗口不会取消或重放该操作"
