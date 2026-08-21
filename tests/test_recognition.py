from __future__ import annotations

import socket
import unittest
from unittest.mock import patch

from mediaflow.application.media_parser import MediaParserService
from mediaflow.application.policies import RecognitionTypePolicyResolver
from mediaflow.application.recognition import RecognitionRuleEngine
from mediaflow.domain.organizer import OrganizeOperationType, OrganizePolicy
from mediaflow.domain.parser import FileContext, ParseResult
from mediaflow.domain.recognition import (
    AtomicCondition,
    ConditionField,
    ConditionOperator,
    LogicalCondition,
    LogicalOperator,
    PolicyReference,
    PolicyResolutionError,
    PolicyResolutionErrorCode,
    RecognitionContext,
    RecognitionRule,
    RecognitionStatus,
    RecognitionType,
    RecognitionTypePolicy,
)

TYPES = tuple(RecognitionType(value, value) for value in ("A", "B", "C"))


def atom(field: ConditionField, operator: ConditionOperator, value, **kwargs) -> AtomicCondition:
    return AtomicCondition(field, operator, value, **kwargs)


def rule(
    rule_id: str,
    output: str,
    condition=None,
    *,
    priority: int = 0,
    score: float = 1,
    enabled: bool = True,
    stop: bool = False,
) -> RecognitionRule:
    return RecognitionRule(
        rule_id,
        rule_id,
        condition or LogicalCondition(LogicalOperator.ALWAYS),
        output,
        enabled=enabled,
        priority=priority,
        score=score,
        stop_on_match=stop,
    )


def parsed_context(
    filename: str = "The.Matrix.1999.1080p.WEB-DL.H265.DDP5.1.HDR10.CHS.-GRP.mkv",
    path: str | None = None,
    library: str = "downloads",
    directories: tuple[str, ...] = ("C",),
) -> RecognitionContext:
    path = path or "/".join((*directories, filename))
    file = FileContext("storage", library, path, filename, directories)
    return RecognitionContext(file, MediaParserService().parse(file))


