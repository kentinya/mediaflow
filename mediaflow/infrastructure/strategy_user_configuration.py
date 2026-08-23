from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from mediaflow.application.strategy_test import StrategyTestConfiguration
from mediaflow.domain.classification import ClassificationPolicy, ClassificationRule
from mediaflow.domain.duplicates import HashMode, HashPolicy
from mediaflow.domain.metadata import (
    CachePolicy,
    MediaQueryType,
    MediaType,
    MetadataPolicy,
    RetryPolicy,
)
from mediaflow.domain.naming import (
    MissingVariableStrategy,
    NamingMediaTypeMode,
    NamingPolicy,
)
from mediaflow.domain.organizer import (
    AttachmentPolicy,
    ConflictStrategy,
    DirectoryCleanupMode,
    DirectoryCleanupPolicy,
    OrganizeOperationType,
    OrganizePolicy,
    RollbackPolicy,
)
from mediaflow.domain.recognition import (
    AtomicCondition,
    ConditionField,
    ConditionOperator,
    LogicalCondition,
    LogicalOperator,
    RecognitionCondition,
    RecognitionRule,
    RecognitionType,
    RecognitionTypePolicy,
)
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration


@dataclass(frozen=True)
class ResourceLibraryBinding:
    library_id: str
    root_path: str | None = None

    def __post_init__(self) -> None:
        if not self.library_id.strip():
            raise ValueError("resource library ID is required")
        if self.root_path is not None and not self.root_path.strip():
            raise ValueError("ResourceLibrary displayRootPath must be non-empty when configured")


@dataclass(frozen=True)
class LoadedStrategyConfiguration:
    strategy: StrategyTestConfiguration
    resource_libraries: tuple[ResourceLibraryBinding, ...]


def load_strategy_configuration(
    document: Any,
    *,
    base: StrategyTestConfiguration | None = None,
    require_complete: bool = False,
) -> LoadedStrategyConfiguration:
    """Convert user JSON data into the same immutable models used by production services."""
    if not isinstance(document, Mapping):
        raise ValueError("strategy configuration must be a JSON object")
    if document.get("version", 1) != 1:
        raise ValueError("unsupported strategy configuration version")
    if base is None and not require_complete:
        base = development_strategy_configuration()
    types = tuple(_recognition_type(item) for item in _list(document, "recognitionTypes"))
    type_by_id = {item.type_id: item for item in types}
    if len(type_by_id) != len(types):
        raise ValueError("recognitionTypes IDs must be unique")
    rules = tuple(_rule(item) for item in _list(document, "recognitionRules"))
    organize_policies = _organize_policies(document, base, require_complete)
    organize_by_id = {policy.policy_id: policy for policy in organize_policies}
    type_policies = tuple(
        _type_policy(item, type_by_id, organize_by_id, require_complete)
        for item in _list(document, "recognitionTypePolicies")
    )
    libraries = tuple(
        ResourceLibraryBinding(_string(item, "id"), _resource_display_root(item))
        for item in _objects(document, "resourceLibraries")
    )
    if len({item.library_id for item in libraries}) != len(libraries):
        raise ValueError("resourceLibraries IDs must be unique")
    metadata_policies = _metadata_policies(document, base, require_complete)
    naming_policies = _naming_policies(document, base, require_complete)
    classification_policies = _classification_policies(document, base, require_complete)
    return LoadedStrategyConfiguration(
        StrategyTestConfiguration(
            types,
            rules,
            type_policies,
            metadata_policies,
            naming_policies,
            classification_policies,
            organize_policies,
        ),
        libraries,
    )


def _resource_display_root(item: Mapping[str, Any]) -> str | None:
    value = item.get("displayRootPath", item.get("rootPath"))
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("ResourceLibrary displayRootPath must be a non-empty string")
    return value


