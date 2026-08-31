from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.configuration_management import RuntimeSnapshotUnavailable
from mediaflow.domain.manual_organize import (
    MAX_MANUAL_INTENT_ITEMS,
    ManualChoice,
    ManualConfigurationSnapshot,
    ManualIntentAudit,
    ManualIntentConflict,
    ManualIntentError,
    ManualIntentItem,
    ManualIntentItemStatus,
    ManualIntentStatus,
    ManualIntentUnavailable,
    ManualMetadataReference,
    ManualOrganizeIntent,
    ManualPolicyOption,
    ManualRecognitionOption,
    ManualSourceIdentity,
)


class ManualOrganizeIntentService:
    """Admit and persist the side-effect-free manual-organize intent boundary.

    This service deliberately consumes only indexed FileIndex records and a
    normalized configuration snapshot.  It never constructs a Storage adapter,
    calls a Metadata provider, creates a Task/Plan, or grants execution
    authority.
    """

    MAX_ITEMS = MAX_MANUAL_INTENT_ITEMS

    def __init__(
        self,
        repository,
        file_catalog,
        configuration_service=None,
        *,
        configuration_resolver: Callable[[], object] | None = None,
        configuration: object | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        max_items: int = MAX_MANUAL_INTENT_ITEMS,
    ) -> None:
        if isinstance(max_items, bool) or not 1 <= max_items <= MAX_MANUAL_INTENT_ITEMS:
            raise ValueError(f"manual intent limit must be between 1 and {MAX_MANUAL_INTENT_ITEMS}")
        self._repository = repository
        self._file_catalog = file_catalog
        self._configuration_service = configuration_service
        self._configuration_resolver = configuration_resolver
        self._configuration = configuration
        self._clock = clock
        self._max_items = max_items

    @property
    def repository(self):
        return self._repository

    def create(self, file_ids: Iterable[str], *, actor: str) -> ManualOrganizeIntent:
        actor = self._actor(actor)
        ids = self._selection(file_ids)
        records = []
        identities: set[tuple[str, str, str]] = set()
        for file_id in ids:
            record = self._resolve_file(file_id)
            self._assert_selectable(record)
            identity = (record.storage_id, record.resource_library_id, record.path)
            if identity in identities:
                raise ManualIntentError(
                    "the selected files contain a duplicate source identity",
                    code="duplicate_source",
                    next_action="remove the duplicate and resubmit the bounded selection",
                    details={"fileId": record.file_id},
                )
            identities.add(identity)
            records.append(record)

        snapshot = self._active_snapshot()
        now = self._clock()
        intent_id = str(uuid4())
        items: list[ManualIntentItem] = []
        for position, record in enumerate(records):
            choice = self._default_choice(record, snapshot)
            self._validate_choice(choice, snapshot, record)
            try:
                source = ManualSourceIdentity.from_file_record(record)
            except ValueError as error:
                raise ManualIntentError(
                    "selected FileIndex source identity is malformed",
                    code="source_invalid",
                    next_action="repair the indexed source identity, then reload Files",
                ) from error
            items.append(
                ManualIntentItem(
                    str(uuid4()),
                    intent_id,
                    position,
                    source,
                    choice,
                    ManualIntentItemStatus.READY,
                    None,
                    1,
                    now,
                    now,
                )
            )
        intent = ManualOrganizeIntent(
            intent_id,
            actor,
            snapshot.snapshot_id,
            snapshot.digest,
            ManualIntentStatus.OPEN,
            1,
            now,
            now,
            tuple(items),
            snapshot,
            "continue to a later manual Preview",
            None,
            (),
        )
        audit = ManualIntentAudit(
            str(uuid4()),
            intent_id,
            None,
            actor,
            "created",
            {},
            {
                "intentId": intent_id,
                "configurationSnapshotId": snapshot.snapshot_id,
                "configurationSnapshotDigest": snapshot.digest,
                "itemIds": [item.item_id for item in items],
                "fileIds": [item.source.file_id for item in items],
            },
            now,
        )
        persisted = self._persist_create(intent, audit)
        return self._with_options(
            persisted if isinstance(persisted, ManualOrganizeIntent) else intent,
            snapshot,
            self._repository.list_manual_intent_audit(intent_id),
        )

    # Explicit aliases make the application boundary easy to consume from
    # adapters while keeping one implementation and one validation path.
    create_intent = create

    def get(self, intent_id: str) -> ManualOrganizeIntent:
        if not isinstance(intent_id, str) or not intent_id.strip():
            raise ManualIntentError("manual intent ID is required", code="invalid_intent_id")
        value = self._repository.get_manual_intent(intent_id)
        if value is None:
            raise ManualIntentError(
                f"manual intent {intent_id!r} was not found",
                code="intent_not_found",
                status=404,
                next_action="return to Files and select a current indexed file",
            )
        # Persistence stores the immutable normalized option projection.  A
        # missing projection is an integrity failure, never a reason to fall
        # back to JSON or the current Active revision.
        if value.options is None:
            raise ManualIntentUnavailable(
                "manual intent configuration option projection is unavailable",
                details={"intentId": intent_id, "snapshotId": value.snapshot_id},
            )
        if (
            value.options.snapshot_id != value.snapshot_id
            or value.options.digest != value.snapshot_digest
        ):
            raise ManualIntentUnavailable(
                "manual intent configuration snapshot identity is corrupt",
                details={"intentId": intent_id, "snapshotId": value.snapshot_id},
            )
        if self._configuration_service is not None:
            try:
                managed_options = self._load_managed_snapshot(
                    value.snapshot_id, value.snapshot_digest
                )
                if managed_options.document() != value.options.document():
                    raise ManualIntentUnavailable(
                        "manual intent configuration option projection does not match its "
                        "pinned managed snapshot",
                        details={
                            "intentId": intent_id,
                            "snapshotId": value.snapshot_id,
                        },
                    )
            except RuntimeSnapshotUnavailable as error:
                raise ManualIntentUnavailable(
                    "the pinned managed Active configuration snapshot is unavailable",
                    details={
                        "intentId": intent_id,
                        "snapshotId": value.snapshot_id,
                        "reason": getattr(error, "reason", None),
                    },
                ) from error
            except Exception as error:
                raise ManualIntentUnavailable(
                    "the pinned managed Active configuration snapshot is unreadable",
                    details={
                        "intentId": intent_id,
                        "snapshotId": value.snapshot_id,
                        "reason": type(error).__name__,
                    },
                ) from error
        audits = self._repository.list_manual_intent_audit(intent_id)
        return self._with_options(value, value.options, audits)

    get_intent = get

    def list(self, *, limit: int = 100) -> tuple[ManualOrganizeIntent, ...]:
        if isinstance(limit, bool) or not 1 <= limit <= self._max_items:
            raise ManualIntentError(
                f"manual intent limit must be between 1 and {self._max_items}",
                code="invalid_limit",
            )
        values = self._repository.list_manual_intents(limit=limit)
        return tuple(self.get(value.intent_id) for value in values)

    def update_choice(
        self,
        intent_id: str,
        item_id: str,
        choice: ManualChoice | dict[str, object],
        *,
        expected_version: int,
        actor: str,
        expected_item_version: int | None = None,
        snapshot_id: str | None = None,
        snapshot_digest: str | None = None,
    ) -> ManualOrganizeIntent:
        actor = self._actor(actor)
        intent = self.get(intent_id)
        self._expected_version(expected_version)
        if intent.status is not ManualIntentStatus.OPEN:
            raise ManualIntentError(
                "cancelled manual intent cannot be changed",
                code="intent_not_open",
                next_action="create a new intent from the current File detail",
                details={"currentVersion": intent.version, "currentState": intent.document(False)},
            )
        if snapshot_id is not None and snapshot_id != intent.snapshot_id:
            raise ManualIntentError(
                "choice belongs to a different configuration snapshot",
                code="cross_snapshot_choice",
                next_action=(
                    "reload the manual intent and choose an option shown under its pinned snapshot"
                ),
                details={"expectedSnapshotId": intent.snapshot_id},
            )
        if snapshot_digest is not None and snapshot_digest != intent.snapshot_digest:
            raise ManualIntentError(
                "choice digest does not match the pinned configuration snapshot",
                code="cross_snapshot_choice",
                next_action=(
                    "reload the manual intent and choose an option shown under its pinned snapshot"
                ),
                details={"expectedSnapshotDigest": intent.snapshot_digest},
            )
        if intent.version != expected_version:
            raise ManualIntentConflict(
                "manual intent version is stale; no choice was changed",
                intent=intent,
                next_action="reload the current manual intent, then retry or cancel explicitly",
            )
        try:
            item = next(item for item in intent.items if item.item_id == item_id)
        except StopIteration as error:
            raise ManualIntentError(
                f"manual intent item {item_id!r} was not found",
                code="item_not_found",
                status=404,
                next_action="reload the current intent and select one of its listed items",
            ) from error
        if expected_item_version is not None:
            self._expected_version(expected_item_version, "expected item version")
            if item.version != expected_item_version:
                raise ManualIntentConflict(
                    "manual intent item version is stale; no choice was changed",
                    intent=intent,
                )
        record = self._resolve_file(item.source.file_id)
        self._assert_source_unchanged(item.source, record)
        if isinstance(choice, dict):
            normalized = self._choice_from_patch(item.choice, choice)
        elif isinstance(choice, ManualChoice):
            normalized = choice
        else:
            raise ManualIntentError("manual choice must be an object", code="malformed_choice")
        self._validate_choice(normalized, intent.options, record)
        now = self._clock()
        updated_item = ManualIntentItem(
            item.item_id,
            item.intent_id,
            item.position,
            item.source,
            normalized,
            ManualIntentItemStatus.READY,
            None,
            item.version + 1,
            item.created_at,
            now,
        )
        updated_intent = ManualOrganizeIntent(
            intent.intent_id,
            intent.actor,
            intent.snapshot_id,
            intent.snapshot_digest,
            intent.status,
            intent.version + 1,
            intent.created_at,
            now,
            tuple(updated_item if value.item_id == item_id else value for value in intent.items),
            intent.options,
            "continue to a later manual Preview",
            None,
            intent.audit,
        )
        audit = ManualIntentAudit(
            str(uuid4()),
            intent.intent_id,
            item.item_id,
            actor,
            "choice_updated",
            {"version": intent.version, "choice": item.choice.document()},
            {"version": updated_intent.version, "choice": normalized.document()},
            now,
        )
        persisted = self._persist_choice(
            updated_intent, updated_item, intent.version, item.version, audit
        )
        return self._with_options(
            persisted, intent.options, self._repository.list_manual_intent_audit(intent_id)
        )

    update_item_choice = update_choice

    def cancel(self, intent_id: str, *, expected_version: int, actor: str) -> ManualOrganizeIntent:
        actor = self._actor(actor)
        intent = self.get(intent_id)
        self._expected_version(expected_version)
        if intent.version != expected_version:
            raise ManualIntentConflict(
                "manual intent version is stale; no cancellation was recorded", intent=intent
            )
        if intent.status is ManualIntentStatus.CANCELLED:
            return intent
        now = self._clock()
        cancelled_items = tuple(
            ManualIntentItem(
                item.item_id,
                item.intent_id,
                item.position,
                item.source,
                item.choice,
                ManualIntentItemStatus.CANCELLED,
                item.error,
                item.version,
                item.created_at,
                now,
            )
            for item in intent.items
        )
        cancelled = ManualOrganizeIntent(
            intent.intent_id,
            intent.actor,
            intent.snapshot_id,
            intent.snapshot_digest,
            ManualIntentStatus.CANCELLED,
            intent.version + 1,
            intent.created_at,
            now,
            cancelled_items,
            intent.options,
            "create a new intent from the current File detail if work is still needed",
            None,
            intent.audit,
        )
        audit = ManualIntentAudit(
            str(uuid4()),
            intent.intent_id,
            None,
            actor,
            "cancelled",
            {"status": intent.status.value, "version": intent.version},
            {"status": cancelled.status.value, "version": cancelled.version},
            now,
        )
        persisted = self._persist_cancel(cancelled, intent.version, audit)
        return self._with_options(
            persisted, intent.options, self._repository.list_manual_intent_audit(intent_id)
        )

    cancel_intent = cancel

    def _selection(self, file_ids: Iterable[str]) -> tuple[str, ...]:
        if isinstance(file_ids, (str, bytes)):
            raise ManualIntentError("fileIds must be a bounded array", code="malformed_selection")
        try:
            values = tuple(file_ids)
        except TypeError as error:
            raise ManualIntentError(
                "fileIds must be a bounded array", code="malformed_selection"
            ) from error
        if not 1 <= len(values) <= self._max_items:
            raise ManualIntentError(
                f"manual selection must contain between 1 and {self._max_items} files",
                code="selection_over_limit" if values else "selection_empty",
                next_action="return to Files and select a non-empty bounded set of current files",
            )
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ManualIntentError(
                "fileIds must contain non-empty strings", code="malformed_selection"
            )
        if len(set(values)) != len(values):
            raise ManualIntentError(
                "fileIds must not contain duplicates",
                code="duplicate_selection",
                next_action="remove duplicate file IDs and resubmit the bounded selection",
            )
        return values

    @staticmethod
    def _actor(actor: str) -> str:
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 200:
            raise ManualIntentError("manual intent actor is invalid", code="invalid_actor")
        return actor.strip()

    @staticmethod
    def _expected_version(value: int, name: str = "expected version") -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ManualIntentError(f"{name} must be a positive integer", code="malformed_version")

    def _resolve_file(self, file_id: str):
        repository = getattr(self._file_catalog, "_repository", None)
        libraries = tuple(getattr(self._file_catalog, "_resource_library_ids", ()))
        if repository is not None and libraries:
            matches = []
            for library_id in libraries:
                values = repository.list_by_resource_library(library_id)
                matches.extend(value for value in values if value.file_id == file_id)
            if not matches:
                raise ManualIntentError(
                    f"FileIndex record {file_id!r} was not found",
                    code="source_missing",
                    status=404,
                    next_action="return to Files and select a current indexed file",
                )
            if len(matches) > 1:
                raise ManualIntentError(
                    "the FileIndex identity is ambiguous across ResourceLibraries",
                    code="source_ambiguous",
                    next_action="scope the Files selection to one ResourceLibrary and reload",
                    details={"fileId": file_id},
                )
            return matches[0]
        try:
            return self._file_catalog.show(file_id)
        except LookupError as error:
            raise ManualIntentError(
                str(error),
                code="source_missing",
                status=404,
                next_action="return to Files and select a current indexed file",
            ) from error

    def _assert_selectable(self, record) -> None:
        configured_storages = tuple(getattr(self._file_catalog, "_storage_ids", ()))
        if configured_storages and record.storage_id not in configured_storages:
            raise ManualIntentError(
                "selected FileIndex source belongs to an unconfigured Storage authority",
                code="source_cross_authority",
                next_action=(
                    "return to Files and select a source from the current configured authority"
                ),
                details={"fileId": record.file_id, "storageId": record.storage_id},
            )
        status = getattr(record.scan_status, "value", record.scan_status)
        if status != "ready":
            raise ManualIntentError(
                "selected FileIndex record is not currently ready",
                code="source_stale",
                next_action="refresh the File detail and select the current ready source",
                details={"fileId": record.file_id, "scanStatus": str(status)},
            )
        if (
            not isinstance(record.path, str)
            or record.path.startswith(("/", "\\"))
            or "\x00" in record.path
        ):
            raise ManualIntentError(
                "selected source path is not a safe indexed Storage-relative identity",
                code="source_invalid",
                next_action="repair the FileIndex record, then reload Files",
            )

    def _assert_source_unchanged(self, source: ManualSourceIdentity, record) -> None:
        try:
            self._assert_selectable(record)
        except ManualIntentError as error:
            raise error
        try:
            current = ManualSourceIdentity.from_file_record(record)
        except ValueError as error:
            raise ManualIntentError(
                "selected FileIndex source identity is malformed",
                code="source_invalid",
                next_action="repair the indexed source identity, then reload Files",
            ) from error
        if (
            current.file_id,
            current.storage_id,
            current.resource_library_id,
            current.path,
            current.filename,
            current.extension,
            current.size,
            current.modified_at,
            current.last_seen_at,
            current.updated_at,
            current.stable_since,
            current.scan_status,
            current.last_scan_id,
        ) != (
            source.file_id,
            source.storage_id,
            source.resource_library_id,
            source.path,
            source.filename,
            source.extension,
            source.size,
            source.modified_at,
            source.last_seen_at,
            source.updated_at,
            source.stable_since,
            source.scan_status,
            source.last_scan_id,
        ):
            raise ManualIntentError(
                "selected FileIndex source changed after intent creation",
                code="source_stale",
                next_action=(
                    "refresh/reopen the intent and create a new selection from current Files"
                ),
                details={"fileId": source.file_id},
            )

    def _active_snapshot(self) -> ManualConfigurationSnapshot:
        try:
            if self._configuration_resolver is not None:
                return self._normalize_snapshot(self._configuration_resolver())
            if self._configuration_service is not None:
                active = self._configuration_service.active()
                if active is None:
                    raise ManualIntentUnavailable("managed Active configuration is unavailable")
                self._configuration_service.verify_integrity(active)
                self._configuration_service.validate_runtime_snapshot(
                    active.revision_id, active.digest
                )
                from mediaflow.infrastructure.runtime_configuration import (
                    load_managed_runtime_configuration,
                )

                database_path = self._configuration_service.bootstrap_database_path
                if not database_path:
                    database_path = str(
                        getattr(self._configuration_service.repository, "database_path", "")
                    )
                runtime = load_managed_runtime_configuration(
                    active.document, bootstrap_database_path=database_path
                )
                return self._snapshot_from_runtime(runtime, active.revision_id, active.digest)
            if self._configuration is not None:
                return self._normalize_snapshot(self._configuration)
        except ManualIntentError:
            raise
        except RuntimeSnapshotUnavailable as error:
            raise ManualIntentUnavailable(
                str(error), details={"reason": getattr(error, "reason", None)}
            ) from error
        except Exception as error:
            raise ManualIntentUnavailable(
                "managed Active configuration is unavailable or not runtime-consumable",
                details={"reason": type(error).__name__},
            ) from error
        raise ManualIntentUnavailable(
            "manual intent requires a managed runtime configuration authority",
            details={"reason": "configuration_authority_unavailable"},
        )

    def _load_managed_snapshot(self, snapshot_id: str, digest: str) -> ManualConfigurationSnapshot:
        """Reload one persisted managed revision without constructing adapters."""

        service = self._configuration_service
        if service is None:
            raise RuntimeSnapshotUnavailable(
                "managed configuration service is unavailable",
                revision_id=snapshot_id,
                digest=digest,
                reason="configuration_authority_unavailable",
            )
        service.validate_runtime_snapshot(snapshot_id, digest)
        revision = service.require(snapshot_id)
        service.verify_integrity(revision)
        from mediaflow.infrastructure.runtime_configuration import (
            load_managed_runtime_configuration,
        )

        database_path = service.bootstrap_database_path
        if not database_path:
            database_path = str(getattr(service.repository, "database_path", ""))
        runtime = load_managed_runtime_configuration(
            revision.document,
            bootstrap_database_path=database_path,
        )
        return self._snapshot_from_runtime(runtime, snapshot_id, digest)

    @staticmethod
    def _normalize_snapshot(value: object) -> ManualConfigurationSnapshot:
        if isinstance(value, ManualConfigurationSnapshot):
            return value
        if isinstance(value, dict):
            raise ManualIntentUnavailable(
                "manual intent cannot use a JSON bootstrap or process-local Draft as Active "
                "authority"
            )
        authority = getattr(value, "configuration_authority", None)
        if authority != "MANAGED":
            raise ManualIntentUnavailable(
                "manual intent requires the managed Active configuration authority",
                details={"authority": authority},
            )
        snapshot_id = getattr(value, "snapshot_id", None) or getattr(
            value, "configuration_snapshot_id", None
        )
        digest = getattr(value, "digest", None) or getattr(
            value, "configuration_snapshot_digest", None
        )
        strategy = getattr(value, "strategy", None)
        if strategy is not None and snapshot_id and digest:
            return ManualOrganizeIntentService._snapshot_from_runtime(value, snapshot_id, digest)
        if isinstance(value, tuple) and len(value) == 2:
            raise ManualIntentUnavailable(
                "configuration resolver returned only an identity without options"
            )
        raise ManualIntentUnavailable(
            "configuration resolver did not return a normalized Active snapshot"
        )

    @staticmethod
    def _snapshot_from_runtime(
        runtime, snapshot_id: str, digest: str
    ) -> ManualConfigurationSnapshot:
        strategy = runtime.strategy
        metadata = {item.policy_id: item for item in strategy.metadata_policies if item.enabled}
        naming = {item.policy_id: item for item in strategy.naming_policies if item.enabled}
        classification = {
            item.policy_id: item for item in strategy.classification_policies if item.enabled
        }
        organize = {item.policy_id: item for item in strategy.organize_policies}
        type_values = {item.type_id: item for item in strategy.recognition_types if item.enabled}
        recognition: list[ManualRecognitionOption] = []
        for policy in sorted(
            strategy.recognition_type_policies,
            key=lambda item: (item.priority, item.policy_id),
            reverse=True,
        ):
            type_value = type_values.get(policy.recognition_type_id)
            if not policy.enabled or type_value is None:
                continue
            if (
                policy.metadata_policy_id not in metadata
                or policy.naming_policy_id not in naming
                or policy.classification_policy_id not in classification
            ):
                continue
            organize_policy_id = policy.organize_policy_id
            if organize_policy_id not in organize:
                # Some bootstrap strategy objects carry the OrganizePolicy on
                # the type policy but omit the flattened strategy collection.
                organize[organize_policy_id] = policy.organize_policy
            recognition.append(
                ManualRecognitionOption(
                    type_value.type_id,
                    type_value.name,
                    type_value.description,
                    policy.policy_id,
                    policy.metadata_policy_id,
                    policy.naming_policy_id,
                    policy.classification_policy_id,
                    organize_policy_id,
                )
            )
        if not recognition:
            raise ManualIntentUnavailable(
                "Active configuration has no enabled compatible RecognitionType policy"
            )
        return ManualConfigurationSnapshot(
            snapshot_id,
            digest,
            tuple(sorted(recognition, key=lambda item: item.type_id)),
            tuple(
                ManualPolicyOption(
                    item.policy_id,
                    item.name or item.policy_id,
                    item.enabled,
                    item.provider_id,
                    item.media_type.value if item.media_type is not None else None,
                )
                for item in sorted(metadata.values(), key=lambda item: item.policy_id)
            ),
            tuple(
                ManualPolicyOption(
                    item.policy_id,
                    item.name or item.policy_id,
                    item.enabled,
                    media_type=item.media_type_mode.value,
                )
                for item in sorted(naming.values(), key=lambda item: item.policy_id)
            ),
            tuple(
                ManualPolicyOption(item.policy_id, item.name or item.policy_id, item.enabled)
                for item in sorted(classification.values(), key=lambda item: item.policy_id)
            ),
            tuple(
                ManualPolicyOption(
                    item.policy_id,
                    item.policy_id,
                    True,
                    operation=item.operation.value,
                    conflict_strategy=item.conflict_strategy.value,
                )
                for item in sorted(organize.values(), key=lambda item: item.policy_id)
            ),
        )

    def _default_choice(self, record, snapshot: ManualConfigurationSnapshot) -> ManualChoice:
        result = None
        try:
            result = self._file_catalog.detail(record.file_id).latest_result
        except (LookupError, ValueError, AttributeError):
            result = None
        by_type = {item.type_id: item for item in snapshot.recognition_types}
        selected_type = None
        if result is not None and result.recognition_type in by_type:
            selected_type = by_type[result.recognition_type]
        if selected_type is None:
            selected_type = snapshot.recognition_types[0]
        metadata = None
        provider = getattr(result, "provider", None) if result is not None else None
        provider_id = getattr(result, "provider_id", None) if result is not None else None
        title = getattr(result, "title", None) if result is not None else None
        metadata_policy = next(
            (
                item
                for item in snapshot.metadata_policies
                if item.policy_id == selected_type.metadata_policy_id
            ),
            None,
        )
        media_type = metadata_policy.media_type if metadata_policy is not None else None
        if (
            provider
            and provider_id
            and metadata_policy is not None
            and provider == metadata_policy.provider_id
        ):
            metadata = ManualMetadataReference(provider, provider_id, media_type, title=title)
        return ManualChoice(
            selected_type.type_id,
            metadata,
            selected_type.naming_policy_id,
            selected_type.classification_policy_id,
            selected_type.organize_policy_id,
        )

    @staticmethod
    def _choice_from_patch(current: ManualChoice, patch: dict[str, object]) -> ManualChoice:
        allowed = {
            "recognitionTypeId",
            "metadata",
            "namingPolicyId",
            "classificationPolicyId",
            "organizePolicyId",
        }
        unknown = set(patch).difference(allowed)
        if unknown:
            raise ManualIntentError(
                f"manual choice field {sorted(unknown)[0]!r} is not supported",
                code="malformed_choice",
                next_action="use only normalized IDs and the bounded metadata identity fields",
            )
        values: dict[str, object] = current.document()
        values.update(patch)
        try:
            return ManualChoice.from_document(values)
        except ValueError as error:
            raise ManualIntentError(
                str(error),
                code="malformed_choice",
                next_action="correct the choice fields using the options shown for this intent",
            ) from error

    @staticmethod
    def _validate_choice(
        choice: ManualChoice, snapshot: ManualConfigurationSnapshot, record
    ) -> None:
        maps = snapshot.option_maps()
        selected_type = maps["recognitionType"].get(choice.recognition_type_id)
        if selected_type is None:
            raise ManualIntentError(
                "RecognitionType is disabled, removed, or not configured by the pinned snapshot",
                code="choice_disabled",
                next_action="reload the intent and select an enabled RecognitionType option",
            )
        required = {
            "metadataPolicy": selected_type.metadata_policy_id,
            "namingPolicy": selected_type.naming_policy_id,
            "classificationPolicy": selected_type.classification_policy_id,
            "organizePolicy": selected_type.organize_policy_id,
        }
        for kind, policy_id in required.items():
            if policy_id not in maps[kind]:
                raise ManualIntentError(
                    f"{kind} {policy_id!r} is unavailable under the pinned snapshot",
                    code="incompatible_choice",
                    next_action="reload the intent and select the configured defaults",
                )
        selected_policy_ids = {
            "namingPolicy": choice.naming_policy_id,
            "classificationPolicy": choice.classification_policy_id,
            "organizePolicy": choice.organize_policy_id,
        }
        for kind, selected_policy_id in selected_policy_ids.items():
            if selected_policy_id != required[kind]:
                raise ManualIntentError(
                    f"{kind} is not compatible with RecognitionType {choice.recognition_type_id!r}",
                    code="incompatible_choice",
                    next_action="choose the downstream policies shown for this RecognitionType",
                )
        if (
            choice.naming_policy_id not in maps["namingPolicy"]
            or choice.classification_policy_id not in maps["classificationPolicy"]
            or choice.organize_policy_id not in maps["organizePolicy"]
        ):
            raise ManualIntentError(
                "one or more selected policies are disabled or removed",
                code="choice_disabled",
                next_action="reload the intent and select only enabled policy options",
            )
        if choice.metadata is not None:
            metadata_policy = maps["metadataPolicy"].get(required["metadataPolicy"])
            if metadata_policy is None:
                raise ManualIntentError(
                    "metadata policy is unavailable", code="incompatible_choice"
                )
            if (
                choice.metadata.provider is not None
                and choice.metadata.provider != metadata_policy.provider_id
            ):
                raise ManualIntentError(
                    "metadata provider is incompatible with the selected RecognitionType policy",
                    code="incompatible_choice",
                    next_action="choose a normalized identity from the pinned provider policy",
                )
            if (
                metadata_policy.media_type
                and choice.metadata.media_type != metadata_policy.media_type
            ):
                raise ManualIntentError(
                    "metadata media type is incompatible with the selected RecognitionType policy",
                    code="incompatible_choice",
                    next_action="choose a normalized identity with the configured media type",
                )
        metadata_default = maps["metadataPolicy"].get(required["metadataPolicy"])
        media_type = (
            choice.metadata.media_type
            if choice.metadata is not None
            else getattr(metadata_default, "media_type", None)
        )
        naming = maps["namingPolicy"].get(choice.naming_policy_id)
        if (
            naming is not None
            and media_type
            and naming.media_type not in {None, "auto", media_type}
        ):
            raise ManualIntentError(
                "NamingPolicy media type is incompatible with the selected Metadata identity",
                code="incompatible_choice",
                next_action="choose a compatible NamingPolicy shown for this identity",
            )
        # The source argument intentionally remains unused beyond being part of
        # the shared validation signature: no path/Storage operation is accepted.
        _ = record

    @staticmethod
    def _with_options(
        intent: ManualOrganizeIntent, options: ManualConfigurationSnapshot, audits
    ) -> ManualOrganizeIntent:
        return ManualOrganizeIntent(
            intent.intent_id,
            intent.actor,
            intent.snapshot_id,
            intent.snapshot_digest,
            intent.status,
            intent.version,
            intent.created_at,
            intent.updated_at,
            intent.items,
            options,
            intent.next_action,
            intent.error,
            tuple(audits),
        )

    def _persist_create(self, intent: ManualOrganizeIntent, audit: ManualIntentAudit):
        method = getattr(self._repository, "create_manual_intent_with_audit", None)
        if not callable(method):
            method = getattr(self._repository, "create_manual_intent", None)
        if not callable(method):
            raise ManualIntentUnavailable("manual intent persistence is unavailable")
        method(intent, intent.items, audit)

    def _persist_choice(self, intent, item, expected_intent_version, expected_item_version, audit):
        method = getattr(self._repository, "update_manual_intent_choice_with_audit", None)
        if not callable(method):
            raise ManualIntentUnavailable("manual intent choice persistence is unavailable")
        try:
            return method(intent, item, expected_intent_version, expected_item_version, audit)
        except ManualIntentConflict:
            raise
        except (LookupError, ValueError) as error:
            current = self.get(intent.intent_id)
            raise ManualIntentConflict(str(error), intent=current) from error

    def _persist_cancel(self, intent, expected_version, audit):
        method = getattr(self._repository, "update_manual_intent_status_with_audit", None)
        if not callable(method):
            raise ManualIntentUnavailable("manual intent cancellation persistence is unavailable")
        try:
            return method(intent, expected_version, audit)
        except (LookupError, ValueError) as error:
            current = self.get(intent.intent_id)
            raise ManualIntentConflict(str(error), intent=current) from error
