"""Object-scoped rules testing and the separate complete-flow check (Slice 44 RO-4).

This module owns the one shared application boundary RO-4 promises: an operator
explicitly tests the *exact unsaved object* in an Add/copy/Edit form using only
that object's necessary inputs, and separately runs complete-flow analysis from
Rules Overview.

Two deliberately different authorities live here:

* :meth:`RulesObjectAnalysisService.analyze` explains exactly one submitted
  object of one family from one exact captured configuration context.  It reuses
  the production Parser, condition engine, Naming and Classification semantics and
  never loads a whole managed runtime, resolves an unrelated family or touches a
  Provider or media Storage.  A valid local result is *not* publication,
  runtime-eligibility or execution authority.
* :meth:`RulesObjectAnalysisService.complete_flow` is the separately labelled
  complete-flow entry.  It reuses the existing complete Python chain (recognition
  competition, policy resolution, Metadata, Naming, Classification, OrganizePlan)
  and reports truthful missing-stage blockers.  Its offline identity is explicitly
  synthetic and performs no Provider call; live Metadata stays separately explicit.

Neither path admits executable work, changes Active, mutates Storage or replays a
previous request.  Every result is bound to the submitted purpose/object/candidate/
sample/context so a later relevant edit or Active change makes it visibly stale.
"""

from __future__ import annotations

import copy
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from mediaflow.application.classification import (
    ClassificationPolicyRegistry,
    ClassificationPreviewService,
)
from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.media_parser import MediaParserService
from mediaflow.application.metadata import (
    CandidateMatcher,
    MetadataIdentificationService,
    MetadataPolicyRegistry,
)
from mediaflow.application.naming import NamingPolicyRegistry, NamingPreviewService
from mediaflow.application.recognition import RecognitionRuleEngine
from mediaflow.application.rules_workspace_commands import (
    RULE_FAMILIES,
    RulesWorkspaceCommandService,
    rules_family_section,
)
from mediaflow.application.strategy_test import (
    StrategyConfigurationError,
    StrategyTestResult,
    file_context_from_path,
    strategy_runner_from_configuration,
)
from mediaflow.domain.classification import (
    ClassificationError,
    ClassificationStatus,
)
from mediaflow.domain.configuration_management import (
    ManagedConfigurationRevision,
    RulesWorkspaceSaveError,
)
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.metadata import (
    MediaIdentity,
    MediaQueryType,
    MediaType,
    MetadataIdentificationStatus,
    MetadataPolicy,
)
from mediaflow.domain.naming import NamingError
from mediaflow.domain.organizer import OrganizePolicy
from mediaflow.domain.parser import FileContext, ParseResult
from mediaflow.domain.recognition import (
    PolicyResolutionError,
    RecognitionContext,
    RecognitionResult,
    RecognitionRule,
    RecognitionStatus,
    RecognitionType,
)
from mediaflow.infrastructure.metadata_provider_bootstrap import (
    MetadataProviderBootstrapError,
    metadata_provider_secret_env_fields,
)
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.strategy_user_configuration import parse_recognition_condition

MAX_ANALYSIS_TEXT = 240
MAX_ANALYSIS_ITEMS = 32
MAX_ASSOCIATED_RULES = 64

# The documented local conclusions.  "not_applicable" is a normal outcome, not a
# technical failure, and runtime eligibility is deliberately a separate fact.
ANALYSIS_OUTCOMES = (
    "valid",
    "matched",
    "not_matched",
    "not_applicable",
    "invalid_input",
    "failed",
)

SAMPLE_FIELDS = frozenset(
    {
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
        "genres",
        "countries",
        "languages",
        "keywords",
        "overview",
    }
)

RULE_SAMPLE_FIELDS = frozenset(
    {
        "path",
        "resourceLibraryId",
        "title",
        "year",
        "season",
        "episode",
        "extension",
        "resolution",
        "source",
        "videoCodec",
        "audio",
        "hdr",
        "version",
        "releaseGroup",
    }
)


@dataclass(frozen=True)
class AnalysisResult:
    """One bounded, secret-free object-analysis result bound to its own inputs."""

    family: str
    object_id: str | None
    outcome: str
    conclusion: str
    result: dict[str, object] = field(default_factory=dict)
    message: str | None = None
    next_action: str | None = None
    failure_category: str | None = None
    applicability: str = "applicable"
    runtime_eligibility: str = "separate"
    readiness: str | None = None
    provider_calls: int = 0
    storage_reads: int = 0
    local_only: bool = True
    identity_status: str | None = None
    synthetic_identity: bool = False
    blockers: tuple[dict[str, object], ...] = ()

    def __post_init__(self) -> None:
        if self.family not in RULE_FAMILIES:
            raise ValueError("analysis family is unsupported")
        if self.outcome not in ANALYSIS_OUTCOMES:
            raise ValueError("analysis outcome is unsupported")

    def document(self) -> dict[str, object]:
        return {
            "family": self.family,
            "objectId": self.object_id,
            "outcome": self.outcome,
            "conclusion": self.conclusion,
            "applicability": self.applicability,
            "runtimeEligibility": self.runtime_eligibility,
            "readiness": self.readiness,
            "result": copy.deepcopy(self.result),
            "message": self.message,
            "nextAction": self.next_action,
            "failureCategory": self.failure_category,
            "sideEffects": "none",
            "retrySafe": True,
            "providerCalls": self.provider_calls,
            "storageReads": self.storage_reads,
            "candidateState": "validated_non_active",
            "localOnly": self.local_only,
            "identityStatus": self.identity_status,
            "syntheticIdentity": self.synthetic_identity,
            "blockers": copy.deepcopy(list(self.blockers)),
        }


def _bounded(value: object, maximum: int = MAX_ANALYSIS_TEXT) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text[:maximum]


