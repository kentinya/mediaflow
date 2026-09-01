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
from uuid import uuid4

from mediaflow.application.attachments import AttachmentDiscovery, AttachmentPlanner
from mediaflow.application.conflict_resolution import ConflictResolver
from mediaflow.application.duplicates import apply_hash_duplicate_detection
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.organizer import OrganizePlanner
from mediaflow.application.read_only_storage import (
    ReadOnlyStorageGuard,
    ReadOnlyStorageMutationError,
)
from mediaflow.application.strategy_test import (
    StrategyConfigurationError,
    StrategyTestRunner,
    strategy_runner_from_configuration,
)
from mediaflow.domain.classification import ClassificationStatus
from mediaflow.domain.manual_organize import (
    ManualChoice,
    ManualIntentError,
    ManualIntentItemStatus,
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
    MediaQueryType,
    MetadataIdentificationStatus,
)
from mediaflow.domain.organizer import (
    ConflictStrategy,
    MediaFileSet,
    OrganizePlan,
    PlanOperation,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.recognition import RecognitionStatus
from mediaflow.domain.storage import Storage, StorageError

_MAX_COLLECTION = 64
_MAX_TEXT = 512
_MAX_ID = 128
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


class ManualOrganizePreviewService:
    """Create and inspect durable, zero-mutation manual Previews."""

    MAX_ITEMS = MAX_MANUAL_PREVIEW_ITEMS

    def __init__(
        self,
        repository,
        intent_service,
        file_catalog=None,
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
        self._file_catalog = file_catalog or getattr(intent_service, "_file_catalog", None)
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
    ) -> ManualOrganizePreview:
        actor = self._actor(actor)
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
        selected = self._select_items(intent, item_ids)
        versions = self._item_versions(selected, expected_item_versions)

        records: dict[str, object] = {}
        states: dict[str, dict[str, object]] = {}
        for item in selected:
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
                record = self._resolve_current_file(item.source.file_id)
                self._assert_source(item.source, record)
                self._validate_choice(intent, item.choice, record)
            except ManualIntentError as error:
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

        preview_id = str(uuid4())
        now = self._clock()
        previous = self._latest_preview(intent.intent_id)
        preview_items: list[ManualPreviewItem] = []
        for item in selected:
            state = states[item.item_id]
            try:
                outcome = self._run_item(
                    intent,
                    item,
                    records[item.item_id],
                    preview_id,
                )
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
        )
        persisted = self._persist_create(preview)
        return persisted or preview

    create_preview = create
    create_manual_preview = create
    preview = create
    preview_intent = create

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

    def _resolve_current_file(self, file_id: str):
        resolver = getattr(self._intent_service, "_resolve_file", None)
        if callable(resolver):
            return resolver(file_id)
        if self._file_catalog is None:
            raise ManualPreviewUnavailable("File catalog is unavailable")
        return self._file_catalog.show(file_id)

    def _assert_source(self, source: ManualSourceIdentity, record) -> None:
        validator = getattr(self._intent_service, "_assert_source_unchanged", None)
        if callable(validator):
            validator(source, record)
            return
        current = ManualSourceIdentity.from_file_record(record)
        if current.document() != source.document():
            raise ManualIntentError(
                "selected FileIndex source changed after intent creation",
                code="source_stale",
                next_action=(
                    "refresh/reopen the intent and create a new selection from current Files"
                ),
            )

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
        source = ManualSourceIdentity.from_file_record(record)
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
            "sourceFingerprint": _fingerprint(source.document()),
            "sourceEvidenceVersions": source_evidence,
            "reviewVersions": reviews,
            "conflictVersions": conflicts,
            "inputFingerprint": _fingerprint(payload),
        }

    def _source_evidence_versions(
        self, source: ManualSourceIdentity
    ) -> tuple[dict[str, object], ...]:
        values: list[dict[str, object]] = []
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

    def _run_item(self, intent, item, record, preview_id: str) -> _PreviewOutcome:
        runtime = self._load_runtime(intent.snapshot_id, intent.snapshot_digest)
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
        metadata_reference = self._metadata_reference(item.choice, intent, record, metadata_policy)
        live_metadata = metadata_policy.query_type is not MediaQueryType.NONE
        if metadata_reference is not None:
            live_metadata = True
        providers = (
            self._provider_registry((metadata_policy.provider_id,)) if live_metadata else None
        )
        runner = self._runner(runtime, providers, source_storage, configured_storages)
        metadata_selection = None
        if metadata_reference is not None:
            metadata_selection = self._metadata_selection(
                item.choice.recognition_type_id,
                type_policy.metadata_policy_id,
                metadata_reference,
            )
        strategy = runner.run_path(
            item.source.path,
            live_metadata=live_metadata,
            show_naming=True,
            show_classification=True,
            resource_library_id=source_library.library_id,
            storage_id=source_library.storage_id,
            metadata_selection=metadata_selection,
            forced_recognition_type_id=item.choice.recognition_type_id,
            storage_path=item.source.path,
            source_storage=source_storage,
        )
        if strategy.recognition.status is not RecognitionStatus.MATCHED:
            return _PreviewOutcome(
                ManualPreviewItemStatus.BLOCKED,
                plan=self._partial_plan(strategy, item, type_policy),
                error="RecognitionType could not be resolved under the pinned choice",
                next_action=(
                    "open the linked Recognition review or choose a valid RecognitionType, "
                    "then rerun Preview"
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
            return _PreviewOutcome(
                ManualPreviewItemStatus.BLOCKED,
                plan=self._partial_plan(strategy, item, type_policy),
                error="metadata identity is not ready for exact planning",
                next_action=(
                    "open or resolve the linked Metadata review, then explicitly rerun Preview"
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
        plan = self._resolve_conflicts(plan, type_policy, target_storage)
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
            return _PreviewOutcome(
                ManualPreviewItemStatus.BLOCKED,
                plan_document,
                plan_fingerprint,
                error=(
                    "exact plan contains unresolved conflicts or a Storage capability gap"
                    if plan.conflicts or capability.get("verdict") == "capability_gap"
                    else "exact plan is invalid"
                ),
                next_action=(
                    "open the affected conflict/capability explanation, resolve it, "
                    "then request a fresh Preview"
                ),
                truncated=truncated,
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
            details={"fileId": record.file_id},
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

    def _resolve_conflicts(self, plan, type_policy, target_storage):
        """Apply only an existing configured/recorded decision; never mutate Storage."""

        if not plan.conflicts:
            return plan
        resolver = ConflictResolver()
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
            if (
                getattr(confirmation, "plan_id", None) != plan.plan_id
                or getattr(confirmation, "source_storage_id", None) != plan.source_storage_id
                or getattr(confirmation, "source_path", None)
                != (plan.source_location.path if plan.source_location else plan.source)
                or getattr(confirmation, "destination_storage_id", None) != plan.target_storage_id
                or getattr(confirmation, "destination_path", None)
                != (plan.destination_location.path if plan.destination_location else plan.target)
                or getattr(getattr(confirmation, "status", None), "value", None) != "resolved"
            ):
                continue
            selected = getattr(confirmation, "selected_strategy", None)
            try:
                strategy = ConflictStrategy(selected)
            except (TypeError, ValueError):
                continue
            if strategy is ConflictStrategy.SKIP:
                return replace(
                    plan, operation=PlanOperation.SKIP, status=PlanStatus.NOOP, conflicts=()
                )
            if strategy is ConflictStrategy.OVERWRITE:
                return resolver.overwrite(
                    plan,
                    type_policy.organize_policy,
                    confirmed=bool(getattr(confirmation, "overwrite_authorized", False)),
                )
            if strategy is ConflictStrategy.RENAME:
                return resolver.rename(plan, target_storage)
        return plan

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

    def _persist_create(self, preview):
        method = getattr(self._repository, "create_manual_preview", None)
        if not callable(method):
            raise ManualPreviewUnavailable("manual Preview persistence is unavailable")
        return method(preview, preview.items)

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
                record = self._resolve_current_file(current.source.file_id)
                self._assert_source(current.source, record)
                state = self._input_state(intent, current, record)
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
