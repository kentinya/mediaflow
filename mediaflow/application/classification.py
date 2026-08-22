from __future__ import annotations

import unicodedata

from mediaflow.domain.classification import (
    ClassificationContext,
    ClassificationError,
    ClassificationErrorCode,
    ClassificationPolicy,
    ClassificationResult,
    ClassificationRule,
    ClassificationStatus,
)


class ClassificationPolicyRegistry:
    def __init__(self, policies: tuple[ClassificationPolicy, ...]) -> None:
        self._policies: dict[str, ClassificationPolicy] = {}
        for policy in policies:
            if policy.policy_id in self._policies:
                raise ClassificationError(
                    ClassificationErrorCode.INVALID_POLICY,
                    f"duplicate ClassificationPolicy ID {policy.policy_id!r}",
                )
            self._policies[policy.policy_id] = policy

    def resolve(self, policy_id: str) -> ClassificationPolicy:
        try:
            policy = self._policies[policy_id]
        except KeyError as error:
            raise ClassificationError(
                ClassificationErrorCode.POLICY_NOT_FOUND,
                f"ClassificationPolicy {policy_id!r} is not configured",
            ) from error
        if not policy.enabled:
            raise ClassificationError(
                ClassificationErrorCode.POLICY_DISABLED,
                f"ClassificationPolicy {policy_id!r} is disabled",
            )
        return policy

    def references(self) -> dict[str, ClassificationPolicy]:
        return dict(self._policies)


class ClassificationEngine:
    """Pure deterministic classification; it has no Storage or Organizer dependency."""

    def classify(
        self, context: ClassificationContext, policy: ClassificationPolicy
    ) -> ClassificationResult:
        if not policy.enabled:
            raise ClassificationError(
                ClassificationErrorCode.POLICY_DISABLED,
                f"ClassificationPolicy {policy.policy_id!r} is disabled",
            )
        matches = []
        for rule in policy.rules:
            if not rule.enabled:
                continue
            matched, evidence = _matches(rule, context)
            if matched:
                matches.append((rule, evidence))
        if not matches:
            return ClassificationResult(
                policy_id=policy.policy_id,
                recognition_type_id=context.recognition_type_id,
                status=ClassificationStatus.UNCLASSIFIED,
                warnings=("no classification rule matched",),
            )
        rule, evidence = sorted(matches, key=lambda item: (-item[0].priority, item[0].rule_id))[0]
        return ClassificationResult(
            rule.media_library_id,
            rule.relative_category_path or "",
            policy.policy_id,
            context.recognition_type_id,
            ClassificationStatus.CLASSIFIED,
            rule.rule_id,
            rule.name,
            rule.library,
            rule.category,
            rule.subcategory,
            rule.confidence,
            evidence,
        )


class ClassificationPreviewService:
    def __init__(
        self,
        registry: ClassificationPolicyRegistry,
        engine: ClassificationEngine | None = None,
    ) -> None:
        self._registry = registry
        self._engine = engine or ClassificationEngine()

    def preview(self, context: ClassificationContext, policy_id: str) -> ClassificationResult:
        return self._engine.classify(context, self._registry.resolve(policy_id))

    def select_configured_rule(
        self, context: ClassificationContext, policy_id: str, rule_id: str
    ) -> ClassificationResult:
        policy = self._registry.resolve(policy_id)
        rule = next(
            (value for value in policy.rules if value.enabled and value.rule_id == rule_id), None
        )
        if rule is None:
            raise ClassificationError(
                ClassificationErrorCode.INVALID_RULE,
                f"configured ClassificationRule {rule_id!r} is unavailable",
            )
        return ClassificationResult(
            rule.media_library_id,
            rule.relative_category_path or "",
            policy.policy_id,
            context.recognition_type_id,
            ClassificationStatus.CLASSIFIED,
            rule.rule_id,
            rule.name,
            rule.library,
            rule.category,
            rule.subcategory,
            rule.confidence,
            (f"manual configured rule={rule.rule_id}",),
        )


def _matches(
    rule: ClassificationRule, context: ClassificationContext
) -> tuple[bool, tuple[str, ...]]:
    identity = context.media_identity
    evidence = []
    if rule.media_types:
        if identity.media_type not in rule.media_types:
            return False, ()
        evidence.append(f"media_type={identity.media_type.value}")
    for name, expected, actual in (
        ("genre", rule.genres, identity.genres),
        ("country", rule.countries, identity.countries),
        ("language", rule.languages, identity.languages),
    ):
        if expected:
            match = _intersection(expected, actual)
            if match is None:
                return False, ()
            evidence.append(f"{name}={match}")
    if rule.year_min is not None:
        if identity.year is None or identity.year < rule.year_min:
            return False, ()
        evidence.append(f"year>={rule.year_min}")
    if rule.year_max is not None:
        if identity.year is None or identity.year > rule.year_max:
            return False, ()
        evidence.append(f"year<={rule.year_max}")
    if rule.keywords:
        matched_keyword = _keyword(rule.keywords, context)
        if matched_keyword is None:
            return False, ()
        evidence.append(f"keyword={matched_keyword}")
    return True, tuple(evidence)


def _intersection(expected: tuple[str, ...], actual: tuple[str, ...]) -> str | None:
    normalized = {_normalize(value): value for value in actual}
    for value in expected:
        if _normalize(value) in normalized:
            return normalized[_normalize(value)]
    return None


def _keyword(expected: tuple[str, ...], context: ClassificationContext) -> str | None:
    identity = context.media_identity
    values = (
        identity.title,
        identity.original_title or "",
        *identity.alternative_titles,
        *identity.translated_titles,
        identity.overview or "",
        *identity.keywords,
        context.parse_result.title_candidate,
        *context.parse_result.alternative_title_candidates,
    )
    haystack = " ".join(_normalize(value) for value in values)
    for keyword in expected:
        if _normalize(keyword) in haystack:
            return keyword
    return None


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()