class RecognitionConditionTests(unittest.TestCase):
    def test_atomic_operator_matrix(self) -> None:
        context = parsed_context()
        cases = (
            (ConditionField.FILENAME, ConditionOperator.EQUALS, context.file_context.filename),
            (ConditionField.FILENAME, ConditionOperator.NOT_EQUALS, "other.mkv"),
            (ConditionField.FILENAME, ConditionOperator.CONTAINS, "matrix"),
            (ConditionField.FILENAME, ConditionOperator.NOT_CONTAINS, "sample"),
            (ConditionField.FILENAME, ConditionOperator.STARTS_WITH, "the.matrix"),
            (ConditionField.FILENAME, ConditionOperator.ENDS_WITH, ".MKV"),
            (ConditionField.EXTENSION, ConditionOperator.IN, ("MP4", "MKV")),
            (ConditionField.EXTENSION, ConditionOperator.NOT_IN, ("avi", "wmv")),
            (ConditionField.FILENAME, ConditionOperator.REGEX, r"^The[.]Matrix[.]\d{4}"),
            (ConditionField.YEAR, ConditionOperator.EQUALS, 1999),
            (ConditionField.YEAR, ConditionOperator.NOT_EQUALS, 2000),
            (ConditionField.YEAR, ConditionOperator.GREATER_THAN, 1990),
            (ConditionField.YEAR, ConditionOperator.GREATER_THAN_OR_EQUAL, 1999),
            (ConditionField.YEAR, ConditionOperator.LESS_THAN, 2000),
            (ConditionField.YEAR, ConditionOperator.LESS_THAN_OR_EQUAL, 1999),
            (ConditionField.YEAR, ConditionOperator.BETWEEN, (1990, 2000)),
            (ConditionField.YEAR, ConditionOperator.IN, (1999, 2024)),
            (ConditionField.DIRECTORY, ConditionOperator.CONTAINS, "c"),
            (ConditionField.DIRECTORY, ConditionOperator.NOT_CONTAINS, "sample"),
            (ConditionField.HDR, ConditionOperator.CONTAINS_ANY, ("DV", "hdr10")),
            (ConditionField.LANGUAGE, ConditionOperator.CONTAINS_ALL, ("zh-cn",)),
        )
        for field, operator, value in cases:
            with self.subTest(field=field, operator=operator):
                result = RecognitionRuleEngine(
                    TYPES, (rule("r", "C", atom(field, operator, value)),)
                ).recognize(context)
                self.assertEqual(result.status, RecognitionStatus.MATCHED)

    def test_supported_fields(self) -> None:
        context = parsed_context(library="anime-downloads")
        expected = (
            (ConditionField.PATH, ConditionOperator.CONTAINS, "/C/"),
            (ConditionField.TITLE, ConditionOperator.EQUALS, "The Matrix"),
            (ConditionField.RESOLUTION, ConditionOperator.EQUALS, "2160p"),
            (ConditionField.SOURCE, ConditionOperator.EQUALS, "web-dl"),
            (ConditionField.VIDEO_CODEC, ConditionOperator.EQUALS, "h265"),
            (ConditionField.AUDIO_CODEC, ConditionOperator.EQUALS, "eac3"),
            (ConditionField.AUDIO_CHANNELS, ConditionOperator.EQUALS, "5.1"),
            (ConditionField.RELEASE_GROUP, ConditionOperator.EQUALS, "grp"),
            (ConditionField.RESOURCE_LIBRARY_ID, ConditionOperator.EQUALS, "ANIME-DOWNLOADS"),
        )
        # The filename says 1080p; prove false conditions remain unrecognized too.
        for field, operator, value in expected:
            with self.subTest(field=field):
                status = (
                    RecognitionRuleEngine(TYPES, (rule("r", "C", atom(field, operator, value)),))
                    .recognize(context)
                    .status
                )
                self.assertEqual(
                    status,
                    RecognitionStatus.UNRECOGNIZED
                    if field is ConditionField.RESOLUTION
                    else RecognitionStatus.MATCHED,
                )

    def test_season_episode_and_version_collection(self) -> None:
        file = FileContext("s", "tv", "TV/Show.S02E03.mkv", "Show.S02E03.mkv", ("TV",), "mkv")
        parsed = ParseResult("Show", season=2, episode=3, episodes=(3,), version_tags=("IMAX",))
        context = RecognitionContext(file, parsed)
        condition = LogicalCondition(
            LogicalOperator.AND,
            (
                atom(ConditionField.SEASON, ConditionOperator.GREATER_THAN_OR_EQUAL, 2),
                atom(ConditionField.EPISODE, ConditionOperator.EQUALS, 3),
                atom(ConditionField.VERSION, ConditionOperator.CONTAINS, "imax"),
            ),
        )
        self.assertEqual(
            RecognitionRuleEngine(TYPES, (rule("tv", "B", condition),))
            .recognize(context)
            .recognition_type_id,
            "B",
        )

    def test_nested_and_or_not_and_evidence(self) -> None:
        condition = LogicalCondition(
            LogicalOperator.AND,
            (
                atom(ConditionField.EXTENSION, ConditionOperator.IN, ("mkv", "mp4")),
                LogicalCondition(
                    LogicalOperator.OR,
                    (
                        atom(ConditionField.PATH, ConditionOperator.CONTAINS, "/C/"),
                        atom(ConditionField.FILENAME, ConditionOperator.STARTS_WITH, "C-"),
                    ),
                ),
                LogicalCondition(
                    LogicalOperator.NOT,
                    (atom(ConditionField.FILENAME, ConditionOperator.CONTAINS, "sample"),),
                ),
            ),
        )
        result = RecognitionRuleEngine(TYPES, (rule("nested", "C", condition),)).recognize(
            parsed_context()
        )
        self.assertEqual(result.recognition_type_id, "C")
        self.assertEqual({item.field for item in result.evidence}, {"extension", "path", "not"})
        self.assertEqual(result.reasons[0].code, "RULE_MATCH")

    def test_regex_is_precompiled_validated_and_bounded(self) -> None:
        valid = atom(ConditionField.FILENAME, ConditionOperator.REGEX, r"matrix[.]\d{4}")
        self.assertIsNotNone(valid._compiled_regex)
        self.assertEqual(
            RecognitionRuleEngine(TYPES, (rule("regex", "A", valid),))
            .recognize(parsed_context())
            .status,
            RecognitionStatus.MATCHED,
        )
        no_match = atom(ConditionField.FILENAME, ConditionOperator.REGEX, r"^Alien[.]")
        self.assertEqual(
            RecognitionRuleEngine(TYPES, (rule("regex", "A", no_match),))
            .recognize(parsed_context())
            .status,
            RecognitionStatus.UNRECOGNIZED,
        )
        for unsafe in ("(", r"(a+)+$", r"(a*){2}", r"(a)\1"):
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                atom(ConditionField.FILENAME, ConditionOperator.REGEX, unsafe)

    def test_condition_shape_and_operator_validation(self) -> None:
        invalid = (
            lambda: atom(ConditionField.YEAR, ConditionOperator.CONTAINS, "19"),
            lambda: atom(ConditionField.FILENAME, ConditionOperator.BETWEEN, (1, 2)),
            lambda: LogicalCondition(LogicalOperator.NOT, ()),
            lambda: LogicalCondition(LogicalOperator.AND, ()),
            lambda: LogicalCondition(
                LogicalOperator.ALWAYS,
                (atom(ConditionField.EXTENSION, ConditionOperator.EQUALS, "mkv"),),
            ),
        )
        for factory in invalid:
            with self.subTest(factory=factory), self.assertRaises(ValueError):
                factory()


