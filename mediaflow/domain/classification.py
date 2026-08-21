from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from enum import StrEnum

from mediaflow.domain.metadata import MediaIdentity, MediaType
from mediaflow.domain.naming import NamingResult
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.recognition import RecognitionType


class ClassificationStatus(StrEnum):
    CLASSIFIED = "classified"
    UNCLASSIFIED = "unclassified"


class ClassificationErrorCode(StrEnum):
    POLICY_NOT_FOUND = "policy_not_found"
    POLICY_DISABLED = "policy_disabled"
    INVALID_POLICY = "invalid_policy"
    INVALID_RULE = "invalid_rule"
    UNSAFE_PATH = "unsafe_path"


class ClassificationError(ValueError):
    def __init__(self, code: ClassificationErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ClassificationRule:
    rule_id: str
    name: str
    media_library_id: str
    library: str
    category: str
    priority: int = 0
    enabled: bool = True
    subcategory: str | None = None
    relative_category_path: str | None = None
    media_types: tuple[MediaType, ...] = ()
    genres: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    year_min: int | None = None
    year_max: int | None = None
    keywords: tuple[str, ...] = ()
    confidence: float = 100
    description: str = ""

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.rule_id, self.name, self.media_library_id)):
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                "classification rule ID, name, and media library ID are required",
            )
        if not self.library.strip() or not self.category.strip():
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                "classification library and category are required",
            )
        if (
            self.year_min is not None
            and self.year_max is not None
            and self.year_min > self.year_max
        ):
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE, "classification year range is invalid"
            )
        if not 0 <= self.confidence <= 100:
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                "classification confidence must be between 0 and 100",
            )
        for collection in (self.genres, self.countries, self.languages, self.keywords):
            if any(not value.strip() for value in collection):
                raise ClassificationError(
                    ClassificationErrorCode.INVALID_RULE,
                    "classification condition values must not be empty",
                )
        path = self.relative_category_path or _category_path(self.category, self.subcategory)
        _validate_relative_path(path)
        object.__setattr__(self, "relative_category_path", path)


@dataclass(frozen=True)
class ClassificationPolicy:
    policy_id: str
    name: str
    rules: tuple[ClassificationRule, ...] = field(default_factory=tuple)
    description: str = ""
    enabled: bool = True
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or not self.name.strip():
            raise ClassificationError(
                ClassificationErrorCode.INVALID_POLICY,
                "classification policy ID and name are required",
            )
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ClassificationError(
                ClassificationErrorCode.INVALID_POLICY,
                "classification rule IDs must be unique within a policy",
            )


@dataclass(frozen=True)
class ClassificationContext:
    recognition_type: RecognitionType
    media_identity: MediaIdentity
    parse_result: ParseResult
    naming_result: NamingResult | None = None

    @property
    def recognition_type_id(self) -> str:
        return self.recognition_type.type_id


@dataclass(frozen=True)
class ClassificationResult:
    # Preserve the Phase 0 positional constructor used by OrganizePlanner.
    media_library_id: str = ""
    relative_path: str = ""
    policy_id: str = ""
    recognition_type_id: str = ""
    status: ClassificationStatus = ClassificationStatus.CLASSIFIED
    matched_rule_id: str | None = None
    matched_rule_name: str | None = None
    library: str | None = None
    category: str | None = None
    subcategory: str | None = None
    confidence: float = 0
    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def _category_path(category: str, subcategory: str | None) -> str:
    return posixpath.join(category, subcategory) if subcategory else category


def _validate_relative_path(value: str) -> None:
    if (
        not value
        or value.startswith(("/", "\\"))
        or "\\" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ClassificationError(
            ClassificationErrorCode.UNSAFE_PATH,
            "classification path must contain safe relative components",
        )
