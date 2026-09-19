"""Files bounded Upload application service.

Admission and durable execution for the bounded Files Upload command.  The
browser submits one bounded manifest (the exact relative items, their declared
sizes and the explicit conflict choice) ahead of the byte payloads; the
service validates the confined destination scope, pins the exact Active
configuration revision, creates one durable Task with one independent item per
uploaded file, and then streams each declared size out of the request body in
bounded chunks.  Every directory creation and every file write crosses
``OrganizerExecutor``; application code here never mutates Storage directly,
never buffers a whole media file in memory, and never persists text contents,
credentials, host roots or raw exception details.

Conflicts use the Transfer conflict semantics with Replace deliberately
absent: the default is no-overwrite (the item fails only, nothing is
replaced), ``skip`` leaves the existing destination untouched, and
``keep_both`` publishes the upload at a backend-generated unique name.  A
write whose effect cannot be proven complete is recorded UNCERTAIN and is
never replayed automatically.
"""

from __future__ import annotations

import hashlib
import io
import json
import posixpath
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import NAMESPACE_URL, uuid5

from mediaflow.application.direct_file_commands import DirectFileError
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.storage_browser import (
    _join_resource_library_path,
)
from mediaflow.application.task_runtime import TaskPauseRequested
from mediaflow.domain.direct_files import (
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_CHECKSUM_BYTES,
    MAX_UPLOAD_DEPTH,
    MAX_UPLOAD_DIRECTORIES,
    MAX_UPLOAD_ITEM_BYTES,
    MAX_UPLOAD_ITEMS,
    UploadConflictChoice,
    UploadItemOutcome,
    UploadItemPlan,
    UploadItemStatus,
    UploadResult,
)
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.storage import (
    Storage,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
)
from mediaflow.domain.task_persistence import (
    FILES_UPLOAD_TASK_COMMAND,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)

__all__ = ["DirectFileUploadService", "DirectFileUploadError"]

_CHUNK_SIZE = 64 * 1024

#: Reserved Windows device names that must never become upload destinations.
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


class DirectFileUploadError(DirectFileError):
    """A stable, secret-free bounded Upload admission or execution failure.

    Subclassing the Files direct-command error keeps one global handler: the
    response carries the exact ``error.details`` recovery projection and the
    exact HTTP status the admission computed.
    """

    @property
    def details(self) -> dict[str, object]:
        document = super().details
        document["stage"] = "files_upload"
        document["sideEffects"] = "storage_mutations"
        document["retrySafe"] = False
        return document


def _storage_category(error: Exception) -> tuple[str, int]:
    """Map one Storage failure onto the stable Upload admission category."""

    code = getattr(error, "code", None)
    if code is StorageErrorCode.NOT_FOUND:
        return "not_found", 404
    if code in {StorageErrorCode.PERMISSION_DENIED, StorageErrorCode.READ_ONLY}:
        return "capability_denied", 403
    if code is StorageErrorCode.AUTHENTICATION_FAILED:
        return "authentication_failed", 503
    if code in {StorageErrorCode.CONNECTION_FAILED, StorageErrorCode.CONNECTION_LOST}:
        return "connection_failed", 503
    if code is StorageErrorCode.TIMEOUT:
        return "timeout", 503
    if code is StorageErrorCode.RATE_LIMITED:
        return "rate_limited", 503
    return "storage_failure", 503


@dataclass(frozen=True)
class _PlannedItem:
    """One upload item with its pinned destination decision."""

    item: UploadItemPlan
    destination: str
    #: A pre-decided non-success outcome from the admission-time conflict
    #: observation; ``None`` when the item is expected to stream.
    pre_outcome: str | None = None
    pre_category: str | None = None


@dataclass
class _UploadState:
    """The mutable admission plan of one bounded Upload request."""

    library: ResourceLibrary
    storage: Storage
    destination_directory: str
    conflict: UploadConflictChoice
    items: tuple[UploadItemPlan, ...]
    planned: dict[int, _PlannedItem] = field(default_factory=dict)
    #: Unique directory-node destinations, keyed by the node's relative path.
    node_destinations: dict[str, str] = field(default_factory=dict)
    #: Directory nodes whose planned destination is occupied by an existing
    #: file; in ``skip`` mode their whole subtree is pre-skipped.
    colliding_nodes: set[str] = field(default_factory=set)
    #: The item indexes whose payload stream has already been accepted.  A
    #: second payload request for one index is refused (an executed item is
    #: never replayed), and items are delivered in manifest order so a
    #: sibling can never read another item's bytes as its own content.
    delivered: set[int] = field(default_factory=set)
    digest: str = ""


