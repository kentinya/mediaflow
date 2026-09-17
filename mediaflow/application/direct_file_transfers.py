"""Files direct Copy/Move transfer application service.

Admission and durable execution for the ordinary bounded Files transfer
commands.  The service resolves the exact immutable Active ResourceLibrary and
Storage of both endpoints at admission, confines and enumerates the bounded
source trees, computes deterministic destinations and conflicts, and pins every
one of those decisions into a server-side manifest whose opaque digest the
browser must return.  Execution rebuilds the manifest from live Storage and
refuses stale evidence before creating any mutation work.

Application code here only lists, stats and reads for bounded admission; every
mutation crosses ``OrganizerExecutor``, there is no hidden cross-operation
fallback, and the media pipeline (Parser, Recognition, Metadata, Naming,
Classification, Planner) is never invoked.
"""

from __future__ import annotations

import json
import posixpath
from dataclasses import dataclass

from mediaflow.application.direct_file_commands import DirectFileCommandService, DirectFileError
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.storage_browser import (
    _join_resource_library_path,
    _normalize_storage_relative_path,
)
from mediaflow.application.task_runtime import TaskPauseRequested
from mediaflow.domain.direct_files import (
    MAX_TRANSFER_BYTES,
    MAX_TRANSFER_DEPTH,
    MAX_TRANSFER_ENTRIES,
    MAX_TRANSFER_PATHS,
    MAX_TRANSFER_PROGRESS_ENTRIES,
    DirectEntryEvidence,
    TransferConflict,
    TransferConflictMode,
    TransferEntryKind,
    TransferImpact,
    TransferManifest,
    TransferManifestEntry,
    TransferOperation,
    transfer_manifest_digest,
)
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.organizer import ExecutionEffectCertainty
from mediaflow.domain.storage import Storage, StorageEntryType, StorageError, StorageErrorCode
from mediaflow.domain.task_persistence import (
    FILES_DIRECT_COMMAND_TASK,
    FILES_TRANSFER_TASK_COMMAND,
    TRANSFER_INTERRUPTED_STAGE,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)

__all__ = ["DirectFileTransferService", "DirectFileTransferError"]


@dataclass(frozen=True)
class _TransferPlan:
    """The executable per-entry decision set of one confirmed transfer.

    Normal execution builds it from the pinned manifest; the durable
    continuation of an interrupted Task rebuilds it from the persisted
    confirmed scope and revalidates it against live Storage.  Either way the
    per-entry destinations are the backend's deterministic decisions — never
    client-side joins.
    """

    operation: TransferOperation
    conflict_mode: TransferConflictMode
    same_storage: bool
    entries: tuple[TransferManifestEntry, ...]
    destinations: dict[str, str]
    top_levels: tuple[str, ...] = ()
    resuming: bool = False

    def destination_for(self, path: str) -> str | None:
        return self.destinations.get(path)


@dataclass(frozen=True)
class _ResumeContext:
    """One item's rebuilt continuation plan plus its persisted checkpoint."""

    plan: _TransferPlan
    destination: ResourceLibrary
    destination_storage: Storage
    skip_paths: frozenset[str]
    confirmed_entries: tuple[tuple[str, str, str], ...]
    confirmed_truncated: bool


def _conflict_outcome(
    mode: TransferConflictMode, path: str, destination: str, category: str
) -> dict[str, object]:
    """The truthful per-entry outcome the selected conflict mode produces.

    ``FAIL`` performs zero mutation for the affected entry, ``SKIP`` records a
    truthful skipped entry, and a keep-both destination that appeared after
    admission is never silently replaced.
    """

    if mode is TransferConflictMode.FAIL:
        status = "FAILED"
    elif mode is TransferConflictMode.SKIP:
        status = "SKIPPED"
    else:
        status = "UNCERTAIN"
        category = "keep_both_conflict_appeared"
    return {
        "path": path,
        "destination": destination,
        "status": status,
        "errorCategory": category,
        "checkpoints": [],
    }


def _item_status(entries: list[dict[str, object]]) -> str:
    """Aggregate one item's entry outcomes into its truthful item status.

    Directory creation, file transfer and emptied-source-directory removal all
    participate: an item whose every entry was skipped is itself skipped, a
    known partial mutation is partial, an unknown effect is uncertain, and
    only an item with no mutation at all is a plain failure.
    """

    statuses = {str(value["status"]) for value in entries}
    if not statuses:
        return "FAILED"
    if "UNCERTAIN" in statuses:
        return "UNCERTAIN"
    if statuses <= {"SKIPPED"}:
        return "SKIPPED"
    if "FAILED" in statuses or "PARTIAL" in statuses:
        mutated = any(value.get("checkpoints") for value in entries)
        return "PARTIAL" if mutated else "FAILED"
    return "SUCCESS"


def _item_checkpoint_evidence(entries: list[dict[str, object]]) -> tuple[str, ...]:
    """The bounded durable checkpoint annotations of one item's Result."""

    values: list[str] = []
    for outcome in entries:
        for checkpoint in outcome.get("checkpoints") or ():
            values.append(f"{checkpoint}:{outcome.get('path', '')}")
    if len(values) > MAX_TRANSFER_PROGRESS_ENTRIES:
        values = values[:MAX_TRANSFER_PROGRESS_ENTRIES]
        values.append("transfer_checkpoints_truncated")
    return tuple(values)


_ITEM_TASK_STATUS = {
    "SUCCESS": TaskItemStatus.SUCCESS,
    "SKIPPED": TaskItemStatus.SKIPPED,
    "PARTIAL": TaskItemStatus.PARTIAL,
    "UNCERTAIN": TaskItemStatus.PARTIAL,
    "FAILED": TaskItemStatus.FAILED,
}

_ITEM_KNOWN_EFFECT = {
    "SUCCESS": "transferred",
    "SKIPPED": "skipped",
    "PARTIAL": "partial",
    "UNCERTAIN": "uncertain",
    "FAILED": "retained",
}


