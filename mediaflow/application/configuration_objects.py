from __future__ import annotations

import copy
import json
import math
import posixpath
import re
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePath
from threading import BoundedSemaphore, Lock, RLock

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.read_only_storage import (
    ReadOnlyStorageGuard,
    ReadOnlyStorageMutationError,
)
from mediaflow.application.strategy_test import (
    StrategyConfigurationError,
    StrategyTestResult,
    strategy_runner_from_configuration,
)
from mediaflow.domain.configuration_management import (
    CONFIGURATION_REFERENCE_EVIDENCE_LIMIT,
    CONFIGURATION_SETUP_CHECK_PATH_LIMIT,
    CONFIGURATION_STRATEGY_RESULT_LIMIT,
    ConfigurationActivationConflict,
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationReferenceEvidence,
    ConfigurationReferenceItem,
    ConfigurationSetupCheckStatus,
    ConfigurationStrategyTestStatus,
    ConfigurationVersionConflict,
    LocalSetupCheckEvidence,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
    ManagedDocumentRedactor,
    RecognitionStrategyTestEvidence,
)
from mediaflow.domain.metadata import (
    METADATA_POLICY_CONFIGURATION_FIELDS,
    MediaQueryType,
    MediaType,
    MetadataErrorCode,
    MetadataIdentificationStatus,
    MetadataPolicy,
    RetryPolicy,
)
from mediaflow.domain.metadata_review import MetadataSelection
from mediaflow.domain.recognition import (
    AtomicCondition,
    ConditionField,
    ConditionOperator,
    LogicalCondition,
    LogicalOperator,
    RecognitionStatus,
)
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.infrastructure.metadata_provider_bootstrap import MetadataProviderBootstrapError
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
        ConfigurationObjectKind.RECOGNITION_TYPE: "recognitionTypes",
        ConfigurationObjectKind.RECOGNITION_RULE: "recognitionRules",
        ConfigurationObjectKind.RECOGNITION_TYPE_POLICY: "recognitionTypePolicies",
        ConfigurationObjectKind.METADATA_POLICY: "metadataPolicies",
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
                "recognitionTypes": self._objects(document, "recognitionTypes"),
                "recognitionRules": self._objects(document, "recognitionRules"),
                "recognitionTypePolicies": self._objects(document, "recognitionTypePolicies"),
                "metadataPolicies": self._objects(document, "metadataPolicies"),
            },
            # Keep every versioned projection on the same immutable revision read.
            # Calling the public helpers here would re-read the repository and could
            # combine objects from one Draft with evidence from a concurrent edit.
            "references": self._references_from_document(document),
            "localSetupCheck": self._check_document(revision),
            "recognitionStrategyTest": self._strategy_test_document(revision),
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
                expected_evidence_tested_at=evidence.tested_at,
            )

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
        candidate_selection: dict[str, object] | None = None,
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
            if live_metadata and strategy.metadata_policy is not None:
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
                )
                result = self._strategy_result_document(strategy, live_metadata=True)
                if candidate_selection is not None and isinstance(result.get("metadata"), dict):
                    result["metadata"]["candidateSelection"] = candidate_selection
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