class DirectFileUploadService:
    """Files-owned admission and execution boundary for bounded Uploads."""

    def __init__(
        self,
        *,
        direct_files,
        executor: OrganizerExecutor | None = None,
    ) -> None:
        self._direct = direct_files
        self._executor = executor or OrganizerExecutor()
        # The admitted-plan registry of the streaming request: admission pins
        # the exact validated plan under the durable Task identity and the
        # same request's payload stream drains it.  A disconnect (the stream
        # never arrives) leaves the entry for GC; it is never a durable
        # authority and holds no Storage or credential state.
        self._admitted: dict[str, _UploadState] = {}

    # ------------------------------------------------------------------
    # Public command boundary
    # ------------------------------------------------------------------

    def upload(
        self,
        *,
        resource_library_id: str,
        manifest: Mapping[str, object],
        stream: BinaryIO | None = None,
    ) -> dict[str, object]:
        """Admit one bounded Upload as one durable Task and return 202.

        Admission performs zero mutation: the confined destination scope is
        validated, the exact Active revision is pinned and one durable
        ``files_upload`` Task is created with every item persisted PENDING.
        No payload byte is read here — the browser streams each item's
        payload afterwards through :meth:`execute_item`, in manifest order,
        while the durable projection (see :meth:`upload_projection`) and the
        cooperative lifecycle controls stay pollable between items.
        """

        if not isinstance(manifest, Mapping):
            raise DirectFileUploadError(
                "files_upload_invalid_request",
                "invalid_request",
                "the Upload manifest must be a bounded object",
                next_action="resend the Upload with a well-formed manifest",
            )
        library = self._direct.library(resource_library_id)
        storage = self._require_writable_storage(library)
        destination_directory = self._direct.relative_path(manifest.get("destinationDirectory", ""))
        conflict = self._conflict(manifest.get("conflict", UploadConflictChoice.NO_OVERWRITE))
        manifest_items = self._items(manifest.get("items"), library)
        state = self._plan_admission(
            library, storage, destination_directory, conflict, manifest_items
        )
        task = self._direct.tasks.create(
            FILES_UPLOAD_TASK_COMMAND,
            execute_authorized=True,
            scope_path=destination_directory,
            item_limit=len(state.items),
            configuration_snapshot_id=self._direct.revision.revision_id,
            configuration_snapshot_digest=self._direct.revision.digest,
        )
        # Every admitted item is persisted PENDING immediately, so the durable
        # projection shows truthful per-item progress from the first poll —
        # before, during and after the payload stream.
        now = datetime.now(UTC)
        for plan in state.planned.values():
            item_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"{task.task_id}:{storage.storage_id}:{plan.item.relative_path}",
                )
            )
            self._direct.tasks.repository.upsert_item(
                PersistentTaskItem(
                    item_id,
                    task.task_id,
                    storage.storage_id,
                    library.library_id,
                    plan.item.relative_path,
                    plan.item.relative_path,
                    TaskItemStatus.PENDING,
                    "files_upload",
                    0,
                    now,
                    now,
                )
            )
        # The same request streams its payloads into this exact plan; the
        # registry is request-scoped (one entry per admitted Task) and the
        # streaming execute consumes it.
        self._admitted[task.task_id] = state
        return {
            "taskId": task.task_id,
            "taskStatus": task.status.value,
            "admitted": True,
            "manifestDigest": state.digest,
            "conflict": state.conflict.value,
            "destinationDirectory": destination_directory,
            "totalItems": len(state.items),
            "status": "RUNNING",
            "sideEffects": "storage_mutations",
            "retrySafe": False,
            "nextAction": "the upload progress appears in the durable Task projection",
        }

    def execute_item(
        self,
        task_id: str,
        index: int,
        stream: BinaryIO,
    ) -> dict[str, object]:
        """Stream one admitted item's exact payload and record its outcome.

        The durable Task stays RUNNING while the browser streams each item in
        manifest order, so the projection (``upload_projection``) and the
        cooperative lifecycle controls stay pollable between items.  The
        item's declared size bounds the read exactly: a body that ends early
        records a truthful truncation, and leftover declared bytes after a
        refused or failed write are drained so no sibling can read this
        item's bytes as its own content.  A pause/cancel request is observed
        at this safe item boundary; the refused item is never replayed.
        """

        state = self._admitted.get(task_id)
        if state is None:
            raise DirectFileUploadError(
                "files_upload_unknown",
                "not_found",
                "no admitted Upload is streaming under this Task identity",
                status=404,
                next_action="resubmit the Upload from the Files workspace",
            )
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= len(state.items)
        ):
            raise DirectFileUploadError(
                "files_upload_invalid_request",
                "invalid_request",
                "the Upload item index is outside the admitted scope",
                status=400,
                next_action="resubmit the Upload with its exact selection",
            )
        if self._direct.tasks.cancellation_observed(task_id):
            return {
                "index": index,
                "path": state.items[index].relative_path,
                "status": "FAILED",
                "errorCategory": "upload_cancelled",
                "taskStatus": "cancelled",
                "terminal": True,
                "sideEffects": "storage_mutations",
                "retrySafe": False,
                "nextAction": "the upload was cancelled; refresh the directory",
            }
        if self._direct.tasks.pause_requested(task_id):
            self._direct.tasks.acknowledge_pause(task_id)
            return {
                "index": index,
                "path": state.items[index].relative_path,
                "status": "FAILED",
                "errorCategory": "upload_paused",
                "taskStatus": "paused",
                "terminal": False,
                "sideEffects": "storage_mutations",
                "retrySafe": False,
                "nextAction": "the upload is paused; the remaining items keep their own outcome",
            }
        task = self._direct.tasks.require(task_id)
        if task.status is not PersistentTaskStatus.RUNNING:
            raise DirectFileUploadError(
                "files_upload_task_not_running",
                "task_not_running",
                "the Upload Task is not streaming in this request sequence",
                status=409,
                next_action="resubmit the Upload from the Files workspace",
            )
        # Framing order is the manifest order: an out-of-order or repeated
        # payload request is refused before any read, so one item's bytes can
        # never be consumed as (or by) a sibling's payload.
        if index in state.delivered:
            raise DirectFileUploadError(
                "files_upload_item_already_delivered",
                "item_already_delivered",
                "this Upload item's payload was already delivered",
                status=409,
                next_action="continue with the next item or finish the upload",
            )
        if index != len(state.delivered):
            raise DirectFileUploadError(
                "files_upload_item_out_of_order",
                "item_out_of_order",
                "Upload payloads must be streamed in the manifest order",
                status=409,
                next_action="stream the remaining items in the manifest order",
            )
        item = state.items[index]
        plan = state.planned[index]
        try:
            task_item = self._direct.tasks.begin_item(
                task_id,
                state.storage.storage_id,
                state.library.library_id,
                item.relative_path,
                item.relative_path,
            )
        except TaskPauseRequested:
            self._direct.tasks.acknowledge_pause(task_id)
            return {
                "index": index,
                "path": item.relative_path,
                "status": "FAILED",
                "errorCategory": "upload_paused",
                "taskStatus": "paused",
                "terminal": False,
                "sideEffects": "storage_mutations",
                "retrySafe": False,
                "nextAction": "the upload is paused; the remaining items keep their own outcome",
            }
        state.delivered.add(index)
        try:
            outcome, item_truncated, checksum, written_destination, category = self._execute_item(
                state, plan, stream
            )
        except DirectFileUploadError as error:
            self._drain_payload(plan, stream)
            self._record_item(
                task_item,
                plan,
                UploadItemStatus.FAILED,
                error.category,
                destination=plan.destination,
            )
            return {
                "index": index,
                "path": item.relative_path,
                "status": "FAILED",
                "errorCategory": error.category,
                "taskStatus": self._direct.tasks.require(task_id).status.value,
                "terminal": False,
                "sideEffects": "storage_mutations",
                "retrySafe": False,
                "nextAction": "review the reason and retry this item or the selection",
            }
        self._record_item(
            task_item,
            plan,
            outcome,
            category,
            checksum=checksum,
            destination=written_destination,
        )
        document: dict[str, object] = {
            "index": index,
            "path": item.relative_path,
            "status": outcome.value,
            "taskStatus": self._direct.tasks.require(task_id).status.value,
            "terminal": False,
            "sideEffects": "storage_mutations",
            "retrySafe": False,
            "nextAction": "continue with the next item or finish the upload",
        }
        if written_destination is not None:
            document["destination"] = written_destination
        if checksum is not None:
            document["checksum"] = checksum
        if category is not None and outcome is not UploadItemStatus.SUCCESS:
            document["errorCategory"] = category
        if outcome is UploadItemStatus.UNCERTAIN:
            document["durableState"] = "mutation_effect_uncertain"
        return document

    def finish_upload(self, task_id: str) -> dict[str, object]:
        """Finalize one streamed Upload and return its bounded result.

        Every item the browser did not deliver keeps its own truthful
        refused outcome (never replayed, never fabricated); the durable
        Task reaches its honest terminal aggregate.
        """

        state = self._admitted.pop(task_id, None)
        if state is None:
            raise DirectFileUploadError(
                "files_upload_unknown",
                "not_found",
                "no admitted Upload is streaming under this Task identity",
                status=404,
                next_action="resubmit the Upload from the Files workspace",
            )
        outcomes: list[UploadItemOutcome] = []
        for index, item in enumerate(state.items):
            item_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"{task_id}:{state.storage.storage_id}:{item.relative_path}",
                )
            )
            previous = self._direct.tasks.repository.get_item(item_id)
            delivered = previous is not None and previous.status in {
                TaskItemStatus.SUCCESS,
                TaskItemStatus.PARTIAL,
                TaskItemStatus.FAILED,
                TaskItemStatus.SKIPPED,
            }
            if delivered:
                # A delivered item keeps its own recorded outcome.
                record = next(
                    (
                        result
                        for result in self._direct.tasks.repository.list_results(task_id)
                        if result.item_id == item_id
                    ),
                    None,
                )
                status = _projection_item_status(previous.status)
                uncertain = (
                    status == "PARTIAL"
                    and record is not None
                    and (record.effect_certainty == "attempted_unverified")
                )
                if uncertain:
                    status = "UNCERTAIN"
                checksum = next(
                    (
                        operation
                        for operation in (record.completed_operations if record else ())
                        if operation.startswith("sha256:")
                    ),
                    None,
                )
                outcomes.append(
                    UploadItemOutcome(
                        item.relative_path,
                        UploadItemStatus.UNCERTAIN
                        if uncertain
                        else (_terminal_item_status(previous.status)),
                        error_category=previous.error,
                        destination=previous.destination_path,
                        checksum=checksum,
                    )
                )
                continue
            plan = state.planned[index]
            outcomes.append(
                self._record_refused(
                    task_id,
                    state.library,
                    state.storage,
                    index,
                    plan,
                    "upload_stream_truncated",
                )
            )
        terminal = None
        task = self._direct.tasks.require(task_id)
        if task.status is PersistentTaskStatus.CANCELLED:
            terminal = "cancelled"
        result = self._finalize(state, task_id, outcomes, terminal)
        document = result.document()
        document["destinationDirectory"] = state.destination_directory
        document["nextAction"] = self._next_action(result)
        if result.status == "UNCERTAIN":
            document["durableState"] = "mutation_effect_uncertain"
        return document

    def upload_projection(self, task_id: str) -> dict[str, object]:
        """The durable, bounded operator projection of one Upload Task.

        Rebuilt from the persisted Task, item rows and Results — never from
        a request-scoped execution result — so polling while the upload
        streams, after admission or after a process restart reproduces the
        truthful per-item progress with the backend-advertised lifecycle
        actions (pause/cancel while running; resume is refused because the
        browser payload bytes are not durable and a paused upload is
        resubmitted as a fresh selection).
        """

        repository = self._direct.tasks.repository
        task = repository.get_task(task_id)
        if task is None or task.command != FILES_UPLOAD_TASK_COMMAND:
            raise DirectFileUploadError(
                "files_upload_unknown",
                "not_found",
                "no bounded Files Upload Task exists under this identity",
                status=404,
                next_action="return to the Files workspace and refresh",
            )
        items = repository.list_items(task_id)
        results = {record.item_id: record for record in repository.list_results(task_id)}
        outcomes: list[dict[str, object]] = []
        succeeded = failed = skipped = uncertain = 0
        processed = 0
        for item in items:
            record = results.get(item.item_id)
            status = _projection_item_status(item.status)
            if (
                status == "PARTIAL"
                and record is not None
                and (record.effect_certainty == "attempted_unverified")
            ):
                status = "UNCERTAIN"
            if status == "SUCCESS":
                succeeded += 1
            elif status == "SKIPPED":
                skipped += 1
            elif status == "UNCERTAIN":
                uncertain += 1
                failed += 1
            elif status == "FAILED":
                failed += 1
            if item.status not in {TaskItemStatus.PENDING}:
                processed += 1
            entry: dict[str, object] = {
                "path": item.source_display,
                "destination": item.destination_path or item.source_display,
                "status": status,
            }
            if item.error and status not in {"SUCCESS", "SKIPPED"}:
                entry["errorCategory"] = item.error
            outcomes.append(entry)
        terminal = task.status in {
            PersistentTaskStatus.COMPLETED,
            PersistentTaskStatus.PARTIAL_SUCCESS,
            PersistentTaskStatus.FAILED,
            PersistentTaskStatus.CANCELLED,
        }
        if terminal:
            if uncertain:
                aggregate = "UNCERTAIN"
            elif failed:
                aggregate = "PARTIAL" if (succeeded or skipped) else "FAILED"
            elif task.status is PersistentTaskStatus.CANCELLED:
                aggregate = "CANCELLED"
            elif skipped and not succeeded:
                aggregate = "SKIPPED"
            else:
                aggregate = "SUCCESS"
        elif task.status is PersistentTaskStatus.PAUSED:
            aggregate = "PAUSED"
        else:
            aggregate = "RUNNING"
        total = task.total_items or len(items)
        actions = [
            {
                "action": "pause",
                "available": task.status is PersistentTaskStatus.RUNNING
                and not task.pause_requested,
            },
            {
                "action": "cancel",
                "available": task.status
                in {PersistentTaskStatus.RUNNING, PersistentTaskStatus.PAUSED},
            },
            {
                "action": "resume",
                "available": False,
                "reason": "uploaded bytes are not durable; resubmit the selection",
            },
        ]
        document: dict[str, object] = {
            "operation": "upload",
            "taskId": task.task_id,
            "taskStatus": task.status.value,
            "status": aggregate,
            "totalItems": total,
            "processedItems": processed,
            "succeededItems": succeeded,
            "skippedItems": skipped,
            "failedItems": failed,
            "items": outcomes,
            "outcomesTruncated": False,
            "terminal": terminal,
            "actions": actions,
            "version": task.updated_at.isoformat(),
            "sideEffects": "storage_mutations" if processed else "none",
            "retrySafe": False,
            "nextAction": (
                "refresh the directory to see the current state"
                if terminal
                else "the upload progress appears here; pause or cancel only when offered"
            ),
        }
        if uncertain:
            document["durableState"] = "mutation_effect_uncertain"
        return document

    @staticmethod
    def _next_action(result: UploadResult) -> str:
        if result.status in {"SUCCESS", "SKIPPED"}:
            return "refresh the directory to see the current state"
        if result.status == "UNCERTAIN":
            return (
                "refresh the directory and inspect the Task before any retry; "
                "uncertain effects are never replayed automatically"
            )
        if result.status in {"PAUSED", "CANCELLED"}:
            return (
                "resume or inspect the Task from Operations; remaining items keep their own outcome"
            )
        return (
            "refresh the directory; failed items keep their own "
            "outcome and can be retried one at a time"
        )

    # ------------------------------------------------------------------
    # Admission (zero mutation)
    # ------------------------------------------------------------------

    def _require_writable_storage(self, library: ResourceLibrary) -> Storage:
        try:
            storage = self._direct.open_storage(library)
        except DirectFileError as error:
            raise DirectFileUploadError(
                error.code,
                error.category,
                "the referenced Storage is unavailable for this Upload",
                status=error.status,
                resource_library_id=library.library_id,
                next_action=error.details.get("nextAction", "retry the Upload"),
            ) from None
        if getattr(storage, "read_only", False):
            raise DirectFileUploadError(
                "files_upload_capability_denied",
                "capability_denied",
                "the referenced Storage is read-only",
                status=403,
                resource_library_id=library.library_id,
                next_action="select a writable ResourceLibrary or enable Storage writes",
            )
        return storage

    @staticmethod
    def _conflict(value: object) -> UploadConflictChoice:
        try:
            return UploadConflictChoice(value)
        except (TypeError, ValueError):
            raise DirectFileUploadError(
                "files_upload_invalid_request",
                "invalid_request",
                "the Upload conflict choice is not supported",
                next_action="choose no-overwrite, skip or keep-both and retry",
            ) from None

    def _items(self, value: object, library: ResourceLibrary) -> tuple[UploadItemPlan, ...]:
        if not isinstance(value, (list, tuple)) or not value:
            raise DirectFileUploadError(
                "files_upload_invalid_request",
                "invalid_request",
                "the Upload manifest requires at least one bounded item",
                resource_library_id=library.library_id,
                next_action="select at least one file or directory and retry",
            )
        plans: list[UploadItemPlan] = []
        seen: set[str] = set()
        for entry in value:
            if not isinstance(entry, Mapping):
                raise DirectFileUploadError(
                    "files_upload_invalid_request",
                    "invalid_request",
                    "each Upload item must be an object with a relative path and size",
                    resource_library_id=library.library_id,
                    next_action="resend the Upload manifest with well-formed items",
                )
            relative = self._validated_relative_path(
                entry.get("relativePath"), library, entry.get("isDirectory") is True
            )
            size = entry.get("size")
            if (
                isinstance(size, bool)
                or not isinstance(size, int)
                or size < 0
                or size > MAX_UPLOAD_ITEM_BYTES
            ):
                raise DirectFileUploadError(
                    "files_upload_size_limit_exceeded",
                    "upload_size_limit_exceeded",
                    "one uploaded file exceeds the bounded per-file size limit",
                    resource_library_id=library.library_id,
                    path=relative,
                    next_action="upload that file in smaller batches",
                )
            if relative in seen:
                raise DirectFileUploadError(
                    "files_upload_invalid_request",
                    "invalid_request",
                    "the Upload manifest repeats one relative item",
                    resource_library_id=library.library_id,
                    path=relative,
                    next_action="remove the duplicate item and retry",
                )
            seen.add(relative)
            plans.append(UploadItemPlan(relative_path=relative, size=size, is_directory=False))
        file_count = sum(1 for plan in plans if plan.is_file)
        if file_count > MAX_UPLOAD_ITEMS:
            raise DirectFileUploadError(
                "files_upload_count_limit_exceeded",
                "upload_count_limit_exceeded",
                f"the Upload selection exceeds the bounded item limit of {MAX_UPLOAD_ITEMS}",
                resource_library_id=library.library_id,
                next_action="upload smaller selections in batches",
            )
        total = sum(plan.size for plan in plans)
        if total > MAX_UPLOAD_BYTES:
            raise DirectFileUploadError(
                "files_upload_size_limit_exceeded",
                "upload_size_limit_exceeded",
                "the Upload selection exceeds the bounded aggregate size limit",
                resource_library_id=library.library_id,
                next_action="upload smaller selections in batches",
            )
        return tuple(plans)

    def _validated_relative_path(
        self, value: object, library: ResourceLibrary, is_directory: bool
    ) -> str:
        if not isinstance(value, str) or not value:
            raise DirectFileUploadError(
                "files_upload_invalid_path",
                "invalid_path",
                "every Upload item needs a safe relative path",
                resource_library_id=library.library_id,
                next_action="select files or directories from the browser and retry",
            )
        if value in {".", ".."} or value.startswith("/") or "\\" in value:
            raise DirectFileUploadError(
                "files_upload_invalid_path",
                "invalid_path",
                "an Upload item path is absolute or unsafe",
                resource_library_id=library.library_id,
                path=value,
                next_action="select files or directories from the browser and retry",
            )
        segments = value.split("/")
        if any(not segment or segment in {".", ".."} for segment in segments):
            raise DirectFileUploadError(
                "files_upload_invalid_path",
                "invalid_path",
                "an Upload item path contains an empty or traversal segment",
                resource_library_id=library.library_id,
                path=value,
                next_action="select files or directories from the browser and retry",
            )
        if len(segments) > MAX_UPLOAD_DEPTH:
            raise DirectFileUploadError(
                "files_upload_depth_limit_exceeded",
                "upload_depth_limit_exceeded",
                "an Upload item nests deeper than the bounded directory depth",
                resource_library_id=library.library_id,
                path=value,
                next_action="flatten the selected directory tree and retry",
            )
        for segment in segments:
            if "\x00" in segment or len(segment.encode("utf-8")) > 255:
                raise DirectFileUploadError(
                    "files_upload_invalid_path",
                    "invalid_path",
                    "an Upload item name is not a safe path component",
                    resource_library_id=library.library_id,
                    path=value,
                    next_action="rename the offending file or folder and retry",
                )
            stem = segment[: -len(posixpath.splitext(segment)[1])]
            if stem in _WINDOWS_RESERVED_NAMES:
                raise DirectFileUploadError(
                    "files_upload_invalid_path",
                    "invalid_path",
                    "an Upload item name is a reserved device name",
                    resource_library_id=library.library_id,
                    path=value,
                    next_action="rename the file or folder and retry",
                )
        if value == "":
            raise DirectFileUploadError(
                "files_upload_invalid_path",
                "invalid_path",
                "the Upload destination is the ResourceLibrary root itself",
                resource_library_id=library.library_id,
                next_action="choose a directory inside the ResourceLibrary",
            )
        return value

    def _plan_admission(
        self,
        library: ResourceLibrary,
        storage: Storage,
        destination_directory: str,
        conflict: UploadConflictChoice,
        items: tuple[UploadItemPlan, ...],
    ) -> _UploadState:
        state = _UploadState(
            library=library,
            storage=storage,
            destination_directory=destination_directory,
            conflict=conflict,
            items=items,
        )
        if destination_directory:
            self._require_destination_directory(library, storage, destination_directory)
        nodes = sorted(
            {prefix for item in items for prefix in self._directory_nodes(item.relative_path)}
        )
        if len(nodes) > MAX_UPLOAD_DIRECTORIES:
            raise DirectFileUploadError(
                "files_upload_count_limit_exceeded",
                "upload_count_limit_exceeded",
                "the Upload selection creates more directories than the bounded limit",
                resource_library_id=library.library_id,
                next_action="upload smaller selections in batches",
            )
        # Directory nodes are resolved shallowest-first so a renamed parent
        # determines the children's exact destination.
        for node in nodes:
            state.node_destinations[node] = self._plan_node_destination(
                library, storage, destination_directory, conflict, node, state
            )
        for index, item in enumerate(items):
            state.planned[index] = self._plan_item(
                library, storage, destination_directory, conflict, item, state
            )
        state.digest = self._manifest_digest(state, self._direct.revision)
        return state

    @staticmethod
    def _directory_nodes(relative_path: str) -> list[str]:
        parts = relative_path.split("/")
        return ["/".join(parts[:index]) for index in range(1, len(parts))]

    def _require_destination_directory(
        self, library: ResourceLibrary, storage: Storage, destination_directory: str
    ) -> None:
        full = _join_resource_library_path(library.root_path, destination_directory)
        try:
            entry = storage.stat(full)
        except (StorageError, OSError) as error:
            raise self._storage_failure(library, destination_directory, error) from None
        if entry.entry_type is not StorageEntryType.DIRECTORY:
            raise DirectFileUploadError(
                "files_upload_not_a_directory",
                "not_a_directory",
                "the Upload destination directory does not exist or is not a folder",
                status=404,
                resource_library_id=library.library_id,
                path=destination_directory,
                next_action="choose an existing directory as the destination",
            )

    def _storage_failure(
        self,
        library: ResourceLibrary,
        relative: str,
        error: Exception,
    ) -> DirectFileUploadError:
        category, status = _storage_category(error)
        return DirectFileUploadError(
            f"files_upload_{category}",
            category,
            "the Storage read for Upload admission failed",
            status=status,
            resource_library_id=library.library_id,
            path=relative,
            next_action="retry the Upload once the Storage is reachable again",
        )

    def _plan_node_destination(
        self,
        library: ResourceLibrary,
        storage: Storage,
        destination_directory: str,
        conflict: UploadConflictChoice,
        node: str,
        state: _UploadState,
    ) -> str:
        parent = posixpath.dirname(node)
        parent_destination = (
            state.node_destinations.get(parent, destination_directory)
            if parent
            else destination_directory
        )
        candidate = self._join(parent_destination, posixpath.basename(node))
        observed = self._safe_stat(library, storage, self._full_destination(library, candidate))
        if observed is None or observed.entry_type is StorageEntryType.DIRECTORY:
            # Absent, or an existing directory that the upload merges into.
            return candidate
        # A file occupies the directory slot.
        if conflict is UploadConflictChoice.KEEP_BOTH:
            # The node (and its whole subtree) is published under a
            # backend-generated unique name.
            return self._unique_destination_name(library, storage, candidate, is_directory=True)
        # No-overwrite and skip both refuse to touch the occupying file; the
        # difference is only whether the affected items fail or are skipped.
        state.colliding_nodes.add(node)
        return candidate

    def _plan_item(
        self,
        library: ResourceLibrary,
        storage: Storage,
        destination_directory: str,
        conflict: UploadConflictChoice,
        item: UploadItemPlan,
        state: _UploadState,
    ) -> _PlannedItem:
        parent = posixpath.dirname(item.relative_path)
        node_destination = (
            state.node_destinations.get(parent, destination_directory)
            if parent
            else destination_directory
        )
        candidate = self._join(node_destination, posixpath.basename(item.relative_path))
        # A directory node colliding with an existing file poisons its whole
        # subtree in the explicit no-overwrite / skip modes.
        colliding_ancestor = next(
            (
                node
                for node in self._directory_nodes(item.relative_path)
                if node in state.colliding_nodes
            ),
            None,
        )
        if colliding_ancestor is not None:
            if conflict is UploadConflictChoice.SKIP:
                return _PlannedItem(
                    item,
                    candidate,
                    pre_outcome="SKIPPED",
                    pre_category="parent_conflict",
                )
            return _PlannedItem(
                item,
                candidate,
                pre_outcome="FAILED",
                pre_category="parent_conflict",
            )
        observed = self._safe_stat(library, storage, self._full_destination(library, candidate))
        if observed is not None and observed.entry_type is StorageEntryType.FILE:
            if conflict is UploadConflictChoice.NO_OVERWRITE:
                return _PlannedItem(
                    item, candidate, pre_outcome="FAILED", pre_category="target_exists"
                )
            if conflict is UploadConflictChoice.SKIP:
                return _PlannedItem(
                    item, candidate, pre_outcome="SKIPPED", pre_category="skipped_existing"
                )
            candidate = self._unique_destination_name(
                library, storage, candidate, is_directory=False
            )
        return _PlannedItem(item, candidate)

    @staticmethod
    def _join(parent: str, name: str) -> str:
        return posixpath.join(parent, name) if parent else name

    def _full_destination(self, library: ResourceLibrary, relative: str) -> str:
        return _join_resource_library_path(library.root_path, relative)

    def _safe_stat(
        self,
        library: ResourceLibrary,
        storage: Storage,
        full: str,
    ) -> object:
        try:
            return storage.stat(full)
        except (StorageError, OSError):
            # A vanished entry is admitted as absent; the executor re-checks
            # the exact state at the last safe boundary before mutating.
            return None

    def _unique_destination_name(
        self,
        library: ResourceLibrary,
        storage: Storage,
        candidate: str,
        *,
        is_directory: bool,
    ) -> str:
        parent = posixpath.dirname(candidate)
        name = posixpath.basename(candidate)
        stem, extension = posixpath.splitext(name)
        index = 1
        while True:
            renamed = self._join(
                parent, f"{stem} ({index}){extension}" if extension else f"{name} ({index})"
            )
            observed = self._safe_stat(library, storage, self._full_destination(library, renamed))
            if observed is None or (
                observed.entry_type
                is (StorageEntryType.DIRECTORY if is_directory else StorageEntryType.FILE)
            ):
                return renamed
            index += 1
            if index > 10_000:
                raise DirectFileUploadError(
                    "files_upload_keep_both_conflict",
                    "keep_both_conflict",
                    "no unique destination name is available",
                    resource_library_id=library.library_id,
                    path=candidate,
                    next_action="remove the colliding entries and retry",
                )

    @staticmethod
    def _manifest_digest(state: _UploadState, revision) -> str:
        payload = json.dumps(
            {
                "revisionId": revision.revision_id,
                "revisionDigest": revision.digest,
                "libraryId": state.library.library_id,
                "storageId": state.library.storage_id,
                "destinationDirectory": state.destination_directory,
                "conflict": state.conflict.value,
                "items": [
                    [
                        item.relative_path,
                        item.size,
                        state.planned[index].destination,
                    ]
                    for index, item in enumerate(state.items)
                ],
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Execution (every mutation crosses OrganizerExecutor)
    # ------------------------------------------------------------------

    @staticmethod
    def _open_payload(plan: _PlannedItem, stream: BinaryIO) -> None:
        """Advance the request framing to one item's payload part.

        The multipart interface layer exposes ``open_next_payload``; a plain
        byte stream (the service-level tests) needs no framing step.
        """

        opener = getattr(stream, "open_next_payload", None)
        if callable(opener):
            opener(plan.item.size)

    @staticmethod
    def _drain_payload(plan: _PlannedItem, stream: BinaryIO) -> None:
        """Discard one item's declared payload bytes from the request stream.

        Outcome-independent framing: a refused, skipped or pre-conflicted
        item never leaves its bytes in the stream for the next sibling to
        read as its own content.  The drain is bounded by the declared size
        and never exceeds it; a body that ends early simply ends the drain
        (the declared-vs-actual mismatch is reported by the streaming item
        and the bounded post-response framing check, never fabricated).
        """

        DirectFileUploadService._open_payload(plan, stream)
        drainer = getattr(stream, "drain_payload", None)
        if callable(drainer):
            drainer(plan.item.size)
            return
        DirectFileUploadService._drain_bytes(stream, plan.item.size)

    @staticmethod
    def _drain_bytes(stream: BinaryIO, size: int) -> None:
        """Discard at most ``size`` declared bytes in bounded chunks."""

        remaining = size
        while remaining > 0:
            chunk = stream.read(min(remaining, _CHUNK_SIZE))
            if not chunk:
                return
            remaining -= len(chunk)

    def _record_refused(
        self,
        task_id: str,
        library: ResourceLibrary,
        storage: Storage,
        index: int,
        plan: _PlannedItem,
        category: str,
    ) -> UploadItemOutcome:
        """Record one item that never crossed the mutation boundary.

        Mirrors the Delete loop: a pause or cancel stops at this safe item
        boundary with zero further mutation, and the remaining items keep
        their own truthful outcome.  The item rows were persisted at
        admission, so a refused item updates its own durable row directly —
        the Task boundary is already past admission and may be paused,
        cancelled or terminal, which ``begin_item`` (an execution boundary)
        refuses; no new row is created and no mutation is attempted.
        """

        item_id = str(
            uuid5(NAMESPACE_URL, f"{task_id}:{storage.storage_id}:{plan.item.relative_path}")
        )
        previous = self._direct.tasks.repository.get_item(item_id)
        now = datetime.now(UTC)
        row = (
            previous
            if previous is not None
            else PersistentTaskItem(
                item_id,
                task_id,
                storage.storage_id,
                library.library_id,
                plan.item.relative_path,
                plan.item.relative_path,
                TaskItemStatus.PENDING,
                "files_upload",
                0,
                now,
                now,
            )
        )
        self._direct.tasks.repository.upsert_item(
            replace(
                row,
                status=TaskItemStatus.FAILED,
                stage=category,
                attempts=row.attempts + 1,
                updated_at=now,
                destination_path=plan.destination,
                error=category,
            )
        )
        return UploadItemOutcome(
            plan.item.relative_path,
            UploadItemStatus.FAILED,
            error_category=category,
        )

    def _execute_item(
        self,
        state: _UploadState,
        plan: _PlannedItem,
        stream: BinaryIO,
    ) -> tuple[UploadItemStatus, bool, str | None, str | None, str | None]:
        """Run one planned item.

        Returns ``(outcome, stream_truncated, bounded_checksum,
        written_destination, category)``.  The checksum is recorded only for
        bounded items and only when the write was verified complete;
        ``category`` is the stable secret-free reason for a non-success item.
        """

        library = state.library
        item = plan.item
        if plan.pre_outcome is not None:
            # Admission already observed the exact conflict; nothing is written.
            # The item's declared payload is drained so the next sibling starts
            # at its own framing boundary and can never read these bytes as
            # its own content.
            self._drain_payload(plan, stream)
            return (
                UploadItemStatus(plan.pre_outcome),
                False,
                None,
                None,
                plan.pre_category,
            )
        # Ensure the destination parent chain exists before the file write.
        # Colliding nodes were pre-planned per conflict mode: skip/fail items
        # never reach this point and keep-both nodes already hold their
        # renamed destination, so a live collision here fails closed.
        for node in self._directory_nodes(item.relative_path):
            node_destination = state.node_destinations[node]
            self._ensure_directory(library, state.storage, node_destination)
        # The last safe boundary: re-plan the exact destination against live
        # Storage so a raced appearance is resolved per the explicit conflict
        # choice instead of overwriting or silently changing.
        destination, skipped, skip_category = self._resolve_live_destination(state, plan)
        if destination is None:
            # Nothing is written: the item ends in its stable outcome and the
            # category names the observed conflict instead of a fabricated
            # write.  Framing stays aligned for the siblings.
            self._drain_payload(plan, stream)
            if skipped:
                return UploadItemStatus.SKIPPED, False, None, None, skip_category
            return UploadItemStatus.FAILED, False, None, None, skip_category or "target_exists"
        full = self._full_destination(library, destination)
        if item.size == 0:
            self._open_payload(plan, stream)
            result = self._executor.execute_direct_write_stream(
                state.storage, full, io.BytesIO(b""), 0, execute=True
            )
            if result.status.value == "SUCCESS":
                return (
                    UploadItemStatus.SUCCESS,
                    False,
                    "sha256:{}".format(hashlib.sha256(b"").hexdigest()),
                    destination,
                    None,
                )
            if result.effect_certainty.value == "attempted_unverified":
                return (
                    UploadItemStatus.UNCERTAIN,
                    False,
                    None,
                    destination,
                    "upload_partial_artifact",
                )
            return UploadItemStatus.FAILED, False, None, destination, "upload_write_failed"
        self._open_payload(plan, stream)
        chunk_stream = _BoundedChunkStream(stream, item.size, _CHUNK_SIZE)
        result = self._executor.execute_direct_write_stream(
            state.storage, full, chunk_stream, item.size, execute=True
        )
        if chunk_stream.truncated:
            # The request body ended before this item's declared size: the
            # destination may hold a partial artifact that can never be
            # proven complete, and the sibling items are short of their
            # bytes.  A partial artifact is UNCERTAIN (recoverable by
            # deleting and re-uploading this one item); a clean short read
            # that wrote nothing is a retry-safe FAILED.
            if result.effect_certainty.value == "attempted_unverified":
                return (
                    UploadItemStatus.UNCERTAIN,
                    True,
                    None,
                    destination,
                    "upload_stream_truncated",
                )
            return (
                UploadItemStatus.FAILED,
                True,
                None,
                destination,
                "upload_stream_truncated",
            )
        # A provider that refused or failed the write may not have consumed
        # the declared payload (or may have consumed less than declared):
        # draining the remainder keeps the framing aligned so the outcome of
        # this item cannot corrupt or conceal a sibling's.
        leftover = item.size - chunk_stream.consumed
        if leftover > 0:
            self._drain_bytes(stream, leftover)
        if result.status.value == "SUCCESS":
            checksum = (
                f"sha256:{chunk_stream.digest_hex()}"
                if item.size <= MAX_UPLOAD_CHECKSUM_BYTES
                else None
            )
            return UploadItemStatus.SUCCESS, False, checksum, destination, None
        if result.effect_certainty.value == "attempted_unverified":
            return (
                UploadItemStatus.UNCERTAIN,
                False,
                None,
                destination,
                "upload_partial_artifact",
            )
        return (
            UploadItemStatus.FAILED,
            False,
            None,
            destination,
            "upload_write_failed",
        )

    def _resolve_live_destination(
        self, state: _UploadState, plan: _PlannedItem
    ) -> tuple[str | None, bool, str | None]:
        """Re-plan one item's destination against live Storage at write time.

        Returns ``(destination, skipped, category)``.  ``destination is None``
        means the item must not be written: ``skipped`` marks an explicit
        conflict skip, otherwise ``category`` carries the stable failure
        reason.  The admission-time pin is authoritative; this re-observation
        only guards a raced appearance of the exact destination between
        admission and the mutation, and a keep-both rename is a single
        deterministic attempt — never a retry loop, and never an overwrite.
        """

        library = state.library
        storage = state.storage
        destination = plan.destination
        observed = self._safe_stat(library, storage, self._full_destination(library, destination))
        if observed is None or observed.entry_type is StorageEntryType.DIRECTORY:
            # Absent (the normal path) or a directory slot the item's own
            # basename can occupy.
            return destination, False, None
        # A live entry now occupies the exact destination.
        if state.conflict is UploadConflictChoice.NO_OVERWRITE:
            return None, False, "target_exists"
        if state.conflict is UploadConflictChoice.SKIP:
            return None, True, "skipped_existing"
        # keep-both: publish this item at a backend-generated unique name.
        parent = posixpath.dirname(plan.item.relative_path)
        node_destination = (
            state.node_destinations.get(parent, state.destination_directory)
            if parent
            else state.destination_directory
        )
        candidate = self._join(node_destination, posixpath.basename(plan.item.relative_path))
        return (
            self._unique_destination_name(library, storage, candidate, is_directory=False),
            False,
            None,
        )

    def _ensure_directory(
        self,
        library: ResourceLibrary,
        storage: Storage,
        node_destination: str,
    ) -> None:
        full = self._full_destination(library, node_destination)
        observed = self._safe_stat(library, storage, full)
        if observed is not None:
            if observed.entry_type is StorageEntryType.DIRECTORY:
                return
            # A file occupies the directory slot; no overwrite is ever
            # attempted.  The item's per-item result carries the stable
            # category instead of a fabricated directory.
            raise DirectFileUploadError(
                "files_upload_parent_conflict",
                "parent_conflict",
                "an uploaded directory collides with an existing file",
                resource_library_id=library.library_id,
                path=node_destination,
                next_action="move the conflicting file and retry the Upload",
            )
        result = self._executor.execute_direct_create_directory(storage, full, execute=True)
        if result.status.value != "SUCCESS":
            category = (
                "parent_conflict"
                if "destination already exists" in "; ".join(result.errors)
                else "upload_storage_failure"
            )
            raise DirectFileUploadError(
                f"files_upload_{category}",
                category,
                "the Upload directory could not be created",
                status=409 if category == "parent_conflict" else 503,
                resource_library_id=library.library_id,
                path=node_destination,
                next_action="review the destination directory and retry the Upload",
            )

    def _record_item(
        self,
        task_item,
        plan: _PlannedItem,
        outcome: UploadItemStatus,
        category: str | None,
        *,
        checksum: str | None = None,
        destination: str | None = None,
    ) -> None:
        """Persist one item outcome and its bounded executor-owned evidence."""

        if outcome is UploadItemStatus.SUCCESS:
            status = TaskItemStatus.SUCCESS
            error = None
            completed = ("write",)
            certainty = "verified_complete"
            uncertain: tuple[str, ...] = ()
        elif outcome is UploadItemStatus.SKIPPED:
            status = TaskItemStatus.SKIPPED
            error = category
            completed = ()
            certainty = "none"
            uncertain = ()
        elif outcome is UploadItemStatus.UNCERTAIN:
            status = TaskItemStatus.PARTIAL
            # The stable per-item category (e.g. ``upload_stream_truncated``
            # or ``upload_partial_artifact``) is the durable, secret-free
            # reason the effect could not be proven complete.
            error = category or "upload destination effect unverified"
            completed = ("write_started",)
            certainty = "attempted_unverified"
            uncertain = ("partial_write",)
        else:
            status = TaskItemStatus.FAILED
            error = category
            completed = ()
            certainty = "none"
            uncertain = ()
        if checksum:
            completed = (*completed, checksum)
        self._direct.tasks.complete_direct_item(
            task_item,
            status=status,
            operation="files_upload",
            target_path=destination or plan.destination,
            error=error,
            effect_certainty=certainty,
            uncertain_effects=uncertain,
            completed_operations=tuple(completed),
        )

    def _finalize(
        self,
        state: _UploadState,
        task_id: str,
        outcomes: list[UploadItemOutcome],
        terminal: str | None,
    ) -> UploadResult:
        from mediaflow.application.media_organizer import MediaOrganizerBatchResult

        if terminal == "paused":
            # A pause keeps the Task paused (non-terminal) with its remaining
            # items paused: the acknowledged pause boundary is the durable
            # outcome, and no aggregate is published over it.
            task = self._direct.tasks.require(task_id)
        else:
            task = self._direct.tasks.finish(task_id, MediaOrganizerBatchResult(items=()))
        status_counts = {
            UploadItemStatus.SUCCESS: 0,
            UploadItemStatus.SKIPPED: 0,
            UploadItemStatus.FAILED: 0,
            UploadItemStatus.UNCERTAIN: 0,
        }
        for outcome in outcomes:
            status_counts[outcome.status] += 1
        uncertain = status_counts[UploadItemStatus.UNCERTAIN]
        succeeded = status_counts[UploadItemStatus.SUCCESS]
        skipped = status_counts[UploadItemStatus.SKIPPED]
        failed = status_counts[UploadItemStatus.FAILED]
        if terminal in {"paused", "cancelled"}:
            aggregate = "PAUSED" if terminal == "paused" else "CANCELLED"
        elif uncertain:
            aggregate = "UNCERTAIN"
        elif failed:
            aggregate = "PARTIAL" if succeeded or skipped else "FAILED"
        elif skipped and not succeeded:
            aggregate = "SKIPPED"
        else:
            aggregate = "SUCCESS"
        return UploadResult(
            manifest_digest=state.digest,
            conflict=state.conflict,
            outcomes=tuple(outcomes),
            total_items=len(outcomes),
            succeeded_items=succeeded,
            skipped_items=skipped,
            failed_items=failed,
            status=aggregate,
            task_id=task_id,
            task_status=task.status.value,
        )


def _projection_item_status(status: TaskItemStatus) -> str:
    """Map one durable TaskItem status onto the upload projection status."""

    return {
        TaskItemStatus.PENDING: "PENDING",
        TaskItemStatus.PROCESSING: "RUNNING",
        TaskItemStatus.SUCCESS: "SUCCESS",
        TaskItemStatus.PARTIAL: "PARTIAL",
        TaskItemStatus.FAILED: "FAILED",
        TaskItemStatus.SKIPPED: "SKIPPED",
        TaskItemStatus.CANCELLED: "FAILED",
        TaskItemStatus.PAUSED: "PENDING",
    }.get(status, "FAILED")


def _terminal_item_status(status: TaskItemStatus) -> UploadItemStatus:
    """Map one durable TaskItem status onto its final per-item outcome."""

    mapped = _projection_item_status(status)
    if mapped in {"SUCCESS", "SKIPPED", "UNCERTAIN"}:
        return UploadItemStatus(mapped)
    # PENDING, RUNNING, PARTIAL, FAILED and every unknown state that never
    # proved a complete write is a refused, retry-safe item outcome.
    return UploadItemStatus.FAILED


class _ItemPayloadStream:
    """One admitted Upload item's exact payload read off its request body.

    The browser posts the item's declared bytes as the request body and sets
    the Content-Length itself, so the production journey needs no script-set
    forbidden header and no streaming ``duplex`` option.  Reads are served
    straight from the request body in bounded chunks (never a whole media
    file); the item's declared size remains the binding contract that the
    executor's bounded stream enforces.
    """

    def __init__(self, input_stream, declared_length: int | None) -> None:
        self._input = input_stream
        self._declared_length = declared_length
        self._remaining: int | None = declared_length

    def read(self, size: int = -1) -> bytes:
        if self._remaining is not None and self._remaining <= 0:
            return b""
        wanted = size if size and size > 0 else 64 * 1024
        if self._remaining is not None:
            wanted = min(wanted, self._remaining)
        chunk = self._input.read(wanted)
        if self._remaining is not None:
            self._remaining -= len(chunk)
        return chunk


class _BoundedChunkStream:
    """Serve exactly one upload item's slice of the request stream.

    The provider's ``write`` copies from this object in bounded chunks, so a
    media file is never buffered whole.  ``truncated`` turns true when the
    request body ends before the item's declared size is satisfied, which is
    how a short upload is detected without trusting the client.  The streaming
    SHA-256 digest is accumulated in the same bounded pass.
    """

    def __init__(self, source: BinaryIO, size: int, chunk_limit: int) -> None:
        self._source = source
        self._remaining = size
        self._chunk_limit = max(1, chunk_limit)
        self._digest = hashlib.sha256()
        self.consumed = 0
        self.truncated = False

    def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        wanted = self._chunk_limit if size is None or size < 0 else min(size, self._chunk_limit)
        wanted = min(wanted, self._remaining)
        chunk = self._source.read(wanted)
        if not chunk:
            self.truncated = self._remaining > 0
            self._remaining = 0
            return b""
        self._digest.update(chunk)
        self._remaining -= len(chunk)
        self.consumed += len(chunk)
        return chunk

    def digest_hex(self) -> str:
        return self._digest.hexdigest()

    def __enter__(self) -> _BoundedChunkStream:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    @property
    def closed(self) -> bool:
        return self._remaining <= 0