class DirectFileTransferError(DirectFileError):
    """A stable, secret-free Copy/Move admission or execution failure.

    ``mutated`` records whether the failing continuation may already have
    completed part of its confirmed work, so recovery messaging can name a
    partial known effect instead of a clean retained state.
    """

    def __init__(self, *args: object, mutated: bool = False, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.mutated = mutated

    @property
    def details(self) -> dict[str, object]:
        document = super().details
        document["stage"] = "files_transfer"
        return document


class DirectFileTransferService:
    """Files-owned admission and execution boundary for Copy/Move transfers."""

    def __init__(
        self,
        *,
        direct_files: DirectFileCommandService,
        executor: OrganizerExecutor | None = None,
    ) -> None:
        self._direct = direct_files
        self._executor = executor or OrganizerExecutor()

    # ------------------------------------------------------------------
    # Zero-mutation impact / admission phase
    # ------------------------------------------------------------------

    def transfer_impact(
        self,
        *,
        resource_library_id: str,
        paths,
        destination_resource_library_id: str,
        destination_directory: str,
        operation: str,
        conflict_mode: str | None = None,
    ) -> TransferImpact:
        """The zero-mutation bounded impact of one proposed Copy/Move.

        Resolves both endpoints from the same pinned Active snapshot, confines
        and enumerates the bounded source scope, computes deterministic
        destinations and conflicts, and returns the pinned manifest plus its
        opaque digest.  No Task is created and no Storage mutation occurs.
        """

        manifest = self._build_manifest(
            resource_library_id=resource_library_id,
            paths=paths,
            destination_resource_library_id=destination_resource_library_id,
            destination_directory=destination_directory,
            operation=operation,
            conflict_mode=conflict_mode,
        )
        destination = self._direct.library(destination_resource_library_id)
        conflicts = self._detect_conflicts(manifest, destination)
        return TransferImpact(
            manifest=manifest,
            conflicts=conflicts,
            capability=(
                f"native_{manifest.operation.value}"
                if manifest.same_storage
                else "cross_storage_stream"
            ),
        )

    # ------------------------------------------------------------------
    # Explicitly submitted execution phase
    # ------------------------------------------------------------------

    def execute_transfer(
        self,
        *,
        resource_library_id: str,
        paths,
        destination_resource_library_id: str,
        destination_directory: str,
        operation: str,
        conflict_mode: str | None = None,
        manifest_digest: str,
    ) -> dict[str, object]:
        """Execute the confirmed bounded transfer through one durable Task.

        The live manifest is rebuilt and compared with the submitted opaque
        digest first: a stale scope returns a stable error and creates no Task
        and no mutation.  Every task item is an independently recoverable
        top-level selection; a failing item never hides a completed sibling and
        no uncertain effect is ever replayed automatically.
        """

        if not isinstance(manifest_digest, str) or not manifest_digest:
            raise DirectFileTransferError(
                "files_transfer_invalid_manifest",
                "invalid_manifest",
                "the transfer is missing the validated manifest evidence",
                resource_library_id=resource_library_id
                if isinstance(resource_library_id, str)
                else None,
                next_action="request the transfer impact summary and confirm again",
            )
        manifest = self._build_manifest(
            resource_library_id=resource_library_id,
            paths=paths,
            destination_resource_library_id=destination_resource_library_id,
            destination_directory=destination_directory,
            operation=operation,
            conflict_mode=conflict_mode,
        )
        if manifest.digest != manifest_digest:
            raise DirectFileTransferError(
                "files_transfer_stale_manifest",
                "stale_manifest",
                "the confirmed transfer scope changed since the impact summary was issued",
                status=409,
                resource_library_id=resource_library_id,
                next_action="review the refreshed transfer impact summary and confirm again",
            )
        source = self._direct.library(resource_library_id)
        destination = self._direct.library(destination_resource_library_id)
        source_storage = self._direct.open_storage(source)
        destination_storage = self._direct.open_storage(destination)
        single_file_inline = (
            len(manifest.top_level_paths) == 1
            and manifest.file_count == 1
            and manifest.directory_count == 0
            and manifest.same_storage
        )
        task = self._direct.tasks.create(
            FILES_DIRECT_COMMAND_TASK if single_file_inline else FILES_TRANSFER_TASK_COMMAND,
            execute_authorized=True,
            scope_path=(
                posixpath.commonpath(manifest.top_level_paths)
                if len(manifest.top_level_paths) > 1
                else manifest.top_level_paths[0]
            ),
            item_limit=max(1, len(manifest.top_level_paths)),
            configuration_snapshot_id=self._direct.revision.revision_id,
            configuration_snapshot_digest=self._direct.revision.digest,
        )
        plan = _TransferPlan(
            operation=manifest.operation,
            conflict_mode=manifest.conflict_mode,
            same_storage=manifest.same_storage,
            entries=manifest.entries,
            destinations=dict(manifest.destinations),
            top_levels=manifest.top_level_paths,
        )
        confirmed_scope, scope_truncated = _confirmed_entries(manifest)
        return self._run_transfer_task(
            task=task,
            plan=plan,
            confirmed_entries=confirmed_scope,
            confirmed_truncated=scope_truncated,
            source=source,
            destination=destination,
            source_storage=source_storage,
            destination_storage=destination_storage,
        )

    def _run_transfer_task(
        self,
        *,
        task,
        plan: _TransferPlan,
        confirmed_entries: tuple[tuple[str, str, str], ...],
        confirmed_truncated: bool,
        source: ResourceLibrary,
        destination: ResourceLibrary,
        source_storage: Storage,
        destination_storage: Storage,
    ) -> dict[str, object]:
        """Drive one durable transfer Task to its truthful durable outcome.

        Every top-level selection is an independently recoverable item: its
        conflict intent is revalidated at the last safe boundary (including a
        conflicting destination directory), every per-entry mutation crosses
        ``OrganizerExecutor``, pause/cancel are observed at every per-entry
        boundary, and the bounded in-flight progress is persisted after each
        entry so a process interruption leaves a known-safe checkpoint.  A
        failing item never hides a completed sibling and no uncertain effect
        is ever replayed automatically.
        """

        outcomes: list[dict[str, object]] = []
        checkpoints: list[dict[str, object]] = []
        known_effects: list[dict[str, object]] = []
        item_summaries: list[dict[str, object]] = []
        uncertain = False
        paused = False
        cancelled = False
        skipped_items = 0
        transferred_items = 0
        partial_items = 0
        failed_items = 0
        claimed: set[str] = set()
        for target in plan.top_levels:
            if self._direct.tasks.cancellation_observed(task.task_id):
                cancelled = True
                break
            root_destination = plan.destination_for(target) or target
            # Deterministic in-batch collision: a later sibling whose resolved
            # destination equals an earlier sibling's is reported through the
            # selected conflict mode instead of merging into it as if the
            # destination were an external pre-existing entry.
            batch_conflict = root_destination in claimed
            claimed.add(root_destination)
            full = _join_resource_library_path(source.root_path, target)
            try:
                item = self._direct.tasks.begin_item(
                    task.task_id,
                    source.storage_id,
                    source.library_id,
                    full,
                    target,
                )
            except TaskPauseRequested:
                self._direct.tasks.acknowledge_pause(task.task_id)
                paused = True
                break
            except Exception:
                outcomes.append(
                    {"path": target, "status": "FAILED", "errorCategory": "path_locked"}
                )
                known_effects.append({"path": target, "effect": "retained", "status": "FAILED"})
                item_summaries.append(
                    {
                        "path": target,
                        "destination": root_destination,
                        "status": "FAILED",
                        "errorCategory": "path_locked",
                    }
                )
                failed_items += 1
                continue
            item_entries, item_paused, item_cancelled = self._execute_item(
                plan=plan,
                top_level=target,
                source=source,
                destination=destination,
                source_storage=source_storage,
                destination_storage=destination_storage,
                checkpoints=checkpoints,
                task_id=task.task_id,
                item=item,
                batch_conflict=batch_conflict,
                destination_root=root_destination,
                confirmed_entries=confirmed_entries,
                confirmed_truncated=confirmed_truncated,
            )
            if item_cancelled:
                cancelled = True
                break
            if item_paused:
                self._direct.tasks.acknowledge_pause(task.task_id)
                paused = True
                break
            outcomes.extend(item_entries)
            status = _item_status(item_entries)
            unknown = status == "UNCERTAIN"
            if unknown:
                uncertain = True
            if status == "SUCCESS":
                transferred_items += 1
            elif status == "SKIPPED":
                skipped_items += 1
            elif status == "PARTIAL":
                partial_items += 1
            else:
                failed_items += 1
            self._direct.tasks.complete_direct_item(
                item,
                status=_ITEM_TASK_STATUS[status],
                operation=plan.operation.value,
                target_path=root_destination,
                error=(
                    None
                    if status == "SUCCESS"
                    else str(
                        next(
                            (
                                outcome.get("errorCategory")
                                for outcome in item_entries
                                if outcome.get("status") != "SUCCESS"
                            ),
                            "transfer_partial",
                        )
                    )
                ),
                effect_certainty=(
                    ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED.value
                    if unknown
                    else ExecutionEffectCertainty.VERIFIED_COMPLETE.value
                ),
                uncertain_effects=("mutation_outcome",) if unknown else (),
                destination_storage_id=destination.storage_id,
                completed_operations=_item_checkpoint_evidence(item_entries),
            )
            known_effects.append(
                {
                    "path": target,
                    "effect": _ITEM_KNOWN_EFFECT[status],
                    "status": status,
                }
            )
            item_summaries.append(
                {
                    "path": target,
                    "destination": root_destination,
                    "status": status,
                    **{
                        "errorCategory": outcome.get("errorCategory")
                        for outcome in item_entries
                        if outcome.get("status") != "SUCCESS" and outcome.get("errorCategory")
                    },
                }
            )
        if paused or cancelled:
            final = self._direct.tasks.require(task.task_id)
        else:
            final = self._direct.tasks.finish(task.task_id, _empty_batch())
        items = self._direct.tasks.repository.list_items(task.task_id)
        succeeded = sum(1 for item in items if item.status is TaskItemStatus.SUCCESS)
        failed_persisted = sum(
            1 for item in items if item.status in {TaskItemStatus.FAILED, TaskItemStatus.PARTIAL}
        )
        skipped_persisted = sum(1 for item in items if item.status is TaskItemStatus.SKIPPED)
        document: dict[str, object] = {
            "operation": plan.operation.value,
            "conflictMode": plan.conflict_mode.value,
            "sameStorage": plan.same_storage,
            "status": _transfer_status(
                uncertain=uncertain,
                paused=paused,
                cancelled=cancelled,
                transferred=transferred_items,
                partial=partial_items,
                skipped=skipped_items,
                failed=failed_items,
            ),
            "taskId": task.task_id,
            "taskStatus": final.status.value,
            "resourceLibraryId": source.library_id,
            "destinationResourceLibraryId": destination.library_id,
            "topLevelPaths": sorted(plan.destinations),
            "destinations": [
                {"path": path, "destination": value} for path, value in plan.destinations.items()
            ],
            "knownEffects": known_effects,
            "itemOutcomes": item_summaries[:MAX_TRANSFER_PATHS],
            "checkpoints": checkpoints[:MAX_TRANSFER_ENTRIES],
            "checkpointsTruncated": len(checkpoints) > MAX_TRANSFER_ENTRIES,
            "totalItems": len(items),
            "succeededItems": succeeded,
            "skippedItems": skipped_persisted,
            "failedItems": failed_persisted,
            "outcomes": outcomes[: MAX_TRANSFER_PATHS * 64],
            "outcomesTruncated": len(outcomes) > MAX_TRANSFER_PATHS * 64,
            "sideEffects": "storage_mutations",
            "retrySafe": False,
            "nextAction": (
                "refresh the source and destination directories to see the current state"
                if final.status.value in {"completed", "partial_success"}
                else "refresh both directories; each item keeps its own durable outcome"
            ),
        }
        if uncertain:
            document["durableState"] = "mutation_effect_uncertain"
            document["status"] = "UNCERTAIN"
            document["nextAction"] = (
                "refresh both directories and inspect the Task before any retry; "
                "uncertain effects are never replayed automatically"
            )
        return document

    # ------------------------------------------------------------------
    # Durable continuation of an interrupted transfer Task
    # ------------------------------------------------------------------

    def resume_transfer(self, task_id: str) -> dict[str, object]:
        """Continue one paused or interrupted Files transfer Task.

        Continuation proceeds only from each item's persisted known-safe
        checkpoint: the confirmed per-entry scope recorded with the item must
        still match live Storage exactly, completed entries are never replayed,
        recorded uncertain effects stop the item with an investigation state,
        and keep-both renames (whose unique names are admission-pinned) are
        never re-derived.  Work outside the confirmed scope is never picked up;
        a scope that changed stops that item with an actionable state instead
        of expanding the confirmed transfer.
        """

        task = self._direct.tasks.require(task_id)
        if task.command != FILES_TRANSFER_TASK_COMMAND:
            raise DirectFileTransferError(
                "files_transfer_resume_unavailable",
                "resume_unavailable",
                "only a bounded Files transfer Task can be continued this way",
                status=409,
                next_action="inspect the Task in Operations",
            )
        if task.status is PersistentTaskStatus.RUNNING:
            raise DirectFileTransferError(
                "files_transfer_resume_running",
                "resume_running",
                "the transfer Task still reports a running execution; it must not be started twice",
                status=409,
                next_action="refresh the Task state and wait for it to finish or cancel it",
            )
        if task.status is not PersistentTaskStatus.PAUSED:
            raise DirectFileTransferError(
                "files_transfer_resume_unavailable",
                "resume_unavailable",
                "the transfer Task has no continuable paused work",
                status=409,
                next_action="submit a fresh bounded transfer instead",
            )
        current = self._direct.revision
        if (
            task.configuration_snapshot_id != current.revision_id
            or task.configuration_snapshot_digest != current.digest
        ):
            raise DirectFileTransferError(
                "files_transfer_resume_stale_snapshot",
                "resume_stale_snapshot",
                "the paused transfer was admitted against a different Active configuration",
                status=409,
                next_action=(
                    "submit a fresh bounded transfer against the current Active configuration"
                ),
            )
        items = self._direct.tasks.repository.list_items(task.task_id)
        continuable = [
            item
            for item in items
            if item.status
            in {TaskItemStatus.PAUSED, TaskItemStatus.PROCESSING, TaskItemStatus.PENDING}
        ]
        if not continuable:
            raise DirectFileTransferError(
                "files_transfer_resume_unavailable",
                "resume_unavailable",
                "the paused transfer has no continuable item",
                status=409,
                next_action="inspect the recorded per-item outcomes and submit a fresh transfer",
            )
        for item in continuable:
            payload = _progress_payload(item)
            if payload is None:
                continue
            if payload.get("conflictMode") == TransferConflictMode.KEEP_BOTH.value:
                raise DirectFileTransferError(
                    "files_transfer_resume_unavailable",
                    "resume_unavailable",
                    "the keep-both destination names were pinned at admission and cannot be "
                    "re-derived after an interruption",
                    status=409,
                    next_action=(
                        "inspect the recorded per-item outcomes and submit a fresh keep-both "
                        "transfer for the remaining entries"
                    ),
                )
        source = self._direct.library(continuable[0].resource_library_id)
        self._direct.tasks.reopen(task.task_id, execute=True)
        outcomes: list[dict[str, object]] = []
        checkpoints: list[dict[str, object]] = []
        known_effects: list[dict[str, object]] = []
        uncertain = False
        paused = False
        cancelled = False
        transferred_items = 0
        partial_items = 0
        skipped_items = 0
        failed_items = 0
        source_storage = self._direct.open_storage(source)
        operation_value = "transfer"
        destination_library_id = ""
        for item in continuable:
            if self._direct.tasks.cancellation_observed(task.task_id):
                cancelled = True
                break
            try:
                context = self._resume_item_plan(item)
            except DirectFileTransferError as error:
                if error.category != "scope_changed":
                    raise
                self._mark_interrupted_item(item, error.code, mutated=error.mutated)
                if error.mutated:
                    partial_items += 1
                    known_effects.append(
                        {
                            "path": item.source_display,
                            "effect": "partial",
                            "status": "PARTIAL",
                        }
                    )
                else:
                    failed_items += 1
                    known_effects.append(
                        {
                            "path": item.source_display,
                            "effect": "retained",
                            "status": "FAILED",
                        }
                    )
                continue
            if context is None:
                # No persisted known-safe checkpoint: the item is an explicit
                # interrupted/investigation state, never a blind retry.
                self._mark_interrupted_item(item, "files_transfer_interrupted_unknown")
                uncertain = True
                known_effects.append(
                    {
                        "path": item.source_display,
                        "effect": "uncertain",
                        "status": "UNCERTAIN",
                    }
                )
                continue
            operation_value = context.plan.operation.value
            destination_library_id = context.destination.library_id
            try:
                resumed_item = self._direct.tasks.begin_item(
                    task.task_id,
                    source.storage_id,
                    source.library_id,
                    _join_resource_library_path(source.root_path, item.source_display),
                    item.source_display,
                )
            except TaskPauseRequested:
                self._direct.tasks.acknowledge_pause(task.task_id)
                paused = True
                break
            except Exception:
                failed_items += 1
                known_effects.append(
                    {
                        "path": item.source_display,
                        "effect": "retained",
                        "status": "FAILED",
                    }
                )
                continue
            item_entries, item_paused, item_cancelled = self._execute_item(
                plan=context.plan,
                top_level=item.source_display,
                source=source,
                destination=context.destination,
                source_storage=source_storage,
                destination_storage=context.destination_storage,
                checkpoints=checkpoints,
                task_id=task.task_id,
                item=resumed_item,
                batch_conflict=False,
                destination_root=context.plan.destinations.get(item.source_display, ""),
                confirmed_entries=context.confirmed_entries,
                confirmed_truncated=context.confirmed_truncated,
                skip_paths=context.skip_paths,
            )
            if item_cancelled:
                cancelled = True
                break
            if item_paused:
                self._direct.tasks.acknowledge_pause(task.task_id)
                paused = True
                break
            outcomes.extend(item_entries)
            status = _item_status(item_entries)
            unknown = status == "UNCERTAIN"
            if unknown:
                uncertain = True
            if status == "SUCCESS":
                transferred_items += 1
            elif status == "SKIPPED":
                skipped_items += 1
            elif status == "PARTIAL":
                partial_items += 1
            else:
                failed_items += 1
            self._direct.tasks.complete_direct_item(
                resumed_item,
                status=_ITEM_TASK_STATUS[status],
                operation=context.plan.operation.value,
                target_path=context.plan.destinations.get(item.source_display, item.source_display),
                error=(
                    None
                    if status == "SUCCESS"
                    else str(
                        next(
                            (
                                outcome.get("errorCategory")
                                for outcome in item_entries
                                if outcome.get("status") != "SUCCESS"
                            ),
                            "transfer_partial",
                        )
                    )
                ),
                effect_certainty=(
                    ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED.value
                    if unknown
                    else ExecutionEffectCertainty.VERIFIED_COMPLETE.value
                ),
                uncertain_effects=("mutation_outcome",) if unknown else (),
                destination_storage_id=context.destination.storage_id,
                completed_operations=_item_checkpoint_evidence(item_entries),
            )
            known_effects.append(
                {
                    "path": item.source_display,
                    "effect": _ITEM_KNOWN_EFFECT[status],
                    "status": status,
                }
            )
        if paused or cancelled:
            final = self._direct.tasks.require(task.task_id)
        else:
            final = self._direct.tasks.finish(task.task_id, _empty_batch())
        persisted = self._direct.tasks.repository.list_items(task.task_id)
        document: dict[str, object] = {
            "operation": operation_value,
            "resumed": True,
            "status": _transfer_status(
                uncertain=uncertain,
                paused=paused,
                cancelled=cancelled,
                transferred=transferred_items,
                partial=partial_items,
                skipped=skipped_items,
                failed=failed_items,
            ),
            "taskId": task.task_id,
            "taskStatus": final.status.value,
            "resourceLibraryId": source.library_id,
            "destinationResourceLibraryId": destination_library_id,
            "topLevelPaths": [item.source_display for item in continuable],
            "knownEffects": known_effects,
            "checkpoints": checkpoints[:MAX_TRANSFER_ENTRIES],
            "checkpointsTruncated": len(checkpoints) > MAX_TRANSFER_ENTRIES,
            "totalItems": len(persisted),
            "succeededItems": sum(1 for item in persisted if item.status is TaskItemStatus.SUCCESS),
            "skippedItems": sum(1 for item in persisted if item.status is TaskItemStatus.SKIPPED),
            "failedItems": sum(
                1
                for item in persisted
                if item.status in {TaskItemStatus.FAILED, TaskItemStatus.PARTIAL}
            ),
            "outcomes": outcomes[: MAX_TRANSFER_PATHS * 64],
            "outcomesTruncated": len(outcomes) > MAX_TRANSFER_PATHS * 64,
            "sideEffects": "storage_mutations",
            "retrySafe": False,
            "nextAction": (
                "refresh both directories; each item keeps its own durable outcome"
                if paused or cancelled
                else "refresh the source and destination directories to see the current state"
            ),
        }
        if uncertain:
            document["durableState"] = "mutation_effect_uncertain"
            document["status"] = "UNCERTAIN"
            document["nextAction"] = (
                "an interrupted item could not be safely continued; inspect the Task and "
                "submit a fresh transfer for the remaining entries"
            )
        return document

    def _mark_interrupted_item(
        self, item: PersistentTaskItem, code: str, *, mutated: bool = False
    ) -> None:
        """Record one item as an explicit interrupted/investigation state.

        The item is never marked as a clean failure or a replayable retry: its
        recorded effects stay authoritative and the code names exactly why the
        continuation stopped.
        """

        self._direct.tasks.complete_direct_item(
            item,
            status=TaskItemStatus.PARTIAL if mutated else TaskItemStatus.FAILED,
            operation="transfer",
            error=code,
            effect_certainty=(
                ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED.value
                if mutated or code == "files_transfer_interrupted_unknown"
                else ExecutionEffectCertainty.VERIFIED_COMPLETE.value
            ),
            uncertain_effects=("mutation_outcome",) if mutated else (),
            stage=TRANSFER_INTERRUPTED_STAGE,
        )

    def _resume_item_plan(self, item: PersistentTaskItem) -> _ResumeContext | None:
        """Rebuild one item's confirmed plan from its persisted checkpoint.

        Returns ``None`` when the item has no usable persisted checkpoint.  A
        confirmed scope that no longer matches live Storage raises a fail-closed
        ``scope_changed`` error so the continuation never expands the confirmed
        transfer, and a recorded uncertain effect is never replayed.
        """

        payload = _progress_payload(item)
        if payload is None:
            return None
        try:
            operation = TransferOperation(str(payload.get("operation")))
            conflict_mode = TransferConflictMode(str(payload.get("conflictMode")))
        except (TypeError, ValueError):
            return None
        destination_path_value = payload.get("destinationPath")
        destination_library_id = payload.get("destinationResourceLibraryId")
        if not isinstance(destination_path_value, str) or not isinstance(
            destination_library_id, str
        ):
            return None
        confirmed = payload.get("confirmedEntries")
        if payload.get("confirmedTruncated") is True or not isinstance(confirmed, list):
            raise DirectFileTransferError(
                "files_transfer_resume_scope_changed",
                "scope_changed",
                "the interrupted item's confirmed scope is not fully recorded, so it cannot "
                "be safely continued",
                status=409,
                next_action="inspect the recorded outcomes and submit a fresh bounded transfer",
                mutated=False,
            )
        try:
            destination = self._direct.library(destination_library_id)
        except DirectFileError:
            raise DirectFileTransferError(
                "files_transfer_resume_scope_changed",
                "scope_changed",
                "the paused transfer's destination ResourceLibrary is not part of the pinned "
                "Active configuration",
                status=409,
                next_action=(
                    "submit a fresh bounded transfer against the current Active configuration"
                ),
                mutated=False,
            ) from None
        destination_storage = self._direct.open_storage(destination)
        source = self._direct.library(item.resource_library_id)
        source_storage = self._direct.open_storage(source)
        top_level = item.source_display
        try:
            observed = self._observed_entry(source, source_storage, top_level)
        except DirectFileTransferError as error:
            raise DirectFileTransferError(
                "files_transfer_resume_scope_changed",
                "scope_changed",
                "the interrupted item's source is no longer observable",
                status=409,
                next_action="inspect the source directory and submit a fresh bounded transfer",
                mutated=bool(payload.get("completedEntries")),
            ) from error
        if observed.entry_type is StorageEntryType.SYMLINK:
            raise DirectFileTransferError(
                "files_transfer_resume_scope_changed",
                "scope_changed",
                "the interrupted item's source changed type",
                status=409,
                next_action="inspect the source directory and submit a fresh bounded transfer",
                mutated=bool(payload.get("completedEntries")),
            )
        entries: list[TransferManifestEntry] = []
        destination_pairs: list[tuple[str, str]] = []
        kind = (
            TransferEntryKind.DIRECTORY
            if observed.entry_type is StorageEntryType.DIRECTORY
            else TransferEntryKind.FILE
        )
        entries.append(
            TransferManifestEntry(
                path=top_level,
                kind=kind,
                size=observed.size,
                modified_at=observed.modified_at.isoformat(),
                fingerprint=getattr(observed, "fingerprint", None) or "",
            )
        )
        destination_pairs.append((top_level, destination_path_value))
        if kind is TransferEntryKind.DIRECTORY:
            self._enumerate_directory(
                source,
                source_storage,
                top_level,
                destination_path_value,
                entries,
                destination_pairs,
            )
        confirmed_set = {(str(value[0]), str(value[1]), str(value[2])) for value in confirmed}
        destinations = dict(destination_pairs)
        fresh_set = {
            (entry.path, destinations.get(entry.path, entry.path), entry.kind.value)
            for entry in entries
        }
        skip: set[str] = set()
        for value in payload.get("entries") or ():
            if not isinstance(value, dict):
                continue
            path = str(value.get("path", ""))
            status = str(value.get("status", ""))
            if status == "UNCERTAIN":
                raise DirectFileTransferError(
                    "files_transfer_resume_uncertain",
                    "scope_changed",
                    "the interrupted item recorded an uncertain effect that must not be replayed",
                    status=409,
                    next_action=("inspect the source and destination directories before any retry"),
                    mutated=True,
                )
            if status == "SUCCESS" and path in {value[0] for value in confirmed_set}:
                # The completed effect stays terminal; its source may already
                # be gone, which is exactly why the fresh enumeration misses it.
                skip.add(path)
        completed = {value for value in confirmed_set if value[0] in skip}
        # The fresh enumeration may legitimately miss confirmed entries whose
        # verified transfer already removed the source; anything else that
        # differs - a new source entry or a lost completed entry - means the
        # scope changed and the continuation stops instead of expanding it.
        if confirmed_set - fresh_set - completed or fresh_set - confirmed_set:
            raise DirectFileTransferError(
                "files_transfer_resume_scope_changed",
                "scope_changed",
                "the source or destination scope changed since the transfer was admitted",
                status=409,
                next_action="inspect both directories and submit a fresh bounded transfer",
                mutated=bool(completed),
            )
        plan = _TransferPlan(
            operation=operation,
            conflict_mode=conflict_mode,
            same_storage=source.storage_id == destination.storage_id,
            entries=tuple(entries),
            destinations=destinations,
            top_levels=(top_level,),
            resuming=True,
        )
        confirmed_scope = tuple(
            (str(value[0]), str(value[1]), str(value[2]))
            for value in confirmed[:MAX_TRANSFER_PROGRESS_ENTRIES]
        )
        return _ResumeContext(
            plan=plan,
            destination=destination,
            destination_storage=destination_storage,
            skip_paths=frozenset(skip),
            confirmed_entries=confirmed_scope,
            confirmed_truncated=False,
        )

    # ------------------------------------------------------------------
    # Manifest construction
    # ------------------------------------------------------------------

    def _build_manifest(
        self,
        *,
        resource_library_id: str,
        paths,
        destination_resource_library_id: str,
        destination_directory: str,
        operation: str,
        conflict_mode: str | None,
    ) -> TransferManifest:
        try:
            transfer_operation = TransferOperation(operation)
        except (TypeError, ValueError):
            raise DirectFileTransferError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the requested transfer operation is not supported",
                resource_library_id=(
                    resource_library_id if isinstance(resource_library_id, str) else None
                ),
                next_action="choose Copy or Move and retry",
            ) from None
        try:
            mode = (
                TransferConflictMode(conflict_mode)
                if conflict_mode is not None
                else TransferConflictMode.FAIL
            )
        except (TypeError, ValueError):
            raise DirectFileTransferError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the requested destination-conflict choice is not supported",
                resource_library_id=(
                    resource_library_id if isinstance(resource_library_id, str) else None
                ),
                next_action="choose no-overwrite, skip or keep-both and retry",
            ) from None
        source = self._direct.library(resource_library_id)
        destination = self._direct.library(destination_resource_library_id)
        targets = self._transfer_targets(source, paths)
        destination_relative = self._destination_directory(destination, destination_directory)
        source_storage = self._direct.open_storage(source)
        destination_storage = self._direct.open_storage(destination)
        same_storage = source.storage_id == destination.storage_id
        self._require_capability(
            transfer_operation, same_storage, source_storage, destination_storage
        )
        self._require_destination_directory(destination, destination_storage, destination_relative)
        entries: list[TransferManifestEntry] = []
        destinations: list[tuple[str, str]] = []
        keep_both_names: list[tuple[str, str]] = []
        assigned: set[str] = set()
        for target in targets:
            observed = self._observed_entry(source, source_storage, target)
            if observed.entry_type is StorageEntryType.SYMLINK:
                raise self._unsupported_entry(source, target, "symbolic links are not transferable")
            destination_path = self._destination_path(
                destination_relative, posixpath.basename(target)
            )
            self._require_no_overlap(source, destination, target, destination_path)
            if mode is TransferConflictMode.KEEP_BOTH and (
                destination_path in assigned
                or self._destination_exists(
                    destination_storage,
                    self._full_destination(destination, destination_path),
                    observed.entry_type,
                )
            ):
                # Keep-both names are pinned against both live Storage and the
                # destinations already assigned inside this batch, so two
                # selected roots with the same basename can never collide.
                destination_path = self._unique_destination_name(
                    destination_storage,
                    destination,
                    destination_path,
                    observed.entry_type,
                    assigned,
                )
                keep_both_names.append((target, destination_path))
            assigned.add(destination_path)
            destinations.append((target, destination_path))
            if observed.entry_type is StorageEntryType.DIRECTORY:
                entries.append(self._manifest_entry(target, observed, TransferEntryKind.DIRECTORY))
                self._enumerate_directory(
                    source, source_storage, target, destination_path, entries, destinations
                )
            else:
                entries.append(self._manifest_entry(target, observed, TransferEntryKind.FILE))
            self._enforce_transfer_limits(source, entries)
        digest = self._manifest_digest(
            source,
            destination,
            targets,
            entries,
            destinations,
            transfer_operation,
            mode,
            destination_relative,
        )
        return TransferManifest(
            revision_id=self._direct.revision.revision_id,
            revision_digest=self._direct.revision.digest,
            source_resource_library_id=source.library_id,
            source_storage_id=source.storage_id,
            source_root=source.root_path,
            destination_resource_library_id=destination.library_id,
            destination_storage_id=destination.storage_id,
            destination_root=destination.root_path,
            destination_directory=destination_relative,
            operation=transfer_operation,
            conflict_mode=mode,
            same_storage=same_storage,
            top_level_paths=targets,
            entries=tuple(entries),
            destinations=tuple(destinations),
            keep_both_names=tuple(keep_both_names),
            digest=digest,
        )

    def _enumerate_directory(
        self,
        source: ResourceLibrary,
        storage: Storage,
        relative: str,
        destination_path: str,
        entries: list[TransferManifestEntry],
        destinations: list[tuple[str, str]],
    ) -> None:
        """Append the bounded flattened transfer scope of one directory tree.

        Every visited directory is a direct child of its confirmed parent, every
        entry is a regular file or directory, and the item/depth/byte bounds are
        enforced as the walk proceeds so an unbounded tree stops before any
        mutation is authorized.
        """

        stack: list[tuple[str, str, int]] = [(relative, destination_path, 0)]
        while stack:
            current, current_destination, depth = stack.pop()
            full = _join_resource_library_path(source.root_path, current)
            try:
                children = tuple(storage.list(full))
            except StorageError as error:
                raise self._storage_admission_failure(source, current, error) from None
            except OSError as error:
                raise self._storage_admission_failure(
                    source, current, StorageError(StorageErrorCode.IO_ERROR, "list", full)
                ) from error
            for child in children:
                if child.path != posixpath.join(current, child.name):
                    raise DirectFileTransferError(
                        "files_transfer_invalid_path",
                        "invalid_path",
                        "a source entry is not a direct child of its directory",
                        resource_library_id=source.library_id,
                        path=current,
                        next_action="refresh the directory and retry",
                    )
                if child.entry_type is StorageEntryType.SYMLINK:
                    raise self._unsupported_entry(
                        source, child.path, "symbolic links are not transferable"
                    )
                if child.entry_type not in {StorageEntryType.FILE, StorageEntryType.DIRECTORY}:
                    raise self._unsupported_entry(source, child.path, "unsupported entry type")
                child_destination = posixpath.join(current_destination, child.name)
                destinations.append((child.path, child_destination))
                if child.entry_type is StorageEntryType.DIRECTORY:
                    if depth + 1 > MAX_TRANSFER_DEPTH:
                        raise self._limit_error(source, "transfer_depth_limit_exceeded")
                    entries.append(
                        self._manifest_entry(child.path, child, TransferEntryKind.DIRECTORY)
                    )
                    stack.append((child.path, child_destination, depth + 1))
                else:
                    entries.append(self._manifest_entry(child.path, child, TransferEntryKind.FILE))
                self._enforce_transfer_limits(source, entries)

    @staticmethod
    def _manifest_entry(path: str, entry, kind: TransferEntryKind) -> TransferManifestEntry:
        return TransferManifestEntry(
            path=path,
            kind=kind,
            size=entry.size,
            modified_at=entry.modified_at.isoformat(),
            fingerprint=getattr(entry, "fingerprint", None) or "",
        )

    def _manifest_digest(
        self,
        source: ResourceLibrary,
        destination: ResourceLibrary,
        targets: tuple[str, ...],
        entries: list[TransferManifestEntry],
        destinations: list[tuple[str, str]],
        operation: TransferOperation,
        mode: TransferConflictMode,
        destination_directory: str,
    ) -> str:
        return transfer_manifest_digest(
            {
                "revisionId": self._direct.revision.revision_id,
                "revisionDigest": self._direct.revision.digest,
                "sourceLibraryId": source.library_id,
                "sourceStorageId": source.storage_id,
                "sourceRoot": source.root_path,
                "destinationLibraryId": destination.library_id,
                "destinationStorageId": destination.storage_id,
                "destinationRoot": destination.root_path,
                "destinationDirectory": destination_directory,
                "operation": operation.value,
                "conflictMode": mode.value,
                "topLevelPaths": list(targets),
                "entries": [
                    [
                        entry.path,
                        entry.kind.value,
                        entry.size,
                        entry.modified_at,
                        entry.fingerprint,
                    ]
                    for entry in sorted(entries, key=lambda value: value.path)
                ],
                "destinations": [[path, value] for path, value in destinations],
            }
        )

    # ------------------------------------------------------------------
    # Admission helpers
    # ------------------------------------------------------------------

    def _transfer_targets(self, source: ResourceLibrary, paths) -> tuple[str, ...]:
        if not isinstance(paths, (list, tuple)) or not paths:
            raise DirectFileTransferError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the transfer requires at least one selected source path",
                resource_library_id=source.library_id,
                next_action="select one or more files or directories and retry",
            )
        if len(paths) > MAX_TRANSFER_PATHS:
            raise DirectFileTransferError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the transfer selection exceeds the bounded multi-selection limit",
                resource_library_id=source.library_id,
                next_action=f"transfer at most {MAX_TRANSFER_PATHS} items per command",
            )
        normalized = tuple(self._direct.relative_path(path) for path in paths)
        if any(not path for path in normalized):
            raise DirectFileTransferError(
                "files_transfer_root_protected",
                "root_protected",
                "the ResourceLibrary root cannot be transferred",
                resource_library_id=source.library_id,
                next_action="select entries inside the ResourceLibrary instead",
            )
        unique = sorted(set(normalized))
        if len(unique) != len(normalized):
            raise DirectFileTransferError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the transfer selection contains duplicate paths",
                resource_library_id=source.library_id,
                next_action="remove duplicate selections and retry",
            )
        for index, path in enumerate(unique):
            for other in unique[index + 1 :]:
                if other.startswith(f"{path}/"):
                    raise DirectFileTransferError(
                        "files_transfer_invalid_request",
                        "invalid_request",
                        "the transfer selection nests a path inside another selected path",
                        resource_library_id=source.library_id,
                        path=path,
                        next_action="select the outermost item only and retry",
                    )
        return tuple(unique)

    def _destination_directory(self, destination: ResourceLibrary, value: object) -> str:
        try:
            return _normalize_storage_relative_path(value if value is not None else "")
        except ValueError as error:
            raise DirectFileTransferError(
                "files_transfer_invalid_path",
                "invalid_path",
                "the destination directory is not a safe ResourceLibrary-relative path",
                resource_library_id=destination.library_id,
                next_action="navigate inside the destination ResourceLibrary and retry",
            ) from error

    def _require_destination_directory(
        self, destination: ResourceLibrary, storage: Storage, relative: str
    ) -> None:
        """The chosen destination directory must exist inside the destination library."""

        if relative == "":
            return
        full = _join_resource_library_path(destination.root_path, relative)
        try:
            entry = storage.stat(full)
        except StorageError as error:
            if error.code is StorageErrorCode.NOT_FOUND:
                raise DirectFileTransferError(
                    "files_transfer_not_a_directory",
                    "not_a_directory",
                    "the destination directory does not exist",
                    status=404,
                    resource_library_id=destination.library_id,
                    path=relative,
                    next_action="choose an existing destination directory",
                ) from None
            raise self._storage_admission_failure(destination, relative, error) from None
        if entry.entry_type is not StorageEntryType.DIRECTORY:
            raise DirectFileTransferError(
                "files_transfer_not_a_directory",
                "not_a_directory",
                "the destination is not a directory",
                resource_library_id=destination.library_id,
                path=relative,
                next_action="choose an existing destination directory",
            )

    def _observed_entry(self, library: ResourceLibrary, storage: Storage, relative: str):
        full = _join_resource_library_path(library.root_path, relative)
        try:
            return storage.stat(full)
        except StorageError as error:
            raise self._storage_admission_failure(library, relative, error) from None
        except OSError as error:
            raise self._storage_admission_failure(
                library, relative, StorageError(StorageErrorCode.IO_ERROR, "stat", full)
            ) from error

    @staticmethod
    def _destination_path(destination_directory: str, name: str) -> str:
        return posixpath.join(destination_directory, name) if destination_directory else name

    @staticmethod
    def _full_destination(destination: ResourceLibrary, destination_path: str) -> str:
        """The confined Storage-relative path of one logical destination.

        Destination state checks must observe the exact physical location the
        mutation will touch: the destination ResourceLibrary root plus its
        relative path.  A bare library-relative path silently observes the
        wrong location whenever the destination library is not mounted at the
        Storage root.
        """

        return _join_resource_library_path(destination.root_path, destination_path)

    def _require_no_overlap(
        self,
        source: ResourceLibrary,
        destination: ResourceLibrary,
        target: str,
        destination_path: str,
    ) -> None:
        """Refuse a same-Storage transfer into itself or one of its descendants.

        The comparison uses the fully resolved confined logical Storage paths
        (ResourceLibrary root plus relative path), so distinct ResourceLibrary
        roots on one Storage neither falsely reject distinct destinations nor
        miss a physical self/descendant overlap.
        """

        if source.storage_id != destination.storage_id:
            return
        resolved_source = posixpath.normpath(_join_resource_library_path(source.root_path, target))
        resolved_destination = posixpath.normpath(
            _join_resource_library_path(destination.root_path, destination_path)
        )
        if resolved_source == resolved_destination or resolved_destination.startswith(
            f"{resolved_source}/"
        ):
            raise DirectFileTransferError(
                "files_transfer_overlap",
                "overlap",
                "the destination is the source itself or one of its descendants",
                resource_library_id=source.library_id,
                path=target,
                next_action="choose a destination outside the transferred directory",
            )
        if resolved_source.startswith(f"{resolved_destination}/"):
            raise DirectFileTransferError(
                "files_transfer_overlap",
                "overlap",
                "the destination is a descendant of a selected source directory",
                resource_library_id=source.library_id,
                path=target,
                next_action="choose a destination outside the transferred directory",
            )

    @staticmethod
    def _destination_exists(
        storage: Storage, destination_path: str, entry_type: StorageEntryType
    ) -> bool:
        try:
            if storage.exists(destination_path):
                return True
            if entry_type is StorageEntryType.DIRECTORY:
                # A conflicting regular file at the same name still blocks a
                # directory transfer through its (virtual) directory entry.
                storage.stat(destination_path)
                return True
        except StorageError as error:
            if error.code is StorageErrorCode.NOT_FOUND:
                return False
            raise
        return False

    def _unique_destination_name(
        self,
        storage: Storage,
        destination: ResourceLibrary,
        destination_path: str,
        entry_type: StorageEntryType,
        assigned: set[str] | None = None,
    ) -> str:
        parent = posixpath.dirname(destination_path)
        name = posixpath.basename(destination_path)
        stem, dot, suffix = name.rpartition(".")
        base = stem if dot else name
        extension = f".{suffix}" if dot else ""
        reserved = assigned or set()
        for index in range(1, 1000):
            candidate_name = f"{base} ({index}){extension}"
            candidate = posixpath.join(parent, candidate_name) if parent else candidate_name
            if candidate not in reserved and not self._destination_exists(
                storage,
                self._full_destination(destination, candidate),
                entry_type,
            ):
                return candidate
        raise DirectFileTransferError(
            "files_transfer_conflict_limit",
            "conflict_limit",
            "no safe keep-both destination name is available",
            next_action="choose a different destination directory",
        )

    def _enforce_transfer_limits(
        self, library: ResourceLibrary, entries: list[TransferManifestEntry]
    ) -> None:
        if len(entries) > MAX_TRANSFER_ENTRIES:
            raise self._limit_error(library, "transfer_entry_limit_exceeded")
        total = sum(entry.size for entry in entries if not entry.is_directory)
        if total > MAX_TRANSFER_BYTES:
            raise self._limit_error(library, "transfer_size_limit_exceeded")

    def _require_capability(
        self,
        operation: TransferOperation,
        same_storage: bool,
        source_storage: Storage,
        destination_storage: Storage,
    ) -> None:
        """Admit only the operation the provider truthfully advertises.

        A same-Storage Copy needs the provider's native ``copy`` and a
        same-Storage Move its native ``move``; a cross-Storage Copy needs a
        writable target and a cross-Storage Move additionally needs the source
        provider's ``delete`` for the compound source deletion.
        """

        target = source_storage if same_storage else destination_storage
        if getattr(target, "read_only", False):
            raise DirectFileTransferError(
                "files_transfer_capability_denied",
                "capability_denied",
                "the destination Storage is read-only",
                status=403,
                next_action="select a writable destination ResourceLibrary",
            )
        if not same_storage:
            if operation is TransferOperation.MOVE:
                source_capabilities = getattr(source_storage, "capabilities", None)
                if source_capabilities is not None and not source_capabilities.can_delete:
                    raise DirectFileTransferError(
                        "files_transfer_unsupported_capability",
                        "unsupported_capability",
                        "the source Storage cannot delete the source a cross-Storage Move requires",
                        status=400,
                        next_action="use Copy, or choose a provider that supports Delete",
                    )
            return
        capabilities = getattr(target, "capabilities", None)
        if capabilities is None:
            return
        if operation is TransferOperation.COPY and not capabilities.can_copy:
            raise self._unsupported_operation("native Copy")
        if operation is TransferOperation.MOVE and not capabilities.can_move:
            raise self._unsupported_operation("native Move")

    def _unsupported_operation(self, label: str) -> DirectFileTransferError:
        return DirectFileTransferError(
            "files_transfer_unsupported_capability",
            "unsupported_capability",
            f"this Storage provider does not advertise a {label} operation",
            status=400,
            next_action="choose a provider that supports the requested operation",
        )

    def _detect_conflicts(
        self, manifest: TransferManifest, destination: ResourceLibrary
    ) -> tuple[TransferConflict, ...]:
        """The current conflict truth of the confirmed top-level destinations.

        Nested entries cannot conflict while their root destination is fresh,
        so the item-level conflicts are the top-level destinations plus the
        deterministic in-batch collisions between two selected roots.
        """

        resolution = {
            TransferConflictMode.FAIL: "fail_no_overwrite",
            TransferConflictMode.SKIP: "skip",
            TransferConflictMode.KEEP_BOTH: "keep_both",
        }[manifest.conflict_mode]
        conflicts: list[TransferConflict] = []
        claimed: set[str] = set()
        top_levels = set(manifest.top_level_paths)
        destination_storage = self._direct.open_storage(destination)
        for path, destination_path in manifest.destinations:
            if path not in top_levels or not destination_path:
                continue
            if destination_path in claimed:
                # Two selected roots resolve to the same destination basename:
                # the later sibling is reported as a batch-internal conflict
                # instead of being misread as an external or uncertain effect.
                conflicts.append(
                    TransferConflict(
                        path=path, destination=destination_path, resolution="batch_conflict"
                    )
                )
                continue
            claimed.add(destination_path)
            try:
                exists = destination_storage.exists(
                    self._full_destination(destination, destination_path)
                )
            except (StorageError, OSError):
                conflicts.append(
                    TransferConflict(path=path, destination=destination_path, resolution="unknown")
                )
                continue
            if exists:
                conflicts.append(
                    TransferConflict(path=path, destination=destination_path, resolution=resolution)
                )
        return tuple(conflicts)

    # ------------------------------------------------------------------
    # Per-item execution
    # ------------------------------------------------------------------

    def _execute_item(
        self,
        *,
        plan: _TransferPlan,
        top_level: str,
        source: ResourceLibrary,
        destination: ResourceLibrary,
        source_storage: Storage,
        destination_storage: Storage,
        checkpoints: list[dict[str, object]],
        task_id: str,
        item: PersistentTaskItem,
        batch_conflict: bool,
        destination_root: str,
        confirmed_entries: tuple[tuple[str, str, str], ...] = (),
        confirmed_truncated: bool = False,
        skip_paths: frozenset[str] = frozenset(),
    ) -> tuple[list[dict[str, object]], bool, bool]:
        """Run one top-level selection to its truthful per-entry outcomes.

        Returns ``(entry outcomes, pause observed, cancellation observed)``.
        The selected conflict mode applies to the top-level destination itself
        — including a directory — and is revalidated fresh at this last safe
        boundary, so a conflicting destination directory is never merged
        entry-by-entry and a directory Move removes no source entry when the
        selected behavior says the item must fail or skip.  Every mutation
        crosses ``OrganizerExecutor``; pause/cancel are observed at every
        per-entry boundary and the bounded in-flight progress is persisted
        after each recorded entry so an interruption leaves a known-safe
        checkpoint instead of an unknown state.
        """

        entries = [
            entry
            for entry in plan.entries
            if entry.path == top_level or entry.path.startswith(f"{top_level}/")
        ]
        recorded: list[dict[str, object]] = []

        def progress() -> None:
            self._record_progress(
                item,
                destination=destination,
                destination_root=destination_root,
                plan=plan,
                recorded=recorded,
                skip_count=len(skip_paths),
                confirmed_entries=confirmed_entries,
                confirmed_truncated=confirmed_truncated,
            )

        def interruption() -> str | None:
            if self._direct.tasks.cancellation_observed(task_id):
                return "cancel"
            if self._direct.tasks.pause_requested(task_id):
                return "pause"
            return None

        if batch_conflict:
            recorded.append(
                _conflict_outcome(plan.conflict_mode, top_level, destination_root, "batch_conflict")
            )
            progress()
            return recorded, False, False
        root_entry = next((value for value in entries if value.path == top_level), None)
        root_kind = (
            StorageEntryType.DIRECTORY
            if root_entry is not None and root_entry.is_directory
            else StorageEntryType.FILE
        )
        # A fresh top-level destination conflict is refused whole: the tree is
        # never merged into the existing destination.  A continuation of an
        # interrupted item revalidates its remaining entries individually — a
        # directory destination that exists without any recorded completed
        # entry cannot be proven to be this item's own partial work, so it
        # stops as an explicit investigation state instead of merging.
        if not skip_paths and self._destination_exists(
            destination_storage,
            _join_resource_library_path(destination.root_path, destination_root),
            root_kind,
        ):
            if plan.resuming:
                if root_kind is StorageEntryType.DIRECTORY:
                    recorded.append(
                        {
                            "path": top_level,
                            "destination": destination_root,
                            "status": "UNCERTAIN",
                            "errorCategory": "interrupted_destination_unknown",
                            "checkpoints": [],
                            "durableState": "mutation_effect_uncertain",
                        }
                    )
                    progress()
                    return recorded, False, False
            else:
                recorded.append(
                    _conflict_outcome(
                        plan.conflict_mode, top_level, destination_root, "target_exists"
                    )
                )
                progress()
                return recorded, False, False
        progress()
        # Explicitly plan the required destination directories, shortest path
        # first.  Every CreateDirectory crosses OrganizerExecutor and joins the
        # item's aggregated known effect.
        for entry in sorted(
            (value for value in entries if value.is_directory),
            key=lambda value: value.path.count("/"),
        ):
            stop = interruption()
            if stop is not None:
                return recorded, stop == "pause", stop == "cancel"
            destination_path = plan.destination_for(entry.path)
            if destination_path is None:
                continue
            if destination_storage.exists(
                _join_resource_library_path(destination.root_path, destination_path)
            ):
                continue
            result = self._executor.execute_direct_create_directory(
                destination_storage,
                _join_resource_library_path(destination.root_path, destination_path),
                execute=True,
            )
            outcome = self._entry_outcome(entry.path, destination_path, result)
            if result.status.value != "SUCCESS":
                outcome["errorCategory"] = "create_directory_failed"
            recorded.append(outcome)
            checkpoints.append(
                {
                    "path": entry.path,
                    "destination": destination_path,
                    "checkpoints": list(result.completed_operations),
                    "status": outcome["status"],
                }
            )
            progress()
            if result.status.value != "SUCCESS":
                return recorded, False, False
        for entry in entries:
            if entry.is_directory:
                continue
            stop = interruption()
            if stop is not None:
                return recorded, stop == "pause", stop == "cancel"
            if entry.path in skip_paths:
                # Completed before the interruption; a completed effect stays
                # terminal and is never replayed.
                continue
            destination_path = plan.destination_for(entry.path) or entry.path
            if plan.resuming:
                # A continuation first proves whether an existing destination
                # already holds the confirmed entry's exact bytes: a verified
                # copy is adopted (never re-copied), a compound Move finishes
                # only its remaining destructive step, and everything else
                # falls through to the selected conflict behavior.
                resumed = self._resume_entry_outcome(
                    plan,
                    entry,
                    destination_path,
                    source,
                    destination,
                    source_storage,
                    destination_storage,
                )
                if resumed is not None:
                    recorded.append(resumed)
                    checkpoints.append(
                        {
                            "path": entry.path,
                            "destination": destination_path,
                            "checkpoints": [
                                str(value) for value in resumed.get("checkpoints") or ()
                            ],
                            "status": resumed["status"],
                        }
                    )
                    progress()
                    continue
            conflict = self._resolve_conflict(
                plan.conflict_mode, entry, destination, destination_path, destination_storage
            )
            if conflict is not None:
                recorded.append(conflict)
                progress()
                continue
            outcome = self._transfer_entry(
                plan,
                entry,
                destination_path,
                source,
                destination,
                source_storage,
                destination_storage,
            )
            recorded.append(outcome)
            checkpoints.append(
                {
                    "path": entry.path,
                    "destination": destination_path,
                    "checkpoints": [str(value) for value in outcome.get("checkpoints") or ()],
                    "status": outcome["status"],
                }
            )
            progress()
        if plan.operation is TransferOperation.MOVE:
            completed_files = {
                str(value["path"]) for value in recorded if value.get("status") == "SUCCESS"
            } | set(skip_paths)
            recorded.extend(
                self._remove_emptied_source_directories(
                    plan,
                    top_level,
                    entries,
                    source,
                    source_storage,
                    checkpoints,
                    completed_files,
                )
            )
            progress()
        return recorded, False, False

    def _record_progress(
        self,
        item: PersistentTaskItem,
        *,
        destination: ResourceLibrary,
        destination_root: str,
        plan: _TransferPlan,
        recorded: list[dict[str, object]],
        skip_count: int,
        confirmed_entries: tuple[tuple[str, str, str], ...],
        confirmed_truncated: bool,
    ) -> None:
        """Persist the bounded in-flight progress snapshot of one item.

        The snapshot carries the item's endpoint identities, requested
        operation and conflict choice beside the confirmed scope, so the
        durable continuation never has to re-derive an admission decision
        that was already pinned.
        """

        completed = sum(1 for value in recorded if value.get("status") == "SUCCESS")
        failed = sum(
            1 for value in recorded if value.get("status") in {"FAILED", "PARTIAL", "UNCERTAIN"}
        )
        skipped = sum(1 for value in recorded if value.get("status") == "SKIPPED")
        self._direct.tasks.record_transfer_progress(
            item,
            destination_storage_id=destination.storage_id,
            destination_resource_library_id=destination.library_id,
            destination_path=destination_root,
            operation=plan.operation.value,
            conflict_mode=plan.conflict_mode.value,
            status=TaskItemStatus.PROCESSING,
            confirmed_entries=confirmed_entries,
            confirmed_truncated=confirmed_truncated,
            entries=tuple(
                {
                    "path": str(value.get("path", "")),
                    "destination": str(value.get("destination", "")),
                    "status": str(value.get("status", "")),
                }
                for value in recorded[:MAX_TRANSFER_PROGRESS_ENTRIES]
            ),
            completed_entries=completed + skip_count,
            failed_entries=failed,
            skipped_entries=skipped,
            truncated=len(recorded) > MAX_TRANSFER_PROGRESS_ENTRIES,
        )

    def _resume_entry_outcome(
        self,
        plan: _TransferPlan,
        entry: TransferManifestEntry,
        destination_path: str,
        source: ResourceLibrary,
        destination: ResourceLibrary,
        source_storage: Storage,
        destination_storage: Storage,
    ) -> dict[str, object] | None:
        """The continuation outcome of one interrupted entry, if determinable.

        Returns ``None`` when the fresh normal path should run (destination
        absent, unverifiable destination or a Storage read failure).  A
        destination proven by digest to already hold the entry's exact bytes
        is adopted — never re-copied — and a cross-Storage Move finishes only
        its remaining destructive step with fresh exact source evidence.
        """

        full_source = _join_resource_library_path(source.root_path, entry.path)
        full_target = _join_resource_library_path(destination.root_path, destination_path)
        try:
            source_present = source_storage.exists(full_source)
            destination_present = destination_storage.exists(full_target)
        except (StorageError, OSError):
            return None
        if source_present and destination_present:
            if not self._executor.verify_streamed_copy(
                source_storage,
                destination_storage,
                full_source,
                full_target,
                expected_size=entry.size,
            ):
                return None
            if plan.operation is TransferOperation.MOVE:
                if plan.same_storage:
                    # A native rename leaves both sides present only when the
                    # destination appeared externally; the selected conflict
                    # behavior decides, never a silent adoption.
                    return None
                evidence = DirectEntryEvidence(
                    size=entry.size,
                    modified_at=entry.modified_at,
                    is_directory=False,
                    fingerprint=entry.fingerprint,
                )
                result = self._executor.execute_direct_move(
                    source_storage,
                    destination_storage,
                    full_source,
                    full_target,
                    source_evidence=evidence,
                    same_storage=False,
                    verified_destination=True,
                    execute=True,
                )
                return self._entry_outcome(entry.path, destination_path, result)
            return {
                "path": entry.path,
                "destination": destination_path,
                "status": "SUCCESS",
                "checkpoints": ["COPY"],
            }
        if not source_present and destination_present:
            if plan.operation is not TransferOperation.MOVE:
                return {
                    "path": entry.path,
                    "destination": destination_path,
                    "status": "UNCERTAIN",
                    "errorCategory": "interrupted_transfer",
                    "checkpoints": [],
                    "durableState": "mutation_effect_uncertain",
                }
            try:
                observed = destination_storage.stat(full_target)
            except (StorageError, OSError):
                return None
            if observed.entry_type is StorageEntryType.FILE and observed.size == entry.size:
                # The source is gone and the destination holds the entry's
                # exact size: the native rename completed before the
                # interruption and is recorded truthfully instead of replayed.
                return {
                    "path": entry.path,
                    "destination": destination_path,
                    "status": "SUCCESS",
                    "checkpoints": ["MOVE"],
                }
            return {
                "path": entry.path,
                "destination": destination_path,
                "status": "UNCERTAIN",
                "errorCategory": "interrupted_transfer",
                "checkpoints": [],
                "durableState": "mutation_effect_uncertain",
            }
        return None

    def _transfer_entry(
        self,
        plan: _TransferPlan,
        entry: TransferManifestEntry,
        destination_path: str,
        source: ResourceLibrary,
        destination: ResourceLibrary,
        source_storage: Storage,
        destination_storage: Storage,
    ) -> dict[str, object]:
        """Execute one file entry through the executor's native-only path.

        The same/cross-Storage decision is the validated business decision
        pinned in the confirmed plan — never incidental adapter object
        identity.
        """

        full_source = _join_resource_library_path(source.root_path, entry.path)
        full_target = _join_resource_library_path(destination.root_path, destination_path)
        evidence = DirectEntryEvidence(
            size=entry.size,
            modified_at=entry.modified_at,
            is_directory=False,
            fingerprint=entry.fingerprint,
        )
        if plan.operation is TransferOperation.COPY:
            result = self._executor.execute_direct_copy(
                source_storage,
                destination_storage,
                full_source,
                full_target,
                source_evidence=evidence,
                same_storage=plan.same_storage,
                execute=True,
            )
        else:
            result = self._executor.execute_direct_move(
                source_storage,
                destination_storage,
                full_source,
                full_target,
                source_evidence=evidence,
                same_storage=plan.same_storage,
                execute=True,
            )
        return self._entry_outcome(entry.path, destination_path, result)

    @staticmethod
    def _entry_outcome(path: str, destination_path: str, result) -> dict[str, object]:
        if result.status.value == "SUCCESS":
            status = "SUCCESS"
        elif result.status.value == "PARTIAL":
            status = "PARTIAL"
        elif result.effect_certainty is ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED:
            status = "UNCERTAIN"
        else:
            status = "FAILED"
        outcome: dict[str, object] = {
            "path": path,
            "destination": destination_path,
            "status": status,
            "checkpoints": list(result.completed_operations),
        }
        error_category = _result_error_category(result)
        if error_category is not None:
            outcome["errorCategory"] = error_category
        if result.effect_certainty is ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED:
            outcome["durableState"] = "mutation_effect_uncertain"
        return outcome

    def _resolve_conflict(
        self,
        conflict_mode: TransferConflictMode,
        entry: TransferManifestEntry,
        destination: ResourceLibrary,
        destination_path: str,
        destination_storage: Storage,
    ) -> dict[str, object] | None:
        """Apply the explicitly selected conflict behavior for one entry.

        The destination state is revalidated at this last safe boundary, so a
        conflict that appears after admission fails, skips or renames
        truthfully and never becomes an implicit merge.
        """

        try:
            exists = destination_storage.exists(
                _join_resource_library_path(destination.root_path, destination_path)
            )
        except (StorageError, OSError):
            return {
                "path": entry.path,
                "destination": destination_path,
                "status": "UNCERTAIN",
                "errorCategory": "destination_state_unknown",
                "checkpoints": [],
            }
        if not exists:
            return None
        return _conflict_outcome(conflict_mode, entry.path, destination_path, "target_exists")

    def _remove_emptied_source_directories(
        self,
        plan: _TransferPlan,
        top_level: str,
        entries: list[TransferManifestEntry],
        source: ResourceLibrary,
        source_storage: Storage,
        checkpoints: list[dict[str, object]],
        completed_files: set[str],
    ) -> list[dict[str, object]]:
        """Remove the source directories the verified Move just emptied.

        Only directories whose confirmed children all reported a completed
        transfer are candidates, and the executor re-lists each one immediately
        before the removal.  An unknown or newly appeared entry stops the
        removal without a recursive delete, an already-absent virtual prefix
        (S3/R2) is truthfully recorded instead of deleting a fictional object,
        and a failed removal keeps the directory Move from being reported
        wholly successful.
        """

        outcomes: list[dict[str, object]] = []
        directories = sorted(
            (
                entry
                for entry in entries
                if entry.is_directory
                and (entry.path == top_level or entry.path.startswith(f"{top_level}/"))
            ),
            key=lambda value: value.path.count("/"),
            reverse=True,
        )
        for entry in directories:
            children = [
                candidate for candidate in entries if candidate.path.startswith(f"{entry.path}/")
            ]
            if not all(child.is_directory or child.path in completed_files for child in children):
                continue
            full = _join_resource_library_path(source.root_path, entry.path)
            result = self._executor.execute_direct_remove_empty_directory(
                source_storage, full, execute=True
            )
            outcome = self._entry_outcome(entry.path, "", result)
            if result.status.value != "SUCCESS":
                outcome["errorCategory"] = "source_directory_removal_failed"
            outcomes.append(outcome)
            checkpoints.append(
                {
                    "path": entry.path,
                    "destination": "",
                    "checkpoints": list(result.completed_operations),
                    "status": outcome["status"],
                }
            )
        return outcomes

    # ------------------------------------------------------------------
    # Error helpers
    # ------------------------------------------------------------------

    def _unsupported_entry(
        self, library: ResourceLibrary, path: str, reason: str
    ) -> DirectFileTransferError:
        return DirectFileTransferError(
            "files_transfer_unsupported_entry",
            "unsupported_entry",
            reason,
            resource_library_id=library.library_id,
            path=path,
            next_action="select a regular file or directory supported by the provider",
        )

    def _limit_error(self, library: ResourceLibrary, category: str) -> DirectFileTransferError:
        return DirectFileTransferError(
            f"files_transfer_{category}",
            category,
            "the transfer scope exceeds the bounded transfer limits",
            status=413,
            resource_library_id=library.library_id,
            next_action="transfer a smaller bounded selection",
        )

    def _storage_admission_failure(
        self, library: ResourceLibrary, relative: str, error: StorageError
    ) -> DirectFileTransferError:
        category, status = _storage_category(error)
        return DirectFileTransferError(
            f"files_transfer_{category}",
            category,
            "the Storage read for transfer admission failed",
            status=status,
            resource_library_id=library.library_id,
            path=relative,
            next_action="retry the transfer once the Storage is reachable again",
        )


