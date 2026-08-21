from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from mediaflow.domain.organizer import OrganizePolicy
from mediaflow.domain.parser import FileContext, ParseResult


@dataclass(frozen=True)
class RecognitionType:
    type_id: str
    name: str
    description: str = ""
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.type_id.strip() or not self.name.strip():
            raise ValueError("recognition type id and name must not be empty")


class RecognitionStatus(StrEnum):
    MATCHED = "matched"
    UNRECOGNIZED = "unrecognized"
    AMBIGUOUS = "ambiguous"


class ConditionField(StrEnum):
    FILENAME = "filename"
    PATH = "path"
    DIRECTORY = "directory"
    EXTENSION = "extension"
    TITLE = "title_candidate"
    YEAR = "year"
    SEASON = "season"
    EPISODE = "episode"
    RESOLUTION = "resolution_tag"
    SOURCE = "source_tag"
    VIDEO_CODEC = "video_codec_tag"
    AUDIO_CODEC = "audio_codec_tag"
    AUDIO_CHANNELS = "audio_channels_tag"
    HDR = "hdr_tag"
    VERSION = "version_tag"
    RELEASE_GROUP = "release_group"
    LANGUAGE = "language_tag"
    RESOURCE_LIBRARY_ID = "resource_library_id"


class ConditionOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    REGEX = "regex"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    BETWEEN = "between"
    CONTAINS_ANY = "contains_any"
    CONTAINS_ALL = "contains_all"


class LogicalOperator(StrEnum):
    AND = "and"
    OR = "or"
    NOT = "not"
    ALWAYS = "always"


STRING_FIELDS = {
    ConditionField.FILENAME,
    ConditionField.PATH,
    ConditionField.EXTENSION,
    ConditionField.TITLE,
    ConditionField.RESOLUTION,
    ConditionField.SOURCE,
    ConditionField.VIDEO_CODEC,
    ConditionField.AUDIO_CODEC,
    ConditionField.AUDIO_CHANNELS,
    ConditionField.RELEASE_GROUP,
    ConditionField.RESOURCE_LIBRARY_ID,
}
NUMERIC_FIELDS = {ConditionField.YEAR, ConditionField.SEASON, ConditionField.EPISODE}
COLLECTION_FIELDS = {
    ConditionField.DIRECTORY,
    ConditionField.HDR,
    ConditionField.VERSION,
    ConditionField.LANGUAGE,
}
STRING_OPERATORS = {
    ConditionOperator.EQUALS,
    ConditionOperator.NOT_EQUALS,
    ConditionOperator.CONTAINS,
    ConditionOperator.NOT_CONTAINS,
    ConditionOperator.STARTS_WITH,
    ConditionOperator.ENDS_WITH,
    ConditionOperator.IN,
    ConditionOperator.NOT_IN,
    ConditionOperator.REGEX,
}
NUMERIC_OPERATORS = {
    ConditionOperator.EQUALS,
    ConditionOperator.NOT_EQUALS,
    ConditionOperator.GREATER_THAN,
    ConditionOperator.GREATER_THAN_OR_EQUAL,
    ConditionOperator.LESS_THAN,
    ConditionOperator.LESS_THAN_OR_EQUAL,
    ConditionOperator.BETWEEN,
    ConditionOperator.IN,
}
COLLECTION_OPERATORS = {
    ConditionOperator.CONTAINS,
    ConditionOperator.NOT_CONTAINS,
    ConditionOperator.CONTAINS_ANY,
    ConditionOperator.CONTAINS_ALL,
}


