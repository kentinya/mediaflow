from __future__ import annotations

import copy
import json
import math
import posixpath
import re
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import PurePath
from threading import BoundedSemaphore, Lock, RLock
from typing import TYPE_CHECKING

from mediaflow.application import organizer as organizer_application
from mediaflow.application.classification import (
    ClassificationPolicyRegistry,
    ClassificationPreviewService,
)
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.conflict_resolution import ConflictResolutionError, ConflictResolver
from mediaflow.application.media_parser import MediaParserService
from mediaflow.application.naming import (
    NamingPolicyRegistry,
    NamingPreviewService,
    validate_naming_policy,
)
from mediaflow.application.policies import RecognitionTypePolicyResolver
from mediaflow.application.read_only_storage import (
    ReadOnlyStorageGuard,
    ReadOnlyStorageMutationError,
)
from mediaflow.application.strategy_test import (
    StrategyConfigurationError,
    StrategyTestResult,
    strategy_runner_from_configuration,
)
from mediaflow.domain.classification import (
    ClassificationContext,
    ClassificationError,
    ClassificationErrorCode,
    ClassificationPolicy,
    ClassificationResult,
    ClassificationRule,
)
from mediaflow.domain.configuration_management import (
    CONFIGURATION_REFERENCE_EVIDENCE_LIMIT,
    CONFIGURATION_SETUP_CHECK_PATH_LIMIT,
    CONFIGURATION_STRATEGY_RESULT_LIMIT,
    ClassificationPreviewEvidence,
    ConfigurationActivationConflict,
    ConfigurationClassificationPreviewStatus,
    ConfigurationDestinationPrecheckStatus,
    ConfigurationDestinationPreviewStatus,
    ConfigurationNamingPreviewStatus,
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationOrganizeAuthorityStatus,
    ConfigurationReferenceEvidence,
    ConfigurationReferenceItem,
    ConfigurationSetupCheckStatus,
    ConfigurationStrategyTestStatus,
    ConfigurationVersionConflict,
    DestinationPrecheckEvidence,
    DestinationPreviewEvidence,
    LocalSetupCheckEvidence,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
    ManagedDocumentRedactor,
    NamingPreviewEvidence,
    OrganizeAuthorityEvidence,
    RecognitionStrategyTestEvidence,
)
from mediaflow.domain.library import MediaLibrary
from mediaflow.domain.metadata import (
    METADATA_POLICY_CONFIGURATION_FIELDS,
    MediaIdentity,
    MediaQueryType,
    MediaType,
    MetadataErrorCode,
    MetadataIdentificationStatus,
    MetadataPolicy,
    RetryPolicy,
)
from mediaflow.domain.metadata_correction import MetadataCorrectionSelection
from mediaflow.domain.metadata_review import MetadataSelection
from mediaflow.domain.naming import (
    MissingVariableStrategy,
    NamingContext,
    NamingError,
    NamingErrorCode,
    NamingMediaTypeMode,
    NamingPolicy,
    NamingResult,
)
from mediaflow.domain.organizer import (
    ConflictStrategy,
    ConflictType,
    DestinationComposition,
    DirectoryCleanupMode,
    OrganizeOperationType,
    OrganizePolicy,
    compose_destination,
)
from mediaflow.domain.parser import FileContext, ParseResult
from mediaflow.domain.recognition import (
    AtomicCondition,
    ConditionField,
    ConditionOperator,
    LogicalCondition,
    LogicalOperator,
    PolicyReference,
    PolicyResolutionError,
    RecognitionResult,
    RecognitionStatus,
    RecognitionType,
    RecognitionTypePolicy,
    ResolvedRecognitionPolicy,
)
from mediaflow.domain.storage import StorageCapabilities, StorageError, StorageErrorCode
from mediaflow.infrastructure.metadata_provider_bootstrap import MetadataProviderBootstrapError
from mediaflow.infrastructure.runtime_configuration import (
    load_managed_runtime_configuration,
    load_runtime_configuration,
)
from mediaflow.infrastructure.strategy_user_configuration import parse_organize_policy

if TYPE_CHECKING:
    from mediaflow.application.metadata import MetadataProviderRegistry


