"""Analysis-only manual-organize Preview application boundary.

This module deliberately stops at a persisted, inspectable plan.  It does not
create a Task or Job, grant execution authority, or call ``OrganizerExecutor``.
The existing strategy and planning services remain the decision authorities;
this service only pins their inputs and converts their bounded results into a
restart-safe operator projection.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from mediaflow.application.attachments import (
    AttachmentDiscovery,
    AttachmentPlanner,
    attachment_result_document,
)
from mediaflow.application.conflict_resolution import ConflictResolver
from mediaflow.application.duplicates import apply_hash_duplicate_detection
from mediaflow.application.media_parser import MediaParserService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.organizer import OrganizePlanner, OrganizerExecutor
from mediaflow.application.read_only_storage import (
    ReadOnlyStorageGuard,
    ReadOnlyStorageMutationError,
)
from mediaflow.application.recognition import RecognitionRuleEngine
from mediaflow.application.scan_filters import StabilityVerdict, stability_decision
from mediaflow.application.strategy_test import (
    StrategyConfigurationError,
    StrategyTestRunner,
    file_context_from_path,
    strategy_runner_from_configuration,
)
from mediaflow.domain.classification import ClassificationStatus
from mediaflow.domain.classification_review import ClassificationSelection
from mediaflow.domain.manual_organize import (
    ManualChoice,
    ManualIntentError,
    ManualIntentItemStatus,
    ManualIntentUnavailable,
    ManualOrganizeIntent,
    ManualSourceIdentity,
)
from mediaflow.domain.manual_organize_preview import (
    MAX_MANUAL_PREVIEW_ITEMS,
    MAX_MANUAL_PREVIEW_PLAN_BYTES,
    ManualOrganizePreview,
    ManualPreviewConflict,
    ManualPreviewError,
    ManualPreviewItem,
    ManualPreviewItemStatus,
    ManualPreviewStatus,
    ManualPreviewUnavailable,
)
from mediaflow.domain.manual_safety import safe_manual_error
from mediaflow.domain.metadata import (
    MediaIdentity,
    MediaQueryType,
    MediaType,
    MetadataIdentificationStatus,
)
from mediaflow.domain.metadata_correction import MetadataCorrectionSelection
from mediaflow.domain.metadata_review import MetadataSelection
from mediaflow.domain.organizer import (
    ConflictStrategy,
    DirectoryCleanupMode,
    MediaFileSet,
    OrganizePlan,
    PlanOperation,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.preview_analysis import PreviewAnalysisControlRequested
from mediaflow.domain.recognition import RecognitionContext, RecognitionStatus
from mediaflow.domain.source_evidence import (
    OccurrenceState,
    occurrence_id_for,
    source_fingerprint,
)
from mediaflow.domain.storage import Storage, StorageEntry, StorageEntryType, StorageError

_MAX_COLLECTION = 64
_MAX_TEXT = 512
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class PreviewReadOnlyStorage(ReadOnlyStorageGuard):
    """A read-only adapter that preserves declared capability evidence.

    ``ReadOnlyStorageGuard`` intentionally exposes no capabilities because it
    is used by the strategy-test command.  Preview needs to show the real
    configured capability verdict while still making every mutating method
    fail before reaching the underlying adapter.
    """

    @property
    def capabilities(self):
        return self._storage.capabilities


ManualPreviewReadOnlyStorage = PreviewReadOnlyStorage


@dataclass(frozen=True)
class _PreviewOutcome:
    status: ManualPreviewItemStatus
    plan: dict[str, object] | None = None
    plan_fingerprint: str | None = None
    error: str | None = None
    next_action: str = "request a fresh Preview for this item"
    truncated: bool = False
    #: The *business* kind of one blocked outcome: ``recognition``,
    #: ``metadata``, ``metadata_correction``, ``classification`` or
    #: ``conflict``.  ``None`` means the item is not one of the four native
    #: organizing problems (a technical failure, an unavailable provider or a
    #: genuinely tracable input).  The Worker uses this to give the admitted
    #: organizing Task its real per-item problem instead of leaving an operator
    #: with a summary they can never resolve.
    problem: str | None = None
    #: The analysis evidence the native review is created from.  It is only
    #: populated together with ``problem`` and is never persisted as such.
    strategy: object | None = None


@dataclass(frozen=True)
class _BoundSourceDecisions:
    """One item's newest resolved continuation decisions for its own source."""

    confirmation: object | None = None
    metadata_review: object | None = None
    metadata_correction: object | None = None
    classification_review: object | None = None
    recognition_review: object | None = None


