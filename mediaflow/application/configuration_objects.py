from __future__ import annotations

import copy
import posixpath
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePath
from threading import BoundedSemaphore, Lock

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.read_only_storage import (
    ReadOnlyStorageGuard,
    ReadOnlyStorageMutationError,
)
from mediaflow.domain.configuration_management import (
    CONFIGURATION_REFERENCE_EVIDENCE_LIMIT,
    CONFIGURATION_SETUP_CHECK_PATH_LIMIT,
    ConfigurationActivationConflict,
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationReferenceEvidence,
    ConfigurationReferenceItem,
    ConfigurationSetupCheckStatus,
    ConfigurationVersionConflict,
    LocalSetupCheckEvidence,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
    ManagedDocumentRedactor,
)
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.infrastructure.runtime_configuration import (
    load_managed_runtime_configuration,
    load_runtime_configuration,
)


class ConfigurationObjectService:
    """Edit the three Phase 22.3 objects inside one managed Draft document."""

    _SECTIONS = {
        ConfigurationObjectKind.STORAGE: "storages",
        ConfigurationObjectKind.RESOURCE_LIBRARY: "resourceLibraries",
        ConfigurationObjectKind.MEDIA_LIBRARY: "mediaLibraries",
    }
    _MAX_OBJECT_BYTES = 64 * 1024
    _SETUP_CHECK_TIMEOUT_SECONDS = 10.0
    _SETUP_CHECK_CAPACITY = 1
    _STORAGE_FIELDS = {"id", "name", "type", "rootPath", "readOnly"}
    _RESOURCE_FIELDS = {
        "id",
        "name",
        "storageId",
        "storagePath",
        "displayRootPath",
        "enabled",
        "extensions",
        "maxDepth",
    }
    _MEDIA_FIELDS = {"id", "name", "storageId", "rootPath", "enabled"}

    def __init__(
        self,
        managed: ManagedConfigurationService,
        *,
        setup_check_timeout_seconds: float = _SETUP_CHECK_TIMEOUT_SECONDS,
    ) -> None:
        if (
            isinstance(setup_check_timeout_seconds, bool)
            or not isinstance(setup_check_timeout_seconds, (int, float))
            or setup_check_timeout_seconds <= 0
            or setup_check_timeout_seconds > 60
        ):
            raise ValueError("setup check timeout must be greater than 0 and at most 60 seconds")
        self._managed = managed
        self._repository = managed.repository
        self._setup_check_timeout_seconds = float(setup_check_timeout_seconds)
        self._setup_check_capacity = BoundedSemaphore(self._SETUP_CHECK_CAPACITY)
        self._setup_check_state_lock = Lock()
        self._setup_checks_in_flight = 0
        self._setup_check_executor = ThreadPoolExecutor(
            max_workers=self._SETUP_CHECK_CAPACITY,
            thread_name_prefix="mediaflow-setup-check",
        )

    @property
    def setup_checks_in_flight(self) -> int:
        with self._setup_check_state_lock:
            return self._setup_checks_in_flight

    def _acquire_setup_check(self) -> bool:
        if not self._setup_check_capacity.acquire(blocking=False):
            return False
        with self._setup_check_state_lock:
            self._setup_checks_in_flight += 1
        return True

    def _release_setup_check(self) -> None:
        with self._setup_check_state_lock:
            self._setup_checks_in_flight -= 1
        self._setup_check_capacity.release()

    def activate_checked(
        self,
        revision_id: str,
        *,
        expected_version: int,
        actor: str,
    ) -> ManagedConfigurationRevision:
        revision = self._managed.require(revision_id)
        self.require_current_local_check(revision)
        return self._managed.activate(
            revision_id,
            expected_version=expected_version,
            actor=actor,
        )

    def revision_detail(self, revision_id: str) -> dict[str, object]:
        revision = self._managed.require(revision_id)
        document = revision.document
        return {
            **revision.summary(),
            "objects": {
                "storages": self._objects(document, "storages", redact_remote=True),
                "resourceLibraries": self._objects(document, "resourceLibraries"),
                "mediaLibraries": self._objects(document, "mediaLibraries"),
            },
            # Keep every versioned projection on the same immutable revision read.
            # Calling the public helpers here would re-read the repository and could
            # combine objects from one Draft with evidence from a concurrent edit.
            "references": self._references_from_document(document),
            "localSetupCheck": self._check_document(revision),
        }

    def references(self, revision_id: str) -> dict[str, dict[str, object]]:
        revision = self._managed.require(revision_id)
        return self._references_from_document(revision.document)

    @classmethod
    def _references_from_document(
        cls, document: Mapping[str, object]
    ) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}
        for kind, section in cls._SECTIONS.items():
            for value in cls._canonical_objects(document, section):
                object_id = str(value.get("id", ""))
                result[f"{kind.value}:{object_id}"] = cls._references_for(
                    kind, object_id, document
                ).document()
        return result

    def mutate(
        self,
        revision_id: str,
        kind: ConfigurationObjectKind,
        *,
        object_id: str | None,
        value: Mapping[str, object] | None,
        expected_version: int,
        actor: str,
        delete: bool = False,
    ) -> ManagedConfigurationRevision:
        section = self._section(kind)
        revision = self._managed.require(revision_id)
        if revision.status not in {
            ManagedConfigurationStatus.DRAFT,
            ManagedConfigurationStatus.VALIDATED,
        }:
            raise ConfigurationVersionConflict(
                "configuration objects can only be changed in a Draft or Validated revision",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
            )
        if revision.version != expected_version:
            raise ConfigurationVersionConflict(
                "configuration Draft is stale; refresh it before editing",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
            )
        current_values = self._canonical_objects(revision.document, section)
        current_by_id = {str(item.get("id", "")): item for item in current_values}
        if delete:
            if not object_id or object_id not in current_by_id:
                raise LookupError(f"{kind.value} {object_id!r} was not found")
            reference_evidence = self._references_for(kind, object_id, revision.document)
            if reference_evidence.total:
                raise ConfigurationObjectReferenced(
                    kind,
                    object_id,
                    reference_evidence.total,
                    evidence=reference_evidence,
                )
            next_values = [item for item in current_values if item.get("id") != object_id]
            before = current_by_id[object_id]
            after = None
            action = "guided_delete"
        else:
            if not isinstance(value, Mapping):
                raise ValueError("configuration object must be an object")
            normalized = self._normalize(kind, value)
            normalized_id = str(normalized["id"])
            if object_id is not None and normalized_id != object_id:
                raise ValueError("configuration object ID cannot change during update")
            if object_id is None and normalized_id in current_by_id:
                raise ValueError(f"{kind.value} {normalized_id!r} already exists")
            if object_id is not None and object_id not in current_by_id:
                raise LookupError(f"{kind.value} {object_id!r} was not found")
            next_values = [
                normalized if item.get("id") == object_id else item for item in current_values
            ]
            if object_id is None:
                next_values.append(normalized)
                before = None
                action = "guided_create"
            else:
                before = current_by_id[object_id]
                action = "guided_update"
            after = normalized
        next_document = copy.deepcopy(revision.document)
        next_document[section] = next_values
        return self._managed.edit_draft(
            revision_id,
            next_document,
            expected_version=expected_version,
            actor=actor,
            audit_context={
                "kind": kind.value,
                "objectId": object_id or (str(after.get("id")) if after else ""),
                "action": action,
                "before": before,
                "after": after,
            },
        )

    def local_check(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
        resource_library_id: str | None = None,
        media_library_id: str | None = None,
    ) -> LocalSetupCheckEvidence:
        revision = self._managed.require(revision_id)
        if revision.status is not ManagedConfigurationStatus.VALIDATED:
            raise ConfigurationVersionConflict(
                "Local setup check requires a Validated Draft",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
            )
        if revision.version != expected_version or revision.digest != expected_digest:
            raise ConfigurationVersionConflict(
                "Local setup check is stale; validate the current Draft again",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
            )
        started = time.monotonic()
        progress = _SetupCheckProgress()
        if not self._acquire_setup_check():
            evidence = self._progress_evidence(
                revision,
                actor=actor,
                progress=progress,
                started=started,
                status=ConfigurationSetupCheckStatus.FAILED,
                resource_library_id=resource_library_id,
                media_library_id=media_library_id,
                failure_category="capacity_unavailable",
                message="Local setup check capacity is occupied by an unfinished check",
                next_action="wait for the in-flight check to finish, then run the check again",
            )
            return evidence
        try:
            future = self._setup_check_executor.submit(
                self._run_local_check,
                revision,
                actor,
                resource_library_id,
                media_library_id,
                progress,
                started,
            )
        except Exception:
            self._release_setup_check()
            evidence = self._progress_evidence(
                revision,
                actor=actor,
                progress=progress,
                started=started,
                status=ConfigurationSetupCheckStatus.FAILED,
                resource_library_id=resource_library_id,
                media_library_id=media_library_id,
                failure_category="unavailable",
                message="Local setup check worker is unavailable",
                next_action="inspect service health, then run the check again",
            )
            return self._repository.save_local_setup_check(evidence)
        lease = _SetupCheckLease(self._release_setup_check)
        future.add_done_callback(lambda _future: lease.worker_finished())
        try:
            try:
                remaining = max(
                    0.0,
                    started + self._setup_check_timeout_seconds - time.monotonic(),
                )
                evidence = future.result(timeout=remaining)
            except FutureTimeoutError:
                evidence = self._progress_evidence(
                    revision,
                    actor=actor,
                    progress=progress,
                    started=started,
                    status=ConfigurationSetupCheckStatus.FAILED,
                    resource_library_id=resource_library_id,
                    media_library_id=media_library_id,
                    failure_category="timeout",
                    message="Local setup check exceeded its overall deadline",
                    next_action=(
                        "wait for the in-flight check to finish; correct availability if needed, "
                        "then run the check again"
                    ),
                )
            except Exception:
                evidence = self._progress_evidence(
                    revision,
                    actor=actor,
                    progress=progress,
                    started=started,
                    status=ConfigurationSetupCheckStatus.FAILED,
                    resource_library_id=resource_library_id,
                    media_library_id=media_library_id,
                    failure_category="unavailable",
                    message="Local setup check worker failed (details redacted)",
                    next_action=(
                        "inspect service health and configuration, then run the check again"
                    ),
                )
            return self._repository.save_local_setup_check(evidence)
        finally:
            lease.response_finished()

    def _run_local_check(
        self,
        revision: ManagedConfigurationRevision,
        actor: str,
        resource_library_id: str | None,
        media_library_id: str | None,
        progress: _SetupCheckProgress,
        started: float,
    ) -> LocalSetupCheckEvidence:
        try:
            selected_resource, selected_media = self._select_libraries(
                revision.document, resource_library_id, media_library_id
            )
            selected_ids = tuple(
                sorted(
                    {
                        str(selected_resource["storageId"]),
                        str(selected_media["storageId"]),
                    }
                )
            )
            progress.select(
                storage_ids=selected_ids,
                resource_library_id=str(selected_resource["id"]),
                media_library_id=str(selected_media["id"]),
            )
            storage_values = {
                str(item["id"]): item
                for item in self._canonical_objects(revision.document, "storages")
            }
            for storage_id in selected_ids:
                storage = storage_values.get(storage_id)
                if storage is None:
                    raise _SetupCheckFailure(
                        "invalid_configuration", "referenced Storage is missing"
                    )
                if str(storage.get("type", "")).lower() != "local":
                    raise _SetupCheckFailure(
                        "unsupported_storage_type",
                        "guided Local setup check supports Local Storage only",
                    )
            check_document = copy.deepcopy(revision.document)
            for storage in self._canonical_objects(check_document, "storages"):
                if storage.get("id") in selected_ids:
                    storage["readOnly"] = True
            if self._managed.bootstrap_database_path is not None:
                runtime = load_managed_runtime_configuration(
                    check_document,
                    bootstrap_database_path=self._managed.bootstrap_database_path,
                )
            else:
                runtime = load_runtime_configuration(check_document)
            progress.complete("runtime.load")
            created_storages = runtime.create_storages(storage_ids=set(selected_ids))
            progress.complete("storage.construct")
            local_storages = {
                storage_id: ReadOnlyStorageGuard(created_storages[storage_id])
                for storage_id in selected_ids
                if storage_id in created_storages
            }
            for storage_id in selected_ids:
                if storage_id not in local_storages:
                    raise _SetupCheckFailure(
                        "invalid_configuration", "Local Storage adapter was not created"
                    )
            source_path = self._join_relative(
                local_storages[str(selected_resource["storageId"])],
                str(selected_resource.get("storagePath", "")),
            )
            destination_path = self._join_relative(
                local_storages[str(selected_media["storageId"])],
                str(selected_media.get("rootPath", "")),
            )
            source_path = self._evidence_path(source_path, "source")
            destination_path = self._evidence_path(destination_path, "destination")
            progress.paths(source=source_path, destination=destination_path)
            self._check_path(
                local_storages[str(selected_resource["storageId"])],
                source_path,
                label="source",
                progress=progress,
            )
            self._check_path(
                local_storages[str(selected_media["storageId"])],
                destination_path,
                label="destination",
                progress=progress,
            )
            return self._progress_evidence(
                revision,
                actor=actor,
                progress=progress,
                started=started,
                status=ConfigurationSetupCheckStatus.PASSED,
                next_action="review the diff and activate this Draft",
            )
        except _SetupCheckFailure as error:
            return self._progress_evidence(
                revision,
                actor=actor,
                progress=progress,
                started=started,
                status=ConfigurationSetupCheckStatus.FAILED,
                failure_category=error.category,
                message=error.message,
                next_action="correct the Draft and validate/check it again",
            )
        except StorageError as error:
            category = {
                StorageErrorCode.NOT_FOUND: "missing_path",
                StorageErrorCode.PERMISSION_DENIED: "permission_denied",
                StorageErrorCode.TIMEOUT: "timeout",
                StorageErrorCode.CONNECTION_FAILED: "unavailable",
                StorageErrorCode.CONNECTION_LOST: "unavailable",
                StorageErrorCode.INVALID_PATH: "invalid_path",
                StorageErrorCode.PATH_TRAVERSAL: "invalid_path",
            }.get(error.code, "unavailable")
            return self._progress_evidence(
                revision,
                actor=actor,
                progress=progress,
                started=started,
                status=ConfigurationSetupCheckStatus.FAILED,
                failure_category=category,
                message="Local setup check could not access the configured path",
                next_action="correct the path or permissions and run the check again",
            )
        except ReadOnlyStorageMutationError:
            return self._progress_evidence(
                revision,
                actor=actor,
                progress=progress,
                started=started,
                status=ConfigurationSetupCheckStatus.FAILED,
                failure_category="read_only_violation",
                message="Local setup check attempted a forbidden Storage mutation",
                next_action="do not activate; inspect the setup-check implementation",
            )
        except Exception:
            return self._progress_evidence(
                revision,
                actor=actor,
                progress=progress,
                started=started,
                status=ConfigurationSetupCheckStatus.FAILED,
                failure_category="unavailable",
                message="Local setup check failed (details redacted)",
                next_action="inspect the paths and run the check again",
            )

    def require_current_local_check(self, revision: ManagedConfigurationRevision) -> None:
        evidence = self._repository.get_local_setup_check(revision.revision_id)
        if evidence is None or evidence.status is not ConfigurationSetupCheckStatus.PASSED:
            raise ConfigurationActivationConflict(
                "a successful Local setup check is required before checked activation",
                revision_id=revision.revision_id,
            )
        if (
            evidence.revision_version != revision.version
            or evidence.revision_digest != revision.digest
        ):
            raise ConfigurationActivationConflict(
                "Local setup check is stale; validate and check the Draft again",
                revision_id=revision.revision_id,
            )

    def _check_document(self, revision: ManagedConfigurationRevision) -> dict[str, object] | None:
        evidence = self._repository.get_local_setup_check(revision.revision_id)
        if evidence is None:
            return None
        value = evidence.document()
        value["stale"] = (
            evidence.revision_version != revision.version
            or evidence.revision_digest != revision.digest
        )
        return value

    @classmethod
    def _section(cls, kind: ConfigurationObjectKind) -> str:
        try:
            return cls._SECTIONS[kind]
        except KeyError as error:
            raise ValueError(
                "only Storage, ResourceLibrary, and MediaLibrary are editable"
            ) from error

    @classmethod
    def _canonical_objects(
        cls, document: Mapping[str, object], section: str
    ) -> list[dict[str, object]]:
        """Return the complete, validated object section from the managed Draft.

        Presentation limits and remote redaction must never become the source of a
        replacement section.  The managed document already has a bounded whole
        document size, so the canonical read is complete rather than paginated.
        """
        if section not in document:
            raise ValueError(f"{section} is missing")
        values = document[section]
        if not isinstance(values, list):
            raise ValueError(f"{section} must be an array")
        result: list[dict[str, object]] = []
        seen: set[str] = set()
        for index, value in enumerate(values):
            if not isinstance(value, Mapping):
                raise ValueError(f"{section}[{index}] must be an object")
            item = copy.deepcopy(dict(value))
            object_id = item.get("id")
            if (
                not isinstance(object_id, str)
                or not object_id.strip()
                or len(object_id) > 64
                or any(character in object_id for character in "/\\\x00")
            ):
                raise ValueError(f"{section}[{index}] has an invalid or missing id")
            if object_id in seen:
                raise ValueError(f"{section} contains duplicate id {object_id!r}")
            seen.add(object_id)
            result.append(item)
        return result

    @classmethod
    def _objects(cls, document: Mapping[str, object], section: str, *, redact_remote: bool = False):
        result = cls._canonical_objects(document, section)
        if redact_remote:
            result = [copy.deepcopy(item) for item in result]
        redacted = []
        for item in result:
            if redact_remote and str(item.get("type", "")).lower() != "local":
                item["readOnly"] = True
                item["editability"] = "json_import_only"
                item = ManagedDocumentRedactor.redact(
                    item,
                    {
                        "token",
                        "password",
                        "secret",
                        "secretkey",
                        "accesskey",
                        "access_key",
                        "secret_key",
                    },
                )
            redacted.append(item)
        return redacted

    @classmethod
    def _normalize(
        cls, kind: ConfigurationObjectKind, value: Mapping[str, object]
    ) -> dict[str, object]:
        section = cls._section(kind)
        allowed = {
            ConfigurationObjectKind.STORAGE: cls._STORAGE_FIELDS,
            ConfigurationObjectKind.RESOURCE_LIBRARY: cls._RESOURCE_FIELDS,
            ConfigurationObjectKind.MEDIA_LIBRARY: cls._MEDIA_FIELDS,
        }[kind]
        unknown = set(value).difference(allowed)
        if unknown:
            raise ValueError(f"{section} contains unsupported field {sorted(unknown)[0]!r}")
        object_id = value.get("id")
        if not isinstance(object_id, str) or not object_id.strip() or len(object_id) > 64:
            raise ValueError(f"{section} id must be a bounded non-empty string")
        if any(character in object_id for character in "/\\\x00"):
            raise ValueError(f"{section} id contains an invalid character")
        name = value.get("name", object_id)
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError(f"{section} name must be a bounded non-empty string")
        result = {"id": object_id, "name": name}
        if kind is ConfigurationObjectKind.STORAGE:
            if str(value.get("type", "")).lower() != "local":
                raise ValueError("guided Storage editing supports Local type only")
            root = cls._host_absolute_path(value.get("rootPath"))
            read_only = value.get("readOnly", False)
            if not isinstance(read_only, bool):
                raise ValueError("Local Storage readOnly must be boolean")
            result.update({"type": "local", "rootPath": root, "readOnly": read_only})
            return result
        storage_id = value.get("storageId")
        if not isinstance(storage_id, str) or not storage_id.strip():
            raise ValueError(f"{section} storageId must be a non-empty string")
        result["storageId"] = storage_id
        enabled = value.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"{section} enabled must be boolean")
        result["enabled"] = enabled
        if kind is ConfigurationObjectKind.RESOURCE_LIBRARY:
            storage_path = value.get("storagePath", "")
            result["storagePath"] = cls._relative_path(storage_path, "ResourceLibrary storagePath")
            if "displayRootPath" in value and value["displayRootPath"] is not None:
                display_root = value["displayRootPath"]
                if not isinstance(display_root, str) or not display_root.strip():
                    raise ValueError("ResourceLibrary displayRootPath must be non-empty")
                result["displayRootPath"] = display_root
            extensions = value.get("extensions")
            if extensions is not None:
                if not isinstance(extensions, list) or not extensions:
                    raise ValueError("ResourceLibrary extensions must be a non-empty array")
                normalized_extensions = []
                for extension in extensions:
                    if not isinstance(extension, str) or not extension.strip():
                        raise ValueError("ResourceLibrary extensions must contain strings")
                    extension = extension.lower().lstrip(".")
                    if "/" in extension or "\\" in extension or "\x00" in extension:
                        raise ValueError("ResourceLibrary extension is unsafe")
                    normalized_extensions.append(extension)
                result["extensions"] = list(dict.fromkeys(normalized_extensions))
            if "maxDepth" in value:
                maximum = value["maxDepth"]
                if maximum is not None and (
                    isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 0
                ):
                    raise ValueError("ResourceLibrary maxDepth must be a non-negative integer")
                result["maxDepth"] = maximum
        else:
            result["rootPath"] = cls._relative_path(
                value.get("rootPath", ""), "MediaLibrary rootPath"
            )
        encoded = repr(result).encode("utf-8")
        if len(encoded) > cls._MAX_OBJECT_BYTES:
            raise ValueError(f"{section} object is too large")
        return result

    @staticmethod
    def _host_absolute_path(value: object) -> str:
        path = PurePath(value) if isinstance(value, str) else None
        if (
            not isinstance(value, str)
            or not value.strip()
            or "\x00" in value
            or path is None
            or not path.is_absolute()
            or ".." in path.parts
        ):
            raise ValueError(
                "Local Storage rootPath must be a host-absolute path without NUL or parent "
                "traversal ('..')"
            )
        return value

    @staticmethod
    def _relative_path(value: object, label: str) -> str:
        if not isinstance(value, str) or "\x00" in value:
            raise ValueError(f"{label} must be a string without NUL")
        normalized = posixpath.normpath(value) if value else ""
        if (
            value.startswith(("/", "\\"))
            or "\\" in value
            or normalized in {"..", "."}
            or normalized.startswith("../")
            or any(part in {"", ".", ".."} for part in value.split("/"))
        ) and value:
            raise ValueError(f"{label} must be a safe Storage-relative path")
        return "" if not value else normalized

    @classmethod
    def _references_for(
        cls,
        kind: ConfigurationObjectKind,
        object_id: str,
        document: Mapping[str, object],
    ) -> ConfigurationReferenceEvidence:
        collector = _ReferenceEvidenceCollector()
        if kind is ConfigurationObjectKind.STORAGE:
            for section in ("resourceLibraries", "mediaLibraries"):
                for index, item in enumerate(cls._canonical_objects(document, section)):
                    storage_id = cls._required_reference_id(
                        item,
                        section=section,
                        index=index,
                        field="storageId",
                    )
                    if storage_id == object_id:
                        collector.add(
                            ConfigurationReferenceItem(
                                section=section,
                                object_id=str(item["id"]),
                                field="storageId",
                            )
                        )
        elif kind is ConfigurationObjectKind.MEDIA_LIBRARY:
            for policy_index, policy in enumerate(
                cls._canonical_objects(document, "classificationPolicies")
            ):
                rules = policy.get("rules")
                if not isinstance(rules, list):
                    raise ValueError(
                        f"classificationPolicies[{policy_index}].rules must be an array"
                    )
                for rule_index, rule in enumerate(rules):
                    if not isinstance(rule, Mapping):
                        raise ValueError(
                            f"classificationPolicies[{policy_index}].rules[{rule_index}]"
                            " must be an object"
                        )
                    result = rule.get("result", rule)
                    if "result" in rule and not isinstance(result, Mapping):
                        raise ValueError(
                            f"classificationPolicies[{policy_index}].rules[{rule_index}].result"
                            " must be an object"
                        )
                    if isinstance(result, Mapping) and "mediaLibraryId" in result:
                        media_library_id = cls._required_reference_value(
                            result.get("mediaLibraryId"),
                            section="classificationPolicies",
                            index=policy_index,
                            field="mediaLibraryId",
                        )
                        if media_library_id == object_id:
                            collector.add(
                                ConfigurationReferenceItem(
                                    section="classificationPolicies",
                                    object_id=str(policy["id"]),
                                    field="mediaLibraryId",
                                )
                            )
        elif kind is ConfigurationObjectKind.RESOURCE_LIBRARY:
            for rule_index, rule in enumerate(cls._canonical_objects(document, "recognitionRules")):
                condition = rule.get("condition")
                if not isinstance(condition, Mapping):
                    raise ValueError(f"recognitionRules[{rule_index}].condition must be an object")
                if cls._contains_resource_reference(condition, object_id, rule_index=rule_index):
                    collector.add(
                        ConfigurationReferenceItem(
                            section="recognitionRules",
                            object_id=str(rule["id"]),
                            field="resourceLibraryId",
                        )
                    )
        return collector.evidence()

    @staticmethod
    def _required_reference_value(
        value: object,
        *,
        section: str,
        index: int,
        field: str,
    ) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 128 or "\x00" in value:
            raise ValueError(f"{section}[{index}].{field} must be a bounded non-empty string")
        return value

    @classmethod
    def _required_reference_id(
        cls,
        item: Mapping[str, object],
        *,
        section: str,
        index: int,
        field: str,
    ) -> str:
        return cls._required_reference_value(
            item.get(field), section=section, index=index, field=field
        )

    @classmethod
    def _contains_resource_reference(
        cls, value: object, object_id: str, *, rule_index: int
    ) -> bool:
        if isinstance(value, Mapping):
            if value.get("field") in {"resource_library_id", "resourceLibraryId"}:
                resource_library_id = cls._required_reference_value(
                    value.get("value"),
                    section="recognitionRules",
                    index=rule_index,
                    field="condition.value",
                )
                if resource_library_id == object_id:
                    return True
            return any(
                cls._contains_resource_reference(item, object_id, rule_index=rule_index)
                for item in value.values()
            )
        if isinstance(value, list):
            return any(
                cls._contains_resource_reference(item, object_id, rule_index=rule_index)
                for item in value
            )
        return False

    @staticmethod
    def _select_libraries(
        document: Mapping[str, object], resource_id: str | None, media_id: str | None
    ) -> tuple[dict[str, object], dict[str, object]]:
        resources = ConfigurationObjectService._canonical_objects(document, "resourceLibraries")
        media = ConfigurationObjectService._canonical_objects(document, "mediaLibraries")
        resources = [item for item in resources if item.get("enabled", True)]
        media = [item for item in media if item.get("enabled", True)]
        if resource_id is not None:
            resources = [item for item in resources if item.get("id") == resource_id]
        if media_id is not None:
            media = [item for item in media if item.get("id") == media_id]
        if len(resources) != 1 or len(media) != 1:
            raise _SetupCheckFailure(
                "invalid_configuration",
                "select exactly one enabled ResourceLibrary and MediaLibrary for the Local check",
            )
        return resources[0], media[0]

    @staticmethod
    def _join_relative(storage: object, relative: str) -> str:
        # LocalStorage performs the authoritative root confinement check; this
        # call only creates the Storage-relative input accepted by its API.
        return relative or ""

    @staticmethod
    def _evidence_path(path: str, label: str) -> str:
        if "\x00" in path or len(path) > CONFIGURATION_SETUP_CHECK_PATH_LIMIT:
            raise _SetupCheckFailure(
                "invalid_path",
                f"configured Local {label} root is too long or unsafe for setup evidence",
            )
        return path

    @staticmethod
    def _check_path(
        storage: object,
        path: str,
        *,
        label: str,
        progress: _SetupCheckProgress,
    ) -> None:
        exists = storage.exists(path)
        progress.complete(f"{label}.exists")
        if not exists:
            raise _SetupCheckFailure("missing_path", "configured Local root does not exist")
        entry = storage.stat(path)
        progress.complete(f"{label}.stat")
        if not entry.is_directory:
            raise _SetupCheckFailure("invalid_path", "configured Local root is not a directory")

    @classmethod
    def _progress_evidence(
        cls,
        revision: ManagedConfigurationRevision,
        *,
        actor: str,
        progress: _SetupCheckProgress,
        started: float,
        status: ConfigurationSetupCheckStatus,
        resource_library_id: str | None = None,
        media_library_id: str | None = None,
        failure_category: str | None = None,
        message: str | None = None,
        next_action: str | None = None,
    ) -> LocalSetupCheckEvidence:
        snapshot = progress.snapshot()
        return cls._evidence(
            revision,
            actor=actor,
            status=status,
            storage_ids=snapshot.storage_ids,
            resource_library_id=snapshot.resource_library_id or resource_library_id,
            media_library_id=snapshot.media_library_id or media_library_id,
            source_path=snapshot.source_path,
            destination_path=snapshot.destination_path,
            operations=snapshot.operations,
            duration_ms=_duration_ms(started),
            failure_category=failure_category,
            message=message,
            next_action=next_action,
        )

    @staticmethod
    def _evidence(
        revision: ManagedConfigurationRevision,
        *,
        actor: str,
        status: ConfigurationSetupCheckStatus,
        storage_ids: tuple[str, ...],
        resource_library_id: str | None,
        media_library_id: str | None,
        source_path: str | None,
        destination_path: str | None,
        operations: tuple[str, ...],
        duration_ms: int,
        failure_category: str | None = None,
        message: str | None = None,
        next_action: str | None = None,
    ) -> LocalSetupCheckEvidence:
        return LocalSetupCheckEvidence(
            revision.revision_id,
            revision.version,
            revision.digest,
            status,
            datetime.now(UTC),
            actor,
            storage_ids,
            resource_library_id,
            media_library_id,
            source_path,
            destination_path,
            operations,
            duration_ms,
            failure_category,
            message,
            next_action,
        )


