from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from mediaflow.domain.recognition import (
    COLLECTION_FIELDS,
    NUMERIC_FIELDS,
    AtomicCondition,
    ConditionField,
    ConditionOperator,
    LogicalCondition,
    LogicalOperator,
    MatchedRule,
    RecognitionAlternative,
    RecognitionContext,
    RecognitionEvidence,
    RecognitionReason,
    RecognitionResult,
    RecognitionRule,
    RecognitionStatus,
    RecognitionType,
)


@dataclass(frozen=True)
class _ConditionMatch:
    matched: bool
    evidence: tuple[RecognitionEvidence, ...] = ()


class RecognitionRuleEngine:
    def __init__(
        self,
        recognition_types: tuple[RecognitionType, ...],
        rules: tuple[RecognitionRule, ...],
    ) -> None:
        self._types = {item.type_id: item for item in recognition_types}
        if len(self._types) != len(recognition_types):
            raise ValueError("recognition type ids must be unique")
        if len({rule.rule_id for rule in rules}) != len(rules):
            raise ValueError("recognition rule ids must be unique")
        for rule in rules:
            output = self._types.get(rule.output_recognition_type_id)
            if output is None:
                raise ValueError(f"rule {rule.rule_id!r} references a missing recognition type")
            if not output.enabled:
                raise ValueError(f"rule {rule.rule_id!r} references a disabled recognition type")
        self._rules = tuple(sorted(rules, key=lambda rule: (-rule.priority, rule.rule_id)))

    def recognize(self, context: RecognitionContext) -> RecognitionResult:
        matches: list[tuple[RecognitionRule, tuple[RecognitionEvidence, ...]]] = []
        for rule in self._rules:
            if not rule.enabled:
                continue
            condition = self._evaluate(rule.condition, context, rule.rule_id)
            if condition.matched:
                matches.append((rule, condition.evidence))
                if rule.stop_on_match:
                    break
        if not matches:
            return RecognitionResult(
                recognition_type=None,
                confidence=0.0,
                status=RecognitionStatus.UNRECOGNIZED,
                reasons=(
                    RecognitionReason("NO_RULE_MATCH", "No enabled recognition rule matched"),
                ),
            )

        grouped = defaultdict(list)
        for rule, evidence in matches:
            grouped[rule.output_recognition_type_id].append((rule, evidence))
        ranked = [
            (
                max(rule.priority for rule, _ in type_matches),
                sum(rule.score for rule, _ in type_matches),
                type_id,
            )
            for type_id, type_matches in grouped.items()
        ]
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
        winning_priority, winning_score, winning_type_id = ranked[0]
        tied = [item for item in ranked if item[:2] == (winning_priority, winning_score)]
        all_matched = tuple(
            MatchedRule(rule.rule_id, rule.output_recognition_type_id, rule.priority, rule.score)
            for rule, _ in matches
        )
        alternatives = tuple(
            RecognitionAlternative(type_id, score, priority) for priority, score, type_id in ranked
        )
        evidence = tuple(item for _, items in matches for item in items)
        if len(tied) > 1:
            return RecognitionResult(
                recognition_type=None,
                confidence=0.0,
                status=RecognitionStatus.AMBIGUOUS,
                matched_rules=all_matched,
                score=winning_score,
                evidence=evidence,
                reasons=(
                    RecognitionReason(
                        "AMBIGUOUS_MATCH",
                        "Multiple recognition types have equal priority and score",
                    ),
                ),
                warnings=("manual recognition is required",),
                alternatives=alternatives,
            )
        first_rule = grouped[winning_type_id][0][0]
        return RecognitionResult(
            recognition_type=self._types[winning_type_id],
            rule_id=first_rule.rule_id,
            confidence=min(1.0, winning_score / 100.0) if winning_score else 0.0,
            status=RecognitionStatus.MATCHED,
            matched_rules=all_matched,
            score=winning_score,
            evidence=evidence,
            reasons=(
                RecognitionReason("RULE_MATCH", f"Matched recognition type {winning_type_id}"),
            ),
            alternatives=alternatives,
        )

    def _evaluate(self, condition, context: RecognitionContext, rule_id: str) -> _ConditionMatch:
        if isinstance(condition, AtomicCondition):
            actual = _field_value(condition.field, context)
            matched = _compare(condition, actual)
            evidence = ()
            if matched:
                evidence = (
                    RecognitionEvidence(
                        rule_id,
                        condition.field.value,
                        condition.operator.value,
                        repr(condition.value),
                        repr(actual),
                    ),
                )
            return _ConditionMatch(matched, evidence)
        if not isinstance(condition, LogicalCondition):
            raise TypeError("unsupported recognition condition")
        if condition.operator is LogicalOperator.ALWAYS:
            return _ConditionMatch(True)
        children = tuple(self._evaluate(child, context, rule_id) for child in condition.children)
        if condition.operator is LogicalOperator.AND:
            matched = all(child.matched for child in children)
            return _ConditionMatch(matched, _evidence(children) if matched else ())
        if condition.operator is LogicalOperator.OR:
            matched = any(child.matched for child in children)
            return _ConditionMatch(matched, _evidence(child for child in children if child.matched))
        matched = not children[0].matched
        evidence = (
            (
                RecognitionEvidence(
                    rule_id,
                    "not",
                    "not",
                    "condition must not match",
                    "condition did not match",
                ),
            )
            if matched
            else ()
        )
        return _ConditionMatch(matched, evidence)