def _transfer_status(
    *,
    uncertain: bool,
    paused: bool,
    cancelled: bool,
    transferred: int,
    partial: int,
    skipped: int,
    failed: int,
) -> str:
    """The stable known-effect status of one confirmed bounded transfer.

    The state names what is durably known about the durable work: any uncertain
    mutation dominates; an interrupted observation is PAUSED/CANCELLED; a
    batch whose every item transferred is SUCCESS; a batch whose every item
    was skipped is SKIPPED; anything mixed (including skipped siblings beside
    transferred ones) is PARTIAL because not every requested transfer
    happened; and only a batch where nothing was mutated is FAILED.
    """

    if uncertain:
        return "UNCERTAIN"
    if paused:
        return "PAUSED"
    if cancelled:
        return "CANCELLED"
    if transferred and not (partial or failed or skipped):
        return "SUCCESS"
    if skipped and not (transferred or partial or failed):
        return "SKIPPED"
    if transferred or partial or skipped:
        return "PARTIAL"
    return "FAILED"


def _confirmed_entries(
    manifest: TransferManifest,
) -> tuple[tuple[tuple[str, str, str], ...], bool]:
    """The bounded confirmed per-entry scope persisted with every item.

    The continuation of an interrupted transfer may proceed only against this
    recorded scope; an item whose confirmed scope was truncated cannot be
    safely continued and stops with an actionable investigation state instead.
    """

    values: list[tuple[str, str, str]] = []
    for entry in manifest.entries:
        values.append(
            (entry.path, manifest.destination_for(entry.path) or entry.path, entry.kind.value)
        )
    truncated = len(values) > MAX_TRANSFER_PROGRESS_ENTRIES
    return tuple(values[:MAX_TRANSFER_PROGRESS_ENTRIES]), truncated