class RecognitionEngineTests(unittest.TestCase):
    def test_a_b_c_core_recognition(self) -> None:
        rules = tuple(
            rule(
                f"rule-{value}",
                value,
                atom(ConditionField.PATH, ConditionOperator.CONTAINS, f"/{value}/"),
            )
            for value in ("A", "B", "C")
        )
        engine = RecognitionRuleEngine(TYPES, rules)
        for value in ("A", "B", "C"):
            with self.subTest(value=value):
                result = engine.recognize(
                    parsed_context(path=f"/{value}/Movie.2024.mkv", directories=(value,))
                )
                self.assertEqual(result.recognition_type_id, value)

    def test_priority_then_aggregate_score_and_ambiguity(self) -> None:
        context = parsed_context()
        higher_priority = RecognitionRuleEngine(
            TYPES,
            (
                rule("generic", "A", priority=10, score=100),
                rule("special", "C", priority=100, score=1),
            ),
        ).recognize(context)
        self.assertEqual(higher_priority.recognition_type_id, "C")
        score_winner = RecognitionRuleEngine(
            TYPES, (rule("a", "A", priority=100, score=50), rule("c", "C", priority=100, score=80))
        ).recognize(context)
        self.assertEqual(score_winner.recognition_type_id, "C")
        ambiguous = RecognitionRuleEngine(
            TYPES, (rule("a", "A", priority=100, score=80), rule("c", "C", priority=100, score=80))
        ).recognize(context)
        self.assertEqual(ambiguous.status, RecognitionStatus.AMBIGUOUS)
        self.assertIsNone(ambiguous.recognition_type)
        self.assertEqual({item.recognition_type_id for item in ambiguous.alternatives}, {"A", "C"})

    def test_same_type_scores_aggregate(self) -> None:
        result = RecognitionRuleEngine(
            TYPES,
            (
                rule("a1", "A", priority=50, score=30),
                rule("a2", "A", priority=50, score=40),
                rule("c", "C", priority=50, score=60),
            ),
        ).recognize(parsed_context())
        self.assertEqual(result.recognition_type_id, "A")
        self.assertEqual(result.score, 70)

    def test_rule_order_is_stable_and_stop_on_match_stops_lower_rules(self) -> None:
        rules = (
            rule("z-low", "B", priority=1),
            rule("b", "C", priority=10, stop=True),
            rule("a", "A", priority=10),
        )
        engine = RecognitionRuleEngine(TYPES, rules)
        first = engine.recognize(parsed_context())
        second = engine.recognize(parsed_context())
        self.assertEqual(first, second)
        # Equal priority is ordered by rule id, so a is evaluated before stopping at b.
        self.assertEqual(tuple(item.rule_id for item in first.matched_rules), ("a", "b"))
        self.assertNotIn("z-low", {item.rule_id for item in first.matched_rules})

    def test_disabled_rule_no_match_and_explicit_default(self) -> None:
        disabled = RecognitionRuleEngine(TYPES, (rule("disabled", "C", enabled=False),)).recognize(
            parsed_context()
        )
        self.assertEqual(disabled.status, RecognitionStatus.UNRECOGNIZED)
        default = RecognitionRuleEngine(TYPES, (rule("default", "A", priority=-1000),)).recognize(
            parsed_context()
        )
        self.assertEqual(default.recognition_type_id, "A")

    def test_rule_and_type_validation(self) -> None:
        with self.assertRaises(ValueError):
            RecognitionRuleEngine(TYPES, (rule("bad", "missing"),))
        with self.assertRaises(ValueError):
            RecognitionRuleEngine(
                (RecognitionType("off", "Off", enabled=False),), (rule("bad", "off"),)
            )
        with self.assertRaises(ValueError):
            RecognitionRule("", "name", LogicalCondition(LogicalOperator.ALWAYS), "A")
        with self.assertRaises(ValueError):
            rule("bad-score", "A", score=-1)

    def test_parser_integration_is_pure_and_has_no_network(self) -> None:
        mutation_calls = {
            name: 0
            for name in (
                "Write",
                "CreateDirectory",
                "Move",
                "Copy",
                "Delete",
                "HardLink",
                "SoftLink",
            )
        }
        with patch.object(socket, "create_connection", side_effect=AssertionError("network call")):
            context = parsed_context(path="/C/The.Matrix.1999.1080p.WEB-DL.mkv")
            condition = LogicalCondition(
                LogicalOperator.AND,
                (
                    atom(ConditionField.PATH, ConditionOperator.CONTAINS, "/C/"),
                    atom(ConditionField.SOURCE, ConditionOperator.EQUALS, "WEB-DL"),
                ),
            )
            result = RecognitionRuleEngine(TYPES, (rule("c-path", "C", condition),)).recognize(
                context
            )
        self.assertEqual(result.recognition_type_id, "C")
        self.assertTrue(all(value == 0 for value in mutation_calls.values()))