class ManualOrganizePreviewService:
    """Create and inspect durable, zero-mutation manual Previews."""

    MAX_ITEMS = MAX_MANUAL_PREVIEW_ITEMS

    def __init__(
        self,
        repository,
        intent_service,
        *,
        configuration_service=None,
        runtime_resolver: Callable[..., object] | None = None,
        configuration: object | None = None,
        strategy_runner_factory: Callable[..., StrategyTestRunner] | None = None,
        metadata_provider_registry_factory: Callable[..., MetadataProviderRegistry] | None = None,
        providers: MetadataProviderRegistry | None = None,
        storages: Mapping[str, Storage] | None = None,
        storage_factory: Callable[..., Mapping[str, Storage]] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        max_items: int = MAX_MANUAL_PREVIEW_ITEMS,
    ) -> None:
        if isinstance(max_items, bool) or not 1 <= max_items <= MAX_MANUAL_PREVIEW_ITEMS:
            raise ValueError(
                f"manual Preview limit must be between 1 and {MAX_MANUAL_PREVIEW_ITEMS}"
            )
        self._repository = repository
        self._intent_service = intent_service
        self._configuration_service = configuration_service or getattr(
            intent_service, "_configuration_service", None
        )
        self._runtime_resolver = runtime_resolver
        self._configuration = configuration
        self._strategy_runner_factory = strategy_runner_factory
        self._provider_factory = metadata_provider_registry_factory
        self._providers = providers
        self._storages = dict(storages or {})
        self._storage_factory = storage_factory
        self._clock = clock
        self._max_items = max_items
        self._provider_cache: dict[tuple[str, ...], MetadataProviderRegistry] = {}

    @property
    def repository(self):
        return self._repository

    def create(
        self,
        intent_id: str,
        item_ids: Sequence[str] | None = None,
        *,
        expected_version: int | None = None,
        actor: str,
        expected_item_versions: Mapping[str, int] | Sequence[int] | None = None,
        snapshot_id: str | None = None,
        snapshot_digest: str | None = None,
        source_scope: str | None = None,
        source_scope_id: str | None = None,
        source_admission_errors: Mapping[str, ManualPreviewError] | None = None,
        review_decisions: object | None = None,
        reuse_analysis_identity: object | None = None,
        require_durable_identity: bool = False,
        skip_current_snapshot_check: bool = False,
        recovery_source_task_id: str | None = None,
        tolerate_unready_sources: bool = False,
        persist: bool = True,
        problem_task_id: str | None = None,
        analysis_checkpoint: Callable[[str, int, int, int], None] | None = None,
    ) -> ManualOrganizePreview:
        """Create one durable zero-mutation Preview.

        ``skip_current_snapshot_check`` is the one explicit opt-in for a
        *pinned historical* intent: the caller has already proven the exact
        published revision through managed authority, and the remaining-scope
        recovery path must review the plan under that pin rather than under the
        current Active revision.  The ordinary Files path keeps the strict
        current-Active rule.

        ``problem_task_id`` names the admitted organizing Task whose own per-item
        four-type problems this analysis should publish.  It is supplied only by
        the bounded discovery Worker for a Files-admitted run, so the Task the
        operator sees in Running/Attention really owns the problem its own analysis
        found; the ordinary Preview path leaves it ``None`` and publishes nothing.
        The live analysis objects are used directly, so no domain value is ever
        reconstructed from a document.

        ``tolerate_unready_sources`` is the one explicit opt-in for the RO-2
        same-page preparation re-analysis: one source that is missing or has
        changed becomes its own bounded per-item finding instead of aborting
        the whole analysis.  That keeps a failed sibling from erasing the
        correction and readable state of every other remaining item.  It is
        never used by the ordinary Files admission, which keeps failing closed.
        """

        actor = self._actor(actor)
        source_admission_errors = dict(source_admission_errors or {})
        self._positive_version(expected_version, "expectedVersion")
        intent = self._load_intent(intent_id)
        if intent.status.value != "open":
            raise ManualPreviewError(
                "cancelled manual intent cannot be Previewed",
                code="intent_not_open",
                next_action="create a new intent from the current File detail",
            )
        if intent.version != expected_version:
            raise ManualPreviewConflict(
                "manual intent version is stale; no Preview was created",
                current_version=intent.version,
            )
        self._check_snapshot(intent, snapshot_id, snapshot_digest)
        if skip_current_snapshot_check:
            # The pinned path proves the revision through the managed authority
            # itself, never through the current Active identity.
            self._load_runtime(intent.snapshot_id, intent.snapshot_digest)
        else:
            self._current_snapshot(snapshot_id, snapshot_digest)
        selected = self._select_items(intent, item_ids)
        versions = self._item_versions(selected, expected_item_versions)

        records: dict[str, object] = {}
        states: dict[str, dict[str, object]] = {}
        for position, item in enumerate(selected):
            self._analysis_checkpoint(analysis_checkpoint, "discovery", position, 0, len(selected))
            self._positive_version(versions[item.item_id], "expectedItemVersion")
            if item.version != versions[item.item_id]:
                raise ManualPreviewConflict(
                    "manual intent item version is stale; no Preview was created",
                    current_version=intent.version,
                    current_item_version=item.version,
                    details={"itemId": item.item_id},
                )
            if item.status is not ManualIntentItemStatus.READY:
                self._invalidate_items(
                    (item.item_id,),
                    "the selected intent item is no longer ready",
                    intent_id=intent.intent_id,
                )
                raise ManualPreviewError(
                    "selected manual intent item is not ready for Preview",
                    code="item_not_ready",
                    next_action="resolve or replace the item, then request a fresh Preview",
                    details={"itemId": item.item_id, "status": item.status.value},
                )
            try:
                runtime = self._load_runtime(intent.snapshot_id, intent.snapshot_digest)
                self._assert_live_source_identity(runtime, item.source)
                record = item.source
                self._validate_choice(intent, item.choice, record)
            except ManualIntentError as error:
                if tolerate_unready_sources:
                    # RO-2: a same-page re-analysis keeps one failed source as
                    # its own bounded finding instead of erasing the correction
                    # and readable state of every other remaining item.  The
                    # per-item outcome below publishes the exact reason and
                    # next action; nothing is admitted and nothing is mutated.
                    source_admission_errors[item.source.source_id] = ManualPreviewError(
                        str(error),
                        code=error.code,
                        status=error.status,
                        next_action=error.next_action,
                        details={"itemId": item.item_id, **error.details},
                    )
                    records[item.item_id] = item.source
                    states[item.item_id] = self._input_state(intent, item, item.source)
                    continue
                if error.code in {"source_stale", "source_missing", "source_invalid"}:
                    self._invalidate_items((item.item_id,), str(error), intent_id=intent.intent_id)
                raise ManualPreviewError(
                    str(error),
                    code=error.code,
                    status=409 if error.code == "source_stale" else error.status,
                    next_action=(
                        "reload the current File detail and request a fresh Preview"
                        if error.code.startswith("source_")
                        else error.next_action
                    ),
                    details={"itemId": item.item_id, **error.details},
                ) from error
            records[item.item_id] = record
            states[item.item_id] = self._input_state(intent, item, record)
            self._analysis_checkpoint(
                analysis_checkpoint, "discovery", position + 1, 0, len(selected)
            )

        preview_id = str(uuid4())
        now = self._clock()
        previous = self._latest_preview(intent.intent_id)
        preview_items: list[ManualPreviewItem] = []
        for position, item in enumerate(selected):
            state = states[item.item_id]
            self._analysis_checkpoint(
                analysis_checkpoint, "analysis", len(selected), position, len(selected)
            )
            try:
                admission_error = source_admission_errors.get(item.source.source_id)
                if admission_error is not None:
                    outcome = self._source_admission_outcome(item, admission_error)
                else:
                    outcome = self._run_item(
                        intent,
                        item,
                        records[item.item_id],
                        preview_id,
                        review_decisions=review_decisions,
                        reuse_analysis_identity=reuse_analysis_identity,
                        require_durable_identity=require_durable_identity,
                        analysis_checkpoint=analysis_checkpoint,
                        visited_entries=len(selected),
                        analysed_items=position,
                        total_items=len(selected),
                        problem_task_id=problem_task_id,
                    )
            except PreviewAnalysisControlRequested:
                raise
            except ManualPreviewUnavailable as error:
                outcome = _PreviewOutcome(
                    ManualPreviewItemStatus.UNAVAILABLE,
                    error=self._safe_error(error),
                    next_action=error.next_action,
                )
            except ManualPreviewError as error:
                outcome = _PreviewOutcome(
                    ManualPreviewItemStatus.BLOCKED,
                    error=self._safe_error(error),
                    next_action=error.next_action,
                )
            except (StrategyConfigurationError, LookupError, StorageError, ValueError) as error:
                outcome = _PreviewOutcome(
                    ManualPreviewItemStatus.FAILED,
                    error=self._safe_error(error),
                    next_action=(
                        "repair the stated analysis or configuration condition, then "
                        "request a fresh Preview"
                    ),
                )
            except (AssertionError, ReadOnlyStorageMutationError):
                raise
            except Exception as error:
                outcome = _PreviewOutcome(
                    ManualPreviewItemStatus.FAILED,
                    error=self._safe_error(error),
                    next_action=(
                        "inspect the bounded analysis failure, repair the dependency, then "
                        "request a fresh Preview"
                    ),
                )
            preview_items.append(
                ManualPreviewItem(
                    str(uuid4()),
                    preview_id,
                    intent.intent_id,
                    item.item_id,
                    item.position,
                    intent.version,
                    item.version,
                    item.source,
                    item.choice,
                    intent.snapshot_id,
                    intent.snapshot_digest,
                    state["sourceFingerprint"],
                    tuple(state["sourceEvidenceVersions"]),
                    tuple(state["reviewVersions"]),
                    tuple(state["conflictVersions"]),
                    state["inputFingerprint"],
                    outcome.plan_fingerprint,
                    outcome.status,
                    outcome.plan,
                    outcome.error,
                    outcome.next_action,
                    True,
                    "not_available_in_this_task",
                    outcome.truncated,
                    now,
                    now,
                    True,
                )
            )
            self._analysis_checkpoint(
                analysis_checkpoint,
                "analysis",
                len(selected),
                position + 1,
                len(selected),
            )

        aggregate_status = self._aggregate_status(preview_items)
        selected_ids = {value.item_id for value in selected}
        preview = ManualOrganizePreview(
            preview_id=preview_id,
            intent_id=intent.intent_id,
            actor=actor,
            intent_version=intent.version,
            configuration_snapshot_id=intent.snapshot_id,
            configuration_snapshot_digest=intent.snapshot_digest,
            status=aggregate_status,
            items=tuple(preview_items),
            created_at=now,
            updated_at=now,
            next_action=self._aggregate_next_action(preview_items),
            previous_preview_id=previous.preview_id if previous is not None else None,
            unselected_item_ids=tuple(
                item.item_id for item in intent.items if item.item_id not in selected_ids
            ),
            truncated=any(item.truncated for item in preview_items),
            source_scope=source_scope,
            source_scope_id=source_scope_id,
            recovery_source_task_id=recovery_source_task_id,
        )
        persisted = self._persist_create(preview) if persist else None
        return persisted or preview

    create_preview = create
    create_manual_preview = create
    preview = create
    preview_intent = create

    def create_current_from_storage(
        self,
        *,
        scope_kind: str,
        actor: str,
        resource_library_id: str | None = None,
        relative_path: str | None = None,
        snapshot_id: str | None = None,
        snapshot_digest: str | None = None,
    ) -> ManualOrganizePreview:
        """Preview UI-V2 Files selections directly from ResourceLibrary Storage.

        The caller supplies only ResourceLibrary identity and a path relative to
        that library root.  This method resolves the Active configuration, maps
        the path to the bound Storage, stats the live file(s), builds immutable
        SourceIdentity/fingerprint evidence, and then uses the existing
        zero-mutation Preview planner.
        """

        actor = self._actor(actor)
        kind = self._current_scope_kind(scope_kind)
        if not self._valid_scope_id(resource_library_id):
            raise ManualPreviewError(
                "Preview requires resourceLibraryId",
                code="malformed_selection",
                next_action="select one enabled ResourceLibrary and retry Preview",
            )
        snapshot = self._current_snapshot(snapshot_id, snapshot_digest)
        runtime = self._load_runtime(snapshot.snapshot_id, snapshot.digest)
        library = self._runtime_library(runtime, resource_library_id)
        storages = self._create_storages(runtime, {library.storage_id})
        storage = self._guarded_storage(storages, library.storage_id)
        if kind == "file":
            rel = self._normalize_library_relative_path(relative_path, allow_empty=False)
            sources = (self._source_identity_from_storage(storage, library, rel),)
            scope_id = rel
        else:
            if relative_path not in (None, ""):
                raise ManualPreviewError(
                    "ResourceLibrary Preview cannot contain a file relativePath",
                    code="malformed_selection",
                    next_action="submit only the ResourceLibrary identity",
                )
            sources = self._enumerate_resource_library_sources(storage, library)
            scope_id = library.library_id
        intent_creator = getattr(self._intent_service, "create_from_sources", None)
        if not callable(intent_creator):
            raise ManualPreviewUnavailable("manual intent service cannot admit Storage sources")
        try:
            intent = intent_creator(
                sources,
                actor=actor,
                snapshot_id=snapshot.snapshot_id,
                snapshot_digest=snapshot.digest,
            )
        except ManualIntentError as error:
            raise ManualPreviewError(
                str(error),
                code=error.code,
                status=error.status,
                next_action=error.next_action,
                details=error.details,
            ) from error
        return self.create(
            intent.intent_id,
            expected_version=intent.version,
            expected_item_versions={item.item_id: item.version for item in intent.items},
            snapshot_id=snapshot.snapshot_id,
            snapshot_digest=snapshot.digest,
            actor=actor,
            source_scope=kind,
            source_scope_id=scope_id,
        )

    create_current_preview = create_current_from_storage
    create_source_preview = create_current_from_storage

    def admit_storage_paths(
        self,
        *,
        resource_library_id: str,
        relative_paths: Sequence[str] | None,
        actor: str,
    ) -> ManualOrganizeIntent:
        """Admit one ordered Files selection as a durable manual intent.

        This is the bounded Files admission of the existing manual Organize
        journey.  The browser supplies only the ResourceLibrary identity and
        normalized ResourceLibrary-relative paths; the pinned Active runtime,
        the bound Storage, every stat, occurrence and fingerprint are resolved
        here, and the resulting immutable ``ManualSourceIdentity`` values are
        admitted through the existing ``create_from_sources`` authority.  It
        creates a durable intent only: no Storage mutation, no Preview and no
        execution authority are produced by this call.
        """

        actor = self._actor(actor)
        if not self._valid_scope_id(resource_library_id):
            raise ManualPreviewError(
                "Files organize admission requires one enabled ResourceLibrary",
                code="malformed_selection",
                next_action="select one enabled ResourceLibrary and retry",
            )
        if not isinstance(relative_paths, (list, tuple)) or not relative_paths:
            raise ManualPreviewError(
                "Files organize admission requires at least one relative path",
                code="selection_empty",
                next_action="select one or more regular files and retry",
            )
        if len(relative_paths) > self._max_items:
            raise ManualPreviewError(
                f"Files organize admission accepts at most {self._max_items} files",
                code="selection_over_limit",
                next_action="select a smaller bounded batch and resubmit",
                details={"limit": self._max_items},
            )
        normalized: list[str] = []
        seen: set[str] = set()
        for value in relative_paths:
            path = self._normalize_library_relative_path(value, allow_empty=False)
            if path in seen:
                raise ManualPreviewError(
                    "the selected files contain a duplicate relative path",
                    code="duplicate_source",
                    next_action="remove the duplicate and resubmit the bounded selection",
                    details={"relativePath": path},
                )
            seen.add(path)
            normalized.append(path)
        snapshot = self._current_snapshot(None, None)
        runtime = self._load_runtime(snapshot.snapshot_id, snapshot.digest)
        library = self._runtime_library(runtime, resource_library_id)
        storages = self._create_storages(runtime, {library.storage_id})
        storage = self._guarded_storage(storages, library.storage_id)
        sources = tuple(
            self._source_identity_from_storage(storage, library, path) for path in normalized
        )
        intent_creator = getattr(self._intent_service, "create_from_sources", None)
        if not callable(intent_creator):
            raise ManualPreviewUnavailable("manual intent service cannot admit Storage sources")
        try:
            return intent_creator(
                sources,
                actor=actor,
                snapshot_id=snapshot.snapshot_id,
                snapshot_digest=snapshot.digest,
            )
        except ManualIntentError as error:
            raise ManualPreviewError(
                str(error),
                code=error.code,
                status=error.status,
                next_action=error.next_action,
                details=error.details,
            ) from error

    admit_files_intent = admit_storage_paths

    def list_current(
        self, scope_kind: str, scope_id: str, *, limit: int = 100
    ) -> tuple[ManualOrganizePreview, ...]:
        kind = self._current_scope_kind(scope_kind)
        if not self._valid_scope_id(scope_id):
            raise ManualPreviewError("source scope ID is required", code="invalid_scope")
        if isinstance(limit, bool) or not 1 <= limit <= self._max_items:
            raise ManualPreviewError(
                f"manual Preview limit must be between 1 and {self._max_items}",
                code="invalid_limit",
            )
        method = getattr(self._repository, "list_manual_previews_by_scope", None)
        if not callable(method):
            return ()
        values = method(kind, scope_id, limit=limit)
        return tuple(self.get_readonly(value.preview_id) for value in values)

    def _runtime_library(self, runtime, resource_library_id: str):
        matches = tuple(
            value
            for value in getattr(runtime, "resource_libraries", ())
            if getattr(value, "library_id", None) == resource_library_id
        )
        if len(matches) != 1 or not getattr(matches[0], "enabled", False):
            raise ManualPreviewError(
                "the selected ResourceLibrary is unavailable in the Active configuration",
                code="resource_library_not_found",
                status=404,
                next_action="refresh Files and choose an enabled ResourceLibrary",
                details={"resourceLibraryId": resource_library_id},
            )
        library = matches[0]
        storage = next(
            (
                item
                for item in getattr(runtime, "storage_definitions", ())
                if getattr(item, "storage_id", None) == library.storage_id
            ),
            None,
        )
        if storage is None or getattr(storage, "enabled", True) is False:
            raise ManualPreviewError(
                "the selected ResourceLibrary Storage is unavailable",
                code="storage_unavailable",
                status=503,
                next_action="repair the ResourceLibrary Storage configuration and retry",
                details={"resourceLibraryId": resource_library_id, "storageId": library.storage_id},
            )
        return library

    def _source_identity_from_storage(
        self, storage: Storage, library, relative_path: str
    ) -> ManualSourceIdentity:
        storage_path = self._join_library_path(library.root_path, relative_path)
        try:
            entry = storage.stat(storage_path)
        except StorageError as error:
            code = getattr(getattr(error, "code", None), "value", "unknown")
            if code == "not_found":
                raise ManualPreviewError(
                    "selected source file no longer exists",
                    code="source_missing",
                    status=404,
                    next_action="refresh Files and request a fresh Preview",
                    details={
                        "resourceLibraryId": library.library_id,
                        "relativePath": relative_path,
                    },
                ) from error
            raise ManualPreviewUnavailable(
                "selected source Storage is unavailable",
                details={"storageId": library.storage_id, "reason": code},
            ) from error
        except (OSError, ValueError, KeyError) as error:
            raise ManualPreviewUnavailable(
                "selected source Storage is unavailable",
                details={"storageId": library.storage_id, "reason": type(error).__name__},
            ) from error
        if isinstance(entry, StorageEntry) and entry.entry_type is StorageEntryType.SYMLINK:
            raise ManualPreviewError(
                "selected source is a symbolic link, which is never organized",
                code="source_symlink",
                status=409,
                next_action="select a regular file inside the ResourceLibrary",
                details={"resourceLibraryId": library.library_id, "relativePath": relative_path},
            )
        if not isinstance(entry, StorageEntry) or entry.entry_type is not StorageEntryType.FILE:
            raise ManualPreviewError(
                "selected source is not a file",
                code="source_not_file",
                status=409,
                next_action="select a file inside the ResourceLibrary",
                details={"resourceLibraryId": library.library_id, "relativePath": relative_path},
            )
        if entry.path != storage_path:
            if not self._path_in_library(entry.path, library.root_path):
                raise ManualPreviewError(
                    "selected source escaped the ResourceLibrary boundary",
                    code="source_cross_authority",
                    status=409,
                    next_action="refresh Files and choose a source inside the ResourceLibrary",
                    details={"resourceLibraryId": library.library_id},
                )
        observed = source_fingerprint(library.storage_id, library.library_id, entry)
        if observed.state is not OccurrenceState.VERIFIED or observed.value is None:
            raise ManualPreviewError(
                "selected source identity could not be verified",
                code="source_unverified",
                status=409,
                next_action="refresh Files and retry after the Storage returns stable stat data",
                details={"resourceLibraryId": library.library_id, "relativePath": relative_path},
            )
        # A directly selected source has only this one observation, so a
        # library that requires a stable-size interval cannot be proven stable
        # here.  Reporting it as ready would fabricate an interval from a first
        # stat; the honest outcome is that the operator waits and re-selects.
        verdict = stability_decision(
            library.stability_policy,
            entry,
            now=self._clock(),
            unchanged_previous=False,
            observed_since=None,
        )
        if verdict is not StabilityVerdict.STABLE:
            raise ManualPreviewError(
                "selected source has not yet been observed unchanged for the configured interval",
                code="source_not_ready",
                status=409,
                next_action=(
                    "wait for the configured stability interval, then refresh the directory and "
                    "select the source again"
                ),
                details={
                    "resourceLibraryId": library.library_id,
                    "relativePath": relative_path,
                    "stability": verdict.value,
                },
            )
        now = self._clock()
        path = entry.path or storage_path
        filename = entry.name or path.rsplit("/", 1)[-1]
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "media"
        occurrence = occurrence_id_for(library.storage_id, library.library_id, path, observed.value)
        return ManualSourceIdentity(
            source_id=occurrence,
            storage_id=library.storage_id,
            resource_library_id=library.library_id,
            path=path,
            filename=filename,
            extension=extension,
            size=entry.size,
            modified_at=entry.modified_at,
            observed_at=now,
            stable_since=None,
            occurrence_id=occurrence,
            fingerprint=observed.value,
            fingerprint_algorithm=observed.algorithm,
            fingerprint_evidence=observed.evidence,
            occurrence_state=OccurrenceState.VERIFIED.value,
        )

    def _enumerate_resource_library_sources(
        self, storage: Storage, library
    ) -> tuple[ManualSourceIdentity, ...]:
        pending = [""]
        sources: list[ManualSourceIdentity] = []
        while pending:
            rel_dir = pending.pop(0)
            storage_dir = self._join_library_path(library.root_path, rel_dir)
            cursor = None
            while True:
                page = storage.list_page(
                    storage_dir, limit=min(100, self._max_items), cursor=cursor
                )
                entries = tuple(getattr(page, "entries", ()))
                for entry in entries:
                    if not isinstance(entry, StorageEntry):
                        continue
                    rel_path = self._strip_library_path(entry.path, library.root_path)
                    if entry.entry_type is StorageEntryType.DIRECTORY:
                        pending.append(rel_path)
                    elif entry.entry_type is StorageEntryType.FILE:
                        sources.append(
                            self._source_identity_from_storage(storage, library, rel_path)
                        )
                        if len(sources) > self._max_items:
                            raise ManualPreviewError(
                                f"ResourceLibrary Preview selection exceeds the bound of "
                                f"{self._max_items}",
                                code="selection_over_limit",
                                next_action="select a smaller batch from Files",
                                details={"resourceLibraryId": library.library_id},
                            )
                cursor = getattr(page, "next_cursor", None)
                if not cursor:
                    break
        if not sources:
            raise ManualPreviewError(
                "ResourceLibrary has no selectable files",
                code="selection_empty",
                next_action="choose a ResourceLibrary containing visible files",
                details={"resourceLibraryId": library.library_id},
            )
        return tuple(sources)

    @staticmethod
    def _normalize_library_relative_path(value: object, *, allow_empty: bool) -> str:
        if value == "" and allow_empty:
            return ""
        if not isinstance(value, str) or not value or "\x00" in value:
            raise ManualPreviewError(
                "relativePath must be a safe ResourceLibrary-relative path",
                code="invalid_path",
                next_action="select a file inside the ResourceLibrary",
            )
        if value.startswith(("/", "\\")) or "\\" in value or ":" in value:
            raise ManualPreviewError(
                "relativePath must be a safe ResourceLibrary-relative path",
                code="invalid_path",
                next_action="select a file inside the ResourceLibrary",
            )
        parts = value.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ManualPreviewError(
                "relativePath must not escape the ResourceLibrary",
                code="invalid_path",
                next_action="select a file inside the ResourceLibrary",
            )
        return "/".join(parts)

    @classmethod
    def _join_library_path(cls, root: str, relative_path: str) -> str:
        root = cls._normalize_library_relative_path(root, allow_empty=True) if root else ""
        relative_path = (
            cls._normalize_library_relative_path(relative_path, allow_empty=True)
            if relative_path
            else ""
        )
        if not root:
            return relative_path
        return f"{root}/{relative_path}" if relative_path else root

    @classmethod
    def _strip_library_path(cls, path: str, root: str) -> str:
        path = cls._normalize_library_relative_path(path, allow_empty=True) if path else ""
        root = cls._normalize_library_relative_path(root, allow_empty=True) if root else ""
        if not root:
            return path
        if path == root:
            return ""
        if path.startswith(root + "/"):
            return path[len(root) + 1 :]
        raise ManualPreviewError(
            "Storage returned a path outside the ResourceLibrary boundary",
            code="source_cross_authority",
            status=409,
            next_action="repair Storage path normalization and retry",
        )

    @classmethod
    def _path_in_library(cls, path: str, root: str) -> bool:
        try:
            cls._strip_library_path(path, root)
            return True
        except ManualPreviewError:
            return False

    @staticmethod
    def _current_scope_kind(value: str) -> str:
        if not isinstance(value, str):
            raise ManualPreviewError(
                "Preview scope must be file or resource_library",
                code="invalid_scope",
                next_action="choose one configured ResourceLibrary or one live directory",
            )
        value = value.strip()
        if value == "resourceLibrary":
            value = "resource_library"
        if value not in {"file", "resource_library"}:
            raise ManualPreviewError(
                "Preview scope must be file or resource_library",
                code="invalid_scope",
                next_action="choose one configured ResourceLibrary or one live directory",
            )
        return value

    @staticmethod
    def _valid_occurrence_id(value: object) -> bool:
        return isinstance(value, str) and bool(_SAFE_ID.fullmatch(value))

    @staticmethod
    def _valid_scope_id(value: object) -> bool:
        return isinstance(value, str) and bool(_SAFE_ID.fullmatch(value))

    @staticmethod
    def _valid_fingerprint(value: object) -> bool:
        return isinstance(value, str) and bool(_SHA256.fullmatch(value))

    def _current_snapshot(self, snapshot_id: str | None, snapshot_digest: str | None):
        if (snapshot_id is None) != (snapshot_digest is None):
            raise ManualPreviewError(
                "configuration snapshot ID and digest must be supplied together",
                code="malformed_snapshot",
                next_action="reload the current Active snapshot and retry Preview",
            )
        resolver = getattr(self._intent_service, "_active_snapshot", None)
        if not callable(resolver):
            raise ManualPreviewUnavailable(
                "the Active configuration snapshot authority is unavailable"
            )
        try:
            current = resolver()
        except ManualIntentError as error:
            raise ManualPreviewUnavailable(
                "the Active configuration snapshot is unavailable",
                details={"reason": type(error).__name__},
            ) from error
        except Exception as error:
            raise ManualPreviewUnavailable(
                "the Active configuration snapshot is unavailable",
                details={"reason": type(error).__name__},
            ) from error
        current_id = getattr(current, "snapshot_id", None)
        current_digest = getattr(current, "digest", None)
        if (
            not isinstance(current_id, str)
            or not current_id.strip()
            or not isinstance(current_digest, str)
            or not current_digest.strip()
        ):
            raise ManualPreviewUnavailable("the Active configuration snapshot identity is invalid")
        if snapshot_id is not None and (
            snapshot_id != current_id or snapshot_digest != current_digest
        ):
            raise ManualPreviewConflict(
                "the requested Preview snapshot is not the current Active snapshot",
                details={
                    "currentSnapshotId": current_id,
                    "currentSnapshotDigest": current_digest,
                },
            )
        return current

    def _assert_live_source_identity(self, runtime, source: ManualSourceIdentity) -> None:
        try:
            storages = self._create_storages(runtime, {source.storage_id})
            storage = self._guarded_storage(storages, source.storage_id)
            entry = storage.stat(source.path)
        except StorageError as error:
            code = getattr(getattr(error, "code", None), "value", "unknown")
            if code == "not_found":
                raise ManualIntentError(
                    "selected source is no longer present in Storage",
                    code="source_missing",
                    status=404,
                    next_action="refresh Files and request a fresh Preview",
                    details={"resourceLibraryId": source.resource_library_id, "path": source.path},
                ) from error
            raise ManualIntentUnavailable(
                "the selected source Storage is unavailable for read-only Preview",
                details={"storageId": source.storage_id, "reason": code},
            ) from error
        except (OSError, ValueError, KeyError) as error:
            raise ManualIntentUnavailable(
                "the selected source Storage is unavailable for read-only Preview",
                details={"storageId": source.storage_id, "reason": type(error).__name__},
            ) from error
        if not isinstance(entry, StorageEntry) or entry.entry_type is not StorageEntryType.FILE:
            raise ManualIntentError(
                "selected source is no longer a file in Storage",
                code="source_stale",
                next_action="refresh Files and request a fresh Preview",
                details={"resourceLibraryId": source.resource_library_id, "path": source.path},
            )
        observed = source_fingerprint(source.storage_id, source.resource_library_id, entry)
        observed_occurrence = occurrence_id_for(
            source.storage_id, source.resource_library_id, entry.path, observed.value
        )
        if (
            entry.path != source.path
            or observed.state is not OccurrenceState.VERIFIED
            or observed.value != source.fingerprint
            or observed_occurrence != source.occurrence_id
        ):
            raise ManualIntentError(
                "selected source changed after Files selection",
                code="source_stale",
                next_action="refresh Files and request a fresh Preview",
                details={"resourceLibraryId": source.resource_library_id, "path": source.path},
            )

    def get(self, preview_id: str) -> ManualOrganizePreview:
        if not isinstance(preview_id, str) or not preview_id.strip():
            raise ManualPreviewError("Preview ID is required", code="invalid_preview_id")
        value = self._repository.get_manual_preview(preview_id)
        if value is None:
            raise ManualPreviewError(
                f"manual Preview {preview_id!r} was not found",
                code="preview_not_found",
                status=404,
                next_action="open the manual intent and explicitly request a fresh Preview",
            )
        if not value.current:
            return value
        stale_ids = self._stale_current_items(value)
        if stale_ids:
            reason = (
                "plan-affecting source, evidence, review, conflict, choice, or "
                "snapshot input changed"
            )
            # Current-source Previews are the immutable analysis evidence for the
            # Files journey.  A read may project stale evidence, but it
            # must not publish a lifecycle mutation merely because the operator
            # opened the detail page.  Keep the legacy intent-scoped behavior
            # below for compatibility with the existing manual-organize loop.
            if value.source_scope is not None:
                return self._stale_projection(value, stale_ids, reason)
            self._invalidate_items(stale_ids, reason, intent_id=value.intent_id)
            refreshed = self._repository.get_manual_preview(preview_id)
            if refreshed is not None:
                return refreshed
            return self._stale_projection(value, stale_ids, reason)
        return value

    def get_readonly(self, preview_id: str) -> ManualOrganizePreview:
        """Read the current Preview without publishing read-time staleness."""

        if not isinstance(preview_id, str) or not preview_id.strip():
            raise ManualPreviewError("Preview ID is required", code="invalid_preview_id")
        value = self._repository.get_manual_preview(preview_id)
        if value is None:
            raise ManualPreviewError(
                f"manual Preview {preview_id!r} was not found",
                code="preview_not_found",
                status=404,
                next_action="open the manual intent and explicitly request a fresh Preview",
            )
        if not value.current:
            return value
        stale_ids = self._stale_current_items(value)
        if not stale_ids:
            return value
        return self._stale_projection(
            value,
            stale_ids,
            "plan-affecting source, evidence, review, conflict, choice, or snapshot input changed",
        )

    get_preview_readonly = get_readonly

    get_preview = get
    get_manual_preview = get

    def latest(self, intent_id: str) -> ManualOrganizePreview:
        value = self._latest_preview(intent_id)
        if value is None:
            raise ManualPreviewError(
                f"manual intent {intent_id!r} has no Preview",
                code="preview_not_found",
                status=404,
                next_action="open the intent and explicitly request a Preview",
            )
        return self.get(value.preview_id)

    def latest_readonly(self, intent_id: str) -> ManualOrganizePreview:
        value = self._latest_preview(intent_id)
        if value is None:
            raise ManualPreviewError(
                f"manual intent {intent_id!r} has no Preview",
                code="preview_not_found",
                status=404,
                next_action="open the intent and explicitly request a Preview",
            )
        return self.get_readonly(value.preview_id)

    current = latest
    get_latest = latest

    def list(self, intent_id: str, *, limit: int = 100) -> tuple[ManualOrganizePreview, ...]:
        if isinstance(limit, bool) or not 1 <= limit <= self._max_items:
            raise ManualPreviewError(
                f"manual Preview limit must be between 1 and {self._max_items}",
                code="invalid_limit",
            )
        method = getattr(self._repository, "list_manual_previews", None)
        if not callable(method):
            return ()
        values = method(intent_id, limit=limit)
        return tuple(self.get(value.preview_id) for value in values)

    def list_readonly(
        self, intent_id: str, *, limit: int = 100
    ) -> tuple[ManualOrganizePreview, ...]:
        if isinstance(limit, bool) or not 1 <= limit <= self._max_items:
            raise ManualPreviewError(
                f"manual Preview limit must be between 1 and {self._max_items}",
                code="invalid_limit",
            )
        method = getattr(self._repository, "list_manual_previews", None)
        if not callable(method):
            return ()
        values = method(intent_id, limit=limit)
        return tuple(self.get_readonly(value.preview_id) for value in values)

    list_previews = list
    list_manual_previews = list

    def invalidate(
        self,
        intent_id: str,
        item_ids: Sequence[str] | None = None,
        *,
        reason: str = "a plan-affecting input changed",
    ) -> None:
        intent = self._load_intent(intent_id)
        selected = self._select_items(intent, item_ids)
        self._invalidate_items(
            tuple(item.item_id for item in selected), reason, intent_id=intent_id
        )

    invalidate_previews = invalidate

    def load_intent_for_admission(self, intent_id: str) -> ManualOrganizeIntent:
        """Read one intent for durable-analysis admission.

        This is the same bounded loader the synchronous Preview uses, exposed so
        the durable-analysis admission can resolve and persist the exact pinned
        intent context *before* any expensive walk or Provider call runs.
        """

        return self._load_intent(intent_id)

    def _load_intent(self, intent_id: str) -> ManualOrganizeIntent:
        try:
            return self._intent_service.get(intent_id)
        except ManualIntentError:
            raise
        except (LookupError, ValueError) as error:
            raise ManualPreviewError(str(error), code="intent_not_found", status=404) from error

    @staticmethod
    def _actor(actor: str) -> str:
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 200:
            raise ManualPreviewError("Preview actor is invalid", code="invalid_actor")
        return actor.strip()

    @staticmethod
    def _positive_version(value: int | None, name: str) -> None:
        if value is None or isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ManualPreviewError(f"{name} must be a positive integer", code="malformed_version")

    @staticmethod
    def _check_snapshot(
        intent: ManualOrganizeIntent, snapshot_id: str | None, digest: str | None
    ) -> None:
        if snapshot_id is not None and snapshot_id != intent.snapshot_id:
            raise ManualPreviewConflict(
                "Preview belongs to a different pinned configuration snapshot",
                details={"expectedSnapshotId": intent.snapshot_id},
            )
        if digest is not None and digest != intent.snapshot_digest:
            raise ManualPreviewConflict(
                "Preview digest does not match the pinned configuration snapshot",
                details={"expectedSnapshotDigest": intent.snapshot_digest},
            )

    def _select_items(
        self, intent: ManualOrganizeIntent, item_ids: Sequence[str] | None
    ) -> tuple[object, ...]:
        if item_ids is None:
            values = tuple(item.item_id for item in intent.items)
        else:
            if isinstance(item_ids, (str, bytes)):
                raise ManualPreviewError(
                    "itemIds must be a bounded array", code="malformed_selection"
                )
            try:
                values = tuple(item_ids)
            except TypeError as error:
                raise ManualPreviewError(
                    "itemIds must be a bounded array", code="malformed_selection"
                ) from error
        if not 1 <= len(values) <= self._max_items:
            raise ManualPreviewError(
                f"Preview selection must contain between 1 and {self._max_items} items",
                code="preview_over_limit" if values else "selection_empty",
            )
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ManualPreviewError(
                "itemIds must contain non-empty strings", code="malformed_selection"
            )
        if len(set(values)) != len(values):
            raise ManualPreviewError(
                "itemIds must not contain duplicates", code="duplicate_selection"
            )
        by_id = {item.item_id: item for item in intent.items}
        missing = [value for value in values if value not in by_id]
        if missing:
            raise ManualPreviewError(
                f"manual intent item {missing[0]!r} was not found",
                code="item_not_found",
                status=404,
                next_action="reload the current intent and select one of its listed items",
            )
        return tuple(sorted((by_id[value] for value in values), key=lambda item: item.position))

    @staticmethod
    def _item_versions(
        items: Sequence, supplied: Mapping[str, int] | Sequence[int] | None
    ) -> dict[str, int]:
        if supplied is None:
            return {item.item_id: item.version for item in items}
        if isinstance(supplied, Mapping):
            if set(supplied) != {item.item_id for item in items}:
                raise ManualPreviewError(
                    "expectedItemVersions must cover exactly the selected items",
                    code="malformed_version",
                )
            values = dict(supplied)
        else:
            if isinstance(supplied, (str, bytes)):
                raise ManualPreviewError(
                    "expectedItemVersions must be an object", code="malformed_version"
                )
            try:
                sequence = tuple(supplied)
            except TypeError as error:
                raise ManualPreviewError(
                    "expectedItemVersions must be an object", code="malformed_version"
                ) from error
            if len(sequence) != len(items):
                raise ManualPreviewError(
                    "expectedItemVersions must cover exactly the selected items",
                    code="malformed_version",
                )
            values = {item.item_id: sequence[index] for index, item in enumerate(items)}
        for item_id, value in values.items():
            ManualOrganizePreviewService._positive_version(
                value, f"expectedItemVersions[{item_id}]"
            )
        return values

    def _source_admission_outcome(self, item, error: ManualPreviewError) -> _PreviewOutcome:
        stale_codes = {"source_missing", "source_stale", "source_not_ready", "source_unverified"}
        status = (
            ManualPreviewItemStatus.STALE
            if error.code in stale_codes
            else ManualPreviewItemStatus.UNAVAILABLE
            if error.status >= 500
            else ManualPreviewItemStatus.BLOCKED
        )
        plan = self._source_failure_plan(item, error)
        return _PreviewOutcome(
            status,
            plan=plan,
            plan_fingerprint=_fingerprint(plan),
            error=self._safe_error(error),
            next_action=error.next_action,
        )

    @staticmethod
    def _source_failure_plan(item, error: ManualPreviewError) -> dict[str, object]:
        return {
            "source": item.source.document(),
            "recognitionType": item.choice.recognition_type_id,
            "policies": {
                "recognitionTypePolicyId": item.choice.recognition_type_id,
                "metadataPolicyId": None,
                "namingPolicyId": item.choice.naming_policy_id,
                "classificationPolicyId": item.choice.classification_policy_id,
                "organizePolicyId": item.choice.organize_policy_id,
            },
            "analysis": {
                "stage": "source_admission",
                "status": "unavailable" if error.status >= 500 else "blocked",
                "error": safe_manual_error(error, "current source admission failed"),
            },
            "destination": None,
            "operation": None,
            "attachments": [],
            "executionPlan": None,
            "capabilities": {
                "verdict": "not_determined",
                "required": [],
                "declared": [],
                "missing": [],
            },
            "conflicts": [],
            "warnings": [],
            "planStatus": "invalid",
            "zeroMutation": True,
            "executionState": "not_available_in_this_task",
            "bounded": True,
            "deterministic": True,
        }

    def _validate_choice(self, intent, choice: ManualChoice, record) -> None:
        validator = getattr(self._intent_service, "_validate_choice", None)
        if callable(validator):
            validator(choice, intent.options, record)
            return
        if choice.recognition_type_id not in intent.options.option_maps()["recognitionType"]:
            raise ManualIntentError(
                "manual RecognitionType is not configured", code="choice_disabled"
            )

    def _input_state(self, intent, item, record) -> dict[str, object]:
        source = (
            record
            if isinstance(record, ManualSourceIdentity)
            else ManualSourceIdentity.from_file_record(record)
        )
        source_evidence = self._source_evidence_versions(source)
        reviews = self._review_versions(source)
        conflicts = self._conflict_versions(source)
        payload = {
            "source": source.document(),
            "choice": item.choice.document(),
            "intentVersion": intent.version,
            "itemVersion": item.version,
            "configurationSnapshotId": intent.snapshot_id,
            "configurationSnapshotDigest": intent.snapshot_digest,
            "sourceEvidenceVersions": source_evidence,
            "reviewVersions": reviews,
            "conflictVersions": conflicts,
        }
        return {
            "source": source,
            "sourceFingerprint": source.fingerprint or _fingerprint(source.document()),
            "sourceEvidenceVersions": source_evidence,
            "reviewVersions": reviews,
            "conflictVersions": conflicts,
            "inputFingerprint": _fingerprint(payload),
        }

    def _source_evidence_versions(
        self, source: ManualSourceIdentity
    ) -> tuple[dict[str, object], ...]:
        values: list[dict[str, object]] = []
        if source.occurrence_id is not None and source.fingerprint is not None:
            values.append(
                {
                    "kind": "source_occurrence",
                    "occurrenceId": source.occurrence_id,
                    "fingerprint": source.fingerprint,
                    "algorithm": source.fingerprint_algorithm,
                    "state": source.occurrence_state,
                    "evidence": source.fingerprint_evidence or {},
                }
            )
        method = getattr(self._repository, "list_evidence_for_source", None)
        if callable(method):
            try:
                evidence = tuple(method(source.storage_id, source.path, limit=100))
            except Exception as error:
                return ({"kind": "evidence", "available": False, "reason": type(error).__name__},)
            for value in evidence[:MAX_MANUAL_PREVIEW_ITEMS]:
                values.append(
                    {
                        "kind": "pipeline_evidence",
                        "id": _bounded(getattr(value, "evidence_id", None)),
                        "capturedAt": _iso(getattr(value, "captured_at", None)),
                        "outcome": _bounded(getattr(value, "outcome", None)),
                        "configurationSnapshotId": _bounded(
                            getattr(value, "configuration_snapshot_id", None)
                        ),
                        "configurationSnapshotDigest": _bounded(
                            getattr(value, "configuration_snapshot_digest", None)
                        ),
                        "digest": _fingerprint(_safe_document(value)),
                    }
                )
        result_method = getattr(self._repository, "list_results_for_source", None)
        if callable(result_method):
            try:
                results = tuple(result_method(source.storage_id, source.path, limit=100))
            except Exception as error:
                values.append(
                    {"kind": "result", "available": False, "reason": type(error).__name__}
                )
            else:
                values.extend(
                    {
                        "kind": "result",
                        "id": _bounded(getattr(value, "result_id", None)),
                        "createdAt": _iso(getattr(value, "created_at", None)),
                        "status": _bounded(getattr(value, "status", None)),
                        "digest": _fingerprint(_safe_document(value)),
                    }
                    for value in results[:MAX_MANUAL_PREVIEW_ITEMS]
                )
        return tuple(
            sorted(
                values,
                key=lambda value: (
                    str(value.get("kind")),
                    str(value.get("id")),
                    str(value.get("digest")),
                ),
            )
        )

    def _review_versions(self, source: ManualSourceIdentity) -> tuple[dict[str, object], ...]:
        method = getattr(self._repository, "list_file_review_links", None)
        if not callable(method):
            return ()
        try:
            links = tuple(method(source.storage_id, source.path, limit=100))
        except Exception as error:
            return ({"available": False, "reason": type(error).__name__},)
        values = [
            {
                "kind": _bounded(getattr(value, "kind", None)),
                "reviewId": _bounded(getattr(value, "review_id", None)),
                "status": _bounded(getattr(value, "status", None)),
                "taskId": _bounded(getattr(value, "task_id", None)),
                "itemId": _bounded(getattr(value, "item_id", None)),
            }
            for value in links[:MAX_MANUAL_PREVIEW_ITEMS]
        ]
        return tuple(
            sorted(
                values,
                key=lambda value: (str(value.get("kind")), str(value.get("reviewId"))),
            )
        )

    def _conflict_versions(self, source: ManualSourceIdentity) -> tuple[dict[str, object], ...]:
        method = getattr(self._repository, "list_confirmations", None)
        if not callable(method):
            return ()
        try:
            values = tuple(method(limit=1000))
        except Exception as error:
            return ({"available": False, "reason": type(error).__name__},)
        result = []
        for value in values:
            if (
                getattr(value, "source_storage_id", None) != source.storage_id
                or getattr(value, "source_path", None) != source.path
            ):
                continue
            result.append(
                {
                    "kind": "conflict",
                    "confirmationId": _bounded(getattr(value, "confirmation_id", None)),
                    "status": _bounded(getattr(value, "status", None)),
                    "configuredStrategy": _bounded(getattr(value, "configured_strategy", None)),
                    "selectedStrategy": _bounded(getattr(value, "selected_strategy", None)),
                    "proposedDestinationPath": _bounded(
                        getattr(value, "proposed_destination_path", None)
                    ),
                    "updatedAt": _iso(getattr(value, "updated_at", None)),
                    "overwriteAuthorized": bool(getattr(value, "overwrite_authorized", False)),
                }
            )
            if len(result) >= MAX_MANUAL_PREVIEW_ITEMS:
                break
        return tuple(sorted(result, key=lambda value: str(value.get("confirmationId"))))

    def _run_item(
        self,
        intent,
        item,
        record,
        preview_id: str,
        *,
        review_decisions: object | None = None,
        reuse_analysis_identity: object | None = None,
        require_durable_identity: bool = False,
        analysis_checkpoint: Callable[[str, int, int, int], None] | None = None,
        visited_entries: int = 0,
        analysed_items: int = 0,
        total_items: int = 0,
        problem_task_id: str | None = None,
    ) -> _PreviewOutcome:
        runtime = self._load_runtime(intent.snapshot_id, intent.snapshot_digest)
        if not item.choice.decided:
            # RO-2/AC-16: the pinned RecognitionRule did not determine a type for this
            # source, so the item stays a genuine native Recognition problem.  The
            # analysis runs the ordinary rule engine over this exact source — it does
            # not force, default or invent a type — and publishes the operator's
            # decision as the item's own review.  Nothing is planned, targeted or
            # mutated before that decision, and a rule that resolves later changes the
            # problem type instead of silently rewriting the item.
            return self._recognition_problem_outcome(
                item,
                runtime,
                problem_task_id=problem_task_id,
            )
        type_policy = next(
            (
                value
                for value in runtime.strategy.recognition_type_policies
                if value.recognition_type_id == item.choice.recognition_type_id
            ),
            None,
        )
        if type_policy is None or not type_policy.enabled:
            return _PreviewOutcome(
                ManualPreviewItemStatus.BLOCKED,
                error="the pinned RecognitionType policy is unavailable",
                next_action=(
                    "reload the intent under a valid Active snapshot, then request a fresh Preview"
                ),
            )
        source_library = next(
            (
                value
                for value in runtime.resource_libraries
                if value.library_id == item.source.resource_library_id
                and value.storage_id == item.source.storage_id
                and value.enabled
            ),
            None,
        )
        if source_library is None:
            return _PreviewOutcome(
                ManualPreviewItemStatus.UNAVAILABLE,
                error="the pinned ResourceLibrary authority is unavailable",
                next_action=(
                    "repair the pinned ResourceLibrary/Storage configuration, then rerun Preview"
                ),
            )
        metadata_policy = next(
            (
                value
                for value in runtime.strategy.metadata_policies
                if value.policy_id == type_policy.metadata_policy_id
            ),
            None,
        )
        if metadata_policy is None or not metadata_policy.enabled:
            return _PreviewOutcome(
                ManualPreviewItemStatus.BLOCKED,
                error="the pinned MetadataPolicy is unavailable",
                next_action=(
                    "choose an enabled MetadataPolicy under the pinned snapshot, then rerun Preview"
                ),
            )
        needed_storage_ids = {item.source.storage_id}
        # The target Storage is determined only by the configured Classification result;
        # constructing the source adapter first keeps arbitrary API paths out of scope.
        configured_storages = self._create_storages(runtime, needed_storage_ids)
        source_storage = self._guarded_storage(configured_storages, item.source.storage_id)
        bound = self._bound_source_decisions(review_decisions, item)
        metadata_reference = self._metadata_reference(item.choice, intent, record, metadata_policy)
        metadata_selection = None
        metadata_identity = None
        metadata_correction = None
        durable_identity = None
        if metadata_reference is not None and metadata_policy.query_type is MediaQueryType.NONE:
            # An offline MetadataPolicy performs no lookup by definition, so a bounded
            # identity that the source-linked authority already grounded is pinned
            # directly instead of being re-resolved through a live Provider.  The
            # reference reached this point only through the Choice/intent source
            # authority check above, and `run_path` re-validates that the pinned
            # identity still matches this exact RecognitionType and MetadataPolicy.
            metadata_identity = MediaIdentity(
                provider=metadata_reference.provider,
                provider_id=metadata_reference.provider_id,
                media_type=MediaType(metadata_reference.media_type),
                title=metadata_reference.title or item.source.filename,
                year=metadata_reference.year,
                recognition_type_id=item.choice.recognition_type_id,
            )
        elif metadata_reference is not None:
            metadata_selection = self._metadata_selection(
                item.choice.recognition_type_id,
                type_policy.metadata_policy_id,
                metadata_reference,
            )
        else:
            metadata_selection, metadata_correction = self._bound_metadata_decision(
                bound, item, type_policy, metadata_policy
            )
        # Reuse the exact identity an already completed, source/pin-bound
        # re-analysis resolved under this same MetadataPolicy.  This is a durable
        # reviewed fact, not a fresh lookup: the summary is built without a second
        # Provider search/detail round-trip.  The identity is re-validated against
        # the pinned policy before it is applied, and when the operator also saved
        # an explicit Metadata decision/reference that decision must still agree
        # with the durable identity; otherwise the item is blocked for a fresh
        # analysis instead of silently overriding either fact.
        if (
            metadata_identity is None
            and metadata_policy.query_type is not MediaQueryType.NONE
            and reuse_analysis_identity is not None
            and self._durable_identity_compatible(metadata_policy, item, reuse_analysis_identity)
        ):
            candidate_durable = self._rebind_durable_identity(
                reuse_analysis_identity, item.choice.recognition_type_id
            )
            mismatch = self._metadata_decision_mismatch(
                candidate_durable, metadata_selection, metadata_correction, metadata_reference
            )
            if mismatch is not None:
                return _PreviewOutcome(
                    ManualPreviewItemStatus.BLOCKED,
                    error=mismatch,
                    next_action=(
                        "request a fresh analysis for this exact item so the saved Metadata "
                        "decision and the resolved identity agree before continuing"
                    ),
                )
            durable_identity = candidate_durable
            metadata_selection = None
            metadata_correction = None
        if (
            require_durable_identity
            and durable_identity is None
            and metadata_identity is None
            and metadata_policy.query_type is not MediaQueryType.NONE
        ):
            # The same-page summary never falls back to a live Provider lookup
            # inside the HTTP request: a missing, incomplete or expired durable
            # identity becomes an explicit re-analysis action handled by the
            # existing durable Job/Worker.
            return _PreviewOutcome(
                ManualPreviewItemStatus.BLOCKED,
                error=(
                    "the completed re-analysis has no reusable metadata identity under the "
                    "pinned MetadataPolicy"
                ),
                next_action=(
                    "request a fresh analysis for this exact item, wait for the Worker, then "
                    "generate the plan summary again"
                ),
            )
        live_metadata = metadata_policy.query_type is not MediaQueryType.NONE
        if metadata_identity is not None or durable_identity is not None:
            live_metadata = False
        if (
            metadata_identity is None
            and durable_identity is None
            and (metadata_selection is not None or metadata_correction is not None)
        ):
            live_metadata = True
        providers = (
            self._provider_registry((metadata_policy.provider_id,)) if live_metadata else None
        )
        runner = self._runner(runtime, providers, source_storage, configured_storages)
        classification_selection = self._bound_classification_decision(bound, item, type_policy)
        # The pinned policy objects this analysis is actually running under.  They
        # are passed to the problem publisher so a native review is built from the
        # exact same authority, never from a re-resolved or defaulted policy.
        classification_policy = next(
            (
                value
                for value in runtime.strategy.classification_policies
                if value.policy_id == type_policy.classification_policy_id
            ),
            None,
        )
        self._analysis_checkpoint(
            analysis_checkpoint, "provider", visited_entries, analysed_items, total_items
        )
        strategy = runner.run_path(
            item.source.path,
            live_metadata=live_metadata,
            show_naming=True,
            show_classification=True,
            resource_library_id=source_library.library_id,
            storage_id=source_library.storage_id,
            metadata_selection=metadata_selection,
            metadata_correction=metadata_correction,
            metadata_identity=metadata_identity,
            durable_identity=durable_identity,
            classification_selection=classification_selection,
            forced_recognition_type_id=item.choice.recognition_type_id,
            storage_path=item.source.path,
            source_storage=source_storage,
        )
        self._analysis_checkpoint(
            analysis_checkpoint, "provider", visited_entries, analysed_items, total_items
        )
        if strategy.recognition.status is not RecognitionStatus.MATCHED:
            outcome = _PreviewOutcome(
                ManualPreviewItemStatus.BLOCKED,
                plan=self._partial_plan(strategy, item, type_policy),
                error="RecognitionType could not be resolved under the pinned choice",
                next_action=(
                    "open the linked Recognition review or choose a valid RecognitionType, "
                    "then rerun Preview"
                ),
                # RO-2/AC-16: a source whose RecognitionType really could not be
                # resolved under its own pinned policy is one of the four native
                # organizing problems, never a silent preparation dead end.  A
                # provider/technical condition keeps its own technical outcome.
                problem="recognition",
            )
            return self._publish_problem(
                problem_task_id,
                outcome,
                strategy=strategy,
                source=item.source,
                type_policy=type_policy,
                metadata_policy=metadata_policy,
                classification_policy=classification_policy,
                recognition_types=tuple(
                    value.recognition_type
                    for value in runtime.strategy.recognition_type_policies
                    if getattr(value, "enabled", False)
                ),
            )
        metadata = strategy.metadata
        if metadata is None or metadata.identity is None:
            status = getattr(metadata, "status", None)
            if status in {
                MetadataIdentificationStatus.PROVIDER_ERROR,
            }:
                return _PreviewOutcome(
                    ManualPreviewItemStatus.UNAVAILABLE,
                    plan=self._partial_plan(strategy, item, type_policy),
                    error=self._safe_error(
                        getattr(metadata, "error", None) or "metadata provider unavailable"
                    ),
                    next_action=(
                        "inspect the configured Metadata Provider, then explicitly rerun Preview"
                    ),
                )
            if status in {
                MetadataIdentificationStatus.NEED_CONFIRM,
                MetadataIdentificationStatus.AMBIGUOUS,
            }:
                outcome = _PreviewOutcome(
                    ManualPreviewItemStatus.BLOCKED,
                    plan=self._partial_plan(strategy, item, type_policy),
                    error="metadata identity needs an explicit candidate selection",
                    next_action=(
                        "choose one of this source's grounded metadata candidates on this page, "
                        "then rerun the analysis"
                    ),
                    problem="metadata",
                )
                return self._publish_problem(
                    problem_task_id,
                    outcome,
                    strategy=strategy,
                    source=item.source,
                    type_policy=type_policy,
                    metadata_policy=metadata_policy,
                    classification_policy=classification_policy,
                    recognition_types=tuple(
                        value.recognition_type
                        for value in runtime.strategy.recognition_type_policies
                        if getattr(value, "enabled", False)
                    ),
                )
            if status is MetadataIdentificationStatus.NOT_FOUND:
                outcome = _PreviewOutcome(
                    ManualPreviewItemStatus.BLOCKED,
                    plan=self._partial_plan(strategy, item, type_policy),
                    error="metadata identity was not found under the pinned MetadataPolicy",
                    next_action=(
                        "correct the metadata search title/year or choose a Provider identity "
                        "for this source, then rerun the analysis"
                    ),
                    problem="metadata_correction",
                )
                return self._publish_problem(
                    problem_task_id,
                    outcome,
                    strategy=strategy,
                    source=item.source,
                    type_policy=type_policy,
                    metadata_policy=metadata_policy,
                    classification_policy=classification_policy,
                    recognition_types=tuple(
                        value.recognition_type
                        for value in runtime.strategy.recognition_type_policies
                        if getattr(value, "enabled", False)
                    ),
                )
            return _PreviewOutcome(
                ManualPreviewItemStatus.BLOCKED,
                plan=self._partial_plan(strategy, item, type_policy),
                error="metadata identity needs an explicit candidate selection",
                next_action=(
                    "choose one of this source's grounded metadata candidates on this page, "
                    "then rerun the analysis"
                ),
            )
        if strategy.naming is None:
            return _PreviewOutcome(
                ManualPreviewItemStatus.BLOCKED,
                plan=self._partial_plan(strategy, item, type_policy),
                error=strategy.naming_error or "NamingPolicy did not produce a result",
                next_action="repair the pinned NamingPolicy or metadata choice, then rerun Preview",
            )
        if (
            strategy.classification is None
            or strategy.classification.status is not ClassificationStatus.CLASSIFIED
        ):
            if (
                strategy.classification is not None
                and strategy.classification.status is ClassificationStatus.UNCLASSIFIED
            ):
                outcome = _PreviewOutcome(
                    ManualPreviewItemStatus.BLOCKED,
                    plan=self._partial_plan(strategy, item, type_policy),
                    error=strategy.classification_error
                    or "ClassificationPolicy did not select a MediaLibrary",
                    next_action=(
                        "choose a configured classification rule for this source, then rerun "
                        "the analysis"
                    ),
                    problem="classification",
                )
                return self._publish_problem(
                    problem_task_id,
                    outcome,
                    strategy=strategy,
                    source=item.source,
                    type_policy=type_policy,
                    metadata_policy=metadata_policy,
                    classification_policy=classification_policy,
                    recognition_types=tuple(
                        value.recognition_type
                        for value in runtime.strategy.recognition_type_policies
                        if getattr(value, "enabled", False)
                    ),
                )
            return _PreviewOutcome(
                ManualPreviewItemStatus.BLOCKED,
                plan=self._partial_plan(strategy, item, type_policy),
                error=strategy.classification_error
                or "ClassificationPolicy did not select a MediaLibrary",
                next_action="open or resolve the linked Classification review, then rerun Preview",
            )
        media_library = next(
            (
                value
                for value in runtime.media_libraries
                if value.library_id == strategy.classification.media_library_id
            ),
            None,
        )
        if media_library is None:
            return _PreviewOutcome(
                ManualPreviewItemStatus.UNAVAILABLE,
                plan=self._partial_plan(strategy, item, type_policy),
                error="classified MediaLibrary is unavailable under the pinned snapshot",
                next_action=(
                    "repair the pinned MediaLibrary/Storage configuration, then rerun Preview"
                ),
            )
        configured_storages = self._create_storages(
            runtime, {item.source.storage_id, media_library.storage_id}
        )
        source_storage = self._guarded_storage(configured_storages, item.source.storage_id)
        target_storage = self._guarded_storage(configured_storages, media_library.storage_id)
        plan = self._plan(
            strategy,
            type_policy,
            media_library,
            source_storage,
            target_storage,
            item,
            source_library.root_path,
        )
        plan = apply_hash_duplicate_detection(
            plan,
            source_storage,
            target_storage,
            type_policy.organize_policy.duplicate_detection,
        )
        truncated = False
        attachments = AttachmentDiscovery().discover(
            source_storage,
            plan.source_location or StorageLocation(item.source.storage_id, item.source.path),
            type_policy.organize_policy.attachments,
        )
        if len(attachments.attachments) > _MAX_COLLECTION:
            attachments = MediaFileSet(
                attachments.primary, attachments.attachments[:_MAX_COLLECTION]
            )
            truncated = True
        plan = AttachmentPlanner().plan(plan, attachments, target_storage)
        plan = self._resolve_conflicts(
            plan, type_policy, target_storage, decision=bound.confirmation
        )
        plan_document = self._plan_document(
            strategy, plan, item, type_policy, source_storage, target_storage
        )
        if truncated:
            plan_document["bounds"] = {
                "truncated": True,
                "reason": "attachment collection exceeded the Preview bound",
            }
        plan_document = _fit_json(plan_document)
        plan_fingerprint = _fingerprint(plan_document)
        capability = plan_document.get("capabilities", {})
        blocked = (
            bool(plan.conflicts)
            or plan.status is PlanStatus.INVALID
            or capability.get("verdict") == "capability_gap"
        )
        if blocked:
            capability_gap = capability.get("verdict") == "capability_gap"
            # Only a genuine destination conflict is one of the four native
            # organizing problems.  A Storage capability gap is a technical
            # condition and keeps its factual, non-business outcome.
            conflict_problem = bool(plan.conflicts) and not capability_gap
            outcome = _PreviewOutcome(
                ManualPreviewItemStatus.BLOCKED,
                plan_document,
                plan_fingerprint,
                error=(
                    "exact plan contains unresolved conflicts or a Storage capability gap"
                    if plan.conflicts or capability_gap
                    else "exact plan is invalid"
                ),
                next_action=(
                    "open the affected conflict/capability explanation, resolve it, "
                    "then request a fresh Preview"
                ),
                truncated=truncated,
                problem="conflict" if conflict_problem else None,
            )
            return self._publish_problem(
                problem_task_id,
                outcome,
                strategy=strategy,
                source=item.source,
                type_policy=type_policy,
                metadata_policy=metadata_policy,
                classification_policy=classification_policy,
                recognition_types=tuple(
                    value.recognition_type
                    for value in runtime.strategy.recognition_type_policies
                    if getattr(value, "enabled", False)
                ),
                plan=plan,
            )
        if truncated:
            return _PreviewOutcome(
                ManualPreviewItemStatus.TRUNCATED,
                plan_document,
                plan_fingerprint,
                error="exact attachment evidence exceeded the Preview bound",
                next_action="reduce the related sidecar set, then request a fresh Preview",
                truncated=True,
            )
        return _PreviewOutcome(
            ManualPreviewItemStatus.PREVIEWED,
            plan_document,
            plan_fingerprint,
            next_action=(
                "inspect this exact zero-mutation plan; authorize selected items for execution"
            ),
        )

    def _load_runtime(self, snapshot_id: str, snapshot_digest: str):
        if self._runtime_resolver is not None:
            try:
                try:
                    runtime = self._runtime_resolver(snapshot_id, snapshot_digest)
                except TypeError:
                    runtime = self._runtime_resolver()
            except ManualPreviewError:
                raise
            except Exception as error:
                raise ManualPreviewUnavailable(
                    "the pinned Active configuration snapshot is unavailable or unreadable",
                    details={"snapshotId": snapshot_id, "reason": type(error).__name__},
                ) from error
        elif self._configuration_service is not None:
            try:
                self._configuration_service.validate_runtime_snapshot(snapshot_id, snapshot_digest)
                revision = self._configuration_service.require(snapshot_id)
                self._configuration_service.verify_integrity(revision)
                from mediaflow.infrastructure.runtime_configuration import (
                    load_managed_runtime_configuration,
                    with_managed_snapshot,
                )

                database_path = self._configuration_service.bootstrap_database_path or str(
                    getattr(self._configuration_service.repository, "database_path", "")
                )
                runtime = with_managed_snapshot(
                    load_managed_runtime_configuration(
                        revision.document, bootstrap_database_path=database_path
                    ),
                    snapshot_id=snapshot_id,
                    digest=snapshot_digest,
                )
            except ManualPreviewError:
                raise
            except Exception as error:
                raise ManualPreviewUnavailable(
                    "the pinned Active configuration snapshot is unavailable or unreadable",
                    details={"snapshotId": snapshot_id, "reason": type(error).__name__},
                ) from error
        elif self._configuration is not None:
            runtime = self._configuration
        else:
            raise ManualPreviewUnavailable(
                "manual Preview runtime configuration is unavailable",
                details={"snapshotId": snapshot_id},
            )
        if isinstance(runtime, Mapping) or not hasattr(runtime, "strategy"):
            raise ManualPreviewUnavailable(
                "manual Preview requires a normalized managed runtime snapshot",
                details={"snapshotId": snapshot_id},
            )
        authority = getattr(runtime, "configuration_authority", "MANAGED")
        runtime_id = getattr(runtime, "configuration_snapshot_id", None)
        runtime_digest = getattr(runtime, "configuration_snapshot_digest", None)
        if authority != "MANAGED" or runtime_id != snapshot_id or runtime_digest != snapshot_digest:
            raise ManualPreviewUnavailable(
                "manual Preview cannot use a draft, JSON bootstrap, or later Active configuration",
                details={"snapshotId": snapshot_id, "authority": authority},
            )
        return runtime

    def _create_storages(self, runtime, ids: set[str]) -> dict[str, Storage]:
        if self._storage_factory is not None:
            try:
                values = self._storage_factory(runtime, ids)
            except TypeError:
                values = self._storage_factory(ids)
            result = dict(values)
        elif callable(getattr(runtime, "create_storages", None)):
            result = dict(runtime.create_storages(external=self._storages, storage_ids=ids))
        else:
            result = dict(self._storages)
        missing = sorted(ids.difference(result))
        if missing:
            raise ManualPreviewUnavailable(
                "a configured Storage required by the exact Preview is unavailable",
                details={"storageIds": missing},
            )
        return result

    @staticmethod
    def _guarded_storage(
        storages: Mapping[str, Storage], storage_id: str
    ) -> PreviewReadOnlyStorage:
        try:
            storage = storages[storage_id]
        except KeyError as error:
            raise ManualPreviewUnavailable(
                f"Storage {storage_id!r} is unavailable", details={"storageId": storage_id}
            ) from error
        if storage is None or getattr(storage, "storage_id", storage_id) != storage_id:
            raise ManualPreviewUnavailable(
                "the selected Storage adapter does not match the pinned authority",
                details={"storageId": storage_id},
            )
        return PreviewReadOnlyStorage(storage)

    def _provider_registry(self, provider_ids: tuple[str, ...]) -> MetadataProviderRegistry:
        if self._providers is not None:
            return self._providers
        requested = tuple(dict.fromkeys(provider_ids))
        if requested in self._provider_cache:
            return self._provider_cache[requested]
        if self._provider_factory is None:
            raise ManualPreviewUnavailable(
                "the Metadata Provider authority required by this Preview is unavailable",
                details={"providerIds": list(requested)},
            )
        try:
            registry = self._provider_factory(requested)
        except ManualPreviewError:
            raise
        except Exception as error:
            raise ManualPreviewUnavailable(
                "the Metadata Provider authority required by this Preview is unavailable",
                details={"providerIds": list(requested), "reason": type(error).__name__},
            ) from error
        if not isinstance(registry, MetadataProviderRegistry):
            raise ManualPreviewUnavailable("Metadata Provider registry is invalid")
        self._provider_cache[requested] = registry
        return registry

    def _runner(self, runtime, providers, source_storage, storages) -> StrategyTestRunner:
        if self._strategy_runner_factory is not None:
            try:
                return self._strategy_runner_factory(runtime, providers, source_storage, storages)
            except TypeError:
                try:
                    return self._strategy_runner_factory(
                        runtime.strategy, providers, source_storage
                    )
                except TypeError:
                    return self._strategy_runner_factory(runtime.strategy)
        return strategy_runner_from_configuration(
            runtime.strategy,
            providers,
            storage_guard=source_storage,
            storages=storages,
        )

    def _metadata_reference(self, choice, intent, record, policy):
        metadata = choice.metadata
        if metadata is None:
            return None
        if metadata.provider and metadata.provider_id and metadata.media_type:
            return metadata
        authorities = getattr(self._intent_service, "_metadata_authorities", lambda *_: ())(
            record, intent.options, getattr(policy, "media_type", None)
        )
        for value in authorities:
            if metadata.review_ref is not None and value.get("reviewRef") != metadata.review_ref:
                continue
            if metadata.candidate_ref is not None and metadata.candidate_ref not in value.get(
                "candidateRefs", ()
            ):
                continue
            if value.get("provider") and value.get("providerId") and value.get("mediaType"):
                return type(metadata)(
                    value["provider"],
                    value["providerId"],
                    value["mediaType"],
                    value.get("title"),
                    value.get("year"),
                    metadata.candidate_ref,
                    metadata.review_ref,
                )
        raise ManualPreviewError(
            "manual metadata reference is no longer linked to current source evidence",
            code="metadata_unverified",
            next_action=(
                "choose the normalized identity shown by the current source-linked review, "
                "then rerun Preview"
            ),
            details={
                "resourceLibraryId": getattr(record, "resource_library_id", None),
                "path": getattr(record, "path", None),
            },
        )

    @staticmethod
    def _metadata_selection(recognition_type, policy_id, metadata):
        from mediaflow.domain.metadata_review import MetadataSelection

        return MetadataSelection(
            recognition_type,
            policy_id,
            metadata.provider,
            metadata.provider_id,
            metadata.media_type,
        )

    @staticmethod
    def _bound_source_decisions(review_decisions: object | None, item):
        """Extract the resolved continuation decisions for one item's source."""

        if review_decisions is None:
            return _BoundSourceDecisions()
        key = (item.source.storage_id, item.source.path)

        def lookup(name: str) -> object | None:
            values = getattr(review_decisions, name, None)
            if not isinstance(values, Mapping):
                return None
            return values.get(key)

        return _BoundSourceDecisions(
            confirmation=lookup("confirmations"),
            metadata_review=lookup("metadata_reviews"),
            metadata_correction=lookup("metadata_corrections"),
            classification_review=lookup("classification_reviews"),
            recognition_review=lookup("recognition_reviews"),
        )

    def _durable_identity_compatible(self, metadata_policy, item, identity) -> bool:
        """Whether a completed analysis identity can be pinned to this item.

        The identity must match the pinned MetadataPolicy's provider and media
        type, so a stale, cross-source or cross-policy identity is never
        replanned.  Its RecognitionType is only the type the analysis happened
        to resolve under; because the same provider+media type is source-
        determined, the identity is rebound to this item's own forced
        RecognitionType by :meth:`_rebind_durable_identity` rather than being
        rejected for a policy-equivalent type difference.
        """

        if not isinstance(identity, MediaIdentity):
            return False
        if not self._identity_compatible(
            metadata_policy, identity.provider, identity.media_type.value
        ):
            return False
        expected = getattr(metadata_policy, "media_type", None)
        if expected is not None and identity.media_type is not expected:
            return False
        return True

    @staticmethod
    def _rebind_durable_identity(
        identity: MediaIdentity, recognition_type_id: str
    ) -> MediaIdentity:
        if identity.recognition_type_id == recognition_type_id:
            return identity
        return replace(identity, recognition_type_id=recognition_type_id)

    @staticmethod
    def _metadata_decision_mismatch(
        durable: MediaIdentity,
        metadata_selection,
        metadata_correction,
        metadata_reference,
    ) -> str | None:
        """Whether a saved Metadata decision contradicts the durable identity.

        The summary reuses the identity the completed re-analysis actually
        resolved, so any decision the operator also saved must agree with it on
        the provider and media type, and on the concrete Provider ID whenever
        the decision named one.  A contradiction is returned as a bounded reason
        so the caller blocks for a fresh analysis instead of silently preferring
        one fact over the other.
        """

        provider = None
        provider_id = None
        media_type = None
        if metadata_selection is not None:
            provider = getattr(metadata_selection, "provider", None)
            provider_id = getattr(metadata_selection, "provider_id", None)
            media_type = getattr(metadata_selection, "media_type", None)
        elif metadata_correction is not None:
            provider = getattr(metadata_correction, "provider", None)
            provider_id = getattr(metadata_correction, "direct_provider_id", None)
            media_type = getattr(metadata_correction, "media_type", None)
        elif metadata_reference is not None:
            provider = getattr(metadata_reference, "provider", None)
            provider_id = getattr(metadata_reference, "provider_id", None)
            media_type = getattr(metadata_reference, "media_type", None)
        else:
            return None
        if provider and provider != durable.provider:
            return "the saved Metadata decision names a different Provider than the analysis"
        if provider_id and provider_id != durable.provider_id:
            return "the saved Metadata decision names a different identity than the analysis"
        if media_type and str(media_type) != durable.media_type.value:
            return "the saved Metadata decision names a different media type than the analysis"
        return None

    @staticmethod
    def _identity_compatible(policy, provider: str | None, media_type: str | None) -> bool:
        """Whether a resolved identity can be planned under the pinned MetadataPolicy."""

        if not provider or not media_type or not getattr(policy, "enabled", True):
            return False
        if getattr(policy, "provider_id", None) != provider:
            return False
        if policy.query_type is MediaQueryType.NONE:
            return False
        expected = getattr(policy, "media_type", None)
        if expected is None:
            return True
        try:
            return expected is MediaType(media_type)
        except ValueError:
            return False

    def _bound_metadata_decision(self, bound, item, type_policy, metadata_policy):
        """Bind a resolved identity decision to the item's own manual choice context.

        A Metadata review decision or a Metadata Correction decision made under the
        linked re-analysis is an identity fact about the source; it can be planned
        again only when it is compatible with the metadata policy pinned by the
        manual choice.  Incompatible decisions are left unapplied so the normal
        analysis runs and reports its own bounded blocker.
        """

        if bound.metadata_review is not None:
            review = bound.metadata_review
            provider = getattr(review, "selected_provider", None)
            provider_id = getattr(review, "selected_provider_id", None)
            media_type = getattr(review, "selected_media_type", None)
            if self._identity_compatible(metadata_policy, provider, media_type):
                return (
                    MetadataSelection(
                        item.choice.recognition_type_id,
                        type_policy.metadata_policy_id,
                        provider,
                        provider_id,
                        media_type,
                    ),
                    None,
                )
            return None, None
        if bound.metadata_correction is not None:
            correction = bound.metadata_correction
            provider = getattr(correction, "provider_id", None)
            media_type = getattr(correction, "corrected_media_type", None)
            if self._identity_compatible(metadata_policy, provider, media_type):
                return (
                    None,
                    MetadataCorrectionSelection(
                        item.choice.recognition_type_id,
                        type_policy.metadata_policy_id,
                        provider,
                        getattr(correction, "corrected_query", None),
                        getattr(correction, "corrected_year", None),
                        media_type,
                        getattr(correction, "direct_provider_id", None),
                    ),
                )
        return None, None

    def _bound_classification_decision(self, bound, item, type_policy):
        """Bind a resolved Classification decision to the pinned manual policy."""

        review = bound.classification_review
        if review is None:
            return None
        if (
            getattr(review, "classification_policy_id", None)
            != type_policy.classification_policy_id
        ):
            return None
        rule_id = getattr(review, "selected_rule_id", None)
        library_id = getattr(review, "selected_media_library_id", None)
        relative_path = getattr(review, "selected_relative_path", None)
        if not rule_id or not library_id or not relative_path:
            return None
        return ClassificationSelection(
            item.choice.recognition_type_id,
            type_policy.classification_policy_id,
            rule_id,
            library_id,
            relative_path,
        )

    @staticmethod
    def _plan(
        strategy,
        type_policy,
        media_library,
        source_storage,
        target_storage,
        item,
        source_library_root,
    ) -> OrganizePlan:
        return OrganizePlanner().plan(
            source_storage_id=item.source.storage_id,
            source=item.source.path,
            source_storage_path=item.source.path,
            source_library_root=source_library_root,
            recognition=strategy.recognition,
            type_policy=type_policy,
            media_library=media_library,
            naming=strategy.naming,
            classification=strategy.classification,
            media_identity=strategy.metadata.identity,
            target_storage=target_storage,
        )

    def _partial_plan(self, strategy, item, type_policy) -> dict[str, object]:
        return {
            "source": item.source.document(),
            "recognitionType": item.choice.recognition_type_id,
            "policies": {
                "recognitionTypePolicyId": type_policy.policy_id,
                "metadataPolicyId": type_policy.metadata_policy_id,
                "namingPolicyId": item.choice.naming_policy_id,
                "classificationPolicyId": item.choice.classification_policy_id,
                "organizePolicyId": item.choice.organize_policy_id,
            },
            "analysis": self._analysis_document(strategy),
            "destination": None,
            "operation": None,
            "attachments": [],
            "capabilities": {
                "verdict": "not_determined",
                "required": [],
                "declared": [],
                "missing": [],
            },
            "conflicts": [],
            "warnings": [],
            "zeroMutation": True,
            "executionState": "not_available_in_this_task",
            "bounded": True,
            "deterministic": True,
        }

    def _plan_document(
        self, strategy, plan, item, type_policy, source_storage, target_storage
    ) -> dict[str, object]:
        destination = {
            "storageId": plan.target_storage_id,
            "mediaLibraryRoot": _bounded(plan.media_library_root),
            "relativePath": _bounded(plan.relative_destination),
            "path": _bounded(plan.target),
        }
        attachment_documents = [
            {
                "type": value.attachment_type.value,
                "source": {
                    "storageId": value.source.storage_id,
                    "path": _bounded(value.source.path),
                },
                "destination": {
                    "storageId": value.destination.storage_id,
                    "path": _bounded(value.destination.path),
                },
                "operation": value.operation.value,
                "suffix": _bounded(value.suffix, 128),
                "language": value.language,
                "blockedReason": value.blocked_reason,
                "nextAction": attachment_result_document(
                    plan, value, status="not_executed", reason=value.blocked_reason
                )["next_action"]
                if value.blocked_reason
                else None,
            }
            for value in plan.attachment_plans[:_MAX_COLLECTION]
        ]
        exact_attachment_documents = [
            {
                "type": value.attachment_type.value,
                "source": {
                    "storageId": value.source.storage_id,
                    "path": value.source.path,
                },
                "destination": {
                    "storageId": value.destination.storage_id,
                    "path": value.destination.path,
                },
                "operation": value.operation.value,
                "suffix": value.suffix,
                "language": value.language,
                "blockedReason": value.blocked_reason,
            }
            for value in plan.attachment_plans[:_MAX_COLLECTION]
        ]
        return {
            "source": item.source.document(),
            "mediaIdentity": _identity_document(strategy.metadata.identity),
            "analysis": self._analysis_document(strategy),
            "recognitionType": strategy.recognition.recognition_type_id,
            "policies": {
                "recognitionTypePolicyId": type_policy.policy_id,
                "metadataPolicyId": type_policy.metadata_policy_id,
                "namingPolicyId": plan.naming_policy_id,
                "classificationPolicyId": plan.classification_policy_id,
                "organizePolicyId": plan.organize_policy_id,
            },
            "destination": destination,
            "operation": plan.operation.value,
            "operationPolicy": type_policy.organize_policy.operation.value,
            "attachments": attachment_documents,
            # This is the exact executor input retained alongside the readable
            # explanation.  It contains no current-config object or provider
            # payload, so execution can reload the reviewed target without
            # rebuilding it from a later Active snapshot.
            "executionPlan": self._execution_plan_document(plan, exact_attachment_documents),
            "cleanupProjection": self._cleanup_projection(plan, source_storage),
            "capabilities": self._capabilities(plan, type_policy, source_storage, target_storage),
            "conflicts": [
                {
                    "type": value.type.value,
                    "source": _bounded(value.source),
                    "destination": _bounded(value.destination),
                    "details": _bounded(value.details),
                }
                for value in plan.conflicts[:_MAX_COLLECTION]
            ],
            "warnings": [_bounded(value) for value in plan.warnings[:_MAX_COLLECTION]],
            "planStatus": plan.status.value,
            "planId": plan.plan_id,
            "zeroMutation": True,
            "executionState": "ready_for_explicit_authorization",
            "bounded": True,
            "deterministic": True,
        }

    def _resolve_conflicts(self, plan, type_policy, target_storage, *, decision=None):
        """Apply only an existing configured/recorded decision; never mutate Storage."""

        if not plan.conflicts:
            return plan
        resolver = ConflictResolver()
        # A saved continuation decision for this exact source collision wins.  The
        # linked re-analysis plan id differs from the manual Preview plan id, so
        # the decision is matched by source and destination rather than plan id.
        if decision is not None:
            replacement = self._apply_conflict_confirmation(
                plan, type_policy, target_storage, decision
            )
            if replacement is not None:
                return replacement
        configured = resolver.apply_configured(plan, type_policy.organize_policy, target_storage)
        if configured is not None:
            return configured
        method = getattr(self._repository, "list_confirmations", None)
        if not callable(method):
            return plan
        try:
            confirmations = tuple(method(status=None, limit=1000))
        except TypeError:
            confirmations = tuple(method(limit=1000))
        for confirmation in confirmations:
            if getattr(confirmation, "plan_id", None) != plan.plan_id:
                continue
            replacement = self._apply_conflict_confirmation(
                plan, type_policy, target_storage, confirmation
            )
            if replacement is not None:
                return replacement
        return plan

    @staticmethod
    def _apply_conflict_confirmation(plan, type_policy, target_storage, confirmation):
        """Apply one resolved conflict confirmation to an exact matching plan."""

        if (
            getattr(confirmation, "source_storage_id", None) != plan.source_storage_id
            or getattr(confirmation, "source_path", None)
            != (plan.source_location.path if plan.source_location else plan.source)
            or getattr(confirmation, "destination_storage_id", None) != plan.target_storage_id
            or getattr(confirmation, "destination_path", None)
            != (plan.destination_location.path if plan.destination_location else plan.target)
            or getattr(getattr(confirmation, "status", None), "value", None) != "resolved"
        ):
            return None
        selected = getattr(confirmation, "selected_strategy", None)
        try:
            strategy = ConflictStrategy(selected)
        except (TypeError, ValueError):
            return None
        resolver = ConflictResolver()
        if strategy is ConflictStrategy.SKIP:
            return replace(plan, operation=PlanOperation.SKIP, status=PlanStatus.NOOP, conflicts=())
        if strategy is ConflictStrategy.OVERWRITE:
            return resolver.overwrite(
                plan,
                type_policy.organize_policy,
                confirmed=bool(getattr(confirmation, "overwrite_authorized", False)),
            )
        if strategy is ConflictStrategy.RENAME:
            return resolver.rename(plan, target_storage)
        return None

    @staticmethod
    def _execution_plan_document(plan, attachments):
        return {
            "planId": plan.plan_id,
            "sourceStorageId": plan.source_storage_id,
            "sourcePath": plan.source_location.path if plan.source_location else plan.source,
            "targetStorageId": plan.target_storage_id,
            "targetPath": plan.destination_location.path
            if plan.destination_location
            else plan.target,
            "operation": plan.operation.value,
            "linkOperation": plan.link_operation.value if plan.link_operation else None,
            "mediaLibraryRoot": plan.media_library_root,
            "relativeDestination": plan.relative_destination,
            "sourceLibraryRoot": plan.source_library_root,
            "overwriteAuthorized": plan.overwrite_authorized,
            "rollback": {
                "enabled": plan.rollback_policy.enabled,
                "cleanupCreatedDirectories": plan.rollback_policy.cleanup_created_directories,
            },
            "sourceDirectoryCleanup": {
                "mode": plan.source_directory_cleanup.mode.value,
                "maxParentDirectories": plan.source_directory_cleanup.max_parent_directories,
                "ignorePatterns": list(
                    plan.source_directory_cleanup.ignore_patterns[:_MAX_COLLECTION]
                ),
                "maxEntries": plan.source_directory_cleanup.max_entries,
            },
            "attachments": attachments,
        }

    @staticmethod
    def _cleanup_projection(plan, source_storage) -> dict[str, object] | None:
        """The bounded read-only explanation of the pinned cleanup policy.

        A pinned plan with no configured cleanup returns ``None`` so the
        Preview does not invent a destructive surface the policy does not have.
        The projection is read-only, confined to the exact source parent and
        names only logical relative paths.
        """

        if plan.source_directory_cleanup.mode is DirectoryCleanupMode.NONE:
            return None
        try:
            projection = OrganizerExecutor().project_source_cleanup(
                plan,
                source_storage,
                plan.source_location.path if plan.source_location else plan.source,
            )
        except Exception:
            return None
        return projection.document()

    def _analysis_document(self, strategy) -> dict[str, object]:
        parsed = strategy.parsed
        recognition = strategy.recognition
        metadata = strategy.metadata
        return {
            "parse": {
                "titleCandidate": _bounded(parsed.title_candidate),
                "year": parsed.year,
                "season": parsed.season,
                "episode": parsed.episode,
                "episodes": list(parsed.episodes[:_MAX_COLLECTION]),
                "resolution": _bounded(parsed.resolution_tag, 64),
                "source": _bounded(parsed.source_tag, 64),
                "videoCodec": _bounded(parsed.video_codec_tag, 64),
                "audio": _bounded(parsed.audio_tag, 64),
                "hdr": _bounded(parsed.hdr_tag, 64),
                "version": _bounded(parsed.version_tag, 64),
                "releaseGroup": _bounded(parsed.release_group, 128),
                "evidence": [
                    {
                        "field": _bounded(value.field, 64),
                        "value": _bounded(value.value, _MAX_TEXT),
                        "source": _bounded(value.source, 64),
                        "confidence": _bounded(value.confidence, 32),
                    }
                    for value in parsed.evidence[:_MAX_COLLECTION]
                ],
                "warnings": [
                    _bounded(value.message) for value in parsed.warnings[:_MAX_COLLECTION]
                ],
            },
            "recognition": {
                "status": recognition.status.value,
                "recognitionTypeId": recognition.recognition_type_id,
                "ruleId": _bounded(recognition.rule_id),
                "score": recognition.score,
                "confidence": _bounded(recognition.confidence, 32),
                "reasons": [
                    {"code": _bounded(value.code, 64), "message": _bounded(value.message)}
                    for value in recognition.reasons[:_MAX_COLLECTION]
                ],
                "warnings": [_bounded(value) for value in recognition.warnings[:_MAX_COLLECTION]],
            },
            "metadata": self._metadata_document(metadata),
            "naming": self._naming_document(strategy.naming, strategy.naming_error),
            "classification": self._classification_document(
                strategy.classification, strategy.classification_error
            ),
        }

    @staticmethod
    def _metadata_document(metadata) -> dict[str, object]:
        if metadata is None:
            return {"available": False, "reason": "metadata stage was not reached"}
        identity = metadata.identity
        match = metadata.match
        return {
            "available": identity is not None,
            "status": metadata.status.value,
            "query": _bounded(metadata.query),
            "identity": _identity_document(identity),
            "match": {
                "status": _bounded(match.status if match else None),
                "score": match.score if match else None,
                "reasons": list(match.reasons[:_MAX_COLLECTION]) if match else [],
                "warnings": list(match.warnings[:_MAX_COLLECTION]) if match else [],
                "candidateCount": len(match.candidate_scores) if match else 0,
                "candidates": [
                    {
                        "provider": _bounded(value.candidate.provider),
                        "providerId": _bounded(value.candidate.provider_id),
                        "mediaType": value.candidate.media_type.value,
                        "title": _bounded(value.candidate.title),
                        "year": value.candidate.year,
                        "score": value.total_score,
                        "exactTitle": value.exact_title,
                        "exactYear": value.exact_year,
                    }
                    for value in (match.candidate_scores[:_MAX_COLLECTION] if match else ())
                ],
            },
        }

    @staticmethod
    def _naming_document(naming, error) -> dict[str, object]:
        if naming is None:
            return {"available": False, "reason": _bounded(error) or "naming stage was not reached"}
        return {
            "available": True,
            "policyId": naming.policy_id,
            "recognitionTypeId": naming.recognition_type_id,
            "directory": _bounded(naming.directory),
            "directorySegments": [
                _bounded(value) for value in naming.directory_segments[:_MAX_COLLECTION]
            ],
            "filename": _bounded(naming.filename),
            "warnings": [_bounded(value) for value in naming.warnings[:_MAX_COLLECTION]],
            "sanitizationChanges": [
                _bounded(value) for value in naming.sanitization_changes[:_MAX_COLLECTION]
            ],
        }

    @staticmethod
    def _classification_document(classification, error) -> dict[str, object]:
        if classification is None:
            return {
                "available": False,
                "reason": _bounded(error) or "classification stage was not reached",
            }
        return {
            "available": classification.status is ClassificationStatus.CLASSIFIED,
            "status": classification.status.value,
            "policyId": classification.policy_id,
            "recognitionTypeId": classification.recognition_type_id,
            "mediaLibraryId": classification.media_library_id,
            "relativePath": _bounded(classification.relative_path),
            "matchedRuleId": _bounded(classification.matched_rule_id),
            "matchedRuleName": _bounded(classification.matched_rule_name),
            "evidence": [_bounded(value) for value in classification.evidence[:_MAX_COLLECTION]],
            "warnings": [_bounded(value) for value in classification.warnings[:_MAX_COLLECTION]],
        }

    @staticmethod
    def _capabilities(plan, type_policy, source_storage, target_storage) -> dict[str, object]:
        required = _required_capabilities(plan)
        declared: list[str] = []
        for capability in required:
            storage = source_storage if capability == "can_delete" else target_storage
            if storage is not None and getattr(storage.capabilities, capability, False):
                declared.append(capability)
        missing = [value for value in required if value not in declared]
        return {
            "required": required,
            "declared": declared,
            "missing": missing,
            "verdict": "capability_gap" if missing else "ok" if required else "not_applicable",
        }

    def _recognition_problem_outcome(
        self,
        item,
        runtime,
        *,
        problem_task_id: str | None,
    ) -> _PreviewOutcome:
        """Publish one undecided source as its own native Recognition problem.

        The rule engine is the production one and reads only the local path/
        filename/directory/extension, so this performs no Provider call, no Storage
        read beyond the already observed identity and no mutation.  The outcome keeps
        whatever the rules really concluded — a miss or an ambiguity — as the
        operator-visible reason, and the review's choices are the pinned enabled
        RecognitionTypes.  No type, identity, target or plan is fabricated, so a
        later confirmation cannot exist before the decision.
        """

        context = file_context_from_path(
            item.source.path,
            resource_library_id=item.source.resource_library_id,
            storage_id=item.source.storage_id,
        )
        parsed = MediaParserService().parse(context)
        engine = RecognitionRuleEngine(
            tuple(runtime.strategy.recognition_types),
            tuple(runtime.strategy.recognition_rules),
        )
        recognition = engine.recognize(RecognitionContext(context, parsed))
        type_policies = {
            policy.recognition_type_id: policy
            for policy in runtime.strategy.recognition_type_policies
            if policy.enabled and policy.recognition_type.enabled
        }
        # The partial plan carries no destination, operation or policy identity: this
        # item has no decided type, so there is nothing to plan and nothing to confirm.
        plan_document = {
            "source": item.source.document(),
            "recognitionType": None,
            "policies": {
                "recognitionTypePolicyId": None,
                "metadataPolicyId": None,
                "namingPolicyId": None,
                "classificationPolicyId": None,
                "organizePolicyId": None,
            },
            "analysis": {
                "stage": "recognition",
                "status": (
                    "ambiguous"
                    if recognition.status is RecognitionStatus.AMBIGUOUS
                    else "unrecognized"
                ),
                "matchedRules": [value.rule_id for value in recognition.matched_rules],
                "alternatives": [
                    {"recognitionType": value.recognition_type_id, "score": value.score}
                    for value in recognition.alternatives
                ],
            },
            "destination": None,
            "operation": None,
            "attachments": [],
            "executionPlan": None,
            "capabilities": {
                "verdict": "not_determined",
                "required": [],
                "declared": [],
                "missing": [],
            },
            "conflicts": [],
            "warnings": [],
            "planStatus": "invalid",
            "zeroMutation": True,
            "executionState": "not_available_in_this_task",
            "bounded": True,
            "deterministic": True,
        }
        outcome = _PreviewOutcome(
            ManualPreviewItemStatus.BLOCKED,
            plan_document,
            error=(
                "several RecognitionTypes match this source with equal priority and score"
                if recognition.status is RecognitionStatus.AMBIGUOUS
                else "no enabled RecognitionRule matched this source"
            ),
            next_action=(
                "choose one enabled RecognitionType for this exact source on this page, then "
                "rerun the analysis"
            ),
            problem="recognition",
        )
        return self._publish_problem(
            problem_task_id,
            outcome,
            strategy=SimpleNamespace(recognition=recognition, parsed=parsed),
            source=item.source,
            type_policy=next(iter(type_policies.values()), None),
            metadata_policy=None,
            classification_policy=None,
            recognition_types=tuple(policy.recognition_type for policy in type_policies.values()),
        )

    def _publish_problem(
        self,
        problem_task_id: str | None,
        outcome: _PreviewOutcome,
        *,
        strategy,
        source,
        type_policy,
        metadata_policy=None,
        classification_policy=None,
        recognition_types=(),
        plan=None,
    ) -> _PreviewOutcome:
        """Publish one native problem on the owning Task from live analysis objects.

        Called at the exact boundary where the shared pipeline concluded the
        problem, so the review is created from the *live* strategy/plan rather than
        reconstructed from a persisted document.  Nothing is published for an
        ordinary Preview (``problem_task_id`` is ``None``) and nothing is published
        for a technical cause.
        """

        if problem_task_id is None or outcome.problem is None:
            return outcome
        projector = getattr(self._repository, "publish_task_item_problem", None)
        if not callable(projector):
            return outcome
        try:
            projector(
                task_id=problem_task_id,
                problem=outcome.problem,
                strategy=strategy,
                source=source,
                type_policy=type_policy,
                metadata_policy=metadata_policy,
                classification_policy=classification_policy,
                recognition_types=recognition_types,
                plan=plan,
            )
        except Exception:  # noqa: BLE001 - one bounded projection, never a media fault
            return outcome
        return outcome

    def _persist_create(self, preview):
        method = getattr(self._repository, "create_manual_preview", None)
        if not callable(method):
            raise ManualPreviewUnavailable("manual Preview persistence is unavailable")
        return method(preview, preview.items)

    @staticmethod
    def _analysis_checkpoint(
        callback: Callable[[str, int, int, int], None] | None,
        phase: str,
        visited_entries: int,
        analysed_items: int,
        total_items: int,
    ) -> None:
        if callback is not None:
            callback(phase, visited_entries, analysed_items, total_items)

    def discard_uncommitted(self, intent_id: str, preview_id: str) -> None:
        """Retire one analyzed plan whose run lost its publication race.

        A Worker that analyzed a frozen manifest may discover at the commit
        boundary that the operator paused, cancelled or handed the run to a
        successor.  That plan was never linked to the run and never entered any
        confirmation, so it must not remain readable as the intent's current
        summary (or as a plan a paused/cancelled run could still reach).  The
        items are marked stale with the truthful reason and the aggregate stops
        being current; nothing is deleted and the exact evidence stays readable
        as history.  An already-current or missing record is left untouched.
        """

        if not isinstance(preview_id, str) or not preview_id.strip():
            return
        value = self._repository.get_manual_preview(preview_id)
        if value is None or not value.current:
            return
        if intent_id and value.intent_id != intent_id:
            return
        reason = "the analysis was not published because the run's control changed first"
        # The retirement is scoped to this exact Preview identity so a newer
        # plan (a successor's link or a continued run's re-analysis) is never
        # affected by the losing owner's cleanup.
        discarder = getattr(self._repository, "discard_manual_preview", None)
        if callable(discarder):
            discarder(preview_id, self._safe_error(reason), self._clock())
            return
        # A repository without that exact-scope capability (a bounded test
        # double) retires the plan through the item-scoped path only while it is
        # still the intent's latest plan, so a newer plan is never touched.
        latest = self._latest_preview(value.intent_id)
        if latest is None or latest.preview_id != preview_id:
            return
        self._invalidate_items(
            tuple(item.item_id for item in value.items),
            reason,
            intent_id=value.intent_id,
        )

    def _latest_preview(self, intent_id: str):
        method = getattr(self._repository, "get_latest_manual_preview", None)
        if callable(method):
            return method(intent_id)
        method = getattr(self._repository, "list_manual_previews", None)
        if callable(method):
            values = method(intent_id, limit=1)
            return values[0] if values else None
        return None

    def _stale_current_items(self, preview) -> tuple[str, ...]:
        try:
            intent = self._load_intent(preview.intent_id)
        except ManualIntentError:
            return tuple(item.item_id for item in preview.items if item.current)
        current_by_id = {item.item_id: item for item in intent.items}
        stale: list[str] = []
        for item in preview.items:
            if not item.current:
                continue
            current = current_by_id.get(item.item_id)
            if current is None or current.version != item.item_version:
                stale.append(item.item_id)
                continue
            try:
                # Preview freshness is based on durable reviewed inputs.
                # The Worker owns the authoritative live Storage check before
                # any mutation, so an unrelated later directory read does not
                # stale this persisted Preview.
                state = self._input_state(intent, current, current.source)
            except Exception:
                stale.append(item.item_id)
                continue
            if state["inputFingerprint"] != item.input_fingerprint:
                stale.append(item.item_id)
        return tuple(stale)

    def _invalidate_items(
        self, item_ids: Sequence[str], reason: str, *, intent_id: str | None = None
    ) -> None:
        if not item_ids:
            return
        method = getattr(self._repository, "mark_manual_preview_items_stale", None)
        if callable(method):
            method(intent_id, tuple(item_ids), self._safe_error(reason), self._clock())

    @staticmethod
    def _stale_projection(value, item_ids, reason):
        from dataclasses import replace

        ids = set(item_ids)
        items = tuple(
            replace(
                item,
                status=ManualPreviewItemStatus.STALE if item.item_id in ids else item.status,
                current=False if item.item_id in ids else item.current,
                error=_bounded(reason) if item.item_id in ids else item.error,
                next_action="request a fresh Preview for this item"
                if item.item_id in ids
                else item.next_action,
            )
            for item in value.items
        )
        return replace(value, status=ManualPreviewStatus.STALE, current=False, items=items)

    @staticmethod
    def _aggregate_status(items: Sequence[ManualPreviewItem]) -> ManualPreviewStatus:
        statuses = {item.status for item in items}
        if statuses == {ManualPreviewItemStatus.PREVIEWED}:
            return ManualPreviewStatus.PREVIEWED
        if statuses == {ManualPreviewItemStatus.STALE}:
            return ManualPreviewStatus.STALE
        if statuses == {ManualPreviewItemStatus.UNAVAILABLE}:
            return ManualPreviewStatus.UNAVAILABLE
        if statuses == {ManualPreviewItemStatus.FAILED}:
            return ManualPreviewStatus.FAILED
        if statuses == {ManualPreviewItemStatus.CANCELLED}:
            return ManualPreviewStatus.CANCELLED
        if statuses.intersection(
            {
                ManualPreviewItemStatus.UNAVAILABLE,
                ManualPreviewItemStatus.FAILED,
                ManualPreviewItemStatus.BLOCKED,
                ManualPreviewItemStatus.STALE,
                ManualPreviewItemStatus.TRUNCATED,
            }
        ):
            return (
                ManualPreviewStatus.PARTIAL
                if ManualPreviewItemStatus.PREVIEWED in statuses
                else ManualPreviewStatus.BLOCKED
            )
        return ManualPreviewStatus.PARTIAL

    @staticmethod
    def _aggregate_next_action(items: Sequence[ManualPreviewItem]) -> str:
        if all(item.status is ManualPreviewItemStatus.PREVIEWED for item in items):
            return "inspect each exact plan; authorize selected items for execution"
        return "inspect each item; resolve its stated blocker or request a fresh Preview"

    @staticmethod
    def _safe_error(value: object) -> str:
        return safe_manual_error(value, "Preview analysis failed")


