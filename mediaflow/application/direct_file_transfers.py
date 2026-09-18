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
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from mediaflow.application.direct_file_commands import DirectFileCommandService, DirectFileError
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.storage_browser import (
    _join_resource_library_path,
    _normalize_storage_relative_path,
)
from mediaflow.application.task_runtime import TaskClaimLost, TaskPauseRequested
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
    FILES_TRANSFER_TASK_COMMAND,
    TRANSFER_INTERRUPTED_STAGE,
    FilesTransferStatus,
    PersistentFilesTransfer,
    PersistentResultRecord,
    PersistentTask,
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


@dataclass(frozen=True)
class _ClaimFence:
    """The Worker-side claim comparison every durable transfer write carries.

    Every post-mutation publication compares the exact claim token while the
    lease is still unexpired, so a Worker that lost ownership (a takeover after
    a stalled provider call, a paused/cancelled claim) stops publishing instead
    of overwriting a newer owner's state.
    """

    transfer_id: str
    claim_token: str

    @property
    def value(self) -> tuple[str, str, datetime]:
        return (self.transfer_id, self.claim_token, datetime.now(UTC))


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

    One deterministic precedence, shared by the response, the TaskItem, the
    durable Result and every reloaded detail:

    * any uncertain mutation dominates as UNCERTAIN;
    * all-success is SUCCESS and all-skipped is SKIPPED;
    * a mixture of SUCCESS with SKIPPED is PARTIAL — a created destination
      directory plus a skipped child is a partial item, never a completed
      transfer;
    * any known mutation beside a FAILED/PARTIAL entry is PARTIAL;
    * only a failure with zero recorded mutation is a plain FAILED.
    """

    return _precedence_status(
        {str(value["status"]) for value in entries},
        known_mutation=_outcomes_have_known_effect(entries),
    )


def _precedence_status(statuses: set[str], *, known_mutation: bool, uncertain: bool = False) -> str:
    """The one deterministic status precedence shared by every transfer surface.

    Any unprovable effect dominates, then the all-success / all-skipped /
    success-plus-skipped cases, then a known mutation beside a failure, and only
    a failure with zero known mutation is a plain FAILED.
    """

    if not statuses:
        return "FAILED"
    if uncertain or "UNCERTAIN" in statuses:
        return "UNCERTAIN"
    if statuses == {"SUCCESS"}:
        return "SUCCESS"
    if statuses <= {"SKIPPED"}:
        return "SKIPPED"
    if statuses and statuses <= {"SUCCESS", "SKIPPED"}:
        return "PARTIAL"
    if known_mutation:
        return "PARTIAL"
    return "FAILED"


def _outcomes_have_known_effect(entries: list[dict[str, object]]) -> bool:
    """Whether any entry recorded a verified mutation (a completed checkpoint).

    A skipped or refused entry records no mutation; a SUCCESS or PARTIAL entry
    does, whether or not its bounded checkpoint list survived truncation.
    """

    return any(
        value.get("checkpoints") or str(value.get("status")) in {"SUCCESS", "PARTIAL"}
        for value in entries
    )


def _result_certainty(*, mutated: bool, uncertain: bool) -> str:
    """Map effect certainty independently from the outcome wording.

    An unprovable effect is ``attempted_unverified``; a verified known effect is
    ``verified_complete``; a stop with zero attempted mutation is ``none``.
    """

    if uncertain:
        return ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED.value
    if mutated:
        return ExecutionEffectCertainty.VERIFIED_COMPLETE.value
    return ExecutionEffectCertainty.NONE.value


#: The durable transfer/Task status each canonical aggregate maps to.  The
#: uncertain aggregate is a terminal investigation outcome: the durable rows
#: keep the bounded ``mutation_outcome`` marker and the Files/Operations
#: projections report ``UNCERTAIN``.
_TRANSFER_AGGREGATE_STATUS = {
    "SUCCESS": FilesTransferStatus.COMPLETED,
    "SKIPPED": FilesTransferStatus.COMPLETED,
    "PARTIAL": FilesTransferStatus.PARTIAL_SUCCESS,
    "FAILED": FilesTransferStatus.FAILED,
    "UNCERTAIN": FilesTransferStatus.FAILED,
}

_TASK_AGGREGATE_STATUS = {
    "SUCCESS": PersistentTaskStatus.COMPLETED,
    "SKIPPED": PersistentTaskStatus.COMPLETED,
    "PARTIAL": PersistentTaskStatus.PARTIAL_SUCCESS,
    "FAILED": PersistentTaskStatus.FAILED,
    "UNCERTAIN": PersistentTaskStatus.FAILED,
}

#: The inverse of ``_TASK_AGGREGATE_STATUS``: the canonical aggregate a durable
#: Task status describes.  The uncertain aggregate is stored as FAILED with the
#: bounded ``mutation_outcome`` marker, so the transfer row itself is derived
#: from ``task.error`` rather than from the row status alone.
_TASK_STATUS_AGGREGATE = {
    PersistentTaskStatus.COMPLETED: "SUCCESS",
    PersistentTaskStatus.PARTIAL_SUCCESS: "PARTIAL",
    PersistentTaskStatus.FAILED: "FAILED",
    PersistentTaskStatus.CANCELLED: "FAILED",
    PersistentTaskStatus.PENDING: "FAILED",
    PersistentTaskStatus.RUNNING: "FAILED",
    PersistentTaskStatus.PAUSED: "FAILED",
}

_TERMINAL_STATUSES = {"SUCCESS", "SKIPPED", "PARTIAL", "FAILED", "DRY_RUN"}


#: Result annotations that describe an entry's aggregate state rather than a
#: completed executor mutation.
_ANNOTATION_MARKERS = frozenset({"entry", "entry_error", "skip_conflict"})


def _completed_operations_have_mutation(operations) -> bool:
    """Whether a Result's bounded annotations contain a real completed mutation."""

    return any(
        str(operation).partition(":")[0] not in _ANNOTATION_MARKERS for operation in operations
    )


def _terminal_item_signal(
    item: PersistentTaskItem, record: PersistentResultRecord | None
) -> tuple[str, bool, bool]:
    """One post-conversion item's ``(status, known_mutation, uncertain)`` signal.

    The Result is authoritative when present (it is the durable terminal
    evidence); a legacy or externally written TaskItem without a Result falls
    back to its own status with no effect certainty.
    """

    if record is not None:
        status = record.status.upper()
        if status not in _TERMINAL_STATUSES:
            status = _ITEM_TASK_INVERSE.get(item.status, "FAILED")
        if record.effect_certainty == ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED.value:
            return status, True, True
        verified = (
            record.effect_certainty == ExecutionEffectCertainty.VERIFIED_COMPLETE.value
            or _completed_operations_have_mutation(record.completed_operations)
        )
        return status, verified, False
    return _ITEM_TASK_INVERSE.get(item.status, "FAILED"), False, False


def _item_checkpoint_evidence(entries: list[dict[str, object]]) -> tuple[str, ...]:
    """The bounded durable checkpoint/known-state annotations of one item.

    Every completed executor checkpoint is recorded as ``checkpoint:path`` and
    every skipped entry as ``skip_conflict:path``, so the durable Result (and
    every reloaded detail) retains the exact skipped-child evidence beside the
    completed directory/file checkpoints.
    """

    values: list[str] = []
    for outcome in entries:
        path = str(outcome.get("path", ""))
        for checkpoint in outcome.get("checkpoints") or ():
            values.append(f"{checkpoint}:{path}")
        # The per-entry status marker keeps the exact per-entry aggregate
        # truth (including an uncertain or failed entry beside successful
        # siblings) reproducible from the durable Result alone.
        values.append(f"entry:{outcome.get('status', '')}:{path}")
        if outcome.get("errorCategory"):
            values.append(f"entry_error:{outcome.get('errorCategory')}:{path}")
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

#: The inverse projection of a terminal TaskItem status that has no Result
#: record (a legacy or externally written row): the projection still names a
#: truthful state instead of fabricating success.
_ITEM_TASK_INVERSE = {value: key for key, value in _ITEM_TASK_STATUS.items()}

_ITEM_KNOWN_EFFECT = {
    "SUCCESS": "transferred",
    "SKIPPED": "skipped",
    "PARTIAL": "partial",
    "UNCERTAIN": "uncertain",
    "FAILED": "retained",
}