class RulesObjectAnalysisService:
    """Object-scoped analysis over one exact configuration context."""

    def __init__(
        self,
        commands: RulesWorkspaceCommandService,
        objects: ConfigurationObjectService,
    ) -> None:
        self._commands = commands
        self._objects = objects

    # ------------------------------------------------------------------
    # Family-specific local analysis
    # ------------------------------------------------------------------

    def analyze(
        self,
        family: str,
        *,
        revision_id: str,
        object_id: str | None,
        sample: Mapping[str, object] | None = None,
        live_metadata: bool = False,
    ) -> AnalysisResult:
        """Analyse exactly one submitted object of ``family`` from one exact revision.

        The revision is the immutable non-Active candidate staged for this
        analysis, so the submitted unsaved object is the authority and no other
        family's unsaved draft can enter the candidate.  Only the requested
        family's own necessary inputs are required.
        """

        if family not in RULE_FAMILIES:
            raise RulesWorkspaceSaveError(
                "rules_analysis_unsupported",
                f"{family!r} is not a rules-workspace object family",
                status=400,
                object_kind=family,
                stage="analyze",
                durable_state="active_unchanged",
                side_effects="none",
                next_action=f"choose one of {', '.join(RULE_FAMILIES)}",
            )
        revision = self._objects._managed.require(revision_id)
        section = rules_family_section(family)
        stored = self._submitted_object(revision, section, object_id)
        resolved_object_id = str(stored.get("id")) if stored is not None else None
        try:
            if family == "recognitionTypes":
                return self._analyze_recognition_type(revision, stored, resolved_object_id, sample)
            if family == "recognitionRules":
                return self._analyze_recognition_rule(revision, stored, resolved_object_id, sample)
            if family == "typeBindings":
                return self._analyze_type_binding(revision, stored, resolved_object_id)
            if family == "metadataPolicies":
                return self._analyze_metadata_policy(
                    revision,
                    stored,
                    resolved_object_id,
                    sample,
                    live_metadata=live_metadata,
                )
            if family == "namingPolicies":
                return self._analyze_naming_policy(revision, stored, resolved_object_id, sample)
            if family == "classificationPolicies":
                return self._analyze_classification_policy(
                    revision, stored, resolved_object_id, sample
                )
            return self._analyze_organize_policy(revision, stored, resolved_object_id)
        except RulesWorkspaceSaveError:
            raise
        except (NamingError, ClassificationError, ValueError, LookupError) as error:
            return AnalysisResult(
                family,
                resolved_object_id,
                "invalid_input",
                "配置或样本无效",
                result={},
                message=_bounded(error, 384) or "invalid input",
                next_action=f"correct the reported {family} field or sample, then explicitly rerun",
                failure_category="invalid_input",
            )

    @staticmethod
    def _submitted_object(
        revision: ManagedConfigurationRevision, section: str, object_id: str | None
    ) -> dict[str, object] | None:
        values = ConfigurationObjectService._canonical_objects(revision.document, section)
        if object_id is None:
            # A create/copy candidate stages exactly one new object in the section;
            # the highest-ordered new row is the submitted candidate.
            return values[-1] if values else None
        for item in values:
            if str(item.get("id")) == object_id:
                return item
        raise RulesWorkspaceSaveError(
            "rules_object_missing",
            f"{section} object {object_id!r} is not present in the analysed candidate",
            status=404,
            object_kind=section,
            object_id=object_id,
            stage="analyze",
            durable_state="active_unchanged",
            side_effects="none",
            next_action="reopen the object from the current Active inventory and retry",
        )

    # -- RecognitionType -------------------------------------------------

    def _analyze_recognition_type(
        self,
        revision: ManagedConfigurationRevision,
        stored: Mapping[str, object] | None,
        object_id: str | None,
        sample: Mapping[str, object] | None,
    ) -> AnalysisResult:
        if stored is None:
            raise ValueError("RecognitionType candidate is missing")
        enabled = stored.get("enabled", True) is not False
        # A valid definition deliberately requires no binding and no downstream
        # policy: this is a definition check, not a runtime-eligibility check.
        definition = {
            "id": _bounded(stored.get("id"), 64),
            "name": _bounded(stored.get("name"), 120),
            "description": _bounded(stored.get("description"), 500),
            "enabled": enabled,
        }
        associated = [
            item
            for item in self._objects._canonical_objects(revision.document, "recognitionRules")
            if str(item.get("outputRecognitionType")) == object_id
        ]
        if not associated:
            return AnalysisResult(
                "recognitionTypes",
                object_id,
                "valid",
                "类型定义有效;暂无关联规则可供试识别",
                result={"definition": definition, "associatedRules": []},
                applicability="not_applicable",
                message="该识别类型当前没有任何关联的识别规则,因此没有可运行的试识别样本",
                next_action="如需试识别,请先创建输出到该类型的识别规则",
            )
        if sample is None:
            return AnalysisResult(
                "recognitionTypes",
                object_id,
                "valid",
                "类型定义有效;可选关联规则试识别未运行",
                result={
                    "definition": definition,
                    "associatedRules": [
                        self._associated_rule_document(item) for item in associated
                    ],
                },
                applicability="optional",
                message="类型定义本身有效;关联规则试识别是可选步骤",
                next_action="提供样本路径后可显式测试该类型的关联规则",
            )
        return self._run_associated_rules(revision, definition, object_id, associated, sample)

    @staticmethod
    def _associated_rule_document(item: Mapping[str, object]) -> dict[str, object]:
        return {
            "id": _bounded(item.get("id"), 64),
            "name": _bounded(item.get("name"), 120),
            "enabled": item.get("enabled", True) is not False,
            "priority": item.get("priority", 0),
            "score": item.get("score", 1),
        }

    def _run_associated_rules(
        self,
        revision: ManagedConfigurationRevision,
        definition: Mapping[str, object],
        object_id: str | None,
        associated: Sequence[Mapping[str, object]],
        sample: Mapping[str, object],
    ) -> AnalysisResult:
        context = self._rule_context(revision, sample)
        types = self._recognition_types(revision)
        results: list[dict[str, object]] = []
        for item in associated[:MAX_ASSOCIATED_RULES]:
            rule_document = self._associated_rule_document(item)
            rule_document["enabled"] = item.get("enabled", True) is not False
            if item.get("enabled", True) is False:
                rule_document["eligibility"] = "disabled"
                rule_document["matched"] = None
                rule_document["conclusion"] = "该规则已停用,不参与运行时匹配"
                results.append(rule_document)
                continue
            try:
                rule = self._recognition_rule(item)
                engine = RecognitionRuleEngine(tuple(types.values()), (rule,))
                evaluation = engine.evaluate_rule(rule, context)
            except (ValueError, TypeError) as error:
                rule_document["eligibility"] = "invalid"
                rule_document["matched"] = None
                rule_document["conclusion"] = _bounded(error, 384)
                results.append(rule_document)
                continue
            rule_document["eligibility"] = "enabled"
            rule_document["matched"] = evaluation.matched
            rule_document["conclusion"] = (
                "该关联规则在提交样本上匹配"
                if evaluation.matched
                else "该关联规则在提交样本上不匹配"
            )
            rule_document["condition"] = evaluation.condition.document()
            results.append(rule_document)
        matched = [item for item in results if item.get("matched") is True]
        # The type is never forced into a fabricated match: a real associated-rule
        # match outputs the rule's own type, and competition belongs to complete flow.
        return AnalysisResult(
            "recognitionTypes",
            object_id,
            "matched" if matched else "not_matched",
            (
                f"类型定义有效;{len(matched)} 条关联规则在提交样本上匹配"
                if matched
                else "类型定义有效;关联规则在提交样本上均不匹配"
            ),
            result={
                "definition": definition,
                "associatedRules": results,
                "matchedRuleCount": len(matched),
                "competition": "single-type local test; rule competition belongs to 完整流程检查",
            },
            message=(None if matched else "没有任何关联规则匹配该样本;这不改变有效的类型定义"),
            next_action=(
                "如需确认该类型在配置规则集中的胜出结果,请使用概览的完整流程检查"
                if matched
                else "调整样本或关联规则条件,然后显式重新运行;或使用完整流程检查"
            ),
        )

    # -- RecognitionRule ------------------------------------------------

    def _analyze_recognition_rule(
        self,
        revision: ManagedConfigurationRevision,
        stored: Mapping[str, object] | None,
        object_id: str | None,
        sample: Mapping[str, object] | None,
    ) -> AnalysisResult:
        if stored is None:
            raise ValueError("RecognitionRule candidate is missing")
        if sample is None:
            raise ValueError("RecognitionRule test requires a submitted sample path")
        output = str(stored.get("outputRecognitionType") or "")
        if not output:
            raise ValueError("RecognitionRule outputRecognitionType is required")
        types = self._recognition_types(revision)
        if output not in types:
            raise ValueError(f"output RecognitionType {output!r} is not configured")
        if types[output].enabled is False:
            return AnalysisResult(
                "recognitionRules",
                object_id,
                "invalid_input",
                "输出识别类型已停用",
                result={"outputRecognitionType": output, "outputTypeEnabled": False},
                message=f"输出 RecognitionType {output!r} 已停用,该规则无法参与运行时匹配",
                next_action="启用该识别类型或改选一个已启用的输出类型,然后显式重新运行",
                failure_category="output_type_disabled",
            )
        rule = self._recognition_rule(stored)
        context = self._rule_context(revision, sample)
        if stored.get("enabled", True) is False:
            return AnalysisResult(
                "recognitionRules",
                object_id,
                "not_applicable",
                "该规则已停用,不参与运行时匹配",
                result={
                    "ruleId": rule.rule_id,
                    "outputRecognitionType": output,
                    "outputTypeEnabled": True,
                    "enabled": False,
                    "parsed": self._parsed_document(context),
                    "condition": None,
                },
                applicability="not_applicable",
                message="规则本身可以解析,但它当前已停用",
                next_action="启用该规则后显式重新运行,即可查看条件求值结果",
            )
        # Evaluate only this submitted rule: no competition, no policy resolution
        # and no downstream requirement can fail an independent local test.
        engine = RecognitionRuleEngine(tuple(types.values()), (rule,))
        evaluation = engine.evaluate_rule(rule, context)
        return AnalysisResult(
            "recognitionRules",
            object_id,
            "matched" if evaluation.matched else "not_matched",
            (
                f"规则在提交路径上匹配,输出类型 {output}"
                if evaluation.matched
                else "规则在提交路径上不匹配"
            ),
            result={
                "ruleId": rule.rule_id,
                "outputRecognitionType": output,
                "outputTypeEnabled": True,
                "enabled": True,
                "testedPath": self._bounded_path(sample),
                "parsed": self._parsed_document(context),
                "condition": evaluation.condition.document(),
                "evidence": [
                    {
                        "field": item.field,
                        "operator": item.operator,
                        "expected": _bounded(item.expected),
                        "actual": _bounded(item.actual),
                    }
                    for item in evaluation.evidence[:MAX_ANALYSIS_ITEMS]
                ],
                "competition": "single-rule local test; priority/score/stop belong to 完整流程检查",
            },
            message=(
                None
                if evaluation.matched
                else "未满足的条件已在条件证据中标出;这不代表该规则在配置规则集中不会胜出"
            ),
            next_action=(
                "本地单规则结论不代表配置竞争结果;如需完整结论请使用完整流程检查"
                if evaluation.matched
                else "修正条件或样本,然后显式重新运行"
            ),
        )

    def _recognition_rule(self, stored: Mapping[str, object]) -> RecognitionRule:
        condition = parse_recognition_condition(copy.deepcopy(dict(stored.get("condition") or {})))
        return RecognitionRule(
            str(stored.get("id")),
            str(stored.get("name") or stored.get("id")),
            condition,
            str(stored.get("outputRecognitionType")),
            bool(stored.get("enabled", True)),
            int(stored.get("priority", 0)),
            float(stored.get("score", 1)),
            bool(stored.get("stopOnMatch", False)),
            str(stored.get("description", "")),
        )

    def _recognition_types(
        self, revision: ManagedConfigurationRevision
    ) -> dict[str, RecognitionType]:
        return {
            str(item.get("id")): RecognitionType(
                str(item.get("id")),
                str(item.get("name") or item.get("id")),
                str(item.get("description", "")),
                bool(item.get("enabled", True)),
            )
            for item in self._objects._canonical_objects(revision.document, "recognitionTypes")
        }

    def _rule_context(
        self, revision: ManagedConfigurationRevision, sample: Mapping[str, object]
    ) -> RecognitionContext:
        if not isinstance(sample, Mapping):
            raise ValueError("recognition rule sample must be an object")
        if unknown := set(sample).difference(RULE_SAMPLE_FIELDS):
            raise ValueError(
                f"recognition rule sample contains unsupported field {sorted(unknown)[0]!r}"
            )
        path = sample.get("path")
        if not isinstance(path, str) or not path.strip() or len(path) > 4096 or "\x00" in path:
            raise ValueError("recognition rule test requires one bounded non-empty sample path")
        library_id = sample.get("resourceLibraryId")
        if library_id is not None and (
            not isinstance(library_id, str) or not library_id.strip() or len(library_id) > 128
        ):
            raise ValueError("recognition rule sample resourceLibraryId must be bounded text")
        # Use the same path-to-FileContext semantics as production strategy
        # tests. In particular, a bare filename has no parent directories; it
        # must not be reinterpreted as its own containing directory.
        context = file_context_from_path(
            path,
            resource_library_id=library_id or "offline-preview",
            storage_id="offline-preview",
        )
        overrides = {
            key: sample[key]
            for key in (
                "title",
                "year",
                "season",
                "episode",
                "resolution",
                "source",
                "videoCodec",
                "audio",
                "hdr",
                "version",
                "releaseGroup",
            )
            if sample.get(key) is not None
        }
        if overrides:
            # An explicit operator override is applied to the parsed result, so a
            # rule can be tested against a genuine parsed field value without a
            # real file and without silently rebasing the submitted path.
            parsed = MediaParserService().parse(context)
            parsed = ParseResult(
                str(overrides.get("title", parsed.title_candidate)),
                year=overrides.get("year", parsed.year),
                season=overrides.get("season", parsed.season),
                episode=overrides.get("episode", parsed.episode),
                episodes=parsed.episodes,
                resolution_tag=overrides.get("resolution", parsed.resolution_tag),
                source_tag=overrides.get("source", parsed.source_tag),
                video_codec_tag=overrides.get("videoCodec", parsed.video_codec_tag),
                audio_tag=overrides.get("audio", parsed.audio_tag),
                hdr_tag=overrides.get("hdr", parsed.hdr_tag),
                version_tag=overrides.get("version", parsed.version_tag),
                release_group=overrides.get("releaseGroup", parsed.release_group),
                original_filename=parsed.original_filename,
                extension=parsed.extension,
            )
        else:
            parsed = MediaParserService().parse(context)
        return RecognitionContext(context, parsed)

    @staticmethod
    def _bounded_path(sample: Mapping[str, object]) -> str | None:
        path = sample.get("path")
        return _bounded(path, 4096) if isinstance(path, str) else None

    @staticmethod
    def _parsed_document(context: RecognitionContext) -> dict[str, object]:
        parsed = context.parse_result
        return {
            "filename": _bounded(context.file_context.filename, 512),
            "path": _bounded("/" + context.file_context.path.replace("\\", "/").lstrip("/"), 4096),
            "titleCandidate": _bounded(parsed.title_candidate, 512),
            "year": parsed.year,
            "season": parsed.season,
            "episode": parsed.episode,
            "episodes": list(parsed.episodes[:MAX_ANALYSIS_ITEMS]),
            "extension": _bounded(parsed.extension, 32),
            "resolutionTag": _bounded(parsed.resolution_tag, 64),
            "sourceTag": _bounded(parsed.source_tag, 64),
            "videoCodecTag": _bounded(parsed.video_codec_tag, 64),
            "audioTag": _bounded(parsed.audio_tag, 64),
            "hdrTags": [_bounded(item, 64) for item in parsed.hdr_tags[:MAX_ANALYSIS_ITEMS]],
            "versionTags": [
                _bounded(item, 64) for item in parsed.version_tags[:MAX_ANALYSIS_ITEMS]
            ],
            "releaseGroup": _bounded(parsed.release_group, 128),
        }

    # -- Type binding ---------------------------------------------------

    def _analyze_type_binding(
        self,
        revision: ManagedConfigurationRevision,
        stored: Mapping[str, object] | None,
        object_id: str | None,
    ) -> AnalysisResult:
        if stored is None:
            raise ValueError("RecognitionTypePolicy candidate is missing")
        enabled = stored.get("enabled", True) is not False
        type_id = str(stored.get("recognitionType") or "")
        references = {
            "metadataPolicy": ("metadataPolicies", str(stored.get("metadataPolicy") or "")),
            "namingPolicy": ("namingPolicies", str(stored.get("namingPolicy") or "")),
            "classificationPolicy": (
                "classificationPolicies",
                str(stored.get("classificationPolicy") or ""),
            ),
            "organizePolicy": ("organizePolicies", str(stored.get("organizePolicy") or "")),
        }
        types = {
            str(item.get("id")): item
            for item in self._objects._canonical_objects(revision.document, "recognitionTypes")
        }
        document: dict[str, object] = {
            "recognitionType": type_id,
            "recognitionTypeEnabled": (types.get(type_id, {}).get("enabled", True) is not False)
            if type_id in types
            else False,
            "enabled": enabled,
            "resolvedPolicies": {},
            # RecognitionType C stays C: reusing A Naming/Classification policies
            # is a policy reference, never a type identity change.
            "recognitionTypeIdentity": type_id,
            "cIdentityPreserved": type_id != "C",
            "checked": "type, enabled uniqueness and four explicit references only",
        }
        problems: list[str] = []
        if type_id not in types:
            problems.append(f"RecognitionType {type_id!r} 未配置")
        elif types[type_id].get("enabled", True) is False:
            problems.append(f"RecognitionType {type_id!r} 已停用")
        for field_name, (section, reference) in references.items():
            catalog = {
                str(item.get("id")): item
                for item in self._objects._canonical_objects(revision.document, section)
            }
            target = catalog.get(reference)
            # OrganizePolicy has no enable state in the domain, so only its
            # existence is a real reference requirement.
            if target is None:
                problems.append(f"{field_name} {reference!r} 未配置")
            elif section != "organizePolicies" and target.get("enabled", True) is False:
                problems.append(f"{field_name} {reference!r} 已停用")
            document["resolvedPolicies"][field_name] = {
                "id": reference or None,
                "resolved": target is not None,
                "enabled": None if target is None else target.get("enabled", True) is not False,
            }
        duplicates = [
            str(item.get("id"))
            for item in self._objects._canonical_objects(
                revision.document, "recognitionTypePolicies"
            )
            if str(item.get("id")) != object_id
            and item.get("enabled", True) is not False
            and str(item.get("recognitionType")) == type_id
        ]
        document["duplicateEnabledBindings"] = duplicates
        if enabled and duplicates:
            problems.append("同一 RecognitionType 存在多个已启用绑定")
        # RecognitionType C keeps being C: reusing A Naming/Classification policies
        # is a policy reference, never a type identity change.
        document["recognitionTypeIdentity"] = type_id
        if problems:
            return AnalysisResult(
                "typeBindings",
                object_id,
                "invalid_input",
                "绑定引用不完整",
                result=document,
                message="; ".join(problems[:4]),
                next_action="修正报告的引用或唯一性,然后显式重新运行",
                failure_category="reference_unavailable",
            )
        return AnalysisResult(
            "typeBindings",
            object_id,
            "valid",
            "绑定有效:类型、启用唯一性与四项策略引用均可解析",
            result=document,
            message=("该检查不执行任何策略引擎、不识别文件、不查询 Provider,也不探测目标路径"),
            next_action="如需确认下游真实结果,请使用完整流程检查;本结论不是执行授权",
        )

    # -- MetadataPolicy -------------------------------------------------

    def _analyze_metadata_policy(
        self,
        revision: ManagedConfigurationRevision,
        stored: Mapping[str, object] | None,
        object_id: str | None,
        sample: Mapping[str, object] | None,
        *,
        live_metadata: bool,
    ) -> AnalysisResult:
        if stored is None:
            raise ValueError("MetadataPolicy candidate is missing")
        normalized = self._objects._normalize(
            self._objects._section_kind("metadataPolicies"), stored
        )
        policies = tuple(
            self._objects._metadata_policy_from_value(item)
            for item in self._objects._canonical_objects(revision.document, "metadataPolicies")
        )
        registry = MetadataPolicyRegistry(policies)
        policy = registry.resolve(str(normalized["id"]))
        settings = self._objects._metadata_policy_document(policy)
        readiness = self._metadata_credential_readiness(str(policy.provider_id))
        document: dict[str, object] = {
            "policyId": policy.policy_id,
            "effectiveSettings": settings,
            "credentialReadiness": readiness,
            "mode": "live" if live_metadata else "offline",
            "queryType": policy.query_type.value,
            "verified": False,
        }
        if not live_metadata:
            # Offline success proves local configuration only: it does not prove
            # credentials, connectivity or an identified movie/show.
            document["conclusion"] = "本地配置有效;未验证凭据、连通性或识别结果"
            return AnalysisResult(
                "metadataPolicies",
                object_id,
                "valid",
                "元数据策略本地配置有效(离线,未调用 Provider)",
                result=document,
                message=(
                    "离线检查只证明本地配置;凭据可用性是独立的就绪事实,且未识别任何影片或剧集"
                ),
                next_action=("如需真实识别,请显式启用实时测试;离线成功不构成 Provider 成功"),
            )
        return self._run_live_metadata(revision, policy, stored, object_id, sample, document)

    def _metadata_credential_readiness(self, provider_id: str) -> dict[str, object]:
        return {
            "providerId": provider_id,
            "fields": [
                {
                    "field": field_name,
                    "state": "SET" if os.environ.get(field_name) else "UNSET",
                }
                for field_name in metadata_provider_secret_env_fields(provider_id)
            ],
        }

    def _run_live_metadata(
        self,
        revision: ManagedConfigurationRevision,
        policy: MetadataPolicy,
        stored: Mapping[str, object],
        object_id: str | None,
        sample: Mapping[str, object] | None,
        document: dict[str, object],
    ) -> AnalysisResult:
        """Explicit live test using this candidate policy directly.

        It uses the existing Provider ports with bounded query/path input and does
        not require rule recognition or a type binding.
        """

        if sample is None:
            raise ValueError("live metadata test requires a bounded sample")
        query = sample.get("title") or sample.get("path")
        if not isinstance(query, str) or not query.strip() or len(query) > 512:
            raise ValueError("live metadata test requires a bounded title or path sample")
        factory = self._objects._metadata_provider_registry_factory
        if factory is None:
            return AnalysisResult(
                "metadataPolicies",
                object_id,
                "failed",
                "实时元数据测试未配置 Provider",
                result=document,
                message="本服务未配置可构造的 Metadata Provider",
                next_action="配置被引用的 Provider,然后显式重新运行实时测试",
                failure_category="provider_not_configured",
                provider_calls=0,
            )
        try:
            registry = factory((str(policy.provider_id),))
        except MetadataProviderBootstrapError as error:
            document["failureCategory"] = error.category
            return AnalysisResult(
                "metadataPolicies",
                object_id,
                "failed",
                "实时元数据测试失败:Provider 不可用",
                result=document,
                message=_bounded(error.message, 384),
                next_action=_bounded(error.next_action, 384),
                failure_category=error.category,
                provider_calls=0,
            )
        except Exception as error:
            # Any other construction failure (missing credential, unavailable
            # adapter, …) is reported as an actionable live-test failure rather
            # than surfacing as an opaque server error.
            document["failureCategory"] = "provider_unavailable"
            return AnalysisResult(
                "metadataPolicies",
                object_id,
                "failed",
                "实时元数据测试失败:Provider 不可用",
                result=document,
                message=_bounded(f"{type(error).__name__}", 384),
                next_action="检查被引用 Provider 的部署配置与凭据,然后显式重新运行实时测试",
                failure_category="provider_unavailable",
                provider_calls=0,
            )
        if policy.query_type is MediaQueryType.NONE:
            return AnalysisResult(
                "metadataPolicies",
                object_id,
                "not_applicable",
                "该策略未启用查询,实时测试不适用",
                result=document,
                applicability="not_applicable",
                message="mediaQueryType=none 的策略不会向 Provider 发起查询",
                next_action="如需实时识别,请把查询类型改为 movie、tv 或 auto",
            )
        parsed = MediaParserService().parse(
            FileContext(
                "offline-preview",
                "offline-preview",
                query,
                query,
                (),
                "mkv",
                "",
            )
        )
        recognition_type = RecognitionType("metadata-live-test", "Metadata live test", enabled=True)
        recognition = RecognitionResult(
            recognition_type, "metadata-live-test", 1.0, RecognitionStatus.MATCHED
        )
        try:
            result = MetadataIdentificationService(registry, CandidateMatcher()).identify(
                recognition, parsed, policy
            )
        except Exception as error:  # Provider/transport failure stays bounded
            document["failureCategory"] = "provider_error"
            return AnalysisResult(
                "metadataPolicies",
                object_id,
                "failed",
                "实时元数据测试技术失败",
                result=document,
                message=_bounded(f"{type(error).__name__}", 384),
                next_action="检查 Provider 可用性与凭据,然后显式重新运行实时测试",
                failure_category="provider_error",
                provider_calls=1,
            )
        identity = result.identity
        document["status"] = result.status.value
        document["query"] = _bounded(result.query, 512)
        document["identity"] = (
            {
                "provider": _bounded(identity.provider, 96),
                "providerId": _bounded(identity.provider_id, 128),
                "mediaType": identity.media_type.value,
                "title": _bounded(identity.title, 512),
                "year": identity.canonical_year,
            }
            if identity
            else None
        )
        document["verified"] = identity is not None
        failed = result.status is MetadataIdentificationStatus.PROVIDER_ERROR
        return AnalysisResult(
            "metadataPolicies",
            object_id,
            "failed" if failed else "valid",
            ("实时元数据测试技术失败" if failed else f"实时元数据测试完成:{result.status.value}"),
            result=document,
            message=(
                _bounded(getattr(result.error, "code", "provider_error"), 128)
                if failed
                else "实时测试直接使用本策略的 Provider 端口;它不需要规则识别或类型绑定"
            ),
            next_action=(
                "检查 Provider 凭据/连通性,然后显式重新运行实时测试"
                if failed
                else "核对识别身份;实时结果不改变任何 Active 配置"
            ),
            failure_category="provider_error" if failed else None,
            provider_calls=1,
        )

    # -- NamingPolicy ---------------------------------------------------

    def _analyze_naming_policy(
        self,
        revision: ManagedConfigurationRevision,
        stored: Mapping[str, object] | None,
        object_id: str | None,
        sample: Mapping[str, object] | None,
    ) -> AnalysisResult:
        if stored is None:
            raise ValueError("NamingPolicy candidate is missing")
        if sample is None:
            raise ValueError("NamingPolicy test requires a typed movie/TV sample")
        policies = tuple(
            self._objects._naming_policy(item)
            for item in self._objects._canonical_objects(revision.document, "namingPolicies")
        )
        policy_id = str(stored.get("id"))
        normalized_input, context = self._objects._naming_context(sample)
        result = NamingPreviewService(NamingPolicyRegistry(policies)).preview(context, policy_id)
        missing = [
            warning.split(":", 1)[1]
            for warning in result.warnings
            if warning.startswith("missing_variable:")
        ]
        policy = next(item for item in policies if item.policy_id == policy_id)
        return AnalysisResult(
            "namingPolicies",
            object_id,
            "valid",
            "命名策略在提交样本上渲染成功",
            result={
                "appliedPolicyId": result.policy_id,
                "recognitionType": result.recognition_type_id,
                "mediaType": result.media_type.value if result.media_type else None,
                "directory": "/".join(result.directory_segments),
                "filename": _bounded(result.filename, 512),
                "renderedVariables": {
                    key: _bounded(value, 512)
                    for key, value in result.rendered_variables
                    if key != "episode_numbers"
                },
                "sanitizationChanges": [
                    _bounded(item) for item in result.sanitization_changes[:MAX_ANALYSIS_ITEMS]
                ],
                "missingVariableStrategy": policy.missing_variable_strategy.value,
                "missingVariableDecisions": [
                    {"variable": name, "decision": policy.missing_variable_strategy.value}
                    for name in missing[:MAX_ANALYSIS_ITEMS]
                ],
                "warnings": [_bounded(item, 384) for item in result.warnings[:MAX_ANALYSIS_ITEMS]],
                "inputMode": normalized_input.get("mode"),
            },
            message=(
                "缺少的变量已按配置的缺失变量策略处理"
                if missing
                else "所有被模板消费的变量都有提交值"
            ),
            next_action=(
                "补齐样本字段或调整缺失变量策略,然后显式重新运行"
                if missing
                else "如需确认完整目标路径,请使用完整流程检查"
            ),
        )

    # -- ClassificationPolicy -------------------------------------------

    def _analyze_classification_policy(
        self,
        revision: ManagedConfigurationRevision,
        stored: Mapping[str, object] | None,
        object_id: str | None,
        sample: Mapping[str, object] | None,
    ) -> AnalysisResult:
        if stored is None:
            raise ValueError("ClassificationPolicy candidate is missing")
        if sample is None:
            raise ValueError("ClassificationPolicy test requires a typed identity sample")
        policies = tuple(
            self._objects._classification_policy(item)
            for item in self._objects._canonical_objects(
                revision.document, "classificationPolicies"
            )
        )
        policy_id = str(stored.get("id"))
        _, context = self._objects._classification_context(sample)
        result = ClassificationPreviewService(ClassificationPolicyRegistry(policies)).preview(
            context, policy_id
        )
        libraries = {
            str(item.get("id")): item
            for item in self._objects._canonical_objects(revision.document, "mediaLibraries")
        }
        library = libraries.get(result.media_library_id or "")
        resolved = library is not None
        # This candidate's own rules plus the referenced MediaLibrary and safe
        # relative path.  No Naming, Provider call or Storage probe participates.
        document: dict[str, object] = {
            "appliedPolicyId": result.policy_id,
            "recognitionType": result.recognition_type_id,
            "status": result.status.value,
            "matchedRuleId": result.matched_rule_id,
            "matchedRuleName": _bounded(result.matched_rule_name, 240),
            "mediaLibraryId": result.media_library_id or None,
            "mediaLibraryResolved": resolved,
            "mediaLibraryRootPath": _bounded(library.get("rootPath"), 512) if library else None,
            "relativePath": _bounded(result.relative_path, 1024) or None,
            "destinationContract": (
                "legacy_library_prefix" if result.legacy_destination else "media_library_path"
            ),
            "matchEvidence": [_bounded(item, 384) for item in result.evidence[:MAX_ANALYSIS_ITEMS]],
            "warnings": [_bounded(item, 384) for item in result.warnings[:MAX_ANALYSIS_ITEMS]],
            "evaluatedRules": len(stored.get("rules") or []),
        }
        if result.status is ClassificationStatus.UNCLASSIFIED:
            return AnalysisResult(
                "classificationPolicies",
                object_id,
                "not_matched",
                "没有任何已启用分类规则匹配提交样本",
                result=document,
                message="未匹配是正常结果;它不表示配置损坏",
                next_action="调整规则条件或样本,然后显式重新运行",
            )
        if not resolved:
            return AnalysisResult(
                "classificationPolicies",
                object_id,
                "invalid_input",
                "匹配规则引用的 MediaLibrary 不可解析",
                result=document,
                message=f"MediaLibrary {result.media_library_id!r} 未配置或不可用",
                next_action="添加或修正该 MediaLibrary,然后显式重新运行",
                failure_category="reference_unavailable",
            )
        return AnalysisResult(
            "classificationPolicies",
            object_id,
            "matched",
            f"匹配分类规则,目标库 {result.media_library_id}",
            result=document,
            message="仅评估本候选的策略规则与引用的 MediaLibrary 安全相对路径",
            next_action="如需确认命名与完整目标路径,请使用完整流程检查",
        )

    # -- OrganizePolicy -------------------------------------------------

    def _analyze_organize_policy(
        self,
        revision: ManagedConfigurationRevision,
        stored: Mapping[str, object] | None,
        object_id: str | None,
    ) -> AnalysisResult:
        if stored is None:
            raise ValueError("OrganizePolicy candidate is missing")
        policy: OrganizePolicy = self._objects._organize_policy(stored)
        required = self._objects._required_storage_capabilities(policy)
        warnings = self._objects._organize_policy_warnings(policy)
        return AnalysisResult(
            "organizePolicies",
            object_id,
            "valid",
            "整理策略定义有效",
            result={
                "policyId": policy.policy_id,
                "operation": policy.operation.value,
                "conflictStrategy": policy.conflict_strategy.value,
                "overwriteAuthorized": policy.conflict_strategy.value == "overwrite",
                "deleteAuthorized": (
                    policy.conflict_strategy.value == "overwrite"
                    or policy.source_directory_cleanup.mode.value != "none"
                ),
                "attachments": self._objects._attachment_document(policy),
                "duplicateDetection": self._objects._hash_document(policy),
                "rollback": self._objects._rollback_document(policy),
                "sourceDirectoryCleanup": self._objects._cleanup_document(policy),
                "requiredStorageCapabilities": required,
                "fallback": "none; unsupported capability is a failure",
                "warnings": [_bounded(item, 384) for item in warnings[:MAX_ANALYSIS_ITEMS]],
                # Physical readiness is deliberately unchecked here: only the
                # complete-flow check can observe a real source/destination.
                "physicalReadiness": "未检查",
                "executionReadiness": "未检查",
                "sourceCapability": "未检查",
                "destinationCapability": "未检查",
            },
            message=("本检查只解释预期效果与所需能力;实际源/目标能力、冲突与执行就绪为「未检查」"),
            next_action=("如需真实能力与冲突结论,请使用完整流程检查;本结论不授予执行权限"),
        )

    # ------------------------------------------------------------------
    # Separately labelled complete-flow analysis
    # ------------------------------------------------------------------

    def complete_flow(
        self,
        *,
        revision_id: str,
        resource_library_id: str,
        synthetic_path: str,
        live_metadata: bool = False,
        synthetic_identity: Mapping[str, object] | None = None,
    ) -> AnalysisResult:
        """Run the complete Python chain and report truthful missing-stage blockers."""

        revision = self._objects._managed.require(revision_id)
        try:
            runtime = self._objects._load_runtime_for_analysis(revision)
        except PolicyResolutionError as error:
            # A missing/duplicate/disabled binding is a truthful *binding* blocker,
            # not an opaque whole-graph failure.
            return self._complete_flow_blocker(
                "binding",
                "完整流程缺少可解析的识别类型绑定",
                _bounded(str(error), 384),
                "为该识别类型配置唯一的已启用绑定及其四项策略引用,然后显式重新运行",
            )
        except Exception as error:
            return self._complete_flow_blocker(
                "graph",
                "配置图无法加载,完整流程不可用",
                _bounded(f"{type(error).__name__}", 384),
                "修正报告的整体配置错误,然后显式重新运行完整流程检查",
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
            return self._complete_flow_blocker(
                "source",
                "所选 ResourceLibrary 未知或已停用",
                f"ResourceLibrary {resource_library_id!r} 不可用于完整流程检查",
                "选择一个已启用的 ResourceLibrary,然后显式重新运行",
            )
        identity = self._synthetic_identity(synthetic_identity)
        providers = None
        if live_metadata:
            factory = self._objects._metadata_provider_registry_factory
            if factory is None:
                return self._complete_flow_blocker(
                    "metadata",
                    "实时元数据测试未配置 Provider",
                    "本服务未配置可构造的 Metadata Provider",
                    "配置被引用的 Provider,然后显式重新运行",
                )
            provider_id = self._effective_provider_id(runtime, synthetic_path, library)
            if provider_id is None:
                return self._complete_flow_blocker(
                    "metadata",
                    "无法解析有效的 MetadataPolicy/Provider",
                    "完整流程在识别或策略解析阶段缺少有效引用",
                    "先修正识别与类型绑定,然后显式重新运行",
                )
            try:
                providers = factory((provider_id,))
            except MetadataProviderBootstrapError as error:
                return self._complete_flow_blocker(
                    "metadata", "实时 Provider 不可用", error.message, error.next_action
                )
            except Exception as error:
                return self._complete_flow_blocker(
                    "metadata",
                    "实时 Provider 不可用",
                    _bounded(f"{type(error).__name__}", 384),
                    "检查被引用 Provider 的部署配置与凭据,然后显式重新运行",
                )
        runner = strategy_runner_from_configuration(runtime.strategy, providers)
        try:
            strategy = runner.run_path(
                synthetic_path,
                live_metadata=providers is not None,
                show_naming=True,
                show_classification=True,
                show_plan=True,
                resource_library_id=library.library_id,
                storage_id=library.storage_id,
                synthetic_identity=identity,
            )
        except (StrategyConfigurationError, PolicyResolutionError) as error:
            return self._complete_flow_blocker(
                "binding",
                "完整流程缺少可解析的下游策略绑定",
                _bounded(str(error), 384),
                "补齐该识别类型绑定的下游策略,然后显式重新运行完整流程检查",
            )
        except Exception as error:
            return self._complete_flow_blocker(
                "graph",
                "完整流程执行失败",
                _bounded(f"{type(error).__name__}", 384),
                "修正报告的配置或引用,然后显式重新运行完整流程检查",
            )
        blockers = self._complete_flow_blockers(strategy, live_metadata=providers is not None)
        document = self._objects._strategy_result_document(
            strategy, live_metadata=providers is not None
        )
        document["missingStages"] = [item["stage"] for item in blockers]
        naming = strategy.naming
        document["naming"] = (
            {
                "status": "complete",
                "directory": _bounded(naming.directory, 4096),
                "directorySegments": [
                    _bounded(item, 512) for item in naming.directory_segments[:16]
                ],
                "filename": _bounded(naming.filename, 4096),
                "warnings": [_bounded(item, 384) for item in naming.warnings[:8]],
            }
            if naming is not None
            else {
                "status": "failed" if strategy.naming_error else "missing",
                "message": _bounded(strategy.naming_error, 384),
            }
        )
        classification = strategy.classification
        document["classification"] = (
            {
                "status": classification.status.value,
                "mediaLibraryId": _bounded(classification.media_library_id, 128) or None,
                "relativePath": _bounded(classification.relative_path, 2048),
                "matchedRuleId": _bounded(classification.matched_rule_id, 128) or None,
                "library": _bounded(classification.library, 512) or None,
                "category": _bounded(classification.category, 512) or None,
                "subcategory": _bounded(classification.subcategory, 512) or None,
                "warnings": [_bounded(item, 384) for item in classification.warnings[:8]],
            }
            if classification is not None
            else {
                "status": "failed" if strategy.classification_error else "missing",
                "message": _bounded(strategy.classification_error, 384),
            }
        )
        plan = strategy.organize_plan
        if plan is not None:
            document["plan"] = {
                "target": _bounded(plan.target, 4096),
                "mediaLibraryRoot": _bounded(plan.media_library_root, 1024),
                "relativeDestination": _bounded(plan.relative_destination, 2048),
                "operation": plan.operation.value,
                "status": plan.status.value,
                "conflicts": [
                    {
                        "type": item.conflict_type.value,
                        "source": _bounded(item.source, 1024),
                        "target": _bounded(item.target, 1024),
                        "message": _bounded(item.message, 384),
                    }
                    for item in plan.conflicts[:MAX_ANALYSIS_ITEMS]
                ],
            }
        complete = not blockers and plan is not None
        return AnalysisResult(
            "recognitionRules",
            None,
            "valid" if complete else "invalid_input",
            ("完整流程检查通过:已生成完整整理计划" if complete else "完整流程检查发现缺失阶段"),
            result=document,
            message=(
                "完整流程已完成识别竞争、策略解析、元数据、命名、分类与整理计划"
                if complete
                else "; ".join(item["message"] for item in blockers[:4])
            ),
            next_action=(
                "本地/完整流程检查都不授予执行权限;如需真实整理请使用既有操作流程"
                if complete
                else "按报告补齐缺失阶段,然后显式重新运行完整流程检查"
            ),
            failure_category=None if complete else "incomplete_graph",
            readiness="complete_plan_ready" if complete else "blocked",
            local_only=False,
            identity_status="live_provider" if providers is not None else "synthetic_offline",
            synthetic_identity=providers is None,
            blockers=tuple(blockers),
        )

    def _complete_flow_blockers(
        self, strategy: StrategyTestResult, *, live_metadata: bool
    ) -> list[dict[str, object]]:
        blockers: list[dict[str, object]] = []
        recognition = strategy.recognition
        if recognition.status is RecognitionStatus.UNRECOGNIZED:
            blockers.append(
                {
                    "stage": "recognition",
                    "message": "没有已启用识别规则匹配该路径",
                }
            )
        elif recognition.status is RecognitionStatus.AMBIGUOUS:
            blockers.append(
                {
                    "stage": "recognition",
                    "message": "多个识别类型优先级与分数相同,需要人工判定",
                }
            )
        if strategy.policy is None and recognition.recognition_type_id:
            blockers.append(
                {
                    "stage": "binding",
                    "message": (
                        f"RecognitionType {recognition.recognition_type_id} "
                        "尚未配置可解析的下游绑定"
                    ),
                }
            )
        if recognition.recognition_type_id and strategy.policy is not None:
            metadata = strategy.metadata
            if metadata is None or metadata.identity is None:
                blockers.append(
                    {
                        "stage": "metadata",
                        "message": (
                            "实时元数据未返回身份"
                            if live_metadata
                            else "离线合成身份不可用于该阶段;请显式启用实时元数据或补齐阶段"
                        ),
                    }
                )
            if strategy.naming is None:
                blockers.append(
                    {
                        "stage": "naming",
                        "message": _bounded(strategy.naming_error, 384) or "命名策略未产生结果",
                    }
                )
            if strategy.classification is None or (
                strategy.classification.status is not ClassificationStatus.CLASSIFIED
            ):
                blockers.append(
                    {
                        "stage": "classification",
                        "message": _bounded(strategy.classification_error, 384)
                        or "分类策略未选择 MediaLibrary",
                    }
                )
            if strategy.organize_plan is None:
                blockers.append(
                    {
                        "stage": "organize",
                        "message": _bounded(strategy.plan_error, 384) or "未生成整理计划",
                    }
                )
        return blockers

    @staticmethod
    def _effective_provider_id(
        runtime: RuntimeConfiguration, path: str, library: ResourceLibrary
    ) -> str | None:
        try:
            runner = strategy_runner_from_configuration(runtime.strategy)
            probe = runner.run_path(
                path,
                resource_library_id=library.library_id,
                storage_id=library.storage_id,
            )
        except Exception:
            return None
        return probe.metadata_policy.provider_id if probe.metadata_policy else None

    def _synthetic_identity(self, value: Mapping[str, object] | None) -> MediaIdentity | None:
        if value is None:
            return None
        title = value.get("title")
        if not isinstance(title, str) or not title.strip() or len(title) > 512:
            raise ValueError("synthetic identity requires a bounded non-empty title")
        media_type_value = value.get("mediaType", MediaType.MOVIE.value)
        try:
            media_type = MediaType(media_type_value)
        except (TypeError, ValueError) as error:
            raise ValueError("synthetic identity mediaType must be movie or tv") from error
        return MediaIdentity(
            "synthetic-offline",
            "synthetic",
            media_type,
            title,
            original_title=_bounded(value.get("originalTitle"), 512),
            year=value.get("year") if isinstance(value.get("year"), int) else None,
            season=value.get("season") if isinstance(value.get("season"), int) else None,
            episode=value.get("episode") if isinstance(value.get("episode"), int) else None,
            episode_title=_bounded(value.get("episodeTitle"), 512),
            genres=tuple(str(item) for item in (value.get("genres") or [])[:64]),
            countries=tuple(str(item) for item in (value.get("countries") or [])[:64]),
            languages=tuple(str(item) for item in (value.get("languages") or [])[:64]),
            keywords=tuple(str(item) for item in (value.get("keywords") or [])[:64]),
            overview=_bounded(value.get("overview"), 2000),
        )

    @staticmethod
    def _complete_flow_blocker(
        stage: str, message: str, detail: str | None, next_action: str
    ) -> AnalysisResult:
        return AnalysisResult(
            "recognitionRules",
            None,
            "invalid_input",
            message,
            result={"blockers": [{"stage": stage, "message": _bounded(detail or message, 384)}]},
            message=_bounded(detail or message, 384),
            next_action=_bounded(next_action, 384),
            failure_category="incomplete_graph",
            readiness="blocked",
            local_only=False,
            identity_status="not_reached",
            blockers=({"stage": stage, "message": _bounded(detail or message, 384)},),
        )