def _required_capabilities(plan: OrganizePlan) -> list[str]:
    if plan.operation in {PlanOperation.NOOP, PlanOperation.SKIP}:
        return []
    if plan.operation is PlanOperation.MOVE:
        return (
            ["can_move"]
            if plan.source_storage_id == plan.target_storage_id
            else ["can_copy", "can_delete"]
        )
    if plan.operation is PlanOperation.COPY:
        return ["can_copy"]
    if plan.operation is PlanOperation.LINK:
        if plan.source_storage_id != plan.target_storage_id:
            # Link operations are intentionally never emulated across Storage
            # providers.  Keep the unsupported requirement visible so the
            # Preview is blocked instead of appearing executable.
            return ["same_storage_link"]
        return [
            "can_soft_link"
            if plan.link_operation and plan.link_operation.value == "soft_link"
            else "can_hard_link"
        ]
    return []


def _identity_document(identity) -> dict[str, object] | None:
    if identity is None:
        return None
    return {
        "provider": _bounded(identity.provider),
        "providerId": _bounded(identity.provider_id),
        "mediaType": identity.media_type.value,
        "title": _bounded(identity.title),
        "originalTitle": _bounded(identity.original_title),
        "year": identity.year,
        "season": identity.season,
        "episode": identity.episode,
        "episodes": list(identity.episodes[:_MAX_COLLECTION]),
        "episodeTitle": _bounded(identity.episode_title),
        "genres": [_bounded(value) for value in identity.genres[:_MAX_COLLECTION]],
        "countries": [_bounded(value) for value in identity.countries[:_MAX_COLLECTION]],
        "languages": [_bounded(value) for value in identity.languages[:_MAX_COLLECTION]],
        "matchedBy": _bounded(identity.matched_by),
        "recognitionTypeId": _bounded(identity.recognition_type_id),
    }