#: The durable projection's effect vocabulary for one item.  Items still
#: queued, running or paused are reported as in progress — never as
#: transferred.
_PROJECTION_EFFECT = {
    "SUCCESS": "transferred",
    "SKIPPED": "skipped",
    "PARTIAL": "partial",
    "UNCERTAIN": "uncertain",
    "FAILED": "retained",
    "CANCELLED": "retained",
    "RUNNING": "in_progress",
    "QUEUED": "in_progress",
    "PAUSED": "in_progress",
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
        runtime_factory: Callable[[str, str], DirectFileCommandService | None] | None = None,
    ) -> None:
        self._direct = direct_files
        self._executor = executor or OrganizerExecutor()
        #: Reconstructs the exact immutable runtime of one persisted
        #: configuration revision for a claimed transfer, so a Worker never
        #: depends on whatever process-local Active snapshot it happened to
        #: start with.  It returns ``None`` when this Worker cannot lawfully
        #: reconstruct that revision, which leaves the transfer claimable.
        self._runtime_factory = runtime_factory

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
    # Explicitly submitted durable admission
    # ------------------------------------------------------------------

    def submit_transfer(
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
        """Admit the confirmed bounded transfer as one durable queued Task.

        The live manifest is rebuilt and compared with the submitted opaque
        digest first: a stale scope returns a stable error and creates no Task
        and no mutation.  Admission then atomically persists the PENDING Task,
        every bounded per-item transfer authority and the claimable transfer
        row, and returns the durable operator projection immediately — before
        the first Storage mutation.  The resident Worker claims the admitted
        transfer under its persisted fence and executes it; the admitting
        request never runs a Storage mutation on its own stack.
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
        now = datetime.now(UTC)
        # The Task object is only built here: it is persisted atomically with
        # the per-item authority and the claimable transfer row by the
        # repository's single admission transaction below.
        task = PersistentTask(
            str(uuid4()),
            FILES_TRANSFER_TASK_COMMAND,
            PersistentTaskStatus.PENDING,
            True,
            now,
            now,
            scope_path=(
                posixpath.commonpath(manifest.top_level_paths)
                if len(manifest.top_level_paths) > 1
                else manifest.top_level_paths[0]
            ),
            item_limit=max(1, len(manifest.top_level_paths)),
            configuration_snapshot_id=self._direct.revision.revision_id,
            configuration_snapshot_digest=self._direct.revision.digest,
        )
        authority = _transfer_authority(manifest)
        items = tuple(
            _admitted_item(task.task_id, manifest, top_level)
            for top_level in manifest.top_level_paths
        )
        transfer = PersistentFilesTransfer(
            transfer_id=task.task_id,
            task_id=task.task_id,
            status=FilesTransferStatus.ADMITTED,
            authority_json=authority,
            configuration_snapshot_id=self._direct.revision.revision_id,
            configuration_snapshot_digest=self._direct.revision.digest,
            created_at=now,
            updated_at=now,
        )
        self._direct.tasks.repository.admit_files_transfer(task, items, transfer)
        return _queued_document(task, manifest, items)

    def run_claimed_transfer(
        self,
        transfer: PersistentFilesTransfer,
        *,
        claim_token: str,
        heartbeat: Callable[[], bool],
        lease_seconds: float,
    ) -> PersistentFilesTransfer:
        """Execute one claimed transfer to its truthful terminal state.

        Every top-level selection is an independently recoverable item.  An
        item the claim owner never started is executed from the pinned
        admission authority; a started item continues only from its recorded
        known-safe checkpoint; a recorded uncertain effect is never replayed.
        The claim is verified (via ``heartbeat``) at every safe boundary, the
        bounded in-flight progress is persisted after each entry, and the
        terminal status is published through a claim-guarded update — so only
        the current claim owner may advance progress or finish the transfer.

        Every unexpected failure converges the transfer row, the Task, the
        unfinished TaskItems and the bounded Result evidence on one truthful
        terminal state in a single guarded commitment, so a reloaded projection
        never reports a permanently running transfer beside a failed row.
        """

        repository = self._direct.tasks.repository
        task_id = transfer.task_id
        claimed_at = datetime.now(UTC)
        if not repository.begin_files_transfer(transfer.transfer_id, claim_token, claimed_at):
            raise DirectFileTransferError(
                "files_transfer_claim_lost",
                "claim_lost",
                "the transfer claim is no longer owned by this Worker",
                status=409,
                next_action="the transfer stays claimable for the next Worker",
            )
        fence = _ClaimFence(transfer.transfer_id, claim_token)
        try:
            if transfer.mutation_state is not None:
                # This claim exists only to resolve an expired in-flight
                # mutation: classify the recorded boundary against live Storage
                # with zero mutation, and either return the entry to a
                # continuation-safe state (so the ordinary verified
                # continuation may resume) or converge it to a durable
                # uncertain/investigation-only outcome.  The interrupted
                # operation is never invoked again, and the classification runs
                # under this transfer's own pinned revision, never under
                # whatever process-local snapshot this Worker started with.
                authority = self._parse_pinned_authority(transfer)
                if not self._resolve_in_flight_mutation(transfer, authority, fence):
                    return repository.require_files_transfer(transfer.transfer_id)
            self._execute_claimed_transfer(
                transfer,
                task_id=task_id,
                heartbeat=heartbeat,
                lease_seconds=lease_seconds,
                fence=fence,
            )
        except (_TransferClaimLost, TaskClaimLost):
            # The lease was lost mid-flight: stop without publishing a
            # terminal state.  The claim has already expired, so a replacement
            # Worker takes over and continues from the persisted checkpoints.
            return repository.require_files_transfer(transfer.transfer_id)
        except _TransferSnapshotUnavailable:
            # This Worker cannot lawfully reconstruct the transfer's pinned
            # immutable runtime.  The transfer is never consumed as a business
            # failure: it returns to the claimable queue with bounded readiness
            # evidence for a compatible Worker.
            self._release_snapshot_unavailable(fence)
            return repository.require_files_transfer(transfer.transfer_id)
        except _TransferAuthorityUnreadable as error:
            # No Worker can lawfully execute a corrupt persisted authority: it
            # converges to a bounded investigation outcome with zero mutation
            # instead of a fabricated business failure or a blind retry.
            self._converge_execution_failure(fence, error, code="files_transfer_invalid_authority")
            return repository.require_files_transfer(transfer.transfer_id)
        except TaskPauseRequested:
            repository.pause_files_transfer(
                transfer.transfer_id, claim_token=claim_token, now=datetime.now(UTC)
            )
            return repository.require_files_transfer(transfer.transfer_id)
        except _TransferCancelled:
            terminal = replace(
                repository.require_files_transfer(transfer.transfer_id),
                status=FilesTransferStatus.CANCELLED,
                error=None,
                next_action="the transfer was cancelled; completed effects stay terminal",
                completed_at=datetime.now(UTC),
            )
        except Exception as error:
            # A failed execution is a durable, bounded, secret-free outcome:
            # the transfer, Task, unfinished items and Result evidence converge
            # on one truthful state instead of being left contradictory.
            self._converge_execution_failure(fence, error)
            return repository.require_files_transfer(transfer.transfer_id)
        else:
            current = repository.require_files_transfer(transfer.transfer_id)
            task = repository.get_task(task_id)
            # The durable transfer row repeats exactly the aggregate the Task
            # row already carries, so no surface can disagree about completion.
            uncertain = task is not None and task.error == "mutation_outcome"
            aggregate = _TASK_STATUS_AGGREGATE.get(
                task.status if task is not None else PersistentTaskStatus.FAILED,
                "FAILED",
            )
            if uncertain:
                aggregate = "UNCERTAIN"
            transfer_status = _TRANSFER_AGGREGATE_STATUS.get(aggregate, FilesTransferStatus.FAILED)
            terminal = replace(
                current,
                status=transfer_status,
                error=(
                    "mutation_outcome"
                    if uncertain
                    else current.error
                    if transfer_status is not FilesTransferStatus.COMPLETED
                    else None
                ),
                next_action=(
                    "an interrupted item could not be safely continued; refresh both "
                    "directories and inspect the recorded per-item outcomes before any "
                    "retry — uncertain effects are never replayed"
                    if uncertain
                    else None
                ),
                completed_at=datetime.now(UTC),
            )
        repository.finish_files_transfer(terminal, claim_token=claim_token, now=datetime.now(UTC))
        return repository.require_files_transfer(transfer.transfer_id)

    def converge_worker_failure(
        self, transfer_id: str, claim_token: str, error: BaseException
    ) -> bool:
        """Converge one claimed transfer whose Worker failed before/while starting.

        Called by the resident Worker when its invocation of this transfer
        raised outside the normal per-item path, so the transfer row, Task,
        unfinished items and Result evidence all reach the same truthful
        terminal state instead of leaving a permanently running projection.
        Returns ``False`` when this claim no longer owns the row.
        """

        return self._converge_execution_failure(_ClaimFence(transfer_id, claim_token), error)

    def _resolve_in_flight_mutation(
        self,
        transfer: PersistentFilesTransfer,
        authority: dict[str, object],
        fence: _ClaimFence,
    ) -> bool:
        """Resolve one expired in-flight mutation without replaying it.

        The recorded boundary names the exact item/entry/action the dead owner
        had entered.  This method re-observes that entry against live Storage
        with **zero mutation** and classifies it:

        * a provably complete effect, or a genuinely idempotent/fenced
          continuation (a verified Copy whose compound Move still owes its
          destructive step), returns the entry to a continuation-safe state and
          lets the ordinary verified continuation resume from it; and
        * anything the provider cannot prove — including a destination that is
          absent or does not hold the confirmed bytes — converges that item, the
          Task and the bounded Result evidence to a durable UNCERTAIN /
          investigation-only outcome.

        Returns ``True`` when the boundary was returned to a continuation-safe
        state and the transfer may continue, ``False`` when it converged.
        """

        repository = self._direct.tasks.repository
        now = datetime.now(UTC)
        items = tuple(repository.list_items(transfer.task_id))
        records = {record.item_id: record for record in repository.list_results(transfer.task_id)}
        item = next((value for value in items if value.item_id == transfer.in_flight_item_id), None)
        if item is not None and self._in_flight_effect_is_proven(transfer, authority, item):
            cleared = repository.clear_files_transfer_mutation(
                transfer.transfer_id, fence.claim_token, now
            )
            if not cleared:
                raise _TransferClaimLost()
            return True
        # The provider cannot prove the interrupted effect: converge the exact
        # in-flight item, the Task and the bounded Result evidence together to
        # a durable uncertain/investigation-only state, and never replay it.
        self._commit_convergence(
            fence,
            transfer,
            items=items,
            records=records,
            code="files_transfer_mutation_unresolved",
            now=now,
            forced_uncertain_item_id=transfer.in_flight_item_id,
        )
        return False

    def _in_flight_effect_is_proven(
        self,
        transfer: PersistentFilesTransfer,
        authority: dict[str, object],
        item: PersistentTaskItem,
    ) -> bool:
        """Whether continuing from the recorded boundary cannot replay an unknown effect.

        Only zero-mutation observations decide this: the exact pinned entry is
        re-read and compared against the confirmed bytes, the destination is
        checked against the confirmed entry, and a directory action is checked
        for its own idempotent post-state.  A missing destination is *not* proof
        that nothing happened (the provider call may still be blocked inside a
        partial write), so it fails closed to investigation.
        """

        action = transfer.in_flight_action or ""
        entry_path = transfer.in_flight_entry_path or ""
        if not entry_path or not (
            entry_path == item.source_display or entry_path.startswith(f"{item.source_display}/")
        ):
            # The recorded boundary is not inside the item that claims it: the
            # durable evidence is inconsistent and fails closed.
            return False
        destinations = {str(pair[0]): str(pair[1]) for pair in authority.get("destinations") or ()}
        entries = {str(entry[0]): entry for entry in authority.get("entries") or () if entry}
        entry = entries.get(entry_path)
        if entry is None:
            return False
        source = self._direct.library(str(authority.get("sourceResourceLibraryId", "")))
        destination = self._direct.library(str(authority.get("destinationResourceLibraryId", "")))
        source_storage = self._direct.open_storage(source)
        destination_storage = self._direct.open_storage(destination)
        destination_path = destinations.get(entry_path, entry_path)
        full_source = _join_resource_library_path(source.root_path, entry_path)
        full_target = _join_resource_library_path(destination.root_path, destination_path)
        if action in {"copy", "move"}:
            try:
                source_present = source_storage.exists(full_source)
                destination_present = destination_storage.exists(full_target)
            except (StorageError, OSError):
                return False
            if not destination_present:
                return False
            if entry_path.endswith("/") or str(entry[1]) == TransferEntryKind.DIRECTORY.value:
                return False
            if source_present:
                return bool(
                    self._executor.verify_streamed_copy(
                        source_storage,
                        destination_storage,
                        full_source,
                        full_target,
                        expected_size=int(entry[2]),
                    )
                )
            try:
                observed = destination_storage.stat(full_target)
            except (StorageError, OSError):
                return False
            return observed.entry_type is StorageEntryType.FILE and observed.size == int(entry[2])
        if action == "create_directory":
            try:
                if not destination_storage.exists(full_target):
                    return False
                return (
                    destination_storage.stat(full_target).entry_type is StorageEntryType.DIRECTORY
                )
            except (StorageError, OSError):
                return False
        if action == "remove_directory":
            try:
                return not source_storage.exists(full_source)
            except (StorageError, OSError):
                return False
        return False

    def _converge_execution_failure(
        self, fence: _ClaimFence, error: BaseException, *, code: str | None = None
    ) -> bool:
        """Publish one truthful terminal state after an unexpected failure.

        Every unfinished item is first converted into an explicit terminal
        interrupted/investigation state with bounded Result evidence; the
        transfer row, the Task row, each TaskItem and each Result are then all
        derived from that single **post-conversion** aggregate, so no surface can
        contradict another.  All of it is one compare-and-set against the
        current claim token, which makes the convergence atomic and idempotent.
        """

        repository = self._direct.tasks.repository
        transfer = repository.get_files_transfer(fence.transfer_id)
        if transfer is None or transfer.status.terminal:
            return True
        return self._commit_convergence(
            fence,
            transfer,
            items=repository.list_items(transfer.task_id),
            records={
                record.item_id: record for record in repository.list_results(transfer.task_id)
            },
            code=code or f"files_transfer_worker_failed_{type(error).__name__}",
            now=datetime.now(UTC),
        )

    def _commit_convergence(
        self,
        fence: _ClaimFence,
        transfer: PersistentFilesTransfer,
        *,
        items: tuple[PersistentTaskItem, ...],
        records: dict[str, PersistentResultRecord],
        code: str,
        now: datetime,
        forced_uncertain_item_id: str | None = None,
    ) -> bool:
        """One atomic truthful terminal commitment for a failed/interrupted transfer."""

        repository = self._direct.tasks.repository
        outcomes: list[PersistentTaskItem] = []
        results: list[PersistentResultRecord] = []
        converted_records: dict[str, PersistentResultRecord] = {}
        for item in items:
            if item.status not in {TaskItemStatus.PENDING, TaskItemStatus.PROCESSING}:
                continue
            mutated, uncertain = _item_known_mutation(item, records.get(item.item_id))
            if item.item_id == forced_uncertain_item_id:
                # The one item whose Storage mutation was interrupted: its
                # effect is unprovable by definition, so it is always
                # investigation-only regardless of what earlier entries
                # recorded.
                uncertain = True
            converted, record = _interrupted_terminal_item(
                item,
                uncertain=uncertain,
                mutated=mutated,
                now=now,
                code=code,
            )
            outcomes.append(converted)
            results.append(record)
            converted_records[converted.item_id] = record
        # The one deterministic aggregate is built from the post-conversion
        # evidence — every item is now terminal — never from the stale
        # pre-conversion list.
        signals = [
            _terminal_item_signal(
                item, converted_records.get(item.item_id) or records.get(item.item_id)
            )
            for item in items
        ]
        statuses = {signal[0] for signal in signals}
        uncertain = any(signal[2] for signal in signals)
        known_mutation = any(signal[1] for signal in signals)
        aggregate = _precedence_status(statuses, known_mutation=known_mutation, uncertain=uncertain)
        status = _TRANSFER_AGGREGATE_STATUS.get(aggregate, FilesTransferStatus.FAILED)
        completed = sum(signal[0] in {"SUCCESS", "SKIPPED", "DRY_RUN"} for signal in signals)
        failed = sum(signal[0] in {"FAILED", "PARTIAL"} for signal in signals)
        terminal_task = None
        task = repository.get_task(transfer.task_id)
        if task is not None and task.status not in {
            PersistentTaskStatus.COMPLETED,
            PersistentTaskStatus.PARTIAL_SUCCESS,
            PersistentTaskStatus.FAILED,
            PersistentTaskStatus.CANCELLED,
        }:
            terminal_task = replace(
                task,
                status=_TASK_AGGREGATE_STATUS.get(aggregate, PersistentTaskStatus.FAILED),
                updated_at=now,
                completed_at=now,
                total_items=len(items),
                completed_items=completed,
                failed_items=failed,
                error=("mutation_outcome" if uncertain else _bounded_transfer_error(None, code)),
                pause_requested=False,
            )
        terminal_transfer = replace(
            transfer,
            status=status,
            error=("mutation_outcome" if uncertain else _bounded_transfer_error(None, code)),
            next_action=(
                "an interrupted item could not be safely continued; refresh both directories "
                "and inspect the recorded per-item outcomes before any retry — uncertain "
                "effects are never replayed"
                if uncertain
                else "inspect the recorded per-item outcomes and submit a fresh transfer "
                "for the remaining entries"
            ),
            completed_at=now,
        )
        converged = getattr(repository, "converge_files_transfer_failure", None)
        if callable(converged):
            return bool(
                converged(
                    terminal_transfer,
                    claim_token=fence.claim_token,
                    now=now,
                    task=terminal_task,
                    items=tuple(outcomes),
                    results=tuple(results),
                )
            )
        return bool(
            repository.finish_files_transfer(
                terminal_transfer, claim_token=fence.claim_token, now=now
            )
        )

    def _execute_claimed_transfer(
        self,
        transfer: PersistentFilesTransfer,
        *,
        task_id: str,
        heartbeat: Callable[[], bool],
        lease_seconds: float,
        fence: _ClaimFence,
    ) -> None:
        """Drive one claimed transfer through its items to a terminal state."""

        repository = self._direct.tasks.repository
        task = repository.get_task(task_id)
        if task is None:
            raise LookupError(f"transfer Task {task_id!r} was not found")
        authority = self._parse_pinned_authority(transfer)
        paused = False
        cancelled = False
        errored = False
        # The Task running boundary is published only now: after the claim
        # fence and before the first mutation.  A queued Task starts here; a
        # Task left running by a crashed Worker continues (takeover); a Task
        # cancelled while it sat queued is never started — its accepted
        # durable state stays the outcome.
        if task.status is PersistentTaskStatus.CANCELLED:
            raise _TransferCancelled()
        if task.status not in {PersistentTaskStatus.PENDING, PersistentTaskStatus.RUNNING}:
            raise TaskPauseRequested(f"task {task_id!r} is {task.status.value}")
        # A crashed Worker leaves its own item locks behind: the claim owner
        # reclaims exactly this Task's locks before any further mutation, so
        # the takeover continues instead of failing on its predecessor.
        self._direct.tasks.locks.reclaim_task_locks(task_id)
        self._direct.tasks.begin_queued(task_id, transfer_fence=fence.value)
        heartbeat()
        items = repository.list_items(task_id)
        # The deterministic in-batch collisions pinned at admission (two
        # selected roots resolving to one destination) stay pinned: a later
        # sibling is reported through the selected conflict mode instead of
        # merging into an earlier sibling's destination.
        claimed_destinations: set[str] = set()
        for item in items:
            if self._direct.tasks.cancellation_observed(task_id):
                cancelled = True
                break
            if item.status is TaskItemStatus.PENDING and item.attempts == 0:
                try:
                    plan, destination = self._plan_from_authority(authority, item)
                except DirectFileTransferError:
                    errored = True
                    break
                root_destination = plan.destinations.get(item.source_display, item.source_display)
                batch_conflict = root_destination in claimed_destinations
                claimed_destinations.add(root_destination)
                stopped = self._run_admitted_item(
                    plan,
                    item,
                    destination,
                    task_id=task_id,
                    authority=authority,
                    batch_conflict=batch_conflict,
                    heartbeat=heartbeat,
                    lease_seconds=lease_seconds,
                    fence=fence,
                )
            else:
                stopped = self._continue_item(
                    item,
                    task_id=task_id,
                    heartbeat=heartbeat,
                    lease_seconds=lease_seconds,
                    fence=fence,
                )
            if stopped == "pause":
                self._direct.tasks.acknowledge_pause(task_id)
                paused = True
                break
            if stopped == "cancel":
                cancelled = True
                break
        if paused or cancelled:
            raise TaskPauseRequested if paused else _TransferCancelled()
        if errored:
            raise _TransferExecutionFailed()
        # The durable Task outcome is the transfer's terminal aggregate: one
        # deterministic precedence computed from the post-execution item/Result
        # evidence, so the Task row, the transfer row, every TaskItem, every
        # Result and the Files/Operations projections all agree.
        self._publish_terminal_task_aggregate(task_id, fence=fence)

    def _publish_terminal_task_aggregate(self, task_id: str, *, fence: _ClaimFence) -> str:
        """Publish the Task terminal status from the one post-execution aggregate."""

        repository = self._direct.tasks.repository
        now = datetime.now(UTC)
        items = repository.list_items(task_id)
        records = {record.item_id: record for record in repository.list_results(task_id)}
        signals = [_terminal_item_signal(item, records.get(item.item_id)) for item in items]
        statuses = {signal[0] for signal in signals}
        uncertain = any(signal[2] for signal in signals)
        known_mutation = any(signal[1] for signal in signals)
        aggregate = _precedence_status(statuses, known_mutation=known_mutation, uncertain=uncertain)
        task = repository.get_task(task_id)
        if task is None:
            return aggregate
        if task.status is PersistentTaskStatus.CANCELLED:
            return aggregate
        completed = sum(signal[0] in {"SUCCESS", "SKIPPED", "DRY_RUN"} for signal in signals)
        failed = sum(signal[0] in {"FAILED", "PARTIAL"} for signal in signals)
        final = replace(
            task,
            status=_TASK_AGGREGATE_STATUS.get(aggregate, PersistentTaskStatus.FAILED),
            updated_at=now,
            completed_at=now,
            total_items=len(items),
            completed_items=completed,
            failed_items=failed,
            error=("mutation_outcome" if uncertain else task.error),
            pause_requested=False,
        )
        guarded = getattr(repository, "update_task_guarded", None)
        if callable(guarded):
            guarded(
                final,
                transfer_id=fence.transfer_id,
                claim_token=fence.claim_token,
                now=now,
            )
        else:  # pragma: no cover - every runtime repository carries the fence
            repository.update_task(final)
        return aggregate

    def _parse_pinned_authority(self, transfer: PersistentFilesTransfer) -> dict[str, object]:
        """The claimed transfer's reconstructed immutable pinned authority.

        The Worker reconstructs the transfer's own persisted configuration
        revision/digest rather than trusting whatever process-local snapshot it
        may hold: an older Worker process may lawfully execute newer admitted
        work, and a newer Worker may lawfully continue work admitted under a
        superseded revision.  A revision this Worker cannot lawfully
        reconstruct raises ``_TransferSnapshotUnavailable`` and leaves the
        transfer claimable instead of consuming it as a business failure.
        """

        authority = _parse_authority(transfer.authority_json)
        pinned_id = transfer.configuration_snapshot_id or str(authority.get("revisionId", ""))
        pinned_digest = transfer.configuration_snapshot_digest or str(
            authority.get("revisionDigest", "")
        )
        if not pinned_id:
            raise _TransferSnapshotUnavailable("the transfer has no pinned configuration identity")
        if not isinstance(authority, dict) or not authority.get("operation"):
            # A corrupt or unreadable pinned authority can never be lawfully
            # reconstructed or replayed: it is bounded investigation evidence,
            # not claimable work and never a mutation.
            raise _TransferAuthorityUnreadable("the pinned transfer authority is unreadable")
        if self._runtime_factory is not None:
            try:
                rebuilt = self._runtime_factory(pinned_id, pinned_digest)
            except Exception as error:
                # A runtime reconstruction failure is a readiness problem, not a
                # business failure of otherwise valid work: leave the transfer
                # claimable for a compatible Worker.
                raise _TransferSnapshotUnavailable(type(error).__name__) from error
            if rebuilt is None:
                raise _TransferSnapshotUnavailable("the pinned revision is unavailable")
            # The factory may return either a direct-command service or a fully
            # composed transfer service; adopt the direct-command boundary (and
            # the executor it was built with, when it carries one) so the
            # claimed transfer executes under its own pinned revision.
            direct = getattr(rebuilt, "_direct", rebuilt)
            self._direct = direct
            executor = getattr(rebuilt, "_executor", None)
            if executor is not None:
                self._executor = executor
            if direct.revision.revision_id != pinned_id or (
                pinned_digest and direct.revision.digest != pinned_digest
            ):
                raise _TransferSnapshotUnavailable("the pinned revision identity does not match")
            return authority
        rebind = getattr(self._direct, "rebind_to_revision", None)
        if not callable(rebind):
            raise _TransferSnapshotUnavailable("the runtime cannot reconstruct a pinned revision")
        try:
            direct = rebind(pinned_id, pinned_digest)
        except Exception as error:  # pragma: no cover - defensive boundary
            raise _TransferSnapshotUnavailable(type(error).__name__) from error
        if direct is None:
            raise _TransferSnapshotUnavailable("the pinned revision is unavailable")
        if direct.revision.revision_id != pinned_id or (
            pinned_digest and direct.revision.digest != pinned_digest
        ):
            raise _TransferSnapshotUnavailable("the pinned revision identity does not match")
        self._direct = direct
        return authority

    def _release_snapshot_unavailable(self, fence: _ClaimFence) -> None:
        """Return one incompatible claim to the queue with readiness evidence.

        The transfer row goes back to the claimable state only under the
        current claim token, so a Worker that already lost ownership writes
        nothing.  The pinned authority and per-item checkpoints are untouched:
        a compatible Worker continues from exactly where the transfer stood.
        """

        repository = self._direct.tasks.repository
        requeue = getattr(repository, "release_files_transfer_claim", None)
        if callable(requeue):
            requeue(
                fence.transfer_id,
                claim_token=fence.claim_token,
                now=datetime.now(UTC),
                error="files_transfer_snapshot_unavailable",
                next_action=(
                    "wait for a Worker that can reconstruct this transfer's pinned "
                    "Active configuration, or inspect the Active revision"
                ),
            )

    def _run_admitted_item(
        self,
        plan: _TransferPlan,
        item: PersistentTaskItem,
        destination: ResourceLibrary,
        *,
        task_id: str,
        authority: dict[str, object],
        batch_conflict: bool = False,
        heartbeat: Callable[[], bool],
        lease_seconds: float,
        fence: _ClaimFence | None = None,
    ) -> str | None:
        """Execute one never-started item from the pinned admission authority.

        Returns the observed interruption, if any.  The per-entry execution
        machinery (conflict revalidation, executor-only mutation, per-entry
        pause/cancel/claim observation and durable progress) is exactly the
        same machinery a resumed item uses, so a resumed Task cannot diverge
        from a freshly executed one.
        """

        source = self._direct.library(_plan_source_library(authority))
        source_storage = self._direct.open_storage(source)
        destination_storage = self._direct.open_storage(destination)
        try:
            claimed_item = self._direct.tasks.begin_item(
                task_id,
                source.storage_id,
                source.library_id,
                _join_resource_library_path(source.root_path, item.source_display),
                item.source_display,
            )
        except TaskPauseRequested:
            return "pause"
        except Exception:
            self._direct.tasks.complete_direct_item(
                item,
                status=TaskItemStatus.FAILED,
                operation=plan.operation.value,
                error="source is locked by another active task",
                transfer_fence=fence.value if fence is not None else None,
            )
            return None
        confirmed_scope = tuple(
            (entry.path, plan.destination_for(entry.path) or entry.path, entry.kind.value)
            for entry in plan.entries
            if entry.path == claimed_item.source_display
            or entry.path.startswith(f"{claimed_item.source_display}/")
        )
        truncated = len(confirmed_scope) > MAX_TRANSFER_PROGRESS_ENTRIES
        return self._execute_item_with_fences(
            plan,
            claimed_item,
            source=source,
            destination=destination,
            source_storage=source_storage,
            destination_storage=destination_storage,
            task_id=task_id,
            heartbeat=heartbeat,
            lease_seconds=lease_seconds,
            confirmed_entries=confirmed_scope[:MAX_TRANSFER_PROGRESS_ENTRIES],
            confirmed_truncated=truncated,
            batch_conflict=batch_conflict,
            fence=fence,
        )

    def _continue_item(
        self,
        item: PersistentTaskItem,
        *,
        task_id: str,
        heartbeat: Callable[[], bool],
        lease_seconds: float,
        fence: _ClaimFence | None = None,
    ) -> str | None:
        """Continue one started item from its persisted checkpoint.

        An item with no usable persisted checkpoint becomes an explicit
        interrupted/investigation state instead of a blind retry; a confirmed
        scope that no longer matches live Storage stops the item.
        """

        if item.status in {
            TaskItemStatus.SUCCESS,
            TaskItemStatus.SKIPPED,
            TaskItemStatus.FAILED,
            TaskItemStatus.CANCELLED,
        }:
            return None
        try:
            context = self._resume_item_plan(item)
        except DirectFileTransferError as error:
            if error.category != "scope_changed":
                raise
            self._mark_interrupted_item(item, error.code, mutated=error.mutated, fence=fence)
            return None
        if context is None:
            # The claim owner never recorded a known-safe checkpoint for this
            # item: it is an explicit interrupted/investigation state.
            self._mark_interrupted_item(item, "files_transfer_interrupted_unknown", fence=fence)
            return None
        source = self._direct.library(item.resource_library_id)
        try:
            resumed_item = self._direct.tasks.begin_item(
                task_id,
                source.storage_id,
                source.library_id,
                _join_resource_library_path(source.root_path, item.source_display),
                item.source_display,
            )
        except TaskPauseRequested:
            return "pause"
        except Exception:
            return None
        return self._execute_item_with_fences(
            context.plan,
            resumed_item,
            source=source,
            destination=context.destination,
            source_storage=self._direct.open_storage(source),
            destination_storage=context.destination_storage,
            task_id=task_id,
            heartbeat=heartbeat,
            lease_seconds=lease_seconds,
            skip_paths=context.skip_paths,
            confirmed_entries=context.confirmed_entries,
            confirmed_truncated=context.confirmed_truncated,
            fence=fence,
        )

    def _execute_item_with_fences(
        self,
        plan: _TransferPlan,
        item: PersistentTaskItem,
        *,
        source: ResourceLibrary,
        destination: ResourceLibrary,
        source_storage: Storage,
        destination_storage: Storage,
        task_id: str,
        heartbeat: Callable[[], bool],
        lease_seconds: float,
        skip_paths: frozenset[str] = frozenset(),
        confirmed_entries: tuple[tuple[str, str, str], ...] = (),
        confirmed_truncated: bool = False,
        batch_conflict: bool = False,
        fence: _ClaimFence | None = None,
    ) -> str | None:
        """Run one item to its durable terminal outcome under claim fences.

        Every per-entry boundary observes the durable pause/cancel requests
        and verifies the Worker's live claim before the next progress write; a
        lost claim raises ``_TransferClaimLost`` before anything further is
        published.  The item's terminal TaskItem/Result publish is the claim
        owner's last durable act for this item.
        """

        def interruption() -> str | None:
            if self._direct.tasks.cancellation_observed(task_id):
                return "cancel"
            if self._direct.tasks.pause_requested(task_id):
                return "pause"
            if not heartbeat():
                raise _TransferClaimLost()
            return None

        outcomes: list[dict[str, object]] = []
        checkpoints: list[dict[str, object]] = []
        _, paused, cancelled = self._execute_item(
            plan=plan,
            top_level=item.source_display,
            source=source,
            destination=destination,
            source_storage=source_storage,
            destination_storage=destination_storage,
            checkpoints=checkpoints,
            task_id=task_id,
            item=item,
            batch_conflict=batch_conflict,
            destination_root=plan.destinations.get(item.source_display, item.source_display),
            confirmed_entries=confirmed_entries,
            confirmed_truncated=confirmed_truncated,
            skip_paths=skip_paths,
            interruption=interruption,
            collect=outcomes.extend,
            fence=fence,
        )
        if paused or cancelled:
            return "pause" if paused else "cancel"
        status = _item_status(outcomes)
        unknown = "UNCERTAIN" in {str(value["status"]) for value in outcomes}
        mutated = _outcomes_have_known_effect(outcomes)
        published = self._direct.tasks.complete_direct_item(
            item,
            status=_ITEM_TASK_STATUS[status],
            operation=plan.operation.value,
            target_path=plan.destinations.get(item.source_display, item.source_display),
            error=(
                None
                if status == "SUCCESS"
                else str(
                    next(
                        (
                            outcome.get("errorCategory")
                            for outcome in outcomes
                            if outcome.get("status") != "SUCCESS"
                        ),
                        "transfer_partial",
                    )
                )
            ),
            effect_certainty=_result_certainty(mutated=mutated, uncertain=unknown),
            uncertain_effects=("mutation_outcome",) if unknown else (),
            destination_storage_id=destination.storage_id,
            completed_operations=_item_checkpoint_evidence(outcomes),
            transfer_fence=fence.value if fence is not None else None,
        )
        if published is False:
            # The lease was taken over: the terminal item publish is another
            # Worker's to make, so this owner stops without touching the Task.
            raise _TransferClaimLost()
        if unknown:
            self._mark_transfer_uncertain(task_id, fence=fence)
        return None

    def _open_mutation(
        self,
        fence: _ClaimFence | None,
        item: PersistentTaskItem,
        *,
        entry_path: str,
        action: str,
    ) -> None:
        """Publish the exact in-flight boundary before one executor mutation.

        From this moment the ordinary claim query refuses the transfer, no
        matter how long the provider call blocks, so a stalled or lost owner can
        never let a replacement Worker invoke the same mutation.  The boundary
        is cleared atomically by the guarded publication that records the
        verified outcome (see ``_clear_mutation_locked``).  A failed publish
        means this Worker is no longer the claim owner: it must stop before
        entering the mutation instead of mutating without a fence.
        """

        if fence is None:
            return None
        repository = self._direct.tasks.repository
        begin = getattr(repository, "begin_files_transfer_mutation", None)
        if not callable(begin):
            return None
        opened = begin(
            fence.transfer_id,
            fence.claim_token,
            datetime.now(UTC),
            item_id=item.item_id,
            entry_path=entry_path,
            action=action,
        )
        if not opened:
            raise _TransferClaimLost()
        return None

    def _mutation_action(self, plan: _TransferPlan) -> str:
        return "copy" if plan.operation is TransferOperation.COPY else "move"

    def _mark_transfer_uncertain(self, task_id: str, *, fence: _ClaimFence | None = None) -> None:
        """Record one uncertain mutation on the Task's durable error surface.

        The marker is set on the still-running Task so a process interruption
        after an uncertain mutation is durably visible before any terminal
        aggregate exists.  On the Worker path it is a claim-guarded update, so
        a Worker that lost ownership cannot overwrite a newer owner's Task.
        """

        repository = self._direct.tasks.repository
        task = repository.get_task(task_id)
        if task is None or task.status is not PersistentTaskStatus.RUNNING:
            return
        uncertain = replace(
            task,
            error="mutation_outcome",
            updated_at=datetime.now(UTC),
        )
        if fence is not None:
            guarded = getattr(repository, "update_task_guarded", None)
            if callable(guarded):
                guarded(
                    uncertain,
                    transfer_id=fence.transfer_id,
                    claim_token=fence.claim_token,
                    now=datetime.now(UTC),
                )
                return
        repository.update_task(uncertain)

    def _plan_from_authority(
        self, authority: dict[str, object], item: PersistentTaskItem
    ) -> tuple[_TransferPlan, ResourceLibrary]:
        """Rebuild one never-started item's plan from the pinned authority."""

        try:
            operation = TransferOperation(str(authority.get("operation")))
            conflict_mode = TransferConflictMode(str(authority.get("conflictMode")))
        except (TypeError, ValueError):
            raise DirectFileTransferError(
                "files_transfer_invalid_authority",
                "invalid_authority",
                "the persisted transfer authority is not usable",
                status=500,
                next_action="submit a fresh bounded transfer",
            ) from None
        destination_library_id = str(authority.get("destinationResourceLibraryId", ""))
        destination = self._direct.library(destination_library_id)
        entries = [
            TransferManifestEntry(
                path=str(entry[0]),
                kind=TransferEntryKind(str(entry[1])),
                size=int(entry[2]),
                modified_at=str(entry[3]),
                fingerprint=str(entry[4]),
            )
            for entry in authority.get("entries") or ()
        ]
        destinations = {str(pair[0]): str(pair[1]) for pair in authority.get("destinations") or ()}
        top_level = item.source_display
        item_top_levels = tuple(authority.get("topLevelPaths") or ())
        plan = _TransferPlan(
            operation=operation,
            conflict_mode=conflict_mode,
            same_storage=bool(authority.get("sameStorage")),
            entries=tuple(
                entry
                for entry in entries
                if entry.path == top_level or entry.path.startswith(f"{top_level}/")
            ),
            destinations=destinations,
            top_levels=(top_level,) if top_level in item_top_levels else (top_level,),
        )
        return plan, destination

    # ------------------------------------------------------------------
    # Durable continuation admission (resume without execution)
    # ------------------------------------------------------------------

    def requeue_transfer(self, task_id: str) -> dict[str, object]:
        """Re-admit one paused or abandoned transfer for Worker pickup.

        The HTTP resume request performs zero Storage work: it re-queues the
        persisted authority and returns the durable operator projection.  The
        resident Worker claims the transfer and continues only from each
        item's recorded known-safe checkpoint.
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
        transfer = self._direct.tasks.repository.get_files_transfer_for_task(task_id)
        if transfer is None:
            raise DirectFileTransferError(
                "files_transfer_resume_unavailable",
                "resume_unavailable",
                "the transfer has no durable continuation authority",
                status=409,
                next_action="submit a fresh bounded transfer instead",
            )
        if transfer.status is FilesTransferStatus.RUNNING and (
            transfer.claim_expires_at is not None and transfer.claim_expires_at > datetime.now(UTC)
        ):
            raise DirectFileTransferError(
                "files_transfer_resume_running",
                "resume_running",
                "the transfer is still owned by a live Worker claim",
                status=409,
                next_action="wait for it to finish, pause or cancel it",
            )
        if transfer.status in {
            FilesTransferStatus.COMPLETED,
            FilesTransferStatus.PARTIAL_SUCCESS,
            FilesTransferStatus.FAILED,
            FilesTransferStatus.CANCELLED,
        }:
            raise DirectFileTransferError(
                "files_transfer_resume_unavailable",
                "resume_unavailable",
                "the transfer already reached a terminal state",
                status=409,
                next_action="inspect the recorded per-item outcomes",
            )
        self._direct.tasks.requeue(task_id)
        transfer = self._direct.tasks.repository.requeue_files_transfer(
            transfer.transfer_id, datetime.now(UTC)
        )
        return self.transfer_projection(task_id)

    def transfer_projection(self, task_id: str) -> dict[str, object]:
        """The durable, bounded operator projection of one transfer Task.

        Rebuilt from the persisted Task, items, progress snapshots and
        Results — never from a request-scoped execution result — so polling
        after admission or a process restart reproduces the truthful state
        with the backend-advertised lifecycle actions.
        """

        repository = self._direct.tasks.repository
        task = repository.get_task(task_id)
        if task is None or task.command != FILES_TRANSFER_TASK_COMMAND:
            raise DirectFileTransferError(
                "files_transfer_unknown",
                "not_found",
                "no bounded Files transfer Task exists under this identity",
                status=404,
                next_action="return to the Files workspace and refresh",
            )
        transfer = repository.get_files_transfer_for_task(task_id)
        items = repository.list_items(task_id)
        results = {record.item_id: record for record in repository.list_results(task_id)}
        known_effects: list[dict[str, object]] = []
        item_summaries: list[dict[str, object]] = []
        outcomes: list[dict[str, object]] = []
        truncated_outcomes = False
        uncertain = task.error == "mutation_outcome"
        succeeded = failed = skipped = partial = 0
        item_statuses: set[str] = set()
        known_mutation = False
        for item in items:
            record = results.get(item.item_id)
            payload = _progress_payload(item)
            outcome_status = _projection_item_status(item, record)
            if (
                outcome_status == "PARTIAL"
                and record is not None
                and record.effect_certainty == ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED.value
            ):
                outcome_status = "UNCERTAIN"
            item_statuses.add(outcome_status)
            if outcome_status in {"SUCCESS", "PARTIAL"} or (
                record is not None
                and _completed_operations_have_mutation(record.completed_operations)
            ):
                known_mutation = True
            if outcome_status == "SUCCESS":
                succeeded += 1
            elif outcome_status == "SKIPPED":
                skipped += 1
            elif outcome_status == "PARTIAL":
                partial += 1
            elif outcome_status in {"FAILED", "UNCERTAIN"}:
                if outcome_status == "UNCERTAIN":
                    uncertain = True
                failed += 1
            known_effects.append(
                {
                    "path": item.source_display,
                    "effect": _PROJECTION_EFFECT.get(outcome_status, "in_progress"),
                    "status": outcome_status,
                }
            )
            summary: dict[str, object] = {
                "path": item.source_display,
                "destination": item.destination_path or item.source_display,
                "status": outcome_status,
            }
            if item.error and outcome_status not in {"SUCCESS", "SKIPPED"}:
                summary["errorCategory"] = item.error
            item_summaries.append(summary)
            entry_outcomes, entry_truncated = _projection_item_outcomes(
                item, payload, record, outcome_status
            )
            if truncated_outcomes or len(outcomes) + len(entry_outcomes) > _MAX_PROJECTION_OUTCOMES:
                truncated_outcomes = True
            outcomes.extend(entry_outcomes[: max(0, _MAX_PROJECTION_OUTCOMES - len(outcomes))])
        transfer_status = _projection_transfer_status(
            task=task,
            transfer=transfer,
            uncertain=uncertain,
            statuses=item_statuses,
            known_mutation=known_mutation,
        )
        terminal = task.status in {
            PersistentTaskStatus.COMPLETED,
            PersistentTaskStatus.PARTIAL_SUCCESS,
            PersistentTaskStatus.FAILED,
            PersistentTaskStatus.CANCELLED,
        }
        claim_live = (
            transfer is not None
            and transfer.status is FilesTransferStatus.RUNNING
            and transfer.claim_expires_at is not None
            and transfer.claim_expires_at > datetime.now(UTC)
        )
        document: dict[str, object] = {
            "operation": _projection_operation(transfer),
            "conflictMode": _projection_conflict_mode(transfer),
            "taskId": task.task_id,
            "taskStatus": task.status.value,
            "resourceLibraryId": _projection_source_library(transfer, items),
            "destinationResourceLibraryId": _projection_destination_library(transfer, items),
            "topLevelPaths": [item.source_display for item in items],
            "knownEffects": known_effects,
            "itemOutcomes": item_summaries[:MAX_TRANSFER_PATHS],
            "outcomes": outcomes,
            "outcomesTruncated": truncated_outcomes,
            "totalItems": len(items),
            "succeededItems": succeeded,
            "skippedItems": skipped,
            "failedItems": failed + partial,
            "status": transfer_status,
            "terminal": terminal,
            "actions": _transfer_actions(task, claim_live),
            "version": task.updated_at.isoformat(),
            "sideEffects": "storage_mutations" if any(item.attempts for item in items) else "none",
            "retrySafe": False,
            "nextAction": _projection_next_action(task, transfer_status, terminal),
        }
        if uncertain:
            document["durableState"] = "mutation_effect_uncertain"
        return document

    # ------------------------------------------------------------------
    # Per-item execution
    # ------------------------------------------------------------------

    def _mark_interrupted_item(
        self,
        item: PersistentTaskItem,
        code: str,
        *,
        mutated: bool = False,
        uncertain: bool = False,
        fence: _ClaimFence | None = None,
    ) -> None:
        """Record one item as an explicit interrupted/investigation state.

        The item is never marked as a clean failure or a replayable retry: its
        recorded effects stay authoritative and the code names exactly why the
        continuation stopped.  Effect certainty is mapped independently from
        the outcome wording: an unprovable effect is ``attempted_unverified``, a
        verified known effect is ``verified_complete`` and a stop with zero
        attempted mutation records ``none``.
        """

        published = self._direct.tasks.complete_direct_item(
            item,
            status=TaskItemStatus.PARTIAL if (mutated or uncertain) else TaskItemStatus.FAILED,
            operation="transfer",
            error=code,
            effect_certainty=_result_certainty(mutated=mutated, uncertain=uncertain),
            uncertain_effects=("mutation_outcome",) if uncertain else (),
            stage=TRANSFER_INTERRUPTED_STAGE,
            transfer_fence=fence.value if fence is not None else None,
        )
        if published is False:
            raise _TransferClaimLost()

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
        interruption: Callable[[], str | None] | None = None,
        collect: Callable[[list[dict[str, object]]], None] | None = None,
        fence: _ClaimFence | None = None,
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
        checkpoint instead of an unknown state.  A Worker-driven item passes
        ``interruption`` (which additionally verifies the live claim) and
        ``collect`` (which accumulates its outcomes for the durable
        completion publish).
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
                fence=fence,
            )

        if interruption is None:

            def interruption() -> str | None:
                if self._direct.tasks.cancellation_observed(task_id):
                    return "cancel"
                if self._direct.tasks.pause_requested(task_id):
                    return "pause"
                return None

        # The Worker-driven caller receives every recorded outcome through
        # ``collect`` exactly once — including each early return (batch
        # conflict, top-level conflict refusal, failed directory creation,
        # pause/cancel) — so its terminal publish covers the whole item.
        if collect is not None:
            try:
                return self._execute_item_entries(
                    plan=plan,
                    top_level=top_level,
                    source=source,
                    destination=destination,
                    source_storage=source_storage,
                    destination_storage=destination_storage,
                    checkpoints=checkpoints,
                    task_id=task_id,
                    item=item,
                    batch_conflict=batch_conflict,
                    destination_root=destination_root,
                    confirmed_entries=confirmed_entries,
                    confirmed_truncated=confirmed_truncated,
                    skip_paths=skip_paths,
                    interruption=interruption,
                    progress=progress,
                    entries=entries,
                    recorded=recorded,
                    collect=collect,
                    fence=fence,
                )
            finally:
                collect(recorded)
        return self._execute_item_entries(
            plan=plan,
            top_level=top_level,
            source=source,
            destination=destination,
            source_storage=source_storage,
            destination_storage=destination_storage,
            checkpoints=checkpoints,
            task_id=task_id,
            item=item,
            batch_conflict=batch_conflict,
            destination_root=destination_root,
            confirmed_entries=confirmed_entries,
            confirmed_truncated=confirmed_truncated,
            skip_paths=skip_paths,
            interruption=interruption,
            progress=progress,
            entries=entries,
            recorded=recorded,
            collect=None,
            fence=fence,
        )

    def _execute_item_entries(
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
        confirmed_entries: tuple[tuple[str, str, str], ...],
        confirmed_truncated: bool,
        skip_paths: frozenset[str],
        interruption: Callable[[], str | None],
        progress: Callable[[], None],
        entries: list[TransferManifestEntry],
        recorded: list[dict[str, object]],
        collect: Callable[[list[dict[str, object]]], None] | None,
        fence: _ClaimFence | None = None,
    ) -> tuple[list[dict[str, object]], bool, bool]:

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
            self._open_mutation(fence, item, entry_path=entry.path, action="create_directory")
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
                    item=item,
                    fence=fence,
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
                item=item,
                fence=fence,
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
            removals, stop = self._remove_emptied_source_directories(
                plan,
                top_level,
                entries,
                source,
                source_storage,
                checkpoints,
                completed_files,
                progress=progress,
                interruption=interruption,
                item=item,
                fence=fence,
            )
            recorded.extend(removals)
            if stop is not None:
                return recorded, stop == "pause", stop == "cancel"
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
        fence: _ClaimFence | None = None,
    ) -> None:
        """Persist the bounded in-flight progress snapshot of one item.

        The snapshot carries the item's endpoint identities, requested
        operation and conflict choice beside the confirmed scope, so the
        durable continuation never has to re-derive an admission decision
        that was already pinned.  On the Worker path the write is
        claim-guarded: a Worker that lost ownership stops instead of publishing
        a stale snapshot over a newer owner's progress.
        """

        completed = sum(1 for value in recorded if value.get("status") == "SUCCESS")
        failed = sum(
            1 for value in recorded if value.get("status") in {"FAILED", "PARTIAL", "UNCERTAIN"}
        )
        skipped = sum(1 for value in recorded if value.get("status") == "SKIPPED")
        published = self._direct.tasks.record_transfer_progress(
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
                    **(
                        {"errorCategory": str(value.get("errorCategory"))}
                        if value.get("errorCategory")
                        else {}
                    ),
                }
                for value in recorded[:MAX_TRANSFER_PROGRESS_ENTRIES]
            ),
            completed_entries=completed + skip_count,
            failed_entries=failed,
            skipped_entries=skipped,
            truncated=len(recorded) > MAX_TRANSFER_PROGRESS_ENTRIES,
            transfer_fence=fence.value if fence is not None else None,
        )
        if published is False:
            raise _TransferClaimLost()

    def _resume_entry_outcome(
        self,
        plan: _TransferPlan,
        entry: TransferManifestEntry,
        destination_path: str,
        source: ResourceLibrary,
        destination: ResourceLibrary,
        source_storage: Storage,
        destination_storage: Storage,
        *,
        item: PersistentTaskItem | None = None,
        fence: _ClaimFence | None = None,
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
                if item is not None:
                    self._open_mutation(fence, item, entry_path=entry.path, action="move")
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
        *,
        item: PersistentTaskItem | None = None,
        fence: _ClaimFence | None = None,
    ) -> dict[str, object]:
        """Execute one file entry through the executor's native-only path.

        The same/cross-Storage decision is the validated business decision
        pinned in the confirmed plan — never incidental adapter object
        identity.  The exact in-flight mutation boundary is published before
        the executor call, so a blocked or stalled provider operation can never
        be handed to a second Worker as replayable work.
        """

        if item is not None:
            self._open_mutation(
                fence, item, entry_path=entry.path, action=self._mutation_action(plan)
            )
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
        progress: Callable[[], None] | None = None,
        interruption: Callable[[], str | None] | None = None,
        item: PersistentTaskItem | None = None,
        fence: _ClaimFence | None = None,
    ) -> tuple[list[dict[str, object]], str | None]:
        """Remove the source directories the verified Move just emptied.

        Only directories whose confirmed children all reported a completed
        transfer are candidates, and the executor re-lists each one immediately
        before the removal.  An unknown or newly appeared entry stops the
        removal without a recursive delete, an already-absent virtual prefix
        (S3/R2) is truthfully recorded instead of deleting a fictional object,
        and a failed removal keeps the directory Move from being reported
        wholly successful.

        A Worker-driven Move observes pause/cancel and its live claim around
        every source-directory removal, so a stalled or lost owner stops before
        the next destructive step and each completed removal is published as
        durable progress before the following one begins.  The observed
        interruption is returned so the caller keeps the pause/cancel outcome
        instead of reporting a completed item.

        Returns ``(outcomes, observed interruption)``.
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
            stop = interruption() if interruption is not None else None
            if stop is not None:
                return outcomes, stop
            full = _join_resource_library_path(source.root_path, entry.path)
            if item is not None:
                self._open_mutation(fence, item, entry_path=entry.path, action="remove_directory")
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
            if progress is not None:
                progress()
        return outcomes, None

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


class _TransferClaimLost(RuntimeError):
    """The Worker's lease expired or was taken over mid-execution."""


class _TransferSnapshotUnavailable(RuntimeError):
    """This Worker cannot lawfully reconstruct the transfer's pinned revision.

    The transfer is not a business failure: the claim is released with bounded
    readiness evidence so a compatible Worker can execute it under exactly the
    configuration it was admitted against.
    """


class _TransferAuthorityUnreadable(RuntimeError):
    """The persisted confirmed authority cannot be read or reconstructed.

    No Worker can lawfully execute it, so it converges to a bounded
    investigation outcome without invoking any Storage operation and without
    pretending it was a retryable business failure.
    """


class _TransferCancelled(RuntimeError):
    """One durable cooperative cancellation was observed at a safe boundary."""


class _TransferExecutionFailed(RuntimeError):
    """One claimed transfer failed before it could reach its Task aggregate."""


def _bounded_transfer_error(error: BaseException | None, code: str | None = None) -> str:
    """A bounded, secret-free error identity for one failed transfer."""

    if code:
        return code
    if isinstance(error, DirectFileTransferError):
        return error.code
    return f"files_transfer_worker_failed_{type(error).__name__}"


def _item_known_mutation(
    item: PersistentTaskItem, record: PersistentResultRecord | None
) -> tuple[bool, bool]:
    """Whether one item already recorded a known mutation, and its certainty.

    The durable per-entry progress of a started item is the authoritative
    known-effect evidence after an unexpected failure: an entry marked
    ``UNCERTAIN`` (or an item already carrying the uncertain marker) means the
    effect cannot be proven and must be investigation-only; any other recorded
    non-skipped entry means a mutation may already have happened.
    """

    if item.error == "mutation_outcome":
        return True, True
    if record is not None:
        if record.effect_certainty == ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED.value:
            return True, True
        if record.effect_certainty == ExecutionEffectCertainty.VERIFIED_COMPLETE.value:
            return True, False
    payload = _progress_payload(item)
    if payload is None:
        return False, False
    statuses = {
        str(value.get("status", ""))
        for value in payload.get("entries") or ()
        if isinstance(value, dict)
    }
    if "UNCERTAIN" in statuses:
        return True, True
    completed = payload.get("completedEntries")
    if statuses & {"SUCCESS", "PARTIAL"} or (isinstance(completed, int) and completed > 0):
        return True, False
    return False, False


def _interrupted_terminal_item(
    item: PersistentTaskItem,
    *,
    uncertain: bool,
    mutated: bool,
    now: datetime,
    code: str,
) -> tuple[PersistentTaskItem, PersistentResultRecord]:
    """One unfinished transfer item converged to an explicit terminal state.

    The item keeps its recorded known-safe progress evidence but becomes a
    terminal interrupted/investigation outcome with a bounded Result, so a
    reloaded Task/Result detail never shows a permanently processing item
    beside a terminal transfer.  The bounded per-entry checkpoint evidence that
    produced the aggregate decision is preserved in the terminal Result rather
    than discarded, and an uncertain known effect stays uncertain while an item
    whose mutation effect is unproven is investigation-only and never silently
    retried.
    """

    status = TaskItemStatus.PARTIAL if (mutated or uncertain) else TaskItemStatus.FAILED
    completed_operations = _progress_checkpoint_evidence(item)
    terminal = replace(
        item,
        status=status,
        stage=TRANSFER_INTERRUPTED_STAGE,
        updated_at=now,
        error=code,
        progress=None,
    )
    record = PersistentResultRecord(
        f"{item.item_id}:{item.attempts}",
        item.task_id,
        item.item_id,
        item.storage_id,
        item.source_display or item.source_path,
        item.destination_storage_id,
        item.destination_path,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "transfer",
        status.value,
        now,
        error=code,
        completed_operations=completed_operations,
        effect_certainty=_result_certainty(mutated=mutated, uncertain=uncertain),
        uncertain_effects=("mutation_outcome",) if uncertain else (),
    )
    return terminal, record


def _progress_checkpoint_evidence(item: PersistentTaskItem) -> tuple[str, ...]:
    """The bounded per-entry evidence still recorded on one unfinished item.

    The in-flight progress snapshot is the authoritative known-effect evidence
    after an unexpected failure; preserving it in the terminal Result lets a
    reloaded detail reproduce exactly which entries completed, skipped or were
    refused instead of collapsing the item to one opaque outcome.
    """

    payload = _progress_payload(item)
    if payload is None:
        return ()
    values: list[str] = []
    for value in payload.get("entries") or ():
        if not isinstance(value, dict):
            continue
        path = str(value.get("path", ""))
        values.append(f"entry:{value.get('status', '')}:{path}")
        if value.get("errorCategory"):
            values.append(f"entry_error:{value.get('errorCategory')}:{path}")
    if len(values) > MAX_TRANSFER_PROGRESS_ENTRIES:
        values = values[:MAX_TRANSFER_PROGRESS_ENTRIES]
        values.append("transfer_checkpoints_truncated")
    return tuple(values)


def _transfer_authority(manifest: TransferManifest) -> str:
    """The bounded, claimable admission authority of one confirmed transfer.

    It pins everything a Worker must reconstruct the exact confirmed
    operation after a process restart: the configuration revision/digest,
    both endpoint ResourceLibrary/Storage identities, the normalized logical
    paths, the operation, the conflict choice, the confirmed per-entry scope
    and the pinned keep-both destinations.  Host roots, credentials, provider
    payloads and content never enter the authority.
    """

    document = {
        "version": 1,
        "revisionId": manifest.revision_id,
        "revisionDigest": manifest.revision_digest,
        "sourceResourceLibraryId": manifest.source_resource_library_id,
        "sourceStorageId": manifest.source_storage_id,
        "destinationResourceLibraryId": manifest.destination_resource_library_id,
        "destinationStorageId": manifest.destination_storage_id,
        "destinationDirectory": manifest.destination_directory,
        "operation": manifest.operation.value,
        "conflictMode": manifest.conflict_mode.value,
        "sameStorage": manifest.same_storage,
        "topLevelPaths": list(manifest.top_level_paths),
        "entries": [
            [entry.path, entry.kind.value, entry.size, entry.modified_at, entry.fingerprint]
            for entry in manifest.entries
        ],
        "destinations": [[path, destination] for path, destination in manifest.destinations],
        "keepBothNames": [[path, destination] for path, destination in manifest.keep_both_names],
        "manifestDigest": manifest.digest,
    }
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse_authority(authority_json: str) -> dict[str, object]:
    """The parsed persisted authority, or a fail-closed empty document."""

    try:
        parsed = json.loads(authority_json)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _plan_source_library(authority: dict[str, object]) -> str:
    return str(authority.get("sourceResourceLibraryId", ""))


def _admitted_item(
    task_id: str,
    manifest: TransferManifest,
    top_level: str,
) -> PersistentTaskItem:
    """The queued TaskItem of one top-level selection with its authority.

    The per-item authority is the same bounded progress shape the in-flight
    execution later maintains: confirmed per-entry scope (this item's slice,
    bounded), endpoint identities, operation and conflict choice.  A Worker
    that never started the item executes it from the full pinned admission
    authority instead, so a scope larger than the per-item continuation bound
    still transfers once.
    """

    source_storage_id = manifest.source_storage_id
    item_id = str(
        uuid5(
            NAMESPACE_URL, f"{task_id}:{source_storage_id}:{_item_full_path(manifest, top_level)}"
        )
    )
    confirmed_scope = tuple(
        (entry.path, manifest.destination_for(entry.path) or entry.path, entry.kind.value)
        for entry in manifest.entries
        if entry.path == top_level or entry.path.startswith(f"{top_level}/")
    )
    truncated = len(confirmed_scope) > MAX_TRANSFER_PROGRESS_ENTRIES
    payload = {
        "version": 1,
        "status": "pending",
        "operation": manifest.operation.value,
        "conflictMode": manifest.conflict_mode.value,
        "destinationStorageId": manifest.destination_storage_id,
        "destinationResourceLibraryId": manifest.destination_resource_library_id,
        "destinationPath": manifest.destination_for(top_level) or top_level,
        "confirmedEntries": [
            list(entry) for entry in confirmed_scope[:MAX_TRANSFER_PROGRESS_ENTRIES]
        ],
        "confirmedTruncated": truncated,
        "completedEntries": 0,
        "failedEntries": 0,
        "skippedEntries": 0,
        "truncated": False,
        "entries": [],
    }
    now = datetime.now(UTC)
    return PersistentTaskItem(
        item_id,
        task_id,
        source_storage_id,
        manifest.source_resource_library_id,
        _item_full_path(manifest, top_level),
        top_level,
        TaskItemStatus.PENDING,
        "admitted",
        0,
        now,
        now,
        destination_storage_id=manifest.destination_storage_id,
        destination_path=payload["destinationPath"],
        progress=json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


def _item_full_path(manifest: TransferManifest, relative: str) -> str:
    return f"{manifest.source_root}/{relative}" if manifest.source_root else relative


def _queued_document(
    task: PersistentTask,
    manifest: TransferManifest,
    items: tuple[PersistentTaskItem, ...],
) -> dict[str, object]:
    """The immediate durable operator projection of one admitted transfer.

    The mutation request returns this before the first Storage mutation: the
    Web follows the queued transfer through the projection read instead of
    holding a request open, and no raw Task ID copy/paste or execution token
    is needed.
    """

    return {
        "operation": manifest.operation.value,
        "conflictMode": manifest.conflict_mode.value,
        "sameStorage": manifest.same_storage,
        "status": "QUEUED",
        "admitted": True,
        "taskId": task.task_id,
        "taskStatus": task.status.value,
        "resourceLibraryId": manifest.source_resource_library_id,
        "destinationResourceLibraryId": manifest.destination_resource_library_id,
        # The exact selected top-level path strings.  The per-entry destination
        # pairs travel in ``destinations``; serializing them here would hand the
        # browser a nested tuple per path and break the shared admission
        # contract the projection and every terminal read already use.
        "topLevelPaths": list(manifest.top_level_paths),
        "destinations": [
            {"path": path, "destination": value} for path, value in manifest.destinations
        ],
        "knownEffects": [],
        "itemOutcomes": [
            {
                "path": item.source_display,
                "destination": item.destination_path or item.source_display,
                "status": "QUEUED",
            }
            for item in items
        ],
        "checkpoints": [],
        "checkpointsTruncated": False,
        "totalItems": len(items),
        "succeededItems": 0,
        "skippedItems": 0,
        "failedItems": 0,
        "outcomes": [],
        "outcomesTruncated": False,
        "sideEffects": "none",
        "retrySafe": True,
        "nextAction": (
            "the transfer is admitted and queued for execution; its progress appears below"
        ),
    }


def _projection_item_status(item: PersistentTaskItem, record: PersistentResultRecord | None) -> str:
    """The truthful projection status of one transfer item."""

    if item.status is TaskItemStatus.PENDING:
        return "QUEUED"
    if item.status in {TaskItemStatus.PROCESSING}:
        return "RUNNING"
    if item.status is TaskItemStatus.PAUSED:
        return "PAUSED"
    if item.status is TaskItemStatus.CANCELLED:
        return "CANCELLED"
    if record is not None:
        record_status = record.status.upper()
        if record_status == "PARTIAL":
            return "PARTIAL"
        if record_status == "SKIPPED":
            return "SKIPPED"
        if record_status == "FAILED":
            return "FAILED"
        if record_status == "SUCCESS":
            return "SUCCESS"
    return _ITEM_TASK_INVERSE.get(item.status, "FAILED")


#: The bounded per-entry outcome surface of one projection.
_MAX_PROJECTION_OUTCOMES = MAX_TRANSFER_PATHS * 64


def _projection_item_outcomes(
    item: PersistentTaskItem,
    payload: dict[str, object] | None,
    record: PersistentResultRecord | None,
    outcome_status: str,
) -> tuple[list[dict[str, object]], bool]:
    """The durable per-entry outcomes of one transfer item.

    A started item's recorded per-entry progress is the source of truth while
    it stays unfinished; a finished item's Result annotations (completed
    executor checkpoints plus the retained skipped-child evidence) reproduce
    the same per-entry truth after the progress marker was consumed.
    """

    outcomes: list[dict[str, object]] = []
    if payload is not None and item.status in {
        TaskItemStatus.PROCESSING,
        TaskItemStatus.PAUSED,
        TaskItemStatus.PENDING,
    }:
        for entry in payload.get("entries") or ():
            if not isinstance(entry, dict):
                continue
            outcome: dict[str, object] = {
                "path": str(entry.get("path", "")),
                "destination": str(entry.get("destination", "")),
                "status": str(entry.get("status", "")),
                "checkpoints": [],
            }
            if entry.get("errorCategory"):
                outcome["errorCategory"] = str(entry.get("errorCategory"))
            outcomes.append(outcome)
        return outcomes, bool(payload.get("truncated"))
    if record is None:
        return outcomes, False
    destination = item.destination_path or ""
    if not record.completed_operations:
        # A refused/failed item records no executor checkpoint: its single
        # truthful outcome is the item's own durable failure evidence.
        outcomes.append(
            {
                "path": item.source_display,
                "destination": destination,
                "status": outcome_status,
                "checkpoints": [],
                **({"errorCategory": record.error} if record.error else {}),
            }
        )
        return outcomes, False
    # The Result annotations group into one outcome per entry path, keeping
    # each compound checkpoint order (copy_written, destination_verified,
    # source_deleted), the exact per-entry status and the skipped-child
    # evidence beside the entry it belongs to.
    grouped: dict[str, dict[str, object]] = {}

    def entry_for(path: str) -> dict[str, object]:
        return grouped.setdefault(
            path,
            {
                "path": path,
                "destination": destination,
                "status": outcome_status,
                "checkpoints": [],
            },
        )

    for annotation in record.completed_operations:
        name, separator, rest = str(annotation).partition(":")
        if not separator or not rest:
            entry_for(item.source_display)["checkpoints"].append(name)
            continue
        if name == "entry":
            status, _, path = rest.partition(":")
            if path:
                entry_for(path)["status"] = status or outcome_status
            continue
        if name == "entry_error":
            category, _, path = rest.partition(":")
            if path:
                entry_for(path)["errorCategory"] = category
            continue
        if name == "skip_conflict":
            entry = entry_for(rest)
            entry["status"] = "SKIPPED"
            entry["errorCategory"] = "target_exists"
            continue
        entry_for(rest)["checkpoints"].append(name)
    outcomes.extend(grouped.values())
    return outcomes, False


def _projection_transfer_status(
    *,
    task: PersistentTask,
    transfer: PersistentFilesTransfer | None,
    uncertain: bool,
    statuses: set[str],
    known_mutation: bool,
) -> str:
    """The aggregate projection status of one durable transfer Task.

    The same deterministic precedence used by the durable Task/transfer rows
    and by the response aggregate decides the terminal states, so the Files and
    Operations projections can never disagree with what was persisted.
    """

    del transfer
    if uncertain:
        return "UNCERTAIN"
    if task.status is PersistentTaskStatus.PENDING:
        return "QUEUED"
    if task.status is PersistentTaskStatus.RUNNING:
        return "RUNNING"
    if task.status is PersistentTaskStatus.PAUSED:
        return "PAUSED"
    if task.status is PersistentTaskStatus.CANCELLED:
        return "CANCELLED"
    return _precedence_status(statuses, known_mutation=known_mutation, uncertain=uncertain)


def _projection_operation(transfer: PersistentFilesTransfer | None) -> str:
    if transfer is None:
        return "transfer"
    authority = _parse_authority(transfer.authority_json)
    return str(authority.get("operation", "transfer"))


def _projection_conflict_mode(transfer: PersistentFilesTransfer | None) -> str:
    if transfer is None:
        return "fail"
    authority = _parse_authority(transfer.authority_json)
    return str(authority.get("conflictMode", "fail"))


def _projection_source_library(
    transfer: PersistentFilesTransfer | None, items: tuple[PersistentTaskItem, ...]
) -> str:
    if transfer is not None:
        return _plan_source_library(_parse_authority(transfer.authority_json))
    return items[0].resource_library_id if items else ""


def _projection_destination_library(
    transfer: PersistentFilesTransfer | None, items: tuple[PersistentTaskItem, ...]
) -> str:
    if transfer is not None:
        return str(
            _parse_authority(transfer.authority_json).get("destinationResourceLibraryId", "")
        )
    return items[0].destination_storage_id or "" if items else ""


def _transfer_actions(task: PersistentTask, claim_live: bool) -> list[dict[str, object]]:
    """The backend-advertised lifecycle actions of one durable transfer."""

    permitted = True
    actions: list[dict[str, object]] = []
    if task.status is PersistentTaskStatus.RUNNING and not task.pause_requested:
        actions.append(
            {
                "action": "pause",
                "available": True,
                "path": f"/api/v1/tasks/{task.task_id}/pause",
            }
        )
    else:
        actions.append(
            {
                "action": "pause",
                "available": False,
                "reason": f"a {task.status.value} transfer cannot be paused",
            }
        )
    if task.status in {
        PersistentTaskStatus.PENDING,
        PersistentTaskStatus.RUNNING,
        PersistentTaskStatus.PAUSED,
    }:
        actions.append(
            {
                "action": "cancel",
                "available": True,
                "path": f"/api/v1/tasks/{task.task_id}/cancel",
            }
        )
    else:
        actions.append(
            {
                "action": "cancel",
                "available": False,
                "reason": "the transfer already reached a terminal state",
            }
        )
    if task.status is PersistentTaskStatus.PAUSED or (
        task.status is PersistentTaskStatus.RUNNING and not claim_live
    ):
        actions.append(
            {
                "action": "resume",
                "available": True,
                "path": f"/api/v1/tasks/{task.task_id}/resume",
            }
        )
    else:
        actions.append(
            {
                "action": "resume",
                "available": False,
                "reason": (
                    "the transfer is queued or running"
                    if not claim_live
                    else "the transfer is running under a live Worker claim"
                ),
            }
        )
    del permitted
    return actions


def _projection_next_action(task: PersistentTask, transfer_status: str, terminal: bool) -> str:
    if transfer_status == "UNCERTAIN":
        return (
            "an interrupted item could not be safely continued; refresh both directories and "
            "inspect the Task before any retry — uncertain effects are never replayed"
        )
    if task.status is PersistentTaskStatus.PENDING:
        return "the transfer is queued for the resident Worker; its progress appears here"
    if task.status is PersistentTaskStatus.RUNNING:
        return "the transfer is running; its per-item progress appears here"
    if task.status is PersistentTaskStatus.PAUSED:
        return (
            "the transfer is paused at a safe boundary; resume continues from the "
            "recorded checkpoints"
        )
    if task.status is PersistentTaskStatus.CANCELLED:
        return (
            "the transfer was cancelled; completed effects stay terminal and each item "
            "keeps its durable outcome"
        )
    if terminal:
        return "refresh the source and destination directories to see the current state"
    return "refresh both directories; each item keeps its own durable outcome"