def __getattr__(name: str) -> object:
    """Resolve the preserved Provider test double without a static class binding."""

    if name == "MetadataProviderRegistry":
        from mediaflow.application.metadata import MetadataProviderRegistry

        return MetadataProviderRegistry
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class _DestinationPreviewFailure(ValueError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


class _DestinationPrecheckMutationError(ReadOnlyStorageMutationError):
    pass


class _ReadOnlyDestinationStorage(ReadOnlyStorageGuard):
    _MAX_RECORDED_READS = 128

    def __init__(self, storage) -> None:
        super().__init__(storage)
        self.read_operations: list[str] = []
        self.read_operation_count = 0
        self.last_storage_error: StorageError | None = None

    def _record(self, operation: str, path: str) -> None:
        self.read_operation_count += 1
        if len(self.read_operations) < self._MAX_RECORDED_READS:
            self.read_operations.append(f"{operation}:{path}")

    def exists(self, path: str) -> bool:
        self._record("exists", path)
        try:
            return super().exists(path)
        except StorageError as error:
            self.last_storage_error = error
            raise

    def stat(self, path: str):
        self._record("stat", path)
        try:
            return super().stat(path)
        except StorageError as error:
            self.last_storage_error = error
            raise

    def _mutation_error(self, operation: str) -> _DestinationPrecheckMutationError:
        return _DestinationPrecheckMutationError(
            f"destination precheck forbids Storage mutation: {operation}"
        )


@dataclass(frozen=True)
class _DestinationResolution:
    normalized_input: dict[str, object]
    resolved: ResolvedRecognitionPolicy
    organize_policy: OrganizePolicy
    naming: NamingResult
    classification: ClassificationResult
    library: dict[str, object]
    composition: DestinationComposition


class ConfigurationObjectService:
    """Edit the three Phase 22.3 objects inside one managed Draft document."""

    _SECTIONS = {
        ConfigurationObjectKind.STORAGE: "storages",
        ConfigurationObjectKind.RESOURCE_LIBRARY: "resourceLibraries",
        ConfigurationObjectKind.MEDIA_LIBRARY: "mediaLibraries",
        ConfigurationObjectKind.RECOGNITION_TYPE: "recognitionTypes",
        ConfigurationObjectKind.RECOGNITION_RULE: "recognitionRules",
        ConfigurationObjectKind.RECOGNITION_TYPE_POLICY: "recognitionTypePolicies",
        ConfigurationObjectKind.METADATA_POLICY: "metadataPolicies",
        ConfigurationObjectKind.NAMING_POLICY: "namingPolicies",
        ConfigurationObjectKind.CLASSIFICATION_POLICY: "classificationPolicies",
        ConfigurationObjectKind.ORGANIZE_POLICY: "organizePolicies",
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
    _RECOGNITION_TYPE_FIELDS = {"id", "name", "description", "enabled"}
    _RECOGNITION_RULE_FIELDS = {
        "id",
        "name",
        "condition",
        "outputRecognitionType",
        "enabled",
        "priority",
        "score",
        "stopOnMatch",
        "description",
    }
    _RECOGNITION_TYPE_POLICY_FIELDS = {
        "id",
        "name",
        "recognitionType",
        "metadataPolicy",
        "namingPolicy",
        "classificationPolicy",
        "organizePolicy",
        "enabled",
        "priority",
    }
    _METADATA_POLICY_FIELDS = METADATA_POLICY_CONFIGURATION_FIELDS
    _NAMING_POLICY_FIELDS = {
        "id",
        "name",
        "description",
        "enabled",
        "mediaTypeMode",
        "directoryTemplate",
        "filenameTemplate",
        "seriesDirectoryTemplate",
        "seasonDirectoryTemplate",
        "episodeFilenameTemplate",
        "multiEpisodeFileTemplate",
        "missingVariableStrategy",
        "maxComponentLength",
    }
    _NAMING_SAMPLE_FIELDS = {
        "path",
        "title",
        "originalTitle",
        "mediaType",
        "recognitionType",
        "provider",
        "providerId",
        "year",
        "season",
        "episode",
        "episodes",
        "episodeTitle",
        "resolution",
        "source",
        "videoCodec",
        "audio",
        "hdr",
        "version",
        "releaseGroup",
        "extension",
    }
    _CLASSIFICATION_POLICY_FIELDS = {
        "id",
        "name",
        "description",
        "enabled",
        "priority",
        "rules",
    }
    _CLASSIFICATION_RULE_FIELDS = {
        "id",
        "name",
        "priority",
        "enabled",
        "confidence",
        "description",
        "conditions",
        "result",
    }
    _CLASSIFICATION_CONDITION_FIELDS = {
        "mediaType",
        "mediaTypes",
        "genres",
        "countries",
        "languages",
        "canonicalYear",
        "yearMin",
        "yearMax",
        "keywords",
    }
    _CLASSIFICATION_RESULT_FIELDS = {
        "mediaLibraryId",
        "library",
        "path",
        "category",
        "subcategory",
    }
    _CLASSIFICATION_SAMPLE_FIELDS = {
        "path",
        "title",
        "originalTitle",
        "mediaType",
        "recognitionType",
        "year",
        "genres",
        "countries",
        "languages",
        "keywords",
        "overview",
    }
    _ORGANIZE_POLICY_FIELDS = {
        "id",
        "operation",
        "conflictStrategy",
        "overwrite",
        "duplicateDetection",
        "rollback",
        "sourceDirectoryCleanup",
        "attachments",
    }

    def __init__(
        self,
        managed: ManagedConfigurationService,
        *,
        setup_check_timeout_seconds: float = _SETUP_CHECK_TIMEOUT_SECONDS,
        metadata_provider_registry_factory: (
            Callable[[tuple[str, ...]], MetadataProviderRegistry] | None
        ) = None,
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
        self._metadata_provider_registry_factory = metadata_provider_registry_factory
        self._strategy_test_operation_lock = RLock()
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
        self.require_current_strategy_test(revision)
        self.require_current_destination_precheck(revision)
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
                "mediaLibraries": (
                    self._objects(document, "mediaLibraries")
                    if "mediaLibraries" in document
                    else []
                ),
                "recognitionTypes": self._objects(document, "recognitionTypes"),
                "recognitionRules": self._objects(document, "recognitionRules"),
                "recognitionTypePolicies": self._objects(document, "recognitionTypePolicies"),
                "metadataPolicies": self._objects(document, "metadataPolicies"),
                "namingPolicies": (
                    self._objects(document, "namingPolicies")
                    if "namingPolicies" in document
                    else []
                ),
                "classificationPolicies": (
                    self._objects(document, "classificationPolicies")
                    if "classificationPolicies" in document
                    else []
                ),
                "organizePolicies": (
                    self._objects(document, "organizePolicies")
                    if "organizePolicies" in document
                    else []
                ),
            },
            # Keep every versioned projection on the same immutable revision read.
            # Calling the public helpers here would re-read the repository and could
            # combine objects from one Draft with evidence from a concurrent edit.
            "references": self._references_from_document(document),
            "localSetupCheck": self._check_document(revision),
            "recognitionStrategyTest": self._strategy_test_document(revision),
            "namingPreview": self._naming_preview_document(revision),
            "classificationPreview": self._classification_preview_document(revision),
            "organizeAuthority": self._organize_authority_document(revision),
            "destinationPreview": self._destination_preview_document(revision),
            "destinationPrecheck": self._destination_precheck_document(revision),
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
            # Historical lightweight repository doubles may omit newly editable
            # sections; canonical managed runtime documents still require them.
            if section not in document:
                continue
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

    def recognition_strategy_test(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
        resource_library_id: str,
        synthetic_path: str,
        live_metadata: bool = False,
    ) -> RecognitionStrategyTestEvidence:
        with self._strategy_test_operation_lock:
            return self._run_recognition_strategy_test(
                revision_id,
                expected_version=expected_version,
                expected_digest=expected_digest,
                actor=actor,
                resource_library_id=resource_library_id,
                synthetic_path=synthetic_path,
                live_metadata=live_metadata,
            )

    def naming_preview(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
        policy_id: str,
        sample: Mapping[str, object],
    ) -> NamingPreviewEvidence:
        revision = self._managed.require(revision_id)
        if revision.status not in {
            ManagedConfigurationStatus.DRAFT,
            ManagedConfigurationStatus.VALIDATED,
        }:
            raise ConfigurationVersionConflict(
                "naming preview requires a Draft or Validated revision",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
            )
        if revision.version != expected_version or revision.digest != expected_digest:
            raise ConfigurationVersionConflict(
                "naming preview requires the exact current revision; reload before previewing",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
                durable_state="current_draft_and_prior_preview_preserved",
                next_action="reload the revision and explicitly rerun naming preview",
            )
        normalized_input: dict[str, object] = {}
        try:
            if not isinstance(policy_id, str) or not policy_id.strip() or len(policy_id) > 64:
                raise ValueError("NamingPolicy ID must be bounded and non-empty")
            normalized_input, context = self._naming_context(sample)
            policies = tuple(
                self._naming_policy(value)
                for value in self._canonical_objects(revision.document, "namingPolicies")
            )
            result = NamingPreviewService(NamingPolicyRegistry(policies)).preview(
                context, policy_id
            )
            missing = [
                warning.split(":", 1)[1]
                for warning in result.warnings
                if warning.startswith("missing_variable:")
            ]
            policy = next(item for item in policies if item.policy_id == policy_id)
            result_document = {
                "appliedPolicyId": result.policy_id,
                "recognitionType": result.recognition_type_id,
                "mediaType": result.media_type.value if result.media_type else None,
                "directory": "/".join(result.directory_segments),
                "directorySegments": list(result.directory_segments),
                "filename": result.filename,
                "renderedVariables": {
                    key: self._bounded_utf8(value, 512)
                    for key, value in result.rendered_variables
                    if key != "episode_numbers"
                },
                "sanitizationChanges": list(result.sanitization_changes),
                "missingVariableStrategy": policy.missing_variable_strategy.value,
                "missingVariableDecisions": [
                    {
                        "variable": name,
                        "decision": policy.missing_variable_strategy.value,
                    }
                    for name in missing
                ],
                "warnings": [self._bounded_utf8(value, 384) for value in result.warnings[:32]],
            }
            evidence = NamingPreviewEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationNamingPreviewStatus.COMPLETED,
                datetime.now(UTC),
                actor,
                policy_id,
                normalized_input,
                result_document,
                message="Naming preview completed through the configured production naming engine",
                next_action=(
                    "review the rendered name, then correct and rerun or validate the Draft"
                ),
            )
        except (NamingError, ValueError) as error:
            category = error.code.value if isinstance(error, NamingError) else "invalid_input"
            evidence = NamingPreviewEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationNamingPreviewStatus.FAILED,
                datetime.now(UTC),
                actor,
                (
                    policy_id
                    if isinstance(policy_id, str) and policy_id.strip() and len(policy_id) <= 64
                    else "invalid"
                ),
                normalized_input or {"mode": "invalid"},
                failure_category=category,
                message=f"Naming preview failed ({category})",
                next_action=(
                    "correct the named policy field or sample, then explicitly rerun preview"
                ),
            )
        return self._repository.save_naming_preview(evidence)

    @classmethod
    def _naming_policy(cls, value: Mapping[str, object]) -> NamingPolicy:
        normalized = cls._normalize(ConfigurationObjectKind.NAMING_POLICY, value)
        return NamingPolicy(
            str(normalized["id"]),
            str(normalized["name"]),
            str(normalized["directoryTemplate"]),
            str(normalized["filenameTemplate"]),
            str(normalized["seriesDirectoryTemplate"]),
            str(normalized["seasonDirectoryTemplate"]),
            str(normalized["episodeFilenameTemplate"]),
            str(normalized["multiEpisodeFileTemplate"]),
            str(normalized["description"]),
            bool(normalized["enabled"]),
            NamingMediaTypeMode(str(normalized["mediaTypeMode"])),
            MissingVariableStrategy(str(normalized["missingVariableStrategy"])),
            max_component_length=int(normalized["maxComponentLength"]),
        )

    @classmethod
    def _naming_context(
        cls, sample: Mapping[str, object]
    ) -> tuple[dict[str, object], NamingContext]:
        if not isinstance(sample, Mapping):
            raise ValueError("naming preview sample must be an object")
        unknown = set(sample).difference(cls._NAMING_SAMPLE_FIELDS)
        if unknown:
            raise ValueError(
                f"naming preview sample contains unsupported field {sorted(unknown)[0]!r}"
            )
        path = sample.get("path")
        if path is not None:
            if (
                len(sample) != 1
                or not isinstance(path, str)
                or not path.strip()
                or len(path) > 4096
            ):
                raise ValueError("path mode requires one bounded non-empty path field")
            if "\x00" in path:
                raise ValueError("naming preview path must not contain NUL")
            pure = PurePath(path.replace("\\", "/"))
            filename = pure.name
            parsed = MediaParserService().parse(
                FileContext(
                    "offline-preview",
                    "offline-preview",
                    path,
                    filename,
                    tuple(pure.parts[:-1]),
                    filename.rsplit(".", 1)[1] if "." in filename else "",
                    str(pure.parent),
                )
            )
            media_type = (
                MediaType.TV
                if parsed.season is not None or parsed.episode is not None
                else MediaType.MOVIE
            )
            # Persist only the basename/parse mode. The operator-supplied path is
            # used locally by the parser and is not retained as preview evidence.
            normalized = {"mode": "path", "filename": filename}
            title = parsed.title_candidate
            recognition_type = "preview-tv" if media_type is MediaType.TV else "preview-movie"
            identity = MediaIdentity(
                "offline-preview",
                "synthetic",
                media_type,
                title,
                year=parsed.year,
                season=parsed.season,
                episode=parsed.episode,
                episodes=parsed.episodes,
                recognition_type_id=recognition_type,
            )
            return normalized, NamingContext(
                recognition_type, identity, parsed, filename, parsed.extension
            )
        title = cls._preview_text(sample.get("title"), "title", 512, required=True)
        media_type_value = sample.get("mediaType", "movie")
        try:
            media_type = MediaType(media_type_value)
        except (TypeError, ValueError) as error:
            raise ValueError("naming preview mediaType must be movie or tv") from error
        if media_type not in {MediaType.MOVIE, MediaType.TV}:
            raise ValueError("naming preview mediaType must be movie or tv")
        recognition_type = cls._preview_text(
            sample.get("recognitionType", "preview"), "recognitionType", 64, required=True
        )
        extension = cls._preview_text(
            sample.get("extension", "mkv"), "extension", 16, required=True
        )
        if not re.fullmatch(r"[A-Za-z0-9]{1,16}", extension):
            raise ValueError("naming preview extension is invalid")
        episodes_value = sample.get("episodes", [])
        if not isinstance(episodes_value, list) or len(episodes_value) > 32:
            raise ValueError("naming preview episodes must be a bounded array")
        episodes = tuple(cls._preview_int(item, "episode", 0, 9999) for item in episodes_value)
        year = cls._preview_optional_int(sample.get("year"), "year", 0, 9999)
        season = cls._preview_optional_int(sample.get("season"), "season", 0, 9999)
        episode = cls._preview_optional_int(sample.get("episode"), "episode", 0, 9999)
        parsed = ParseResult(
            title,
            year=year,
            season=season,
            episode=episode,
            episodes=episodes,
            resolution_tag=cls._preview_text(sample.get("resolution"), "resolution", 64),
            source_tag=cls._preview_text(sample.get("source"), "source", 64),
            video_codec_tag=cls._preview_text(sample.get("videoCodec"), "videoCodec", 64),
            audio_tag=cls._preview_text(sample.get("audio"), "audio", 64),
            hdr_tag=cls._preview_text(sample.get("hdr"), "hdr", 64),
            version_tag=cls._preview_text(sample.get("version"), "version", 64),
            release_group=cls._preview_text(sample.get("releaseGroup"), "releaseGroup", 128),
            original_filename=f"{title}.{extension}",
            extension=extension.lower(),
        )
        identity = MediaIdentity(
            cls._preview_text(
                sample.get("provider", "offline-preview"), "provider", 64, required=True
            ),
            cls._preview_text(
                sample.get("providerId", "synthetic"), "providerId", 128, required=True
            ),
            media_type,
            title,
            original_title=cls._preview_text(sample.get("originalTitle"), "originalTitle", 512),
            year=year,
            season=season,
            episode=episode,
            episodes=episodes,
            episode_title=cls._preview_text(sample.get("episodeTitle"), "episodeTitle", 512),
            recognition_type_id=recognition_type,
        )
        normalized = {"mode": "synthetic", **copy.deepcopy(dict(sample))}
        return normalized, NamingContext(
            recognition_type, identity, parsed, parsed.original_filename, parsed.extension
        )

    @staticmethod
    def _preview_text(
        value: object, label: str, maximum: int, *, required: bool = False
    ) -> str | None:
        if value is None and not required:
            return None
        if (
            not isinstance(value, str)
            or (required and not value.strip())
            or len(value) > maximum
            or "\x00" in value
        ):
            raise ValueError(f"naming preview {label} must be bounded text")
        return value

    @staticmethod
    def _preview_int(value: object, label: str, minimum: int, maximum: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"naming preview {label} is out of bounds")
        return value

    @classmethod
    def _preview_optional_int(
        cls, value: object, label: str, minimum: int, maximum: int
    ) -> int | None:
        return None if value is None else cls._preview_int(value, label, minimum, maximum)

    def classification_preview(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
        policy_id: str,
        sample: Mapping[str, object],
    ) -> ClassificationPreviewEvidence:
        revision = self._managed.require(revision_id)
        if revision.status not in {
            ManagedConfigurationStatus.DRAFT,
            ManagedConfigurationStatus.VALIDATED,
        }:
            raise ConfigurationVersionConflict(
                "classification preview requires a Draft or Validated revision",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
            )
        if revision.version != expected_version or revision.digest != expected_digest:
            raise ConfigurationVersionConflict(
                "classification preview requires the exact current revision; "
                "reload before previewing",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
                durable_state="current_draft_and_prior_preview_preserved",
                next_action="reload the revision and explicitly rerun classification preview",
            )
        normalized_input: dict[str, object] = {}
        try:
            if not isinstance(policy_id, str) or not policy_id.strip() or len(policy_id) > 64:
                raise ValueError("ClassificationPolicy ID must be bounded and non-empty")
            normalized_input, context = self._classification_context(sample)
            policies = tuple(
                self._classification_policy(value)
                for value in self._canonical_objects(revision.document, "classificationPolicies")
            )
            result = ClassificationPreviewService(ClassificationPolicyRegistry(policies)).preview(
                context, policy_id
            )
            media_library_ids = {
                str(item.get("id"))
                for item in self._canonical_objects(revision.document, "mediaLibraries")
            }
            resolved = (
                bool(result.media_library_id) and result.media_library_id in media_library_ids
            )
            warnings = list(result.warnings)
            if result.media_library_id and not resolved:
                warnings.append(f"unresolved_media_library:{result.media_library_id}")
            result_document = {
                "appliedPolicyId": result.policy_id,
                "recognitionType": result.recognition_type_id,
                "status": result.status.value,
                "matchedRuleId": result.matched_rule_id,
                "matchedRuleName": result.matched_rule_name,
                "mediaLibraryId": result.media_library_id or None,
                "mediaLibraryResolved": resolved,
                "relativePath": result.relative_path or None,
                "library": result.library,
                "category": result.category,
                "subcategory": result.subcategory,
                "confidence": result.confidence,
                "matchEvidence": [self._bounded_utf8(value, 384) for value in result.evidence[:32]],
                "warnings": [self._bounded_utf8(value, 384) for value in warnings[:32]],
                "reason": (
                    "no enabled classification rule matched the sample"
                    if result.status.value == "unclassified"
                    else "highest-priority matching rule selected"
                ),
            }
            next_action = (
                "adjust the rule conditions or sample, then explicitly rerun classification preview"
                if result.status.value == "unclassified"
                else (
                    "add or correct the MediaLibrary in this Draft, then rerun "
                    "classification preview"
                    if not resolved
                    else "review the classification explanation, then correct and rerun "
                    "or validate the Draft"
                )
            )
            evidence = ClassificationPreviewEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationClassificationPreviewStatus.COMPLETED,
                datetime.now(UTC),
                actor,
                policy_id,
                normalized_input,
                result_document,
                message="Classification preview completed through the configured production engine",
                next_action=next_action,
            )
        except (ClassificationError, ValueError) as error:
            category = (
                error.code.value if isinstance(error, ClassificationError) else "invalid_input"
            )
            evidence = ClassificationPreviewEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationClassificationPreviewStatus.FAILED,
                datetime.now(UTC),
                actor,
                (
                    policy_id
                    if isinstance(policy_id, str) and policy_id.strip() and len(policy_id) <= 64
                    else "invalid"
                ),
                normalized_input or {"mode": "invalid"},
                failure_category=category,
                message=f"Classification preview failed ({category})",
                next_action=(
                    "correct the policy or sample, then explicitly rerun classification preview"
                ),
            )
        return self._repository.save_classification_preview(evidence)

    def organize_authority(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
        recognition_type: str,
    ) -> OrganizeAuthorityEvidence:
        revision = self._managed.require(revision_id)
        if revision.status not in {
            ManagedConfigurationStatus.DRAFT,
            ManagedConfigurationStatus.VALIDATED,
        }:
            raise ConfigurationVersionConflict(
                "organize authority explanation requires a Draft or Validated revision",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
            )
        if revision.version != expected_version or revision.digest != expected_digest:
            raise ConfigurationVersionConflict(
                "organize authority explanation requires the exact current revision; "
                "reload before explaining",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
                durable_state="current_draft_and_prior_organize_authority_preserved",
                next_action="reload the revision and explicitly rerun organize authority",
            )
        if (
            not isinstance(recognition_type, str)
            or not recognition_type.strip()
            or len(recognition_type) > 64
            or "\x00" in recognition_type
        ):
            raise ValueError("organize authority RecognitionType must be bounded and non-empty")

        try:
            resolver, organize_policies = self._policy_resolution_catalog(revision.document)
            resolved = resolver.resolve(RecognitionType(recognition_type, recognition_type))
            policy = organize_policies[resolved.organize_policy_id]
            cleanup_enabled = policy.source_directory_cleanup.mode is not DirectoryCleanupMode.NONE
            overwrite = policy.conflict_strategy is ConflictStrategy.OVERWRITE
            delete_authorized = overwrite or cleanup_enabled
            required_capabilities = self._required_storage_capabilities(policy)
            warnings: list[str] = []
            if overwrite:
                warnings.append(
                    "conflictStrategy=overwrite grants explicit destination replacement authority"
                )
            if cleanup_enabled:
                warnings.append(
                    "sourceDirectoryCleanup grants explicit source-directory delete authority"
                )
            if policy.operation is OrganizeOperationType.MOVE and not policy.rollback.enabled:
                warnings.append("rollback is disabled for Move; partial effects may remain")
            if policy.operation in {
                OrganizeOperationType.HARD_LINK,
                OrganizeOperationType.SOFT_LINK,
            }:
                warnings.append(
                    f"{policy.operation.value} has no fallback to Copy or Move; unsupported "
                    "capability is a failure"
                )
            result = {
                "recognitionType": resolved.recognition_type_id,
                "recognitionTypePolicyId": resolved.type_policy_id,
                "organizePolicyId": policy.policy_id,
                "operation": policy.operation.value,
                "conflictStrategy": policy.conflict_strategy.value,
                "overwriteAuthorized": overwrite,
                "deleteAuthorized": delete_authorized,
                "attachments": self._attachment_document(policy),
                "duplicateDetection": self._hash_document(policy),
                "rollback": self._rollback_document(policy),
                "sourceDirectoryCleanup": self._cleanup_document(policy),
                "requiredStorageCapabilities": required_capabilities,
                "fallback": "none; unsupported capability is a failure",
                "warnings": warnings,
            }
            evidence = OrganizeAuthorityEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationOrganizeAuthorityStatus.COMPLETED,
                datetime.now(UTC),
                actor,
                recognition_type,
                result,
                message="Organize authority resolved through the production policy resolver",
                next_action=(
                    "review each destructive warning, then correct and rerun or validate the Draft"
                    if warnings
                    else (
                        "review the declared authority, then correct and rerun or validate "
                        "the Draft"
                    )
                ),
            )
        except PolicyResolutionError as error:
            evidence = OrganizeAuthorityEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationOrganizeAuthorityStatus.FAILED,
                datetime.now(UTC),
                actor,
                recognition_type,
                failure_category=error.code.value,
                message=self._bounded_utf8(str(error), 384),
                next_action=(
                    "add, enable, deduplicate or repoint the RecognitionTypePolicy in this Draft, "
                    "then explicitly rerun organize authority"
                ),
            )
        return self._repository.save_organize_authority(evidence)

    def destination_preview(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
        recognition_type: str,
        sample: Mapping[str, object],
    ) -> DestinationPreviewEvidence:
        revision = self._managed.require(revision_id)
        if revision.status not in {
            ManagedConfigurationStatus.DRAFT,
            ManagedConfigurationStatus.VALIDATED,
        }:
            raise ConfigurationVersionConflict(
                "destination preview requires a Draft or Validated revision",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
            )
        if revision.version != expected_version or revision.digest != expected_digest:
            raise ConfigurationVersionConflict(
                "destination preview requires the exact current revision; reload before previewing",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
                durable_state="current_draft_and_prior_destination_preview_preserved",
                next_action="reload the revision and explicitly rerun destination preview",
            )
        self._validate_destination_request(recognition_type, sample, "destination preview")

        normalized_input: dict[str, object] = {}
        resolution_state: dict[str, object] = {}
        try:
            resolution = self._resolve_destination(
                revision.document,
                recognition_type,
                sample,
                normalized_input,
                resolution_state,
            )
            resolved = resolution.resolved
            naming = resolution.naming
            classification = resolution.classification
            library = resolution.library
            composition = resolution.composition
            result = {
                "recognitionType": resolved.recognition_type_id,
                "recognitionTypePolicyId": resolved.type_policy_id,
                "namingPolicyId": resolved.naming_policy_id,
                "classificationPolicyId": resolved.classification_policy_id,
                "mediaLibraryId": classification.media_library_id,
                "mediaLibraryStorageId": str(library.get("storageId", "")),
                "mediaLibraryRootPath": composition.media_library_root,
                "classificationRuleId": classification.matched_rule_id,
                "classificationRelativePath": classification.relative_path,
                "namingDirectorySegments": list(naming.directory_segments),
                "namingFilename": naming.filename,
                "rootRelativeDestination": composition.relative_destination,
                "composedStorageRelativeDestination": composition.target,
            }
            evidence = DestinationPreviewEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationDestinationPreviewStatus.COMPLETED,
                datetime.now(UTC),
                actor,
                recognition_type,
                normalized_input,
                result,
                message="Destination preview completed through the production composition rules",
                next_action=(
                    "review every attributed contribution, then correct and rerun or validate "
                    "the Draft"
                ),
            )
        except (PolicyResolutionError, NamingError, ClassificationError, ValueError) as error:
            resolved = resolution_state.get("resolved")
            if isinstance(error, (PolicyResolutionError, NamingError, ClassificationError)):
                category = error.code.value
            elif isinstance(error, _DestinationPreviewFailure):
                category = error.category
            else:
                category = "invalid_input"
            if isinstance(error, _DestinationPreviewFailure):
                message = str(error)
            elif isinstance(error, NamingError):
                message = f"NamingPolicy {resolved.naming_policy_id!r} failed ({category})"
            elif isinstance(error, ClassificationError):
                message = (
                    f"ClassificationPolicy {resolved.classification_policy_id!r} "
                    f"failed ({category})"
                )
            elif isinstance(error, PolicyResolutionError):
                message = f"RecognitionTypePolicy resolution failed ({category})"
            else:
                message = f"Destination preview failed ({category})"
            evidence = DestinationPreviewEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationDestinationPreviewStatus.FAILED,
                datetime.now(UTC),
                actor,
                recognition_type,
                normalized_input or {"mode": "invalid"},
                failure_category=category,
                message=self._bounded_utf8(message, 384),
                next_action=(
                    "correct the named mapping, policy, MediaLibrary, sample or path contribution "
                    "in this Draft, then explicitly rerun destination preview"
                ),
            )
        return self._repository.save_destination_preview(evidence)

    def _validate_destination_request(
        self, recognition_type: str, sample: Mapping[str, object], label: str
    ) -> None:
        if (
            not isinstance(recognition_type, str)
            or not recognition_type.strip()
            or len(recognition_type) > 64
            or "\x00" in recognition_type
        ):
            raise ValueError(f"{label} RecognitionType must be bounded and non-empty")
        if not isinstance(sample, Mapping):
            raise ValueError(f"{label} sample must be an object")
        allowed = self._NAMING_SAMPLE_FIELDS | self._CLASSIFICATION_SAMPLE_FIELDS
        if any(not isinstance(key, str) or len(key) > 64 for key in sample):
            raise ValueError(f"{label} sample field names must be bounded text")
        if unknown := set(sample).difference(allowed):
            raise ValueError(f"{label} sample contains unsupported field {sorted(unknown)[0]!r}")
        if "path" in sample and len(sample) != 1:
            raise ValueError(f"{label} path mode accepts only the path field")

    def _resolve_destination(
        self,
        document: Mapping[str, object],
        recognition_type: str,
        sample: Mapping[str, object],
        normalized_input: dict[str, object],
        resolution_state: dict[str, object] | None = None,
    ) -> _DestinationResolution:
        resolver, organize_policies = self._policy_resolution_catalog(document)
        resolved = resolver.resolve(RecognitionType(recognition_type, recognition_type))
        if resolution_state is not None:
            resolution_state["resolved"] = resolved
        if "path" in sample:
            naming_sample = classification_sample = dict(sample)
        else:
            naming_sample = {
                key: copy.deepcopy(value)
                for key, value in sample.items()
                if key in self._NAMING_SAMPLE_FIELDS
            }
            classification_sample = {
                key: copy.deepcopy(value)
                for key, value in sample.items()
                if key in self._CLASSIFICATION_SAMPLE_FIELDS
            }
            naming_sample["recognitionType"] = recognition_type
            classification_sample["recognitionType"] = recognition_type
        naming_input, naming_context = self._naming_context(naming_sample)
        _, classification_context = self._classification_context(classification_sample)
        normalized_input.update(
            naming_input
            if "path" in sample
            else {"mode": "synthetic", **copy.deepcopy(dict(sample))}
        )
        naming_identity = replace(
            naming_context.media_identity, recognition_type_id=recognition_type
        )
        naming_context = replace(
            naming_context,
            recognition_type_id=recognition_type,
            media_identity=naming_identity,
        )
        classification_identity = replace(
            classification_context.media_identity, recognition_type_id=recognition_type
        )
        classification_context = replace(
            classification_context,
            recognition_type=resolved.recognition_type,
            media_identity=classification_identity,
        )
        naming_policies = tuple(
            self._naming_policy(value)
            for value in self._canonical_objects(document, "namingPolicies")
        )
        naming = NamingPreviewService(NamingPolicyRegistry(naming_policies)).preview(
            naming_context, resolved.naming_policy_id
        )
        classification_policies = tuple(
            self._classification_policy(value)
            for value in self._canonical_objects(document, "classificationPolicies")
        )
        classification = ClassificationPreviewService(
            ClassificationPolicyRegistry(classification_policies)
        ).preview(classification_context, resolved.classification_policy_id)
        if classification.status.value != "classified":
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                "no enabled classification rule matched the destination sample",
            )
        libraries = {
            str(value.get("id")): value
            for value in self._canonical_objects(document, "mediaLibraries")
        }
        library = libraries.get(classification.media_library_id)
        if library is None:
            raise _DestinationPreviewFailure(
                "unresolved_media_library",
                f"MediaLibrary {classification.media_library_id!r} is unresolved",
            )
        root_path = library.get("rootPath")
        if not isinstance(root_path, str):
            raise _DestinationPreviewFailure(
                "unsafe_destination",
                f"MediaLibrary {classification.media_library_id!r}.rootPath is unsafe",
            )
        composition = compose_destination(
            root_path,
            classification.relative_path,
            naming.directory,
            naming.directory_segments,
            naming.filename,
        )
        if not composition.safe:
            owners = {
                "mediaLibrary.rootPath": f"MediaLibrary:{classification.media_library_id}",
                "classification.relativePath": (
                    f"ClassificationPolicy:{resolved.classification_policy_id}"
                ),
                "naming.directory": f"NamingPolicy:{resolved.naming_policy_id}",
                "naming.filename": f"NamingPolicy:{resolved.naming_policy_id}",
            }
            contribution = composition.unsafe_contribution or "destination"
            owner = owners.get(contribution, f"NamingPolicy:{resolved.naming_policy_id}")
            raise _DestinationPreviewFailure(
                "unsafe_destination", f"unsafe contribution {contribution!r} owned by {owner}"
            )
        return _DestinationResolution(
            normalized_input,
            resolved,
            organize_policies[resolved.organize_policy_id],
            naming,
            classification,
            library,
            composition,
        )

    def destination_precheck(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
        recognition_type: str,
        sample: Mapping[str, object] | None = None,
        samples: Sequence[Mapping[str, object]] | None = None,
    ) -> DestinationPrecheckEvidence:
        if (sample is None) == (samples is None):
            raise ValueError("destination precheck requires exactly one of sample or samples")
        revision = self._managed.require(revision_id)
        if revision.status not in {
            ManagedConfigurationStatus.DRAFT,
            ManagedConfigurationStatus.VALIDATED,
        }:
            raise ConfigurationVersionConflict(
                "destination precheck requires a Draft or Validated revision",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
            )
        if revision.version != expected_version or revision.digest != expected_digest:
            raise ConfigurationVersionConflict(
                "destination precheck requires the exact current revision; reload before checking",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
                durable_state="current_draft_and_prior_destination_precheck_preserved",
                next_action="reload the revision and explicitly rerun destination precheck",
            )
        request_samples: list[Mapping[str, object]] = (
            [sample] if sample is not None else list(samples or ())
        )
        if not 1 <= len(request_samples) <= 8:
            raise ValueError("destination precheck accepts one to eight sample objects")
        for index, item in enumerate(request_samples):
            self._validate_destination_request(
                recognition_type, item, f"destination precheck sample[{index}]"
            )
        normalized_input: dict[str, object] = {}
        resolutions: list[tuple[int, _DestinationResolution]] = []
        precomposed_rows: list[tuple[int, dict[str, object]]] = []
        for index, item in enumerate(request_samples):
            sample_input: dict[str, object] = {}
            resolution_state: dict[str, object] = {}
            try:
                resolution = self._resolve_destination(
                    revision.document,
                    recognition_type,
                    item,
                    sample_input,
                    resolution_state,
                )
            except (PolicyResolutionError, NamingError, ClassificationError, ValueError) as error:
                if not normalized_input:
                    normalized_input = sample_input
                resolved = resolution_state.get("resolved")
                category, message = self._destination_failure_details(
                    error,
                    resolved if isinstance(resolved, ResolvedRecognitionPolicy) else None,
                )
                precomposed_rows.append(
                    (index, self._destination_sample_failure_row(index, category, message))
                )
            else:
                if not normalized_input:
                    normalized_input = sample_input
                resolutions.append((index, resolution))
        if not resolutions:
            first_index, first_row = precomposed_rows[0]
            evidence = self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                normalized_input,
                str(first_row["failureCategory"]),
                str(first_row["message"]),
                "fix the composition in this Draft, rerun destination preview, then rerun precheck",
                result=self._destination_multi_result(
                    len(request_samples),
                    [row for _, row in sorted(precomposed_rows)],
                    [],
                ),
            )
            return self._repository.save_destination_precheck(evidence)

        storage_values = {
            str(value.get("id")): value
            for value in self._canonical_objects(revision.document, "storages")
        }
        storage_ids = [
            str(resolution.library.get("storageId", "")) for _, resolution in resolutions
        ]
        if any(storage_id not in storage_values for storage_id in storage_ids):
            evidence = self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                normalized_input,
                "invalid_configuration",
                "destination Storage is unresolved",
                "add or correct the destination Storage in this Draft, then rerun precheck",
            )
            return self._repository.save_destination_precheck(evidence)
        if any(
            str(storage_values[storage_id].get("type", "")).lower() != "local"
            for storage_id in storage_ids
        ):
            offending = next(
                storage_id
                for storage_id in storage_ids
                if str(storage_values[storage_id].get("type", "")).lower() != "local"
            )
            evidence = self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                normalized_input,
                "unsupported_storage_type",
                f"Storage {offending!r} is not supported; destination precheck is Local-only",
                "point the MediaLibrary at Local Storage or wait for remote precheck support",
            )
            return self._repository.save_destination_precheck(evidence)
        if len(set(storage_ids)) != 1:
            labels = ", ".join(
                f"{storage_id}:{str(storage_values[storage_id].get('type', '')).lower()}"
                for storage_id in sorted(set(storage_ids))
            )
            rows = [row for _, row in sorted(precomposed_rows)] + [
                self._destination_sample_resolution_row(index, resolution)
                for index, resolution in sorted(resolutions)
            ]
            rows = sorted(rows, key=lambda row: int(row["index"]))
            evidence = self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                normalized_input,
                "multiple_destination_storages",
                (
                    "destination samples route to multiple destination Storages "
                    f"({labels}); precheck one destination Storage at a time"
                ),
                (
                    "narrow the samples to one destination Storage and precheck each "
                    "destination Storage separately, then rerun"
                ),
                result=self._destination_multi_result(len(request_samples), rows, []),
            )
            return self._repository.save_destination_precheck(evidence)
        storage_id = storage_ids[0]
        if not self._acquire_setup_check():
            return self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                normalized_input,
                "capacity_unavailable",
                "destination precheck capacity is occupied by an unfinished check",
                "wait for the in-flight check to finish, then rerun destination precheck",
            )
        try:
            future = self._setup_check_executor.submit(
                self._run_destination_precheck,
                revision,
                actor,
                recognition_type,
                tuple(resolutions),
                storage_id,
                precomposed_rows,
                normalized_input,
            )
        except Exception:
            self._release_setup_check()
            evidence = self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                normalized_input,
                "unavailable",
                "destination precheck worker is unavailable",
                "inspect service health, then rerun destination precheck",
            )
            return self._repository.save_destination_precheck(evidence)
        lease = _SetupCheckLease(self._release_setup_check)
        future.add_done_callback(lambda _future: lease.worker_finished())
        try:
            try:
                evidence = future.result(timeout=self._setup_check_timeout_seconds)
            except FutureTimeoutError:
                evidence = self._destination_precheck_failure(
                    revision,
                    actor,
                    recognition_type,
                    normalized_input,
                    "timeout",
                    "destination precheck exceeded its overall deadline",
                    "wait for the in-flight check to finish, fix availability, then rerun",
                )
            except Exception:
                evidence = self._destination_precheck_failure(
                    revision,
                    actor,
                    recognition_type,
                    normalized_input,
                    "unavailable",
                    "destination precheck worker failed (details redacted)",
                    "inspect service health and configuration, then rerun precheck",
                )
            return self._repository.save_destination_precheck(evidence)
        finally:
            lease.response_finished()

    def _run_destination_precheck(
        self,
        revision: ManagedConfigurationRevision,
        actor: str,
        recognition_type: str,
        resolutions: Sequence[tuple[int, _DestinationResolution]],
        storage_id: str,
        precomposed_rows: Sequence[tuple[int, dict[str, object]]] = (),
        normalized_input: dict[str, object] | None = None,
    ) -> DestinationPrecheckEvidence:
        if len(resolutions) == 1 and not precomposed_rows:
            return self._run_single_destination_precheck(
                revision,
                actor,
                recognition_type,
                resolutions[0][1],
                storage_id,
            )
        return self._run_multi_destination_precheck(
            revision,
            actor,
            recognition_type,
            resolutions,
            storage_id,
            precomposed_rows,
            normalized_input or {},
        )

    def _run_single_destination_precheck(
        self,
        revision: ManagedConfigurationRevision,
        actor: str,
        recognition_type: str,
        resolution: _DestinationResolution,
        storage_id: str,
    ) -> DestinationPrecheckEvidence:
        guard: _ReadOnlyDestinationStorage | None = None
        try:
            if self._managed.bootstrap_database_path is not None:
                runtime = load_managed_runtime_configuration(
                    revision.document,
                    bootstrap_database_path=self._managed.bootstrap_database_path,
                )
            else:
                runtime = load_runtime_configuration(revision.document)
            created = runtime.create_storages(storage_ids={storage_id})
            adapter = created.get(storage_id)
            if adapter is None:
                raise _DestinationPreviewFailure(
                    "invalid_configuration", "Local destination Storage was not created"
                )
            capabilities = adapter.capabilities
            guard = _ReadOnlyDestinationStorage(adapter)
            root = resolution.composition.media_library_root
            root_exists = guard.exists(root)
            if not root_exists:
                return self._destination_precheck_failure(
                    revision,
                    actor,
                    recognition_type,
                    resolution.normalized_input,
                    "missing_destination_root",
                    "configured MediaLibrary root does not exist",
                    "create the root out of band or correct MediaLibrary.rootPath, then rerun",
                    result=self._destination_probe_identity(resolution, storage_id, False, False),
                )
            root_entry = guard.stat(root)
            if not root_entry.is_directory:
                return self._destination_precheck_failure(
                    revision,
                    actor,
                    recognition_type,
                    resolution.normalized_input,
                    "destination_root_not_directory",
                    "configured MediaLibrary root is not a directory",
                    "correct MediaLibrary.rootPath, then rerun destination precheck",
                    result=self._destination_probe_identity(resolution, storage_id, True, False),
                )
            parent = posixpath.dirname(resolution.composition.relative_destination)
            segments = [] if not parent else parent.split("/")
            if len(segments) > 64:
                raise _DestinationPreviewFailure(
                    "invalid_path", "destination ancestor depth exceeds 64 segments"
                )
            deepest = root
            directories_to_create: list[str] = []
            for index, segment in enumerate(segments):
                candidate = posixpath.join(root, *segments[: index + 1])
                if guard.exists(candidate):
                    if not guard.stat(candidate).is_directory:
                        raise _DestinationPreviewFailure(
                            "invalid_path", "an existing destination ancestor is not a directory"
                        )
                    deepest = candidate
                    continue
                directories_to_create = [
                    posixpath.join(root, *segments[: offset + 1])
                    for offset in range(index, len(segments))
                ]
                break
            policy = resolution.organize_policy
            type_policy = RecognitionTypePolicy(
                resolution.resolved.type_policy_id,
                resolution.resolved.recognition_type,
                resolution.resolved.metadata_policy_id,
                resolution.resolved.naming_policy_id,
                resolution.resolved.classification_policy_id,
                policy,
            )
            plan = organizer_application.OrganizePlanner().plan(
                source_storage_id="destination-precheck-source",
                source="destination-precheck-source.mkv",
                recognition=RecognitionResult(
                    resolution.resolved.recognition_type, "destination-precheck"
                ),
                type_policy=type_policy,
                media_library=MediaLibrary(
                    str(resolution.library.get("id")),
                    str(resolution.library.get("name") or resolution.library.get("id")),
                    storage_id,
                    root,
                ),
                naming=resolution.naming,
                classification=resolution.classification,
                media_identity=None,
                target_storage=guard,
                claimed_destinations=None,
                known_media=None,
            )
            if guard.last_storage_error is not None:
                raise guard.last_storage_error
            if any(
                conflict.type is ConflictType.INVALID_DESTINATION for conflict in plan.conflicts
            ):
                raise _DestinationPreviewFailure(
                    "unsafe_destination",
                    "planner rejected the composed destination as unsafe",
                )
            conflicts = [conflict.type.value for conflict in plan.conflicts]
            target_exists = ConflictType.DESTINATION_EXISTS in {
                conflict.type for conflict in plan.conflicts
            }
            resolved_plan = ConflictResolver().apply_configured(plan, policy, guard)
            if guard.last_storage_error is not None:
                raise guard.last_storage_error
            if not plan.conflicts:
                projected = "ready"
            elif policy.conflict_strategy is ConflictStrategy.SKIP:
                projected = "skip"
            elif policy.conflict_strategy is ConflictStrategy.RENAME:
                projected = "rename"
            elif policy.conflict_strategy is ConflictStrategy.OVERWRITE:
                projected = "overwrite_requires_confirmation"
            else:
                projected = "manual_confirmation_required"
            proposed = (
                resolved_plan.relative_destination
                if projected == "rename" and resolved_plan is not None
                else None
            )
            required = self._required_storage_capabilities(policy)
            declared = self._capability_names(capabilities)
            missing = [value for value in required if value not in declared]
            verdict = "capability_gap" if missing else projected
            if guard is not None and any(guard.mutation_calls.values()):
                raise _DestinationPrecheckMutationError("guard counted a forbidden mutation")
            result = {
                **self._destination_probe_identity(resolution, storage_id, True, True),
                "relativeDestination": resolution.composition.relative_destination,
                "destinationPath": resolution.composition.target,
                "deepestExistingAncestor": deepest,
                "directoriesToCreate": directories_to_create,
                "targetExists": target_exists,
                "conflictProjection": {
                    "configuredStrategy": policy.conflict_strategy.value,
                    "plannerConflicts": conflicts,
                    "projectedOutcome": projected,
                    "proposedRelativeDestination": proposed,
                },
                "requiredStorageCapabilities": required,
                "destinationStorageCapabilities": declared,
                "missingStorageCapabilities": missing,
                "requiredByOperation": policy.operation.value,
                "fallback": "none; an unsupported capability is a failure",
                "probeOperations": list(guard.read_operations),
                "probeOperationCount": guard.read_operation_count,
                "probeOperationsTruncated": (
                    guard.read_operation_count > len(guard.read_operations)
                ),
                "guardMutationCalls": dict(guard.mutation_calls),
                "verdict": verdict,
                "authorityGranted": "none",
                "sampleCount": 1,
                "items": [
                    {
                        "index": 0,
                        "relativeDestination": resolution.composition.relative_destination,
                        "destinationPath": resolution.composition.target,
                        "targetExists": target_exists,
                        "plannerConflicts": conflicts,
                        "projectedOutcome": projected,
                        "proposedRelativeDestination": proposed,
                        "failureCategory": None,
                        "message": None,
                    }
                ],
                "collisions": [],
            }
            return DestinationPrecheckEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationDestinationPrecheckStatus.COMPLETED,
                datetime.now(UTC),
                actor,
                recognition_type,
                resolution.normalized_input,
                result,
                message=(
                    "Destination capability gap detected; there is no fallback"
                    if missing
                    else "Destination precheck completed with read-only observations"
                ),
                next_action=(
                    "change the operation or destination Storage, then rerun precheck"
                    if missing
                    else "review the projected outcome, then correct and rerun or validate"
                ),
            )
        except StorageError as error:
            category = self._storage_failure_category(error.code)
            return self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                resolution.normalized_input,
                category,
                "destination precheck could not read the configured Local path",
                "correct availability, permissions or path, then rerun destination precheck",
            )
        except _DestinationPrecheckMutationError:
            return self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                resolution.normalized_input,
                "read_only_violation",
                "destination precheck attempted a forbidden Storage mutation",
                "do not activate; inspect the destination-precheck implementation",
            )
        except (ConflictResolutionError, _DestinationPreviewFailure) as error:
            category = (
                error.category if isinstance(error, _DestinationPreviewFailure) else "invalid"
            )
            return self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                resolution.normalized_input,
                category,
                "destination precheck could not safely project the destination",
                "correct the destination or conflict policy, then rerun precheck",
            )
        except Exception:
            return self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                resolution.normalized_input,
                "unavailable",
                "destination precheck failed (details redacted)",
                "inspect service health and configuration, then rerun precheck",
            )

    def _run_multi_destination_precheck(
        self,
        revision: ManagedConfigurationRevision,
        actor: str,
        recognition_type: str,
        resolutions: Sequence[tuple[int, _DestinationResolution]],
        storage_id: str,
        precomposed_rows: Sequence[tuple[int, dict[str, object]]],
        normalized_input: dict[str, object],
    ) -> DestinationPrecheckEvidence:
        guard: _ReadOnlyDestinationStorage | None = None
        rows: list[tuple[int, dict[str, object]]] = list(precomposed_rows)
        first_details: dict[str, object] | None = None
        any_missing = False
        claimed: dict[str, str] = {}
        claimed_indexes: dict[str, int] = {}
        collision_indexes: dict[str, list[int]] = {}
        try:
            if self._managed.bootstrap_database_path is not None:
                runtime = load_managed_runtime_configuration(
                    revision.document,
                    bootstrap_database_path=self._managed.bootstrap_database_path,
                )
            else:
                runtime = load_runtime_configuration(revision.document)
            created = runtime.create_storages(storage_ids={storage_id})
            adapter = created.get(storage_id)
            if adapter is None:
                raise _DestinationPreviewFailure(
                    "invalid_configuration", "Local destination Storage was not created"
                )
            capabilities = adapter.capabilities
            guard = _ReadOnlyDestinationStorage(adapter)
            for index, resolution in resolutions:
                try:
                    row, details = self._probe_destination_sample(
                        resolution,
                        storage_id,
                        guard,
                        capabilities,
                        claimed,
                        claimed_indexes,
                        collision_indexes,
                        index,
                    )
                except StorageError as error:
                    category = self._storage_failure_category(error.code)
                    row = self._destination_sample_failure_row(
                        index,
                        category,
                        "destination precheck could not read the configured Local path",
                    )
                except _DestinationPrecheckMutationError:
                    raise
                except (ConflictResolutionError, _DestinationPreviewFailure) as error:
                    category = (
                        error.category
                        if isinstance(error, _DestinationPreviewFailure)
                        else "invalid"
                    )
                    row = self._destination_sample_failure_row(
                        index,
                        category,
                        "destination precheck could not safely project the destination",
                    )
                except Exception:
                    row = self._destination_sample_failure_row(
                        index,
                        "unavailable",
                        "destination precheck failed (details redacted)",
                    )
                rows.append((index, row))
                if row["failureCategory"] is None:
                    if first_details is None:
                        first_details = details
                    if details["missingStorageCapabilities"]:
                        any_missing = True
            if guard is not None and any(guard.mutation_calls.values()):
                raise _DestinationPrecheckMutationError("guard counted a forbidden mutation")
        except StorageError as error:
            category = self._storage_failure_category(error.code)
            items = [row for _, row in sorted(rows)]
            guard_calls = dict(guard.mutation_calls) if guard is not None else {}
            return self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                normalized_input,
                category,
                "destination precheck could not read the configured Local path",
                "correct availability, permissions or path, then rerun destination precheck",
                result={
                    **self._destination_multi_result(len(items), items, []),
                    "guardMutationCalls": guard_calls,
                    "authorityGranted": "none",
                },
            )
        except _DestinationPrecheckMutationError:
            items = [row for _, row in sorted(rows)]
            guard_calls = dict(guard.mutation_calls) if guard is not None else {}
            return self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                normalized_input,
                "read_only_violation",
                "destination precheck attempted a forbidden Storage mutation",
                "do not activate; inspect the destination-precheck implementation",
                result={
                    **self._destination_multi_result(len(items), items, []),
                    "guardMutationCalls": guard_calls,
                    "authorityGranted": "none",
                },
            )
        except Exception:
            items = [row for _, row in sorted(rows)]
            guard_calls = dict(guard.mutation_calls) if guard is not None else {}
            return self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                normalized_input,
                "unavailable",
                "destination precheck failed (details redacted)",
                "inspect service health and configuration, then rerun precheck",
                result={
                    **self._destination_multi_result(len(items), items, []),
                    "guardMutationCalls": guard_calls,
                    "authorityGranted": "none",
                },
            )

        items = [row for _, row in sorted(rows)]
        collisions = [
            {"destinationPath": target, "itemIndexes": indexes}
            for target, indexes in sorted(collision_indexes.items())
        ]
        guard_calls = dict(guard.mutation_calls) if guard is not None else {}
        if collisions:
            return self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                normalized_input,
                "duplicate_destination",
                (
                    f"{len(collisions)} cross-item destination collision(s) detected; "
                    "distinct samples compose the same destination"
                ),
                (
                    "add a distinguishing naming variable or correct the naming/classification "
                    "policy so distinct inputs compose distinct destinations, then rerun "
                    "the precheck"
                ),
                result={
                    **self._destination_multi_result(len(items), items, collisions),
                    "guardMutationCalls": guard_calls,
                    "authorityGranted": "none",
                },
            )
        failures = sorted(
            (index, str(row["failureCategory"]), str(row["message"]))
            for index, row in rows
            if row["failureCategory"] is not None
        )
        if failures:
            index, category, message = failures[0]
            return self._destination_precheck_failure(
                revision,
                actor,
                recognition_type,
                normalized_input,
                category,
                message,
                self._destination_sample_next_action(category),
                result={
                    **self._destination_multi_result(len(items), items, collisions),
                    "guardMutationCalls": guard_calls,
                    "authorityGranted": "none",
                },
            )
        first_index, first_resolution = resolutions[0]
        assert first_details is not None
        severity = {
            "ready": 0,
            "skip": 1,
            "rename": 2,
            "overwrite_requires_confirmation": 3,
            "manual_confirmation_required": 4,
        }
        outcomes = [
            str(row["projectedOutcome"]) for _, row in rows if row["projectedOutcome"] is not None
        ]
        verdict = (
            "capability_gap" if any_missing else max(outcomes, key=lambda value: severity[value])
        )
        result = {
            **self._destination_probe_identity(first_resolution, storage_id, True, True),
            **first_details,
            "verdict": verdict,
            "sampleCount": len(items),
            "items": items,
            "collisions": collisions,
        }
        return DestinationPrecheckEvidence(
            revision.revision_id,
            revision.version,
            revision.digest,
            ConfigurationDestinationPrecheckStatus.COMPLETED,
            datetime.now(UTC),
            actor,
            recognition_type,
            normalized_input,
            result,
            message=(
                "Destination capability gap detected; there is no fallback"
                if any_missing
                else "Destination precheck completed with read-only observations"
            ),
            next_action=(
                "change the operation or destination Storage, then rerun precheck"
                if any_missing
                else "review the projected outcome, then correct and rerun or validate"
            ),
        )

    def _probe_destination_sample(
        self,
        resolution: _DestinationResolution,
        storage_id: str,
        guard: _ReadOnlyDestinationStorage,
        capabilities: StorageCapabilities,
        claimed: dict[str, str],
        claimed_indexes: dict[str, int],
        collision_indexes: dict[str, list[int]],
        index: int,
    ) -> tuple[dict[str, object], dict[str, object]]:
        root = resolution.composition.media_library_root
        if not guard.exists(root):
            raise _DestinationPreviewFailure(
                "missing_destination_root", "configured MediaLibrary root does not exist"
            )
        root_entry = guard.stat(root)
        if not root_entry.is_directory:
            raise _DestinationPreviewFailure(
                "destination_root_not_directory",
                "configured MediaLibrary root is not a directory",
            )
        parent = posixpath.dirname(resolution.composition.relative_destination)
        segments = [] if not parent else parent.split("/")
        if len(segments) > 64:
            raise _DestinationPreviewFailure(
                "invalid_path", "destination ancestor depth exceeds 64 segments"
            )
        deepest = root
        directories_to_create: list[str] = []
        for segment_index, segment in enumerate(segments):
            candidate = posixpath.join(root, *segments[: segment_index + 1])
            if guard.exists(candidate):
                if not guard.stat(candidate).is_directory:
                    raise _DestinationPreviewFailure(
                        "invalid_path", "an existing destination ancestor is not a directory"
                    )
                deepest = candidate
                continue
            directories_to_create = [
                posixpath.join(root, *segments[: offset + 1])
                for offset in range(segment_index, len(segments))
            ]
            break
        policy = resolution.organize_policy
        type_policy = RecognitionTypePolicy(
            resolution.resolved.type_policy_id,
            resolution.resolved.recognition_type,
            resolution.resolved.metadata_policy_id,
            resolution.resolved.naming_policy_id,
            resolution.resolved.classification_policy_id,
            policy,
        )
        source = f"destination-precheck-source-{index}.mkv"
        plan = organizer_application.OrganizePlanner().plan(
            source_storage_id="destination-precheck-source",
            source=source,
            recognition=RecognitionResult(
                resolution.resolved.recognition_type, "destination-precheck"
            ),
            type_policy=type_policy,
            media_library=MediaLibrary(
                str(resolution.library.get("id")),
                str(resolution.library.get("name") or resolution.library.get("id")),
                storage_id,
                root,
            ),
            naming=resolution.naming,
            classification=resolution.classification,
            media_identity=None,
            target_storage=guard,
            claimed_destinations=claimed,
            known_media=None,
        )
        if guard.last_storage_error is not None:
            raise guard.last_storage_error
        if any(conflict.type is ConflictType.INVALID_DESTINATION for conflict in plan.conflicts):
            raise _DestinationPreviewFailure(
                "unsafe_destination",
                "planner rejected the composed destination as unsafe",
            )
        target = plan.target
        conflicts = [conflict.type.value for conflict in plan.conflicts]
        target_exists = ConflictType.DESTINATION_EXISTS in {
            conflict.type for conflict in plan.conflicts
        }
        resolved_plan = ConflictResolver().apply_configured(plan, policy, guard)
        if guard.last_storage_error is not None:
            raise guard.last_storage_error
        if not plan.conflicts:
            projected = "ready"
        elif policy.conflict_strategy is ConflictStrategy.SKIP:
            projected = "skip"
        elif policy.conflict_strategy is ConflictStrategy.RENAME:
            projected = "rename"
        elif policy.conflict_strategy is ConflictStrategy.OVERWRITE:
            projected = "overwrite_requires_confirmation"
        else:
            projected = "manual_confirmation_required"
        proposed = (
            resolved_plan.relative_destination
            if projected == "rename" and resolved_plan is not None
            else None
        )
        required = self._required_storage_capabilities(policy)
        declared = self._capability_names(capabilities)
        missing = [value for value in required if value not in declared]
        verdict = "capability_gap" if missing else projected
        if any(guard.mutation_calls.values()):
            raise _DestinationPrecheckMutationError("guard counted a forbidden mutation")
        prior = claimed_indexes.get(target)
        if prior is None:
            claimed[target] = source
            claimed_indexes[target] = index
        else:
            collision_indexes.setdefault(target, [prior]).append(index)
        row: dict[str, object] = {
            "index": index,
            "relativeDestination": resolution.composition.relative_destination,
            "destinationPath": target,
            "targetExists": target_exists,
            "plannerConflicts": conflicts,
            "projectedOutcome": projected,
            "proposedRelativeDestination": proposed,
            "failureCategory": None,
            "message": None,
        }
        details: dict[str, object] = {
            "relativeDestination": resolution.composition.relative_destination,
            "destinationPath": target,
            "deepestExistingAncestor": deepest,
            "directoriesToCreate": directories_to_create,
            "targetExists": target_exists,
            "conflictProjection": {
                "configuredStrategy": policy.conflict_strategy.value,
                "plannerConflicts": conflicts,
                "projectedOutcome": projected,
                "proposedRelativeDestination": proposed,
            },
            "requiredStorageCapabilities": required,
            "destinationStorageCapabilities": declared,
            "missingStorageCapabilities": missing,
            "requiredByOperation": policy.operation.value,
            "fallback": "none; an unsupported capability is a failure",
            "probeOperations": list(guard.read_operations),
            "probeOperationCount": guard.read_operation_count,
            "probeOperationsTruncated": (guard.read_operation_count > len(guard.read_operations)),
            "guardMutationCalls": dict(guard.mutation_calls),
            "verdict": verdict,
            "authorityGranted": "none",
        }
        return row, details

    @staticmethod
    def _destination_sample_failure_row(
        index: int, category: str, message: str
    ) -> dict[str, object]:
        return {
            "index": index,
            "relativeDestination": None,
            "destinationPath": None,
            "targetExists": None,
            "plannerConflicts": [],
            "projectedOutcome": None,
            "proposedRelativeDestination": None,
            "failureCategory": category,
            "message": ConfigurationObjectService._bounded_utf8(message, 384),
            "nextAction": ConfigurationObjectService._destination_sample_next_action(category),
        }

    @staticmethod
    def _destination_sample_resolution_row(
        index: int, resolution: _DestinationResolution
    ) -> dict[str, object]:
        return {
            "index": index,
            "relativeDestination": resolution.composition.relative_destination,
            "destinationPath": resolution.composition.target,
            "targetExists": None,
            "plannerConflicts": [],
            "projectedOutcome": None,
            "proposedRelativeDestination": None,
            "failureCategory": None,
            "message": None,
            "nextAction": None,
        }

    @staticmethod
    def _destination_multi_result(
        sample_count: int,
        items: list[dict[str, object]],
        collisions: list[dict[str, object]],
    ) -> dict[str, object]:
        return {
            "sampleCount": sample_count,
            "items": items,
            "collisions": collisions,
        }

    @classmethod
    def _destination_sample_next_action(cls, category: str) -> str:
        return {
            "missing_destination_root": (
                "create the root out of band or correct MediaLibrary.rootPath, then rerun"
            ),
            "destination_root_not_directory": (
                "correct MediaLibrary.rootPath, then rerun destination precheck"
            ),
            "read_only_violation": (
                "do not activate; inspect the destination-precheck implementation"
            ),
            "permission_denied": (
                "correct availability, permissions or path, then rerun destination precheck"
            ),
            "unavailable": ("inspect service health and configuration, then rerun precheck"),
            "timeout": ("wait for the in-flight check to finish, fix availability, then rerun"),
        }.get(category, "correct the destination or conflict policy, then rerun precheck")

    @staticmethod
    def _destination_probe_identity(
        resolution: _DestinationResolution,
        storage_id: str,
        root_exists: bool,
        root_is_directory: bool,
    ) -> dict[str, object]:
        return {
            "recognitionType": resolution.resolved.recognition_type_id,
            "recognitionTypePolicyId": resolution.resolved.type_policy_id,
            "organizePolicyId": resolution.organize_policy.policy_id,
            "destinationStorageId": storage_id,
            "destinationStorageType": "local",
            "storageSupport": "local_only",
            "mediaLibraryId": str(resolution.library.get("id")),
            "mediaLibraryRootPath": resolution.composition.media_library_root,
            "destinationRootExists": root_exists,
            "destinationRootIsDirectory": root_is_directory,
        }

    @staticmethod
    def _required_storage_capabilities(policy: OrganizePolicy) -> list[str]:
        values = {
            OrganizeOperationType.MOVE: ["can_move"],
            OrganizeOperationType.COPY: ["can_copy"],
            OrganizeOperationType.HARD_LINK: ["can_hard_link"],
            OrganizeOperationType.SOFT_LINK: ["can_soft_link"],
        }[policy.operation]
        cleanup = policy.source_directory_cleanup.mode is not DirectoryCleanupMode.NONE
        if policy.conflict_strategy is ConflictStrategy.OVERWRITE or cleanup:
            values.append("can_delete")
        return values

    @staticmethod
    def _capability_names(capabilities: StorageCapabilities) -> list[str]:
        return [
            name
            for name in (
                "can_move",
                "can_copy",
                "can_delete",
                "can_hard_link",
                "can_soft_link",
            )
            if getattr(capabilities, name)
        ]

    @staticmethod
    def _storage_failure_category(code: StorageErrorCode) -> str:
        return {
            StorageErrorCode.PERMISSION_DENIED: "permission_denied",
            StorageErrorCode.TIMEOUT: "timeout",
            StorageErrorCode.CONNECTION_FAILED: "unavailable",
            StorageErrorCode.CONNECTION_LOST: "unavailable",
            StorageErrorCode.INVALID_PATH: "invalid_path",
            StorageErrorCode.PATH_TRAVERSAL: "invalid_path",
        }.get(code, "unavailable")

    @classmethod
    def _destination_precheck_failure(
        cls,
        revision: ManagedConfigurationRevision,
        actor: str,
        recognition_type: str,
        normalized_input: dict[str, object],
        category: str,
        message: str,
        next_action: str,
        *,
        result: dict[str, object] | None = None,
    ) -> DestinationPrecheckEvidence:
        return DestinationPrecheckEvidence(
            revision.revision_id,
            revision.version,
            revision.digest,
            ConfigurationDestinationPrecheckStatus.FAILED,
            datetime.now(UTC),
            actor,
            recognition_type,
            normalized_input or {"mode": "invalid"},
            result,
            failure_category=category,
            message=cls._bounded_utf8(message, 384),
            next_action=cls._bounded_utf8(next_action, 500),
        )

    @staticmethod
    def _destination_failure_details(
        error: Exception, resolved: ResolvedRecognitionPolicy | None
    ) -> tuple[str, str]:
        if isinstance(error, (PolicyResolutionError, NamingError, ClassificationError)):
            category = error.code.value
        elif isinstance(error, _DestinationPreviewFailure):
            category = error.category
        else:
            category = "invalid_input"
        if isinstance(error, _DestinationPreviewFailure):
            message = str(error)
        elif isinstance(error, NamingError) and resolved is not None:
            message = f"NamingPolicy {resolved.naming_policy_id!r} failed ({category})"
        elif isinstance(error, ClassificationError) and resolved is not None:
            message = (
                f"ClassificationPolicy {resolved.classification_policy_id!r} failed ({category})"
            )
        elif isinstance(error, PolicyResolutionError):
            message = f"RecognitionTypePolicy resolution failed ({category})"
        else:
            message = f"Destination composition failed ({category})"
        return category, message

    def _policy_resolution_catalog(
        self, document: Mapping[str, object]
    ) -> tuple[RecognitionTypePolicyResolver, dict[str, OrganizePolicy]]:
        types = {
            str(value["id"]): RecognitionType(
                str(value["id"]),
                str(value.get("name") or value["id"]),
                str(value.get("description", "")),
                bool(value.get("enabled", True)),
            )
            for value in self._canonical_objects(document, "recognitionTypes")
        }
        organize_policies = {
            policy.policy_id: policy
            for policy in (
                self._organize_policy(value)
                for value in self._canonical_objects(document, "organizePolicies")
            )
        }
        type_policies: list[RecognitionTypePolicy] = []
        for value in self._canonical_objects(document, "recognitionTypePolicies"):
            normalized = self._normalize(ConfigurationObjectKind.RECOGNITION_TYPE_POLICY, value)
            type_id = str(normalized["recognitionType"])
            known_type = types.get(type_id, RecognitionType(type_id, type_id))
            organize_id = str(normalized["organizePolicy"])
            organize = organize_policies.get(
                organize_id, OrganizePolicy(organize_id, OrganizeOperationType.MOVE)
            )
            type_policies.append(
                RecognitionTypePolicy(
                    str(normalized["id"]),
                    known_type,
                    str(normalized["metadataPolicy"]),
                    str(normalized["namingPolicy"]),
                    str(normalized["classificationPolicy"]),
                    organize,
                    str(normalized["name"]),
                    bool(normalized["enabled"]),
                    int(normalized["priority"]),
                )
            )

        def references(section: str) -> dict[str, PolicyReference]:
            return {
                str(value["id"]): PolicyReference(
                    str(value["id"]), bool(value.get("enabled", True))
                )
                for value in self._canonical_objects(document, section)
            }

        return (
            RecognitionTypePolicyResolver(
                type_policies,
                metadata_policies=references("metadataPolicies"),
                naming_policies=references("namingPolicies"),
                classification_policies=references("classificationPolicies"),
                organize_policies={key: PolicyReference(key) for key in organize_policies},
            ),
            organize_policies,
        )

    @classmethod
    def _organize_policy(cls, value: Mapping[str, object]) -> OrganizePolicy:
        normalized = cls._normalize(ConfigurationObjectKind.ORGANIZE_POLICY, value)
        return parse_organize_policy(normalized)

    @staticmethod
    def _attachment_document(policy: OrganizePolicy) -> dict[str, object]:
        value = policy.attachments
        return {
            "enabled": value.enabled,
            "subtitles": value.subtitles,
            "nfo": value.nfo,
            "artwork": value.artwork,
            "trailers": value.trailers,
            "otherSameStem": value.other_same_stem,
        }

    @staticmethod
    def _hash_document(policy: OrganizePolicy) -> dict[str, object]:
        value = policy.duplicate_detection
        return {
            "mode": value.mode.value,
            "fastSampleBytes": value.fast_sample_bytes,
            "fullMaxFileSize": value.full_max_file_size,
            "chunkSize": value.chunk_size,
        }

    @staticmethod
    def _rollback_document(policy: OrganizePolicy) -> dict[str, object]:
        value = policy.rollback
        return {
            "enabled": value.enabled,
            "cleanupCreatedDirectories": value.cleanup_created_directories,
        }

    @staticmethod
    def _cleanup_document(policy: OrganizePolicy) -> dict[str, object]:
        value = policy.source_directory_cleanup
        return {
            "mode": value.mode.value,
            "maxParentDirectories": value.max_parent_directories,
            "ignorePatterns": list(value.ignore_patterns),
            "maxEntries": value.max_entries,
        }

    @classmethod
    def _classification_context(
        cls, sample: Mapping[str, object]
    ) -> tuple[dict[str, object], ClassificationContext]:
        if not isinstance(sample, Mapping):
            raise ValueError("classification preview sample must be an object")
        unknown = set(sample).difference(cls._CLASSIFICATION_SAMPLE_FIELDS)
        if unknown:
            raise ValueError(
                f"classification preview sample contains unsupported field {sorted(unknown)[0]!r}"
            )
        path = sample.get("path")
        if path is not None:
            if not isinstance(path, str) or not path.strip() or len(path) > 4096 or "\x00" in path:
                raise ValueError("classification preview path must be bounded non-empty text")
            pure = PurePath(path.replace("\\", "/"))
            parsed_path = MediaParserService().parse(
                FileContext(
                    "offline-preview",
                    "offline-preview",
                    path,
                    pure.name,
                    tuple(pure.parts[:-1]),
                    pure.name.rsplit(".", 1)[1] if "." in pure.name else "",
                    str(pure.parent),
                )
            )
            normalized: dict[str, object] = {
                "mode": "path",
                "filename": pure.name,
            }
            title_default = parsed_path.title_candidate
            year_default = parsed_path.year
        else:
            parsed_path = None
            normalized = {"mode": "synthetic", **copy.deepcopy(dict(sample))}
            title_default = None
            year_default = None
        title = cls._preview_text(sample.get("title", title_default), "title", 512, required=True)
        media_type_value = sample.get("mediaType", "movie")
        try:
            media_type = MediaType(media_type_value)
        except (TypeError, ValueError) as error:
            raise ValueError("classification preview mediaType must be movie or tv") from error
        if media_type not in {MediaType.MOVIE, MediaType.TV}:
            raise ValueError("classification preview mediaType must be movie or tv")
        recognition_id = cls._preview_text(
            sample.get("recognitionType", "preview"),
            "recognitionType",
            64,
            required=True,
        )
        year = cls._preview_optional_int(sample.get("year", year_default), "year", 0, 9999)

        def strings(field: str) -> tuple[str, ...]:
            value = sample.get(field, [])
            if not isinstance(value, list) or len(value) > 64:
                raise ValueError(f"classification preview {field} must be a bounded array")
            return tuple(cls._preview_text(item, field, 200, required=True) or "" for item in value)

        parsed = parsed_path or ParseResult(
            title or "",
            year=year,
            original_filename=f"{title}.mkv",
            extension="mkv",
        )
        identity = MediaIdentity(
            "offline-preview",
            "synthetic",
            media_type,
            title or "",
            original_title=cls._preview_text(sample.get("originalTitle"), "originalTitle", 512),
            year=year,
            genres=strings("genres"),
            countries=strings("countries"),
            languages=strings("languages"),
            keywords=strings("keywords"),
            overview=cls._preview_text(sample.get("overview"), "overview", 2000),
            recognition_type_id=recognition_id,
        )
        recognition_type = RecognitionType(recognition_id or "preview", recognition_id or "preview")
        return normalized, ClassificationContext(recognition_type, identity, parsed)

    @classmethod
    def _classification_policy(cls, value: Mapping[str, object]) -> ClassificationPolicy:
        normalized = cls._normalize(ConfigurationObjectKind.CLASSIFICATION_POLICY, value)
        return ClassificationPolicy(
            str(normalized["id"]),
            str(normalized["name"]),
            tuple(cls._classification_rule(item)[0] for item in normalized["rules"]),
            str(normalized["description"]),
            bool(normalized["enabled"]),
            int(normalized["priority"]),
        )

    def recognition_strategy_select_candidate(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        expected_tested_at: str,
        candidate_rank: int,
        actor: str,
    ) -> RecognitionStrategyTestEvidence:
        if (
            isinstance(candidate_rank, bool)
            or not isinstance(candidate_rank, int)
            or candidate_rank < 1
            or candidate_rank > 5
        ):
            raise ValueError("candidate rank must be between 1 and 5")
        if not isinstance(expected_tested_at, str) or not expected_tested_at.strip():
            raise ValueError("expected Strategy Test evidence time is required")
        with self._strategy_test_operation_lock:
            revision = self._managed.require(revision_id)
            if (
                revision.status is not ManagedConfigurationStatus.VALIDATED
                or revision.version != expected_version
                or revision.digest != expected_digest
            ):
                raise ConfigurationVersionConflict(
                    "candidate confirmation requires the exact current Validated revision",
                    revision_id=revision_id,
                    current_version=revision.version,
                    current_digest=revision.digest,
                )
            evidence = self._repository.get_recognition_strategy_test(revision_id)
            if (
                evidence is None
                or evidence.revision_version != revision.version
                or evidence.revision_digest != revision.digest
                or evidence.tested_at.isoformat() != expected_tested_at
            ):
                raise ConfigurationVersionConflict(
                    "Strategy Test evidence changed; reload before confirming a candidate",
                    revision_id=revision_id,
                    current_version=revision.version,
                    current_digest=revision.digest,
                )
            result = evidence.result
            if not isinstance(result, dict) or result.get("mode") != "live":
                raise ValueError("candidate confirmation requires current live Metadata evidence")
            metadata = result.get("metadata")
            match = metadata.get("match") if isinstance(metadata, dict) else None
            if (
                not isinstance(metadata, dict)
                or metadata.get("status") not in {"need_confirm", "ambiguous"}
                or not isinstance(match, dict)
                or match.get("status") not in {"need_confirm", "ambiguous"}
            ):
                raise ValueError(
                    "candidate confirmation requires NeedConfirm or Ambiguous Metadata evidence"
                )
            candidates = match.get("candidates")
            if not isinstance(candidates, list) or candidate_rank > len(candidates):
                raise ValueError("candidate rank is not present in the persisted evidence")
            candidate = candidates[candidate_rank - 1]
            recognition = result.get("recognition")
            policy = result.get("policy")
            if not all(isinstance(item, dict) for item in (candidate, recognition, policy)):
                raise ValueError("persisted candidate evidence is malformed")
            provider = candidate.get("provider")
            provider_id = candidate.get("providerId")
            media_type = candidate.get("mediaType")
            recognition_type = recognition.get("recognitionType")
            metadata_policy_id = policy.get("metadataPolicy")
            if not all(
                isinstance(value, str) and value
                for value in (
                    provider,
                    provider_id,
                    media_type,
                    recognition_type,
                    metadata_policy_id,
                )
            ) or media_type not in {"movie", "tv"}:
                raise ValueError("persisted candidate evidence is malformed")
            selection = MetadataSelection(
                recognition_type,
                metadata_policy_id,
                provider,
                provider_id,
                media_type,
            )
            selection_document = {
                "rank": candidate_rank,
                "sourceOutcome": metadata["status"],
                "provider": provider,
                "providerId": provider_id,
                "mediaType": media_type,
            }
            correction_context = metadata.get("correction")
            if correction_context is not None and not isinstance(correction_context, dict):
                raise ValueError("persisted Metadata correction evidence is malformed")
            return self._run_recognition_strategy_test(
                revision_id,
                expected_version=expected_version,
                expected_digest=expected_digest,
                actor=actor,
                resource_library_id=evidence.resource_library_id,
                synthetic_path=evidence.synthetic_path,
                live_metadata=True,
                metadata_selection=selection,
                candidate_selection=selection_document,
                correction_context=correction_context,
                expected_evidence_tested_at=evidence.tested_at,
            )

    def recognition_strategy_correct_metadata(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        expected_tested_at: str,
        media_type: str,
        query: str | None,
        year: int | None,
        provider_id: str | None,
        actor: str,
    ) -> RecognitionStrategyTestEvidence:
        normalized_query = self._correction_text(query, 500, "corrected query")
        normalized_provider_id = self._correction_text(provider_id, 200, "direct Provider ID")
        if bool(normalized_query) == bool(normalized_provider_id):
            raise ValueError("provide exactly one corrected query or direct Provider ID")
        if normalized_provider_id and not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}", normalized_provider_id
        ):
            raise ValueError("direct Provider ID is invalid")
        if year is not None and (
            normalized_provider_id
            or isinstance(year, bool)
            or not isinstance(year, int)
            or not 1870 <= year <= 2100
        ):
            raise ValueError(
                "corrected year must be between 1870 and 2100 and is valid only with a query"
            )
        if not isinstance(media_type, str) or media_type not in {
            MediaType.MOVIE.value,
            MediaType.TV.value,
        }:
            raise ValueError("corrected media type must be movie or tv")
        if (
            not isinstance(expected_tested_at, str)
            or not expected_tested_at.strip()
            or len(expected_tested_at) > 64
            or "\x00" in expected_tested_at
        ):
            raise ValueError("expected Strategy Test evidence time is required")

        with self._strategy_test_operation_lock:
            revision = self._managed.require(revision_id)
            if (
                revision.status is not ManagedConfigurationStatus.VALIDATED
                or revision.version != expected_version
                or revision.digest != expected_digest
            ):
                raise ConfigurationVersionConflict(
                    "Metadata correction requires the exact current Validated revision",
                    revision_id=revision_id,
                    current_version=revision.version,
                    current_digest=revision.digest,
                )
            evidence = self._repository.get_recognition_strategy_test(revision_id)
            if (
                evidence is None
                or evidence.revision_version != revision.version
                or evidence.revision_digest != revision.digest
                or evidence.tested_at.isoformat() != expected_tested_at
            ):
                raise ConfigurationVersionConflict(
                    "Strategy Test evidence changed; reload before running Metadata correction",
                    revision_id=revision_id,
                    current_version=revision.version,
                    current_digest=revision.digest,
                )
            result = evidence.result
            metadata = result.get("metadata") if isinstance(result, dict) else None
            recognition = result.get("recognition") if isinstance(result, dict) else None
            policy = result.get("policy") if isinstance(result, dict) else None
            effective = result.get("effectiveMetadataPolicy") if isinstance(result, dict) else None
            if not isinstance(result, dict) or result.get("mode") != "live":
                raise ValueError("Metadata correction requires current live Metadata evidence")
            correctable_outcomes = {
                "not_found",
                "need_confirm",
                "ambiguous",
            }
            metadata_status = metadata.get("status") if isinstance(metadata, dict) else None
            prior_correction = metadata.get("correction") if isinstance(metadata, dict) else None
            correction_failure = (
                metadata_status in {"provider_error", "configuration_error"}
                and isinstance(prior_correction, dict)
                and prior_correction.get("sourceOutcome") in correctable_outcomes
            )
            if metadata_status not in correctable_outcomes and not correction_failure:
                raise ValueError(
                    "Metadata correction requires a current correctable outcome or a persisted "
                    "correction Provider failure"
                )
            if not all(isinstance(item, dict) for item in (recognition, policy, effective)):
                raise ValueError("persisted Metadata correction evidence is malformed")
            recognition_type = recognition.get("recognitionType")
            metadata_policy_id = policy.get("metadataPolicy")
            provider = effective.get("providerId")
            if (
                not all(
                    isinstance(value, str) and value
                    for value in (recognition_type, metadata_policy_id, provider)
                )
                or effective.get("id") != metadata_policy_id
                or (correction_failure and prior_correction.get("provider") != provider)
            ):
                raise ValueError("persisted Metadata correction policy evidence is malformed")
            try:
                runtime = load_managed_runtime_configuration(
                    revision.document,
                    bootstrap_database_path=self._managed.bootstrap_database_path
                    or self._repository.database_path,
                )
                library = next(
                    (
                        item
                        for item in runtime.resource_libraries
                        if item.library_id == evidence.resource_library_id and item.enabled
                    ),
                    None,
                )
                if library is None:
                    raise ValueError
                current = strategy_runner_from_configuration(runtime.strategy).run_path(
                    evidence.synthetic_path,
                    resource_library_id=library.library_id,
                    storage_id=library.storage_id,
                )
            except (StrategyConfigurationError, ValueError) as error:
                raise ValueError(
                    "current revision no longer supports the persisted Metadata correction"
                ) from error
            if (
                current.policy is None
                or current.metadata_policy is None
                or current.recognition.recognition_type_id != recognition_type
                or current.policy.metadata_policy_id != metadata_policy_id
                or current.metadata_policy.provider_id != provider
                or current.metadata_policy.query_type is MediaQueryType.NONE
            ):
                raise ValueError(
                    "persisted Metadata correction no longer matches the effective policy"
                )
            selection = MetadataCorrectionSelection(
                recognition_type,
                metadata_policy_id,
                provider,
                normalized_query,
                year,
                media_type,
                normalized_provider_id,
            )
            context: dict[str, object] = {
                "mode": "direct_provider_id" if normalized_provider_id else "query",
                "sourceOutcome": (
                    prior_correction["sourceOutcome"] if correction_failure else metadata_status
                ),
                "mediaType": media_type,
                "provider": provider,
            }
            if normalized_provider_id:
                context["providerId"] = normalized_provider_id
            else:
                context["query"] = normalized_query
                context["year"] = year
            return self._run_recognition_strategy_test(
                revision_id,
                expected_version=expected_version,
                expected_digest=expected_digest,
                actor=actor,
                resource_library_id=evidence.resource_library_id,
                synthetic_path=evidence.synthetic_path,
                live_metadata=True,
                metadata_correction=selection,
                correction_context=context,
                expected_evidence_tested_at=evidence.tested_at,
            )

    @staticmethod
    def _correction_text(value: str | None, maximum: int, label: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"{label} must be text")
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > maximum or "\x00" in normalized:
            raise ValueError(f"{label} must be bounded and NUL-free")
        return normalized

    def _run_recognition_strategy_test(
        self,
        revision_id: str,
        *,
        expected_version: int,
        expected_digest: str,
        actor: str,
        resource_library_id: str,
        synthetic_path: str,
        live_metadata: bool = False,
        metadata_selection: MetadataSelection | None = None,
        metadata_correction: MetadataCorrectionSelection | None = None,
        candidate_selection: dict[str, object] | None = None,
        correction_context: dict[str, object] | None = None,
        expected_evidence_tested_at: datetime | None = None,
    ) -> RecognitionStrategyTestEvidence:
        revision = self._managed.require(revision_id)
        if revision.status is not ManagedConfigurationStatus.VALIDATED:
            raise ConfigurationVersionConflict(
                "Recognition Strategy Test requires a Validated Draft",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
            )
        if revision.version != expected_version or revision.digest != expected_digest:
            raise ConfigurationVersionConflict(
                "Recognition Strategy Test is stale; validate the current Draft again",
                revision_id=revision_id,
                current_version=revision.version,
                current_digest=revision.digest,
            )
        if (
            not isinstance(resource_library_id, str)
            or not resource_library_id.strip()
            or len(resource_library_id) > 128
            or "\x00" in resource_library_id
        ):
            raise ValueError("Strategy Test ResourceLibrary ID must be bounded and non-empty")
        if (
            not isinstance(synthetic_path, str)
            or not synthetic_path.strip()
            or len(synthetic_path) > 4096
            or "\x00" in synthetic_path
        ):
            raise ValueError("Strategy Test path must be bounded, non-empty, and NUL-free")
        if not isinstance(live_metadata, bool):
            raise ValueError("Strategy Test liveMetadata must be a boolean")
        result: dict[str, object] | None = None
        try:
            runtime = load_managed_runtime_configuration(
                revision.document,
                bootstrap_database_path=self._managed.bootstrap_database_path
                or self._repository.database_path,
            )
            library = next(
                (
                    item
                    for item in runtime.resource_libraries
                    if item.library_id == resource_library_id and item.enabled
                ),
                None,
            )
            if library is None:
                raise ValueError("selected ResourceLibrary is unknown or disabled")
            # The offline pass is intentional: it obtains the exact effective policy without
            # constructing a Provider. It is also the complete behavior when liveMetadata is false.
            strategy = strategy_runner_from_configuration(runtime.strategy).run_path(
                synthetic_path,
                resource_library_id=library.library_id,
                storage_id=library.storage_id,
            )
            result = self._strategy_result_document(strategy, live_metadata=False)
            if live_metadata:
                result["mode"] = "live"
            if (
                live_metadata
                and metadata_correction is not None
                and strategy.metadata_policy is None
            ):
                raise StrategyConfigurationError(
                    "persisted Metadata correction no longer resolves an effective policy"
                )
            if live_metadata and strategy.metadata_policy is not None:
                if metadata_correction is not None and (
                    strategy.policy is None
                    or metadata_correction.recognition_type
                    != strategy.recognition.recognition_type_id
                    or metadata_correction.metadata_policy_id != strategy.policy.metadata_policy_id
                    or metadata_correction.provider != strategy.metadata_policy.provider_id
                    or strategy.metadata_policy.query_type is MediaQueryType.NONE
                ):
                    raise StrategyConfigurationError(
                        "persisted Metadata correction no longer matches the effective policy"
                    )
                if self._metadata_provider_registry_factory is None:
                    raise MetadataProviderBootstrapError(
                        "provider_not_configured",
                        "Live Metadata testing is not configured by this service.",
                        "configure the referenced Provider, then explicitly rerun the live "
                        "Metadata test",
                    )
                providers = self._metadata_provider_registry_factory(
                    (strategy.metadata_policy.provider_id,)
                )
                strategy = strategy_runner_from_configuration(runtime.strategy, providers).run_path(
                    synthetic_path,
                    live_metadata=True,
                    resource_library_id=library.library_id,
                    storage_id=library.storage_id,
                    metadata_selection=metadata_selection,
                    metadata_correction=metadata_correction,
                )
                result = self._strategy_result_document(strategy, live_metadata=True)
                if isinstance(result.get("metadata"), dict):
                    if candidate_selection is not None:
                        result["metadata"]["candidateSelection"] = candidate_selection
                    if correction_context is not None:
                        result["metadata"]["correction"] = correction_context
                    result = self._fit_strategy_result_document(result)
            recognition = strategy.recognition
            metadata = strategy.metadata
            status = ConfigurationStrategyTestStatus.COMPLETED
            failure_category = None
            message = (
                "Live Metadata test completed through CandidateMatcher"
                if live_metadata and metadata is not None
                else "Synthetic path completed through Parser, Recognition, and policy resolution"
            )
            next_action = self._strategy_test_next_action(recognition.status)
            if live_metadata and metadata is not None:
                failure_category, message, next_action = self._metadata_outcome_guidance(metadata)
                if correction_context is not None:
                    if metadata.status in {
                        MetadataIdentificationStatus.NEED_CONFIRM,
                        MetadataIdentificationStatus.AMBIGUOUS,
                    }:
                        next_action = (
                            "review the persisted corrected candidates and explicitly confirm one, "
                            "or adjust the correction and run the Metadata correction test again"
                        )
                    elif metadata.status is MetadataIdentificationStatus.NOT_FOUND:
                        next_action = (
                            "review the persisted correction input, adjust it, and explicitly run "
                            "the Metadata correction test again"
                        )
                    elif metadata.status is MetadataIdentificationStatus.PROVIDER_ERROR:
                        next_action = (
                            f"{next_action}; preserve or adjust the correction input, then "
                            "explicitly rerun the Metadata correction test"
                        )
                if metadata.status is MetadataIdentificationStatus.PROVIDER_ERROR:
                    status = ConfigurationStrategyTestStatus.FAILED
            evidence = RecognitionStrategyTestEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                status,
                datetime.now(UTC),
                actor,
                resource_library_id,
                synthetic_path,
                result,
                failure_category=failure_category,
                message=message,
                next_action=next_action,
            )
        except MetadataProviderBootstrapError as error:
            if result is not None:
                result["mode"] = "live"
                result["metadata"] = {
                    "status": "configuration_error",
                    "failureCategory": error.category,
                }
                if candidate_selection is not None:
                    result["metadata"]["candidateSelection"] = candidate_selection
                if correction_context is not None:
                    result["metadata"]["correction"] = correction_context
                result = self._fit_strategy_result_document(result)
            evidence = RecognitionStrategyTestEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationStrategyTestStatus.FAILED,
                datetime.now(UTC),
                actor,
                resource_library_id,
                synthetic_path,
                result,
                failure_category=error.category,
                message=error.message,
                next_action=error.next_action,
            )
        except StrategyConfigurationError:
            if result is not None and correction_context is not None:
                result["mode"] = "live"
                result["metadata"] = {
                    "status": "configuration_error",
                    "failureCategory": "provider_not_configured",
                    "correction": correction_context,
                }
                result = self._fit_strategy_result_document(result)
            evidence = RecognitionStrategyTestEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationStrategyTestStatus.FAILED,
                datetime.now(UTC),
                actor,
                resource_library_id,
                synthetic_path,
                result,
                failure_category="provider_not_configured"
                if live_metadata
                else "invalid_configuration",
                message=(
                    "The Provider referenced by the effective MetadataPolicy is not configured."
                    if live_metadata
                    else "Recognition Strategy Test failed (StrategyConfigurationError)"
                ),
                next_action=(
                    "configure the referenced Provider, then explicitly rerun the live "
                    "Metadata test"
                    if live_metadata
                    else "correct and validate the Draft, then explicitly rerun Strategy Test"
                ),
            )
        except Exception as error:
            message = f"Recognition Strategy Test failed ({type(error).__name__})"
            evidence = RecognitionStrategyTestEvidence(
                revision.revision_id,
                revision.version,
                revision.digest,
                ConfigurationStrategyTestStatus.FAILED,
                datetime.now(UTC),
                actor,
                resource_library_id,
                synthetic_path,
                failure_category="invalid_configuration",
                message=message,
                next_action=("correct and validate the Draft, then explicitly rerun Strategy Test"),
            )
        if expected_evidence_tested_at is None:
            return self._repository.save_recognition_strategy_test(evidence)
        return self._repository.replace_recognition_strategy_test(
            evidence,
            expected_revision_version=expected_version,
            expected_revision_digest=expected_digest,
            expected_tested_at=expected_evidence_tested_at,
        )

    def _strategy_result_document(
        self, strategy: StrategyTestResult, *, live_metadata: bool
    ) -> dict[str, object]:
        recognition = strategy.recognition
        policy = strategy.policy
        metadata_policy = strategy.metadata_policy
        document = {
            "mode": "live" if live_metadata else "offline",
            "parsed": {
                "titleCandidate": self._bounded_utf8(strategy.parsed.title_candidate, 512),
                "evidenceTruncated": len(strategy.parsed.title_candidate.encode("utf-8")) > 512,
                "year": strategy.parsed.year,
                "season": strategy.parsed.season,
                "episode": strategy.parsed.episode,
                "episodes": list(strategy.parsed.episodes),
                "extension": strategy.parsed.extension,
            },
            "recognition": {
                "status": recognition.status.value,
                "recognitionType": recognition.recognition_type_id,
                "ruleId": recognition.rule_id or None,
                "confidence": recognition.confidence,
                "score": recognition.score,
                "matchedRules": [
                    {
                        "ruleId": item.rule_id,
                        "recognitionType": item.recognition_type_id,
                        "priority": item.priority,
                        "score": item.score,
                    }
                    for item in recognition.matched_rules[:32]
                ],
                "alternatives": [
                    {
                        "recognitionType": item.recognition_type_id,
                        "priority": item.priority,
                        "score": item.score,
                    }
                    for item in recognition.alternatives[:32]
                ],
                "reasons": [
                    {
                        "code": self._bounded_utf8(item.code, 96),
                        "message": self._bounded_utf8(item.message, 384),
                    }
                    for item in recognition.reasons[:32]
                ],
                "warnings": [
                    self._bounded_utf8(str(item), 384) for item in recognition.warnings[:32]
                ],
            },
            "policy": {
                "typePolicyId": policy.type_policy_id,
                "recognitionType": policy.recognition_type_id,
                "metadataPolicy": policy.metadata_policy_id,
                "namingPolicy": policy.naming_policy_id,
                "classificationPolicy": policy.classification_policy_id,
                "organizePolicy": policy.organize_policy_id,
            }
            if policy
            else None,
            "effectiveMetadataPolicy": self._metadata_policy_document(metadata_policy)
            if metadata_policy
            else None,
            "metadata": self._metadata_result_document(strategy) if live_metadata else None,
            "recognitionTypePreserved": strategy.recognition_type_preserved,
        }
        return self._fit_strategy_result_document(document)

    @classmethod
    def _metadata_result_document(cls, strategy: StrategyTestResult) -> dict[str, object] | None:
        metadata = strategy.metadata
        if metadata is None:
            return None
        identity = metadata.identity
        match = metadata.match
        candidate_total = len(match.candidate_scores) if match else 0
        metadata_truncated = len(metadata.query.encode("utf-8")) > 512
        if identity:
            metadata_truncated = metadata_truncated or any(
                len(value.encode("utf-8")) > maximum
                for value, maximum in (
                    (identity.provider, 96),
                    (identity.provider_id, 128),
                    (identity.title, 512),
                    (identity.original_title or "", 512),
                )
            )
        candidates = []
        match_text_truncated = False
        if match:
            match_text_truncated = any(
                len(str(item).encode("utf-8")) > 384
                for item in (*match.reasons[:8], *match.warnings[:8])
            )
            for scored in match.candidate_scores[:5]:
                component_total = len(scored.components)
                candidate_text_truncated = any(
                    len(value.encode("utf-8")) > maximum
                    for value, maximum in (
                        (scored.candidate.provider, 96),
                        (scored.candidate.provider_id, 128),
                        (scored.candidate.title, 512),
                        (scored.candidate.original_title or "", 512),
                        (scored.matched_local_title or "", 512),
                        (scored.matched_provider_title or "", 512),
                        (scored.matched_title_source or "", 96),
                    )
                ) or any(
                    len(value.encode("utf-8")) > maximum
                    for component in scored.components[:6]
                    for value, maximum in (
                        (component.name, 96),
                        (component.reason, 384),
                    )
                )
                components = [
                    {
                        "name": cls._bounded_utf8(component.name, 96),
                        "score": component.score,
                        "reason": cls._bounded_utf8(component.reason, 384),
                    }
                    for component in scored.components[:6]
                ]
                candidates.append(
                    {
                        "provider": cls._bounded_utf8(scored.candidate.provider, 96),
                        "providerId": cls._bounded_utf8(scored.candidate.provider_id, 128),
                        "mediaType": scored.candidate.media_type.value,
                        "title": cls._bounded_utf8(scored.candidate.title, 512),
                        "originalTitle": cls._bounded_utf8(scored.candidate.original_title, 512),
                        "canonicalYear": scored.candidate.canonical_year,
                        "regionalYear": scored.candidate.regional_year,
                        "totalScore": scored.total_score,
                        "matchedLocalTitle": cls._bounded_utf8(scored.matched_local_title, 512),
                        "matchedProviderTitle": cls._bounded_utf8(
                            scored.matched_provider_title, 512
                        ),
                        "matchedTitleSource": cls._bounded_utf8(scored.matched_title_source, 96),
                        "componentTotal": component_total,
                        "componentProjected": len(components),
                        "truncated": component_total > len(components) or candidate_text_truncated,
                        "components": components,
                    }
                )
        return {
            "status": metadata.status.value,
            "query": cls._bounded_utf8(metadata.query, 512),
            "cacheStatus": "not_reported",
            "truncated": metadata_truncated
            or candidate_total > len(candidates)
            or any(candidate["truncated"] for candidate in candidates),
            "identity": {
                "provider": cls._bounded_utf8(identity.provider, 96),
                "providerId": cls._bounded_utf8(identity.provider_id, 128),
                "mediaType": identity.media_type.value,
                "title": cls._bounded_utf8(identity.title, 512),
                "originalTitle": cls._bounded_utf8(identity.original_title, 512),
                "canonicalYear": identity.canonical_year,
                "regionalYear": identity.regional_year,
                "confidence": identity.confidence,
                "matchedBy": cls._bounded_utf8(identity.matched_by, 96),
            }
            if identity
            else None,
            "match": {
                "status": match.status.value,
                "score": match.score,
                "reasons": [cls._bounded_utf8(str(item), 384) for item in match.reasons[:8]],
                "warnings": [cls._bounded_utf8(str(item), 384) for item in match.warnings[:8]],
                "candidateTotal": candidate_total,
                "candidateProjected": len(candidates),
                "truncated": match_text_truncated
                or candidate_total > len(candidates)
                or any(candidate["truncated"] for candidate in candidates),
                "candidates": candidates,
            }
            if match
            else None,
        }

    @staticmethod
    def _bounded_utf8(value: str | None, maximum_bytes: int) -> str | None:
        if value is None:
            return None
        encoded = value.encode("utf-8")
        if len(encoded) <= maximum_bytes:
            return value
        return encoded[:maximum_bytes].decode("utf-8", errors="ignore")

    @classmethod
    def _fit_strategy_result_document(cls, value: dict[str, object]) -> dict[str, object]:
        """Deterministically retain high-value evidence within the domain byte limit."""

        result = copy.deepcopy(value)

        def size() -> int:
            return len(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )

        metadata = result.get("metadata")
        metadata_object = metadata if isinstance(metadata, dict) else None
        match_value = metadata_object.get("match") if metadata_object else None
        match = match_value if isinstance(match_value, dict) else None
        candidates_value = match.get("candidates") if match else None
        candidates = candidates_value if isinstance(candidates_value, list) else []

        def mark_metadata_truncated() -> None:
            if metadata_object is not None:
                metadata_object["truncated"] = True
            if match is not None:
                match["truncated"] = True
                match["candidateProjected"] = len(candidates)

        # Lower-ranked candidates are removed before evidence from the highest-ranked candidate.
        while size() > CONFIGURATION_STRATEGY_RESULT_LIMIT and len(candidates) > 1:
            candidates.pop()
            mark_metadata_truncated()

        # Preserve title/year components first; discard lower-value components from the tail.
        while size() > CONFIGURATION_STRATEGY_RESULT_LIMIT and candidates:
            changed = False
            for candidate in reversed(candidates):
                components = candidate.get("components")
                if isinstance(components, list) and len(components) > 2:
                    components.pop()
                    candidate["componentProjected"] = len(components)
                    candidate["truncated"] = True
                    changed = True
                    mark_metadata_truncated()
                    if size() <= CONFIGURATION_STRATEGY_RESULT_LIMIT:
                        break
            if not changed:
                break

        # Bounded summaries are less valuable than the winner and its title/year score evidence.
        for container, key in (
            (match, "warnings"),
            (match, "reasons"),
            (result.get("recognition"), "warnings"),
            (result.get("recognition"), "reasons"),
            (result.get("recognition"), "alternatives"),
            (result.get("recognition"), "matchedRules"),
        ):
            if not isinstance(container, dict):
                continue
            values = container.get(key)
            while (
                size() > CONFIGURATION_STRATEGY_RESULT_LIMIT
                and isinstance(values, list)
                and (len(values) > (1 if key == "matchedRules" else 0))
            ):
                values.pop()
                if container is match:
                    mark_metadata_truncated()
                else:
                    container["evidenceTruncated"] = True

        if size() > CONFIGURATION_STRATEGY_RESULT_LIMIT:
            # All projected free text is already individually bounded. Halving it in a stable
            # path order is a final guard for unusually dense but valid recognition evidence.
            text_paths: list[tuple[dict[str, object], str]] = []
            parsed = result.get("parsed")
            if isinstance(parsed, dict):
                text_paths.append((parsed, "titleCandidate"))
            if metadata_object is not None:
                text_paths.append((metadata_object, "query"))
                identity = metadata_object.get("identity")
                if isinstance(identity, dict):
                    text_paths.extend((identity, key) for key in ("title", "originalTitle"))
            if candidates:
                text_paths.extend(
                    (candidates[0], key)
                    for key in (
                        "title",
                        "originalTitle",
                        "matchedLocalTitle",
                        "matchedProviderTitle",
                    )
                )
            for container, key in text_paths:
                current = container.get(key)
                while (
                    size() > CONFIGURATION_STRATEGY_RESULT_LIMIT
                    and isinstance(current, str)
                    and len(current.encode("utf-8")) > 32
                ):
                    current = cls._bounded_utf8(current, len(current.encode("utf-8")) // 2)
                    container[key] = current
                    mark_metadata_truncated()

        if size() > CONFIGURATION_STRATEGY_RESULT_LIMIT:
            raise ValueError("bounded strategy test result exceeds the evidence byte limit")
        return result

    @staticmethod
    def _metadata_outcome_guidance(metadata) -> tuple[str | None, str, str]:
        if metadata.status is MetadataIdentificationStatus.MATCHED:
            return (
                None,
                "Live Metadata test matched one identity",
                (
                    "review the selected identity and candidate explanation, then explicitly "
                    "checked-activate this revision if the existing checks are current"
                ),
            )
        if metadata.status is MetadataIdentificationStatus.NEED_CONFIRM:
            return (
                "need_confirm",
                "Live Metadata test requires candidate confirmation",
                (
                    "inspect candidate scores and correct the MetadataPolicy or synthetic path, "
                    "then "
                    "Validate and explicitly rerun the live Metadata test"
                ),
            )
        if metadata.status is MetadataIdentificationStatus.AMBIGUOUS:
            return (
                "ambiguous",
                "Live Metadata test found ambiguous candidates",
                (
                    "inspect the score gap and candidate evidence, correct the Draft if needed, "
                    "then "
                    "Validate and explicitly rerun the live Metadata test"
                ),
            )
        if metadata.status is MetadataIdentificationStatus.NOT_FOUND:
            return (
                "not_found",
                "Live Metadata test found no acceptable candidate",
                (
                    "inspect the query, locale and score evidence, correct the Draft or synthetic "
                    "path, "
                    "then Validate and explicitly rerun the live Metadata test"
                ),
            )
        if metadata.status is MetadataIdentificationStatus.METADATA_MISMATCH:
            return (
                "metadata_mismatch",
                "Provider metadata did not verify the parsed media",
                (
                    "inspect parsed season or episodes and Provider evidence, correct the input "
                    "or "
                    "Draft, then explicitly rerun the live Metadata test"
                ),
            )
        code = metadata.error.code if metadata.error else MetadataErrorCode.UNKNOWN
        category, message, action = {
            MetadataErrorCode.INVALID_REQUEST: (
                "invalid_provider_request",
                "The Metadata Provider rejected the correction request.",
                "review the correction fields or direct Provider ID, then explicitly rerun the "
                "Metadata correction test",
            ),
            MetadataErrorCode.NOT_FOUND: (
                "provider_id_not_found",
                "The Metadata Provider did not find the requested identity.",
                "review the direct Provider ID and Movie/TV choice, then explicitly rerun the "
                "Metadata correction test",
            ),
            MetadataErrorCode.AUTHENTICATION_FAILED: (
                "authentication_failed",
                "The Metadata Provider rejected its credential.",
                "correct the service credential, restart if required, and explicitly rerun the "
                "live Metadata test",
            ),
            MetadataErrorCode.PERMISSION_DENIED: (
                "authentication_failed",
                "The Metadata Provider credential lacks permission.",
                "correct Provider credential permissions and explicitly rerun the live Metadata "
                "test",
            ),
            MetadataErrorCode.RATE_LIMITED: (
                "rate_limited",
                "The Metadata Provider rate limit was reached.",
                "wait for the Provider limit to recover, then explicitly rerun the live Metadata "
                "test",
            ),
            MetadataErrorCode.TIMEOUT: (
                "timeout",
                "The Metadata Provider request timed out.",
                "check Provider connectivity or policy timeout, then explicitly rerun the live "
                "Metadata test",
            ),
            MetadataErrorCode.MALFORMED_RESPONSE: (
                "malformed_response",
                "The Metadata Provider returned a malformed response.",
                "check Provider availability and explicitly rerun; retain this evidence if the "
                "failure persists",
            ),
            MetadataErrorCode.CONNECTION_FAILED: (
                "provider_unavailable",
                "The Metadata Provider could not be reached.",
                "check service network access and explicitly rerun the live Metadata test",
            ),
            MetadataErrorCode.PROVIDER_UNAVAILABLE: (
                "provider_unavailable",
                "The Metadata Provider is unavailable.",
                "check Provider status and explicitly rerun the live Metadata test",
            ),
        }.get(
            code,
            (
                "provider_error",
                "The Metadata Provider request failed.",
                "check Provider configuration and availability, then explicitly rerun the live "
                "Metadata test",
            ),
        )
        return category, message, action

    @staticmethod
    def _strategy_test_next_action(status: RecognitionStatus) -> str:
        if status is RecognitionStatus.MATCHED:
            return (
                "review the matched rules and policy resolution, then explicitly checked-activate "
                "this revision"
            )
        if status is RecognitionStatus.AMBIGUOUS:
            return (
                "inspect the competing rules, correct rule priorities or conditions in the Draft, "
                "Validate, then explicitly rerun Strategy Test"
            )
        if status is RecognitionStatus.UNRECOGNIZED:
            return (
                "correct the selected ResourceLibrary context or RecognitionRules in the Draft, "
                "Validate, then explicitly rerun Strategy Test"
            )
        raise ValueError("unsupported Recognition Strategy Test outcome")

    @staticmethod
    def _metadata_policy_document(policy: MetadataPolicy) -> dict[str, object]:
        """Return the bounded, provider-neutral policy actually consumed offline."""

        return {
            "id": policy.policy_id,
            "name": policy.name,
            "providerId": policy.provider_id,
            "mediaType": policy.media_type.value if policy.media_type else None,
            "mediaQueryType": policy.query_type.value,
            "language": policy.language,
            "region": policy.region,
            "automaticThreshold": policy.automatic_threshold,
            "confirmationThreshold": policy.confirmation_threshold,
            "minimumScoreGap": policy.minimum_score_gap,
            "timeout": policy.timeout,
            "retry": {
                "count": policy.retry_policy.retry_count,
                "baseDelay": policy.retry_policy.base_delay,
                "maxDelay": policy.retry_policy.max_delay,
            },
            "cache": {
                "searchTtl": policy.cache_policy.search_ttl,
                "detailsTtl": policy.cache_policy.details_ttl,
                "negativeTtl": policy.cache_policy.negative_ttl,
            },
            "maxCandidates": policy.max_candidates,
            "maxSearchPages": policy.max_search_pages,
            "maxProviderRequests": policy.max_provider_requests,
            "maxCandidateEnrichments": policy.max_candidate_enrichments,
            "enabled": policy.enabled,
        }

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

    def require_current_strategy_test(self, revision: ManagedConfigurationRevision) -> None:
        evidence = self._repository.get_recognition_strategy_test(revision.revision_id)
        if evidence is None or evidence.status is not ConfigurationStrategyTestStatus.COMPLETED:
            raise ConfigurationActivationConflict(
                "a completed Recognition Strategy Test is required before checked activation",
                revision_id=revision.revision_id,
            )
        if (
            evidence.revision_version != revision.version
            or evidence.revision_digest != revision.digest
        ):
            raise ConfigurationActivationConflict(
                "Recognition Strategy Test is stale; validate and test the Draft again",
                revision_id=revision.revision_id,
            )

    def require_current_destination_precheck(self, revision: ManagedConfigurationRevision) -> None:
        storages = {
            str(value.get("id")): str(value.get("type", "")).lower()
            for value in self._canonical_objects(revision.document, "storages")
        }
        applicable = any(
            storages.get(str(library.get("storageId"))) == "local"
            for library in (
                self._canonical_objects(revision.document, "mediaLibraries")
                if "mediaLibraries" in revision.document
                else []
            )
        )
        if not applicable:
            return
        evidence = self._repository.get_destination_precheck(revision.revision_id)
        if evidence is None:
            raise ConfigurationActivationConflict(
                "a current Local destination precheck is required before checked activation",
                revision_id=revision.revision_id,
                next_action=(
                    "run the read-only destination precheck on this revision, then activate checked"
                ),
            )
        if (
            evidence.revision_version != revision.version
            or evidence.revision_digest != revision.digest
        ):
            raise ConfigurationActivationConflict(
                "Local destination precheck is stale; rerun it before checked activation",
                revision_id=revision.revision_id,
                next_action=(
                    "reload this revision and rerun the destination precheck on its current "
                    "version and digest"
                ),
            )
        if evidence.status is not ConfigurationDestinationPrecheckStatus.COMPLETED:
            category = self._bounded_utf8(evidence.failure_category or "unavailable", 128)
            raise ConfigurationActivationConflict(
                f"Local destination precheck failed with category {category}",
                revision_id=revision.revision_id,
                next_action=(
                    evidence.next_action
                    or "correct the destination configuration, then rerun the precheck"
                ),
            )
        result = evidence.result or {}
        if result.get("verdict") == "capability_gap":
            raise ConfigurationActivationConflict(
                "Local destination precheck completed with a capability_gap verdict",
                revision_id=revision.revision_id,
                next_action=(
                    "change the configured operation or destination Storage, "
                    "then rerun the precheck"
                ),
            )

    def _strategy_test_document(
        self, revision: ManagedConfigurationRevision
    ) -> dict[str, object] | None:
        evidence = self._repository.get_recognition_strategy_test(revision.revision_id)
        if evidence is None:
            return None
        value = evidence.document()
        value["stale"] = (
            evidence.revision_version != revision.version
            or evidence.revision_digest != revision.digest
        )
        return value

    def _naming_preview_document(
        self, revision: ManagedConfigurationRevision
    ) -> dict[str, object] | None:
        getter = getattr(self._repository, "get_naming_preview", None)
        evidence = getter(revision.revision_id) if getter is not None else None
        if evidence is None:
            return None
        value = evidence.document()
        value["stale"] = (
            evidence.revision_version != revision.version
            or evidence.revision_digest != revision.digest
        )
        return value

    def _classification_preview_document(
        self, revision: ManagedConfigurationRevision
    ) -> dict[str, object] | None:
        getter = getattr(self._repository, "get_classification_preview", None)
        evidence = getter(revision.revision_id) if getter is not None else None
        if evidence is None:
            return None
        value = evidence.document()
        value["stale"] = (
            evidence.revision_version != revision.version
            or evidence.revision_digest != revision.digest
        )
        return value

    def _organize_authority_document(
        self, revision: ManagedConfigurationRevision
    ) -> dict[str, object] | None:
        getter = getattr(self._repository, "get_organize_authority", None)
        evidence = getter(revision.revision_id) if getter is not None else None
        if evidence is None:
            return None
        value = evidence.document()
        value["stale"] = (
            evidence.revision_version != revision.version
            or evidence.revision_digest != revision.digest
        )
        return value

    def _destination_preview_document(
        self, revision: ManagedConfigurationRevision
    ) -> dict[str, object] | None:
        getter = getattr(self._repository, "get_destination_preview", None)
        evidence = getter(revision.revision_id) if getter is not None else None
        if evidence is None:
            return None
        value = evidence.document()
        value["stale"] = (
            evidence.revision_version != revision.version
            or evidence.revision_digest != revision.digest
        )
        return value

    def _destination_precheck_document(
        self, revision: ManagedConfigurationRevision
    ) -> dict[str, object] | None:
        getter = getattr(self._repository, "get_destination_precheck", None)
        evidence = getter(revision.revision_id) if getter is not None else None
        if evidence is None:
            return None
        value = evidence.document()
        value["stale"] = (
            evidence.revision_version != revision.version
            or evidence.revision_digest != revision.digest
        )
        return value

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
                "this configuration object kind is not editable in the current slice"
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
            ConfigurationObjectKind.RECOGNITION_TYPE: cls._RECOGNITION_TYPE_FIELDS,
            ConfigurationObjectKind.RECOGNITION_RULE: cls._RECOGNITION_RULE_FIELDS,
            ConfigurationObjectKind.RECOGNITION_TYPE_POLICY: cls._RECOGNITION_TYPE_POLICY_FIELDS,
            ConfigurationObjectKind.METADATA_POLICY: cls._METADATA_POLICY_FIELDS,
            ConfigurationObjectKind.NAMING_POLICY: cls._NAMING_POLICY_FIELDS,
            ConfigurationObjectKind.CLASSIFICATION_POLICY: cls._CLASSIFICATION_POLICY_FIELDS,
            ConfigurationObjectKind.ORGANIZE_POLICY: cls._ORGANIZE_POLICY_FIELDS,
        }[kind]
        unknown = set(value).difference(allowed)
        if unknown:
            raise ValueError(f"{section} contains unsupported field {sorted(unknown)[0]!r}")
        object_id = value.get("id")
        if not isinstance(object_id, str) or not object_id.strip() or len(object_id) > 64:
            raise ValueError(f"{section} id must be a bounded non-empty string")
        if any(character in object_id for character in "/\\\x00"):
            raise ValueError(f"{section} id contains an invalid character")
        if kind is ConfigurationObjectKind.ORGANIZE_POLICY:
            operation = value.get("operation")
            if (
                not isinstance(operation, str)
                or not operation.strip()
                or len(operation) > 64
                or "\x00" in operation
            ):
                raise ValueError("OrganizePolicy operation must be bounded non-empty text")
            # Reuse the runtime loader so a managed edit cannot accept, reject, or
            # normalize an organize policy differently from the Active snapshot; the
            # domain objects it builds own every bound and the overwrite cross-field rule.
            try:
                policy = parse_organize_policy(copy.deepcopy(dict(value)))
            except ValueError as error:
                raise ValueError(f"OrganizePolicy {cls._bounded_utf8(str(error), 384)}") from error
            if policy.operation not in {
                OrganizeOperationType.MOVE,
                OrganizeOperationType.COPY,
                OrganizeOperationType.HARD_LINK,
                OrganizeOperationType.SOFT_LINK,
            }:
                raise ValueError(
                    "OrganizePolicy operation must be Move, Copy, HardLink, or SoftLink"
                )
            normalized = {
                "id": policy.policy_id,
                "operation": policy.operation.value,
                "conflictStrategy": policy.conflict_strategy.value,
                "overwrite": policy.conflict_strategy is ConflictStrategy.OVERWRITE,
                "duplicateDetection": cls._hash_document(policy),
                "rollback": cls._rollback_document(policy),
                "sourceDirectoryCleanup": cls._cleanup_document(policy),
                "attachments": cls._attachment_document(policy),
            }
            return cls._bounded_object(section, normalized)
        name = value.get("name", object_id)
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError(f"{section} name must be a bounded non-empty string")
        result = {"id": object_id, "name": name}
        if kind is ConfigurationObjectKind.CLASSIFICATION_POLICY:
            rules_value = value.get("rules")
            if not isinstance(rules_value, list) or not rules_value or len(rules_value) > 128:
                raise ClassificationError(
                    ClassificationErrorCode.INVALID_POLICY,
                    "ClassificationPolicy rules must be a non-empty bounded array",
                )
            rules: list[dict[str, object]] = []
            domain_rules: list[ClassificationRule] = []
            for index, rule_value in enumerate(rules_value):
                if not isinstance(rule_value, Mapping):
                    raise ClassificationError(
                        ClassificationErrorCode.INVALID_RULE,
                        f"ClassificationPolicy rules[{index}] must be an object",
                    )
                domain_rule, normalized_rule = cls._classification_rule(rule_value, index=index)
                domain_rules.append(domain_rule)
                rules.append(normalized_rule)
            description = cls._text(value, "description", "", 500, "ClassificationPolicy")
            enabled = cls._bool(value, "enabled", True, "ClassificationPolicy")
            priority = cls._int(value, "priority", 0, "ClassificationPolicy")
            ClassificationPolicy(
                object_id,
                name,
                tuple(domain_rules),
                description,
                enabled,
                priority,
            )
            result.update(
                {
                    "description": description,
                    "enabled": enabled,
                    "priority": priority,
                    "rules": rules,
                }
            )
            return cls._bounded_object(section, result)
        if kind is ConfigurationObjectKind.NAMING_POLICY:
            media_type_mode = value.get("mediaTypeMode", "auto")
            missing_strategy = value.get("missingVariableStrategy", "omit_token")
            try:
                mode = NamingMediaTypeMode(media_type_mode)
                strategy = MissingVariableStrategy(missing_strategy)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    "NamingPolicy mediaTypeMode or missingVariableStrategy is unsupported"
                ) from error
            max_length = cls._bounded_int(
                value,
                "maxComponentLength",
                200,
                minimum=8,
                maximum=255,
                label="NamingPolicy",
            )
            templates = {
                "directoryTemplate": value.get("directoryTemplate", "{title} ({year})"),
                "filenameTemplate": value.get("filenameTemplate", "{title} ({year}).{ext}"),
                "seriesDirectoryTemplate": value.get("seriesDirectoryTemplate", "{title} ({year})"),
                "seasonDirectoryTemplate": value.get(
                    "seasonDirectoryTemplate", "Season {season:02}"
                ),
                "episodeFilenameTemplate": value.get(
                    "episodeFilenameTemplate",
                    "{title} - S{season:02}E{episode:02} - {episode_title}.{ext}",
                ),
                "multiEpisodeFileTemplate": value.get(
                    "multiEpisodeFileTemplate", "{title} - S{season:02}{episodes}.{ext}"
                ),
            }
            for field, template in templates.items():
                if not isinstance(template, str):
                    raise ValueError(f"NamingPolicy {field} must be bounded non-empty text")
                if not template:
                    raise NamingError(
                        NamingErrorCode.INVALID_TEMPLATE,
                        f"NamingPolicy {field} is empty",
                    )
                if len(template.encode("utf-8")) > 4096:
                    raise NamingError(
                        NamingErrorCode.COMPONENT_TOO_LONG,
                        f"NamingPolicy {field} exceeds the template limit",
                    )
                if "\x00" in template:
                    raise NamingError(
                        NamingErrorCode.UNSAFE_PATH,
                        f"NamingPolicy {field} contains NUL",
                    )
            description = value.get("description", "")
            if not isinstance(description, str) or len(description) > 500 or "\x00" in description:
                raise ValueError("NamingPolicy description must be bounded text")
            enabled = cls._bool(value, "enabled", True, "NamingPolicy")
            policy = NamingPolicy(
                object_id,
                name,
                templates["directoryTemplate"],
                templates["filenameTemplate"],
                templates["seriesDirectoryTemplate"],
                templates["seasonDirectoryTemplate"],
                templates["episodeFilenameTemplate"],
                templates["multiEpisodeFileTemplate"],
                description,
                enabled,
                mode,
                strategy,
                max_component_length=max_length,
            )
            validate_naming_policy(policy)
            result.update(templates)
            result.update(
                {
                    "description": description,
                    "enabled": enabled,
                    "mediaTypeMode": mode.value,
                    "missingVariableStrategy": strategy.value,
                    "maxComponentLength": max_length,
                }
            )
            return result
        if kind is ConfigurationObjectKind.METADATA_POLICY:
            provider_id = cls._metadata_identifier(value, "providerId", "MetadataPolicy")
            raw_media_type = value.get("mediaType")
            raw_query_type = value.get("mediaQueryType")
            try:
                media_type = MediaType(raw_media_type) if raw_media_type is not None else None
                query_type = MediaQueryType(raw_query_type) if raw_query_type is not None else None
            except (TypeError, ValueError) as error:
                raise ValueError("MetadataPolicy media/query type is unsupported") from error
            language = cls._metadata_locale(value.get("language"), "language", language=True)
            region = cls._metadata_locale(value.get("region"), "region", language=False)
            automatic = cls._bounded_number(
                value, "automaticThreshold", 90, minimum=0, maximum=100, label="MetadataPolicy"
            )
            confirmation = cls._bounded_number(
                value, "confirmationThreshold", 70, minimum=0, maximum=100, label="MetadataPolicy"
            )
            gap = cls._bounded_number(
                value, "minimumScoreGap", 5, minimum=0, maximum=100, label="MetadataPolicy"
            )
            timeout = cls._bounded_number(
                value, "timeout", 10, minimum=0.001, maximum=120, label="MetadataPolicy"
            )
            retry_count = cls._bounded_int(
                value, "retryCount", 2, minimum=0, maximum=10, label="MetadataPolicy"
            )
            max_candidates = cls._bounded_int(
                value, "maxCandidates", 20, minimum=1, maximum=100, label="MetadataPolicy"
            )
            max_pages = cls._bounded_int(
                value, "maxSearchPages", 2, minimum=1, maximum=10, label="MetadataPolicy"
            )
            max_requests = cls._bounded_int(
                value, "maxProviderRequests", 6, minimum=1, maximum=100, label="MetadataPolicy"
            )
            max_enrichments = cls._bounded_int(
                value, "maxCandidateEnrichments", 2, minimum=0, maximum=100, label="MetadataPolicy"
            )
            enabled = cls._bool(value, "enabled", True, "MetadataPolicy")
            # Reuse the production domain semantics, including threshold ordering.
            MetadataPolicy(
                object_id,
                provider_id,
                media_type,
                language,
                region,
                name,
                query_type,
                automatic,
                confirmation,
                gap,
                timeout,
                RetryPolicy(retry_count),
                max_candidates=max_candidates,
                max_search_pages=max_pages,
                max_provider_requests=max_requests,
                max_candidate_enrichments=max_enrichments,
                enabled=enabled,
            )
            result.update(
                {
                    "providerId": provider_id,
                    "automaticThreshold": automatic,
                    "confirmationThreshold": confirmation,
                    "minimumScoreGap": gap,
                    "timeout": timeout,
                    "retryCount": retry_count,
                    "maxCandidates": max_candidates,
                    "maxSearchPages": max_pages,
                    "maxProviderRequests": max_requests,
                    "maxCandidateEnrichments": max_enrichments,
                    "enabled": enabled,
                }
            )
            if media_type is not None:
                result["mediaType"] = media_type.value
            if query_type is not None:
                result["mediaQueryType"] = query_type.value
            if language is not None:
                result["language"] = language
            if region is not None:
                result["region"] = region
            return cls._bounded_object(section, result)
        if kind is ConfigurationObjectKind.RECOGNITION_TYPE:
            description = value.get("description", "")
            enabled = value.get("enabled", True)
            if not isinstance(description, str) or len(description) > 1000:
                raise ValueError("RecognitionType description must be bounded text")
            if not isinstance(enabled, bool):
                raise ValueError("RecognitionType enabled must be boolean")
            result.update({"description": description, "enabled": enabled})
            return result
        if kind is ConfigurationObjectKind.RECOGNITION_RULE:
            output = value.get("outputRecognitionType")
            if not isinstance(output, str) or not output.strip() or len(output) > 64:
                raise ValueError("RecognitionRule outputRecognitionType is required")
            condition = value.get("condition")
            cls._recognition_condition(condition)
            result.update(
                {
                    "condition": copy.deepcopy(condition),
                    "outputRecognitionType": output,
                    "enabled": cls._bool(value, "enabled", True, "RecognitionRule"),
                    "priority": cls._int(value, "priority", 0, "RecognitionRule"),
                    "score": cls._number(value, "score", 1, "RecognitionRule"),
                    "stopOnMatch": cls._bool(value, "stopOnMatch", False, "RecognitionRule"),
                    "description": cls._text(value, "description", "", 1000, "RecognitionRule"),
                }
            )
            return cls._bounded_object(section, result)
        if kind is ConfigurationObjectKind.RECOGNITION_TYPE_POLICY:
            for field in (
                "recognitionType",
                "metadataPolicy",
                "namingPolicy",
                "classificationPolicy",
                "organizePolicy",
            ):
                reference = value.get(field)
                if not isinstance(reference, str) or not reference.strip() or len(reference) > 64:
                    raise ValueError(f"RecognitionTypePolicy {field} is required")
                result[field] = reference
            result.update(
                {
                    "enabled": cls._bool(value, "enabled", True, "RecognitionTypePolicy"),
                    "priority": cls._int(value, "priority", 0, "RecognitionTypePolicy"),
                }
            )
            return cls._bounded_object(section, result)
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

    @classmethod
    def _classification_rule(
        cls, value: Mapping[str, object], *, index: int = 0
    ) -> tuple[ClassificationRule, dict[str, object]]:
        if unknown := set(value).difference(cls._CLASSIFICATION_RULE_FIELDS):
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                f"ClassificationPolicy rules[{index}] contains unsupported field "
                f"{sorted(unknown)[0]!r}",
            )
        rule_id = value.get("id")
        if (
            not isinstance(rule_id, str)
            or not rule_id.strip()
            or len(rule_id) > 64
            or any(character in rule_id for character in "/\\\x00")
        ):
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                f"ClassificationPolicy rules[{index}].id must be bounded and safe",
            )
        name = value.get("name", rule_id)
        if not isinstance(name, str) or not name.strip() or len(name) > 120 or "\x00" in name:
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                f"ClassificationPolicy rules[{index}].name must be bounded text",
            )
        conditions = value.get("conditions", {})
        result = value.get("result")
        if not isinstance(conditions, Mapping):
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                f"ClassificationPolicy rules[{index}].conditions must be an object",
            )
        if not isinstance(result, Mapping):
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                f"ClassificationPolicy rules[{index}].result must be an object",
            )
        if unknown := set(conditions).difference(cls._CLASSIFICATION_CONDITION_FIELDS):
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                f"ClassificationPolicy rules[{index}].conditions contains unsupported field "
                f"{sorted(unknown)[0]!r}",
            )
        if unknown := set(result).difference(cls._CLASSIFICATION_RESULT_FIELDS):
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                f"ClassificationPolicy rules[{index}].result contains unsupported field "
                f"{sorted(unknown)[0]!r}",
            )

        def bounded_string(field: str, *, required: bool = False, maximum: int = 200):
            raw = result.get(field)
            if raw is None and not required:
                return None
            if (
                not isinstance(raw, str)
                or (required and not raw.strip())
                or len(raw) > maximum
                or "\x00" in raw
            ):
                raise ClassificationError(
                    ClassificationErrorCode.INVALID_RULE,
                    f"ClassificationPolicy rules[{index}].result.{field} must be bounded text",
                )
            return raw

        media_library_id = bounded_string("mediaLibraryId", required=True, maximum=64)
        library = bounded_string("library", required=True, maximum=200)
        path_value = result.get("path")
        if isinstance(path_value, list):
            if not path_value or len(path_value) > 32:
                raise ClassificationError(
                    ClassificationErrorCode.UNSAFE_PATH,
                    f"ClassificationPolicy rules[{index}].result.path must be a bounded path",
                )
            path_parts = []
            for part_index, part in enumerate(path_value):
                if not isinstance(part, str) or not part.strip() or len(part) > 200:
                    raise ClassificationError(
                        ClassificationErrorCode.UNSAFE_PATH,
                        f"ClassificationPolicy rules[{index}].result.path[{part_index}] is invalid",
                    )
                path_parts.append(part)
            relative_path = "/".join(path_parts)
        elif isinstance(path_value, str):
            relative_path = path_value
            path_parts = path_value.split("/")
        else:
            raise ClassificationError(
                ClassificationErrorCode.UNSAFE_PATH,
                f"ClassificationPolicy rules[{index}].result.path is required",
            )
        category = bounded_string("category") or (
            path_parts[0] if path_parts and path_parts[0] else "path"
        )
        subcategory = bounded_string("subcategory")

        def condition_strings(field: str) -> tuple[str, ...]:
            raw = conditions.get(field, [])
            if not isinstance(raw, list) or len(raw) > 64:
                raise ClassificationError(
                    ClassificationErrorCode.INVALID_RULE,
                    f"ClassificationPolicy rules[{index}].conditions.{field} must be a "
                    "bounded array",
                )
            values: list[str] = []
            for item in raw:
                if (
                    not isinstance(item, str)
                    or not item.strip()
                    or len(item) > 200
                    or "\x00" in item
                ):
                    raise ClassificationError(
                        ClassificationErrorCode.INVALID_RULE,
                        f"ClassificationPolicy rules[{index}].conditions.{field} contains "
                        "invalid text",
                    )
                values.append(item)
            return tuple(values)

        media_type_value = conditions.get("mediaType", conditions.get("mediaTypes", []))
        if isinstance(media_type_value, str):
            media_type_value = [media_type_value]
        if not isinstance(media_type_value, list) or len(media_type_value) > 8:
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                f"ClassificationPolicy rules[{index}].conditions.mediaType must be bounded",
            )
        try:
            media_types = tuple(MediaType(item) for item in media_type_value)
        except (TypeError, ValueError) as error:
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                f"ClassificationPolicy rules[{index}].conditions.mediaType is unsupported",
            ) from error
        canonical_year = conditions.get("canonicalYear")
        if canonical_year is not None and (
            isinstance(canonical_year, bool)
            or not isinstance(canonical_year, int)
            or not 0 <= canonical_year <= 9999
        ):
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                f"ClassificationPolicy rules[{index}].conditions.canonicalYear must be a "
                "bounded integer",
            )
        year_min = canonical_year if canonical_year is not None else conditions.get("yearMin")
        year_max = canonical_year if canonical_year is not None else conditions.get("yearMax")
        for field, raw in (("yearMin", year_min), ("yearMax", year_max)):
            if raw is not None and (
                isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= 9999
            ):
                raise ClassificationError(
                    ClassificationErrorCode.INVALID_RULE,
                    f"ClassificationPolicy rules[{index}].conditions.{field} must be a "
                    "bounded integer",
                )
        priority = cls._int(value, "priority", 0, f"ClassificationPolicy rules[{index}]")
        enabled = cls._bool(value, "enabled", True, f"ClassificationPolicy rules[{index}]")
        confidence = cls._bounded_number(
            value,
            "confidence",
            100,
            minimum=0,
            maximum=100,
            label=f"ClassificationPolicy rules[{index}]",
        )
        description = cls._text(
            value, "description", "", 500, f"ClassificationPolicy rules[{index}]"
        )
        try:
            domain = ClassificationRule(
                rule_id,
                name,
                media_library_id or "",
                library or "",
                category or "",
                priority=priority,
                enabled=enabled,
                subcategory=subcategory,
                relative_category_path=relative_path,
                media_types=media_types,
                genres=condition_strings("genres"),
                countries=condition_strings("countries"),
                languages=condition_strings("languages"),
                year_min=year_min,
                year_max=year_max,
                keywords=condition_strings("keywords"),
                confidence=confidence,
                description=description,
            )
        except ClassificationError as error:
            if error.code is not ClassificationErrorCode.UNSAFE_PATH:
                raise
            raise ClassificationError(
                error.code,
                f"ClassificationPolicy rules[{index}].result.path: {error}",
            ) from error
        normalized_conditions: dict[str, object] = {}
        if media_types:
            normalized_conditions["mediaType"] = [item.value for item in media_types]
        for field, values in (
            ("genres", domain.genres),
            ("countries", domain.countries),
            ("languages", domain.languages),
            ("keywords", domain.keywords),
        ):
            if values:
                normalized_conditions[field] = list(values)
        if canonical_year is not None:
            normalized_conditions["canonicalYear"] = canonical_year
        else:
            if year_min is not None:
                normalized_conditions["yearMin"] = year_min
            if year_max is not None:
                normalized_conditions["yearMax"] = year_max
        normalized_result: dict[str, object] = {
            "mediaLibraryId": media_library_id or "",
            "library": library or "",
            "path": list(path_parts),
        }
        if result.get("category") is not None:
            normalized_result["category"] = category or ""
        if subcategory is not None:
            normalized_result["subcategory"] = subcategory
        normalized = {
            "id": rule_id,
            "name": name,
            "priority": priority,
            "enabled": enabled,
            "confidence": confidence,
            "description": description,
            "conditions": normalized_conditions,
            "result": normalized_result,
        }
        return domain, normalized

    @classmethod
    def _recognition_condition(cls, value: object, *, depth: int = 0) -> object:
        if depth > 16 or not isinstance(value, Mapping):
            raise ValueError("RecognitionRule condition must be a bounded object")
        if "field" in value:
            allowed = {"field", "operator", "value", "caseSensitive"}
            if unknown := set(value).difference(allowed):
                raise ValueError(
                    f"RecognitionRule condition has unsupported field {sorted(unknown)[0]!r}"
                )
            AtomicCondition(
                ConditionField(str(value.get("field", ""))),
                ConditionOperator(str(value.get("operator", ""))),
                value.get("value"),
                cls._bool(value, "caseSensitive", False, "RecognitionRule condition"),
            )
            return value
        allowed = {"operator", "children"}
        if unknown := set(value).difference(allowed):
            raise ValueError(
                f"RecognitionRule condition has unsupported field {sorted(unknown)[0]!r}"
            )
        raw_children = value.get("children", [])
        if not isinstance(raw_children, list) or len(raw_children) > 64:
            raise ValueError("RecognitionRule condition children must be a bounded array")
        children = tuple(
            cls._recognition_condition(child, depth=depth + 1) for child in raw_children
        )
        # Domain construction enforces always/not/and/or cardinality.
        LogicalCondition(LogicalOperator(str(value.get("operator", ""))), children)  # type: ignore[arg-type]
        return value

    @staticmethod
    def _bool(value: Mapping[str, object], field: str, default: bool, label: str) -> bool:
        result = value.get(field, default)
        if not isinstance(result, bool):
            raise ValueError(f"{label} {field} must be boolean")
        return result

    @staticmethod
    def _int(value: Mapping[str, object], field: str, default: int, label: str) -> int:
        result = value.get(field, default)
        if (
            isinstance(result, bool)
            or not isinstance(result, int)
            or result < -1_000_000
            or result > 1_000_000
        ):
            raise ValueError(f"{label} {field} must be a bounded integer")
        return result

    @staticmethod
    def _number(value: Mapping[str, object], field: str, default: float, label: str) -> float:
        result = value.get(field, default)
        if (
            isinstance(result, bool)
            or not isinstance(result, int | float)
            or not math.isfinite(result)
            or result < 0
            or result > 1_000_000
        ):
            raise ValueError(f"{label} {field} must be a bounded non-negative number")
        return float(result)

    @staticmethod
    def _bounded_number(
        value: Mapping[str, object],
        field: str,
        default: float,
        *,
        minimum: float,
        maximum: float,
        label: str,
    ) -> float:
        result = value.get(field, default)
        if (
            isinstance(result, bool)
            or not isinstance(result, int | float)
            or not math.isfinite(result)
            or result < minimum
            or result > maximum
        ):
            raise ValueError(f"{label} {field} must be between {minimum} and {maximum}")
        return float(result)

    @staticmethod
    def _bounded_int(
        value: Mapping[str, object],
        field: str,
        default: int,
        *,
        minimum: int,
        maximum: int,
        label: str,
    ) -> int:
        result = value.get(field, default)
        if (
            isinstance(result, bool)
            or not isinstance(result, int)
            or not minimum <= result <= maximum
        ):
            raise ValueError(f"{label} {field} must be between {minimum} and {maximum}")
        return result

    @staticmethod
    def _metadata_identifier(value: Mapping[str, object], field: str, label: str) -> str:
        result = value.get(field)
        if (
            not isinstance(result, str)
            or not result.strip()
            or len(result) > 64
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", result)
        ):
            raise ValueError(f"{label} {field} must be a bounded provider identifier")
        return result

    @staticmethod
    def _metadata_locale(value: object, field: str, *, language: bool) -> str | None:
        if value is None:
            return None
        pattern = (
            r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*" if language else r"(?:[A-Za-z]{2}|[0-9]{3})"
        )
        if not isinstance(value, str) or len(value) > 35 or not re.fullmatch(pattern, value):
            raise ValueError(f"MetadataPolicy {field} is invalid")
        return value

    @staticmethod
    def _text(
        value: Mapping[str, object], field: str, default: str, maximum: int, label: str
    ) -> str:
        result = value.get(field, default)
        if not isinstance(result, str) or len(result) > maximum:
            raise ValueError(f"{label} {field} must be bounded text")
        return result

    @classmethod
    def _bounded_object(cls, section: str, value: dict[str, object]) -> dict[str, object]:
        if len(repr(value).encode("utf-8")) > cls._MAX_OBJECT_BYTES:
            raise ValueError(f"{section} object is too large")
        return value

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
                if section not in document:
                    continue
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
            policies = (
                cls._canonical_objects(document, "classificationPolicies")
                if "classificationPolicies" in document
                else []
            )
            for policy_index, policy in enumerate(policies):
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
        elif kind is ConfigurationObjectKind.RECOGNITION_TYPE:
            for section, field in (
                ("recognitionRules", "outputRecognitionType"),
                ("recognitionTypePolicies", "recognitionType"),
            ):
                for index, item in enumerate(cls._canonical_objects(document, section)):
                    reference = cls._required_reference_id(
                        item, section=section, index=index, field=field
                    )
                    if reference == object_id:
                        collector.add(
                            ConfigurationReferenceItem(
                                section=section,
                                object_id=str(item["id"]),
                                field=field,
                            )
                        )
        elif kind is ConfigurationObjectKind.METADATA_POLICY:
            for index, item in enumerate(
                cls._canonical_objects(document, "recognitionTypePolicies")
            ):
                reference = cls._required_reference_id(
                    item,
                    section="recognitionTypePolicies",
                    index=index,
                    field="metadataPolicy",
                )
                if reference == object_id:
                    collector.add(
                        ConfigurationReferenceItem(
                            section="recognitionTypePolicies",
                            object_id=str(item["id"]),
                            field="metadataPolicy",
                        )
                    )
        elif kind is ConfigurationObjectKind.NAMING_POLICY:
            for index, item in enumerate(
                cls._canonical_objects(document, "recognitionTypePolicies")
            ):
                reference = cls._required_reference_id(
                    item,
                    section="recognitionTypePolicies",
                    index=index,
                    field="namingPolicy",
                )
                if reference == object_id:
                    collector.add(
                        ConfigurationReferenceItem(
                            section="recognitionTypePolicies",
                            object_id=str(item["id"]),
                            field="namingPolicy",
                        )
                    )
        elif kind is ConfigurationObjectKind.CLASSIFICATION_POLICY:
            for index, item in enumerate(
                cls._canonical_objects(document, "recognitionTypePolicies")
            ):
                reference = cls._required_reference_id(
                    item,
                    section="recognitionTypePolicies",
                    index=index,
                    field="classificationPolicy",
                )
                if reference == object_id:
                    collector.add(
                        ConfigurationReferenceItem(
                            section="recognitionTypePolicies",
                            object_id=str(item["id"]),
                            field="classificationPolicy",
                        )
                    )
        elif kind is ConfigurationObjectKind.ORGANIZE_POLICY:
            for index, item in enumerate(
                cls._canonical_objects(document, "recognitionTypePolicies")
            ):
                reference = cls._required_reference_id(
                    item,
                    section="recognitionTypePolicies",
                    index=index,
                    field="organizePolicy",
                )
                if reference == object_id:
                    collector.add(
                        ConfigurationReferenceItem(
                            section="recognitionTypePolicies",
                            object_id=str(item["id"]),
                            field="organizePolicy",
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