@dataclass(frozen=True)
class _SetupCheckProgressSnapshot:
    storage_ids: tuple[str, ...]
    resource_library_id: str | None
    media_library_id: str | None
    source_path: str | None
    destination_path: str | None
    operations: tuple[str, ...]


class _SetupCheckProgress:
    def __init__(self) -> None:
        self._lock = Lock()
        self._storage_ids: tuple[str, ...] = ()
        self._resource_library_id: str | None = None
        self._media_library_id: str | None = None
        self._source_path: str | None = None
        self._destination_path: str | None = None
        self._operations: list[str] = []

    def select(
        self,
        *,
        storage_ids: tuple[str, ...],
        resource_library_id: str,
        media_library_id: str,
    ) -> None:
        with self._lock:
            self._storage_ids = storage_ids
            self._resource_library_id = resource_library_id
            self._media_library_id = media_library_id

    def paths(self, *, source: str, destination: str) -> None:
        with self._lock:
            self._source_path = source
            self._destination_path = destination

    def complete(self, operation: str) -> None:
        with self._lock:
            self._operations.append(operation)

    def snapshot(self) -> _SetupCheckProgressSnapshot:
        with self._lock:
            return _SetupCheckProgressSnapshot(
                self._storage_ids,
                self._resource_library_id,
                self._media_library_id,
                self._source_path,
                self._destination_path,
                tuple(self._operations),
            )


