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

from mediaflow.domain.direct_files import LibraryKind, scoped_library_id
from mediaflow.domain.file_operation_history import (
    OrdinaryFileOperationRow,
    ordinary_file_commands,
    ordinary_operation_command,
    ordinary_operation_command_name,
    ordinary_operation_label,
)
from mediaflow.domain.task_persistence import (
    FILES_DELETE_TASK_COMMAND,
    FILES_DIRECT_COMMAND_TASK,
    FILES_TRANSFER_TASK_COMMAND,
    TaskItemStatus,
)

__all__ = ["LibraryFileOperationHistoryService", "LibraryFileOperationError"]

_MAX_IDENTIFIER = 256
_FAMILY_LABELS = {
    FILES_DIRECT_COMMAND_TASK: "文件维护",
    FILES_TRANSFER_TASK_COMMAND: "复制/移动",
    FILES_DELETE_TASK_COMMAND: "删除",
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
        """One ordinary operation of this library, or a bounded refusal."""

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
        return document

    def resolve(self, *, task_id: str) -> dict[str, object]:
        """Resolve one Task/run deep link to its exact owning library page.

        ``matched`` is ``True`` only when durable admitted evidence proves the
        Task is ordinary file work *and* names exactly one originating library
        of this service's kind.  Everything else stays an explicit non-match so
        the caller can render bounded guidance instead of guessing a library or
        loading a generic organizing recovery surface.
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
        if split is None or split[0] is not self._kind:
            return {
                "matched": False,
                "taskId": task.task_id,
                "reason": "not_ordinary_file_work",
                "nextAction": "open the exact Task detail in Operations",
                "sideEffects": "none",
            }
        identities = self._task_item_identities(task.task_id)
        library_id = self._origin(identities)
        if library_id is None:
            return {
                "matched": False,
                "taskId": task.task_id,
                "reason": "origin_unavailable",
                "nextAction": "open the exact Task detail in Operations",
                "sideEffects": "none",
            }
        return {
            "matched": True,
            "taskId": task.task_id,
            "libraryKind": self._kind.value,
            "libraryIdField": self._library_id_field(),
            "libraryId": library_id,
            self._library_id_field(): library_id,
            "path": self._deep_link_path(task),
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

        resolved = {identity for identity in identities if isinstance(identity, str) and identity}
        if len(resolved) != 1:
            return None
        persisted = resolved.pop()
        if self._kind is LibraryKind.MEDIA:
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