def _naming_policies(document, base, required):
    values = _objects(document, "namingPolicies", required=False)
    if not values:
        if required:
            raise ValueError("runtime configuration 'namingPolicies' must not be empty")
        assert base is not None
        return base.naming_policies
    policies = tuple(
        NamingPolicy(
            _string(item, "id"),
            str(item.get("name") or item["id"]),
            item.get("directoryTemplate", item.get("movieDirectoryTemplate", "{title} ({year})")),
            item.get("filenameTemplate", item.get("movieFileTemplate", "{title} ({year}).{ext}")),
            item.get(
                "seriesDirectoryTemplate", item.get("tvSeriesDirectoryTemplate", "{title} ({year})")
            ),
            item.get(
                "seasonDirectoryTemplate",
                item.get("tvSeasonDirectoryTemplate", "Season {season:02}"),
            ),
            item.get(
                "episodeFilenameTemplate",
                item.get(
                    "tvEpisodeFileTemplate",
                    "{title} - S{season:02}E{episode:02} - {episode_title}.{ext}",
                ),
            ),
            item.get("multiEpisodeFileTemplate", "{title} - S{season:02}{episodes}.{ext}"),
            str(item.get("description", "")),
            _boolean(item, "enabled", True),
            NamingMediaTypeMode(str(item.get("mediaTypeMode", "auto"))),
            MissingVariableStrategy(str(item.get("missingVariableStrategy", "omit_token"))),
            max_component_length=_integer(item, "maxComponentLength", 200),
        )
        for item in values
    )
    _unique(policies, lambda item: item.policy_id, "namingPolicies")
    return policies


def _classification_policies(document, base, required):
    values = _objects(document, "classificationPolicies", required=False)
    if not values:
        if required:
            raise ValueError("runtime configuration 'classificationPolicies' must not be empty")
        assert base is not None
        return base.classification_policies
    policies = tuple(
        ClassificationPolicy(
            _string(item, "id"),
            str(item.get("name") or item["id"]),
            tuple(_classification_rule(rule) for rule in _objects(item, "rules")),
            str(item.get("description", "")),
            _boolean(item, "enabled", True),
            _integer(item, "priority", 0),
        )
        for item in values
    )
    _unique(policies, lambda item: item.policy_id, "classificationPolicies")
    return policies