class _SetupCheckLease:
    """Release one capacity slot after work and response persistence both finish."""

    def __init__(self, release: Callable[[], None]) -> None:
        self._release = release
        self._lock = Lock()
        self._worker_done = False
        self._response_done = False
        self._released = False

    def worker_finished(self) -> None:
        self._finish(worker=True)

    def response_finished(self) -> None:
        self._finish(worker=False)

    def _finish(self, *, worker: bool) -> None:
        release = False
        with self._lock:
            if worker:
                self._worker_done = True
            else:
                self._response_done = True
            if self._worker_done and self._response_done and not self._released:
                self._released = True
                release = True
        if release:
            self._release()


class _SetupCheckFailure(RuntimeError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.message = message


class _ReferenceEvidenceCollector:
    """Build exact reference counts while retaining only bounded evidence."""

    _MAX_ITEMS = CONFIGURATION_REFERENCE_EVIDENCE_LIMIT

    def __init__(self) -> None:
        self._total = 0
        self._items: list[ConfigurationReferenceItem] = []

    def add(self, item: ConfigurationReferenceItem) -> None:
        self._total += 1
        if len(self._items) < self._MAX_ITEMS:
            self._items.append(item)

    def evidence(self) -> ConfigurationReferenceEvidence:
        return ConfigurationReferenceEvidence(
            total=self._total,
            items=tuple(self._items),
            truncated=self._total > len(self._items),
            max_items=self._MAX_ITEMS,
        )


def _duration_ms(started: float) -> int:
    return max(0, min(86_400_000, int((time.monotonic() - started) * 1000)))