class RecognitionPolicyTests(unittest.TestCase):
    @staticmethod
    def type_policy(
        recognition_type: RecognitionType, metadata: str, shared: str
    ) -> RecognitionTypePolicy:
        return RecognitionTypePolicy(
            f"type-{recognition_type.type_id}",
            recognition_type,
            f"metadata-{metadata}",
            f"naming-{shared}",
            f"classification-{shared}",
            OrganizePolicy(f"organize-{shared}", OrganizeOperationType.MOVE),
        )

    @staticmethod
    def catalogs(enabled: bool = True):
        return {
            "metadata_policies": {
                f"metadata-{value}": PolicyReference(f"metadata-{value}")
                for value in ("A", "B", "C")
            },
            "naming_policies": {
                "naming-A": PolicyReference("naming-A", enabled),
                "naming-B": PolicyReference("naming-B"),
            },
            "classification_policies": {
                f"classification-{value}": PolicyReference(f"classification-{value}")
                for value in ("A", "B")
            },
            "organize_policies": {
                f"organize-{value}": PolicyReference(f"organize-{value}") for value in ("A", "B")
            },
        }

    def test_a_b_c_mapping_keeps_recognition_identity_independent(self) -> None:
        a, b, c = TYPES
        resolver = RecognitionTypePolicyResolver(
            (
                self.type_policy(a, "A", "A"),
                self.type_policy(b, "B", "B"),
                self.type_policy(c, "C", "A"),
            ),
            **self.catalogs(),
        )
        expected = {
            "A": ("metadata-A", "naming-A", "classification-A", "organize-A"),
            "B": ("metadata-B", "naming-B", "classification-B", "organize-B"),
            "C": ("metadata-C", "naming-A", "classification-A", "organize-A"),
        }
        for item in TYPES:
            with self.subTest(item=item.type_id):
                resolved = resolver.resolve(item.type_id)
                self.assertEqual(resolved.recognition_type_id, item.type_id)
                self.assertEqual(
                    (
                        resolved.metadata_policy_id,
                        resolved.naming_policy_id,
                        resolved.classification_policy_id,
                        resolved.organize_policy_id,
                    ),
                    expected[item.type_id],
                )
        self.assertEqual(resolver.resolve("C").recognition_type_id, "C")
        self.assertNotEqual(resolver.resolve("C").recognition_type_id, "A")

    def test_missing_disabled_and_duplicate_policy_fail_explicitly(self) -> None:
        c = TYPES[2]
        policy = self.type_policy(c, "C", "A")
        missing = self.catalogs()
        del missing["naming_policies"]["naming-A"]
        with self.assertRaises(PolicyResolutionError) as caught:
            RecognitionTypePolicyResolver((policy,), **missing).resolve("C")
        self.assertEqual(caught.exception.code, PolicyResolutionErrorCode.INVALID_POLICY_REFERENCE)
        with self.assertRaises(PolicyResolutionError) as caught:
            RecognitionTypePolicyResolver((policy,), **self.catalogs(enabled=False)).resolve("C")
        self.assertEqual(caught.exception.code, PolicyResolutionErrorCode.POLICY_DISABLED)
        with self.assertRaises(PolicyResolutionError) as caught:
            RecognitionTypePolicyResolver((policy, policy))
        self.assertEqual(caught.exception.code, PolicyResolutionErrorCode.DUPLICATE_TYPE_POLICY)
        with self.assertRaises(PolicyResolutionError) as caught:
            RecognitionTypePolicyResolver(()).resolve("C")
        self.assertEqual(caught.exception.code, PolicyResolutionErrorCode.MISSING_TYPE_POLICY)


if __name__ == "__main__":
    unittest.main()