def _progress_payload(item: PersistentTaskItem) -> dict[str, object] | None:
    """The parsed bounded progress snapshot of one transfer item, if any."""

    if not item.progress:
        return None
    try:
        payload = json.loads(item.progress)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _result_error_category(result) -> str | None:
    if not result.errors:
        return None
    if result.effect_certainty is ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED:
        return "uncertain_effect"
    text = "; ".join(result.errors).casefold()
    if "destination already exists" in text:
        return "target_exists"
    if "changed since it was observed" in text or "source changed" in text:
        return "stale_source"
    if "source does not exist" in text:
        return "source_missing"
    if "capability denied" in text or "read only" in text:
        return "capability_denied"
    if "unsupported capability" in text:
        return "unsupported_capability"
    if "version evidence is required" in text:
        return "entry_identity_unavailable"
    if "invalid destination" in text:
        return "invalid_path"
    if "verification failed" in text:
        return "verification_failed"
    if "directory is not empty" in text:
        return "source_directory_not_empty"
    return "storage_failure"


def _storage_category(error: StorageError) -> tuple[str, int]:
    code = error.code
    if code is StorageErrorCode.NOT_FOUND:
        return "not_found", 404
    if code in {StorageErrorCode.PERMISSION_DENIED, StorageErrorCode.READ_ONLY}:
        return "permission_denied", 403
    if code is StorageErrorCode.AUTHENTICATION_FAILED:
        return "authentication_failed", 503
    if code in {StorageErrorCode.CONNECTION_FAILED, StorageErrorCode.CONNECTION_LOST}:
        return "connection_failed", 503
    if code is StorageErrorCode.TIMEOUT:
        return "timeout", 503
    if code is StorageErrorCode.RATE_LIMITED:
        return "rate_limited", 503
    return "storage_failure", 503


def _empty_batch():
    from mediaflow.application.media_organizer import MediaOrganizerBatchResult

    return MediaOrganizerBatchResult(items=())
