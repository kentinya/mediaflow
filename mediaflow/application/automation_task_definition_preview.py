"""Analysis-only Automation Task Definition Preview application boundary.

This service answers "what would one managed Automation Task Definition do"
without creating a Job, Task, authority, configuration revision, or Storage
effect.  It pins the exact definition document and the exact managed
configuration revision, enforces the definition's ResourceLibrary scope and
per-run item limit, and persists bounded per-item evidence through the same
read-only analysis chain used by the rest of MediaFlow.
"""

from __future__ import annotations

import json
import posixpath
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.application.attachments import AttachmentDiscovery, AttachmentPlanner
from mediaflow.application.conflict_resolution import ConflictResolver
from mediaflow.application.duplicates import apply_hash_duplicate_detection
from mediaflow.application.manual_organize_preview import (
    PreviewReadOnlyStorage,
    _bounded,
    _fingerprint,
    _fit_json,
    _identity_document,
    _required_capabilities,
)
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.organizer import OrganizePlanner
from mediaflow.application.read_only_storage import (
    ReadOnlyStorageMutationError,
)
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import (
    StrategyConfigurationError,
    StrategyTestRunner,
    strategy_runner_from_configuration,
)
from mediaflow.domain.automation import AutomationTaskDefinition
from mediaflow.domain.automation_task_definition_preview import (
    MAX_AUTOMATION_PREVIEW_ITEMS,
    AutomationPreviewSource,
    AutomationTaskDefinitionPreview,
    AutomationTaskDefinitionPreviewError,
    AutomationTaskDefinitionPreviewItem,
    AutomationTaskDefinitionPreviewItemStatus,
    AutomationTaskDefinitionPreviewStatus,
    AutomationTaskDefinitionPreviewUnavailable,
)
from mediaflow.domain.classification import ClassificationStatus
from mediaflow.domain.configuration_management import ManagedConfigurationStatus
from mediaflow.domain.manual_safety import safe_manual_error
from mediaflow.domain.metadata import (
    MediaQueryType,
    MetadataIdentificationStatus,
)
from mediaflow.domain.organizer import PlanStatus
from mediaflow.domain.recognition import RecognitionStatus
from mediaflow.domain.storage import Storage, StorageEntry, StorageEntryType, StorageError

_MAX_COLLECTION = 64
_MAX_TEXT = 512
_NO_FILE_INDEX_RECORD = object()


def _safe_error(value: object) -> str:
    return safe_manual_error(value, "automation Preview analysis failed")


_SAFE_ERROR = _safe_error


@dataclass(frozen=True)
class _AutomationItemOutcome:
    status: AutomationTaskDefinitionPreviewItemStatus
    plan: dict[str, object] | None = None
    plan_fingerprint: str | None = None
    error: str | None = None
    next_action: str = "inspect the stated blocker, then rerun Preview"