@dataclass(frozen=True)
class AtomicCondition:
    field: ConditionField
    operator: ConditionOperator
    value: Any
    case_sensitive: bool = False
    _compiled_regex: re.Pattern[str] | None = field(
        default=None, init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if self.field in STRING_FIELDS:
            allowed = STRING_OPERATORS
        elif self.field in NUMERIC_FIELDS:
            allowed = NUMERIC_OPERATORS
        else:
            allowed = COLLECTION_OPERATORS
        if self.operator not in allowed:
            raise ValueError(f"operator {self.operator} is incompatible with field {self.field}")
        collection_operators = {
            ConditionOperator.IN,
            ConditionOperator.NOT_IN,
            ConditionOperator.BETWEEN,
            ConditionOperator.CONTAINS_ANY,
            ConditionOperator.CONTAINS_ALL,
        }
        if self.operator in collection_operators and (
            isinstance(self.value, (str, bytes))
            or not isinstance(self.value, (tuple, list, set, frozenset))
        ):
            raise ValueError(f"operator {self.operator} requires a collection value")
        if self.operator is ConditionOperator.BETWEEN and len(self.value) != 2:
            raise ValueError("between requires exactly two bounds")
        if self.operator is ConditionOperator.REGEX:
            pattern = str(self.value)
            if len(pattern) > 256 or _looks_like_dangerous_regex(pattern):
                raise ValueError("regex exceeds safety limits")
            try:
                compiled = re.compile(pattern, 0 if self.case_sensitive else re.IGNORECASE)
            except re.error as error:
                raise ValueError(f"invalid regex: {error}") from error
            object.__setattr__(self, "_compiled_regex", compiled)


@dataclass(frozen=True)
class LogicalCondition:
    operator: LogicalOperator
    children: tuple[RecognitionCondition, ...] = ()

    def __post_init__(self) -> None:
        if self.operator is LogicalOperator.ALWAYS and self.children:
            raise ValueError("always condition cannot have children")
        if self.operator is LogicalOperator.NOT and len(self.children) != 1:
            raise ValueError("not condition requires exactly one child")
        if self.operator in {LogicalOperator.AND, LogicalOperator.OR} and not self.children:
            raise ValueError(f"{self.operator} condition requires children")


RecognitionCondition = AtomicCondition | LogicalCondition


@dataclass(frozen=True)
class RecognitionRule:
    rule_id: str
    name: str
    condition: RecognitionCondition
    output_recognition_type_id: str
    enabled: bool = True
    priority: int = 0
    score: float = 1.0
    stop_on_match: bool = False
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if (
            not self.rule_id.strip()
            or not self.name.strip()
            or not self.output_recognition_type_id.strip()
        ):
            raise ValueError("rule id, name, and output recognition type id must not be empty")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise ValueError("rule priority must be an integer")
        if (
            isinstance(self.score, bool)
            or not isinstance(self.score, (int, float))
            or self.score < 0
        ):
            raise ValueError("rule score must be a non-negative number")


@dataclass(frozen=True)
class RecognitionContext:
    file_context: FileContext
    parse_result: ParseResult


@dataclass(frozen=True)
class RecognitionEvidence:
    rule_id: str
    field: str
    operator: str
    expected: str
    actual: str


@dataclass(frozen=True)
class RecognitionReason:
    code: str
    message: str


@dataclass(frozen=True)
class MatchedRule:
    rule_id: str
    recognition_type_id: str
    priority: int
    score: float


@dataclass(frozen=True)
class RecognitionAlternative:
    recognition_type_id: str
    score: float
    priority: int


@dataclass(frozen=True)
class RecognitionResult:
    # Preserve the bootstrap positional constructor used by Organizer tests.
    recognition_type: RecognitionType | None = None
    rule_id: str = ""
    confidence: float = 1.0
    status: RecognitionStatus = RecognitionStatus.MATCHED
    matched_rules: tuple[MatchedRule, ...] = ()
    score: float = 0.0
    evidence: tuple[RecognitionEvidence, ...] = ()
    reasons: tuple[RecognitionReason, ...] = ()
    warnings: tuple[str, ...] = ()
    alternatives: tuple[RecognitionAlternative, ...] = ()

    @property
    def recognition_type_id(self) -> str | None:
        return self.recognition_type.type_id if self.recognition_type else None


@dataclass(frozen=True)
class RecognitionTypePolicy:
    # Preserve the bootstrap positional constructor used by existing callers.
    policy_id: str
    recognition_type: RecognitionType
    metadata_policy_id: str
    naming_policy_id: str
    classification_policy_id: str
    organize_policy: OrganizePolicy
    name: str = ""
    enabled: bool = True
    priority: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        identifiers = (
            self.policy_id,
            self.recognition_type.type_id,
            self.metadata_policy_id,
            self.naming_policy_id,
            self.classification_policy_id,
            self.organize_policy.policy_id,
        )
        if not all(identifier.strip() for identifier in identifiers):
            raise ValueError("policy identifiers must not be empty")

    @property
    def recognition_type_id(self) -> str:
        return self.recognition_type.type_id

    @property
    def organize_policy_id(self) -> str:
        return self.organize_policy.policy_id


@dataclass(frozen=True)
class PolicyReference:
    policy_id: str
    enabled: bool = True


@dataclass(frozen=True)
class ResolvedRecognitionPolicy:
    recognition_type: RecognitionType
    metadata_policy_id: str
    naming_policy_id: str
    classification_policy_id: str
    organize_policy_id: str
    type_policy_id: str

    @property
    def recognition_type_id(self) -> str:
        return self.recognition_type.type_id


class PolicyResolutionErrorCode(StrEnum):
    MISSING_TYPE_POLICY = "missing_type_policy"
    DUPLICATE_TYPE_POLICY = "duplicate_type_policy"
    INVALID_POLICY_REFERENCE = "invalid_policy_reference"
    POLICY_DISABLED = "policy_disabled"
    RECOGNITION_TYPE_DISABLED = "recognition_type_disabled"


class PolicyResolutionError(LookupError):
    def __init__(self, code: PolicyResolutionErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _looks_like_dangerous_regex(pattern: str) -> bool:
    # The stdlib engine has no timeout. Reject common catastrophic nested
    # quantifiers/backreferences and cap both pattern and evaluated input.
    return bool(re.search(r"\\[1-9]|\([^)]*[+*][^)]*\)[+*{]", pattern))
