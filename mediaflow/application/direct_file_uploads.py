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
from dataclasses import dataclass, field
from typing import BinaryIO

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

    # ------------------------------------------------------------------
    # Public command boundary
    # ------------------------------------------------------------------

    def upload(
        self,
        *,
        resource_library_id: str,
        manifest: Mapping[str, object],
        stream: BinaryIO,
    ) -> dict[str, object]:
        """Admit one bounded Upload and stream its items into the library.

        ``manifest`` is the interface-parsed request manifest: the
        confined ``destinationDirectory``, the explicit ``conflict``
        choice and the ordered ``items`` (relative path + declared size).
        ``stream`` serves each item's payload in manifest order; every
        payload is read in bounded chunks and handed to the executor
        without ever buffering a whole media file.  Admission performs
        zero mutation: only after the confined scope is validated and the
        durable Task exists do writes cross OrganizerExecutor.  The
        returned document is the bounded per-item result projection.
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
        result = self._execute(state, task.task_id, stream)
        document = result.document()
        document["destinationDirectory"] = destination_directory
        document["nextAction"] = self._next_action(result)
        if result.status == "UNCERTAIN":
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

    def _execute(
        self,
        state: _UploadState,
        task_id: str,
        stream: BinaryIO,
    ) -> UploadResult:
        library = state.library
        storage = state.storage
        outcomes: list[UploadItemOutcome] = []
        terminal: str | None = None  # "paused" | "cancelled" | "truncated"
        for index, item in enumerate(state.items):
            plan = state.planned[index]
            if terminal is not None:
                # A previous item set the terminal condition; every remaining
                # item keeps its own truthful outcome without touching Storage.
                category = {
                    "truncated": "upload_stream_truncated",
                    "paused": "upload_paused",
                    "cancelled": "upload_cancelled",
                }[terminal]
                outcomes.append(
                    self._record_refused(task_id, library, storage, index, plan, category)
                )
                continue
            if self._direct.tasks.cancellation_observed(task_id):
                terminal = "cancelled"
                outcomes.append(
                    self._record_refused(task_id, library, storage, index, plan, "upload_cancelled")
                )
                continue
            if self._direct.tasks.pause_requested(task_id):
                terminal = "paused"
                outcomes.append(
                    self._record_refused(task_id, library, storage, index, plan, "upload_paused")
                )
                continue
            try:
                task_item = self._direct.tasks.begin_item(
                    task_id,
                    storage.storage_id,
                    library.library_id,
                    item.relative_path,
                    item.relative_path,
                )
            except TaskPauseRequested:
                # A pause requested while the request is streaming stops at
                # this safe item boundary, with zero further mutation.
                self._direct.tasks.acknowledge_pause(task_id)
                terminal = "paused"
                outcomes.append(
                    UploadItemOutcome(
                        item.relative_path,
                        UploadItemStatus.FAILED,
                        error_category="upload_paused",
                    )
                )
                continue
            try:
                outcome, item_truncated, checksum, written_destination, category = (
                    self._execute_item(state, plan, stream)
                )
            except DirectFileUploadError as error:
                # A parent conflict or storage refusal mid-stream: this item
                # ends in its own stable failure; siblings keep going.
                self._record_item(
                    task_item,
                    plan,
                    UploadItemStatus.FAILED,
                    error.category,
                    destination=plan.destination,
                )
                outcomes.append(
                    UploadItemOutcome(
                        item.relative_path,
                        UploadItemStatus.FAILED,
                        error_category=error.category,
                    )
                )
                continue
            if item_truncated:
                terminal = "truncated"
            self._record_item(
                task_item,
                plan,
                outcome,
                category,
                checksum=checksum,
                destination=written_destination,
            )
            outcomes.append(
                UploadItemOutcome(
                    item.relative_path,
                    outcome,
                    error_category=None if outcome is UploadItemStatus.SUCCESS else category,
                    destination=written_destination,
                    checksum=checksum,
                )
            )
        return self._finalize(state, task_id, outcomes, terminal)

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
        their own truthful outcome in the response document.  A refused item
        is persisted when the Task boundary still admits it; a pause
        boundary that refuses the item itself is reported without a durable
        row, exactly like the Delete command.
        """

        try:
            task_item = self._direct.tasks.begin_item(
                task_id,
                storage.storage_id,
                library.library_id,
                plan.item.relative_path,
                plan.item.relative_path,
            )
        except TaskPauseRequested:
            self._direct.tasks.acknowledge_pause(task_id)
            return UploadItemOutcome(
                plan.item.relative_path,
                UploadItemStatus.FAILED,
                error_category=category,
            )
        self._record_item(
            task_item,
            plan,
            UploadItemStatus.FAILED,
            category,
            destination=plan.destination,
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
            # write.
            if skipped:
                return UploadItemStatus.SKIPPED, False, None, None, skip_category
            return UploadItemStatus.FAILED, False, None, None, skip_category or "target_exists"
        full = self._full_destination(library, destination)
        if item.size == 0:
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
            error = "upload destination effect unverified"
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