class AutomationTaskDefinitionPreviewService:
    """Create and inspect durable, zero-mutation exact-definition Previews."""

    MAX_ITEMS = MAX_AUTOMATION_PREVIEW_ITEMS

    def __init__(
        self,
        repository,
        configuration_service=None,
        *,
        runtime_resolver: Callable[..., object] | None = None,
        configuration: object | None = None,
        strategy_runner_factory: Callable[..., StrategyTestRunner] | None = None,
        metadata_provider_registry_factory: Callable[..., MetadataProviderRegistry] | None = None,
        providers: MetadataProviderRegistry | None = None,
        storages: Mapping[str, Storage] | None = None,
        file_index=None,
        storage_factory: Callable[..., Mapping[str, Storage]] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        max_items: int = MAX_AUTOMATION_PREVIEW_ITEMS,
    ) -> None:
        if isinstance(max_items, bool) or not 1 <= max_items <= MAX_AUTOMATION_PREVIEW_ITEMS:
            raise ValueError(
                f"automation Preview limit must be between 1 and {MAX_AUTOMATION_PREVIEW_ITEMS}"
            )
        self._repository = repository
        self._configuration_service = configuration_service
        self._runtime_resolver = runtime_resolver
        self._configuration = configuration
        self._strategy_runner_factory = strategy_runner_factory
        self._provider_factory = metadata_provider_registry_factory
        self._providers = providers
        self._storages = dict(storages or {})
        self._file_index = file_index
        self._storage_factory = storage_factory
        self._clock = clock
        self._max_items = max_items
        self._provider_cache: dict[tuple[str, ...], MetadataProviderRegistry] = {}

    @property
    def repository(self):
        return self._repository

    def create(
        self,
        definition_id: str,
        *,
        revision_id: str | None = None,
        actor: str,
    ) -> AutomationTaskDefinitionPreview:
        actor = self._actor(actor)
        revision = self._resolve_revision(revision_id)
        runtime = self._load_runtime(revision)
        if (
            self._configuration_service is None
            and revision_id is not None
            and revision_id != getattr(runtime, "configuration_snapshot_id", None)
        ):
            raise AutomationTaskDefinitionPreviewError(
                "the requested configuration revision does not match the pinned runtime snapshot",
                code="automation_preview_revision_conflict",
                status=409,
                next_action="rerun Preview against the current Active configuration revision",
            )
        definition = self._definition(runtime, definition_id)
        resource_library = self._resource_library(runtime, definition)
        source_storage = self._source_storage(runtime, resource_library)
        scope_root = self._scope_root(resource_library.root_path, definition.source_scope)
        self._assert_scope_directory(source_storage, scope_root, definition)

        discovered = self._discover(
            runtime,
            resource_library,
            definition,
            source_storage,
            scope_root,
        )
        records = discovered["records"]
        counts = discovered["counts"]
        boundary_errors = discovered["errors"]
        counts["permitted"] = counts["selected"]

        preview_id = str(uuid4())
        now = self._clock()
        preview_items: list[AutomationTaskDefinitionPreviewItem] = []
        for position, value in enumerate(records):
            if value["status"] in {
                AutomationTaskDefinitionPreviewItemStatus.EXCLUDED,
                AutomationTaskDefinitionPreviewItemStatus.UNSTABLE,
                AutomationTaskDefinitionPreviewItemStatus.TRUNCATED,
            }:
                preview_items.append(
                    self._minimal_item(
                        preview_id,
                        definition_id,
                        position,
                        value["source"],
                        value["status"],
                        value["next_action"],
                        now,
                    )
                )
                continue
            source = value["source"]
            try:
                item = self._run_item(
                    runtime,
                    definition,
                    resource_library,
                    source,
                    preview_id,
                    definition_id,
                    position,
                    now,
                )
            except AutomationTaskDefinitionPreviewUnavailable as error:
                item = self._failed_item(
                    preview_id,
                    definition_id,
                    position,
                    source,
                    AutomationTaskDefinitionPreviewItemStatus.UNAVAILABLE,
                    _SAFE_ERROR(error),
                    error.next_action,
                    now,
                )
            except AutomationTaskDefinitionPreviewError as error:
                item = self._failed_item(
                    preview_id,
                    definition_id,
                    position,
                    source,
                    AutomationTaskDefinitionPreviewItemStatus.BLOCKED,
                    _SAFE_ERROR(error),
                    error.next_action,
                    now,
                )
            except (StrategyConfigurationError, LookupError, StorageError, ValueError) as error:
                item = self._failed_item(
                    preview_id,
                    definition_id,
                    position,
                    source,
                    AutomationTaskDefinitionPreviewItemStatus.FAILED,
                    _SAFE_ERROR(error),
                    "repair the stated analysis or configuration condition, then rerun Preview",
                    now,
                )
            except (AssertionError, ReadOnlyStorageMutationError):
                raise
            except Exception as error:
                item = self._failed_item(
                    preview_id,
                    definition_id,
                    position,
                    source,
                    AutomationTaskDefinitionPreviewItemStatus.FAILED,
                    _SAFE_ERROR(error),
                    (
                        "inspect the bounded analysis failure, repair the dependency, "
                        "then rerun Preview"
                    ),
                    now,
                )
            preview_items.append(item)

        status = self._aggregate_status(preview_items)
        preview = AutomationTaskDefinitionPreview(
            preview_id=preview_id,
            definition_id=definition.definition_id,
            definition_fingerprint=_fingerprint(definition.document()),
            configuration_revision_id=self._revision_id(runtime, revision),
            configuration_revision_version=self._revision_version(revision),
            configuration_revision_digest=self._revision_digest(runtime, revision),
            configuration_status=self._configuration_status(revision),
            resource_library_id=resource_library.library_id,
            storage_id=resource_library.storage_id,
            source_scope=definition.source_scope,
            run_mode=definition.mode.value,
            effective_item_limit=definition.item_limit,
            counts=counts,
            status=status,
            items=tuple(preview_items),
            actor=actor,
            created_at=now,
            updated_at=now,
            next_action=self._aggregate_next_action(preview_items),
            boundary_errors=tuple(boundary_errors),
            truncated=discovered["records_truncated"]
            or any(
                isinstance(item.plan, dict) and item.plan.get("truncated") is True
                for item in preview_items
            ),
        )
        persisted = self._persist_create(preview)
        return persisted or preview

    create_preview = create
    run = create

    def get(self, preview_id: str) -> AutomationTaskDefinitionPreview:
        value = self._get_raw(preview_id)
        if not value.current:
            return value
        reason = self._stale_reason(value)
        if reason is not None:
            self._invalidate_previews(value.definition_id, reason, self._clock())
            refreshed = self._repository.get_automation_task_definition_preview(preview_id)
            if refreshed is not None:
                return refreshed
            return self._stale_projection(value, reason)
        return value

    def get_readonly(self, preview_id: str) -> AutomationTaskDefinitionPreview:
        value = self._get_raw(preview_id)
        if not value.current:
            return value
        reason = self._stale_reason(value)
        if reason is None:
            return value
        return self._stale_projection(value, reason)

    get_preview = get
    get_manual_preview = get
    get_preview_readonly = get_readonly

    def latest(self, definition_id: str) -> AutomationTaskDefinitionPreview:
        value = self._latest_preview(definition_id)
        if value is None:
            raise AutomationTaskDefinitionPreviewError(
                f"Automation Task Definition {definition_id!r} has no Preview",
                code="automation_preview_not_found",
                status=404,
                next_action="run a Preview for the definition from Automation",
            )
        return self.get(value.preview_id)

    def latest_readonly(self, definition_id: str) -> AutomationTaskDefinitionPreview:
        value = self._latest_preview(definition_id)
        if value is None:
            raise AutomationTaskDefinitionPreviewError(
                f"Automation Task Definition {definition_id!r} has no Preview",
                code="automation_preview_not_found",
                status=404,
                next_action="run a Preview for the definition from Automation",
            )
        return self.get_readonly(value.preview_id)

    def list(
        self, definition_id: str, *, limit: int = 100
    ) -> tuple[AutomationTaskDefinitionPreview, ...]:
        self._definition_id(definition_id)
        limit = self._list_limit(limit)
        values = tuple(
            self._repository.list_automation_task_definition_previews(definition_id, limit=limit)
        )
        return tuple(self.get(value.preview_id) for value in values)

    def list_readonly(
        self, definition_id: str, *, limit: int = 100
    ) -> tuple[AutomationTaskDefinitionPreview, ...]:
        self._definition_id(definition_id)
        limit = self._list_limit(limit)
        values = tuple(
            self._repository.list_automation_task_definition_previews(definition_id, limit=limit)
        )
        return tuple(self.get_readonly(value.preview_id) for value in values)

    def items(
        self,
        preview_id: str,
        *,
        limit: int = 100,
        after: int | None = None,
    ) -> tuple[tuple[AutomationTaskDefinitionPreviewItem, ...], int, int | None]:
        """Bounded deterministic per-item paging for one Preview."""

        if isinstance(limit, bool) or not 1 <= limit <= 500:
            raise AutomationTaskDefinitionPreviewError(
                "automation Preview item limit must be between 1 and 500",
                code="invalid_limit",
            )
        if after is not None and (
            isinstance(after, bool) or not isinstance(after, int) or after < 0
        ):
            raise AutomationTaskDefinitionPreviewError(
                "automation Preview item cursor must be a non-negative position",
                code="invalid_cursor",
            )
        preview = self.get_readonly(preview_id)
        total = len(preview.items)
        start = 0 if after is None else after
        values = preview.items[start : start + limit]
        next_after = start + len(values) if start + len(values) < total else None
        return values, total, next_after

    def invalidate(self, definition_id: str, reason: str) -> None:
        """Mark current Previews for one definition stale after a definition change."""

        self._definition_id(definition_id)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 512:
            raise ValueError("automation Preview stale reason is invalid")
        self._invalidate_previews(definition_id, reason, self._clock())

    invalidate_for_definition = invalidate

    def _invalidate_previews(self, definition_id: str, reason: str, now: datetime) -> None:
        method = getattr(self._repository, "mark_automation_task_definition_previews_stale", None)
        if not callable(method):
            return
        method(definition_id, reason, now)

    def _get_raw(self, preview_id: str) -> AutomationTaskDefinitionPreview:
        if not isinstance(preview_id, str) or not preview_id.strip():
            raise AutomationTaskDefinitionPreviewError(
                "Preview ID is required", code="invalid_preview_id"
            )
        value = self._repository.get_automation_task_definition_preview(preview_id)
        if value is None:
            raise AutomationTaskDefinitionPreviewError(
                f"automation Preview {preview_id!r} was not found",
                code="automation_preview_not_found",
                status=404,
                next_action="run a fresh Preview for the definition from Automation",
            )
        return value

    def _latest_preview(self, definition_id: str) -> AutomationTaskDefinitionPreview | None:
        method = getattr(self._repository, "get_latest_automation_task_definition_preview", None)
        if callable(method):
            return method(definition_id)
        method = getattr(self._repository, "list_automation_task_definition_previews", None)
        if callable(method):
            values = method(definition_id, limit=1)
            return values[0] if values else None
        return None

    @staticmethod
    def _actor(actor: str) -> str:
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 200:
            raise AutomationTaskDefinitionPreviewError(
                "Preview actor is invalid", code="invalid_actor"
            )
        return actor.strip()

    @staticmethod
    def _definition_id(value: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise AutomationTaskDefinitionPreviewError(
                "definition id is required", code="invalid_definition_id"
            )
        return value

    @staticmethod
    def _list_limit(value: int) -> int:
        if isinstance(value, bool) or not 1 <= value <= 500:
            raise AutomationTaskDefinitionPreviewError(
                "automation Preview limit must be between 1 and 500", code="invalid_limit"
            )
        return value

    def _resolve_revision(self, revision_id: str | None):
        if self._configuration_service is None:
            return None
        if revision_id is not None:
            if not isinstance(revision_id, str) or not revision_id.strip():
                raise AutomationTaskDefinitionPreviewError(
                    "configuration revisionId is required", code="invalid_revision"
                )
            try:
                revision = self._configuration_service.require(revision_id)
            except LookupError as error:
                raise AutomationTaskDefinitionPreviewError(
                    f"configuration revision {revision_id!r} was not found",
                    code="automation_preview_revision_not_found",
                    status=404,
                    next_action="reload the Automation list and choose an existing revision",
                ) from error
        else:
            revision = self._configuration_service.active()
            if revision is None:
                raise AutomationTaskDefinitionPreviewUnavailable(
                    "no Active managed configuration revision is available",
                    details={"revisionId": None},
                )
            if revision.status is not ManagedConfigurationStatus.ACTIVE:
                raise AutomationTaskDefinitionPreviewUnavailable(
                    "the current Active managed configuration revision is not published",
                    details={"revisionId": revision.revision_id},
                )
        self._configuration_service.verify_integrity(revision)
        return revision

    def _load_runtime(self, revision):
        if self._runtime_resolver is not None:
            try:
                try:
                    runtime = self._runtime_resolver(
                        revision.revision_id if revision is not None else None,
                        revision.digest if revision is not None else None,
                    )
                except TypeError:
                    runtime = self._runtime_resolver()
            except AutomationTaskDefinitionPreviewError:
                raise
            except Exception as error:
                raise AutomationTaskDefinitionPreviewUnavailable(
                    "the pinned configuration snapshot is unavailable or unreadable",
                    details={"reason": type(error).__name__},
                ) from error
        elif self._configuration_service is not None:
            try:
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
                    snapshot_id=revision.revision_id,
                    digest=revision.digest,
                )
            except AutomationTaskDefinitionPreviewError:
                raise
            except Exception as error:
                raise AutomationTaskDefinitionPreviewUnavailable(
                    "the pinned configuration snapshot is unavailable or unreadable",
                    details={"revisionId": revision.revision_id, "reason": type(error).__name__},
                ) from error
        elif self._configuration is not None:
            runtime = self._configuration
        else:
            raise AutomationTaskDefinitionPreviewUnavailable(
                "automation Preview runtime configuration is unavailable"
            )
        if isinstance(runtime, Mapping) or not hasattr(runtime, "strategy"):
            raise AutomationTaskDefinitionPreviewUnavailable(
                "automation Preview requires a normalized runtime configuration"
            )
        if self._configuration_service is None:
            authority = getattr(runtime, "configuration_authority", "JSON_BOOTSTRAP")
            runtime_id = getattr(runtime, "configuration_snapshot_id", None)
            if authority != "MANAGED" or not runtime_id:
                raise AutomationTaskDefinitionPreviewUnavailable(
                    "automation Preview requires a managed configuration snapshot"
                )
        return runtime

    def _definition(self, runtime, definition_id: str) -> AutomationTaskDefinition:
        definition_id = self._definition_id(definition_id)
        definitions = tuple(getattr(runtime, "automation_task_definitions", ()))
        value = next((item for item in definitions if item.definition_id == definition_id), None)
        if value is None:
            raise AutomationTaskDefinitionPreviewError(
                f"automationTaskDefinitions {definition_id!r} was not found",
                code="automation_preview_definition_not_found",
                status=404,
                next_action="reload the Automation list and select an existing definition",
            )
        return value

    @staticmethod
    def _resource_library(runtime, definition: AutomationTaskDefinition):
        value = next(
            (
                item
                for item in getattr(runtime, "resource_libraries", ())
                if item.library_id == definition.resource_library_id
            ),
            None,
        )
        if value is None or value.enabled is not True:
            raise AutomationTaskDefinitionPreviewError(
                "the definition references a missing or disabled ResourceLibrary",
                code="automation_preview_resource_library_unavailable",
                next_action=(
                    "repair or enable the referenced ResourceLibrary under the pinned "
                    "configuration, then rerun Preview"
                ),
                details={"resourceLibraryId": definition.resource_library_id},
            )
        return value

    def _source_storage(self, runtime, resource_library):
        storages = self._create_storages(runtime, {resource_library.storage_id})
        return self._guarded_storage(storages, resource_library.storage_id)

    @staticmethod
    def _scope_root(root_path: str, source_scope: str | None) -> str:
        if not source_scope:
            return root_path or ""
        return posixpath.join(root_path, source_scope) if root_path else source_scope

    def _assert_scope_directory(
        self,
        storage: PreviewReadOnlyStorage,
        scope_root: str,
        definition: AutomationTaskDefinition,
    ) -> None:
        try:
            entry = storage.stat(scope_root)
        except StorageError as error:
            raise AutomationTaskDefinitionPreviewError(
                "the definition source scope root is missing or inaccessible",
                code="automation_preview_scope_unavailable",
                next_action=(
                    "repair the ResourceLibrary root or normalized sourceScope, then rerun Preview"
                ),
                details={
                    "resourceLibraryId": definition.resource_library_id,
                    "sourceScope": definition.source_scope,
                    "reason": str(error.code.value),
                },
            ) from error
        if not entry.is_directory:
            raise AutomationTaskDefinitionPreviewError(
                "the definition source scope root is not a directory",
                code="automation_preview_scope_invalid",
                next_action="correct the definition sourceScope, then rerun Preview",
            )

    def _discover(
        self,
        runtime,
        resource_library,
        definition: AutomationTaskDefinition,
        storage: PreviewReadOnlyStorage,
        scope_root: str,
    ) -> dict[str, object]:
        counts = {
            "discovered": 0,
            "selected": 0,
            "permitted": 0,
            "excludedIgnored": 0,
            "unstable": 0,
            "truncatedByLimit": 0,
        }
        records: list[dict[str, object]] = []
        selected: list[AutomationPreviewSource] = []
        errors: list[str] = []
        records_truncated = False
        ready_seen = 0
        now = self._clock()
        pending: deque[tuple[str, int]] = deque([(scope_root, 0)])
        limit = definition.item_limit

        def add_record(
            entry: StorageEntry,
            status: AutomationTaskDefinitionPreviewItemStatus,
            next_action: str,
            stability: str,
            scan_status: str,
        ) -> None:
            nonlocal records_truncated
            if len(records) >= self._max_items:
                records_truncated = True
                return
            relative = StorageScanner._relative(entry.path, scope_root)
            extension = (
                entry.name.rsplit(".", 1)[-1].lower()
                if entry.entry_type is StorageEntryType.FILE and "." in entry.name
                else ""
            )
            records.append(
                {
                    "source": AutomationPreviewSource(
                        storage.storage_id,
                        resource_library.library_id,
                        entry.path,
                        entry.name,
                        extension,
                        entry.size,
                        entry.modified_at,
                        stability,
                        scan_status,
                    ),
                    "status": status,
                    "next_action": next_action,
                    "relative": relative,
                    "entry": entry,
                }
            )

        while pending:
            directory, depth = pending.popleft()
            try:
                entries = tuple(
                    sorted(
                        storage.list(directory),
                        key=lambda item: item.name,
                    )
                )
            except StorageError as error:
                errors.append(
                    _SAFE_ERROR(
                        f"Storage listing failed for {_bounded(directory, 256)}: {error.code.value}"
                    )
                )
                if len(errors) >= 16:
                    break
                continue
            for entry in entries:
                relative = StorageScanner._relative(entry.path, scope_root)
                if entry.entry_type is StorageEntryType.DIRECTORY:
                    if StorageScanner._excluded(
                        resource_library.exclude_rules, relative, entry.name, "", True
                    ):
                        continue
                    if not StorageScanner._directory_may_match(
                        resource_library.include_rules, relative
                    ):
                        continue
                    if resource_library.max_depth is None or depth < resource_library.max_depth:
                        pending.append((entry.path, depth + 1))
                    continue
                counts["discovered"] += 1
                if entry.entry_type is not StorageEntryType.FILE:
                    counts["excludedIgnored"] += 1
                    add_record(
                        entry,
                        AutomationTaskDefinitionPreviewItemStatus.EXCLUDED,
                        "non-file entries are outside the automation source scope",
                        "not_applicable",
                        "excluded",
                    )
                    continue
                extension = entry.name.rsplit(".", 1)[-1].lower() if "." in entry.name else ""
                ignored = extension not in resource_library.file_extensions
                ignored = ignored or StorageScanner._excluded(
                    resource_library.exclude_rules, relative, entry.name, extension, False
                )
                ignored = ignored or not StorageScanner._included(
                    resource_library.include_rules, relative, entry.name, extension
                )
                if ignored:
                    counts["excludedIgnored"] += 1
                    add_record(
                        entry,
                        AutomationTaskDefinitionPreviewItemStatus.EXCLUDED,
                        "file is excluded by extension or ResourceLibrary rules",
                        "not_applicable",
                        "excluded",
                    )
                    continue
                stable, stability = self._stable(resource_library, entry, now)
                if not stable:
                    counts["unstable"] += 1
                    add_record(
                        entry,
                        AutomationTaskDefinitionPreviewItemStatus.UNSTABLE,
                        self._stability_next_action(stability),
                        stability,
                        "unstable",
                    )
                    continue
                if ready_seen < limit:
                    counts["selected"] += 1
                    source = AutomationPreviewSource(
                        storage.storage_id,
                        resource_library.library_id,
                        entry.path,
                        entry.name,
                        extension,
                        entry.size,
                        entry.modified_at,
                        stability,
                        "ready",
                    )
                    add_record(
                        entry,
                        AutomationTaskDefinitionPreviewItemStatus.PREVIEWED,
                        "",
                        stability,
                        "ready",
                    )
                    selected.append(source)
                else:
                    counts["truncatedByLimit"] += 1
                    add_record(
                        entry,
                        AutomationTaskDefinitionPreviewItemStatus.TRUNCATED,
                        (
                            "item is beyond the definition itemLimit; raise the limit or "
                            "narrow sourceScope, then rerun Preview"
                        ),
                        stability,
                        "truncated",
                    )
                ready_seen += 1
        return {
            "records": records,
            "counts": counts,
            "selected": selected,
            "errors": errors,
            "records_truncated": records_truncated,
        }

    def _stable(
        self,
        resource_library,
        entry: StorageEntry,
        now: datetime,
        *,
        previous=_NO_FILE_INDEX_RECORD,
    ) -> tuple[bool, str]:
        policy = resource_library.stability_policy
        age = max(0.0, (now - entry.modified_at).total_seconds())
        required_age = max(policy.minimum_age_seconds, policy.modified_threshold_seconds)
        if policy.stable_size_duration_seconds > 0:
            if previous is _NO_FILE_INDEX_RECORD:
                if self._file_index is None:
                    return False, "unstable_no_history"
                find_by_path = getattr(self._file_index, "find_by_path", None)
                if not callable(find_by_path):
                    return False, "unstable_history_unavailable"
                try:
                    previous = find_by_path(
                        resource_library.storage_id,
                        resource_library.library_id,
                        entry.path,
                    )
                except Exception:
                    return False, "unstable_history_unavailable"
            if previous is None:
                return False, "unstable_no_history"
            if previous.size != entry.size or previous.modified_at != entry.modified_at:
                return False, "unstable_changed"
            stable_since = previous.stable_since or previous.last_seen_at
            stable_duration = (now - stable_since).total_seconds()
            if stable_duration < policy.stable_size_duration_seconds:
                return False, "unstable_size"
        return age >= required_age, "stable" if age >= required_age else "unstable_age"

    @staticmethod
    def _stability_next_action(stability: str) -> str:
        if stability == "unstable_no_history":
            return (
                "run a ResourceLibrary scan to record this file, wait for the configured "
                "stable-size duration, then rerun Preview"
            )
        if stability == "unstable_history_unavailable":
            return (
                "restore durable FileIndex history, run a ResourceLibrary scan, then rerun Preview"
            )
        if stability == "unstable_changed":
            return (
                "run a ResourceLibrary scan after the file stops changing, wait for the "
                "configured stable-size duration, then rerun Preview"
            )
        if stability == "unstable_size":
            return "wait for the configured stable-size duration, then rerun Preview"
        return "wait until the file meets the configured stability policy, then rerun Preview"

    def _run_item(
        self,
        runtime,
        definition: AutomationTaskDefinition,
        resource_library,
        source: AutomationPreviewSource,
        preview_id: str,
        definition_id: str,
        position: int,
        now: datetime,
    ) -> AutomationTaskDefinitionPreviewItem:
        outcome = self._analyze(runtime, resource_library, source)
        if outcome.status is AutomationTaskDefinitionPreviewItemStatus.PREVIEWED:
            next_action = "inspect this exact zero-mutation plan; this evidence grants no authority"
        else:
            next_action = outcome.next_action
        plan = outcome.plan if isinstance(outcome.plan, dict) else {}

        def pget(*keys: str) -> object:
            value: object = plan
            for key in keys:
                if not isinstance(value, dict):
                    return None
                value = value.get(key)
            return value

        return AutomationTaskDefinitionPreviewItem(
            preview_item_id=str(uuid4()),
            preview_id=preview_id,
            definition_id=definition_id,
            position=position,
            source=source,
            source_fingerprint=_fingerprint(source.document()),
            status=outcome.status,
            next_action=next_action,
            recognition_status=pget("analysis", "recognition", "status"),
            recognition_rule_id=pget("analysis", "recognition", "ruleId"),
            recognition_type_id=pget("recognitionType"),
            recognition_type_policy_id=pget("policies", "recognitionTypePolicyId"),
            metadata_policy_id=pget("policies", "metadataPolicyId"),
            naming_policy_id=pget("policies", "namingPolicyId"),
            classification_policy_id=pget("policies", "classificationPolicyId"),
            organize_policy_id=pget("policies", "organizePolicyId"),
            metadata_provider=pget("mediaIdentity", "provider"),
            metadata_provider_id=pget("mediaIdentity", "providerId"),
            media_type=pget("mediaIdentity", "mediaType"),
            metadata_status=pget("analysis", "metadata", "status"),
            metadata_title=pget("mediaIdentity", "title"),
            metadata_year=pget("mediaIdentity", "year"),
            naming_directory=pget("analysis", "naming", "directory"),
            naming_filename=pget("analysis", "naming", "filename"),
            classification_media_library_id=pget("classification", "mediaLibraryId"),
            classification_relative_path=pget("classification", "relativePath"),
            destination_storage_id=pget("destination", "storageId"),
            destination_path=pget("destination", "path"),
            operation=pget("operation"),
            attachments_json=json.dumps(
                pget("attachments") or [], ensure_ascii=False, sort_keys=True
            ),
            required_capabilities_json=json.dumps(
                (pget("capabilities") or {}).get("required", []),
                ensure_ascii=False,
                sort_keys=True,
            ),
            declared_capabilities_json=json.dumps(
                (pget("capabilities") or {}).get("declared", []),
                ensure_ascii=False,
                sort_keys=True,
            ),
            capability_verdict=(pget("capabilities") or {}).get("verdict"),
            conflict_strategy=pget("conflictStrategy"),
            conflicts_json=json.dumps(pget("conflicts") or [], ensure_ascii=False, sort_keys=True),
            warnings_json=json.dumps(pget("warnings") or [], ensure_ascii=False, sort_keys=True),
            plan_fingerprint=outcome.plan_fingerprint,
            plan=outcome.plan,
            blocker=outcome.error,
            zero_mutation=True,
            current=True,
            created_at=now,
            updated_at=now,
        )

    def _analyze(self, runtime, resource_library, source: AutomationPreviewSource):
        configured_storages = self._create_storages(runtime, {resource_library.storage_id})
        source_storage = self._guarded_storage(configured_storages, resource_library.storage_id)
        recognition_runner = self._runner(runtime, None, source_storage, configured_storages)
        recognition_only = recognition_runner.run_path(
            source.path,
            live_metadata=False,
            show_naming=False,
            show_classification=False,
            resource_library_id=resource_library.library_id,
            storage_id=resource_library.storage_id,
            storage_path=source.path,
            source_storage=source_storage,
        )
        if recognition_only.recognition.status is not RecognitionStatus.MATCHED:
            return _AutomationItemOutcome(
                AutomationTaskDefinitionPreviewItemStatus.BLOCKED,
                error="Recognition did not match a RecognitionRule for this source",
                next_action=(
                    "inspect the Recognition explanation or extend the configured rules, "
                    "then rerun Preview"
                ),
            )
        type_policy = next(
            (
                value
                for value in runtime.strategy.recognition_type_policies
                if value.recognition_type_id == recognition_only.recognition.recognition_type_id
            ),
            None,
        )
        if type_policy is None or not type_policy.enabled:
            return _AutomationItemOutcome(
                AutomationTaskDefinitionPreviewItemStatus.BLOCKED,
                error="the matched RecognitionTypePolicy is unavailable or disabled",
                next_action=("repair the pinned RecognitionTypePolicy, then rerun Preview"),
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
            return _AutomationItemOutcome(
                AutomationTaskDefinitionPreviewItemStatus.BLOCKED,
                error="the pinned MetadataPolicy is unavailable or disabled",
                next_action="repair the pinned MetadataPolicy, then rerun Preview",
            )
        providers = (
            self._provider_registry((metadata_policy.provider_id,))
            if metadata_policy.query_type is not MediaQueryType.NONE
            else None
        )
        runner = self._runner(runtime, providers, source_storage, configured_storages)
        strategy = runner.run_path(
            source.path,
            live_metadata=providers is not None,
            show_naming=True,
            show_classification=True,
            resource_library_id=resource_library.library_id,
            storage_id=resource_library.storage_id,
            storage_path=source.path,
            source_storage=source_storage,
        )
        if strategy.recognition.status is not RecognitionStatus.MATCHED:
            return _AutomationItemOutcome(
                AutomationTaskDefinitionPreviewItemStatus.BLOCKED,
                error="Recognition did not match a RecognitionRule for this source",
                next_action="inspect the Recognition explanation, then rerun Preview",
            )
        metadata = strategy.metadata
        if metadata is None or metadata.identity is None:
            status = getattr(metadata, "status", None)
            if status is MetadataIdentificationStatus.PROVIDER_ERROR:
                return _AutomationItemOutcome(
                    AutomationTaskDefinitionPreviewItemStatus.UNAVAILABLE,
                    error=_SAFE_ERROR(
                        getattr(metadata, "error", None) or "metadata provider unavailable"
                    ),
                    next_action=(
                        "inspect the configured Metadata Provider availability, then "
                        "explicitly rerun Preview"
                    ),
                )
            return _AutomationItemOutcome(
                AutomationTaskDefinitionPreviewItemStatus.BLOCKED,
                error="metadata identity is not ready for exact planning",
                next_action="open or resolve the linked Metadata review, then rerun Preview",
            )
        if strategy.naming is None:
            return _AutomationItemOutcome(
                AutomationTaskDefinitionPreviewItemStatus.BLOCKED,
                error=strategy.naming_error or "NamingPolicy did not produce a result",
                next_action="repair the pinned NamingPolicy or metadata choice, then rerun Preview",
            )
        if (
            strategy.classification is None
            or strategy.classification.status is not ClassificationStatus.CLASSIFIED
        ):
            return _AutomationItemOutcome(
                AutomationTaskDefinitionPreviewItemStatus.BLOCKED,
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
            return _AutomationItemOutcome(
                AutomationTaskDefinitionPreviewItemStatus.UNAVAILABLE,
                error="classified MediaLibrary is unavailable under the pinned snapshot",
                next_action=(
                    "repair the pinned MediaLibrary/Storage configuration, then rerun Preview"
                ),
            )
        configured_storages = self._create_storages(
            runtime, {resource_library.storage_id, media_library.storage_id}
        )
        source_storage = self._guarded_storage(configured_storages, resource_library.storage_id)
        target_storage = self._guarded_storage(configured_storages, media_library.storage_id)
        plan = self._plan(
            strategy,
            type_policy,
            media_library,
            source_storage,
            target_storage,
            source,
            resource_library.root_path,
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
            plan.source_location or _StorageLocation(resource_library.storage_id, source.path),
            type_policy.organize_policy.attachments,
        )
        if len(attachments.attachments) > _MAX_COLLECTION:
            attachments = type(attachments)(
                attachments.primary, attachments.attachments[:_MAX_COLLECTION]
            )
            truncated = True
        plan = AttachmentPlanner().plan(plan, attachments, target_storage)
        plan = self._resolve_conflicts(plan, type_policy, target_storage)
        plan_document = self._plan_document(
            strategy, plan, source, type_policy, source_storage, target_storage
        )
        if truncated:
            plan_document["bounds"] = {
                "truncated": True,
                "reason": "attachment collection exceeded the Preview bound",
            }
        plan_document = _fit_json(plan_document)
        plan_fingerprint = _fingerprint(plan_document)
        capability = plan_document.get("capabilities") or {}
        blocked = (
            bool(plan.conflicts)
            or plan.status is PlanStatus.INVALID
            or capability.get("verdict") == "capability_gap"
        )
        if blocked:
            return _AutomationItemOutcome(
                AutomationTaskDefinitionPreviewItemStatus.BLOCKED,
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
            )
        return _AutomationItemOutcome(
            AutomationTaskDefinitionPreviewItemStatus.PREVIEWED,
            plan_document,
            plan_fingerprint,
            next_action=(
                "inspect this exact zero-mutation plan; this evidence grants no execution authority"
            ),
        )

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
            raise AutomationTaskDefinitionPreviewUnavailable(
                "a configured Storage required by the exact Preview is unavailable",
                details={"storageIds": missing},
            )
        return result

    @staticmethod
    def _guarded_storage(storages: Mapping[str, Storage], storage_id: str):
        try:
            storage = storages[storage_id]
        except KeyError as error:
            raise AutomationTaskDefinitionPreviewUnavailable(
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
            raise AutomationTaskDefinitionPreviewUnavailable(
                "the Metadata Provider authority required by this Preview is unavailable",
                details={"providerIds": list(requested)},
            )
        try:
            registry = self._provider_factory(requested)
        except AutomationTaskDefinitionPreviewError:
            raise
        except Exception as error:
            raise AutomationTaskDefinitionPreviewUnavailable(
                "the Metadata Provider authority required by this Preview is unavailable",
                details={"providerIds": list(requested), "reason": type(error).__name__},
            ) from error
        if not isinstance(registry, MetadataProviderRegistry):
            raise AutomationTaskDefinitionPreviewUnavailable(
                "Metadata Provider registry is invalid"
            )
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

    @staticmethod
    def _plan(
        strategy,
        type_policy,
        media_library,
        source_storage,
        target_storage,
        source: AutomationPreviewSource,
        source_library_root,
    ) -> object:
        return OrganizePlanner().plan(
            source_storage_id=source.storage_id,
            source=source.path,
            source_storage_path=source.path,
            source_library_root=source_library_root,
            recognition=strategy.recognition,
            type_policy=type_policy,
            media_library=media_library,
            naming=strategy.naming,
            classification=strategy.classification,
            media_identity=strategy.metadata.identity,
            target_storage=target_storage,
        )

    def _resolve_conflicts(self, plan, type_policy, target_storage):
        if not plan.conflicts:
            return plan
        resolved = ConflictResolver().apply_configured(
            plan, type_policy.organize_policy, target_storage
        )
        return resolved or plan

    def _plan_document(
        self, strategy, plan, source, type_policy, source_storage, target_storage
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
        conflicts = [
            {
                "type": value.type.value,
                "source": _bounded(value.source),
                "destination": _bounded(value.destination),
                "details": _bounded(value.details),
            }
            for value in plan.conflicts[:_MAX_COLLECTION]
        ]
        return {
            "source": source.document(),
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
            "classification": {
                "mediaLibraryId": _bounded(strategy.classification.media_library_id),
                "relativePath": _bounded(strategy.classification.relative_path),
                "policyId": _bounded(strategy.classification.policy_id),
                "status": strategy.classification.status.value,
            },
            "destination": destination,
            "operation": plan.operation.value,
            "operationPolicy": type_policy.organize_policy.operation.value,
            "conflictStrategy": type_policy.organize_policy.conflict_strategy.value,
            "attachments": attachment_documents,
            "executionPlan": self._execution_plan_document(plan, exact_attachment_documents),
            "capabilities": self._capabilities(plan, source_storage, target_storage),
            "conflicts": conflicts,
            "warnings": [_bounded(value) for value in plan.warnings[:_MAX_COLLECTION]],
            "planStatus": plan.status.value,
            "planId": plan.plan_id,
            "zeroMutation": True,
            "executionState": "not_available_in_this_task",
            "bounded": True,
            "deterministic": True,
        }

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
    def _capabilities(plan, source_storage, target_storage) -> dict[str, object]:
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

    @staticmethod
    def _analysis_document(strategy) -> dict[str, object]:
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
            "metadata": AutomationTaskDefinitionPreviewService._metadata_document(metadata),
            "naming": AutomationTaskDefinitionPreviewService._naming_document(
                strategy.naming, strategy.naming_error
            ),
            "classification": AutomationTaskDefinitionPreviewService._classification_document(
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
    def _minimal_item(
        preview_id,
        definition_id,
        position,
        source,
        status,
        next_action,
        now,
    ) -> AutomationTaskDefinitionPreviewItem:
        return AutomationTaskDefinitionPreviewItem(
            preview_item_id=str(uuid4()),
            preview_id=preview_id,
            definition_id=definition_id,
            position=position,
            source=source,
            source_fingerprint=_fingerprint(source.document()),
            status=status,
            next_action=next_action,
            zero_mutation=True,
            current=True,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _failed_item(
        preview_id,
        definition_id,
        position,
        source,
        status,
        error,
        next_action,
        now,
    ) -> AutomationTaskDefinitionPreviewItem:
        return AutomationTaskDefinitionPreviewItem(
            preview_item_id=str(uuid4()),
            preview_id=preview_id,
            definition_id=definition_id,
            position=position,
            source=source,
            source_fingerprint=_fingerprint(source.document()),
            status=status,
            next_action=next_action,
            blocker=_SAFE_ERROR(error),
            zero_mutation=True,
            current=True,
            created_at=now,
            updated_at=now,
        )

    def _persist_create(self, preview):
        method = getattr(self._repository, "create_automation_task_definition_preview", None)
        if not callable(method):
            raise AutomationTaskDefinitionPreviewUnavailable(
                "automation Preview persistence is unavailable"
            )
        return method(preview, preview.items)

    @staticmethod
    def _revision_id(runtime, revision) -> str:
        if revision is not None:
            return revision.revision_id
        value = getattr(runtime, "configuration_snapshot_id", None)
        if not value:
            raise AutomationTaskDefinitionPreviewUnavailable(
                "automation Preview configuration snapshot identity is unavailable"
            )
        return value

    @staticmethod
    def _revision_version(revision) -> int:
        if revision is not None:
            return revision.version
        return 1

    @staticmethod
    def _revision_digest(runtime, revision) -> str:
        if revision is not None:
            return revision.digest
        value = getattr(runtime, "configuration_snapshot_digest", None)
        if not value:
            raise AutomationTaskDefinitionPreviewUnavailable(
                "automation Preview configuration snapshot digest is unavailable"
            )
        return value

    @staticmethod
    def _configuration_status(revision) -> str:
        if revision is None:
            return "MANAGED"
        return revision.status.value

    def _stale_reason(self, preview: AutomationTaskDefinitionPreview) -> str | None:
        runtime = None
        if self._configuration_service is not None:
            try:
                revision = self._configuration_service.require(preview.configuration_revision_id)
                self._configuration_service.verify_integrity(revision)
            except Exception:
                return "the pinned configuration revision is unavailable or unreadable"
            if revision.digest != preview.configuration_revision_digest:
                return "the pinned configuration revision changed"
            if preview.configuration_status == ManagedConfigurationStatus.ACTIVE.value:
                try:
                    active = self._configuration_service.active()
                except Exception:
                    active = None
                if active is None or active.revision_id != preview.configuration_revision_id:
                    return (
                        "the pinned configuration revision is no longer the current Active revision"
                    )
            try:
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
                    snapshot_id=revision.revision_id,
                    digest=revision.digest,
                )
            except Exception:
                return "the pinned configuration revision cannot be reloaded"
        elif self._configuration is not None:
            runtime = self._configuration
            if (
                getattr(runtime, "configuration_snapshot_id", None)
                != preview.configuration_revision_id
                or getattr(runtime, "configuration_snapshot_digest", None)
                != preview.configuration_revision_digest
            ):
                return "the pinned configuration revision changed"
        else:
            return "automation Preview runtime configuration is unavailable"
        current_definition = next(
            (
                item
                for item in getattr(runtime, "automation_task_definitions", ())
                if item.definition_id == preview.definition_id
            ),
            None,
        )
        if (
            current_definition is None
            or _fingerprint(current_definition.document()) != preview.definition_fingerprint
        ):
            return "the pinned Automation Task Definition changed or no longer exists"
        resource_library = next(
            (
                item
                for item in getattr(runtime, "resource_libraries", ())
                if item.library_id == preview.resource_library_id
            ),
            None,
        )
        if resource_library is None or resource_library.storage_id != preview.storage_id:
            return "the pinned ResourceLibrary or Storage is unavailable"
        return self._indexed_source_stale_reason(preview, resource_library)

    def _indexed_source_stale_reason(self, preview, resource_library) -> str | None:
        """Compare recorded source facts without contacting the configured Storage."""

        if self._file_index is None:
            return None
        find_by_path = getattr(self._file_index, "find_by_path", None)
        if not callable(find_by_path):
            return "the durable FileIndex required to verify source facts is unavailable"
        now = self._clock()
        for item in preview.items:
            if item.source.scan_status == "excluded":
                continue
            try:
                record = find_by_path(
                    item.source.storage_id,
                    item.source.resource_library_id,
                    item.source.path,
                )
            except Exception:
                return "the durable FileIndex required to verify source facts is unavailable"
            if record is None:
                continue
            if (
                record.filename != item.source.filename
                or record.extension != item.source.extension
                or record.size != item.source.size
                or record.modified_at != item.source.modified_at
            ):
                return "a plan-affecting source fact changed"
            if getattr(record.scan_status, "value", record.scan_status) == "missing":
                return "a plan-affecting source fact changed"
            _, current_stability = self._stable(
                resource_library,
                StorageEntry(
                    item.source.filename,
                    item.source.path,
                    StorageEntryType.FILE,
                    item.source.size,
                    item.source.modified_at,
                ),
                now,
                previous=record,
            )
            if current_stability != item.source.stability:
                return "a plan-affecting source fact changed"
        return None

    @staticmethod
    def _stale_projection(
        value: AutomationTaskDefinitionPreview, reason: str
    ) -> AutomationTaskDefinitionPreview:
        from dataclasses import replace

        return replace(
            value,
            status=AutomationTaskDefinitionPreviewStatus.STALE,
            current=False,
            stale_reason=reason,
            next_action="request a fresh Preview after resolving the stated stale reason",
        )

    @staticmethod
    def _aggregate_status(
        items: Sequence[AutomationTaskDefinitionPreviewItem],
    ) -> AutomationTaskDefinitionPreviewStatus:
        if not items:
            # An empty current scope is a valid zero-mutation observation. It
            # grants no item authority, but it must not block the exact
            # definition grant itself.
            return AutomationTaskDefinitionPreviewStatus.PREVIEWED
        statuses = {item.status for item in items}
        benign = {
            AutomationTaskDefinitionPreviewItemStatus.PREVIEWED,
            AutomationTaskDefinitionPreviewItemStatus.EXCLUDED,
            AutomationTaskDefinitionPreviewItemStatus.UNSTABLE,
            AutomationTaskDefinitionPreviewItemStatus.TRUNCATED,
        }
        if statuses.issubset(benign) and (
            AutomationTaskDefinitionPreviewItemStatus.PREVIEWED in statuses
        ):
            return AutomationTaskDefinitionPreviewStatus.PREVIEWED
        if statuses.issubset(benign):
            return AutomationTaskDefinitionPreviewStatus.PREVIEWED
        if statuses == {AutomationTaskDefinitionPreviewItemStatus.UNAVAILABLE}:
            return AutomationTaskDefinitionPreviewStatus.UNAVAILABLE
        if statuses == {AutomationTaskDefinitionPreviewItemStatus.FAILED}:
            return AutomationTaskDefinitionPreviewStatus.FAILED
        if statuses.intersection(
            {
                AutomationTaskDefinitionPreviewItemStatus.UNAVAILABLE,
                AutomationTaskDefinitionPreviewItemStatus.FAILED,
                AutomationTaskDefinitionPreviewItemStatus.BLOCKED,
            }
        ):
            return (
                AutomationTaskDefinitionPreviewStatus.PARTIAL
                if AutomationTaskDefinitionPreviewItemStatus.PREVIEWED in statuses
                else AutomationTaskDefinitionPreviewStatus.BLOCKED
            )
        return AutomationTaskDefinitionPreviewStatus.PARTIAL

    @staticmethod
    def _aggregate_next_action(
        items: Sequence[AutomationTaskDefinitionPreviewItem],
    ) -> str:
        if not items:
            return (
                "no media items were discovered under the definition scope; adjust the "
                "ResourceLibrary or sourceScope, then rerun Preview"
            )
        if all(
            item.status is AutomationTaskDefinitionPreviewItemStatus.PREVIEWED for item in items
        ):
            return (
                "inspect each exact zero-mutation plan; this evidence grants no execution authority"
            )
        return "inspect each item; resolve its stated blocker or request a fresh Preview"


class _StorageLocation:
    """Tiny compatibility holder matching StorageLocation shape used by attachments."""

    def __init__(self, storage_id: str, path: str) -> None:
        self.storage_id = storage_id
        self.path = path


AutomationTaskDefinitionPreviewServiceAlias = AutomationTaskDefinitionPreviewService


__all__ = ["AutomationTaskDefinitionPreviewService"]