def _safe_document(value: object) -> object:
    method = getattr(value, "document", None)
    if callable(method):
        try:
            return method()
        except Exception:
            return {"type": type(value).__name__}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _safe_document(item) for key, item in list(value.items())[:_MAX_COLLECTION]
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_safe_document(item) for item in list(value)[:_MAX_COLLECTION]]
    return {"type": type(value).__name__}


def _fit_json(value: dict[str, object]) -> dict[str, object]:
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        return {
            "bounded": True,
            "deterministic": True,
            "truncated": True,
            "unavailable": "plan evidence was not JSON serializable",
            "zeroMutation": True,
            "executionState": "not_available_in_this_task",
        }
    if len(encoded.encode("utf-8")) <= MAX_MANUAL_PREVIEW_PLAN_BYTES:
        return value
    media_identity = value.get("mediaIdentity")
    compact_identity = _compact_media_identity(media_identity)
    conflicts = value.get("conflicts")
    if not isinstance(conflicts, list):
        conflicts = []
    warnings = value.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
    essential = {
        "source": value.get("source"),
        "mediaIdentity": compact_identity,
        "recognitionType": value.get("recognitionType"),
        "policies": value.get("policies"),
        "destination": value.get("destination"),
        "executionPlan": value.get("executionPlan"),
        "operation": value.get("operation"),
        "capabilities": value.get("capabilities"),
        "conflicts": conflicts[:_MAX_COLLECTION],
        "warnings": warnings[:_MAX_COLLECTION],
        "bounded": True,
        "deterministic": True,
        "truncated": True,
        "zeroMutation": True,
        "executionState": value.get("executionState") or "not_available_in_this_task",
        "unavailable": "plan evidence exceeded the bounded Preview size",
    }
    essential_encoded = json.dumps(essential, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if len(essential_encoded.encode("utf-8")) <= MAX_MANUAL_PREVIEW_PLAN_BYTES:
        return essential
    return {
        "source": value.get("source"),
        "mediaIdentity": compact_identity,
        "recognitionType": value.get("recognitionType"),
        "policies": value.get("policies"),
        "destination": value.get("destination"),
        "executionPlan": value.get("executionPlan"),
        "operation": value.get("operation"),
        "capabilities": value.get("capabilities"),
        "conflicts": [],
        "warnings": [],
        "bounded": True,
        "deterministic": True,
        "truncated": True,
        "zeroMutation": True,
        "executionState": value.get("executionState") or "not_available_in_this_task",
        "unavailable": "plan evidence was compacted to the bounded Preview identity",
    }


def _compact_media_identity(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    result = {
        key: value.get(key)
        for key in (
            "provider",
            "providerId",
            "mediaType",
            "title",
            "originalTitle",
            "year",
            "season",
            "episode",
            "recognitionTypeId",
        )
        if value.get(key) is not None
    }
    result["episodes"] = list(value.get("episodes", ()))[:16]
    for key in ("genres", "countries", "languages"):
        result[key] = [str(item)[:128] for item in value.get(key, ())[:16]]
    for key in ("episodeTitle", "matchedBy"):
        if value.get(key) is not None:
            result[key] = str(value[key])[:256]
    return result


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _bounded(value: object, limit: int = _MAX_TEXT) -> str | None:
    if value is None:
        return None
    text = str(getattr(value, "value", value))
    return text[:limit]


def _iso(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else _bounded(value, 64)


# Compatibility names for adapters that expose the shorter manual Preview
# terminology while retaining one shared application implementation.
ManualPreviewService = ManualOrganizePreviewService
CurrentSourcePreviewService = ManualOrganizePreviewService