def _classification_rule(value: Mapping[str, Any]) -> ClassificationRule:
    nested = "conditions" in value or "result" in value
    conditions = value.get("conditions", value)
    result = value.get("result", value)
    if not isinstance(conditions, Mapping) or not isinstance(result, Mapping):
        raise ValueError("classification rule conditions/result must be objects")
    allowed_conditions = {
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
    unknown_conditions = set(conditions) - allowed_conditions if nested else set()
    if unknown_conditions:
        raise ValueError(f"unsupported classification conditions: {sorted(unknown_conditions)}")
    allowed_result = {"mediaLibraryId", "library", "path", "category", "subcategory"}
    unknown_result = set(result) - allowed_result if nested else set()
    if unknown_result:
        raise ValueError(f"unsupported classification result fields: {sorted(unknown_result)}")
    path_value = result.get("path", value.get("relativePath"))
    if isinstance(path_value, list):
        if not all(isinstance(item, str) and item.strip() for item in path_value):
            raise ValueError("classification result path must contain non-empty strings")
        relative_path = "/".join(path_value)
    elif path_value is None or isinstance(path_value, str):
        relative_path = path_value
    else:
        raise ValueError("classification result path must be a string or array")
    library = _string(result, "library")
    category = str(
        result.get("category")
        or (path_value[0] if isinstance(path_value, list) and path_value else "")
    )
    if not category:
        raise ValueError("classification rule category or result.path is required")
    media_types = conditions.get("mediaType", conditions.get("mediaTypes", []))
    if isinstance(media_types, str):
        media_types = [media_types]
    normalized_conditions = dict(conditions)
    normalized_conditions["mediaTypes"] = media_types
    canonical_year = conditions.get("canonicalYear")
    if canonical_year is not None:
        if isinstance(canonical_year, bool) or not isinstance(canonical_year, int):
            raise ValueError("classification canonicalYear must be an integer")
        normalized_conditions["yearMin"] = canonical_year
        normalized_conditions["yearMax"] = canonical_year
    return ClassificationRule(
        _string(value, "id"),
        str(value.get("name") or value["id"]),
        str(result.get("mediaLibraryId") or _slug(library)),
        library,
        category,
        priority=_integer(value, "priority", 0),
        enabled=_boolean(value, "enabled", True),
        subcategory=_optional_string(result, "subcategory", None),
        relative_category_path=relative_path,
        media_types=tuple(
            MediaType(item) for item in _string_list(normalized_conditions, "mediaTypes")
        ),
        genres=_string_list(conditions, "genres"),
        countries=_string_list(conditions, "countries"),
        languages=_string_list(conditions, "languages"),
        year_min=_optional_integer(normalized_conditions, "yearMin"),
        year_max=_optional_integer(normalized_conditions, "yearMax"),
        keywords=_string_list(conditions, "keywords"),
        confidence=_number(value, "confidence", 100),
        description=str(value.get("description", "")),
    )


def _metadata_policies(document, base, required):
    overrides = _objects(document, "metadataPolicies", required=False)
    if not overrides:
        if required:
            raise ValueError("runtime configuration 'metadataPolicies' must not be empty")
        assert base is not None
        return base.metadata_policies
    policies = {} if required else {policy.policy_id: policy for policy in base.metadata_policies}  # type: ignore[union-attr]
    for value in overrides:
        policy_id = _string(value, "id")
        if not required and policy_id in policies:
            current = policies[policy_id]
            media_type = value.get("mediaType")
            query_type = value.get("mediaQueryType")
            policies[policy_id] = replace(
                current,
                provider_id=str(value.get("providerId", current.provider_id)),
                media_type=MediaType(media_type) if media_type is not None else current.media_type,
                media_query_type=MediaQueryType(query_type)
                if query_type is not None
                else current.media_query_type,
                language=_optional_string(value, "language", current.language),
                region=_optional_string(value, "region", current.region),
                automatic_threshold=_number(
                    value, "automaticThreshold", current.automatic_threshold
                ),
                confirmation_threshold=_number(
                    value, "confirmationThreshold", current.confirmation_threshold
                ),
                minimum_score_gap=_number(value, "minimumScoreGap", current.minimum_score_gap),
                max_provider_requests=_integer(
                    value, "maxProviderRequests", current.max_provider_requests
                ),
                max_candidate_enrichments=_integer(
                    value, "maxCandidateEnrichments", current.max_candidate_enrichments
                ),
            )
            continue
        media_type = value.get("mediaType")
        query_type = value.get("mediaQueryType")
        policies[policy_id] = MetadataPolicy(
            policy_id,
            _string(value, "providerId"),
            MediaType(media_type) if media_type is not None else None,
            _optional_string(value, "language", None),
            _optional_string(value, "region", None),
            str(value.get("name") or policy_id),
            MediaQueryType(query_type) if query_type is not None else None,
            _number(value, "automaticThreshold", 90),
            _number(value, "confirmationThreshold", 70),
            _number(value, "minimumScoreGap", 5),
            _number(value, "timeout", 10),
            RetryPolicy(_integer(value, "retryCount", 2)),
            CachePolicy(),
            _integer(value, "maxCandidates", 20),
            _integer(value, "maxSearchPages", 2),
            _integer(value, "maxProviderRequests", 6),
            _integer(value, "maxCandidateEnrichments", 2),
            _boolean(value, "enabled", True),
        )
    if required and len(policies) != len(overrides):
        raise ValueError("metadataPolicies IDs must be unique")
    return tuple(policies.values())


def _organize_policies(document, base, required):
    values = _objects(document, "organizePolicies", required=False)
    if not values:
        if required:
            raise ValueError("runtime configuration 'organizePolicies' must not be empty")
        assert base is not None
        inherited = getattr(base, "organize_policies", ())
        if inherited:
            return inherited
        return tuple(policy.organize_policy for policy in base.recognition_type_policies)
    policies = tuple(_organize_policy(item) for item in values)
    _unique(policies, lambda item: item.policy_id, "organizePolicies")
    return policies


def _organize_policy(item: Mapping[str, Any]) -> OrganizePolicy:
    legacy_overwrite = _boolean(item, "overwrite", False)
    raw_strategy = item.get("conflictStrategy")
    if raw_strategy is None:
        strategy = ConflictStrategy.OVERWRITE if legacy_overwrite else ConflictStrategy.MANUAL
    else:
        try:
            strategy = ConflictStrategy(str(raw_strategy).casefold())
        except ValueError as error:
            raise ValueError(
                "organize policy conflictStrategy must be skip, rename, manual, or overwrite"
            ) from error
        if legacy_overwrite and strategy is not ConflictStrategy.OVERWRITE:
            raise ValueError("overwrite=true conflicts with the configured conflictStrategy")
    return OrganizePolicy(
        _string(item, "id"),
        _organize_operation(_string(item, "operation")),
        strategy,
        _attachment_policy(item.get("attachments")),
        _hash_policy(item.get("duplicateDetection")),
        _rollback_policy(item.get("rollback")),
        _directory_cleanup_policy(item.get("sourceDirectoryCleanup")),
    )


def _attachment_policy(value: Any) -> AttachmentPolicy:
    if value is None:
        return AttachmentPolicy()
    if not isinstance(value, Mapping):
        raise ValueError("organize policy attachments must be an object")
    allowed = {"enabled", "subtitles", "nfo", "artwork", "trailers", "otherSameStem"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"unknown attachment policy field: {sorted(unknown)[0]}")
    for key in value:
        if not isinstance(value[key], bool):
            raise ValueError(f"attachment policy {key} must be boolean")
    return AttachmentPolicy(
        enabled=value.get("enabled", False),
        subtitles=value.get("subtitles", True),
        nfo=value.get("nfo", True),
        artwork=value.get("artwork", True),
        trailers=value.get("trailers", True),
        other_same_stem=value.get("otherSameStem", False),
    )


def _hash_policy(value: Any) -> HashPolicy:
    if value is None:
        return HashPolicy()
    if not isinstance(value, Mapping):
        raise ValueError("organize policy duplicateDetection must be an object")
    allowed = {"mode", "fastSampleBytes", "fullMaxFileSize", "chunkSize"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"unknown duplicateDetection field: {sorted(unknown)[0]}")
    raw_mode = value.get("mode", "none")
    if not isinstance(raw_mode, str):
        raise ValueError("duplicateDetection mode must be none, fast, or full")
    try:
        mode = HashMode(raw_mode.casefold())
    except ValueError as error:
        raise ValueError("duplicateDetection mode must be none, fast, or full") from error
    return HashPolicy(
        mode,
        _integer(value, "fastSampleBytes", 1_048_576),
        _integer(value, "fullMaxFileSize", 1_099_511_627_776),
        _integer(value, "chunkSize", 1_048_576),
    )


def _rollback_policy(value: Any) -> RollbackPolicy:
    if value is None:
        return RollbackPolicy()
    if not isinstance(value, Mapping):
        raise ValueError("organize policy rollback must be an object")
    allowed = {"enabled", "cleanupCreatedDirectories"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"unknown rollback policy field: {sorted(unknown)[0]}")
    return RollbackPolicy(
        _boolean(value, "enabled", False),
        _boolean(value, "cleanupCreatedDirectories", True),
    )


def _directory_cleanup_policy(value: Any) -> DirectoryCleanupPolicy:
    if value is None:
        return DirectoryCleanupPolicy()
    if not isinstance(value, Mapping):
        raise ValueError("sourceDirectoryCleanup must be an object")
    allowed = {"mode", "maxParentDirectories", "ignorePatterns", "maxEntries"}
    if unknown := set(value) - allowed:
        raise ValueError(f"unknown sourceDirectoryCleanup field: {sorted(unknown)[0]}")
    raw_mode = value.get("mode", "none")
    if not isinstance(raw_mode, str):
        raise ValueError("sourceDirectoryCleanup mode must be none, empty, or ignorable")
    try:
        mode = DirectoryCleanupMode(raw_mode.casefold())
    except ValueError as error:
        raise ValueError("sourceDirectoryCleanup mode must be none, empty, or ignorable") from error
    patterns = value.get("ignorePatterns", [])
    if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
        raise ValueError("sourceDirectoryCleanup ignorePatterns must be an array of strings")
    return DirectoryCleanupPolicy(
        mode,
        _integer(value, "maxParentDirectories", 1),
        tuple(patterns),
        _integer(value, "maxEntries", 100),
    )


def _recognition_type(value: Mapping[str, Any]) -> RecognitionType:
    return RecognitionType(
        _string(value, "id"),
        _string(value, "name"),
        str(value.get("description", "")),
        _boolean(value, "enabled", True),
    )


def _rule(value: Mapping[str, Any]) -> RecognitionRule:
    return RecognitionRule(
        _string(value, "id"),
        _string(value, "name"),
        _condition(_object(value, "condition")),
        _string(value, "outputRecognitionType"),
        _boolean(value, "enabled", True),
        _integer(value, "priority", 0),
        _number(value, "score", 1),
        _boolean(value, "stopOnMatch", False),
        str(value.get("description", "")),
    )


def _condition(value: Mapping[str, Any]) -> RecognitionCondition:
    if "field" in value:
        return AtomicCondition(
            ConditionField(_string(value, "field")),
            ConditionOperator(_string(value, "operator")),
            value.get("value"),
            _boolean(value, "caseSensitive", False),
        )
    operator = LogicalOperator(_string(value, "operator"))
    children = tuple(_condition(item) for item in _objects(value, "children", required=False))
    return LogicalCondition(operator, children)


def _type_policy(value, types, organize_policies, require_complete) -> RecognitionTypePolicy:
    type_id = _string(value, "recognitionType")
    try:
        recognition_type = types[type_id]
    except KeyError as error:
        raise ValueError(f"type policy references unknown RecognitionType {type_id!r}") from error
    organize_id = _string(value, "organizePolicy")
    organize_policy = organize_policies.get(organize_id)
    if organize_policy is None and not require_complete and "organizeOperation" in value:
        organize_policy = OrganizePolicy(
            organize_id, _organize_operation(str(value["organizeOperation"]))
        )
    if organize_policy is None:
        raise ValueError(f"RecognitionTypePolicy references unknown OrganizePolicy {organize_id!r}")
    return RecognitionTypePolicy(
        _string(value, "id"),
        recognition_type,
        _string(value, "metadataPolicy"),
        _string(value, "namingPolicy"),
        _string(value, "classificationPolicy"),
        organize_policy,
        str(value.get("name", "")),
        _boolean(value, "enabled", True),
        _integer(value, "priority", 0),
    )


def _list(document: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    values = _objects(document, key)
    if not values:
        raise ValueError(f"strategy configuration {key!r} must not be empty")
    return values


def _objects(
    document: Mapping[str, Any], key: str, *, required: bool = True
) -> list[Mapping[str, Any]]:
    values = document.get(key)
    if values is None and not required:
        return []
    if not isinstance(values, list) or not all(isinstance(item, Mapping) for item in values):
        raise ValueError(f"strategy configuration {key!r} must be an array of objects")
    return values


def _object(document: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = document.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"strategy configuration {key!r} must be an object")
    return value


def _string(document: Mapping[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"strategy configuration {key!r} must be a non-empty string")
    return value


def _optional_string(document: Mapping[str, Any], key: str, default: str | None) -> str | None:
    value = document.get(key, default)
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"strategy configuration {key!r} must be a string or null")
    return value


def _boolean(document: Mapping[str, Any], key: str, default: bool) -> bool:
    value = document.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"strategy configuration {key!r} must be a boolean")
    return value


def _integer(document: Mapping[str, Any], key: str, default: int) -> int:
    value = document.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"strategy configuration {key!r} must be an integer")
    return value


def _number(document: Mapping[str, Any], key: str, default: float) -> float:
    value = document.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"strategy configuration {key!r} must be a number")
    return float(value)


def _string_list(document: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = document.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"strategy configuration {key!r} must be an array of strings")
    return tuple(value)


def _optional_integer(document: Mapping[str, Any], key: str) -> int | None:
    value = document.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"strategy configuration {key!r} must be an integer or null")
    return value


def _organize_operation(value: str) -> OrganizeOperationType:
    aliases = {
        "MOVE": "move",
        "COPY": "copy",
        "HARDLINK": "hard_link",
        "HARD_LINK": "hard_link",
        "SYMLINK": "soft_link",
        "SOFTLINK": "soft_link",
        "SOFT_LINK": "soft_link",
    }
    try:
        return OrganizeOperationType(aliases.get(value.upper(), value.lower()))
    except ValueError as error:
        raise ValueError(f"unsupported organize operation {value!r}") from error


def _unique(values, key, label):
    ids = [key(item) for item in values]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{label} IDs must be unique")


def _slug(value: str) -> str:
    return value.strip().casefold().replace(" ", "-")
