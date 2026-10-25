"""Durable identity of ordinary file work that belongs to one library page.

The ordinary maintenance journey (Create Folder/Text, Rename, bounded text
Save, Copy, Move, Delete) is admitted per configured library and recorded in
the shared Task/TaskItem/transfer tables.  An operator who closes the browser,
changes directory, switches library, reconnects or restarts the service must
still be able to read exactly the work that originated in *this* library.

This module owns the two durable facts that read needs and nothing else:

* the closed set of ordinary command families, and their MediaLibrary
  ``media_``-prefixed twins, so a read can name its population by durable
  command identity instead of by display text or a Job link; and
* the operation label of one command family, used only for operator wording.

It holds no authority: no command is admitted here, no Task is replayed, and a
row that is missing durable origin evidence stays explicitly unavailable
rather than being guessed from today's Active configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mediaflow.domain.direct_files import DirectFileOperation, LibraryKind
from mediaflow.domain.task_persistence import (
    FILES_DELETE_TASK_COMMAND,
    FILES_DIRECT_COMMAND_TASK,
    FILES_TRANSFER_TASK_COMMAND,
    MEDIA_LIBRARY_TASK_COMMAND_PREFIX,
    TaskItemStatus,
)

__all__ = [
    "ORDINARY_FILE_COMMAND_BASES",
    "OrdinaryFileOperationRow",
    "ordinary_file_commands",
    "ordinary_operation_command",
    "ordinary_operation_command_name",
    "ordinary_operation_label",
    "ordinary_task_library_identity",
]

#: The ordinary command families of one library page, in the durable command
#: spelling a ResourceLibrary Task records.  A MediaLibrary Task records the
#: same names behind :data:`MEDIA_LIBRARY_TASK_COMMAND_PREFIX`.
ORDINARY_FILE_COMMAND_BASES: tuple[str, ...] = (
    FILES_DIRECT_COMMAND_TASK,
    FILES_TRANSFER_TASK_COMMAND,
    FILES_DELETE_TASK_COMMAND,
)

_LABELS = {
    FILES_DIRECT_COMMAND_TASK: "文件维护",
    FILES_TRANSFER_TASK_COMMAND: "复制/移动",
    FILES_DELETE_TASK_COMMAND: "删除",
}

_OPERATION_LABELS = {
    DirectFileOperation.CREATE_DIRECTORY.value: "新建文件夹",
    DirectFileOperation.CREATE_TEXT.value: "新建文本文件",
    DirectFileOperation.RENAME.value: "重命名",
    DirectFileOperation.SAVE_TEXT.value: "编辑文本",
    DirectFileOperation.DELETE.value: "删除",
    "copy": "复制",
    "move": "移动",
}

#: The executor's own operation names, as one durable Result records them.
_EXECUTOR_OPERATIONS = {
    "CREATE_DIRECTORY": DirectFileOperation.CREATE_DIRECTORY.value,
    "RENAME": DirectFileOperation.RENAME.value,
    "DELETE": DirectFileOperation.DELETE.value,
    "COPY": "copy",
    "MOVE": "move",
}

#: The one ambiguous executor operation: a bounded text write is either a new
#: file or an in-place edit.  The durable admission evidence distinguishes them
#: — a creation publishes the directory it happened in as its source scope and
#: the created entry as its target, while an in-place edit names the same entry
#: on both sides — so the distinction is read, never guessed.
_AMBIGUOUS_WRITE = "WRITE"


def ordinary_file_commands(kind: LibraryKind) -> tuple[str, ...]:
    """The durable Task commands of ordinary work owned by one library kind."""

    prefix = MEDIA_LIBRARY_TASK_COMMAND_PREFIX if kind is LibraryKind.MEDIA else ""
    return tuple(f"{prefix}{command}" for command in ORDINARY_FILE_COMMAND_BASES)


def ordinary_operation_command(command: object) -> tuple[LibraryKind, str] | None:
    """Split one durable ordinary command into its kind and base family.

    ``None`` means the command is not ordinary file work at all — an organizing
    Task, a manual preparation, an Automation run or an unknown legacy value —
    so a library history read can never pull it in.  A derived
    ``<family>:<identity>`` continuation keeps its family.
    """

    text = command if isinstance(command, str) else ""
    if not text:
        return None
    kind = LibraryKind.RESOURCE
    base = text
    if text.startswith(MEDIA_LIBRARY_TASK_COMMAND_PREFIX):
        kind = LibraryKind.MEDIA
        base = text[len(MEDIA_LIBRARY_TASK_COMMAND_PREFIX) :]
    family = base.split(":", 1)[0]
    if family not in ORDINARY_FILE_COMMAND_BASES:
        return None
    return kind, family


def ordinary_operation_command_name(
    operation: object,
    *,
    source_scope: object = None,
    target_scope: object = None,
) -> str | None:
    """The stable command identity of one persisted Result operation value.

    A direct command persists the executor's operation name (upper case) and a
    transfer persists its own name, so one durable value would otherwise have
    two spellings in the page.  The lower-case command identity is the single
    form the library history publishes.

    ``WRITE`` is the one genuinely ambiguous value: the same executor operation
    serves "create a text file" and "edit a text file in place".  The durable
    admission evidence settles it — a creation records the directory it
    happened in as its source scope and the created entry as its target,
    whereas an in-place edit names the same entry on both sides.  Without that
    evidence the value stays unknown rather than being guessed.
    """

    if not isinstance(operation, str) or not operation:
        return None
    candidate = operation if operation in _OPERATION_LABELS else operation.upper()
    if candidate == _AMBIGUOUS_WRITE:
        if not isinstance(source_scope, str) or not isinstance(target_scope, str):
            return None
        if not source_scope or not target_scope:
            return None
        return (
            DirectFileOperation.CREATE_TEXT.value
            if source_scope != target_scope
            else DirectFileOperation.SAVE_TEXT.value
        )
    if candidate in _EXECUTOR_OPERATIONS:
        return _EXECUTOR_OPERATIONS[candidate]
    lowered = operation.lower()
    if lowered in _OPERATION_LABELS:
        return lowered
    return None


def ordinary_operation_label(
    command: object,
    operation: object = None,
    *,
    source_scope: object = None,
    target_scope: object = None,
) -> str:
    """Bounded operator wording for one ordinary command (never authority)."""

    split = ordinary_operation_command(command)
    if split is None:
        return "未知文件操作"
    _kind, family = split
    resolved = ordinary_operation_command_name(
        operation, source_scope=source_scope, target_scope=target_scope
    )
    if resolved is not None:
        return _OPERATION_LABELS[resolved]
    return _LABELS[family]


def ordinary_task_library_identity(item_resource_library_ids) -> tuple[LibraryKind, str] | None:
    """The exact originating library of one Task, from its persisted items.

    A Task's identity comes from the scoped library identity the admission
    wrote on every TaskItem.  Items of two kinds, or of two libraries, never
    describe one origin: such a Task is explicitly unprovable and contributes
    ``None`` instead of a guessed library.
    """

    identities = {value for value in item_resource_library_ids if isinstance(value, str) and value}
    if len(identities) != 1:
        return None
    persisted = identities.pop()
    if persisted.startswith(MEDIA_LIBRARY_TASK_COMMAND_PREFIX):
        remainder = persisted[len(MEDIA_LIBRARY_TASK_COMMAND_PREFIX) :]
        if not remainder:
            return None
        return LibraryKind.MEDIA, remainder
    return LibraryKind.RESOURCE, persisted


@dataclass(frozen=True)
class OrdinaryFileOperationRow:
    """One ordinary operation of a library page, from one durable read.

    The row carries the Task aggregate plus the aggregates an operator needs to
    recognise it without opening it: the item counts, the exact operation the
    last durable Result recorded and the bounded display scope admitted with
    the work.  ``operation`` and the display scopes stay ``None`` when the
    durable evidence does not prove them — a legacy row is never backfilled
    from today's Active configuration.
    """

    task_id: str
    command: str
    status: str
    created_at: datetime
    updated_at: datetime
    item_total: int
    item_success: int
    item_failed: int
    operation: str | None = None
    source_scope: str | None = None
    target_scope: str | None = None
    pause_requested: bool = False
    configuration_snapshot_id: str | None = None

    @property
    def terminal(self) -> bool:
        return self.status in {"completed", "partial_success", "failed", "cancelled"}

    @property
    def item_pending(self) -> int:
        settled = self.item_success + self.item_failed
        return max(0, self.item_total - settled)

    @property
    def settled(self) -> bool:
        """Whether every admitted item already holds a factual outcome."""

        return self.item_total > 0 and self.item_pending == 0

    @property
    def succeeded_all(self) -> bool:
        return self.item_total > 0 and self.item_success == self.item_total


#: Statuses that prove an item reached a factual, non-replayable outcome.
SETTLED_ITEM_STATUSES = frozenset(
    {
        TaskItemStatus.SUCCESS,
        TaskItemStatus.PARTIAL,
        TaskItemStatus.FAILED,
        TaskItemStatus.SKIPPED,
        TaskItemStatus.CANCELLED,
    }
)