def _evidence(matches) -> tuple[RecognitionEvidence, ...]:
    return tuple(item for match in matches for item in match.evidence)


def _field_value(field: ConditionField, context: RecognitionContext) -> Any:
    file, parsed = context.file_context, context.parse_result
    values = {
        ConditionField.FILENAME: file.filename,
        ConditionField.PATH: "/" + file.path.replace("\\", "/").lstrip("/"),
        ConditionField.DIRECTORY: file.parent_directories,
        ConditionField.EXTENSION: parsed.extension or file.extension,
        ConditionField.TITLE: parsed.title_candidate,
        ConditionField.YEAR: parsed.year,
        ConditionField.SEASON: parsed.season,
        ConditionField.EPISODE: parsed.episode,
        ConditionField.RESOLUTION: parsed.resolution_tag,
        ConditionField.SOURCE: parsed.source_tag,
        ConditionField.VIDEO_CODEC: parsed.video_codec_tag,
        ConditionField.AUDIO_CODEC: parsed.audio_codec_tag,
        ConditionField.AUDIO_CHANNELS: parsed.audio_channels_tag,
        ConditionField.HDR: parsed.hdr_tags,
        ConditionField.VERSION: parsed.version_tags,
        ConditionField.RELEASE_GROUP: parsed.release_group,
        ConditionField.LANGUAGE: parsed.language_tags,
        ConditionField.RESOURCE_LIBRARY_ID: file.resource_library_id,
    }
    return values[field]


def _compare(condition: AtomicCondition, actual: Any) -> bool:
    operator, expected = condition.operator, condition.value
    if actual is None:
        return operator is ConditionOperator.NOT_EQUALS and expected is not None
    if condition.field in NUMERIC_FIELDS:
        if operator is ConditionOperator.EQUALS:
            return actual == expected
        if operator is ConditionOperator.NOT_EQUALS:
            return actual != expected
        if operator is ConditionOperator.GREATER_THAN:
            return actual > expected
        if operator is ConditionOperator.GREATER_THAN_OR_EQUAL:
            return actual >= expected
        if operator is ConditionOperator.LESS_THAN:
            return actual < expected
        if operator is ConditionOperator.LESS_THAN_OR_EQUAL:
            return actual <= expected
        if operator is ConditionOperator.BETWEEN:
            return expected[0] <= actual <= expected[1]
        return actual in expected
    if condition.field in COLLECTION_FIELDS:
        haystack = tuple(_normalize(item, condition.case_sensitive) for item in actual)
        if operator in {ConditionOperator.CONTAINS, ConditionOperator.NOT_CONTAINS}:
            result = _normalize(expected, condition.case_sensitive) in haystack
            return result if operator is ConditionOperator.CONTAINS else not result
        needles = {_normalize(item, condition.case_sensitive) for item in expected}
        if operator is ConditionOperator.CONTAINS_ANY:
            return bool(needles.intersection(haystack))
        return needles.issubset(haystack)
    left = _normalize(actual, condition.case_sensitive)
    if operator is ConditionOperator.REGEX:
        assert condition._compiled_regex is not None
        return bool(condition._compiled_regex.search(str(actual)[:4096]))
    if operator in {ConditionOperator.IN, ConditionOperator.NOT_IN}:
        result = left in {_normalize(item, condition.case_sensitive) for item in expected}
        return result if operator is ConditionOperator.IN else not result
    right = _normalize(expected, condition.case_sensitive)
    if operator is ConditionOperator.EQUALS:
        return left == right
    if operator is ConditionOperator.NOT_EQUALS:
        return left != right
    if operator is ConditionOperator.CONTAINS:
        return right in left
    if operator is ConditionOperator.NOT_CONTAINS:
        return right not in left
    if operator is ConditionOperator.STARTS_WITH:
        return left.startswith(right)
    return left.endswith(right)


def _normalize(value: Any, case_sensitive: bool) -> str:
    text = str(value)
    return text if case_sensitive else text.casefold()
